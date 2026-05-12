"""Execute agent's manual SQL tests against CDS via db-testing-tool API."""
import requests, json, time

BASE = "http://localhost:8550"
DS_ID = 2  # CDS datasource in db-testing-tool

tests = [
    {"id": 1, "name": "TXN total stock movement row count", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72)", "expected": "20", "type": "exact"},
    {"id": 2, "name": "TXN row count for S10REC (SRC_STM_ID=29)", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 29", "expected": "18", "type": "exact"},
    {"id": 3, "name": "TXN row count for S10DEL (SRC_STM_ID=30)", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 30", "expected": "2", "type": "exact"},
    {"id": 4, "name": "TXN row count for S10TFRS (SRC_STM_ID=72)", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 72", "expected": "0", "type": "exact"},
    {"id": 5, "name": "TXN row count for MULBULMT (SRC_STM_ID=71)", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID = 71", "expected": "0", "type": "exact"},
    {"id": 6, "name": "EXEC_SBTP_ID not null for trailer-parsed", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30) AND EXEC_SBTP_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 7, "name": "SRC_PCS_TP_ID not null for stock movements", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SRC_PCS_TP_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 8, "name": "TXN_TP_ID populated for stock movements", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_TP_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 9, "name": "TXN_SBTP_ID null count (trailer streams)", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30) AND TXN_SBTP_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 10, "name": "AR_ID populated for stock movements", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND AR_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 11, "name": "APA.PD_ID populated for stock movement TXNs", "sql": "SELECT COUNT(*) AS NULL_PD FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72) AND a.PD_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 12, "name": "CDSM_RULE_MAP lookup table exists", "sql": "SELECT COUNT(*) AS CNT FROM ALL_TABLES WHERE OWNER = 'CCAL_OWNER' AND TABLE_NAME = 'CDSM_RULE_MAP'", "expected": "1", "type": "exact"},
    {"id": 13, "name": "APA records exist for stock movement TXNs", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.APA a JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)", "expected": ">0", "type": "positive"},
    {"id": 14, "name": "FIP records for stock movement APA", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.FIP f JOIN CCAL_OWNER.APA a ON f.APA_ID = a.APA_ID JOIN CCAL_OWNER.TXN t ON a.EXEC_ID = t.TXN_ID WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)", "expected": ">=0", "type": "non_negative"},
    {"id": 15, "name": "TXN_RLTNP count exists", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN_RLTNP", "expected": ">=0", "type": "non_negative"},
    {"id": 16, "name": "SD not null for stock movements", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND SD IS NULL", "expected": "0", "type": "zero"},
    {"id": 17, "name": "TXN_SRC_KEY not null", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND TXN_SRC_KEY IS NULL", "expected": "0", "type": "zero"},
    {"id": 18, "name": "No duplicate TXN_SRC_KEY per stream", "sql": "SELECT COUNT(*) AS DUP_COUNT FROM (SELECT TXN_SRC_KEY, SRC_STM_ID, COUNT(*) AS C FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY TXN_SRC_KEY, SRC_STM_ID HAVING COUNT(*) > 1)", "expected": "0", "type": "zero"},
    {"id": 19, "name": "TD exists in DATE_DIM", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.DATE_DIM WHERE DT = DATE '2026-03-30'", "expected": "1", "type": "exact"},
    {"id": 20, "name": "SRC_PCS_TP_ID distribution", "sql": "SELECT SRC_PCS_TP_ID, COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) GROUP BY SRC_PCS_TP_ID ORDER BY SRC_PCS_TP_ID", "expected": "rows", "type": "has_rows"},
    {"id": 21, "name": "Staging row count", "sql": "SELECT COUNT(*) AS CNT FROM CDS_STG_OWNER.STCCCALQ_STG WHERE TD = DATE '2026-03-30'", "expected": ">0", "type": "positive"},
    {"id": 22, "name": "Staging SRC_STM_ID distribution", "sql": "SELECT SRC_STM_ID, COUNT(*) AS CNT FROM CDS_STG_OWNER.STCCCALQ_STG WHERE TD = DATE '2026-03-30' GROUP BY SRC_STM_ID ORDER BY SRC_STM_ID", "expected": "rows", "type": "has_rows"},
    {"id": 23, "name": "MNY_TXN_QUALFR table accessible", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.MNY_TXN_QUALFR", "expected": ">=0", "type": "non_negative"},
    {"id": 24, "name": "CCAL_ACVT_ID populated", "sql": "SELECT COUNT(*) AS CNT FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29, 30, 71, 72) AND CCAL_ACVT_ID IS NULL", "expected": "0", "type": "zero"},
    {"id": 25, "name": "No orphan APA records", "sql": "SELECT COUNT(*) AS ORPHAN_COUNT FROM CCAL_OWNER.APA a WHERE a.EXEC_ID IN (SELECT t.TXN_ID FROM CCAL_OWNER.TXN t WHERE t.TD = DATE '2026-03-30' AND t.SRC_STM_ID IN (29, 30, 71, 72)) AND NOT EXISTS (SELECT 1 FROM CCAL_OWNER.TXN t2 WHERE t2.TXN_ID = a.EXEC_ID)", "expected": "0", "type": "zero"},
]

results = []
for t in tests:
    start = time.time()
    try:
        r = requests.post(f"{BASE}/api/datasources/{DS_ID}/query",
                          json={"sql": t["sql"], "limit": 100}, timeout=60)
        elapsed = int((time.time() - start) * 1000)
        data = r.json()

        if "error" in data and data["error"]:
            results.append({**t, "status": "error", "actual": None, "error": data["error"], "ms": elapsed})
            continue

        rows = data.get("rows", data.get("data", []))
        if not rows:
            # Check if result is in different format
            results.append({**t, "status": "error", "actual": "empty response", "error": str(data)[:200], "ms": elapsed})
            continue

        # Evaluate
        first_row = rows[0] if rows else {}
        first_val = list(first_row.values())[0] if first_row else None

        if t["type"] == "exact":
            passed = str(first_val) == t["expected"]
        elif t["type"] == "zero":
            passed = first_val == 0 or first_val == "0"
        elif t["type"] == "positive":
            passed = first_val is not None and int(first_val) > 0
        elif t["type"] == "non_negative":
            passed = first_val is not None and int(first_val) >= 0
        elif t["type"] == "has_rows":
            passed = len(rows) > 0
        else:
            passed = True

        status = "PASS" if passed else "FAIL"
        results.append({**t, "status": status, "actual": first_val, "rows": rows if t["type"] == "has_rows" else None, "error": None, "ms": elapsed})
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        results.append({**t, "status": "error", "actual": None, "error": str(e), "ms": elapsed})

# Print results
print("=" * 90)
print(f"{'#':>3} {'Status':6} {'ms':>5}  {'Test Name':<50} {'Expected':>10} {'Actual':>10}")
print("=" * 90)
passed = failed = errors = 0
for r in results:
    if r["status"] == "PASS": passed += 1
    elif r["status"] == "FAIL": failed += 1
    else: errors += 1
    actual = str(r.get("actual", ""))[:10] if r["status"] != "error" else "(err)"
    print(f"{r['id']:3d} {r['status']:6} {r['ms']:5d}  {r['name']:<50} {r['expected']:>10} {actual:>10}")
    if r["status"] == "error":
        print(f"    ERROR: {r.get('error', '')[:80]}")

print("=" * 90)
print(f"TOTAL: {len(results)} | PASS: {passed} | FAIL: {failed} | ERROR: {errors}")

# Save as JSON
import json
import os
os.makedirs(r"c:\GIT_Repo\test_reports", exist_ok=True)
with open(r"c:\GIT_Repo\test_reports\agent_manual_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to test_reports/agent_manual_results.json")
