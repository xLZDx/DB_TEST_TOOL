import requests, json
BASE = 'http://localhost:8550'

def q(sql, limit=500):
    r = requests.post(f"{BASE}/api/datasources/2/query", json={"sql": sql, "limit": limit}, timeout=120)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get('detail'):
        raise RuntimeError(str(data['detail']))
    return data.get('rows', [])

cols_vw = q("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='CDS_STG_OWNER' AND TABLE_NAME='STCCCALQ_GG_VW' ORDER BY COLUMN_ID", 500)
cols_map = q("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='CCAL_OWNER' AND TABLE_NAME='CDSM_RULE_MAP' ORDER BY COLUMN_ID", 500)
cols_txn = q("SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='CCAL_OWNER' AND TABLE_NAME='TXN' ORDER BY COLUMN_ID", 500)

print('GG_VW column count:', len(cols_vw))
print('GG_VW key-like columns:')
for r in cols_vw:
    c = r['COLUMN_NAME']
    if any(k in c for k in ['TRAIL', 'RECORD', 'TYPE', 'LOCATION', 'TERM', 'SECURITY', 'WS_', 'SRC_', 'TXN', 'TD']):
        print(' ', c, r['DATA_TYPE'])

print('\nCDSM_RULE_MAP column count:', len(cols_map))
for r in cols_map:
    print(' ', r['COLUMN_NAME'], r['DATA_TYPE'])

print('\nTXN selected columns:')
for r in cols_txn:
    c = r['COLUMN_NAME']
    if c in {'TXN_ID','TD','SRC_STM_ID','TXN_SBTP_ID','SRC_PCS_TP_ID','EXEC_SBTP_ID','TXN_SRC_KEY','AR_ID','SD','TXN_TP_ID','EXEC_TP_ID','EXEC_ID'}:
        print(' ', c, r['DATA_TYPE'])

# sample source rows for date
sample = q("SELECT * FROM CDS_STG_OWNER.STCCCALQ_GG_VW WHERE TD = DATE '2026-03-30' FETCH FIRST 10 ROWS ONLY", 50)
print('\nSample GG_VW rows:', len(sample))
if sample:
    print('Sample columns:', list(sample[0].keys()))
    for row in sample[:3]:
        mini = {k: row.get(k) for k in row.keys() if k in ['TD','SRC_STM_ID','TRAILER','RECORD_TYPE_MULTI','FROM_LOCATION','TO_LOCATION','SHARES','TERM_NAME','OPTION_CLS','SECURITY_TYPE_N','SECURITY_TYPE_X','WS_PRODUCT_CATEGORY','WS_MARKET_MAKER_5','TXN_SRC_KEY']}
        print(mini)
