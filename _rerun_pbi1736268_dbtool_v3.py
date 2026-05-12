import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "http://localhost:8550"
DS_ID = 2
BUSINESS_DATE = "2026-03-30"
STREAMS = "29,30,71,72"


def post(path: str, payload: dict, timeout: int = 120):
    r = requests.post(f"{BASE}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get(path: str, timeout: int = 120):
    r = requests.get(f"{BASE}{path}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def query(sql: str, limit: int = 1000):
    return post(f"/api/datasources/{DS_ID}/query", {"sql": sql, "limit": limit}, timeout=180)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def escape_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\- ]+", "_", name).strip()


def build_common_cte() -> str:
    return f"""
WITH src AS (
    SELECT
        stg.txn_src_key,
        stg.td,
        stg.to_location,
        stg.from_location,
        stg.shares,
        stg.trailer,
        stg.option_cls,
        stg.security_type,
        stg.product_category,
        stg.term_name,
        stg.ws_mkt_mkr_5,
        stg.ws_subtype,
        stg.ws_cnx_ind,
        stg.ws_execution_subtype,
        UPPER(REGEXP_REPLACE(NVL(stg.trailer, ' '), '^[[:space:]]+', '')) AS trlr
    FROM CDS_STG_OWNER.STCCCALQ_GG_VW stg
    WHERE stg.ws_exception_text = 'MATCH NOT FOUND'
),
parsed AS (
    SELECT
        src.txn_src_key,
        map.trlr_rule_txt,
        map.regex_patt,
        map.rec_tp_seq,
        map.txn_sbtp_cd,
        map.exec_sbtp_cd,
        map.cnx_ind AS src_pcs_tp_cd,
        map.cdsm_rule_map_id,
        CASE
            WHEN INSTR(NVL(map.trlr_rule_txt, ' '), '<') = 0 THEN 1
            WHEN INSTR(NVL(map.trlr_rule_txt, ' '), '<VARPLUS>') > 0 THEN 3
            ELSE 2
        END AS prty
    FROM src
    JOIN CCAL_OWNER.CDSM_RULE_MAP map
      ON map.eff_dt <= TRUNC(NVL(src.td, SYSDATE))
     AND map.end_dt > TRUNC(NVL(src.td, SYSDATE))
     AND map.calling_prgm = 'STRCCDSB'
     AND map.rec_tp = 7
     AND (map.fm_loc IS NULL OR map.fm_loc = src.from_location)
     AND (map.to_loc IS NULL OR map.to_loc = src.to_location)
     AND (map.sec_tp IS NULL OR map.sec_tp = src.security_type)
     AND (map.pd_cgy IS NULL OR map.pd_cgy = src.product_category)
     AND (
            map.trlr_shs_tp_cd IS NULL
         OR (map.trlr_shs_tp_cd = 'Y' AND src.shares <> 0)
         OR (map.trlr_shs_tp_cd = 'P' AND src.shares > 0)
         OR (map.trlr_shs_tp_cd = 'N' AND src.shares < 0)
         )
     AND (map.opt_cls IS NULL OR map.opt_cls = src.option_cls)
     AND (map.src_prgm IS NULL OR map.src_prgm = src.term_name)
     AND (map.mkt_mkr_5 IS NULL OR map.mkt_mkr_5 = src.ws_mkt_mkr_5)
    WHERE REGEXP_LIKE(src.trlr, map.regex_patt, 'c')
),
ranked AS (
    SELECT
        parsed.txn_src_key,
        parsed.txn_sbtp_cd,
        parsed.exec_sbtp_cd,
        parsed.src_pcs_tp_cd,
        parsed.cdsm_rule_map_id,
        ROW_NUMBER() OVER (
            PARTITION BY parsed.txn_src_key
            ORDER BY parsed.prty, parsed.trlr_rule_txt, parsed.rec_tp_seq
        ) AS rn
    FROM parsed
),
final_map AS (
    SELECT
        r.txn_src_key,
        r.txn_sbtp_cd,
        (
            SELECT cl_val_id
            FROM ccal_owner.cl_val_vw
            WHERE cl_val_code = TRIM(r.txn_sbtp_cd)
              AND cl_scm_code = 'TXNSBTP'
              AND ROWNUM = 1
        ) AS txn_sbtp_id,
        r.exec_sbtp_cd,
        (
            SELECT cl_val_id
            FROM ccal_owner.cl_val_vw
            WHERE cl_val_code = TRIM(r.exec_sbtp_cd)
              AND cl_scm_code = 'EXECSBTP'
              AND ROWNUM = 1
        ) AS exec_sbtp_id,
        r.src_pcs_tp_cd,
        (
            SELECT cl_val_id
            FROM ccal_owner.cl_val_vw
            WHERE cl_val_code = TRIM(r.src_pcs_tp_cd)
              AND cl_scm_code = 'SRCPCSTP'
              AND ROWNUM = 1
        ) AS src_pcs_tp_id,
        r.cdsm_rule_map_id
    FROM ranked r
    WHERE r.rn = 1
),
scoped_txn AS (
    SELECT t.*
    FROM ccal_owner.txn t
    WHERE t.td = DATE '{BUSINESS_DATE}'
      AND t.src_stm_id IN ({STREAMS})
)
"""


def build_tests():
    cte = build_common_cte()
    return [
        {
            "name": "Regex parse produces mapping candidates",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM final_map",
            "expected": ">0",
        },
        {
            "name": "Every scoped TXN has source row with MATCH NOT FOUND",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN src s ON s.txn_src_key=t.txn_src_key WHERE s.txn_src_key IS NULL",
            "expected": "0",
        },
        {
            "name": "Every scoped TXN has exactly one ranked regex rule",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE f.txn_src_key IS NULL",
            "expected": "0",
        },
        {
            "name": "No duplicate winning regex row per TXN",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM (SELECT txn_src_key, COUNT(*) c FROM final_map GROUP BY txn_src_key HAVING COUNT(*) > 1)",
            "expected": "0",
        },
        {
            "name": "TXN.TXN_SBTP_ID matches regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.txn_sbtp_id,-1) <> NVL(f.txn_sbtp_id,-1)",
            "expected": "0",
        },
        {
            "name": "TXN.EXEC_SBTP_ID matches regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.exec_sbtp_id,-1) <> NVL(f.exec_sbtp_id,-1)",
            "expected": "0",
        },
        {
            "name": "TXN.SRC_PCS_TP_ID matches regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.src_pcs_tp_id,-1) <> NVL(f.src_pcs_tp_id,-1)",
            "expected": "0",
        },
        {
            "name": "Mapped CDSM_RULE_MAP row is active and RecordType 7",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM final_map f JOIN ccal_owner.cdsm_rule_map m ON m.cdsm_rule_map_id=f.cdsm_rule_map_id WHERE NOT (m.actv_f='Y' AND m.rec_tp=7)",
            "expected": "0",
        },
        {
            "name": "Rule effective dates cover TXN business date",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key JOIN ccal_owner.cdsm_rule_map m ON m.cdsm_rule_map_id=f.cdsm_rule_map_id WHERE NOT (m.eff_dt <= TRUNC(t.td) AND m.end_dt > TRUNC(t.td))",
            "expected": "0",
        },
        {
            "name": "APA exists for each scoped TXN",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN ccal_owner.apa a ON a.exec_id=t.txn_id WHERE a.apa_id IS NULL",
            "expected": "0",
        },
        {
            "name": "FIP rows linked to scoped TXN reference valid APA",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM ccal_owner.fip f JOIN ccal_owner.apa a ON a.apa_id=f.apa_id JOIN scoped_txn t ON t.txn_id=a.exec_id WHERE a.apa_id IS NULL",
            "expected": "0",
        },
        {
            "name": "TXN_RLTNP rows linked to scoped TXN have valid endpoints",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM ccal_owner.txn_rltnp r JOIN scoped_txn bt ON (bt.txn_id=r.src_txn_id OR bt.txn_id=r.trgt_txn_id) LEFT JOIN ccal_owner.txn s ON s.txn_id=r.src_txn_id LEFT JOIN ccal_owner.txn t ON t.txn_id=r.trgt_txn_id WHERE s.txn_id IS NULL OR t.txn_id IS NULL",
            "expected": "0",
        },
    ]


def assert_sql_works(sql: str):
    data = query(sql, limit=20)
    if isinstance(data, dict) and data.get("detail"):
        raise RuntimeError(data["detail"])
    rows = data.get("rows", [])
    if not rows:
        raise RuntimeError("No result rows returned")
    key = next(iter(rows[0].keys()))
    val = rows[0][key]
    return val


def create_folder(name: str):
    return post("/api/tests/folders", {"name": name}, timeout=60)


def create_test(folder_id: int, test: dict):
    payload = {
        "name": test["name"],
        "test_type": "custom_sql",
        "source_datasource_id": DS_ID,
        "target_datasource_id": None,
        "source_query": test["sql"],
        "target_query": None,
        "expected_result": test["expected"],
        "tolerance": 0,
        "severity": "critical",
        "description": "PBI1736268 trailer parsing regex validation (source->rule_map->target)",
        "is_ai_generated": False,
        "folder_id": folder_id,
    }
    return post("/api/tests", payload, timeout=90)


def run_batch(test_ids):
    started = post("/api/tests/run-batch/start", {"test_ids": test_ids}, timeout=60)
    batch_id = started["batch_id"]
    for _ in range(120):
        time.sleep(2)
        status = get(f"/api/tests/run-batch/status/{batch_id}", timeout=60)
        if status.get("status") in {"completed", "stopped", "error"}:
            return batch_id, status
    return batch_id, {"status": "timeout"}


def main():
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save source and rule-map schemas for traceability.
    src_cols = query("SELECT column_name FROM all_tab_columns WHERE owner='CDS_STG_OWNER' AND table_name='STCCCALQ_GG_VW' ORDER BY column_id")
    map_cols = query("SELECT column_name FROM all_tab_columns WHERE owner='CCAL_OWNER' AND table_name='CDSM_RULE_MAP' ORDER BY column_id")
    save_json(out_dir / "stcccalq_gg_vw_columns.json", src_cols)
    save_json(out_dir / "cdsm_rule_map_columns.json", map_cols)

    tests = build_tests()

    # Pre-validate all SQL against datasource to fail early on syntax/column issues.
    probe_results = []
    for t in tests:
        try:
            val = assert_sql_works(t["sql"])
            probe_results.append({"name": t["name"], "ok": True, "sample_value": val})
        except Exception as exc:
            probe_results.append({"name": t["name"], "ok": False, "error": str(exc)})
    save_json(out_dir / "dbtool_v3_probe_results.json", probe_results)

    failed = [p for p in probe_results if not p["ok"]]
    if failed:
        raise RuntimeError(f"Probe failed for {len(failed)} tests; aborting save. First error: {failed[0]}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"PBI1736268-TrailerParsing-v3-DB-{stamp}"
    folder = create_folder(folder_name)

    created = []
    for t in tests:
        c = create_test(folder["id"], t)
        created.append({"id": c["id"], "name": c["name"]})

    test_ids = [c["id"] for c in created]
    batch_id, run_status = run_batch(test_ids)

    folders = get("/api/tests/folders", timeout=60)
    folder_snapshot = next((f for f in folders if f.get("id") == folder["id"]), None)

    # SQLite verification against actual db file used by app.
    db_path = Path((Path.home() / "AppData" / "Local" / "DBTestingTool" / "app.db"))
    sqlite_verify = {"db_path": str(db_path), "exists": db_path.exists()}
    if db_path.exists():
        import sqlite3
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM test_case_folders WHERE folder_id=?", (folder["id"],))
        sqlite_verify["linked_tests"] = cur.fetchone()[0]
        cur.execute("SELECT test_case_id FROM test_case_folders WHERE folder_id=? ORDER BY test_case_id", (folder["id"],))
        sqlite_verify["test_case_ids"] = [r[0] for r in cur.fetchall()]
        con.close()

    report = {
        "timestamp": stamp,
        "business_date": BUSINESS_DATE,
        "streams": STREAMS,
        "folder": folder,
        "created_tests": created,
        "batch_id": batch_id,
        "run_status": run_status,
        "folder_snapshot": folder_snapshot,
        "sqlite_verify": sqlite_verify,
        "artifacts_dir": str(out_dir),
        "probe_results": probe_results,
    }

    out_file = out_dir / f"dbtool_v3_rerun_result_{stamp}.json"
    save_json(out_file, report)

    print("ARTIFACTS_DIR", out_dir)
    print("RESULT_FILE", out_file)
    print("FOLDER", folder)
    print("TEST_IDS", test_ids)
    print("BATCH", batch_id)
    print("RUN_STATUS", run_status)
    print("FOLDER_SNAPSHOT", folder_snapshot)
    print("SQLITE_VERIFY", sqlite_verify)


if __name__ == "__main__":
    main()
