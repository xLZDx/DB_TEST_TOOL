"""Control-table analysis, comparison, and training-rule endpoints.

All routes are registered on _ct_router (no prefix) and included by tests.py
into the main /api/tests router.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.factory import get_connector_from_model
from app.database import get_db
from app.models.control_table_training import ControlTableCorrectionRule, ControlTableFileState
from app.models.datasource import DataSource
from app.models.test_case import TestCase, TestCaseFolder
from app.services.control_table_service import (
    analyze_control_table,
    apply_compare_decisions,
    apply_sql_variant_preserving_joins,
    build_control_table_ddl,
    compare_insert_variants,
    dedupe_insert_join_blocks,
    ensure_parallel_hints,
    load_target_table_definition,
    normalize_insert_source_target_aliases,
    validate_insert_join_aliases,
    _enforce_not_null_in_insert_sql,
)
from app.routers.tests_utils import (
    DEFAULT_TEST_FOLDER_NAME,
    FIXTURE_ROOT,
    ControlTableTrainingRuleCreate,
    ControlTableTrainingRuleUpdate,
    _assign_test_to_folder,
    _create_new_folder,
    _derive_control_suite_base_name,
    _ensure_folder,
    _ensure_non_redshift_datasource,
)

_ct_router = APIRouter()

# ── Pydantic models (control-table specific) ─────────────────────────────────


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


# ── Private helpers (CT-only) ─────────────────────────────────────────────────


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
    col = (row.get("column") or "").strip().upper()
    if not col:
        return None
    src = (row.get("source_attribute") or "").strip().upper()
    status = (row.get("status") or "").strip().lower()
    best: Optional[ControlTableCorrectionRule] = None
    best_score = -1
    for rule in rules:
        if (rule.target_column or "").strip().upper() != col:
            continue
        score = 5
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


# ── SQL analysis helpers (used only by check_control_table_insert_sql) ────────


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
        text, flags=re.IGNORECASE | re.DOTALL,
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
        (sql or ""), flags=re.IGNORECASE | re.DOTALL,
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
    if re.search(r'ORA-00942: table or view does not exist', err, flags=re.IGNORECASE):
        suggestions.append("Oracle could not find a table/view referenced by the SQL. Verify schema.table names and datasource selection.")
    if re.search(r'ORA-02289: sequence does not exist', err, flags=re.IGNORECASE):
        suggestions.append("A referenced sequence does not exist. Check sequence schema/name or replace with the correct load logic.")
    return suggestions


# ── Routes ────────────────────────────────────────────────────────────────────


@_ct_router.post("/control-table/analyze")
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
    filename = file.filename or "file.csv"
    fingerprint = _file_fingerprint(file_bytes)
    target_table_u = target_table.strip().upper()

    restored_state = await _load_file_state(db, target_table_u, fingerprint)
    state_restored = restored_state is not None

    rules = await _load_training_rules(db, target_table_u)

    result = analyze_control_table(
        file_bytes=file_bytes,
        filename=filename,
        target_schema=target_schema,
        target_table=target_table,
        source_datasource_id=source_datasource_id,
        target_datasource_id=resolved_target_datasource_id,
        control_schema=control_schema.upper(),
        main_grain=main_grain,
        manual_sql=manual_sql or (restored_state.final_insert_sql if restored_state else ""),
        selected_fields=selected_fields if selected_fields else None,
        sheet_name=sheet_name.strip() or None,
    )
    comparison = result.get("comparison") or {"rows": []}
    result["comparison"] = _apply_training_rules_to_comparison(comparison, rules)
    result["file_fingerprint"] = fingerprint
    result["state_restored"] = state_restored
    result["state_file_name"] = restored_state.file_name if restored_state else ""
    result["join_alias_issues"] = validate_insert_join_aliases(result.get("generated_insert_sql", ""))
    return result


@_ct_router.post("/control-table/preview-drd")
async def preview_control_table_drd(
    file: UploadFile = File(...),
    sheet_name: str = Form(""),
):
    from app.services.drd_import_service import preview_file, extract_drd_metadata, read_excel_all_sheets
    file_bytes = await file.read()
    filename = file.filename or "file.xlsx"
    result = preview_file(file_bytes, filename, sheet_name=sheet_name.strip() or None)
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("xlsx", "xls"):
        try:
            all_sheets = read_excel_all_sheets(file_bytes)
            sheet_infos = []
            for sn, rows in all_sheets.items():
                meta = extract_drd_metadata(file_bytes, filename, sheet_name=sn)
                sheet_infos.append({"name": sn, "row_count": len(rows), "metadata": meta})
            result["sheet_details"] = sheet_infos
        except Exception:
            pass
    return result


@_ct_router.post("/control-table/empty")
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


@_ct_router.post("/control-table/compare")
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


@_ct_router.post("/control-table/apply")
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


@_ct_router.post("/control-table/apply-sql")
async def apply_control_table_sql_variant(body: ControlTableApplySqlRequest):
    sql = normalize_insert_source_target_aliases(
        dedupe_insert_join_blocks(ensure_parallel_hints(apply_sql_variant_preserving_joins(body.base_sql, body.variant_sql)))
    )
    return {"sql": sql}


@_ct_router.post("/control-table/save-insert-state")
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


@_ct_router.post("/control-table/check-insert")
async def check_control_table_insert_sql(body: ControlTableInsertCheckRequest, db: AsyncSession = Depends(get_db)):
    ds = await _ensure_non_redshift_datasource(db, body.target_datasource_id, "Target")
    sql = (body.sql or "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="sql is required")

    connector = get_connector_from_model(ds)
    try:
        connector.connect()
        diagnostics = _analyze_sql_references(connector, sql)

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


@_ct_router.delete("/control-table/file-state")
async def clear_control_table_file_state(
    target_table: str,
    file_fingerprint: str = "",
    db: AsyncSession = Depends(get_db),
):
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
    return {"cleared": True, "rows_deleted": result.rowcount or 0, "target_table": table_u}


@_ct_router.post("/control-table/suite")
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


@_ct_router.get("/control-table/training/rules")
async def list_control_table_training_rules(target_table: str, db: AsyncSession = Depends(get_db)):
    rules = await _load_training_rules(db, target_table)
    return {"target_table": target_table.strip().upper(), "rules": [_serialize_training_rule(r) for r in rules]}


@_ct_router.delete("/control-table/training/rules/{rule_id}")
async def delete_training_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(ControlTableCorrectionRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"deleted": True, "id": rule_id}


@_ct_router.put("/control-table/training/rules/{rule_id}")
async def update_training_rule(rule_id: int, body: ControlTableTrainingRuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(ControlTableCorrectionRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if body.replacement_expression is not None:
        rule.replacement_expression = body.replacement_expression
    if body.recommended_source is not None:
        rule.recommended_source = body.recommended_source
    if body.issue_type is not None:
        rule.issue_type = body.issue_type
    if body.notes is not None:
        rule.notes = body.notes
    await db.commit()
    return {"updated": True, "id": rule_id}


@_ct_router.post("/control-table/training/rules")
async def create_training_rule(body: ControlTableTrainingRuleCreate, db: AsyncSession = Depends(get_db)):
    target_table = body.target_table.strip().upper()
    target_column = body.target_column.strip().upper()
    if not target_table or not target_column:
        raise HTTPException(status_code=400, detail="target_table and target_column are required")
    stmt = select(ControlTableCorrectionRule).where(
        ControlTableCorrectionRule.target_table == target_table,
        ControlTableCorrectionRule.target_column == target_column,
    ).order_by(ControlTableCorrectionRule.id.desc())
    result = await db.execute(stmt)
    all_existing = list(result.scalars().all())
    if all_existing:
        rule = all_existing[0]
        for old_rule in all_existing[1:]:
            await db.delete(old_rule)
        rule.replacement_expression = body.replacement_expression or rule.replacement_expression
        rule.recommended_source = body.recommended_source or rule.recommended_source
        rule.issue_type = body.issue_type or rule.issue_type
        if body.notes is not None:
            rule.notes = body.notes
        await db.commit()
        return {"created": False, "updated": True, "id": rule.id}
    rule = ControlTableCorrectionRule(
        target_table=target_table,
        target_column=target_column,
        replacement_expression=body.replacement_expression or "",
        recommended_source=body.recommended_source or "manual",
        issue_type=body.issue_type or "expression_mismatch",
        notes=body.notes or "",
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"created": True, "id": rule.id}


@_ct_router.delete("/control-table/training/rules")
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


@_ct_router.post("/control-table/training/feedback")
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


@_ct_router.get("/control-table/training/fixtures")
async def list_control_table_fixture_packs():
    if not FIXTURE_ROOT.exists():
        return {"fixtures": []}
    files = sorted([p.name for p in FIXTURE_ROOT.glob("*.csv")])
    return {"fixtures": files}


@_ct_router.post("/control-table/training/replay")
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
            replay_items.append({"fixture": fixture_name, "ok": False, "error": "Fixture not found"})
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
            replay_items.append({"fixture": fixture_name, "ok": False, "error": str(exc)})

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
