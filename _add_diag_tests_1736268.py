import json
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
    r = requests.get(f"{BASE}{path},", timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} {path}: {r.text[:1200]}")
    return r.json()


def query(sql: str, limit: int = 2000):
    r = requests.post(
        f"{BASE}/api/datasources/{DS_ID}/query",
        json={"sql": sql, "limit": limit},
        timeout=240,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"query failed {r.status_code}: {r.text[:1200]}")
    d = r.json()
    if isinstance(d, dict) and d.get("detail"):
        raise RuntimeError(str(d["detail"]))
    return d


def common_cte() -> str:
    return f"""
WITH src AS (
    SELECT
        s.txn_src_key,
        t.td,
        t.txn_id,
        t.src_stm_id,
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
    SELECT *
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


def create_test(t: dict):
    payload = {
        "name": t["name"],
        "test_type": "custom_sql",
        "source_datasource_id": DS_ID,
        "target_datasource_id": None,
        "source_query": t["sql"],
        "target_query": None,
        "expected_result": str(t["expected"]),
        "tolerance": 0,
        "severity": "high",
        "description": "Diagnostic tests for PBI1736268 failed trailer-parsing checks",
        "is_ai_generated": False,
    }
    return post("/api/tests", payload, timeout=90)


def run_batch(test_ids):
    started = post("/api/tests/run-batch/start", {"test_ids": test_ids}, timeout=60)
    bid = started["batch_id"]
    for _ in range(120):
        time.sleep(2)
        s = requests.get(f"{BASE}/api/tests/run-batch/status/{bid}", timeout=60)
        s.raise_for_status()
        data = s.json()
        if data.get("status") in ("completed", "stopped", "error"):
            return bid, data
    return bid, {"status": "timeout"}


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    cte = common_cte()

    missing_src_sql = cte + """
SELECT COUNT(*) AS CNT
FROM scoped_txn t
LEFT JOIN src s ON s.txn_src_key=t.txn_src_key
WHERE s.txn_src_key IS NULL
"""

    missing_winner_sql = cte + """
SELECT COUNT(*) AS CNT
FROM scoped_txn t
LEFT JOIN final_map f ON f.txn_src_key=t.txn_src_key
WHERE f.txn_src_key IS NULL
"""

    winner_count_sql = cte + "SELECT COUNT(*) AS CNT FROM final_map"

    expected_missing_src = query(missing_src_sql, 50)["rows"][0]["CNT"]
    expected_missing_winner = query(missing_winner_sql, 50)["rows"][0]["CNT"]
    expected_winner_count = query(winner_count_sql, 50)["rows"][0]["CNT"]

    tests = [
        {
            "name": "DIAG count TXNs missing MATCH_NOT_FOUND source row",
            "sql": missing_src_sql,
            "expected": expected_missing_src,
        },
        {
            "name": "DIAG count TXNs missing regex winner row",
            "sql": missing_winner_sql,
            "expected": expected_missing_winner,
        },
        {
            "name": "DIAG count regex winner rows",
            "sql": winner_count_sql,
            "expected": expected_winner_count,
        },
    ]

    # Row-level evidence outputs.
    missing_src_rows_sql = cte + """
SELECT t.txn_id, t.txn_src_key, t.src_stm_id, t.td
FROM scoped_txn t
LEFT JOIN src s ON s.txn_src_key=t.txn_src_key
WHERE s.txn_src_key IS NULL
ORDER BY t.txn_id
"""

    missing_winner_rows_sql = cte + """
SELECT s.txn_id, s.txn_src_key, s.src_stm_id, s.record_type_multi, s.term_name,
       SUBSTR(s.trailer,1,120) AS trailer_prefix
FROM src s
LEFT JOIN final_map f ON f.txn_src_key=s.txn_src_key
WHERE f.txn_src_key IS NULL
ORDER BY s.txn_id
"""

    rule_fit_sql = cte + """
