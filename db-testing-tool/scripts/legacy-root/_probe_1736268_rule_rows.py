import requests

BASE='http://localhost:8550'
DS=2

sqls = {
 'map_active': "SELECT COUNT(*) CNT FROM ccal_owner.cdsm_rule_map WHERE actv_f='Y' AND calling_prgm='STRCCDSB' AND rec_tp=7 AND eff_dt <= DATE '2026-03-30' AND end_dt > DATE '2026-03-30'",
 'map_active_any_prog': "SELECT calling_prgm, COUNT(*) CNT FROM ccal_owner.cdsm_rule_map WHERE actv_f='Y' AND rec_tp=7 AND eff_dt <= DATE '2026-03-30' AND end_dt > DATE '2026-03-30' GROUP BY calling_prgm ORDER BY CNT DESC",
 'map_regex_not_null': "SELECT COUNT(*) CNT FROM ccal_owner.cdsm_rule_map WHERE regex_patt IS NOT NULL AND actv_f='Y' AND rec_tp=7",
 'src_record_types': "SELECT record_type_multi, COUNT(*) CNT FROM cds_stg_owner.stcccalq_gg_vw s JOIN ccal_owner.txn t ON t.txn_src_key=s.txn_src_key WHERE t.td=DATE '2026-03-30' AND t.src_stm_id IN (29,30,71,72) GROUP BY record_type_multi ORDER BY CNT DESC",
 'src_term': "SELECT term_name, COUNT(*) CNT FROM cds_stg_owner.stcccalq_gg_vw s JOIN ccal_owner.txn t ON t.txn_src_key=s.txn_src_key WHERE t.td=DATE '2026-03-30' AND t.src_stm_id IN (29,30,71,72) GROUP BY term_name ORDER BY CNT DESC",
}

for name, sql in sqls.items():
    r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":200},timeout=180)
    print('\n===',name,'status',r.status_code,'===')
    print(r.text[:3000])
