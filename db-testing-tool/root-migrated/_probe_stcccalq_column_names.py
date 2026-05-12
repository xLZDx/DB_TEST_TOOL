import requests

BASE='http://localhost:8550'
DS=2

sql = """
SELECT column_name
FROM all_tab_columns
WHERE owner='CDS_STG_OWNER'
  AND table_name='STCCCALQ_GG_VW'
  AND (
    column_name LIKE 'WS_%'
    OR column_name LIKE '%CATEGORY%'
    OR column_name IN ('TO_LOCATION','FROM_LOCATION','SHARES','TRAILER','OPTION_CLS','SECURITY_TYPE','TERM_NAME','RECORD_TYPE_MULTI')
  )
ORDER BY column_name
"""

r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":500},timeout=180)
print('status',r.status_code)
print(r.text[:8000])
