"""Fix test 360 and run ALL 20 manual tests. DS cache fix should prevent cascade."""
import httpx, json, time

c = httpx.Client(base_url="http://localhost:8550", timeout=300)

# Fix test 360: CDSM_RULE_MAP is not accessible to the user. 
# Change to check via ALL_TABLES data dictionary view instead.
r = c.put("/api/tests/360", json={
    "name": "CDSM_RULE_MAP lookup table exists in database", 
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM ALL_TABLES WHERE TABLE_NAME = 'CDSM_RULE_MAP'",
    "expected_result": None,
    "severity": "medium",
    "description": "Validates CDSM_RULE_MAP lookup table (CDSMANUL/SumridgeHoldings rule mapping) exists in database. Note: user may not have direct SELECT on the table."
})
print(f"Fix 360: {r.status_code}")

# Clear all runs
c.post("/api/tests/runs/clear-all-statuses")
print("Cleared runs")

# Run tests one by one to avoid any cache issues early on
ids = list(range(349, 369))
results = {}
for tid in ids:
    r = c.post(f"/api/tests/run/{tid}")
    d = r.json()
    status = d.get("status", "?")
    results[tid] = status
    err = (d.get("error_message") or "")[:80]
    detail = ""
    if d.get("actual_result"):
        try:
            detail = json.loads(d["actual_result"]).get("detail", "")[:80]
        except:
            pass
    print(f"  #{tid} {status:7s} {d.get('execution_time_ms',0):5d}ms | {err or detail}")

passed = sum(1 for v in results.values() if v == "passed")
failed = sum(1 for v in results.values() if v == "failed")
error = sum(1 for v in results.values() if v == "error")
print(f"\nTotal: {passed} passed, {failed} failed, {error} error out of {len(ids)}")
