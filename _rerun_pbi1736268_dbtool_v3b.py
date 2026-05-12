import json
import sqlite3
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
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} {path}: {r.text[:1200]}")
    return r.json()


def get(path: str, timeout: int = 120):
    r = requests.get(f"{BASE}{path}", timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} {path}: {r.text[:1200]}")
    return r.json()


def query(sql: str, limit: int = 1000):
    data = post(f"/api/datasources/{DS_ID}/query", {"sql": sql, "limit": limit}, timeout=240)
    if isinstance(data, dict) and data.get("detail"):
        raise RuntimeError(str(data["detail"]))
    return data


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def common_cte() -> str:
    return f"""
WITH src AS (
    SELECT
        s.txn_src_key,
        t.td,
        s.to_location,
        s.from_location,
        s.shares,
        s.trailer,
        s.option_cls,
        s.security_type_n,
        s.security_type_x,
        s.ws_product_category,
        s.term_name,
        s.ws_market_maker_5,
        s.ws_subtype,
        s.ws_cnx_ind,
        s.ws_execution_subtype,
        s.ws_trailer_rule_text_match,
        s.record_type_multi,
        UPPER(REGEXP_REPLACE(NVL(s.trailer, ' '), '^[[:space:]]+', '')) AS trlr
    FROM CDS_STG_OWNER.STCCCALQ_GG_VW s
    JOIN CCAL_OWNER.TXN t
      ON t.txn_src_key = s.txn_src_key
    WHERE t.td = DATE '{BUSINESS_DATE}'
      AND t.src_stm_id IN ({STREAMS})
      AND s.ws_exception_text = 'MATCH NOT FOUND'
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
            WHEN map.has_tokens = 0 THEN 1
            WHEN map.has_varplus = 1 THEN 3
            ELSE 2
        END AS prty
    FROM src
    JOIN CCAL_OWNER.CDSM_RULE_MAP map
      ON map.eff_dt <= TRUNC(src.td)
     AND map.end_dt > TRUNC(src.td)
     AND map.calling_prgm = 'STRCCDSB'
     AND map.rec_tp = 7
     AND map.actv_f = 'Y'
     AND (map.fm_loc IS NULL OR map.fm_loc = src.from_location)
     AND (map.to_loc IS NULL OR map.to_loc = src.to_location)
     AND (map.sec_tp IS NULL OR map.sec_tp IN (src.security_type_n, src.security_type_x))
     AND (map.pd_cgy IS NULL OR map.pd_cgy = src.ws_product_category)
     AND (
            map.trlr_shs_tp_cd IS NULL
         OR (map.trlr_shs_tp_cd = 'Y' AND src.shares <> 0)
         OR (map.trlr_shs_tp_cd = 'P' AND src.shares > 0)
         OR (map.trlr_shs_tp_cd = 'N' AND src.shares < 0)
         )
     AND (map.opt_cls IS NULL OR map.opt_cls = src.option_cls)
     AND (map.src_prgm IS NULL OR map.src_prgm = src.term_name)
     AND (map.mkt_mkr_5 IS NULL OR map.mkt_mkr_5 = src.ws_market_maker_5)
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
            FROM CCAL_OWNER.CL_VAL_VW
            WHERE cl_val_code = TRIM(r.txn_sbtp_cd)
              AND cl_scm_code = 'TXNSBTP'
              AND ROWNUM = 1
        ) AS txn_sbtp_id,
        r.exec_sbtp_cd,
        (
            SELECT cl_val_id
            FROM CCAL_OWNER.CL_VAL_VW
            WHERE cl_val_code = TRIM(r.exec_sbtp_cd)
              AND cl_scm_code = 'EXECSBTP'
              AND ROWNUM = 1
        ) AS exec_sbtp_id,
        r.src_pcs_tp_cd,
        (
            SELECT cl_val_id
            FROM CCAL_OWNER.CL_VAL_VW
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
    FROM CCAL_OWNER.TXN t
    WHERE t.td = DATE '{BUSINESS_DATE}'
      AND t.src_stm_id IN ({STREAMS})
)
"""


