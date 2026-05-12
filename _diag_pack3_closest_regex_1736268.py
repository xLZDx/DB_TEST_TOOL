import json
from datetime import datetime
from pathlib import Path

import requests

BASE = "http://localhost:8550"
DS_ID = 2
BUSINESS_DATE = "2026-03-30"
STREAMS = "29,30,71,72"


def query(sql: str, limit: int = 5000):
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


def read_latest_diag2_prefixes(base_dir: Path):
    reports = sorted(base_dir.glob("diag2_report_*.json"))
    if not reports:
        return [
            "DIRECT ROLLOVER - STOCK",
            "SECURITY RECEIVED IN BRANCH",
            "ACAT TEST",
        ]
    data = json.loads(reports[-1].read_text(encoding="utf-8"))
    prefixes = []
    for row in data.get("top_trailer_prefixes", []):
        p = (row.get("TRAILER_PREFIX") or "").strip()
        if p:
            prefixes.append(p)
    return prefixes[:3] or [
        "DIRECT ROLLOVER - STOCK",
        "SECURITY RECEIVED IN BRANCH",
        "ACAT TEST",
    ]


def sql_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build_base_cte(prefixes):
    in_prefix = ", ".join(sql_quote(p) for p in prefixes)
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
        s.record_type_multi,
        UPPER(REGEXP_REPLACE(NVL(s.trailer, ' '), '^[[:space:]]+', '')) AS trlr,
        SUBSTR(s.trailer, 1, 80) AS trailer_prefix
    FROM CDS_STG_OWNER.STCCCALQ_GG_VW s
    JOIN CCAL_OWNER.TXN t ON t.txn_src_key = s.txn_src_key
    WHERE t.td = DATE '{BUSINESS_DATE}'
      AND t.src_stm_id IN ({STREAMS})
      AND s.ws_exception_text = 'MATCH NOT FOUND'
      AND SUBSTR(s.trailer, 1, 80) IN ({in_prefix})
),
candidates AS (
    SELECT
        s.txn_id,
        s.txn_src_key,
        s.trailer_prefix,
        s.trlr,
        m.cdsm_rule_map_id,
        m.trlr_rule_txt,
        m.regex_patt,
        m.rec_tp_seq,
        m.txn_sbtp_cd,
        m.exec_sbtp_cd,
        m.cnx_ind
    FROM src s
    JOIN CCAL_OWNER.CDSM_RULE_MAP m
      ON m.eff_dt <= TRUNC(s.td)
     AND m.end_dt > TRUNC(s.td)
     AND m.calling_prgm = 'STRCCDSB'
     AND m.rec_tp = 7
     AND m.actv_f = 'Y'
     AND (m.fm_loc IS NULL OR m.fm_loc = s.from_location)
     AND (m.to_loc IS NULL OR m.to_loc = s.to_location)
     AND (m.sec_tp IS NULL OR m.sec_tp IN (s.security_type_n, s.security_type_x))
     AND (m.pd_cgy IS NULL OR m.pd_cgy = s.ws_product_category)
     AND (
            m.trlr_shs_tp_cd IS NULL
         OR (m.trlr_shs_tp_cd = 'Y' AND s.shares <> 0)
         OR (m.trlr_shs_tp_cd = 'P' AND s.shares > 0)
         OR (m.trlr_shs_tp_cd = 'N' AND s.shares < 0)
         )
     AND (m.opt_cls IS NULL OR m.opt_cls = s.option_cls)
     AND (m.src_prgm IS NULL OR m.src_prgm = s.term_name)
     AND (m.mkt_mkr_5 IS NULL OR m.mkt_mkr_5 = s.ws_market_maker_5)
),
tokens AS (
    SELECT
        s.txn_src_key,
        REGEXP_SUBSTR(
            REGEXP_REPLACE(UPPER(s.trailer_prefix), '[^A-Z0-9 ]', ' '),
            '[^ ]+',
            1,
            LEVEL
        ) AS token
    FROM src s
    CONNECT BY REGEXP_SUBSTR(
                  REGEXP_REPLACE(UPPER(s.trailer_prefix), '[^A-Z0-9 ]', ' '),
                  '[^ ]+',
                  1,
                  LEVEL
               ) IS NOT NULL
       AND PRIOR s.txn_src_key = s.txn_src_key
       AND PRIOR SYS_GUID() IS NOT NULL
),
scored AS (
    SELECT
        c.trailer_prefix,
        c.txn_src_key,
        c.cdsm_rule_map_id,
        c.trlr_rule_txt,
        c.regex_patt,
        c.rec_tp_seq,
        c.txn_sbtp_cd,
        c.exec_sbtp_cd,
        c.cnx_ind,
        SUM(
            CASE
                WHEN LENGTH(NVL(t.token, '')) >= 3
                 AND INSTR(UPPER(NVL(c.trlr_rule_txt, ' ') || ' ' || NVL(c.regex_patt, ' ')), t.token) > 0
                THEN 1 ELSE 0
            END
        ) AS token_hits,
        SUM(CASE WHEN LENGTH(NVL(t.token, '')) >= 3 THEN 1 ELSE 0 END) AS token_cnt,
        MAX(CASE WHEN REGEXP_LIKE(c.trlr, c.regex_patt, 'c') THEN 1 ELSE 0 END) AS regex_match_flag
    FROM candidates c
    LEFT JOIN tokens t ON t.txn_src_key = c.txn_src_key
    GROUP BY
        c.trailer_prefix,
        c.txn_src_key,
        c.cdsm_rule_map_id,
        c.trlr_rule_txt,
        c.regex_patt,
        c.rec_tp_seq,
        c.txn_sbtp_cd,
        c.exec_sbtp_cd,
        c.cnx_ind
),
agg AS (
    SELECT
        trailer_prefix,
        cdsm_rule_map_id,
        MIN(trlr_rule_txt) AS trlr_rule_txt,
        MIN(regex_patt) AS regex_patt,
        MIN(rec_tp_seq) AS rec_tp_seq,
        MIN(txn_sbtp_cd) AS txn_sbtp_cd,
        MIN(exec_sbtp_cd) AS exec_sbtp_cd,
        MIN(cnx_ind) AS cnx_ind,
        COUNT(*) AS appearances,
        SUM(token_hits) AS token_hits_sum,
        SUM(token_cnt) AS token_cnt_sum,
        ROUND(AVG(token_hits), 2) AS avg_token_hits,
        ROUND(AVG(CASE WHEN token_cnt > 0 THEN token_hits / token_cnt ELSE 0 END), 4) AS avg_token_hit_ratio,
        MAX(regex_match_flag) AS any_regex_match
    FROM scored
    GROUP BY trailer_prefix, cdsm_rule_map_id
),
ranked AS (
    SELECT
        a.*,
        ROW_NUMBER() OVER (
            PARTITION BY a.trailer_prefix
            ORDER BY a.avg_token_hit_ratio DESC, a.avg_token_hits DESC, a.appearances DESC, a.rec_tp_seq
        ) AS rn
    FROM agg a
)
"""


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    prefixes = read_latest_diag2_prefixes(out_dir)
    base = build_base_cte(prefixes)

    sql_top = base + """
