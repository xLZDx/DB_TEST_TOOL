"""Test management router for IntelliTest – CRUD, execution, folders."""
import asyncio
import json
import time
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update

from app.database import get_db
from app.models.test_case import TestCase, TestRun, TestFolder, TestCaseFolder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tests", tags=["tests"])

# ── Batch execution state (in-memory) ──────────────────────────────────────
_batch_state: dict = {}  # batch_id → {status, total, completed, passed, failed, error, stopped}

# ── Oracle helper ───────────────────────────────────────────────────────────

def _get_oracle_connection(ds_cfg: dict):
    """Return an oracledb connection from a datasource config dict."""
    import oracledb
    host = ds_cfg.get("host", "")
    port = ds_cfg.get("port", 1521)
    db = ds_cfg.get("database_name") or ds_cfg.get("service") or ds_cfg.get("database", "")
    user = ds_cfg.get("username", "")
    pw = ds_cfg.get("password") or ""
    dsn = f"{host}:{port}/{db}"
    return oracledb.connect(user=user, password=pw, dsn=dsn, tcp_connect_timeout=8)


def _find_datasource(ds_id: int) -> Optional[dict]:
    """Look up a datasource from the in-memory store (datasources router)."""
    from app.routers.datasources import _datasources
    return next((d for d in _datasources if d.get("id") == ds_id), None)


def _execute_sql(ds_cfg: dict, sql: str) -> dict:
    """Execute SQL on a datasource and return rows dict."""
    conn = None
    try:
        conn = _get_oracle_connection(ds_cfg)
        cur = conn.cursor()
        cur.execute(sql.rstrip().rstrip(";"))
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = [dict(zip(cols, row)) for row in cur.fetchmany(500)]
        return {"rows": rows, "count": len(rows), "error": None}
    except Exception as e:
        return {"rows": [], "count": 0, "error": str(e)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _compare_results(test: TestCase, src_res: dict, tgt_res: dict) -> tuple:
    """Returns (passed, mismatch_count, detail)."""
    if src_res.get("error"):
        return False, 0, f"Source error: {src_res['error']}"
    if tgt_res.get("error"):
        return False, 0, f"Target error: {tgt_res['error']}"

    if test.test_type == "row_count":
        s = src_res["rows"][0].get("CNT", src_res["rows"][0].get("cnt", 0)) if src_res["rows"] else 0
        t = tgt_res["rows"][0].get("CNT", tgt_res["rows"][0].get("cnt", 0)) if tgt_res["rows"] else 0
        diff = abs(s - t)
        return diff <= (test.tolerance or 0), diff, f"Source={s} Target={t} Diff={diff}"

    if test.test_type in ("null_check", "uniqueness"):
        cnt = tgt_res["rows"][0].get("CNT", tgt_res["rows"][0].get("cnt", 0)) if tgt_res["rows"] else 0
        return cnt == 0, cnt, f"Violations={cnt}"

    if test.test_type == "value_match":
        if not src_res["rows"] or not tgt_res["rows"]:
            return False, 0, "No data returned"
        sr = {k.upper(): v for k, v in src_res["rows"][0].items()}
        tr = {k.upper(): v for k, v in tgt_res["rows"][0].items()}
        mismatches = sum(1 for k in sr if sr[k] != tr.get(k))
        detail = "; ".join(f"{k}: src={sr[k]} tgt={tr.get(k)}" for k in sr if sr[k] != tr.get(k))
        return mismatches == 0, mismatches, detail or "Match"

    # custom_sql – pick whichever result set has data
    res = src_res if src_res["rows"] else tgt_res
    if test.expected_result:
        try:
            expected = json.loads(test.expected_result)
            if isinstance(expected, (int, float)):
                actual = None
                if res["rows"]:
                    actual = next(iter(res["rows"][0].values()))
                    try:
                        actual = float(actual)
                    except (TypeError, ValueError):
                        actual = res["count"]
                diff = abs((actual or 0) - expected)
                return diff <= (test.tolerance or 0), int(diff), f"Expected={expected} Actual={actual}"
        except Exception:
            pass
    return True, 0, "Executed (no specific assertion)"


# ── Pydantic models ────────────────────────────────────────────────────────

class TestCreate(BaseModel):
    name: str
    test_type: str = "custom_sql"
    source_datasource_id: Optional[int] = None
    target_datasource_id: Optional[int] = None
    source_query: Optional[str] = None
    target_query: Optional[str] = None
    expected_result: Optional[str] = None
    tolerance: float = 0.0
    severity: str = "medium"
    description: Optional[str] = None
    is_ai_generated: bool = False
    folder_id: Optional[int] = None


class BulkDeleteRequest(BaseModel):
    ids: List[int]


class FolderMoveRequest(BaseModel):
    test_ids: List[int]
    folder_id: int


class FolderCreateRequest(BaseModel):
    name: str


class FolderDatasourceRequest(BaseModel):
    source_datasource_id: Optional[int] = None
    target_datasource_id: Optional[int] = None


class BatchRunRequest(BaseModel):
    test_ids: Optional[List[int]] = None


class SaveSuiteRequest(BaseModel):
    suite_name: str
    tests: List[dict]
    source_datasource_id: Optional[int] = None


# ── Dashboard ───────────────────────────────────────────────────────────────

@router.get("/dashboard-stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(TestCase.id)))).scalar() or 0
    total_runs = (await db.execute(select(func.count(TestRun.id)))).scalar() or 0
    passed = (await db.execute(select(func.count(TestRun.id)).where(TestRun.status == "passed"))).scalar() or 0
    failed = (await db.execute(select(func.count(TestRun.id)).where(TestRun.status == "failed"))).scalar() or 0
    errors = (await db.execute(select(func.count(TestRun.id)).where(TestRun.status == "error"))).scalar() or 0
    return {"total_tests": total, "total_runs": total_runs, "passed": passed, "failed": failed, "errors": errors,
            "pass_rate": round(passed / total_runs * 100, 1) if total_runs else 0}


# ── Test CRUD ──────────────────────────────────────────────────────────────

@router.get("")
async def list_tests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TestCase).order_by(TestCase.id))
    tests = result.scalars().all()
    # Get folder info and last run
    out = []
    for t in tests:
        folder_row = await db.execute(
            select(TestFolder.id, TestFolder.name)
            .join(TestCaseFolder, TestCaseFolder.folder_id == TestFolder.id)
            .where(TestCaseFolder.test_case_id == t.id)
        )
        folder = folder_row.first()
        last_run_row = await db.execute(
            select(TestRun).where(TestRun.test_case_id == t.id).order_by(TestRun.id.desc()).limit(1)
        )
        last_run = last_run_row.scalars().first()
        out.append({
            "id": t.id, "name": t.name, "test_type": t.test_type,
            "source_datasource_id": t.source_datasource_id,
            "target_datasource_id": t.target_datasource_id,
            "source_query": t.source_query, "target_query": t.target_query,
            "expected_result": t.expected_result, "tolerance": t.tolerance,
            "severity": t.severity, "is_active": t.is_active,
            "is_ai_generated": t.is_ai_generated, "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "folder_id": folder[0] if folder else None,
            "folder_name": folder[1] if folder else None,
            "last_run_status": last_run.status if last_run else None,
            "last_run_at": last_run.executed_at.isoformat() if last_run and last_run.executed_at else None,
            "last_error_message": last_run.error_message if last_run else None,
        })
    return out


