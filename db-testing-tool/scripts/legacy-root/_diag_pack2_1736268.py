import json
from datetime import datetime
from pathlib import Path

import requests

BASE = "http://localhost:8550"
DS_ID = 2
BUSINESS_DATE = "2026-03-30"
STREAMS = "29,30,71,72"


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


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cte() -> str:
    return f"""
WITH src AS (
    SELECT
        s.txn_src_key,
        t.txn_id,
        t.td,
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
rule_fit AS (
    SELECT
        s.txn_id,
        s.txn_src_key,
        s.src_stm_id,
        s.record_type_multi,
        s.term_name,
        SUBSTR(s.trailer,1,80) AS trailer_prefix,
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
    GROUP BY
        s.txn_id,
        s.txn_src_key,
        s.src_stm_id,
        s.record_type_multi,
        s.term_name,
        SUBSTR(s.trailer,1,80)
)
"""


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    sql_no_winner_detail = cte() + """
SELECT *
FROM rule_fit
WHERE candidate_rules_after_regex = 0
ORDER BY txn_id
"""

    sql_group_term = cte() + """
SELECT
    NVL(term_name,'<NULL>') AS term_name,
    COUNT(*) AS no_winner_cnt,
    MIN(candidate_rules_before_regex) AS min_prefilter_candidates,
    MAX(candidate_rules_before_regex) AS max_prefilter_candidates,
    ROUND(AVG(candidate_rules_before_regex),2) AS avg_prefilter_candidates
FROM rule_fit
WHERE candidate_rules_after_regex = 0
GROUP BY NVL(term_name,'<NULL>')
ORDER BY no_winner_cnt DESC, term_name
"""

    sql_group_rec = cte() + """
SELECT
    NVL(record_type_multi,'<NULL>') AS record_type_multi,
    COUNT(*) AS no_winner_cnt,
    MIN(candidate_rules_before_regex) AS min_prefilter_candidates,
    MAX(candidate_rules_before_regex) AS max_prefilter_candidates,
    ROUND(AVG(candidate_rules_before_regex),2) AS avg_prefilter_candidates
FROM rule_fit
WHERE candidate_rules_after_regex = 0
GROUP BY NVL(record_type_multi,'<NULL>')
ORDER BY no_winner_cnt DESC, record_type_multi
"""

    sql_group_prefix = cte() + """
SELECT
    NVL(trailer_prefix,'<NULL>') AS trailer_prefix,
    COUNT(*) AS no_winner_cnt,
    MIN(candidate_rules_before_regex) AS min_prefilter_candidates,
    MAX(candidate_rules_before_regex) AS max_prefilter_candidates,
    ROUND(AVG(candidate_rules_before_regex),2) AS avg_prefilter_candidates
FROM rule_fit
WHERE candidate_rules_after_regex = 0
GROUP BY NVL(trailer_prefix,'<NULL>')
ORDER BY no_winner_cnt DESC, trailer_prefix
"""

    sql_blocking_summary = cte() + """
SELECT
    COUNT(*) AS total_src_rows,
    SUM(CASE WHEN candidate_rules_before_regex = 0 THEN 1 ELSE 0 END) AS no_rule_prefilter,
    SUM(CASE WHEN candidate_rules_before_regex > 0 AND candidate_rules_after_regex = 0 THEN 1 ELSE 0 END) AS regex_blocked,
    SUM(CASE WHEN candidate_rules_after_regex > 0 THEN 1 ELSE 0 END) AS regex_matched
FROM rule_fit
"""

    no_winner_detail = query(sql_no_winner_detail, 5000)
    grouped_term = query(sql_group_term, 2000)
    grouped_rec = query(sql_group_rec, 2000)
    grouped_prefix = query(sql_group_prefix, 5000)
    blocking_summary = query(sql_blocking_summary, 50)

    f1 = out_dir / f"diag2_no_winner_detail_{stamp}.json"
    f2 = out_dir / f"diag2_group_term_{stamp}.json"
    f3 = out_dir / f"diag2_group_record_type_{stamp}.json"
    f4 = out_dir / f"diag2_group_trailer_prefix_{stamp}.json"
    f5 = out_dir / f"diag2_blocking_summary_{stamp}.json"

    save_json(f1, no_winner_detail)
    save_json(f2, grouped_term)
    save_json(f3, grouped_rec)
    save_json(f4, grouped_prefix)
    save_json(f5, blocking_summary)

    top_term = (grouped_term.get("rows") or [])[:5]
    top_prefix = (grouped_prefix.get("rows") or [])[:5]
    summary_row = (blocking_summary.get("rows") or [{}])[0]

    report = {
        "generated_at": stamp,
        "business_date": BUSINESS_DATE,
        "streams": STREAMS,
        "summary": summary_row,
        "top_terms": top_term,
        "top_trailer_prefixes": top_prefix,
        "files": [str(f1), str(f2), str(f3), str(f4), str(f5)],
    }

    report_file = out_dir / f"diag2_report_{stamp}.json"
    save_json(report_file, report)

    print("REPORT", report_file)
    print("SUMMARY", summary_row)
    print("TOP_TERMS", top_term)
    print("TOP_PREFIX", top_prefix)


if __name__ == "__main__":
    main()
