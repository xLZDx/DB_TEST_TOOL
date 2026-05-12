import requests

BASE='http://localhost:8550'
DS=2

sql = """
SELECT owner, table_name
FROM all_tab_columns
WHERE column_name='TRAILER'
  AND owner IN ('CCAL_OWNER','CDS_STG_OWNER','CCAL_REPL_OWNER')
ORDER BY owner, table_name
"""

r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":500},timeout=180)
print('status',r.status_code)
print(r.text[:4000])

if r.status_code==200:
    rows=r.json().get('rows',[])
    for row in rows:
        owner=row['OWNER']; table=row['TABLE_NAME']
        q=f"SELECT column_name FROM all_tab_columns WHERE owner='{owner}' AND table_name='{table}' ORDER BY column_id"
        r2=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":q,"limit":500},timeout=180)
        print('\n===',owner+'.'+table,'cols status',r2.status_code,'===')
        print(r2.text[:3000])
        c=f"SELECT COUNT(*) CNT FROM {owner}.{table}"
        r3=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":c,"limit":10},timeout=180)
        print('count status',r3.status_code, r3.text[:500])