@router.post("")
async def create_test(body: TestCreate, db: AsyncSession = Depends(get_db)):
    tc = TestCase(
        name=body.name, test_type=body.test_type,
        source_datasource_id=body.source_datasource_id,
        target_datasource_id=body.target_datasource_id,
        source_query=body.source_query, target_query=body.target_query,
        expected_result=body.expected_result, tolerance=body.tolerance,
        severity=body.severity, description=body.description,
        is_ai_generated=body.is_ai_generated,
    )
    db.add(tc)
    await db.flush()
    if body.folder_id:
        db.add(TestCaseFolder(test_case_id=tc.id, folder_id=body.folder_id))
    await db.commit()
    return {"id": tc.id, "name": tc.name, "status": "created"}


@router.post("/bulk-delete")
async def bulk_delete_tests(body: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    if not body.ids:
        return {"deleted": 0}
    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.test_case_id.in_(body.ids)))
    await db.execute(delete(TestRun).where(TestRun.test_case_id.in_(body.ids)))
    result = await db.execute(delete(TestCase).where(TestCase.id.in_(body.ids)))
    await db.commit()
    return {"deleted": result.rowcount}


# ── Folders (must come before /{test_id} to avoid route conflict) ───────────

@router.get("/folders")
async def list_folders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TestFolder).order_by(TestFolder.id))
    folders = result.scalars().all()
    out = []
    for f in folders:
        cnt = (await db.execute(
            select(func.count(TestCaseFolder.test_case_id)).where(TestCaseFolder.folder_id == f.id)
        )).scalar() or 0
        out.append({"id": f.id, "name": f.name, "test_count": cnt})
    return out


