import requests
BASE='http://localhost:8550'

def q(sql,limit=200):
    r=requests.post(f"{BASE}/api/datasources/2/query",json={"sql":sql,"limit":limit},timeout=120)
    data=r.json()
    if r.status_code>=400 or (isinstance(data,dict) and data.get('detail')):
        print('ERROR',r.status_code,data)
        return []
    return data.get('rows',[])

print('SRC_PCS_TP columns:')
for r in q("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='CCAL_OWNER' AND TABLE_NAME='SRC_PCS_TP' ORDER BY COLUMN_ID",100):
    print(r)

print('\nSample SRC_PCS_TP rows:')
for r in q("SELECT * FROM CCAL_OWNER.SRC_PCS_TP FETCH FIRST 20 ROWS ONLY",50):
    print(r)

print('\nCodes from source for date:')
for r in q("""
SELECT WS_CNX_IND, WS_EXECUTION_SUBTYPE, WS_SUBTYPE, COUNT(*) CNT
FROM CDS_STG_OWNER.STCCCALQ_GG_VW s
JOIN CCAL_OWNER.TXN t ON t.TXN_SRC_KEY = s.TXN_SRC_KEY
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29,30,71,72)
GROUP BY WS_CNX_IND, WS_EXECUTION_SUBTYPE, WS_SUBTYPE
ORDER BY CNT DESC
""",100):
    print(r)

print('\nCL_VAL lookup for ESTP0014 and subtype null handling:')
for r in q("SELECT CL_VAL_ID, CL_VAL_CODE, CL_SCM_ID FROM CCAL_OWNER.CL_VAL WHERE CL_VAL_CODE IN ('ESTP0014','INITIAL','REVERSAL') ORDER BY CL_VAL_CODE, CL_VAL_ID",200):
    print(r)

print('\nDistinct CL_VAL matches for execution subtype codes in sample:')
for r in q("""
SELECT s.WS_EXECUTION_SUBTYPE, COUNT(DISTINCT c.CL_VAL_ID) AS CL_CNT, MIN(c.CL_VAL_ID) AS MIN_ID, MAX(c.CL_VAL_ID) AS MAX_ID
FROM CDS_STG_OWNER.STCCCALQ_GG_VW s
LEFT JOIN CCAL_OWNER.CL_VAL c ON c.CL_VAL_CODE = s.WS_EXECUTION_SUBTYPE
JOIN CCAL_OWNER.TXN t ON t.TXN_SRC_KEY = s.TXN_SRC_KEY
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29,30,71,72)
GROUP BY s.WS_EXECUTION_SUBTYPE
""",100):
    print(r)