SELECT s.txn_id, s.txn_src_key,
       COUNT(map.cdsm_rule_map_id) AS candidate_rules_before_regex,
       SUM(CASE WHEN REGEXP_LIKE(s.trlr, map.regex_patt, 'c') THEN 1 ELSE 0 END) AS candidate_rules_after_regex
FROM src s
JOIN CCAL_OWNER.CDSM_RULE_MAP map
  ON map.eff_dt <= TRUNC(s.td)
 AND map.end_dt > TRUNC(s.td)
 AND map.calling_prgm = 'STRCCDSB'
 AND map.rec_tp = 7
 AND map.actv_f = 'Y'
 AND (map.fm_loc IS NULL OR map.fm_loc = s.from_location)
 AND (map.to_loc IS NULL OR map.to_loc = s.to_location)
 AND (map.sec_tp IS NULL OR map.sec_tp IN (s.security_type_n, s.security_type_x))
 AND (map.pd_cgy IS NULL OR map.pd_cgy = s.ws_product_category)
 AND (
        map.trlr_shs_tp_cd IS NULL
     OR (map.trlr_shs_tp_cd = 'Y' AND s.shares <> 0)
     OR (map.trlr_shs_tp_cd = 'P' AND s.shares > 0)
     OR (map.trlr_shs_tp_cd = 'N' AND s.shares < 0)
     )
 AND (map.opt_cls IS NULL OR map.opt_cls = s.option_cls)
 AND (map.src_prgm IS NULL OR map.src_prgm = s.term_name)
 AND (map.mkt_mkr_5 IS NULL OR map.mkt_mkr_5 = s.ws_market_maker_5)
GROUP BY s.txn_id, s.txn_src_key
ORDER BY s.txn_id
"""

    missing_src_rows = query(missing_src_rows_sql, 500)
    missing_winner_rows = query(missing_winner_rows_sql, 500)
    rule_fit_rows = query(rule_fit_sql, 1000)

    (out_dir / f"diag_missing_src_rows_{stamp}.json").write_text(json.dumps(missing_src_rows, indent=2), encoding="utf-8")
    (out_dir / f"diag_missing_winner_rows_{stamp}.json").write_text(json.dumps(missing_winner_rows, indent=2), encoding="utf-8")
    (out_dir / f"diag_rule_fit_{stamp}.json").write_text(json.dumps(rule_fit_rows, indent=2), encoding="utf-8")

    # Find latest v3 folder and append tests.
    folders = requests.get(f"{BASE}/api/tests/folders", timeout=60).json()
    v3 = [f for f in folders if str(f.get("name", "")).startswith("PBI1736268-TrailerParsing-v3-DB-")]
    if not v3:
        raise RuntimeError("No v3 folder found")
    folder = sorted(v3, key=lambda x: x.get("id", 0))[-1]

    created = [create_test(t) for t in tests]
    ids = [t["id"] for t in created]
    move = post("/api/tests/folders/move", {"test_ids": ids, "folder_id": folder["id"]}, timeout=90)

    batch_id, batch_status = run_batch(ids)

    latest_folders = requests.get(f"{BASE}/api/tests/folders", timeout=60).json()
    snap = next((f for f in latest_folders if f.get("id") == folder["id"]), None)

    report = {
        "folder": folder,
        "created_test_ids": ids,
        "move_result": move,
        "batch_id": batch_id,
        "batch_status": batch_status,
        "folder_snapshot": snap,
        "expecteds": {
            "missing_src": expected_missing_src,
            "missing_winner": expected_missing_winner,
            "winner_count": expected_winner_count,
        },
    }
    report_file = out_dir / f"diag_append_report_{stamp}.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("FOLDER", folder)
    print("CREATED_IDS", ids)
    print("MOVE", move)
    print("BATCH", batch_id)
    print("STATUS", batch_status)
    print("SNAP", snap)
    print("REPORT", report_file)


if __name__ == "__main__":
    main()
