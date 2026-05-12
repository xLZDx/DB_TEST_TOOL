"""Show test run results for db-testing-tool PBI tests."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=30)

# Get runs from latest batch
runs = c.get("/api/tests/runs", params={"limit": 20}).json()
for r in runs[:13]:
    status = r["status"]
    test_id = r["test_case_id"]
    err = (r.get("error_message") or "")[:120]
    detail = ""
    if r.get("actual_result"):
        try:
            d = json.loads(r["actual_result"])
            detail = d.get("detail", "")[:100]
        except:
            detail = r["actual_result"][:100]
    print(f"  Test {test_id}: {status} | {err or detail}")
