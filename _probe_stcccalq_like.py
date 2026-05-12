import requests

BASE='http://localhost:8550'
DS=2

needed = ['TRAILER','WS_SUBTYPE','WS_EXECUTION_SUBTYPE','WS_CNX_IND','TO_LOCATION','FROM_LOCATION','SHARES','RECORD_TYPE_MULTI']
in_list = ','.join("'"+c+"'" for c in needed)

sql = f"""
SELECT owner, table_name, COUNT(DISTINCT column_name) matched_cols
FROM all_tab_columns
WHERE column_name IN ({in_list})
  AND table_name LIKE '%STCCCALQ%'
GROUP BY owner, table_name
ORDER BY matched_cols DESC, owner, table_name
"""

r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":500},timeout=180)
print('status',r.status_code)
print(r.text[:5000])

if r.status_code==200:
    rows=r.json().get('rows',[])
    for row in rows:
        owner=row['OWNER']; table=row['TABLE_NAME']
        q=f"SELECT COUNT(*) CNT FROM {owner}.{table}"
        r2=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":q,"limit":10},timeout=180)
        print(owner, table, 'count_status', r2.status_code, r2.text[:300])
