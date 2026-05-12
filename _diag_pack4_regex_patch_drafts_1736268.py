import json
import re
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


def save_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def save_json(path: Path, data):
    save_text(path, json.dumps(data, indent=2))


def latest_file(base_dir: Path, pattern: str) -> Path:
    items = sorted(base_dir.glob(pattern))
    if not items:
        raise RuntimeError(f"No files for pattern {pattern}")
    return items[-1]


def regex_from_prefix(prefix: str) -> str:
    # Build strict word sequence with flexible spacing and optional trailing spaces.
    tokens = [t for t in prefix.upper().strip().split() if t]
    parts = [re.escape(t) for t in tokens]
    core = r"[[:space:]]+".join(parts)
    return f"^{core}([[:space:]]*)$"


def sql_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def count_matches(prefix: str, regex_patt: str):
    sql = f"""
WITH src AS (
    SELECT
        s.txn_src_key,
        UPPER(REGEXP_REPLACE(NVL(s.trailer, ' '), '^[[:space:]]+', '')) AS trlr,
        SUBSTR(s.trailer, 1, 80) AS trailer_prefix
    FROM CDS_STG_OWNER.STCCCALQ_GG_VW s
    JOIN CCAL_OWNER.TXN t ON t.txn_src_key = s.txn_src_key
    WHERE t.td = DATE '{BUSINESS_DATE}'
      AND t.src_stm_id IN ({STREAMS})
      AND s.ws_exception_text = 'MATCH NOT FOUND'
)
SELECT
    COUNT(DISTINCT CASE WHEN trailer_prefix = {sql_quote(prefix)} THEN txn_src_key END) AS prefix_txn_cnt,
    COUNT(DISTINCT CASE WHEN trailer_prefix = {sql_quote(prefix)} AND REGEXP_LIKE(trlr, {sql_quote(regex_patt)}, 'c') THEN txn_src_key END) AS regex_match_txn_cnt
FROM src
"""
    rows = query(sql, 50).get("rows", [])
    if not rows:
        return {"prefix_txn_cnt": 0, "regex_match_txn_cnt": 0}
    r = rows[0]
    return {
        "prefix_txn_cnt": int(r.get("PREFIX_TXN_CNT") or 0),
        "regex_match_txn_cnt": int(r.get("REGEX_MATCH_TXN_CNT") or 0),
    }


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"c:\GIT_Repo\test_reports\pbi1736268_artifacts_20260424")
    out_dir.mkdir(parents=True, exist_ok=True)

    diag3_report_file = latest_file(out_dir, "diag3_report_*.json")
    diag3_candidates_file = latest_file(out_dir, "diag3_closest_candidates_*.json")
    diag3_terms_file = latest_file(out_dir, "diag3_prefix_term_split_*.json")

    report = json.loads(diag3_report_file.read_text(encoding="utf-8"))
    candidates = json.loads(diag3_candidates_file.read_text(encoding="utf-8")).get("rows", [])
    terms = json.loads(diag3_terms_file.read_text(encoding="utf-8")).get("rows", [])

    prefixes = report.get("prefixes", [])[:3]

    by_prefix = {}
    for row in candidates:
        by_prefix.setdefault(row.get("TRAILER_PREFIX"), []).append(row)

    terms_by_prefix = {}
    for row in terms:
        terms_by_prefix.setdefault(row.get("TRAILER_PREFIX"), []).append(row)

    drafts = []
    sql_lines = [
        "-- Draft-only regex patch candidates for PBI 1736268",
        "-- DO NOT execute directly in production without business sign-off.",
        "",
    ]

    for p in prefixes:
        draft_regex = regex_from_prefix(p)
        counts = count_matches(p, draft_regex)

        top = sorted(by_prefix.get(p, []), key=lambda x: int(x.get("RN") or 999))[:3]
        top_terms = terms_by_prefix.get(p, [])[:3]

        options = []
        for cand in top:
            options.append(
                {
                    "based_on_cdsm_rule_map_id": cand.get("CDSM_RULE_MAP_ID"),
                    "rec_tp_seq": cand.get("REC_TP_SEQ"),
                    "txn_sbtp_cd": cand.get("TXN_SBTP_CD"),
                    "exec_sbtp_cd": cand.get("EXEC_SBTP_CD"),
                    "cnx_ind": cand.get("CNX_IND"),
                    "existing_trlr_rule_txt": cand.get("TRLR_RULE_TXT"),
                    "existing_regex_patt": cand.get("REGEX_PATT"),
                }
            )

        item = {
            "trailer_prefix": p,
            "proposed_trlr_rule_txt": p,
            "proposed_regex_patt": draft_regex,
            "validation": counts,
            "top_term_context": top_terms,
            "inheritance_options": options,
        }
        drafts.append(item)

        sql_lines.append(f"-- Prefix: {p}")
        sql_lines.append(f"-- Validation: prefix_txn_cnt={counts['prefix_txn_cnt']}, regex_match_txn_cnt={counts['regex_match_txn_cnt']}")
        sql_lines.append("-- Option A: update existing closest rule (replace <TARGET_RULE_ID>)")
        sql_lines.append("UPDATE CCAL_OWNER.CDSM_RULE_MAP")
        sql_lines.append(f"   SET TRLR_RULE_TXT = {sql_quote(p)},")
        sql_lines.append(f"       REGEX_PATT   = {sql_quote(draft_regex)},")
        sql_lines.append("       LAST_UDT_DTM = SYSTIMESTAMP,")
        sql_lines.append("       LAST_UDT_USR_NM = 'PBI1736268_DIAG_DRAFT'")
        sql_lines.append(" WHERE CDSM_RULE_MAP_ID = <TARGET_RULE_ID>;")
        sql_lines.append("")
        sql_lines.append("-- Option B: insert new active rule row based on approved business mapping")
        sql_lines.append("-- INSERT INTO CCAL_OWNER.CDSM_RULE_MAP (...columns...) VALUES (...);")
        sql_lines.append("")

    summary = {
        "generated_at": stamp,
        "business_date": BUSINESS_DATE,
        "streams": STREAMS,
        "source_diag3_report": str(diag3_report_file),
        "draft_count": len(drafts),
        "drafts": drafts,
    }

    json_file = out_dir / f"diag4_regex_patch_drafts_{stamp}.json"
    sql_file = out_dir / f"diag4_regex_patch_drafts_{stamp}.sql"
    md_file = out_dir / f"diag4_regex_patch_drafts_{stamp}.md"

    save_json(json_file, summary)
    save_text(sql_file, "\n".join(sql_lines) + "\n")

    md_lines = [
        "# Diagnostic Pack 4 - Regex Patch Drafts",
        "",
        f"Generated: {stamp}",
        f"Business date: {BUSINESS_DATE}",
        f"Streams: {STREAMS}",
        "",
        "These are draft candidates only. No DB update was performed.",
        "",
    ]
    for d in drafts:
        md_lines.append(f"## {d['trailer_prefix']}")
        md_lines.append(f"- Proposed rule text: `{d['proposed_trlr_rule_txt']}`")
        md_lines.append(f"- Proposed regex: `{d['proposed_regex_patt']}`")
        md_lines.append(f"- Prefix TXN count: `{d['validation']['prefix_txn_cnt']}`")
        md_lines.append(f"- Regex matched TXN count (draft regex): `{d['validation']['regex_match_txn_cnt']}`")
        md_lines.append("- Top inheritance options:")
        for opt in d["inheritance_options"]:
            md_lines.append(
                f"  - map_id={opt['based_on_cdsm_rule_map_id']}, txn_sbtp_cd={opt['txn_sbtp_cd']}, exec_sbtp_cd={opt['exec_sbtp_cd']}, cnx_ind={opt['cnx_ind']}"
            )
        md_lines.append("")

    save_text(md_file, "\n".join(md_lines))

    print("JSON", json_file)
    print("SQL", sql_file)
    print("MD", md_file)
    print("SUMMARY", [{"prefix": d["trailer_prefix"], **d["validation"]} for d in drafts])


if __name__ == "__main__":
    main()
