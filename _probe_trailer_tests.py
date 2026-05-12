import requests
BASE='http://localhost:8550'

def run(name, sql):
    r=requests.post(f"{BASE}/api/datasources/2/query",json={"sql":sql,"limit":200},timeout=120)
    data=r.json()
    if r.status_code>=400:
        print(name, 'HTTP', r.status_code, data)
        return
    if isinstance(data,dict) and data.get('detail'):
        print(name, 'ERR', data['detail'])
        return
    rows=data.get('rows',[])
    print('\n',name)
    print(rows[:5])

base_cte = """
WITH base AS (
 SELECT t.txn_id,t.txn_src_key,t.td,t.src_stm_id,
        s.trailer,s.record_type_multi,s.from_location,s.to_location,s.term_name,s.option_cls,
        s.security_type_n,s.security_type_x,s.ws_product_category,s.ws_market_maker_5,
        s.ws_subtype,s.ws_cnx_ind,s.ws_execution_subtype,
        t.txn_sbtp_id,t.src_pcs_tp_id,t.exec_sbtp_id
 FROM ccal_owner.txn t
 JOIN cds_stg_owner.stcccalq_gg_vw s ON s.txn_src_key=t.txn_src_key
 WHERE t.td=DATE '2026-03-30' and t.src_stm_id in (29,30,71,72)
)
"""
cond = """
  m.actv_f='Y'
  AND b.td BETWEEN m.eff_dt AND m.end_dt
  AND (m.rec_tp IS NULL OR TO_CHAR(m.rec_tp)=b.record_type_multi)
  AND (m.fm_loc IS NULL OR m.fm_loc=b.from_location)
  AND (m.to_loc IS NULL OR m.to_loc=b.to_location)
  AND (m.src_prgm IS NULL OR m.src_prgm=b.term_name OR m.calling_prgm=b.term_name)
  AND (m.opt_cls IS NULL OR m.opt_cls=b.option_cls)
  AND (m.sec_tp IS NULL OR m.sec_tp IN (b.security_type_n,b.security_type_x))
  AND (m.pd_cgy IS NULL OR m.pd_cgy=b.ws_product_category)
  AND (m.mkt_mkr_5 IS NULL OR m.mkt_mkr_5=b.ws_market_maker_5)
  AND REGEXP_LIKE(b.trailer, m.regex_patt)
"""

run('base count', base_cte + "SELECT COUNT(*) CNT FROM base")
run('unmatched rules', base_cte + f"SELECT COUNT(*) CNT FROM base b WHERE NOT EXISTS (SELECT 1 FROM ccal_owner.cdsm_rule_map m WHERE {cond})")
run('duplicate matches', base_cte + f"SELECT COUNT(*) CNT FROM (SELECT b.txn_id, COUNT(*) c FROM base b JOIN ccal_owner.cdsm_rule_map m ON {cond} GROUP BY b.txn_id HAVING COUNT(*)>1)")
run('ws_exec vs rule exec_sbtp_cd mismatches', base_cte + f"SELECT COUNT(*) CNT FROM base b JOIN ccal_owner.cdsm_rule_map m ON {cond} WHERE m.exec_sbtp_cd IS NOT NULL AND NVL(b.ws_execution_subtype,'~') <> NVL(m.exec_sbtp_cd,'~')")
run('ws_cnx vs rule cnx mismatches', base_cte + f"SELECT COUNT(*) CNT FROM base b JOIN ccal_owner.cdsm_rule_map m ON {cond} WHERE m.cnx_ind IS NOT NULL AND NVL(b.ws_cnx_ind,'~') <> NVL(m.cnx_ind,'~')")
run('ws_subtype vs rule txn_sbtp_cd mismatches', base_cte + f"SELECT COUNT(*) CNT FROM base b JOIN ccal_owner.cdsm_rule_map m ON {cond} WHERE m.txn_sbtp_cd IS NOT NULL AND NVL(b.ws_subtype,'~') <> NVL(m.txn_sbtp_cd,'~')")
run('target exec_sbtp_id mismatches', base_cte + """
SELECT COUNT(*) CNT
FROM base b
LEFT JOIN ccal_owner.cl_val c ON c.cl_val_code = b.ws_execution_subtype
WHERE b.ws_execution_subtype IS NOT NULL
  AND NVL(b.exec_sbtp_id,-1) <> NVL(c.cl_val_id,-1)
""")
run('target src_pcs_tp_id mismatches', base_cte + """
SELECT COUNT(*) CNT
FROM base b
LEFT JOIN ccal_owner.src_pcs_tp p ON p.src_pcs_tp_code = b.ws_cnx_ind
WHERE b.ws_cnx_ind IS NOT NULL
  AND NVL(b.src_pcs_tp_id,-1) <> NVL(p.src_pcs_tp_id,-1)
""")
run('target txn_sbtp_id mismatches when ws_subtype present', base_cte + """
SELECT COUNT(*) CNT
FROM base b
LEFT JOIN ccal_owner.cl_val c ON c.cl_val_code = b.ws_subtype
WHERE b.ws_subtype IS NOT NULL
  AND NVL(b.txn_sbtp_id,-1) <> NVL(c.cl_val_id,-1)
""")
run('target txn_sbtp_id should be null when ws_subtype null', base_cte + "SELECT COUNT(*) CNT FROM base WHERE ws_subtype IS NULL AND txn_sbtp_id IS NOT NULL")
run('APA exists for each txn', base_cte + "SELECT COUNT(*) CNT FROM base b LEFT JOIN ccal_owner.apa a ON a.exec_id=b.txn_id WHERE a.apa_id IS NULL")
run('TXN_RLTNP referential integrity', """
SELECT COUNT(*) CNT
FROM ccal_owner.txn_rltnp r
LEFT JOIN ccal_owner.txn s ON s.txn_id = r.src_txn_id
LEFT JOIN ccal_owner.txn t ON t.txn_id = r.trgt_txn_id
WHERE s.txn_id IS NULL OR t.txn_id IS NULL
""")