@router.post("/folders")
async def create_folder(body: FolderCreateRequest, db: AsyncSession = Depends(get_db)):
    f = TestFolder(name=body.name)
    db.add(f)
    await db.commit()
    return {"id": f.id, "name": f.name}


@router.post("/folders/move")
async def move_to_folder(body: FolderMoveRequest, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.test_case_id.in_(body.test_ids)))
    for tid in body.test_ids:
        db.add(TestCaseFolder(test_case_id=tid, folder_id=body.folder_id))
    await db.commit()
    return {"moved": len(body.test_ids), "folder_id": body.folder_id}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(TestCaseFolder.test_case_id).where(TestCaseFolder.folder_id == folder_id))
    test_ids = [r[0] for r in rows.all()]
    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.folder_id == folder_id))
    if test_ids:
        await db.execute(delete(TestRun).where(TestRun.test_case_id.in_(test_ids)))
        await db.execute(delete(TestCase).where(TestCase.id.in_(test_ids)))
    f = await db.get(TestFolder, folder_id)
    if f:
        await db.delete(f)
    await db.commit()
    return {"deleted": True, "folder_id": folder_id, "tests_deleted": len(test_ids)}


@router.post("/folders/{folder_id}/datasource")
async def set_folder_datasource(folder_id: int, body: FolderDatasourceRequest, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(TestCaseFolder.test_case_id).where(TestCaseFolder.folder_id == folder_id))
    test_ids = [r[0] for r in rows.all()]
    if not test_ids:
        return {"updated": 0}
    values = {}
    if body.source_datasource_id is not None:
        values["source_datasource_id"] = body.source_datasource_id
    if body.target_datasource_id is not None:
        values["target_datasource_id"] = body.target_datasource_id
    if values:
        await db.execute(update(TestCase).where(TestCase.id.in_(test_ids)).values(**values))
        await db.commit()
    return {"updated": len(test_ids), "folder_id": folder_id}


# ── Individual test routes (after folders to avoid route conflict) ──────────

@router.get("/{test_id}")
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    return {
        "id": tc.id, "name": tc.name, "test_type": tc.test_type,
        "source_datasource_id": tc.source_datasource_id,
        "target_datasource_id": tc.target_datasource_id,
        "source_query": tc.source_query, "target_query": tc.target_query,
        "expected_result": tc.expected_result, "tolerance": tc.tolerance,
        "severity": tc.severity, "is_active": tc.is_active,
        "is_ai_generated": tc.is_ai_generated, "description": tc.description,
    }


