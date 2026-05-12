"""Find TXN to APA relationship."""
import httpx

c = httpx.Client(base_url="http://localhost:8550", timeout=30)

# Check TXN columns with ID
r = c.post("/api/datasources/2/query", json={"sql":
    "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='TXN' AND OWNER='CCAL_OWNER' AND COLUMN_NAME LIKE '%ID%' ORDER BY COLUMN_NAME"
})
print("TXN ID columns:")
for row in r.json().get("rows", []):
    print(f"  {row['COLUMN_NAME']}")

# Check if EXEC_ID is on TXN
r2 = c.post("/api/datasources/2/query", json={"sql":
    "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='TXN' AND OWNER='CCAL_OWNER' AND COLUMN_NAME IN ('TXN_ID','EXEC_ID','APA_ID') ORDER BY COLUMN_NAME"
})
print("\nTXN key columns:")
for row in r2.json().get("rows", []):
    print(f"  {row['COLUMN_NAME']}")

# Try a sample join to see how TXN relates to APA
r3 = c.post("/api/datasources/2/query", json={"sql":
    """SELECT t.TXN_ID, a.APA_ID, a.EXEC_ID FROM CCAL_OWNER.TXN t 
    JOIN CCAL_OWNER.APA a ON a.EXEC_ID = t.TXN_ID 
    WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29,30) AND ROWNUM <= 3"""
})
print("\nSample TXN-APA join (via EXEC_ID=TXN_ID):")
for row in r3.json().get("rows", []):
    print(f"  {row}")
