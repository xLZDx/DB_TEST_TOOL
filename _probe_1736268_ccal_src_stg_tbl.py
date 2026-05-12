import requests

BASE='http://localhost:8550'
DS=2

queries = {
  'cols': "SELECT column_name FROM all_tab_columns WHERE owner='CCAL_OWNER' AND table_name='CCAL_SRC_STG_TBL' ORDER BY column_id",
  'join_cnt': "SELECT COUNT(*) CNT FROM ccal_owner.ccal_src_stg_tbl s JOIN ccal_owner.txn t ON t.txn_src_key=s.txn_src_key WHERE t.td=DATE '2026-03-30' AND t.src_stm_id IN (29,30,71,72)",
  'sample': "SELECT s.txn_src_key, s.td, s.to_location, s.from_location, s.shares, s.trailer, s.option_cls, s.security_type, s.product_category, s.term_name, s.ws_mkt_mkr_5, s.ws_subtype, s.ws_cnx_ind, s.ws_execution_subtype, s.ws_exception_text FROM ccal_owner.ccal_src_stg_tbl s WHERE ROWNUM <= 3",
}

for name, sql in queries.items():
    r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":200},timeout=180)
    print('\n===',name,'status',r.status_code,'===')
    print(r.text[:5000])