def build_tests():
    cte = common_cte()
    return [
        {
            "name": "Regex parsing produced at least one winning rule",
            "sql": cte + "SELECT CASE WHEN COUNT(*) > 0 THEN 0 ELSE 1 END AS CNT FROM final_map",
            "expected": "0",
        },
        {
            "name": "Every scoped TXN has source MATCH NOT FOUND row",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN src s ON s.txn_src_key=t.txn_src_key WHERE s.txn_src_key IS NULL",
            "expected": "0",
        },
        {
            "name": "Every scoped TXN has regex winner row",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE f.txn_src_key IS NULL",
            "expected": "0",
        },
        {
            "name": "No duplicate winning regex rows per TXN",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM (SELECT txn_src_key, COUNT(*) c FROM final_map GROUP BY txn_src_key HAVING COUNT(*) > 1)",
            "expected": "0",
        },
        {
            "name": "TXN_SBTP_ID equals regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.txn_sbtp_id,-1) <> NVL(f.txn_sbtp_id,-1)",
            "expected": "0",
        },
        {
            "name": "EXEC_SBTP_ID equals regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.exec_sbtp_id,-1) <> NVL(f.exec_sbtp_id,-1)",
            "expected": "0",
        },
        {
            "name": "SRC_PCS_TP_ID equals regex-derived mapped id",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t JOIN final_map f ON f.txn_src_key=t.txn_src_key WHERE NVL(t.src_pcs_tp_id,-1) <> NVL(f.src_pcs_tp_id,-1)",
            "expected": "0",
        },
        {
            "name": "Rule-text match column links to active rule row",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM src s LEFT JOIN CCAL_OWNER.CDSM_RULE_MAP m ON m.trlr_rule_txt=s.ws_trailer_rule_text_match AND m.actv_f='Y' WHERE s.ws_trailer_rule_text_match IS NOT NULL AND m.cdsm_rule_map_id IS NULL",
            "expected": "0",
        },
        {
            "name": "WS_EXECUTION_SUBTYPE agrees with mapped rule EXEC_SBTP_CD",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM src s JOIN final_map f ON f.txn_src_key=s.txn_src_key JOIN CCAL_OWNER.CDSM_RULE_MAP m ON m.cdsm_rule_map_id=f.cdsm_rule_map_id WHERE m.exec_sbtp_cd IS NOT NULL AND NVL(s.ws_execution_subtype,'~') <> NVL(m.exec_sbtp_cd,'~')",
            "expected": "0",
        },
        {
            "name": "APA exists for each scoped TXN",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM scoped_txn t LEFT JOIN CCAL_OWNER.APA a ON a.exec_id=t.txn_id WHERE a.apa_id IS NULL",
            "expected": "0",
        },
        {
            "name": "FIP rows for scoped TXN have valid APA",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.FIP f JOIN CCAL_OWNER.APA a ON a.apa_id=f.apa_id JOIN scoped_txn t ON t.txn_id=a.exec_id WHERE a.apa_id IS NULL",
            "expected": "0",
        },
        {
            "name": "TXN_RLTNP rows for scoped TXN have valid endpoints",
            "sql": cte + "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN_RLTNP r JOIN scoped_txn bt ON (bt.txn_id=r.src_txn_id OR bt.txn_id=r.trgt_txn_id) LEFT JOIN CCAL_OWNER.TXN s ON s.txn_id=r.src_txn_id LEFT JOIN CCAL_OWNER.TXN t ON t.txn_id=r.trgt_txn_id WHERE s.txn_id IS NULL OR t.txn_id IS NULL",
            "expected": "0",
        },
    ]


