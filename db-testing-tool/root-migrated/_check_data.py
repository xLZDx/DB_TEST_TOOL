"""Check STCCCALQ_STG columns for WS_ prefix columns."""
import httpx, json
c = httpx.Client(base_url="http://localhost:8550", timeout=30)
sql = """SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS 
WHERE TABLE_NAME='STCCCALQ_STG' AND OWNER='CDS_STG_OWNER' 
AND (COLUMN_NAME LIKE '%SUB%' OR COLUMN_NAME LIKE '%EXEC%' 
     OR COLUMN_NAME LIKE '%CNX%' OR COLUMN_NAME LIKE '%TRLR%'
     OR COLUMN_NAME LIKE '%WS%' OR COLUMN_NAME LIKE '%IND%')
ORDER BY COLUMN_NAME"""
r = c.post("/api/datasources/2/query", json={"sql": sql, "max_rows": 50})
data = r.json()
print("STCCCALQ_STG columns:")
for row in data.get("rows", []):
    print(f"  {row['COLUMN_NAME']}")

# Also check the actual row counts
sql2 = """SELECT SRC_STM_ID, COUNT(*) AS CNT FROM CCAL_OWNER.TXN 
WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29,30,71,72) 
GROUP BY SRC_STM_ID ORDER BY SRC_STM_ID"""
r2 = c.post("/api/datasources/2/query", json={"sql": sql2, "max_rows": 10})
data2 = r2.json()
print("\nTXN row counts by SRC_STM_ID for 2026-03-30:")
for row in data2.get("rows", []):
    print(f"  SRC_STM_ID={row['SRC_STM_ID']}: {row['CNT']}")
total = sum(r['CNT'] for r in data2.get("rows", []))
print(f"  Total: {total}")

# Check if CDSM_RULE_MAP exists
sql3 = """SELECT COUNT(*) AS CNT FROM ALL_TABLES WHERE TABLE_NAME='CDSM_RULE_MAP'"""
r3 = c.post("/api/datasources/2/query", json={"sql": sql3, "max_rows": 1})
d3 = r3.json()
print(f"\nCDSM_RULE_MAP exists: {d3.get('rows', [{}])[0].get('CNT', 0)}")

# Check if TXN_SBTP_ID and SRC_PCS_TP_ID are populated
sql4 = """SELECT SRC_STM_ID, 
    COUNT(CASE WHEN TXN_SBTP_ID IS NULL THEN 1 END) AS NULL_SBTP,
    COUNT(CASE WHEN EXEC_SBTP_ID IS NULL THEN 1 END) AS NULL_EXEC_SBTP,
    COUNT(CASE WHEN SRC_PCS_TP_ID IS NULL THEN 1 END) AS NULL_SRC_PCS,
    COUNT(*) AS TOTAL
FROM CCAL_OWNER.TXN 
WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29,30,71,72) 
GROUP BY SRC_STM_ID ORDER BY SRC_STM_ID"""
r4 = c.post("/api/datasources/2/query", json={"sql": sql4, "max_rows": 10})
d4 = r4.json()
print("\nNull counts on TXN for 2026-03-30:")
for row in d4.get("rows", []):
    print(f"  SRC_STM_ID={row['SRC_STM_ID']}: null_sbtp={row['NULL_SBTP']}, null_exec={row['NULL_EXEC_SBTP']}, null_src_pcs={row['NULL_SRC_PCS']}, total={row['TOTAL']}")
