import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.ai_service import (
    orchestrate_test_generation,
    build_tfs_and_schema_context,
    analyze_etl_requirements,
    design_sql_tests,
)

OUT_ROOT = ROOT / "reports" / "e2e_batch_runs"


def read_artifact(path: str, max_chars: int = 32000) -> str:
    p = Path(path)
    if not p.exists():
        return f"[MISSING ARTIFACT] {path}"
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as exc:
        return f"[ARTIFACT READ ERROR] {path}: {exc}"


def write_test_outputs(folder: Path, tests: List[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "tests.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")

    sql_chunks: List[str] = []
    for idx, test in enumerate(tests, start=1):
        sql_chunks.append(f"-- Test {idx}: {test.get('name', 'Unnamed')}")
        sql_chunks.append("-- Source Query")
        sql_chunks.append((test.get("source_query") or "").strip())
        sql_chunks.append("\n-- Target Query")
        sql_chunks.append((test.get("target_query") or "").strip())
        sql_chunks.append("\n")

    (folder / "tests.sql").write_text("\n".join(sql_chunks), encoding="utf-8")


def build_scenarios() -> List[Dict[str, object]]:
    odi_stcccalq = r"C:\Users\ikorostelev\Downloads\SCEN_CCAL_PKG_LOAD_TX_STCCCALQ_STG_Version_001.xml"
    odi_sbdi = r"C:\Users\ikorostelev\Downloads\SCEN_CCAL_PKG_LOAD_TX_SBDI_RT_MT_Version_001.xml"
    drd_csv = r"C:\GIT_Repo\DRD_Activity_Fact(Table-View).csv"
    drd_xlsx = r"C:\GIT_Repo\DRD_Activity_Fact.xlsx"
    control_patch = str(ROOT / "control-table-fix.patch")

    return [
        {
            "name": "pbi_1736268_trailer",
            "tfs_item_id": "1736268",
            "validation_datasource_id": 2,
            "prompt": (
                "PBI 1736268. Generate Oracle ETL validation tests for trailer-rule population into "
                "CCAL_OWNER.TXN, CCAL_OWNER.APA, CCAL_OWNER.FIP, CCAL_OWNER.TXN_RLTNP. "
                "Do not assume hardcoded CTEs. Derive logic from ODI artifacts and schema context. "
                "Validate txn_src_key level mapping for txn_sbtp_id, exec_sbtp_id, src_pcs_tp_id."
            ),
            "artifact_paths": [odi_stcccalq, odi_sbdi],
        },
        {
            "name": "pbi_1915216_trailer_3_sources",
            "tfs_item_id": "1915216",
            "validation_datasource_id": 2,
            "prompt": (
                "PBI 1915216. Same trailer-rule business requirement as 1736268 but source is split across "
                "three source tables instead of a single GG view. Generate Oracle ETL validation tests for "
                "CCAL_OWNER target population and validate cross-source joins and trailer rule ranking. "
                "Do not hardcode source CTE assumptions; infer from artifacts."
            ),
            "artifact_paths": [odi_stcccalq, odi_sbdi],
        },
        {
            "name": "ct_control_table_validation",
            "tfs_item_id": None,
            "validation_datasource_id": 2,
            "prompt": (
                "Generate Oracle SQL validation tests for control-table behavior (CT): task/session tracking, "
                "error threshold handling, and partition/thread isolation behavior in ETL flow. "
                "Use provided artifacts to derive control table dependencies and validation assertions."
            ),
            "artifact_paths": [odi_stcccalq, control_patch],
        },
        {
            "name": "drd_mapping_validation",
            "tfs_item_id": None,
            "validation_datasource_id": None,
            "skip_validation": True,
            "prompt": (
                "Generate Oracle SQL validation tests from DRD mapping content for source-to-target correctness, "
                "required field mappings, and business-rule checks. Build tests aligned to DRD table/view definitions."
            ),
            "artifact_paths": [drd_csv, drd_xlsx],
        },
    ]


async def run_one(run_folder: Path, scenario: Dict[str, object], validation_datasource_id: Optional[int]) -> Dict[str, object]:
    name = str(scenario["name"])
    out = run_folder / name
    out.mkdir(parents=True, exist_ok=True)

    artifact_contents = [read_artifact(p) for p in scenario.get("artifact_paths", [])]
    prompt = str(scenario["prompt"])
    tfs_item_id = scenario.get("tfs_item_id")
    scenario_validation_ds = scenario.get("validation_datasource_id", validation_datasource_id)
    skip_validation = bool(scenario.get("skip_validation", False))

    result: Dict[str, object] = {
        "scenario": name,
        "tfs_item_id": tfs_item_id,
        "status": "ok",
        "test_count": 0,
        "output_folder": str(out),
    }

    try:
        if skip_validation:
            context = await build_tfs_and_schema_context(
                tfs_item_id=str(tfs_item_id) if tfs_item_id is not None else None,
                artifact_contents=artifact_contents,
                user_prompt=prompt,
            )
            spec = await analyze_etl_requirements(context)
            tests = await design_sql_tests(spec, db_dialect="oracle")
        else:
            tests = await orchestrate_test_generation(
                tfs_item_id=str(tfs_item_id) if tfs_item_id is not None else None,
                artifact_contents=artifact_contents,
                user_prompt=prompt,
                db_dialect="oracle",
                validation_datasource_id=scenario_validation_ds,
            )

        payload = [t.model_dump() for t in tests]
        write_test_outputs(out, payload)
        result["test_count"] = len(payload)

    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        (out / "error.txt").write_text(str(exc), encoding="utf-8")

    (out / "scenario_meta.json").write_text(json.dumps({
        "scenario": scenario,
        "result": result,
    }, indent=2), encoding="utf-8")

    return result


async def main(only: Optional[List[str]] = None) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = OUT_ROOT / ts
    run_folder.mkdir(parents=True, exist_ok=True)

    scenarios = build_scenarios()
    if only:
        allowed = {name.strip().lower() for name in only if name.strip()}
        scenarios = [s for s in scenarios if str(s.get("name", "")).lower() in allowed]

    summary: List[Dict[str, object]] = []

    for scenario in scenarios:
        res = await run_one(run_folder, scenario, validation_datasource_id=2)
        summary.append(res)
        print(f"[{res['status'].upper()}] {res['scenario']} -> tests={res.get('test_count', 0)}")

    (run_folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    ok = sum(1 for s in summary if s.get("status") == "ok")
    err = sum(1 for s in summary if s.get("status") != "ok")
    print(f"\nBatch completed. Success={ok}, Errors={err}")
    print(f"Output: {run_folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run E2E batch orchestration scenarios")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Optional scenario names to run (e.g., drd_mapping_validation)",
    )
    args = parser.parse_args()
    asyncio.run(main(only=args.only))
