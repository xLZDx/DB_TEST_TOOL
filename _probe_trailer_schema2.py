import requests
BASE='http://localhost:8550'

def q(sql,limit=50):
    r=requests.post(f"{BASE}/api/datasources/2/query",json={"sql":sql,"limit":limit},timeout=120)
    print('status',r.status_code)
    try:
        data=r.json()
    except Exception:
        print(r.text[:500]); raise
    if r.status_code>=400:
        print(data)
        return []
    if isinstance(data,dict) and data.get('detail'):
        print(data)
        return []
    return data.get('rows',[])

cols=q("SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER='CDS_STG_OWNER' AND TABLE_NAME='STCCCALQ_GG_VW' ORDER BY COLUMN_ID",500)
print('columns:', [c['COLUMN_NAME'] for c in cols])
rows=q("SELECT * FROM CDS_STG_OWNER.STCCCALQ_GG_VW FETCH FIRST 5 ROWS ONLY",5)
print('rows',len(rows))
if rows:
    print('row keys', list(rows[0].keys()))
    for r in rows:
        print({k:r.get(k) for k in ['TXN_SRC_KEY','SRC_STM_ID','RECORD_TYPE_MULTI','TRAILER','FM_LOC','TO_LOC','TRLR_SHS_TP_CD','TERM_NAME','OPT_CLS','SECURITY_TYPE_N','SECURITY_TYPE_X','WS_PRODUCT_CATEGORY','WS_MARKET_MAKER_5'] if k in r})
