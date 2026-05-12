import json
import requests

BASE = 'http://localhost:8550'
DS = 2

queries = {
    'stg_cols': "SELECT column_name FROM all_tab_columns WHERE owner='CDS_STG_OWNER' AND table_name='STCCCALQ_GG_VW' ORDER BY column_id",
    'map_cols': "SELECT column_name FROM all_tab_columns WHERE owner='CCAL_OWNER' AND table_name='CDSM_RULE_MAP' ORDER BY column_id",
    'txn_cols': "SELECT column_name FROM all_tab_columns WHERE owner='CCAL_OWNER' AND table_name='TXN' ORDER BY column_id",
    'candidate_tables': "SELECT owner, table_name FROM all_tables WHERE table_name IN ('STCCCALQ_GG','CCAL_SRC_STG_TBL') ORDER BY owner, table_name",
    'candidate_views': "SELECT owner, view_name FROM all_views WHERE view_name IN ('STCCCALQ_GG_VW','CCAL_SRC_STG_TBL_VW') ORDER BY owner, view_name",
    'stcccalq_gg_cols': "SELECT column_name FROM all_tab_columns WHERE owner='CCAL_REPL_OWNER' AND table_name='STCCCALQ_GG' ORDER BY column_id",
}

for name, sql in queries.items():
    r = requests.post(f"{BASE}/api/datasources/{DS}/query", json={"sql": sql, "limit": 1000}, timeout=180)
    print('\n===', name, 'status', r.status_code, '===')
    if r.status_code != 200:
        print(r.text[:2000])
        continue
    data = r.json()
    if isinstance(data, dict) and data.get('detail'):
        print('detail', data['detail'])
        continue
    rows = data.get('rows', [])
    print('row_count', len(rows))
    print([row.get('COLUMN_NAME') for row in rows[:220]])

# Probe a minimal version of user's CTE fields.
probe_sql = """
SELECT txn_src_key, td, to_location, from_location, shares, trailer, option_cls
FROM CDS_STG_OWNER.STCCCALQ_GG_VW
WHERE ROWNUM <= 1
"""
r = requests.post(f"{BASE}/api/datasources/{DS}/query", json={"sql": probe_sql, "limit": 5}, timeout=180)
print('\n=== probe_select status', r.status_code, '===')
print(r.text[:2000])
