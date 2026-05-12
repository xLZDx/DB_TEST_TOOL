"""Fix manual tests that reference PD_ID on TXN (PD_ID is on APA, not TXN)."""
import httpx

c = httpx.Client(base_url="http://localhost:8550", timeout=30)

# Test 359: PD_ID not null => change to check AR_ID instead (AR_ID is on TXN)
# Actually let me first check which exact tests have PD_ID
for tid in range(349, 369):
    t = c.get(f"/api/tests/{tid}").json()
    sql = t.get("source_query", "")
    if "PD_ID" in sql:
        print(f"  #{tid} has PD_ID: {t['name']}")
        print(f"    SQL: {sql[:150]}")
        print()