@router.put("/{test_id}")
async def update_test(test_id: int, body: TestCreate, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    for field in ("name", "test_type", "source_datasource_id", "target_datasource_id",
                  "source_query", "target_query", "expected_result", "tolerance",
                  "severity", "description", "is_ai_generated"):
        setattr(tc, field, getattr(body, field))
    await db.commit()
    return {"id": tc.id, "name": tc.name, "status": "updated"}


@router.delete("/{test_id}")
async def delete_test(test_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")
    await db.execute(delete(TestCaseFolder).where(TestCaseFolder.test_case_id == test_id))
    await db.delete(tc)
    await db.commit()
    return {"deleted": True}


# ── Test Execution ──────────────────────────────────────────────────────────

@router.post("/run/{test_id}")
async def run_single_test(test_id: int, db: AsyncSession = Depends(get_db)):
    tc = await db.get(TestCase, test_id)
    if not tc:
        raise HTTPException(404, "Test not found")

    batch_id = str(uuid.uuid4())[:12]
    run = TestRun(test_case_id=tc.id, batch_id=batch_id, status="running")
    db.add(run)
    await db.flush()

    start = time.time()
    src_res = {"rows": [], "count": 0, "error": None}
    tgt_res = {"rows": [], "count": 0, "error": None}

    try:
        if tc.source_query and tc.source_datasource_id:
            ds = _find_datasource(tc.source_datasource_id)
            if ds:
                src_res = await asyncio.to_thread(_execute_sql, ds, tc.source_query)

        if tc.target_query and tc.target_datasource_id:
            ds = _find_datasource(tc.target_datasource_id)
            if ds:
                tgt_res = await asyncio.to_thread(_execute_sql, ds, tc.target_query)
        elif tc.source_query and not tc.target_query:
            # Single-DB mode: source only
            pass

        elapsed = int((time.time() - start) * 1000)
        passed, mismatches, detail = _compare_results(tc, src_res, tgt_res)

        run.status = "passed" if passed else "failed"
        run.source_result = json.dumps(src_res["rows"][:10], default=str) if src_res["rows"] else None
        run.target_result = json.dumps(tgt_res["rows"][:10], default=str) if tgt_res["rows"] else None
        run.actual_result = json.dumps({"detail": detail}, default=str)
        run.mismatch_count = mismatches
        run.execution_time_ms = elapsed

        if src_res.get("error") or tgt_res.get("error"):
            run.status = "error"
            run.error_message = src_res.get("error") or tgt_res.get("error")
    except Exception as e:
        run.status = "error"
        run.error_message = str(e)

    await db.commit()
    return {
        "run_id": run.id, "batch_id": run.batch_id, "status": run.status,
        "mismatch_count": run.mismatch_count, "execution_time_ms": run.execution_time_ms,
        "error_message": run.error_message,
        "actual_result": run.actual_result,
        "source_result": run.source_result,
        "target_result": run.target_result,
    }


@router.post("/run-batch")
async def run_batch(body: BatchRunRequest, db: AsyncSession = Depends(get_db)):
    batch_id = str(uuid.uuid4())[:12]
    if body.test_ids:
        result = await db.execute(select(TestCase).where(TestCase.id.in_(body.test_ids)))
    else:
        result = await db.execute(select(TestCase).where(TestCase.is_active == True))
    tests = result.scalars().all()

    _batch_state[batch_id] = {"status": "running", "total": len(tests), "completed": 0,
                               "passed": 0, "failed": 0, "error": 0, "stopped": False}

    stats = {"passed": 0, "failed": 0, "error": 0}
    for tc in tests:
        if _batch_state[batch_id].get("stopped"):
            break
        run = TestRun(test_case_id=tc.id, batch_id=batch_id, status="running")
        db.add(run)
        await db.flush()

        start = time.time()
        src_res = {"rows": [], "count": 0, "error": None}
        tgt_res = {"rows": [], "count": 0, "error": None}

        try:
            if tc.source_query and tc.source_datasource_id:
                ds = _find_datasource(tc.source_datasource_id)
                if ds:
                    src_res = await asyncio.to_thread(_execute_sql, ds, tc.source_query)
            if tc.target_query and tc.target_datasource_id:
                ds = _find_datasource(tc.target_datasource_id)
                if ds:
                    tgt_res = await asyncio.to_thread(_execute_sql, ds, tc.target_query)

            elapsed = int((time.time() - start) * 1000)
            passed, mismatches, detail = _compare_results(tc, src_res, tgt_res)

            run.status = "passed" if passed else "failed"
            run.source_result = json.dumps(src_res["rows"][:10], default=str) if src_res["rows"] else None
            run.target_result = json.dumps(tgt_res["rows"][:10], default=str) if tgt_res["rows"] else None
            run.actual_result = json.dumps({"detail": detail}, default=str)
            run.mismatch_count = mismatches
            run.execution_time_ms = elapsed

            if src_res.get("error") or tgt_res.get("error"):
                run.status = "error"
                run.error_message = src_res.get("error") or tgt_res.get("error")
        except Exception as e:
            run.status = "error"
            run.error_message = str(e)

        stats[run.status] = stats.get(run.status, 0) + 1
        _batch_state[batch_id]["completed"] += 1
        _batch_state[batch_id][run.status] = _batch_state[batch_id].get(run.status, 0) + 1
        await db.commit()

    _batch_state[batch_id]["status"] = "completed"
    return {"batch_id": batch_id, "status": "completed", "total": len(tests), **stats}


@router.get("/run-batch/status/{batch_id}")
async def batch_status(batch_id: str):
    state = _batch_state.get(batch_id)
    if not state:
        raise HTTPException(404, "Batch not found")
    return {"batch_id": batch_id, **state}


@router.post("/run-batch/stop/{batch_id}")
async def stop_batch(batch_id: str):
    state = _batch_state.get(batch_id)
    if state:
        state["stopped"] = True
        state["status"] = "stopped"
    return {"batch_id": batch_id, "status": "stopped"}


# ── Test Runs ───────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(batch_id: Optional[str] = None, limit: int = 100, db: AsyncSession = Depends(get_db)):
    q = select(TestRun).order_by(TestRun.id.desc()).limit(limit)
    if batch_id:
        q = q.where(TestRun.batch_id == batch_id)
    result = await db.execute(q)
    runs = result.scalars().all()
    return [{"id": r.id, "test_case_id": r.test_case_id, "batch_id": r.batch_id,
             "status": r.status, "mismatch_count": r.mismatch_count,
             "error_message": r.error_message, "execution_time_ms": r.execution_time_ms,
             "executed_at": r.executed_at.isoformat() if r.executed_at else None,
             "source_result": r.source_result, "target_result": r.target_result,
             "actual_result": r.actual_result} for r in runs]


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(TestRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return {"id": r.id, "test_case_id": r.test_case_id, "batch_id": r.batch_id,
            "status": r.status, "source_result": r.source_result,
            "target_result": r.target_result, "actual_result": r.actual_result,
            "mismatch_count": r.mismatch_count, "error_message": r.error_message,
            "execution_time_ms": r.execution_time_ms,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None}


@router.post("/runs/clear")
async def clear_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(TestRun))
    await db.commit()
    return {"deleted": result.rowcount}


# ── Save Suite (bulk create from AI-generated tests) ────────────────────────

@router.post("/save-suite")
async def save_suite(body: SaveSuiteRequest, db: AsyncSession = Depends(get_db)):
    folder = TestFolder(name=body.suite_name)
    db.add(folder)
    await db.flush()

    created = []
    for t in body.tests:
        tc = TestCase(
            name=t.get("name") or t.get("title") or t.get("test_name", "Untitled"),
            test_type=t.get("test_type") or t.get("type", "custom_sql"),
            source_datasource_id=body.source_datasource_id or t.get("source_datasource_id"),
            source_query=t.get("source_query") or t.get("sql_validation") or t.get("sql"),
            target_query=t.get("target_query"),
            expected_result=t.get("expected_result"),
            tolerance=float(t.get("tolerance", 0)),
            severity=t.get("severity", "medium"),
            description=t.get("description", ""),
            is_ai_generated=True,
        )
        db.add(tc)
        await db.flush()
        db.add(TestCaseFolder(test_case_id=tc.id, folder_id=folder.id))
        created.append({"id": tc.id, "name": tc.name})

    await db.commit()
    return {"count": len(created), "suite_name": body.suite_name, "folder_id": folder.id, "tests": created}


# ── AI Generate (preserves original endpoint) ──────────────────────────────

class GenerateTestsRequest(BaseModel):
    prompt: str = ""
    target_table: str = ""
    source_table: str = ""
    context: str = ""
    mapping_rows: Optional[List[dict]] = None
    jira_context: Optional[dict] = None
    tfs_context: Optional[dict] = None
    artifact_ids: List[str] = []
    multi_layer: bool = True


@router.post("/generate")
async def generate_tests(body: GenerateTestsRequest):
    """Generate SQL validation tests from mapping context using AI."""
    from app.services.ai_service import ai_generate_tests
    from app.services.artifact_memory import get_artifact_content, list_artifacts

    context_parts = []
    if body.prompt:
        context_parts.append(body.prompt)
    if body.context:
        context_parts.append(body.context)
    if body.artifact_ids:
        art_index = {a["id"]: a for a in list_artifacts()}
        for art_id in body.artifact_ids[:8]:
            content = get_artifact_content(art_id)
            if content:
                meta = art_index.get(art_id, {})
                context_parts.append(f"=== {meta.get('name', art_id)} ===\n{content[:3000]}")

    combined_context = "\n\n".join(context_parts)
    try:
        result = await ai_generate_tests(
            context=combined_context,
            target_table=body.target_table,
            source_table=body.source_table,
            mapping_rows=body.mapping_rows,
            jira_context=body.jira_context,
            tfs_context=body.tfs_context,
            multi_layer=body.multi_layer,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ── TestRail Export (preserved) ─────────────────────────────────────────────

class ExportTestrailRequest(BaseModel):
    tests: List[dict]
    project_id: Optional[int] = None
    section_id: Optional[int] = None
    suite_id: Optional[int] = None
    milestone_id: Optional[int] = None


@router.post("/export-testrail")
async def export_to_testrail(body: ExportTestrailRequest):
    from app.services.testrail_service import bulk_add_test_cases
    if not body.section_id:
        return {"ok": True, "exported": 0, "message": "No TestRail section specified."}
    try:
        results = await bulk_add_test_cases(body.section_id, body.tests)
        return {"ok": True, "exported": len(results), "cases": results}
    except Exception as e:
        raise HTTPException(500, str(e))
