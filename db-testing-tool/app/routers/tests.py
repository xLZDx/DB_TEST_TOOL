"""Test case and test run endpoints."""
import asyncio
import csv
import io
import uuid
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from app.database import get_db, async_session
from app.models.test_case import TestCase, TestRun, TestFolder, TestCaseFolder
from app.models.control_table_training import ControlTableCorrectionRule, ControlTableFileState
from app.models.datasource import DataSource
from app.services.test_generator import generate_tests_for_rule, generate_tests_for_all_rules, preview_tests_for_rule, create_selected_tests
from app.services.test_executor import run_test, run_all_tests
from app.services.control_table_service import (
    analyze_control_table,
    compare_insert_variants,
    apply_compare_decisions,
    apply_sql_variant_preserving_joins,
    dedupe_insert_join_blocks,
    ensure_parallel_hints,
    normalize_insert_source_target_aliases,
    load_target_table_definition,
    build_control_table_ddl,
    _enforce_not_null_in_insert_sql,
    validate_insert_join_aliases,
    extract_sql_expression_map,
    normalize_sql_expr,
)
from app.connectors.factory import get_connector_from_model
from app.services.sql_pattern_validation import validate_sql_pattern
from app.services.training_automation_service import (
    get_training_automation_status,
    start_training_automation_loop,
    stop_training_automation_loop,
    run_training_automation_cycle,
)
from app.config import DATA_DIR
from pydantic import BaseModel
from typing import Optional, List
import re
from datetime import datetime
router = APIRouter(prefix="/api/tests", tags=["tests"])
DEFAULT_TEST_FOLDER_NAME = "All Tests"
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
TRAINING_PACK_ROOT = Path(__file__).resolve().parents[2] / "training_packs"

_batch_control = {}
_batch_tasks = {}


async def _ensure_non_redshift_datasource(db: AsyncSession, datasource_id: int, label: str) -> DataSource:
    ds = await db.get(DataSource, datasource_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"{label} datasource not found")
    if (ds.db_type or "").strip().lower() == "redshift":
        raise HTTPException(status_code=400, detail="Redshift testing is disabled. Use CDS or LH Oracle datasource.")
    return ds


def _extract_target_table_name(target_query: Optional[str], source_query: Optional[str]) -> Optional[str]:
    """Extract target table name from SQL queries, trying multiple sources."""
    # DRD tests: target table is aliased as T (e.g. LEFT JOIN SCHEMA.TABLE T)
    if source_query:
        m = re.search(r'\bLEFT\s+JOIN\s+[\w\.]+\.([\w]+)\s+T\b', source_query, flags=re.IGNORECASE)
        if m:
            return m.group(1)[:255]
        # Row-count / constant tests: FROM SCHEMA.TABLE T
        m = re.search(r'\bFROM\s+[\w\.]+\.([\w]+)\s+T\b', source_query, flags=re.IGNORECASE)
        if m:
            return m.group(1)[:255]
    # Fallback: first FROM/JOIN token in target_query then source_query
    for sql_text in [target_query, source_query]:
        if not sql_text:
            continue
        m = re.search(r'\b(?:FROM|JOIN)\s+(["\w\.]+)', sql_text, flags=re.IGNORECASE)
        if m:
            token = m.group(1).replace('"', '')
            table = token.split('.')[-1]
            if table:
                return table[:255]
    return None


def _normalize_oracle_identifier(name: str) -> str:
    token = (name or "").strip().replace('"', '')
    token = token.replace("`", "")
    token = re.sub(r"[^A-Z0-9_\.]+", "", token.upper())
    token = token.strip(".")
    return token


def _extract_sql_table_tokens(sql_text: str) -> dict:
    sql = str(sql_text or "")
    target_candidates = []
    source_candidates = []

    for patt in [
        r'\bINSERT\s+INTO\s+([A-Z0-9_\."]+)',
        r'\bMERGE\s+INTO\s+([A-Z0-9_\."]+)',
        r'\bUPDATE\s+([A-Z0-9_\."]+)',
    ]:
        for m in re.finditer(patt, sql, flags=re.IGNORECASE):
            token = _normalize_oracle_identifier(m.group(1) or "")
            if token:
                target_candidates.append(token)

    for m in re.finditer(r'\b(?:FROM|JOIN)\s+([A-Z0-9_\."]+)', sql, flags=re.IGNORECASE):
        token = _normalize_oracle_identifier(m.group(1) or "")
        if token:
            source_candidates.append(token)

    return {
        "targets": target_candidates,
        "sources": source_candidates,
    }


def _extract_table_like_tokens_from_text(text: str) -> List[str]:
    txt = str(text or "")
    out = []
    for m in re.finditer(r"\b([A-Z][A-Z0-9_]{2,}(?:\.[A-Z][A-Z0-9_]{2,})?)\b", txt.upper()):
        token = _normalize_oracle_identifier(m.group(1) or "")
        if token:
            out.append(token)
    return out


def _derive_training_context(
    *,
    target_table: str,
    source_tables_csv: str,
    source_sql: str,
    expected_sql: str,
    file_names: List[str],
    file_texts: List[str],
) -> dict:
    explicit_target = _normalize_oracle_identifier(target_table)
    explicit_sources = [
        _normalize_oracle_identifier(item)
        for item in (source_tables_csv or "").split(",")
        if _normalize_oracle_identifier(item)
    ]

    sql_tokens = _extract_sql_table_tokens("\n".join([source_sql or "", expected_sql or ""]))
    text_tokens = _extract_table_like_tokens_from_text("\n".join(file_texts or []))
    name_tokens = _extract_table_like_tokens_from_text("\n".join(file_names or []))

    derived_target = explicit_target
    if not derived_target and sql_tokens["targets"]:
        derived_target = sql_tokens["targets"][0]
    if not derived_target:
        for candidate in text_tokens:
            if "." in candidate:
                derived_target = candidate
                break
    if not derived_target and text_tokens:
        derived_target = text_tokens[0]

    source_candidates = []
    for token in explicit_sources + sql_tokens["sources"] + text_tokens + name_tokens:
        normalized = _normalize_oracle_identifier(token)
        if not normalized:
            continue
        if derived_target and normalized == derived_target:
            continue
        source_candidates.append(normalized)

    deduped_sources = []
    seen = set()
    for token in source_candidates:
        if token in seen:
            continue
        seen.add(token)
        deduped_sources.append(token)

    hints = []
    if derived_target and "." not in derived_target:
        hints.append("Target table has no schema prefix; prefer SCHEMA.TABLE for Oracle execution.")
    if "MERGE" in (source_sql or "").upper():
        hints.append("MERGE detected in source SQL; verify join keys and update clauses against DRD grain.")
    if len(deduped_sources) > 8:
        hints.append("Many source tables detected; keep only DRD-critical tables before training replay.")

    return {
        "target_table": derived_target,
        "source_tables": deduped_sources[:20],
        "oracle_normalized": True,
        "hints": hints,
    }


