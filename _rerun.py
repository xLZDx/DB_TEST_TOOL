"""Clear old runs and re-execute all manual tests."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=120)

# Clear all old runs
r = c.post("/api/tests/runs/clear-all-statuses")
print("Cleared:", r.json())

# Run test 349 (simple count) individually first
r = c.post("/api/tests/run/349")
d = r.json()
print(f"Test 349: status={d['status']}, error={(d.get('error_message') or 'none')[:200]}")
print(f"Source result: {d.get('source_result','')}")

# If 349 passed, run all manual tests (349-368)
if d["status"] == "passed":
    print("\nRunning all manual tests (349-368)...")
    ids = list(range(349, 369))
    r = c.post("/api/tests/run-batch", json={"test_ids": ids})
    batch = r.json()
    print(f"Batch: passed={batch.get('passed',0)}, failed={batch.get('failed',0)}, error={batch.get('error',0)}")
    
    # Show results
    runs = c.get("/api/tests/runs", params={"limit": 30}).json()
    batch_runs = [r for r in runs if r.get("batch_id") == batch.get("batch_id")]
    for run in batch_runs:
        detail = ""
        if run.get("actual_result"):
            try:
                d = json.loads(run["actual_result"])
                detail = d.get("detail", "")[:100]
            except:
                pass
        err = (run.get("error_message") or "")[:100]
        print(f"  #{run['test_case_id']} {run['status']:7s} {run.get('execution_time_ms',0):5d}ms | {err or detail}")
