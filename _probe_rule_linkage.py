import requests

BASE = 'http://localhost:8550'
sql = """
SELECT COUNT(*) AS TOTAL,
       SUM(CASE WHEN s.WS_TRAILER_RULE_TEXT_MATCH IS NOT NULL THEN 1 ELSE 0 END) AS WS_RULE_POP
FROM CCAL_OWNER.TXN t
JOIN CDS_STG_OWNER.STCCCALQ_GG_VW s ON s.TXN_SRC_KEY=t.TXN_SRC_KEY
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29,30,71,72)
"""

r = requests.post(f"{BASE}/api/datasources/2/query", json={"sql": sql, "limit": 20}, timeout=60)
print(r.status_code)
print(r.text)
