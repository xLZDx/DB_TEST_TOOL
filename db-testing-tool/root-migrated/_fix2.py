"""Fix all failing manual tests and re-execute."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=120)

# Fix test 359: APA.PD_ID check (use correct join: APA.EXEC_ID = TXN.TXN_ID)
c.put("/api/tests/359", json={
    "name": "APA.PD_ID populated for stock movement TXNs",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND a.PD_ID IS NULL",
    "expected_result": "0",
    "severity": "high",
    "description": "Product ID on APA must be populated for stock movement transactions. Join: APA.EXEC_ID = TXN.TXN_ID"
})

# Fix test 361: APA records exist (correct join)
c.put("/api/tests/361", json={
    "name": "APA records exist for stock movement TXNs",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.APA a WHERE a.EXEC_ID = t.TXN_ID)",
    "expected_result": "0",
    "severity": "high",
    "description": "Every stock movement TXN should have a corresponding APA record (joined via EXEC_ID)"
})

# Fix test 362: FIP records exist (FIP joins to APA via APA_ID)
c.put("/api/tests/362", json={
    "name": "FIP records exist for stock movement APA records",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.FIP f WHERE f.APA_ID = a.APA_ID)",
    "expected_result": "0",
    "severity": "high",
    "description": "Every stock movement APA should have FIP record(s). FIP.APA_ID = APA.APA_ID"
})

# Fix test 363: TXN_RLTNP (correct: SRC_TXN_ID or TRGT_TXN_ID)
c.put("/api/tests/363", json={
    "name": "TXN_RLTNP relationships for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.TXN_RLTNP r WHERE r.SRC_TXN_ID = t.TXN_ID OR r.TRGT_TXN_ID = t.TXN_ID)",
    "expected_result": None,
    "severity": "medium",
    "description": "Check how many stock movement TXNs have TXN_RLTNP entries (SRC_TXN_ID or TRGT_TXN_ID)"
})

print("Fixed tests 359, 361, 362, 363")

# Now clear runs and re-run all manual tests
c.post("/api/tests/runs/clear-all-statuses")

# Restart needed to clear failure cache - but let's just wait and run one at a time
# Actually the failure cache TTL is 2 min. Let's first run a test to verify the fix
r = c.post("/api/tests/run/359")
d = r.json()
print(f"Test 359: {d['status']} | {(d.get('error_message') or d.get('actual_result',''))[:100]}")

# If 359 passed, run all
if d["status"] != "error":
    ids = list(range(349, 369))
    batch = c.post("/api/tests/run-batch", json={"test_ids": ids}).json()
    print(f"Batch: passed={batch.get('passed',0)}, failed={batch.get('failed',0)}, error={batch.get('error',0)}")
    
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
        print(f"  #{run['test_case_id']} {run['status']:7s} {run.get('execution_time_ms',0):5d}ms | {err or detail}")
else:
    print("Test 359 still erroring - need to restart server to clear cache")
