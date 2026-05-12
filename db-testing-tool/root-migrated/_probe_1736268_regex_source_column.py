import requests

BASE = 'http://localhost:8550'
DS = 2

candidate_cols = [
    'FTR_INST',
    'CHARGE_CODE',
    'INTRM_ACTG_CODE',
    'LOCATION_STK',
    'ACCOUNT_TYPE_STK',
    'ACCOUNT_TYPE_ALPHA',
    'SECURITY_TYPE_N',
    'SECURITY_TYPE_X',
    'CUSIP_NUMBER_MULTI',
    'EXTRA_CUSIP_MULTI',
    'CUSIP_STK',
    'EXTRA_CUSIP_STK',
    'TERM_NAME',
    'BUY_SELL_CODE_MULTI',
    'RECORD_TYPE_MULTI',
]

for col in candidate_cols:
    sql = f"""
    WITH src AS (
      SELECT s.txn_src_key, t.td, s.term_name, s.record_type_multi, s.security_type_n, s.security_type_x,
             UPPER(REGEXP_REPLACE(NVL(TO_CHAR(s.{col}),' '),'^[[:space:]]+','')) trlr
      FROM cds_stg_owner.stcccalq_gg_vw s
      JOIN ccal_owner.txn t ON t.txn_src_key=s.txn_src_key
      WHERE t.td=DATE '2026-03-30' AND t.src_stm_id IN (29,30,71,72)
    )
    SELECT COUNT(*) CNT
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
    """
    r = requests.post(f"{BASE}/api/datasources/{DS}/query", json={"sql": sql, "limit": 20}, timeout=180)
    if r.status_code != 200:
        print(col, 'HTTP', r.status_code, r.text[:200])
        continue
    data = r.json()
    if isinstance(data, dict) and data.get('detail'):
        print(col, 'ERR', data['detail'])
        continue
    rows = data.get('rows', [])
    cnt = rows[0].get('CNT') if rows else None
    print(col, cnt)
