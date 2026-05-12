"""Debug PD_ID and check failing tests."""
import httpx, json
c = httpx.Client(base_url="http://localhost:8550", timeout=30)

# Check if PD_ID exists on TXN
r = c.post("/api/datasources/2/query", json={"sql": "SELECT COUNT(*) AS C FROM ALL_TAB_COLUMNS WHERE TABLE_NAME='TXN' AND OWNER='CCAL_OWNER' AND COLUMN_NAME='PD_ID'"})
print("PD_ID on TXN:", r.json().get("rows", [{}])[0].get("C", "?"))

# Check if PD_ID exists somewhere else
r2 = c.post("/api/datasources/2/query", json={"sql": "SELECT TABLE_NAME, COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE COLUMN_NAME='PD_ID' AND OWNER='CCAL_OWNER'"})
print("PD_ID tables:", r2.json().get("rows", []))

# Now check test 359  
t = c.get("/api/tests/359").json()
print(f"\nTest 359: {t['name']}")
print(f"SQL: {t['source_query']}")

# And test 349 (first manual test)
t2 = c.get("/api/tests/349").json()
print(f"\nTest 349: {t2['name']}")
print(f"SQL: {t2['source_query']}")

# Run test 349 individually
r = c.post("/api/tests/run/349")
d = r.json()
print(f"\nRun 349: status={d.get('status')}, error={d.get('error_message','')[:200]}")
