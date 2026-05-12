"""Check TXN column names."""
import httpx
c = httpx.Client(base_url="http://localhost:8550", timeout=30)
sql = """SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS 
WHERE TABLE_NAME='TXN' AND OWNER='CCAL_OWNER' 
AND (COLUMN_NAME LIKE '%SUB%' OR COLUMN_NAME LIKE '%EXEC%' 
     OR COLUMN_NAME LIKE '%CNX%' OR COLUMN_NAME LIKE '%TRAILER%'
     OR COLUMN_NAME LIKE '%IND%' OR COLUMN_NAME LIKE '%SRC_STM%'
     OR COLUMN_NAME LIKE '%TP_CODE%' OR COLUMN_NAME LIKE '%TP_ID%')
ORDER BY COLUMN_NAME"""
r = c.post("/api/datasources/2/query", json={"sql": sql, "max_rows": 50})
print(r.text[:2000])
