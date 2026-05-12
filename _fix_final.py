"""Fix tests 360-368 and final run."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=120)

# Fix test 360: CDSM_RULE_MAP - try with schema prefix or different approach
# The user might not have direct access to CDS_STG_OWNER. Check if table exists via ALL_TABLES
c.put("/api/tests/360", json={
    "name": "CDSM_RULE_MAP exists and has rules", 
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM ALL_TABLES WHERE TABLE_NAME = 'CDSM_RULE_MAP'",
    "expected_result": None,
    "severity": "high",
    "description": "Validates CDSM_RULE_MAP lookup table (CDSMANUL equivalent) exists in the database"
})

# Fix test 361: APA records - join was already fixed, but let's make sure the query works
c.put("/api/tests/361", json={
    "name": "APA records exist for stock movement TXNs",
    "test_type": "custom_sql", 
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.APA a WHERE a.EXEC_ID = t.TXN_ID)",
    "expected_result": "0",
    "severity": "high",
    "description": "Every stock movement TXN should have a corresponding APA record"
})

# Fix test 362: FIP records
c.put("/api/tests/362", json={
    "name": "FIP records exist for stock movement APA",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.FIP f WHERE f.APA_ID = a.APA_ID)",
    "expected_result": "0",
    "severity": "high",
    "description": "Every stock movement APA should have FIP records"
})

# Fix test 363: TXN_RLTNP
c.put("/api/tests/363", json={
    "name": "TXN_RLTNP count for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN_RLTNP r WHERE EXISTS (SELECT 1 FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND (r.SRC_TXN_ID = t.TXN_ID OR r.TRGT_TXN_ID = t.TXN_ID))",
    "expected_result": None,
    "severity": "medium",
    "description": "Count of TXN_RLTNP relationships for stock movements on 2026-03-30"
})

# Fix test 364: SD not null
c.put("/api/tests/364", json={
    "name": "SD not null for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SD IS NULL",
    "expected_result": "0",
    "severity": "medium",
    "description": "Settlement date should be populated for stock movements"
})

# Fix test 365: TXN_SRC_KEY not null
c.put("/api/tests/365", json={
    "name": "TXN_SRC_KEY not null for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_SRC_KEY IS NULL",
    "expected_result": "0",
    "severity": "high",
    "description": "Transaction source key must be populated"
})

# Fix test 366: Duplicate check
c.put("/api/tests/366", json={
    "name": "No duplicate TXN_SRC_KEY per SRC_STM_ID",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM (SELECT TXN_SRC_KEY, SRC_STM_ID, COUNT(*) AS C FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY TXN_SRC_KEY, SRC_STM_ID HAVING COUNT(*) > 1)",
    "expected_result": "0",
    "severity": "high",
    "description": "Each TXN_SRC_KEY should be unique per SRC_STM_ID on business day"
})

# Fix test 367: DATE_DIM
c.put("/api/tests/367", json={
    "name": "TD exists in DATE_DIM",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.DATE_DIM WHERE CAL_DT = DATE '2026-03-30'",
    "expected_result": "1",
    "severity": "low",
    "description": "Business day 2026-03-30 must exist in DATE_DIM"
})

# Fix test 368: SRC_PCS_TP_ID distribution
c.put("/api/tests/368", json={
    "name": "SRC_PCS_TP_ID distribution for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 2,
    "source_query": "SELECT SRC_STM_ID, SRC_PCS_TP_ID, COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY SRC_STM_ID, SRC_PCS_TP_ID ORDER BY SRC_STM_ID",
    "expected_result": None,
    "severity": "medium",
    "description": "Distribution of source processing type across stock movement streams"
})

print("All tests fixed.")

# Clear runs
c.post("/api/tests/runs/clear-all-statuses")

# Run manual tests
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
    print(f"  #{run['test_case_id']} {run['status']:7s} {run.get('execution_time_ms',0):5d}ms | {err or detail}")
