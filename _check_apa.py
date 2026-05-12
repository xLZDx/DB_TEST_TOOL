"""Find the correct APA join key and fix test 359."""
import httpx

c = httpx.Client(base_url="http://localhost:8550", timeout=30)

# Check APA columns - look for TXN-related columns
r = c.post("/api/datasources/2/query", json={"sql": 
    "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='APA' AND OWNER='CCAL_OWNER' AND (COLUMN_NAME LIKE '%TXN%' OR COLUMN_NAME LIKE '%ID%') ORDER BY COLUMN_NAME"
})
print("APA columns with TXN or ID:")
for row in r.json().get("rows", []):
    print(f"  {row['COLUMN_NAME']}")

# Also check FIP
r2 = c.post("/api/datasources/2/query", json={"sql": 
    "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='FIP' AND OWNER='CCAL_OWNER' AND (COLUMN_NAME LIKE '%TXN%' OR COLUMN_NAME LIKE '%ID%') ORDER BY COLUMN_NAME"
})
print("\nFIP columns with TXN or ID:")
for row in r2.json().get("rows", []):
    print(f"  {row['COLUMN_NAME']}")

# Check TXN_RLTNP
r3 = c.post("/api/datasources/2/query", json={"sql": 
    "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='TXN_RLTNP' AND OWNER='CCAL_OWNER' ORDER BY COLUMN_NAME"
})
print("\nTXN_RLTNP columns:")
for row in r3.json().get("rows", []):
    print(f"  {row['COLUMN_NAME']}")
