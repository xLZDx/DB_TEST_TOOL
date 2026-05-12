"""Fix test 359 and re-run all manual tests."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=120)

# Fix test 359: PD_ID is on APA, not TXN. Check that APA.PD_ID is populated instead
c.put("/api/tests/359", json={
    "name": "APA.PD_ID not null for stock movement TXNs",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": """SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a
JOIN CCAL_OWNER.TXN t ON a.TXN_ID = t.TXN_ID
WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND a.PD_ID IS NULL""",
    "expected_result": "0",
    "severity": "high",
    "description": "Product ID on APA must be populated for all stock movement transactions"
})
print("Fixed test 359")

# Clear all runs
c.post("/api/tests/runs/clear-all-statuses")
print("Cleared all runs")

# Run all manual tests
ids = list(range(349, 369))
print(f"Running {len(ids)} manual tests...")
batch = c.post("/api/tests/run-batch", json={"test_ids": ids}).json()
print(f"Batch: passed={batch.get('passed',0)}, failed={batch.get('failed',0)}, error={batch.get('error',0)}")

# Show results
runs = c.get("/api/tests/runs", params={"limit": 30}).json()
batch_runs = sorted([r for r in runs if r.get("batch_id") == batch.get("batch_id")], key=lambda r: r["test_case_id"])
for run in batch_runs:
    detail = ""
    if run.get("actual_result"):
        try:
            d = json.loads(run["actual_result"])
            detail = d.get("detail", "")[:100]
        except:
            pass
    err = (run.get("error_message") or "")[:100]
    t_name = ""
    for t in c.get("/api/tests").json():
        if t["id"] == run["test_case_id"]:
            t_name = t["name"][:50]
            break
    print(f"  #{run['test_case_id']} {run['status']:7s} {run.get('execution_time_ms',0):5d}ms | {t_name} | {err or detail}")
