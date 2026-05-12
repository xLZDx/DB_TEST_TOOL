"""Smoke test for all DB Testing Tool API endpoints."""
import httpx
import json
import sys

BASE = "http://127.0.0.1:8550"
passed = 0
failed = 0

def check(name, response, expect_status=200):
    global passed, failed
    ok = response.status_code == expect_status
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    body = response.text[:200]
    print(f"  [{status}] {name} -> {response.status_code} {body}")
    return ok

def main():
    global passed, failed
    client = httpx.Client(base_url=BASE, timeout=30)

    print("=" * 60)
    print("  DB Testing Tool - API Smoke Tests")
    print("=" * 60)

    # ── 1. Dashboard ────────────────────────────────────────────
    print("\n-- Dashboard --")
    r = client.get("/")
    check("GET / (dashboard page)", r)

    r = client.get("/api/tests/dashboard-stats")
    check("GET /api/tests/dashboard-stats", r)

    # ── 2. Data Sources ─────────────────────────────────────────
    print("\n-- Data Sources --")
    r = client.get("/api/datasources")
    check("GET /api/datasources (empty)", r)

    # Create Oracle datasource
    r = client.post("/api/datasources", json={
        "name": "Test Oracle",
        "db_type": "oracle",
        "host": "fake-oracle-host",
        "port": 1521,
        "database_name": "ORCL",
        "username": "testuser",
        "password": "testpass",
    })
    check("POST /api/datasources (create oracle)", r)
    oracle_id = r.json().get("id")

    # Create Redshift datasource
    r = client.post("/api/datasources", json={
        "name": "Test Redshift",
        "db_type": "redshift",
        "host": "fake-redshift-host",
        "port": 5439,
        "database_name": "analytics",
        "username": "rsuser",
        "password": "rspass",
    })
    check("POST /api/datasources (create redshift)", r)
    redshift_id = r.json().get("id")

    r = client.get("/api/datasources")
    check("GET /api/datasources (2 items)", r)
    ds_count = len(r.json())
    if ds_count == 2:
        passed += 1
        print(f"  [PASS] datasources count = {ds_count}")
    else:
        failed += 1
        print(f"  [FAIL] datasources count = {ds_count}, expected 2")

    # Test connection (will fail since fake host, but should not crash)
    r = client.post(f"/api/datasources/{oracle_id}/test")
    check("POST /api/datasources/{id}/test (oracle, expected fail)", r)

    # ── 3. Pages ────────────────────────────────────────────────
    print("\n-- Page Routes --")
    for page in ["/datasources", "/schema-browser", "/mappings", "/tests", "/runs", "/ai-assistant", "/tfs", "/settings"]:
        r = client.get(page)
        check(f"GET {page}", r)

    # ── 4. Schema Browser ──────────────────────────────────────
    print("\n-- Schema Browser --")
    r = client.get(f"/api/schemas/tree/{oracle_id}")
    check("GET /api/schemas/tree/{id} (empty)", r)

    # ── 5. Mapping Rules ───────────────────────────────────────
    print("\n-- Mapping Rules --")
    r = client.get("/api/mappings")
    check("GET /api/mappings (empty)", r)

    r = client.post("/api/mappings", json={
        "name": "Test Mapping: SRC_TBL -> TGT_TBL",
        "source_datasource_id": oracle_id,
        "source_schema": "SRC_SCHEMA",
        "source_table": "SRC_TABLE",
        "source_columns": '["col1", "col2", "amount"]',
        "target_datasource_id": redshift_id,
        "target_schema": "tgt_schema",
        "target_table": "tgt_table",
        "target_columns": '["col1", "col2", "amount"]',
        "rule_type": "direct",
        "description": "Test mapping rule",
    })
    check("POST /api/mappings (create)", r)
    rule_id = r.json().get("id")

    r = client.get(f"/api/mappings/{rule_id}")
    check(f"GET /api/mappings/{rule_id}", r)

    # ── 6. Test Generation ──────────────────────────────────────
    print("\n-- Test Generation --")
    r = client.post(f"/api/tests/generate/{rule_id}")
    check(f"POST /api/tests/generate/{rule_id}", r)
    gen_count = r.json().get("count", 0)
    print(f"       Generated {gen_count} test(s)")

    r = client.get("/api/tests")
    check("GET /api/tests (after generation)", r)
    tests = r.json()
    test_count = len(tests)
    if test_count > 0:
        passed += 1
        print(f"  [PASS] tests count = {test_count}")
    else:
        failed += 1
        print(f"  [FAIL] tests count = {test_count}, expected > 0")

    # ── 7. Manual Test Creation ─────────────────────────────────
    print("\n-- Manual Test Creation --")
    r = client.post("/api/tests", json={
        "name": "Custom Row Count Check",
        "test_type": "custom_sql",
        "target_datasource_id": redshift_id,
        "target_query": "SELECT 1 AS result",
        "severity": "medium",
        "description": "A manually created custom test",
    })
    check("POST /api/tests (manual create)", r)
    manual_test_id = r.json().get("id")

    # ── 8. Test Runs ────────────────────────────────────────────
    print("\n-- Test Runs --")
    r = client.get("/api/tests/runs")
    check("GET /api/tests/runs (empty)", r)

    # Note: running a test will fail at execution since DBs are fake,
    # but the endpoint itself should return 200 with error status
    if tests:
        first_test_id = tests[0]["id"]
        r = client.post(f"/api/tests/run/{first_test_id}")
        check(f"POST /api/tests/run/{first_test_id} (will error, fake db)", r)
        run_data = r.json()
        print(f"       Run status: {run_data.get('status')}")

    # Batch run
    r = client.post("/api/tests/run-batch", json={"test_ids": None})
    check("POST /api/tests/run-batch (all)", r)
    batch = r.json()
    print(f"       Batch: total={batch.get('total')}, passed={batch.get('passed')}, error={batch.get('error')}")

    r = client.get("/api/tests/runs")
    check("GET /api/tests/runs (after execution)", r)
    runs = r.json()
    if len(runs) > 0:
        passed += 1
        print(f"  [PASS] runs count = {len(runs)}")

        # Get run detail
        r = client.get(f"/api/tests/runs/{runs[0]['id']}")
        check(f"GET /api/tests/runs/{runs[0]['id']} (detail)", r)

    # ── 9. TFS Work Items ──────────────────────────────────────
    print("\n-- TFS Work Items --")
    r = client.get("/api/tfs/workitems")
    check("GET /api/tfs/workitems (empty)", r)

    r = client.post("/api/tfs/workitems", json={
        "title": "Test Bug from Smoke Test",
        "description": "Automated smoke test bug",
        "repro_steps": "1. Run smoke tests\n2. Review",
        "test_run_ids": [1],
        "severity": "3 - Medium",
        "tags": "SmokeTest",
    })
    check("POST /api/tfs/workitems (create local)", r)

    r = client.get("/api/tfs/workitems")
    check("GET /api/tfs/workitems (1 item)", r)
    wi_count = len(r.json())
    if wi_count >= 1:
        passed += 1
        print(f"  [PASS] work items count = {wi_count}")

    # Auto-bugs for batch
    if batch.get("batch_id"):
        r = client.post("/api/tfs/auto-bugs", json={"batch_id": batch["batch_id"]})
        check("POST /api/tfs/auto-bugs", r)

    # ── 10. AI Endpoints ────────────────────────────────────────
    print("\n-- AI Endpoints (no API key, expect graceful error) --")
    r = client.post("/api/ai/analyze-sql", json={"sql_text": "SELECT 1 FROM dual"})
    check("POST /api/ai/analyze-sql", r)
    ai_resp = r.json()
    if "error" in ai_resp and "API key" in ai_resp.get("error", ""):
        passed += 1
        print(f"  [PASS] AI returns key-not-configured message")

    r = client.post("/api/ai/extract-rules", json={"sql_text": "INSERT INTO tgt SELECT * FROM src"})
    check("POST /api/ai/extract-rules", r)

    # ── 11. Cleanup ─────────────────────────────────────────────
    print("\n-- Cleanup --")
    if manual_test_id:
        r = client.delete(f"/api/tests/{manual_test_id}")
        check(f"DELETE /api/tests/{manual_test_id}", r)

    r = client.delete(f"/api/mappings/{rule_id}")
    check(f"DELETE /api/mappings/{rule_id}", r)

    r = client.delete(f"/api/datasources/{oracle_id}")
    check(f"DELETE /api/datasources/{oracle_id}", r)

    r = client.delete(f"/api/datasources/{redshift_id}")
    check(f"DELETE /api/datasources/{redshift_id}", r)

    # ── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    client.close()
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
