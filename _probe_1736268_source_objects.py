import requests

BASE='http://localhost:8550'
DS=2

cols = [
    'TRAILER','WS_EXECUTION_SUBTYPE','WS_CNX_IND','WS_SUBTYPE','WS_TRAILER_RULE_TEXT_MATCH',
    'TO_LOCATION','FROM_LOCATION','SHARES','PRODUCT_CATEGORY','OPTION_CLS','WS_MKT_MKR_5',
    'TXN_SRC_KEY','WS_EXCEPTION_TEXT','RECORD_TYPE_MULTI','SECURITY_TYPE','SECURITY_TYPE_N','SECURITY_TYPE_X'
]

in_list = ','.join("'" + c + "'" for c in cols)
sql = f"""
SELECT owner, table_name, column_name
FROM all_tab_columns
WHERE column_name IN ({in_list})
  AND owner IN ('CDS_STG_OWNER','CCAL_REPL_OWNER','CCAL_OWNER')
ORDER BY owner, table_name, column_id
"""

r=requests.post(f"{BASE}/api/datasources/{DS}/query",json={"sql":sql,"limit":5000},timeout=240)
print('status',r.status_code)
if r.status_code != 200:
    print(r.text[:4000])
else:
    d=r.json()
    rows=d.get('rows',[])
    print('rows',len(rows))
    for row in rows[:400]:
        print(row)
