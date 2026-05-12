"""Execute tests in both tools and collect results."""
import httpx, json, sys

DB_TOOL = "http://localhost:8550"
INTELLITEST = "http://localhost:8560"


def run_dbtool_tests():
    """Run PBI1736268 tests in db-testing-tool."""
    c = httpx.Client(base_url=DB_TOOL, timeout=300)
    
    # Get folders
    folders = c.get("/api/tests/folders").json()
    pbi_folders = [f for f in folders if "PBI1736268" in f.get("name", "")]
    print("db-tool PBI folders:", [(f["id"], f["name"], f["test_count"]) for f in pbi_folders])
    
    for folder in pbi_folders:
        fid = folder["id"]
        fname = folder["name"]
        # Get tests in folder
        all_tests = c.get("/api/tests").json()
        folder_tests = [t for t in all_tests if t.get("folder_id") == fid]
        if not folder_tests:
            print(f"  {fname}: 0 tests, skipping")
            continue
        
        test_ids = [t["id"] for t in folder_tests]
        print(f"\n  Running {fname} ({len(test_ids)} tests): {test_ids[:5]}...")
        
        r = c.post("/api/tests/run-batch", json={"test_ids": test_ids})
        batch = r.json()
        print(f"  Result: passed={batch.get('passed',0)}, failed={batch.get('failed',0)}, error={batch.get('error',0)}")
        
        # Show individual results
        runs = c.get("/api/tests/runs", params={"limit": 100}).json()
        batch_runs = [r for r in runs if r.get("batch_id") == batch.get("batch_id")]
        for run in batch_runs:
            test = next((t for t in folder_tests if t["id"] == run["test_case_id"]), {})
            detail = ""
            if run.get("actual_result"):
                try:
                    d = json.loads(run["actual_result"])
                    detail = d.get("detail", "")[:100]
                except:
                    detail = str(run["actual_result"])[:100]
            err = (run.get("error_message") or "")[:100]
            ms = run.get("execution_time_ms", 0)
            print(f"    #{run['test_case_id']} {run['status']:7s} {ms:5d}ms | {test.get('name','')[:50]} | {err or detail}")


def run_intellitest_tests():
    """Run all tests in IntelliTest."""
    c = httpx.Client(base_url=INTELLITEST, timeout=300)
    
    folders = c.get("/api/tests/folders").json()
    print("IntelliTest folders:", [(f["id"], f["name"], f["test_count"]) for f in folders])
    
    all_tests = c.get("/api/tests").json()
    
    for folder in folders:
        fid = folder["id"]
        fname = folder["name"]
        folder_tests = [t for t in all_tests if t.get("folder_id") == fid]
        if not folder_tests:
            print(f"  {fname}: 0 tests, skipping")
            continue
        
        test_ids = [t["id"] for t in folder_tests]
        print(f"\n  Running {fname} ({len(test_ids)} tests)...")
        
        r = c.post("/api/tests/run-batch", json={"test_ids": test_ids})
        batch = r.json()
        print(f"  Result: passed={batch.get('passed',0)}, failed={batch.get('failed',0)}, error={batch.get('error',0)}")
        
        # Show failing tests
        runs = c.get("/api/tests/runs", params={"limit": 100}).json()
        batch_runs = [r for r in runs if r.get("batch_id") == batch.get("batch_id")]
        for run in batch_runs:
            test = next((t for t in folder_tests if t["id"] == run["test_case_id"]), {})
            err = (run.get("error_message") or "")[:100]
            detail = ""
            if run.get("actual_result"):
                try:
                    d = json.loads(run["actual_result"])
                    detail = d.get("detail", "")[:100]
                except:
                    pass
            ms = run.get("execution_time_ms", 0)
            print(f"    #{run['test_case_id']} {run['status']:7s} {ms:5d}ms | {test.get('name','')[:50]} | {err or detail}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    if mode in ("dbtool", "both"):
        print("=" * 60)
        print("DB-TESTING-TOOL EXECUTION")
        print("=" * 60)
        run_dbtool_tests()
    
    if mode in ("intellitest", "both"):
        print("\n" + "=" * 60)
        print("INTELLITEST EXECUTION")
        print("=" * 60)
        run_intellitest_tests()
