import requests
BASE='http://localhost:8550'

def q(sql,limit=200):
    r=requests.post(f"{BASE}/api/datasources/2/query",json={"sql":sql,"limit":limit},timeout=120)
    data=r.json()
    if r.status_code>=400 or (isinstance(data,dict) and data.get('detail')):
        print('ERROR',r.status_code,data)
        return []
    return data.get('rows',[])

rows=q("""
SELECT CDSM_RULE_MAP_ID, TRLR_RULE_TXT, REGEX_PATT, REC_TP, FM_LOC, TO_LOC,
       TRLR_SHS_TP_CD, SRC_PRGM, OPT_CLS, SEC_TP, PD_CGY, MKT_MKR_5,
       TXN_SBTP_CD, CNX_IND, EXEC_SBTP_CD, ACTV_F, EFF_DT, END_DT
FROM CCAL_OWNER.CDSM_RULE_MAP
WHERE ACTV_F='Y'
ORDER BY CDSM_RULE_MAP_ID
""",300)
print('active rules',len(rows))
for r in rows[:25]:
    print(r)

# how many source rows have ws trailer fields not null for likely March 2026 data in target
rows2=q("""
SELECT COUNT(*) CNT,
       SUM(CASE WHEN WS_SUBTYPE IS NOT NULL THEN 1 ELSE 0 END) AS WS_SUBTYPE_POP,
       SUM(CASE WHEN WS_CNX_IND IS NOT NULL THEN 1 ELSE 0 END) AS WS_CNX_IND_POP,
       SUM(CASE WHEN WS_EXECUTION_SUBTYPE IS NOT NULL THEN 1 ELSE 0 END) AS WS_EXEC_POP
FROM CDS_STG_OWNER.STCCCALQ_GG_VW
""",10)
print('source pop stats',rows2)

# sample rows matching source streams from txn side
rows3=q("""
SELECT t.TD, t.SRC_STM_ID, t.TXN_SRC_KEY, t.TXN_SBTP_ID, t.SRC_PCS_TP_ID, t.EXEC_SBTP_ID,
       s.TRAILER, s.RECORD_TYPE_MULTI, s.FROM_LOCATION, s.TO_LOCATION,
       s.WS_SUBTYPE, s.WS_CNX_IND, s.WS_EXECUTION_SUBTYPE
FROM CCAL_OWNER.TXN t
JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY = t.TXN_SRC_KEY
WHERE t.SRC_STM_ID IN (29,30,71,72)
  AND t.TD = DATE '2026-03-30'
FETCH FIRST 50 ROWS ONLY
""",100)
print('joined txn-source rows',len(rows3))
for r in rows3[:10]:
    print(r)