def _derive_control_suite_base_name(suite_name: Optional[str], tests: List[dict]) -> str:
    requested = (suite_name or "").strip()

    # Prefer explicit target table embedded in generated control-table test names.
    for test_def in tests or []:
        name = (test_def.get("name") or "").strip()
        m = re.search(r"\bfor\s+([A-Z0-9_]+)\s*$", name, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r"^([A-Z0-9_]+):\s+.*control\s+vs\s+target$", name, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()

    return requested or "CONTROL_TABLE_SUITE"


async def _ensure_folder(db: AsyncSession, folder_name: str) -> Optional[TestFolder]:
    name = (folder_name or "").strip()
    if not name:
        return None
    existing = await db.execute(select(TestFolder).where(TestFolder.name == name))
    folder = existing.scalar_one_or_none()
    if folder:
        return folder
    folder = TestFolder(name=name)
    db.add(folder)
    await db.flush()
    return folder


async def _create_new_folder(db: AsyncSession, folder_name: str) -> Optional[TestFolder]:
    name = (folder_name or "").strip()
    if not name:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = TestFolder(name=f"{name}_{timestamp}")
    db.add(folder)
    await db.flush()
    return folder


async def _assign_test_to_folder(db: AsyncSession, test_id: int, folder_id: int):
    existing = await db.execute(select(TestCaseFolder).where(TestCaseFolder.test_case_id == test_id))
    link = existing.scalar_one_or_none()
    if link:
        link.folder_id = folder_id
    else:
        db.add(TestCaseFolder(test_case_id=test_id, folder_id=folder_id))


async def _run_batch_background(batch_id: str, test_ids: Optional[List[int]] = None):
    async with async_session() as db:
        if test_ids:
            tests_r = await db.execute(select(TestCase).where(TestCase.id.in_(test_ids), TestCase.is_active == True))
            tests = tests_r.scalars().all()
        else:
            tests_r = await db.execute(select(TestCase).where(TestCase.is_active == True))
            all_tests = tests_r.scalars().all()
            executed_ids_r = await db.execute(select(TestRun.test_case_id).distinct())
            executed_ids = {row[0] for row in executed_ids_r.all() if row and row[0] is not None}
            tests = [t for t in all_tests if t.id not in executed_ids]
        state = {
            "batch_id": batch_id,
            "status": "running",
            "total": len(tests),
            "completed": 0,
            "passed": 0,
            "failed": 0,
            "error": 0,
            "stopped": False,
            "current_test_number": None,
            "current_test_id": None,
        }
        existing = _batch_control.get(batch_id)
        if existing is not None:
            was_stopped = existing.get("stopped", False)
            existing.update(state)
            existing["stopped"] = was_stopped
            state = existing
        _batch_control[batch_id] = state

        try:
            for idx, test in enumerate(tests, start=1):
                if _batch_control.get(batch_id, {}).get("stopped"):
                    state["status"] = "stopped"
                    break

                state["current_test_number"] = idx
                state["current_test_id"] = test.id

                run = await run_test(db, test.id, batch_id)
                state["completed"] += 1
                state[run.status] = state.get(run.status, 0) + 1
                state["status"] = "running"

            if state["status"] != "stopped":
                state["status"] = "completed"
            state["current_test_number"] = None
            state["current_test_id"] = None
        except asyncio.CancelledError:
            state["stopped"] = True
            state["status"] = "stopped"
            state["current_test_number"] = None
            state["current_test_id"] = None
            raise
        except Exception as e:
            state["status"] = "error"
            state["error"] = state.get("error", 0) + 1
            state["last_error"] = str(e)
            state["current_test_number"] = None
            state["current_test_id"] = None
            raise
        finally:
            _batch_tasks.pop(batch_id, None)


class TestCreate(BaseModel):
    name: str
    test_type: str
    mapping_rule_id: Optional[int] = None
    source_datasource_id: Optional[int] = None
    target_datasource_id: Optional[int] = None
    source_query: Optional[str] = None
    target_query: Optional[str] = None
    expected_result: Optional[str] = None
    tolerance: float = 0.0
    severity: str = "medium"
    description: Optional[str] = None


class RunRequest(BaseModel):
    test_ids: Optional[List[int]] = None


class StartBatchRequest(BaseModel):
    test_ids: Optional[List[int]] = None


class FolderDatasourceUpdateRequest(BaseModel):
    source_datasource_id: Optional[int] = None
    target_datasource_id: Optional[int] = None


class TrainingEventRequest(BaseModel):
    event_type: str
    entity_type: str = ""
    entity_id: Optional[str] = None
    target_table: str = ""
    source: str = ""
    status: str = ""
    details: dict = {}
    knowledge_refs: List[str] = []


class TrainingAutomationRequest(BaseModel):
    interval_seconds: int = 600
    mode: str = "ghc"
    agent_id: Optional[int] = None
    target_table: str = ""
    max_packs_per_cycle: int = 3


# ── Dashboard stats (MUST come before /{test_id}) ───────────────────────────

@router.get("/dashboard-stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_tests = (await db.execute(select(func.count(TestCase.id)))).scalar() or 0
    total_runs = (await db.execute(select(func.count(TestRun.id)))).scalar() or 0
    passed = (await db.execute(
        select(func.count(TestRun.id)).where(TestRun.status == "passed")
    )).scalar() or 0
    failed = (await db.execute(
        select(func.count(TestRun.id)).where(TestRun.status == "failed")
    )).scalar() or 0
    errors = (await db.execute(
        select(func.count(TestRun.id)).where(TestRun.status == "error")
    )).scalar() or 0
    return {
        "total_tests": total_tests,
        "total_runs": total_runs,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": round(passed / total_runs * 100, 1) if total_runs else 0,
    }


# ── Runs / Results (MUST come before /{test_id}) ───────────────────────────

@router.get("/runs")
async def list_runs(batch_id: Optional[str] = None, limit: int = 100,
                    db: AsyncSession = Depends(get_db)):
    q = select(TestRun).order_by(TestRun.id.desc()).limit(limit)
    if batch_id:
        q = q.where(TestRun.batch_id == batch_id)
    result = await db.execute(q)
    runs = result.scalars().all()
    return [
        {
            "id": r.id, "test_case_id": r.test_case_id,
            "batch_id": r.batch_id, "status": r.status,
            "mismatch_count": r.mismatch_count,
            "execution_time_ms": r.execution_time_ms,
            "error_message": r.error_message,
            "actual_result": r.actual_result,
            "executed_at": str(r.executed_at) if r.executed_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(TestRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return {
        "id": r.id, "test_case_id": r.test_case_id,
        "batch_id": r.batch_id, "status": r.status,
        "source_result": r.source_result,
        "target_result": r.target_result,
        "actual_result": r.actual_result,
        "mismatch_count": r.mismatch_count,
        "mismatch_sample": r.mismatch_sample,
        "execution_time_ms": r.execution_time_ms,
        "error_message": r.error_message,
        "executed_at": str(r.executed_at) if r.executed_at else None,
    }


# ── Generation (MUST come before /{test_id}) ───────────────────────────────

@router.post("/generate-all")
async def generate_for_all(connection_id: int = None, db: AsyncSession = Depends(get_db)):
    count = await generate_tests_for_all_rules(db, connection_id)
    if count > 0:
        folder = await _ensure_folder(db, DEFAULT_TEST_FOLDER_NAME)
        if folder:
            all_tests_r = await db.execute(select(TestCase.id))
            all_test_ids = [row[0] for row in all_tests_r.all()]
            linked_r = await db.execute(select(TestCaseFolder.test_case_id))
            linked_ids = {row[0] for row in linked_r.all()}
            for test_id in all_test_ids:
                if test_id not in linked_ids:
                    await _assign_test_to_folder(db, test_id, folder.id)
            await db.commit()
    return {"count": count}


@router.post("/generate/{rule_id}")
async def generate_for_rule(rule_id: int, connection_id: int = None, db: AsyncSession = Depends(get_db)):
    tests = await generate_tests_for_rule(db, rule_id, connection_id)
    folder = await _ensure_folder(db, DEFAULT_TEST_FOLDER_NAME)
    if folder:
        for t in tests:
            await _assign_test_to_folder(db, t.id, folder.id)
        await db.commit()
    return {"count": len(tests), "tests": [{"id": t.id, "name": t.name} for t in tests]}


@router.post("/preview/{rule_id}")
async def preview_for_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    """Preview suggested tests for a rule WITHOUT creating them."""
    defs = await preview_tests_for_rule(db, rule_id)
    return {"tests": defs}


class CreateSelectedRequest(BaseModel):
    tests: List[dict]


class FolderCreateRequest(BaseModel):
    name: str


class MoveTestsToFolderRequest(BaseModel):
    test_ids: List[int]
    folder_id: int


@router.post("/create-selected")
async def create_selected(body: CreateSelectedRequest, db: AsyncSession = Depends(get_db)):
    """Create only the user-selected test definitions."""
    created = await create_selected_tests(db, body.tests)

    # Try to determine folder name from tests' target tables
    folder_name = DEFAULT_TEST_FOLDER_NAME
    if created:
        target_tables = set()
        for t in created:
            # Try extracting from SQL queries first
            tgt_table = _extract_target_table_name(t.target_query, t.source_query)
            # If not found in SQL, try extracting from test name (e.g. "Join Mapping: SRC → TARGET_TABLE")
            if not tgt_table and t.name:
                # "→ SCHEMA.TABLE.COLUMN" or "→ TABLE.COLUMN" in test name
                m = re.search(r'[→>]\s*([\w]+(?:\.[\w]+)*)', t.name)
                if m:
                    parts = m.group(1).split('.')
                    # Last part is column, second-to-last is table (if present)
                    tgt_table = parts[-2] if len(parts) >= 2 else parts[-1]
            if tgt_table:
                target_tables.add(tgt_table)
        if target_tables:
            # Use the most common target table; ties broken alphabetically
            from collections import Counter
            counts = Counter(
                _extract_target_table_name(t.target_query, t.source_query) or DEFAULT_TEST_FOLDER_NAME
                for t in created
            )
            folder_name = counts.most_common(1)[0][0]

    folder = await _create_new_folder(db, folder_name)
    if folder:
        for t in created:
            await _assign_test_to_folder(db, t.id, folder.id)

    await db.commit()
    return {"count": len(created), "tests": [{"id": t.id, "name": t.name} for t in created]}


class ValidateSqlRequest(BaseModel):
    tests: List[dict]
    datasource_id: Optional[int] = None


@router.post("/validate-sql")
async def validate_sql(body: ValidateSqlRequest, db: AsyncSession = Depends(get_db)):
    """Validate SQL syntax for each test via EXPLAIN PLAN before saving.

    Returns a list of results with index, name, and any error message.
    Only Oracle datasources support EXPLAIN PLAN validation; other DB types
    are skipped with ``valid=True``.
    """
    connectors = {}
    ds_cache = {}

    async def _get_connector_for_ds(ds_id: Optional[int]):
        if not ds_id:
            return None
        if ds_id in connectors:
            return connectors[ds_id]
        ds = ds_cache.get(ds_id)
        if not ds:
            ds = await db.get(DataSource, ds_id)
            if not ds:
                return None
            if (ds.db_type or "").strip().lower() == "redshift":
                return None
            ds_cache[ds_id] = ds
        connector = get_connector_from_model(ds)
        if not hasattr(connector, "validate_sql_batch"):
            return None
        await asyncio.to_thread(connector.connect)
        connectors[ds_id] = connector
        return connector

    results = []

    for idx, t in enumerate(body.tests):
        name = t.get("name", "")
        src_sql = (t.get("source_query") or "").strip()
        tgt_sql = (t.get("target_query") or "").strip()
        src_ds_id = t.get("source_datasource_id") or body.datasource_id
        tgt_ds_id = t.get("target_datasource_id") or body.datasource_id

        errs = []
        pattern_src = validate_sql_pattern(src_sql)
        pattern_tgt = validate_sql_pattern(tgt_sql)
        if pattern_src:
            errs.append("source: " + "; ".join(pattern_src))
        if pattern_tgt:
            errs.append("target: " + "; ".join(pattern_tgt))

        if src_sql and not pattern_src:
            src_connector = await _get_connector_for_ds(int(src_ds_id) if src_ds_id else None)
            if src_connector:
                src_err = (await asyncio.to_thread(src_connector.validate_sql_batch, [src_sql]))[0]
                if src_err:
                    errs.append("source: " + str(src_err))

        if tgt_sql and not pattern_tgt:
            tgt_connector = await _get_connector_for_ds(int(tgt_ds_id) if tgt_ds_id else None)
            if tgt_connector:
                tgt_err = (await asyncio.to_thread(tgt_connector.validate_sql_batch, [tgt_sql]))[0]
                if tgt_err:
                    errs.append("target: " + str(tgt_err))

        results.append({
            "index": idx,
            "name": name,
            "valid": len(errs) == 0,
            "error": " | ".join(errs) if errs else None,
        })

    for conn in connectors.values():
        try:
            await asyncio.to_thread(conn.disconnect)
        except Exception:
            pass

    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = sum(1 for r in results if not r["valid"])
    return {"results": results, "valid_count": valid_count, "invalid_count": invalid_count}


class ExportTfsCsvRequest(BaseModel):
    test_ids: List[int]
    area_path: str = ""
    assigned_to: str = ""
    state: str = "Design"


@router.post("/export-tfs-csv")
async def export_tfs_csv(body: ExportTfsCsvRequest, db: AsyncSession = Depends(get_db)):
    """Export selected tests as a TFS-importable CSV file.

    Each test becomes a Test Case header row followed by step rows for each SQL query.
    """
    tests = []
    for test_id in body.test_ids:
        tc = await db.get(TestCase, test_id)
        if tc:
            tests.append(tc)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["ID", "Work Item Type", "Title", "Test Step", "Step Action", "Step Expected", "Area Path", "Assigned To", "State"])

    for t in tests:
        # Test Case header row
        writer.writerow(["", "Test Case", t.name or "", "", "", "", body.area_path, body.assigned_to, body.state])
        step = 1
        if t.source_query:
            writer.writerow(["", "", "", str(step), t.source_query, t.expected_result or "", "", "", ""])
            step += 1
        if t.target_query:
            writer.writerow(["", "", "", str(step), t.target_query, "", "", "", ""])

    csv_bytes = output.getvalue().encode("utf-8-sig")  # utf-8-sig adds BOM for Excel compatibility
    filename = f"tfs_tests_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/control-table/analyze")
async def analyze_control_table_from_drd(
    file: UploadFile = File(...),
    target_schema: str = Form(...),
    target_table: str = Form(...),
    source_datasource_id: int = Form(...),
    target_datasource_id: Optional[int] = Form(None),
    control_schema: str = Form("ikorostelev"),
    main_grain: str = Form(""),
    manual_sql: str = Form(""),
    selected_fields: List[str] = Form([]),
    sheet_name: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "File must be CSV or Excel format")
    resolved_target_datasource_id = target_datasource_id or source_datasource_id
    await _ensure_non_redshift_datasource(db, source_datasource_id, "Source")
    await _ensure_non_redshift_datasource(db, resolved_target_datasource_id, "Target")
    file_bytes = await file.read()
    fingerprint = _file_fingerprint(file_bytes)
    try:
        result = analyze_control_table(
            file_bytes=file_bytes,
            filename=file.filename,
            target_schema=target_schema,
            target_table=target_table,
            source_datasource_id=source_datasource_id,
            target_datasource_id=resolved_target_datasource_id,
            control_schema=control_schema.upper(),
            main_grain=main_grain,
            manual_sql=manual_sql,
            selected_fields=selected_fields or None,
            sheet_name=sheet_name.strip() or None,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Analysis error: {exc}") from exc
    result["generated_insert_sql"] = normalize_insert_source_target_aliases(
        dedupe_insert_join_blocks(result.get("generated_insert_sql", ""))
    )

    target_table_u = (target_table or "").strip().upper()
    rules = await _load_training_rules(db, target_table_u)

    def _build_rule_decisions(sql_text: str) -> list:
        """Compare current SQL against rules and build decision list with old expressions for JOIN fixes."""
        cmp = compare_insert_variants(
            result.get("analysis_rows", []),
            sql_text,
            manual_sql or "",
            compare_mode="all",
        )
        cmp = _apply_training_rules_to_comparison(cmp, rules)
        decisions = []
        for row in cmp.get("rows", []) or []:
            if (row.get("recommended_source") or "").strip().lower() == "rule":
                expr = (row.get("rule_expression") or "").strip()
                col = row.get("column")
                if expr and col:
                    decisions.append({
                        "column": col,
                        "expression": expr,
                        "old_expression": (row.get("generated_expression") or "").strip(),
                        "source_attribute": (row.get("source_attribute") or "").strip(),
                    })
        return decisions

    # Auto-apply only confirmed training-rule corrections (not generic DRD/manual suggestions).
    if rules:
        decisions = _build_rule_decisions(result.get("generated_insert_sql", ""))
        if decisions:
            result["generated_insert_sql"] = dedupe_insert_join_blocks(
                apply_compare_decisions(result.get("generated_insert_sql", ""), decisions)
            )

    # Restore exact previously fixed SQL for the same file content.
    state_restored = False
    restored_state = await _load_file_state(db, target_table_u, fingerprint)
    if restored_state and (restored_state.final_insert_sql or "").strip():
        result["generated_insert_sql"] = normalize_insert_source_target_aliases(
            dedupe_insert_join_blocks(restored_state.final_insert_sql)
        )
        state_restored = True
        # Re-apply training rules on top of restored state.  Restored SQL may
        # have been saved before a rule was created, so rules must win.
        if rules:
            decisions = _build_rule_decisions(result.get("generated_insert_sql", ""))
            if decisions:
                result["generated_insert_sql"] = dedupe_insert_join_blocks(
                    apply_compare_decisions(result.get("generated_insert_sql", ""), decisions)
                )

    # Rebuild comparison after auto-applies/restores so UI sees current state.
    comparison = compare_insert_variants(
        result.get("analysis_rows", []),
        result.get("generated_insert_sql", ""),
        manual_sql or "",
        compare_mode="all",
    )
    result["comparison"] = _apply_training_rules_to_comparison(comparison, rules)
    result["file_fingerprint"] = fingerprint
    result["state_restored"] = state_restored
    result["state_file_name"] = restored_state.file_name if restored_state else ""
    # Post-generation join alias validation
    result["join_alias_issues"] = validate_insert_join_aliases(result.get("generated_insert_sql", ""))
    return result


class ControlTableCompareRequest(BaseModel):
    analysis_rows: List[dict]
    generated_sql: str
    manual_sql: str = ""
    target_table: str = ""
    compare_mode: str = "all"


class ControlTableEmptyRequest(BaseModel):
    target_datasource_id: int
    target_schema: str
    target_table: str
    control_schema: str = "ikorostelev"


class ControlTableSaveSuiteRequest(BaseModel):
    suite_name: str
    tests: List[dict]


class ControlTableFeedbackRequest(BaseModel):
    target_table: str
    target_column: str
    issue_type: str = ""
    source_attribute: str = ""
    recommended_source: str = "drd"
    chosen_expression: str = ""
    notes: str = ""


class ControlTableReplayRequest(BaseModel):
    target_schema: str
    target_table: str
    source_datasource_id: int
    target_datasource_id: int
    control_schema: str = "ikorostelev"
    main_grain: str = ""
    fixture_files: List[str] = []


async def _delete_folder_with_children(db: AsyncSession, folder_id: int) -> dict:
    folder = await db.get(TestFolder, folder_id)
    if not folder:
        return {"deleted": False, "folder_id": folder_id, "tests_deleted": 0, "runs_deleted": 0}

    links_q = await db.execute(select(TestCaseFolder.test_case_id).where(TestCaseFolder.folder_id == folder_id))
    test_ids = [row[0] for row in links_q.all() if row and row[0] is not None]

    runs_deleted = 0
    tests_deleted = 0
    if test_ids:
        runs_res = await db.execute(delete(TestRun).where(TestRun.test_case_id.in_(test_ids)))
        tests_res = await db.execute(delete(TestCase).where(TestCase.id.in_(test_ids)))
        runs_deleted = runs_res.rowcount or 0
        tests_deleted = tests_res.rowcount or 0

    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.folder_id == folder_id))
    await db.delete(folder)
    return {
        "deleted": True,
        "folder_id": folder_id,
        "tests_deleted": tests_deleted,
        "runs_deleted": runs_deleted,
    }


async def _load_training_rules(db: AsyncSession, target_table: str) -> List[ControlTableCorrectionRule]:
    target = (target_table or "").strip().upper()
    bare = target.rsplit(".", 1)[-1] if "." in target else target
    from sqlalchemy import or_
    result = await db.execute(
        select(ControlTableCorrectionRule)
        .where(or_(
            ControlTableCorrectionRule.target_table == target,
            ControlTableCorrectionRule.target_table == bare,
        ))
        .order_by(ControlTableCorrectionRule.updated_at.desc())
    )
    return result.scalars().all()


def _file_fingerprint(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes or b"").hexdigest()


async def _load_file_state(db: AsyncSession, target_table: str, file_fingerprint: str) -> Optional[ControlTableFileState]:
    target = (target_table or "").strip().upper()
    fingerprint = (file_fingerprint or "").strip().lower()
    if not target or not fingerprint:
        return None
    result = await db.execute(
        select(ControlTableFileState).where(
            ControlTableFileState.target_table == target,
            ControlTableFileState.file_fingerprint == fingerprint,
        )
    )
    return result.scalar_one_or_none()


async def _upsert_file_state(
    db: AsyncSession,
    *,
    target_table: str,
    file_name: str,
    file_fingerprint: str,
    final_insert_sql: str,
    decisions: List[dict],
) -> None:
    target = (target_table or "").strip().upper()
    fingerprint = (file_fingerprint or "").strip().lower()
    final_sql = (final_insert_sql or "").strip()
    if not target or not fingerprint or not final_sql:
        return

    state = await _load_file_state(db, target, fingerprint)
    decisions_text = json.dumps(decisions or [], ensure_ascii=True)
    if not state:
        db.add(
            ControlTableFileState(
                target_table=target,
                file_name=(file_name or "").strip() or None,
                file_fingerprint=fingerprint,
                final_insert_sql=final_sql,
                last_applied_decisions=decisions_text,
            )
        )
        return

    state.file_name = (file_name or "").strip() or state.file_name
    state.final_insert_sql = final_sql
    state.last_applied_decisions = decisions_text


def _rule_for_row(row: dict, rules: List[ControlTableCorrectionRule]) -> Optional[ControlTableCorrectionRule]:
    """Return the best saved rule for a comparison row.

    A rule MUST match by target_column (exact). issue_type and source_attribute
    are only used as tiebreakers when multiple rules share the same column name.
    This prevents a rule saved for column X from leaking into unrelated columns
    that happen to share the same issue_type or source_attribute.
    """
    col = (row.get("column") or "").strip().upper()
    if not col:
        return None
    src = (row.get("source_attribute") or "").strip().upper()
    status = (row.get("status") or "").strip().lower()
    best: Optional[ControlTableCorrectionRule] = None
    best_score = -1
    for rule in rules:
        # target_column match is mandatory — no match means this rule does not apply.
        if (rule.target_column or "").strip().upper() != col:
            continue
        score = 5  # base score for target_column match
        if (rule.source_attribute or "").strip().upper() and (rule.source_attribute or "").strip().upper() == src:
            score += 3
        if (rule.issue_type or "").strip().lower() and (rule.issue_type or "").strip().lower() == status:
            score += 2
        if score > best_score:
            best = rule
            best_score = score
    return best


def _apply_training_rules_to_comparison(comparison: dict, rules: List[ControlTableCorrectionRule]) -> dict:
    rows = comparison.get("rows") or []
    for row in rows:
        rule = _rule_for_row(row, rules)
        if not rule:
            continue
        row["training_rule_id"] = rule.id
        row["training_rule_notes"] = rule.notes or ""
        if (rule.replacement_expression or "").strip():
            row["rule_expression"] = rule.replacement_expression
            row["recommended_source"] = "rule"
        elif (rule.recommended_source or "").strip().lower() in {"generated", "manual", "drd"}:
            row["recommended_source"] = rule.recommended_source.strip().lower()
    return comparison


def _serialize_training_rule(rule: ControlTableCorrectionRule) -> dict:
    return {
        "id": rule.id,
        "target_table": rule.target_table,
        "target_column": rule.target_column,
        "issue_type": rule.issue_type,
        "source_attribute": rule.source_attribute,
        "recommended_source": rule.recommended_source,
        "replacement_expression": rule.replacement_expression,
        "notes": rule.notes,
        "created_at": str(rule.created_at) if rule.created_at else None,
        "updated_at": str(rule.updated_at) if rule.updated_at else None,
    }


@router.post("/control-table/preview-drd")
async def preview_control_table_drd(
    file: UploadFile = File(...),
    sheet_name: str = Form(""),
):
    """Preview DRD file: return sheet list, metadata, headers, sample rows."""
    from app.services.drd_import_service import preview_file, extract_drd_metadata, read_excel_all_sheets
    file_bytes = await file.read()
    filename = file.filename or "file.xlsx"
    result = preview_file(file_bytes, filename, sheet_name=sheet_name.strip() or None)
    # For Excel files, add all sheet names + per-sheet metadata
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("xlsx", "xls"):
        try:
            all_sheets = read_excel_all_sheets(file_bytes)
            sheet_infos = []
            for sn, rows in all_sheets.items():
                meta = extract_drd_metadata(file_bytes, filename, sheet_name=sn)
                row_count = len(rows)
                sheet_infos.append({"name": sn, "row_count": row_count, "metadata": meta})
            result["sheet_details"] = sheet_infos
        except Exception:
            pass
    return result


@router.post("/control-table/empty")
async def build_empty_control_table(body: ControlTableEmptyRequest):
    target_definition = load_target_table_definition(
        body.target_datasource_id,
        body.target_schema,
        body.target_table,
    )
    return {
        "target_definition": target_definition,
        "create_table_sql": build_control_table_ddl(body.control_schema.upper(), body.target_table, target_definition),
    }


@router.post("/control-table/compare")
async def compare_control_table_sql(body: ControlTableCompareRequest, db: AsyncSession = Depends(get_db)):
    comparison = compare_insert_variants(
        body.analysis_rows,
        body.generated_sql,
        body.manual_sql,
        compare_mode=(body.compare_mode or "all"),
    )
    target_table = (body.target_table or "").strip().upper()
    if not target_table:
        for row in body.analysis_rows or []:
            if (row.get("column") or "").strip():
                candidate = (row.get("target_table") or row.get("table") or "").strip().upper()
                if candidate:
                    target_table = candidate
                    break
    if not target_table:
        m = re.search(r"\bINSERT\s+INTO\s+[A-Z0-9_\.]+\.([A-Z0-9_]+)\b", body.generated_sql or "", flags=re.IGNORECASE)
        if m:
            target_table = m.group(1).upper()
    if target_table:
        rules = await _load_training_rules(db, target_table)
        comparison = _apply_training_rules_to_comparison(comparison, rules)
    return comparison


class ControlTableApplyRequest(BaseModel):
    base_sql: str
    decisions: List[dict]
    target_table: str = ""
    file_fingerprint: str = ""
    file_name: str = ""


class ControlTableInsertCheckRequest(BaseModel):
    target_datasource_id: int
    sql: str
    execute: bool = False


class ControlTableApplySqlRequest(BaseModel):
    base_sql: str
    variant_sql: str


class ControlTableSaveInsertStateRequest(BaseModel):
    target_table: str
    file_fingerprint: str = ""
    file_name: str = ""
    sql: str
    decisions: List[dict] = []


def _split_sql_columns(clause: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    for ch in clause or "":
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            continue
        if not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue
        current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _parse_insert_select_pairs(sql: str) -> List[dict]:
    text = str(sql or "")
    m = re.search(
        r"\bINSERT\b.*?\bINTO\b\s+([A-Z0-9_\.\"]+)\s*\((?P<cols>.*?)\)\s*\bSELECT\b(?P<select>.*?)\bFROM\b",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    cols = [c.strip().replace('"', '').split('.')[-1].upper() for c in _split_sql_columns(m.group("cols") or "") if c.strip()]
    exprs = _split_sql_columns(m.group("select") or "")
    pairs: List[dict] = []
    for idx, col in enumerate(cols):
        if idx >= len(exprs):
            break
        pairs.append({"column": col, "expression": (exprs[idx] or "").strip()})
    return pairs


def _is_nullable_column(col_obj) -> bool:
    for attr in ("nullable", "is_nullable", "null_ok"):
        val = getattr(col_obj, attr, None)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            txt = val.strip().upper()
            if txt in {"Y", "YES", "TRUE", "1"}:
                return True
            if txt in {"N", "NO", "FALSE", "0"}:
                return False
    return True


def _column_data_type(col_obj) -> str:
    return str(getattr(col_obj, "data_type", "") or getattr(col_obj, "type_name", "") or "").upper()


def _extract_table_aliases(sql: str) -> List[dict]:
    refs: List[dict] = []
    text = (sql or "")
    patt = re.compile(
        r'\b(FROM|JOIN|INTO)\s+([A-Z0-9_\.\"]+)(?:\s+([A-Z][A-Z0-9_]*))?',
        flags=re.IGNORECASE,
    )
    for m in patt.finditer(text):
        raw = (m.group(2) or "").strip()
        if not raw or raw.startswith("("):
            continue
        token = raw.replace('"', '')
        parts = token.split('.')
        schema = parts[-2].upper() if len(parts) >= 2 else ""
        table = parts[-1].upper()
        alias = (m.group(3) or "").strip().upper() or table
        refs.append({"schema": schema, "table": table, "alias": alias})
    return refs


def _analyze_sql_references(connector, sql: str) -> dict:
    refs = _extract_table_aliases(sql)
    alias_map = {r["alias"]: (r["schema"], r["table"]) for r in refs if r.get("alias")}

    missing_tables: List[dict] = []
    for r in refs:
        schema = r.get("schema") or ""
        table = r.get("table") or ""
        if not schema or not table:
            continue
        try:
            exists = connector.table_exists(schema, table)
        except Exception:
            exists = True
        if not exists:
            missing_tables.append({"schema": schema, "table": table})

    columns_cache: dict = {}
    missing_columns: List[dict] = []

    insert_target_schema = ""
    insert_target_table = ""
    insert_target_columns: List[str] = []
    insert_match = re.search(
        r"\bINSERT\b.*?\bINTO\b\s+([A-Z0-9_\.\"]+)\s*\((?P<cols>.*?)\)\s*\bSELECT\b",
        (sql or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if insert_match:
        token = (insert_match.group(1) or "").replace('"', '').strip()
        parts = token.split('.')
        insert_target_schema = parts[-2].upper() if len(parts) >= 2 else ""
        insert_target_table = parts[-1].upper() if parts else ""
        insert_target_columns = [
            c.strip().replace('"', '').split('.')[-1].upper()
            for c in re.split(r",", insert_match.group("cols") or "")
            if c.strip()
        ]
    for m in re.finditer(r"\b([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_\$#]*)\b", (sql or ""), flags=re.IGNORECASE):
        alias = (m.group(1) or "").upper()
        col = (m.group(2) or "").upper()
        if alias not in alias_map:
            continue
        schema, table = alias_map[alias]
        if not schema or not table:
            continue
        cache_key = (schema, table)
        if cache_key not in columns_cache:
            try:
                cols = connector.get_columns(schema, table)
                columns_cache[cache_key] = {c.column_name.upper() for c in cols}
            except Exception:
                columns_cache[cache_key] = set()
        if columns_cache[cache_key] and col not in columns_cache[cache_key]:
            missing_columns.append({"schema": schema, "table": table, "column": col, "alias": alias})

    if insert_target_schema and insert_target_table and insert_target_columns:
        cache_key = (insert_target_schema, insert_target_table)
        if cache_key not in columns_cache:
            try:
                cols = connector.get_columns(insert_target_schema, insert_target_table)
                columns_cache[cache_key] = {c.column_name.upper() for c in cols}
            except Exception:
                columns_cache[cache_key] = set()
        if columns_cache[cache_key]:
            for col in insert_target_columns:
                if col not in columns_cache[cache_key]:
                    missing_columns.append({
                        "schema": insert_target_schema,
                        "table": insert_target_table,
                        "column": col,
                        "alias": "INSERT_TARGET",
                    })

    unknown_aliases: List[dict] = []
    for m in re.finditer(r"\b([A-Z_][A-Z0-9_]*)\.([A-Z_][A-Z0-9_\$#]*)\b", (sql or ""), flags=re.IGNORECASE):
        alias = (m.group(1) or "").upper()
        if alias in alias_map:
            continue
        if alias in {"SYS", "DUAL"}:
            continue
        unknown_aliases.append({"alias": alias, "column": (m.group(2) or "").upper()})

    not_null_risks: List[dict] = []
    datatype_risks: List[dict] = []
    if insert_target_schema and insert_target_table and hasattr(connector, "get_columns"):
        try:
            target_cols = connector.get_columns(insert_target_schema, insert_target_table)
            target_map = {str(c.column_name).upper(): c for c in target_cols}
            for pair in _parse_insert_select_pairs(sql):
                col_name = (pair.get("column") or "").upper()
                expr = (pair.get("expression") or "").strip()
                col_obj = target_map.get(col_name)
                if not col_obj:
                    continue
                nullable = _is_nullable_column(col_obj)
                dtype = _column_data_type(col_obj)
                expr_u = expr.upper()
                expr_core = re.sub(r"\s+AS\s+[A-Z0-9_]+\s*$", "", expr_u, flags=re.IGNORECASE).strip()

                if not nullable and (
                    expr_core == "NULL"
                    or " ELSE NULL" in expr_u
                    or re.search(r"\bTHEN\s+NULL\b", expr_u)
                ):
                    not_null_risks.append({
                        "schema": insert_target_schema,
                        "table": insert_target_table,
                        "column": col_name,
                        "expression": expr,
                        "data_type": dtype,
                    })

                if any(tok in dtype for tok in ("NUMBER", "INTEGER", "DECIMAL", "FLOAT")):
                    if re.search(r"^'[^']*'$", expr.strip()):
                        datatype_risks.append({
                            "schema": insert_target_schema,
                            "table": insert_target_table,
                            "column": col_name,
                            "expected": dtype,
                            "expression": expr,
                            "issue": "numeric_column_has_string_literal",
                        })
                if any(tok in dtype for tok in ("DATE", "TIMESTAMP")):
                    if re.search(r"^'[^']*'$", expr.strip()) and "TO_DATE(" not in expr_u and "TO_TIMESTAMP(" not in expr_u:
                        datatype_risks.append({
                            "schema": insert_target_schema,
                            "table": insert_target_table,
                            "column": col_name,
                            "expected": dtype,
                            "expression": expr,
                            "issue": "date_column_has_plain_string_literal",
                        })
        except Exception:
            pass

    suggestions: List[str] = []
    for t in missing_tables:
        suggestions.append(f"Table not found: {t['schema']}.{t['table']}. Verify schema/table name in FROM/JOIN/INTO or choose correct datasource.")
    for c in missing_columns:
        suggestions.append(f"Column not found: {c['schema']}.{c['table']}.{c['column']} (alias {c['alias']}). Fix attribute name or lookup join/table.")
    for a in unknown_aliases:
        suggestions.append(f"Alias mismatch: {a['alias']}.{a['column']} is used in SELECT/WHERE but alias {a['alias']} is not present in FROM/JOIN.")
    for r in not_null_risks:
        suggestions.append(f"NOT NULL risk: {r['schema']}.{r['table']}.{r['column']} cannot be NULL but expression may resolve to NULL. Provide a non-null expression with correct type.")
    for r in datatype_risks:
        suggestions.append(f"Datatype risk: {r['schema']}.{r['table']}.{r['column']} expects {r['expected']} but expression looks incompatible ({r['issue']}).")

    return {
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "unknown_aliases": unknown_aliases,
        "not_null_risks": not_null_risks,
        "datatype_risks": datatype_risks,
        "suggestions": suggestions,
    }


def _build_sql_error_suggestions(error_text: str, diagnostics: dict) -> List[str]:
    suggestions = list((diagnostics or {}).get("suggestions") or [])
    err = str(error_text or "")
    invalid_col = re.search(r'ORA-00904:\s*"?([A-Z0-9_\$#]+)"?: invalid identifier', err, flags=re.IGNORECASE)
    if invalid_col:
        suggestions.append(
            f"Oracle invalid identifier: {invalid_col.group(1)}. Check column name spelling, alias context, or lookup table for that attribute."
        )
    missing_tbl = re.search(r'ORA-00942: table or view does not exist', err, flags=re.IGNORECASE)
    if missing_tbl:
        suggestions.append("Oracle could not find a table/view referenced by the SQL. Verify schema.table names and datasource selection.")
    missing_seq = re.search(r'ORA-02289: sequence does not exist', err, flags=re.IGNORECASE)
    if missing_seq:
        suggestions.append("A referenced sequence does not exist. Check sequence schema/name or replace with the correct load logic.")
    return suggestions


@router.post("/control-table/apply")
async def apply_control_table_decisions(body: ControlTableApplyRequest, db: AsyncSession = Depends(get_db)):
    sql = normalize_insert_source_target_aliases(
        dedupe_insert_join_blocks(ensure_parallel_hints(apply_compare_decisions(body.base_sql, body.decisions)))
    )
    await _upsert_file_state(
        db,
        target_table=body.target_table,
        file_name=body.file_name,
        file_fingerprint=body.file_fingerprint,
        final_insert_sql=sql,
        decisions=body.decisions,
    )
    await db.commit()
    return {"sql": sql}


@router.post("/control-table/apply-sql")
async def apply_control_table_sql_variant(body: ControlTableApplySqlRequest):
    sql = normalize_insert_source_target_aliases(
        dedupe_insert_join_blocks(ensure_parallel_hints(apply_sql_variant_preserving_joins(body.base_sql, body.variant_sql)))
    )
    return {"sql": sql}


@router.post("/control-table/save-insert-state")
async def save_control_table_insert_state(body: ControlTableSaveInsertStateRequest, db: AsyncSession = Depends(get_db)):
    target_table = (body.target_table or "").strip().upper()
    sql = normalize_insert_source_target_aliases(
        dedupe_insert_join_blocks(ensure_parallel_hints((body.sql or "").strip()))
    )
    fingerprint = (body.file_fingerprint or "").strip().lower() or hashlib.sha256(sql.encode("utf-8")).hexdigest()
    if not target_table:
        raise HTTPException(status_code=400, detail="target_table is required")
    if not sql:
        raise HTTPException(status_code=400, detail="sql is required")

    await _upsert_file_state(
        db,
        target_table=target_table,
        file_name=(body.file_name or "").strip(),
        file_fingerprint=fingerprint,
        final_insert_sql=sql,
        decisions=body.decisions or [],
    )
    await db.commit()
    return {"saved": True, "target_table": target_table, "sql": sql}


@router.post("/control-table/check-insert")
async def check_control_table_insert_sql(body: ControlTableInsertCheckRequest, db: AsyncSession = Depends(get_db)):
    ds = await _ensure_non_redshift_datasource(db, body.target_datasource_id, "Target")
    sql = (body.sql or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="sql is required")

    connector = get_connector_from_model(ds)
    try:
        connector.connect()
        diagnostics = _analyze_sql_references(connector, sql)

        # Auto-fix NOT NULL risks: build a target_definition from live connector metadata
        # and apply _enforce_not_null_in_insert_sql to the input SQL.
        auto_fixed_sql = sql
        if diagnostics.get("not_null_risks"):
            target_insert_schema = ""
            target_insert_table = ""
            ins_m = re.search(
                r'\bINSERT\b.*?\bINTO\b\s+([A-Z0-9_\.\"]+)\s*\(',
                sql, flags=re.IGNORECASE | re.DOTALL,
            )
            if ins_m:
                token = (ins_m.group(1) or "").replace('"', '').strip()
                parts = token.split('.')
                target_insert_schema = parts[-2].upper() if len(parts) >= 2 else ""
                target_insert_table = parts[-1].upper() if parts else ""
            if target_insert_schema and target_insert_table:
                try:
                    cols = connector.get_columns(target_insert_schema, target_insert_table)
                    synthetic_def: dict = {
                        "columns": [
                            {
                                "name": c.column_name,
                                "data_type": getattr(c, "data_type", "VARCHAR2"),
                                "nullable": getattr(c, "nullable", True),
                                "is_pk": getattr(c, "is_pk", False),
                            }
                            for c in cols
                        ],
                        "primary_keys": [c.column_name for c in cols if getattr(c, "is_pk", False)],
                    }
                    auto_fixed_sql = _enforce_not_null_in_insert_sql(sql, synthetic_def)
                except Exception:
                    pass

        if body.execute:
            try:
                result = connector.execute_query(sql)
                return {
                    "ok": True,
                    "mode": "execute",
                    "message": "SQL script executed successfully.",
                    "rows_returned": len(result or []),
                    "diagnostics": diagnostics,
                    "auto_fixed_sql": auto_fixed_sql if auto_fixed_sql != sql else None,
                }
            except Exception as e:
                return {
                    "ok": False,
                    "mode": "execute",
                    "error": str(e),
                    "diagnostics": diagnostics,
                    "suggestions": _build_sql_error_suggestions(str(e), diagnostics),
                    "auto_fixed_sql": auto_fixed_sql if auto_fixed_sql != sql else None,
                }

        err = connector.validate_sql(sql)
        if err:
            return {
                "ok": False,
                "mode": "validate",
                "error": err,
                "diagnostics": diagnostics,
                "suggestions": _build_sql_error_suggestions(err, diagnostics),
                "auto_fixed_sql": auto_fixed_sql if auto_fixed_sql != sql else None,
            }
        return {
            "ok": True,
            "mode": "validate",
            "message": "SQL validation passed.",
            "diagnostics": diagnostics,
            "auto_fixed_sql": auto_fixed_sql if auto_fixed_sql != sql else None,
        }
    finally:
        try:
            connector.disconnect()
        except Exception:
            pass


@router.delete("/control-table/file-state")
async def clear_control_table_file_state(
    target_table: str,
    file_fingerprint: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Delete the persisted file+fix state for a given table (optionally scoped to a fingerprint)."""
    table_u = (target_table or "").strip().upper()
    if not table_u:
        raise HTTPException(status_code=400, detail="target_table is required")
    from sqlalchemy import delete as sa_delete
    if file_fingerprint.strip():
        stmt = sa_delete(ControlTableFileState).where(
            ControlTableFileState.target_table == table_u,
            ControlTableFileState.file_fingerprint == file_fingerprint.strip().lower(),
        )
    else:
        stmt = sa_delete(ControlTableFileState).where(
            ControlTableFileState.target_table == table_u,
        )
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount, "target_table": table_u}


@router.post("/control-table/save-suite")
async def save_control_table_suite(body: ControlTableSaveSuiteRequest, db: AsyncSession = Depends(get_db)):
    base_name = _derive_control_suite_base_name(body.suite_name, body.tests)
    folder = await _create_new_folder(db, base_name)
    created = []
    for test_def in body.tests:
        tc = TestCase(
            name=test_def["name"],
            test_type=test_def["test_type"],
            mapping_rule_id=test_def.get("mapping_rule_id"),
            source_datasource_id=test_def.get("source_datasource_id"),
            target_datasource_id=test_def.get("target_datasource_id"),
            source_query=test_def.get("source_query"),
            target_query=test_def.get("target_query"),
            expected_result=test_def.get("expected_result"),
            severity=test_def.get("severity", "medium"),
            description=test_def.get("description"),
            is_active=test_def.get("is_active", True),
        )
        db.add(tc)
        await db.flush()
        if folder:
            await _assign_test_to_folder(db, tc.id, folder.id)
        created.append(tc)
    await db.commit()
    return {
        "count": len(created),
        "suite_name": folder.name if folder else body.suite_name,
        "folder_id": folder.id if folder else None,
        "tests": [{"id": t.id, "name": t.name} for t in created],
    }


@router.get("/control-table/training/rules")
async def list_control_table_training_rules(target_table: str, db: AsyncSession = Depends(get_db)):
    rules = await _load_training_rules(db, target_table)
    return {"target_table": target_table.strip().upper(), "rules": [_serialize_training_rule(r) for r in rules]}


@router.delete("/control-table/training/rules/{rule_id}")
async def delete_training_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(ControlTableCorrectionRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True, "id": rule_id}


@router.put("/control-table/training/rules/{rule_id}")
async def update_training_rule(rule_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    rule = await db.get(ControlTableCorrectionRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if "replacement_expression" in body:
        rule.replacement_expression = body["replacement_expression"]
    if "recommended_source" in body:
        rule.recommended_source = body["recommended_source"]
    if "issue_type" in body:
        rule.issue_type = body["issue_type"]
    if "notes" in body:
        rule.notes = body["notes"]
    await db.commit()
    return {"updated": True, "id": rule_id}


@router.post("/control-table/training/rules")
async def create_training_rule(body: dict, db: AsyncSession = Depends(get_db)):
    target_table = (body.get("target_table") or "").strip().upper()
    target_column = (body.get("target_column") or "").strip().upper()
    if not target_table or not target_column:
        raise HTTPException(status_code=400, detail="target_table and target_column are required")
    # Deduplicate: if rule for same table+column exists, update it instead of creating a new one
    stmt = select(ControlTableCorrectionRule).where(
        ControlTableCorrectionRule.target_table == target_table,
        ControlTableCorrectionRule.target_column == target_column,
    ).order_by(ControlTableCorrectionRule.id.desc())
    result = await db.execute(stmt)
    all_existing = list(result.scalars().all())
    if all_existing:
        rule = all_existing[0]
        # Delete any older duplicates for this table+column
        for old_rule in all_existing[1:]:
            await db.delete(old_rule)
        rule.replacement_expression = body.get("replacement_expression", rule.replacement_expression)
        rule.recommended_source = body.get("recommended_source", rule.recommended_source)
        rule.issue_type = body.get("issue_type", rule.issue_type)
        if "notes" in body:
            rule.notes = body["notes"]
        await db.commit()
        return {"created": False, "updated": True, "id": rule.id}
    rule = ControlTableCorrectionRule(
        target_table=target_table,
        target_column=target_column,
        replacement_expression=body.get("replacement_expression", ""),
        recommended_source=body.get("recommended_source", "manual"),
        issue_type=body.get("issue_type", "expression_mismatch"),
        notes=body.get("notes", ""),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"created": True, "id": rule.id}


@router.delete("/control-table/training/rules")
async def clear_training_rules_for_table(target_table: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete as sa_delete
    target_table_u = (target_table or "").strip().upper()
    if not target_table_u:
        raise HTTPException(status_code=400, detail="target_table is required")
    await db.execute(
        sa_delete(ControlTableCorrectionRule).where(
            ControlTableCorrectionRule.target_table == target_table_u
        )
    )
    await db.commit()
    return {"cleared": True, "target_table": target_table_u}


@router.post("/control-table/training/feedback")
async def save_control_table_training_feedback(body: ControlTableFeedbackRequest, db: AsyncSession = Depends(get_db)):
    target_table = (body.target_table or "").strip().upper()
    target_column = (body.target_column or "").strip().upper()
    if not target_table or not target_column:
        raise HTTPException(status_code=400, detail="target_table and target_column are required")

    existing = await db.execute(
        select(ControlTableCorrectionRule).where(
            ControlTableCorrectionRule.target_table == target_table,
            ControlTableCorrectionRule.target_column == target_column,
            ControlTableCorrectionRule.issue_type == (body.issue_type or "").strip().lower(),
        )
    )
    rule = existing.scalar_one_or_none()
    if not rule:
        rule = ControlTableCorrectionRule(
            target_table=target_table,
            target_column=target_column,
            issue_type=(body.issue_type or "").strip().lower(),
        )
        db.add(rule)

    rule.source_attribute = (body.source_attribute or "").strip().upper() or None
    rule.recommended_source = (body.recommended_source or "drd").strip().lower()
    rule.replacement_expression = (body.chosen_expression or "").strip() or None
    rule.notes = (body.notes or "").strip() or None

    await db.commit()
    await db.refresh(rule)
    return {"saved": True, "rule": _serialize_training_rule(rule)}


@router.get("/control-table/training/fixtures")
async def list_control_table_fixture_packs():
    if not FIXTURE_ROOT.exists():
        return {"fixtures": []}
    files = sorted([p.name for p in FIXTURE_ROOT.glob("*.csv")])
    return {"fixtures": files}


@router.post("/control-table/training/replay")
async def replay_control_table_training_rules(body: ControlTableReplayRequest, db: AsyncSession = Depends(get_db)):
    await _ensure_non_redshift_datasource(db, body.source_datasource_id, "Source")
    await _ensure_non_redshift_datasource(db, body.target_datasource_id, "Target")

    requested = [f for f in (body.fixture_files or []) if f]
    if not requested:
        requested = ["closed_lot.csv"]

    rules = await _load_training_rules(db, body.target_table)
    replay_items = []
    total_rows = 0
    total_rule_hits = 0

    for fixture_name in requested:
        fixture_path = FIXTURE_ROOT / fixture_name
        if not fixture_path.exists() or fixture_path.suffix.lower() != ".csv":
            replay_items.append({
                "fixture": fixture_name,
                "ok": False,
                "error": "Fixture not found",
            })
            continue
        try:
            result = analyze_control_table(
                file_bytes=fixture_path.read_bytes(),
                filename=fixture_path.name,
                target_schema=body.target_schema,
                target_table=body.target_table,
                source_datasource_id=body.source_datasource_id,
                target_datasource_id=body.target_datasource_id,
                control_schema=body.control_schema.upper(),
                main_grain=body.main_grain,
                manual_sql="",
                selected_fields=None,
            )
            comparison = result.get("comparison") or {"rows": []}
            rows = comparison.get("rows") or []
            total_rows += len(rows)
            hits = 0
            matched_columns = []
            for row in rows:
                rule = _rule_for_row(row, rules)
                if not rule:
                    continue
                hits += 1
                matched_columns.append((row.get("column") or "").strip().upper())
            total_rule_hits += hits
            replay_items.append({
                "fixture": fixture_name,
                "ok": True,
                "total_rows": len(rows),
                "mismatch_count": comparison.get("mismatch_count", 0),
                "rule_hits": hits,
                "matched_columns": sorted([c for c in set(matched_columns) if c])[:30],
            })
        except Exception as exc:
            replay_items.append({
                "fixture": fixture_name,
                "ok": False,
                "error": str(exc),
            })

    return {
        "target_table": body.target_table.strip().upper(),
        "fixtures": replay_items,
        "summary": {
            "requested": len(requested),
            "rules": len(rules),
            "total_rows": total_rows,
            "total_rule_hits": total_rule_hits,
            "hit_rate": round((total_rule_hits / total_rows) * 100, 2) if total_rows else 0.0,
        },
    }


@router.get("/folders")
async def list_folders(db: AsyncSession = Depends(get_db)):
    folders_r = await db.execute(select(TestFolder).order_by(TestFolder.name.asc()))
    folders = folders_r.scalars().all()
    counts_r = await db.execute(select(TestCaseFolder.folder_id, func.count(TestCaseFolder.test_case_id)).group_by(TestCaseFolder.folder_id))
    counts = {row[0]: row[1] for row in counts_r.all()}
    return [{"id": f.id, "name": f.name, "test_count": counts.get(f.id, 0)} for f in folders]


@router.post("/folders/{folder_id}/datasource")
async def update_folder_datasource(folder_id: int, body: FolderDatasourceUpdateRequest,
                                   db: AsyncSession = Depends(get_db)):
    folder = await db.get(TestFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    result = await db.execute(
        select(TestCase).join(TestCaseFolder, TestCaseFolder.test_case_id == TestCase.id).where(TestCaseFolder.folder_id == folder_id)
    )
    tests = result.scalars().all()
    if not tests:
        return {"updated": 0, "folder_id": folder.id, "folder_name": folder.name}

    for test in tests:
        if body.source_datasource_id is not None:
            test.source_datasource_id = body.source_datasource_id
        if body.target_datasource_id is not None:
            test.target_datasource_id = body.target_datasource_id

    await db.commit()
    return {
        "updated": len(tests),
        "folder_id": folder.id,
        "folder_name": folder.name,
        "source_datasource_id": body.source_datasource_id,
        "target_datasource_id": body.target_datasource_id,
    }


@router.post("/training-packs")
async def save_training_pack(
    target_table: str = Form(...),
    source_tables: str = Form(""),
    notes: str = Form(""),
    reference_sql: str = Form(""),
    validation_sql: str = Form(""),
    source_datasource_id: str = Form(""),
    target_datasource_id: str = Form(""),
    drd_files: List[UploadFile] = File(default=[]),
):
    target_table_u = (target_table or "").strip().upper()
    if not target_table_u:
        raise HTTPException(status_code=400, detail="target_table is required")

    slug = re.sub(r"[^A-Z0-9_]+", "_", target_table_u).strip("_") or "TRAINING_PACK"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack_dir = TRAINING_PACK_ROOT / f"{slug}_{timestamp}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for upload in drd_files or []:
        filename = Path(upload.filename or "upload.bin").name
        content = await upload.read()
        (pack_dir / filename).write_bytes(content)
        saved_files.append(filename)

    metadata = {
        "target_table": target_table_u,
        "source_tables": [item.strip() for item in (source_tables or "").split(",") if item.strip()],
        "notes": notes or "",
        "reference_sql": reference_sql or "",
        "validation_sql": validation_sql or "",
        "source_datasource_id": source_datasource_id or "",
        "target_datasource_id": target_datasource_id or "",
        "saved_files": saved_files,
        "created_at": datetime.now().isoformat(),
        "questions": [
            "Confirm which SQL blocks are setup-only versus validation-critical.",
            "Confirm whether multi-step SQL should be preserved as separate setup tests before attribute validations.",
            "Confirm the datasource pair to use when the DRD covers more than one source stream.",
        ],
    }
    (pack_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if reference_sql:
        (pack_dir / "reference.sql").write_text(reference_sql, encoding="utf-8")
    if validation_sql:
        (pack_dir / "validation.sql").write_text(validation_sql, encoding="utf-8")

    return {
        "saved": True,
        "target_table": target_table_u,
        "pack_id": pack_dir.name,
        "pack_dir": str(pack_dir),
        "saved_files": saved_files,
        "questions": metadata["questions"],
    }


@router.post("/training-packs/derive-context")
async def derive_training_pack_context(
    target_table: str = Form(""),
    source_tables: str = Form(""),
    source_sql: str = Form(""),
    expected_sql: str = Form(""),
    drd_files: List[UploadFile] = File(default=[]),
):
    file_names: List[str] = []
    file_texts: List[str] = []

    for upload in drd_files or []:
        filename = Path(upload.filename or "upload.bin").name
        file_names.append(filename)
        try:
            content = await upload.read()
            if not content:
                continue
            if filename.lower().endswith((".txt", ".md", ".sql", ".csv", ".json", ".xml")):
                file_texts.append(content[:200000].decode("utf-8", errors="ignore"))
        except Exception:
            continue

    context = _derive_training_context(
        target_table=target_table,
        source_tables_csv=source_tables,
        source_sql=source_sql,
        expected_sql=expected_sql,
        file_names=file_names,
        file_texts=file_texts,
    )
    return {
        "derived": True,
        **context,
        "file_count": len(file_names),
    }


@router.post("/training-events")
async def save_training_event(body: TrainingEventRequest):
    TRAINING_PACK_ROOT.mkdir(parents=True, exist_ok=True)
    event_file = TRAINING_PACK_ROOT / "training_events.jsonl"
    payload = {
        "event_type": body.event_type,
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "target_table": (body.target_table or "").strip().upper(),
        "source": body.source,
        "status": body.status,
        "details": body.details or {},
        "knowledge_refs": body.knowledge_refs or [],
        "created_at": datetime.now().isoformat(),
    }
    with event_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return {"saved": True, "event_file": str(event_file), "event_type": body.event_type}


@router.get("/training-automation/status")
async def training_automation_status():
    return get_training_automation_status()


@router.post("/training-automation/start")
async def training_automation_start(body: TrainingAutomationRequest):
    return await start_training_automation_loop(body.model_dump())


@router.post("/training-automation/stop")
async def training_automation_stop():
    return await stop_training_automation_loop()


@router.post("/training-automation/run-once")
async def training_automation_run_once(body: TrainingAutomationRequest):
    return await run_training_automation_cycle(body.model_dump())


class TrainingPipelineRequest(BaseModel):
    target_table: str
    source_tables: str = ""
    source_sql: str = ""  # ODI/manual reference SQL
    expected_sql: str = ""  # Expected final insert/transformation
    drd_context: str = ""  # Derived DRD context JSON
    max_iterations: int = 5
    columns: List[str] = []  # specific columns to train on, or [] for all
    mode: str = "ghc"
    agent_id: Optional[int] = None


@router.post("/training-pipeline/run")
async def run_training_pipeline(body: TrainingPipelineRequest):
    """Run an iterative training pipeline that tries to reproduce the expected SQL.

    For each iteration, the AI generates SQL, the tool compares column expressions against
    the expected, and feeds back the mismatches.  Wins are persisted to KB.
    """
    from app.services.ai_service import ai_chat
    import json as _json

    target_table = (body.target_table or "").strip()
    expected_sql = (body.expected_sql or "").strip()
    source_sql = (body.source_sql or "").strip()
    if not target_table or not expected_sql:
        raise HTTPException(422, "target_table and expected_sql are required")

    # Parse expected SQL into column→expression map
    expected_map = extract_sql_expression_map(expected_sql)
    if not expected_map:
        raise HTTPException(422, "Could not parse column expressions from expected SQL")

    train_cols = set(c.upper() for c in body.columns) if body.columns else set(expected_map.keys())

    iterations = []
    current_sql = source_sql or expected_sql
    best_match_count = 0
    best_sql = ""

    for i in range(min(body.max_iterations, 10)):
        # Parse current generated SQL
        current_map = extract_sql_expression_map(current_sql)

        # Compare per-column
        results = []
        match_count = 0
        mismatch_details = []
        for col in sorted(train_cols):
            gen_expr = normalize_sql_expr(current_map.get(col, ""))
            exp_expr = normalize_sql_expr(expected_map.get(col, ""))
            if gen_expr == exp_expr:
                results.append({"column": col, "status": "match", "generated": current_map.get(col, ""), "expected": expected_map.get(col, "")})
                match_count += 1
            else:
                results.append({"column": col, "status": "mismatch", "generated": current_map.get(col, ""), "expected": expected_map.get(col, "")})
                mismatch_details.append(f"Column {col}: generated='{current_map.get(col, 'NULL')}' but expected='{expected_map.get(col, 'NULL')}'")

        # Track best
        if match_count > best_match_count:
            best_match_count = match_count
            best_sql = current_sql

        iteration_result = {
            "iteration": i + 1,
            "match_count": match_count,
            "total_columns": len(train_cols),
            "mismatch_count": len(train_cols) - match_count,
            "results": results,
        }
        iterations.append(iteration_result)

        # All matched — success!
        if match_count == len(train_cols):
            break

        # Build feedback prompt for next iteration
        if i < body.max_iterations - 1 and mismatch_details:
            feedback = (
                f"You are generating an Oracle INSERT/MERGE SQL for target table {target_table}.\n"
                f"Reference ODI/source SQL:\n{source_sql[:2000] if source_sql else '[none]'}\n\n"
                f"Your current SQL has {len(mismatch_details)} column mismatches out of {len(train_cols)} total.\n"
                f"Mismatches:\n" + "\n".join(mismatch_details[:20]) + "\n\n"
                f"Please fix ONLY the mismatched columns to match the expected expressions exactly. "
                f"Return a complete INSERT...SELECT statement with the corrected expressions. "
                f"Do NOT change columns that already match. Return only the SQL, no explanation."
            )
            if body.drd_context:
                feedback += f"\n\nDRD Context:\n{body.drd_context[:2000]}"

            try:
                messages = [{"role": "user", "content": feedback}]
                ai_result = await ai_chat(
                    messages,
                    "",
                    "githubcopilot",
                    "",
                    [],
                )
                reply = ai_result.get("reply") or ai_result.get("message") or ai_result.get("response") or ""
                # Extract SQL from reply
                sql_match = re.search(r'(INSERT\b[\s\S]*?;)', reply, flags=re.IGNORECASE)
                if sql_match:
                    current_sql = sql_match.group(1)
                elif "SELECT" in reply.upper():
                    current_sql = reply.strip()
            except Exception as e:
                iteration_result["ai_error"] = str(e)
                break

    # Persist wins to KB if we achieved full or near-full match
    final_match = iterations[-1]["match_count"] if iterations else 0
    final_total = iterations[-1]["total_columns"] if iterations else 0
    win = final_match == final_total

    if win and best_sql:
        # Save winning expressions as training rules
        exp_map_for_save = expected_map
        rules_saved = 0
        try:
            # Save to training_packs as a successful example
            packs_dir = DATA_DIR.parent / "db-testing-tool" / "training_packs"
            packs_dir.mkdir(exist_ok=True)
            pack_name = f"auto_win_{target_table}_{int(__import__('time').time())}"
            pack_dir = packs_dir / pack_name
            pack_dir.mkdir(exist_ok=True)
            (pack_dir / "metadata.json").write_text(_json.dumps({
                "target_table": target_table,
                "source_tables": body.source_tables.split(",") if body.source_tables else [],
                "notes": f"Auto-trained: {final_match}/{final_total} columns matched in {len(iterations)} iterations",
                "trained_at": __import__("datetime").datetime.now().isoformat(),
                "status": "win",
            }, indent=2))
            (pack_dir / "reference.sql").write_text(expected_sql)
            (pack_dir / "validation.sql").write_text(best_sql)
            rules_saved = final_match
        except Exception:
            pass

    return {
        "status": "win" if win else "partial",
        "iterations": iterations,
        "total_iterations": len(iterations),
        "final_match_count": final_match,
        "final_total_columns": final_total,
        "best_match_count": best_match_count,
        "best_sql": best_sql,
        "rules_saved": rules_saved if win else 0,
        "training_summary": _build_training_summary(iterations, target_table),
    }


def _build_training_summary(iterations, target_table):
    """Build human-readable training summary."""
    if not iterations:
        return "No iterations completed."
    parts = [f"Training pipeline for {target_table}:"]
    for it in iterations:
        parts.append(
            f"  Iteration {it['iteration']}: {it['match_count']}/{it['total_columns']} columns matched "
            f"({it['mismatch_count']} mismatches)"
        )
    final = iterations[-1]
    if final["match_count"] == final["total_columns"]:
        parts.append(f"  → SUCCESS: All {final['total_columns']} columns matched!")
    else:
        parts.append(f"  → PARTIAL: {final['match_count']}/{final['total_columns']} columns matched after {len(iterations)} iterations")
        # List remaining mismatches
        mismatches = [r for r in final.get("results", []) if r["status"] == "mismatch"]
        if mismatches:
            parts.append("  Remaining mismatches:")
            for m in mismatches[:10]:
                parts.append(f"    {m['column']}: got '{m['generated'][:60]}' expected '{m['expected'][:60]}'")
    return "\n".join(parts)


@router.get("/training-pipeline/rules")
async def list_training_pipeline_rules(target_table: str = "", db: AsyncSession = Depends(get_db)):
    """List all training rules (correction rules) with optional filter."""
    from sqlalchemy import select as sa_select, or_
    stmt = sa_select(ControlTableCorrectionRule)
    if target_table:
        tbl_upper = target_table.strip().upper()
        # Match both fully-qualified (SCHEMA.TABLE) and bare table name.
        bare = tbl_upper.rsplit(".", 1)[-1] if "." in tbl_upper else tbl_upper
        stmt = stmt.where(or_(
            ControlTableCorrectionRule.target_table == tbl_upper,
            ControlTableCorrectionRule.target_table == bare,
        ))
    stmt = stmt.order_by(ControlTableCorrectionRule.target_table, ControlTableCorrectionRule.target_column)
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "target_table": r.target_table,
            "target_column": r.target_column,
            "issue_type": r.issue_type,
            "source_attribute": r.source_attribute,
            "recommended_source": r.recommended_source,
            "replacement_expression": r.replacement_expression,
            "notes": r.notes,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rules
    ]


@router.post("/folders")
async def create_folder(body: FolderCreateRequest, db: AsyncSession = Depends(get_db)):
    folder = await _ensure_folder(db, body.name)
    await db.commit()
    return {"id": folder.id, "name": folder.name}


@router.post("/folders/move")
async def move_tests_to_folder(body: MoveTestsToFolderRequest, db: AsyncSession = Depends(get_db)):
    moved = 0
    for test_id in body.test_ids:
        tc = await db.get(TestCase, test_id)
        if not tc:
            continue
        await _assign_test_to_folder(db, test_id, body.folder_id)
        moved += 1
    await db.commit()
    return {"moved": moved, "folder_id": body.folder_id}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, db: AsyncSession = Depends(get_db)):
    result = await _delete_folder_with_children(db, folder_id)
    if not result.get("deleted"):
        raise HTTPException(404, "Folder not found")
    await db.commit()
    return result


class BulkFolderDeleteRequest(BaseModel):
    folder_ids: List[int]


@router.post("/folders/bulk-delete")
async def bulk_delete_folders(body: BulkFolderDeleteRequest, db: AsyncSession = Depends(get_db)):
    deleted_folders = 0
    deleted_tests = 0
    deleted_runs = 0
    for folder_id in body.folder_ids or []:
        result = await _delete_folder_with_children(db, folder_id)
        if result.get("deleted"):
            deleted_folders += 1
            deleted_tests += int(result.get("tests_deleted") or 0)
            deleted_runs += int(result.get("runs_deleted") or 0)
    await db.commit()
    return {
        "deleted_folders": deleted_folders,
        "deleted_tests": deleted_tests,
        "deleted_runs": deleted_runs,
    }


# ── Execution (MUST come before /{test_id}) ─────────────────────────────────

@router.post("/run-batch")
async def execute_batch(body: RunRequest, db: AsyncSession = Depends(get_db)):
    summary = await run_all_tests(db, body.test_ids)
    return summary


@router.post("/run-batch/start")
async def start_batch(body: StartBatchRequest):
    batch_id = str(uuid.uuid4())[:12]
    task = asyncio.create_task(_run_batch_background(batch_id, body.test_ids))
    _batch_tasks[batch_id] = task
    _batch_control[batch_id] = {
        "batch_id": batch_id,
        "status": "starting",
        "total": 0,
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "error": 0,
        "stopped": False,
        "current_test_number": None,
        "current_test_id": None,
    }
    return {"batch_id": batch_id, "status": "starting"}


@router.get("/run-batch/status/{batch_id}")
async def get_batch_status(batch_id: str, db: AsyncSession = Depends(get_db)):
    state = _batch_control.get(batch_id)
    if not state:
        # fallback from persisted runs if state has been evicted
        q = await db.execute(
            select(TestRun.status, func.count(TestRun.id))
            .where(TestRun.batch_id == batch_id)
            .group_by(TestRun.status)
        )
        groups = dict(q.all())
        total = sum(groups.values())
        if total == 0:
            raise HTTPException(404, "Batch not found")
        return {
            "batch_id": batch_id,
            "status": "completed",
            "total": total,
            "completed": total,
            "passed": groups.get("passed", 0),
            "failed": groups.get("failed", 0),
            "error": groups.get("error", 0),
            "stopped": False,
            "current_test_number": None,
            "current_test_id": None,
        }
    return state


@router.post("/run-batch/stop/{batch_id}")
async def stop_batch(batch_id: str):
    state = _batch_control.get(batch_id)
    if not state:
        raise HTTPException(404, "Batch not found")
    state["stopped"] = True
    state["status"] = "stopping"
    task = _batch_tasks.get(batch_id)
    if task and not task.done():
        task.cancel()
    return {"batch_id": batch_id, "status": "stopping"}


@router.post("/run/{test_id}")
async def execute_test(test_id: int, db: AsyncSession = Depends(get_db)):
    run = await run_test(db, test_id)
    return {
        "run_id": run.id, "batch_id": run.batch_id,
        "status": run.status, "mismatch_count": run.mismatch_count,
        "execution_time_ms": run.execution_time_ms,
        "error_message": run.error_message,
        "actual_result": run.actual_result,
    }


# ── Test Cases CRUD ─────────────────────────────────────────────────────────

@router.get("")
async def list_tests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TestCase).order_by(TestCase.id.asc()))
    items = result.scalars().all()

    folder_links_r = await db.execute(select(TestCaseFolder))
    folder_links = folder_links_r.scalars().all()
    test_to_folder = {fl.test_case_id: fl.folder_id for fl in folder_links}

    folders_r = await db.execute(select(TestFolder))
    folders = folders_r.scalars().all()
    folder_names = {f.id: f.name for f in folders}

    payload = []
    for t in items:
        latest_run_q = await db.execute(
            select(TestRun)
            .where(TestRun.test_case_id == t.id)
            .order_by(TestRun.id.desc())
            .limit(1)
        )
        latest_run = latest_run_q.scalar_one_or_none()
        folder_id = test_to_folder.get(t.id)
        payload.append({
            "id": t.id, "name": t.name, "test_type": t.test_type,
            "mapping_rule_id": t.mapping_rule_id,
            "source_datasource_id": t.source_datasource_id,
            "target_datasource_id": t.target_datasource_id,
            "source_query": t.source_query,
            "target_query": t.target_query,
            "severity": t.severity,
            "is_active": t.is_active,
            "is_ai_generated": t.is_ai_generated,
            "description": t.description,
            "last_run_status": latest_run.status if latest_run else "untested",
            "last_run_at": str(latest_run.executed_at) if latest_run and latest_run.executed_at else None,
            "last_run_batch_id": latest_run.batch_id if latest_run else None,
            "last_error_message": latest_run.error_message if latest_run else None,
            "folder_id": folder_id,
            "folder_name": folder_names.get(folder_id) if folder_id else None,
        })
    payload.sort(key=lambda x: ((x.get("folder_name") or "~ungrouped").lower(), x["id"]))
    return payload


@router.post("")
async def create_test(body: TestCreate, db: AsyncSession = Depends(get_db)):
    tc = TestCase(**body.model_dump())
    db.add(tc)
    await db.flush()

    folder = await _ensure_folder(db, DEFAULT_TEST_FOLDER_NAME)
    if folder:
        await _assign_test_to_folder(db, tc.id, folder.id)

    await db.commit()
    await db.refresh(tc)
    return {"id": tc.id, "name": tc.name, "status": "created"}


class BulkDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/bulk-delete")
async def bulk_delete_tests(body: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    """Delete multiple test cases by IDs."""
    deleted = 0
    for test_id in body.ids:
        await db.execute(delete(TestRun).where(TestRun.test_case_id == test_id))
        await db.execute(delete(TestCaseFolder).where(TestCaseFolder.test_case_id == test_id))
        tc = await db.get(TestCase, test_id)
        if tc:
            await db.delete(tc)
            deleted += 1
    await db.commit()
    return {"deleted": deleted}


@router.post("/runs/bulk-delete")
async def bulk_delete_runs(body: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    """Delete multiple test runs by IDs."""
    deleted = 0
    for run_id in body.ids:
        run = await db.get(TestRun, run_id)
        if run:
            await db.delete(run)
            deleted += 1
    await db.commit()
    return {"deleted": deleted}


@router.post("/runs/clear")
async def clear_runs(batch_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Clear test run history (all runs, or only a specific batch)."""
    if batch_id:
        result = await db.execute(delete(TestRun).where(TestRun.batch_id == batch_id))
    else:
        result = await db.execute(delete(TestRun))
    await db.commit()
    return {"deleted": result.rowcount or 0, "batch_id": batch_id}


@router.post("/runs/clear-all-statuses")
async def clear_all_run_statuses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(TestRun))
    await db.commit()
    return {"deleted": result.rowcount or 0}


@router.get("/{test_id}")
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    latest_run_q = await db.execute(
        select(TestRun)
        .where(TestRun.test_case_id == tc.id)
        .order_by(TestRun.id.desc())
        .limit(1)
    )
    latest_run = latest_run_q.scalar_one_or_none()
    return {
        "id": tc.id, "name": tc.name, "test_type": tc.test_type,
        "mapping_rule_id": tc.mapping_rule_id,
        "source_datasource_id": tc.source_datasource_id,
        "target_datasource_id": tc.target_datasource_id,
        "source_query": tc.source_query, "target_query": tc.target_query,
        "expected_result": tc.expected_result, "tolerance": tc.tolerance,
        "severity": tc.severity, "is_active": tc.is_active,
        "is_ai_generated": tc.is_ai_generated, "description": tc.description,
        "last_run_status": latest_run.status if latest_run else "untested",
        "last_run_at": str(latest_run.executed_at) if latest_run and latest_run.executed_at else None,
        "last_error_message": latest_run.error_message if latest_run else None,
        "last_actual_result": latest_run.actual_result if latest_run else None,
        "last_mismatch_count": latest_run.mismatch_count if latest_run else 0,
    }


@router.put("/{test_id}")
async def update_test(test_id: int, body: TestCreate, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    for key, value in body.model_dump().items():
        setattr(tc, key, value)
    await db.commit()
    await db.refresh(tc)
    return {"id": tc.id, "name": tc.name, "status": "updated"}


@router.delete("/{test_id}")
async def delete_test(test_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    await db.execute(delete(TestRun).where(TestRun.test_case_id == test_id))
    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.test_case_id == test_id))
    await db.delete(tc)
    await db.commit()
    return {"deleted": True}