def probe_tests(tests):
    out = []
    for t in tests:
        try:
            data = query(t["sql"], limit=20)
            rows = data.get("rows", [])
            val = None
            if rows:
                first_key = list(rows[0].keys())[0]
                val = rows[0][first_key]
            out.append({"name": t["name"], "ok": True, "value": val})
        except Exception as exc:
            out.append({"name": t["name"], "ok": False, "error": str(exc)})
    return out


def create_folder(name: str):
    return post("/api/tests/folders", {"name": name}, timeout=60)


def create_test(folder_id: int, t: dict):
    payload = {
        "name": t["name"],
        "test_type": "custom_sql",
        "source_datasource_id": DS_ID,
        "target_datasource_id": None,
        "source_query": t["sql"],
        "target_query": None,
        "expected_result": t["expected"],
        "tolerance": 0,
        "severity": "critical",
        "description": "PBI1736268 regex trailer parsing validation against CDSM_RULE_MAP",
        "is_ai_generated": False,
        "folder_id": folder_id,
    }
    return post("/api/tests", payload, timeout=90)


def move_tests_to_folder(test_ids, folder_id: int):
    return post("/api/tests/folders/move", {"test_ids": test_ids, "folder_id": folder_id}, timeout=90)


def run_batch(ids):
    start = post("/api/tests/run-batch/start", {"test_ids": ids}, timeout=60)
    bid = start["batch_id"]
    for _ in range(120):
        time.sleep(2)
        st = get(f"/api/tests/run-batch/status/{bid}", timeout=60)
        if st.get("status") in ("completed", "stopped", "error"):
            return bid, st
    return bid, {"status": "timeout"}


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    tests = build_tests()
    probes = probe_tests(tests)
    save_json(out_dir / f"dbtool_v3b_probe_{stamp}.json", probes)

    failed = [p for p in probes if not p["ok"]]
    if failed:
        raise RuntimeError(f"Probe errors: {failed[0]}")

    folder_name = f"PBI1736268-TrailerParsing-v3-DB-{stamp}"
    folder = create_folder(folder_name)

    created = []
    for t in tests:
        tc = create_test(folder["id"], t)
        created.append({"id": tc["id"], "name": tc["name"]})

    ids = [c["id"] for c in created]
    move_result = move_tests_to_folder(ids, folder["id"])
    batch_id, run_status = run_batch(ids)

    folders = get("/api/tests/folders", timeout=60)
    folder_snapshot = next((f for f in folders if f.get("id") == folder["id"]), None)

    db_path = Path.home() / "AppData" / "Local" / "DBTestingTool" / "app.db"
    sqlite_verify = {"path": str(db_path), "exists": db_path.exists()}
    if db_path.exists():
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM test_case_folders WHERE folder_id=?", (folder["id"],))
        sqlite_verify["linked_tests"] = cur.fetchone()[0]
        cur.execute("SELECT test_case_id FROM test_case_folders WHERE folder_id=? ORDER BY test_case_id", (folder["id"],))
        sqlite_verify["test_case_ids"] = [r[0] for r in cur.fetchall()]
        con.close()

    report = {
        "folder": folder,
        "move_result": move_result,
        "folder_snapshot": folder_snapshot,
        "created_tests": created,
        "batch_id": batch_id,
        "run_status": run_status,
        "sqlite_verify": sqlite_verify,
        "artifact_dir": str(out_dir),
        "probe": probes,
    }
    report_file = out_dir / f"dbtool_v3b_result_{stamp}.json"
    save_json(report_file, report)

    print("ARTIFACT_DIR", out_dir)
    print("REPORT_FILE", report_file)
    print("FOLDER", folder)
    print("TEST_IDS", ids)
    print("BATCH", batch_id)
    print("RUN_STATUS", run_status)
    print("FOLDER_SNAPSHOT", folder_snapshot)
    print("SQLITE_VERIFY", sqlite_verify)


if __name__ == "__main__":
    main()
