"""Fix IntelliTest manual tests 31-40 to match corrected db-tool versions, then run all 20 manual."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8560", timeout=300, follow_redirects=True)

# Fix test 31: PD_ID - join via APA
c.put("/api/tests/31", json={
    "name": "APA.PD_ID populated for stock movement TXNs",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND a.PD_ID IS NULL",
    "expected_result": "0",
    "severity": "high",
    "description": "Product ID on APA must be populated for stock movement transactions. Join: APA.EXEC_ID = TXN.TXN_ID"
})
print("Fixed 31")

# Fix test 32: CDSM_RULE_MAP - use ALL_TABLES
c.put("/api/tests/32", json={
    "name": "CDSM_RULE_MAP lookup table exists in database",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM ALL_TABLES WHERE TABLE_NAME = 'CDSM_RULE_MAP'",
    "expected_result": None,
    "severity": "medium",
    "description": "Validates CDSM_RULE_MAP lookup table exists in database via ALL_TABLES catalog"
})
print("Fixed 32")

# Fix test 33: APA records
c.put("/api/tests/33", json={
    "name": "APA records exist for stock movement TXNs",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.APA a WHERE a.EXEC_ID = t.TXN_ID)",
    "expected_result": "0",
    "severity": "high",
    "description": "Every stock movement TXN should have a corresponding APA record"
})
print("Fixed 33")

# Fix test 34: FIP records (informational)
c.put("/api/tests/34", json={
    "name": "FIP records for stock movement APA (informational)",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.FIP f WHERE f.APA_ID = a.APA_ID)",
    "expected_result": None,
    "severity": "low",
    "description": "Count APAs without FIP records. Non-zero is informational (FIP may not be populated for all streams)."
})
print("Fixed 34")

# Fix test 35: TXN_RLTNP (optimized join)
c.put("/api/tests/35", json={
    "name": "TXN_RLTNP count for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN_RLTNP r JOIN CCAL_OWNER.TXN t ON r.SRC_TXN_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)",
    "expected_result": None,
    "severity": "medium",
    "description": "Count of TXN_RLTNP source relationships for stock movements on 2026-03-30"
})
print("Fixed 35")

# Test 36 (SD not null) - should be OK already but verify
c.put("/api/tests/36", json={
    "name": "SD not null for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SD IS NULL",
    "expected_result": "0",
    "severity": "medium",
    "description": "Settlement date should be populated for stock movements"
})
print("Fixed 36")

# Test 37 (TXN_SRC_KEY)
c.put("/api/tests/37", json={
    "name": "TXN_SRC_KEY not null for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_SRC_KEY IS NULL",
    "expected_result": "0",
    "severity": "high",
    "description": "Transaction source key must be populated"
})
print("Fixed 37")

# Test 38 (duplicates)
c.put("/api/tests/38", json={
    "name": "No duplicate TXN_SRC_KEY per SRC_STM_ID",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM (SELECT TXN_SRC_KEY, SRC_STM_ID, COUNT(*) AS C FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY TXN_SRC_KEY, SRC_STM_ID HAVING COUNT(*) > 1)",
    "expected_result": "0",
    "severity": "high",
    "description": "Each TXN_SRC_KEY should be unique per SRC_STM_ID on business day"
})
print("Fixed 38")

# Test 39 (DATE_DIM)
c.put("/api/tests/39", json={
    "name": "TD exists in DATE_DIM",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.DATE_DIM WHERE CAL_DT = DATE '2026-03-30'",
    "expected_result": "1",
    "severity": "low",
    "description": "Business day 2026-03-30 must exist in DATE_DIM"
})
print("Fixed 39")

# Test 40 (distribution)
c.put("/api/tests/40", json={
    "name": "SRC_PCS_TP_ID distribution for stock movements",
    "test_type": "custom_sql",
    "source_datasource_id": 1,
    "source_query": "SELECT SRC_STM_ID, SRC_PCS_TP_ID, COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY SRC_STM_ID, SRC_PCS_TP_ID ORDER BY SRC_STM_ID",
    "expected_result": None,
    "severity": "medium",
    "description": "Distribution of source processing type across stock movement streams"
})
print("Fixed 40")

# Now run all 20 manual tests (21-40) individually
print("\nRunning 20 IntelliTest manual tests...")
for tid in range(21, 41):
    try:
        r = c.post(f"/api/tests/run/{tid}", timeout=60)
        if r.status_code == 200:
            d = r.json()
            status = d.get("status", "?")
            err = (d.get("error_message") or "")[:80]
            detail = ""
            if d.get("actual_result"):
                try:
                    detail = json.loads(d["actual_result"]).get("detail", "")[:80]
                except:
                    pass
            print(f"  #{tid} {status:7s} {d.get('execution_time_ms',0):5d}ms | {err or detail}")
        else:
            print(f"  #{tid} HTTP {r.status_code}: {r.text[:200]}")
    except httpx.ReadTimeout:
        print(f"  #{tid} TIMEOUT (>60s)")
    except Exception as e:
        print(f"  #{tid} ERROR: {e}")

print("Done")