SELECT
    trailer_prefix,
    rn,
    cdsm_rule_map_id,
    rec_tp_seq,
    appearances,
    token_hits_sum,
    token_cnt_sum,
    avg_token_hits,
    avg_token_hit_ratio,
    any_regex_match,
    SUBSTR(trlr_rule_txt, 1, 180) AS trlr_rule_txt,
    SUBSTR(regex_patt, 1, 180) AS regex_patt,
    txn_sbtp_cd,
    exec_sbtp_cd,
    cnx_ind
FROM ranked
WHERE rn <= 15
ORDER BY trailer_prefix, rn
"""

    sql_coverage = base + """
SELECT
    trailer_prefix,
    COUNT(DISTINCT txn_src_key) AS txn_cnt,
    COUNT(DISTINCT cdsm_rule_map_id) AS candidate_rule_cnt,
    MAX(CASE WHEN regex_match_flag = 1 THEN 1 ELSE 0 END) AS any_regex_match_in_scored
FROM scored
GROUP BY trailer_prefix
ORDER BY trailer_prefix
"""

    sql_prefix_terms = base + """
SELECT trailer_prefix, term_name, COUNT(*) AS cnt
FROM src
GROUP BY trailer_prefix, term_name
ORDER BY trailer_prefix, cnt DESC, term_name
"""

    top_rows = query(sql_top, 10000)
    coverage = query(sql_coverage, 5000)
    prefix_terms = query(sql_prefix_terms, 5000)

    f_top = out_dir / f"diag3_closest_candidates_{stamp}.json"
    f_cov = out_dir / f"diag3_prefix_coverage_{stamp}.json"
    f_terms = out_dir / f"diag3_prefix_term_split_{stamp}.json"

    save_json(f_top, top_rows)
    save_json(f_cov, coverage)
    save_json(f_terms, prefix_terms)

    report = {
        "generated_at": stamp,
        "business_date": BUSINESS_DATE,
        "streams": STREAMS,
        "prefixes": prefixes,
        "files": [str(f_top), str(f_cov), str(f_terms)],
        "top_preview": (top_rows.get("rows") or [])[:12],
        "coverage_preview": coverage.get("rows") or [],
    }

    report_file = out_dir / f"diag3_report_{stamp}.json"
    save_json(report_file, report)

    print("REPORT", report_file)
    print("PREFIXES", prefixes)
    print("COVERAGE", coverage.get("rows") or [])
    print("TOP_FIRST", (top_rows.get("rows") or [])[:5])


if __name__ == "__main__":
    main()
