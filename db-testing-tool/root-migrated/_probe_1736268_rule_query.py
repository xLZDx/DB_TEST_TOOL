import requests

BASE = "http://localhost:8550"
DS = 2

sql = """
WITH src AS (
	SELECT s.txn_src_key, t.td, s.term_name, s.record_type_multi, s.security_type_n, s.security_type_x,
				 UPPER(REGEXP_REPLACE(NVL(s.ftr_inst,' '),'^[[:space:]]+','')) trlr
	FROM cds_stg_owner.stcccalq_gg_vw s
	JOIN ccal_owner.txn t ON t.txn_src_key=s.txn_src_key
	WHERE t.td=DATE '2026-03-30'
		AND t.src_stm_id IN (29,30,71,72)
),
parsed AS (
	SELECT src.txn_src_key, map.cdsm_rule_map_id, map.regex_patt, map.trlr_rule_txt, map.txn_sbtp_cd, map.exec_sbtp_cd, map.cnx_ind, map.rec_tp_seq,
				 CASE WHEN map.has_tokens=0 THEN 1 WHEN map.has_varplus=1 THEN 3 ELSE 2 END prty
	FROM src
	JOIN ccal_owner.cdsm_rule_map map
		ON map.eff_dt <= TRUNC(src.td)
	 AND map.end_dt > TRUNC(src.td)
	 AND map.actv_f='Y'
	 AND map.calling_prgm='STRCCDSB'
	 AND (map.rec_tp IS NULL OR TO_CHAR(map.rec_tp)=src.record_type_multi)
	 AND (map.sec_tp IS NULL OR map.sec_tp IN (src.security_type_n, src.security_type_x))
	 AND (map.src_prgm IS NULL OR map.src_prgm = src.term_name)
	WHERE REGEXP_LIKE(src.trlr, map.regex_patt, 'c')
),
ranked AS (
	SELECT txn_src_key, cdsm_rule_map_id, txn_sbtp_cd, exec_sbtp_cd, cnx_ind,
				 ROW_NUMBER() OVER (PARTITION BY txn_src_key ORDER BY prty, trlr_rule_txt, rec_tp_seq) rn
	FROM parsed
)
SELECT
	(SELECT COUNT(*) FROM src) src_cnt,
	(SELECT COUNT(*) FROM parsed) parsed_cnt,
	(SELECT COUNT(*) FROM ranked WHERE rn=1) winner_cnt
FROM dual
"""

r = requests.post(f"{BASE}/api/datasources/{DS}/query", json={"sql": sql, "limit": 50}, timeout=180)
print("status", r.status_code)
print(r.text[:4000])