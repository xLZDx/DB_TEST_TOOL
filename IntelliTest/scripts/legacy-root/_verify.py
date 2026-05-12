"""Verify test counts and sample data in both tools."""
import httpx

r1 = httpx.get("http://localhost:8550/api/tests/dashboard-stats").json()
print(f"db-tool: {r1['total_tests']} tests")

r2 = httpx.get("http://localhost:8560/api/tests/dashboard-stats").json()
print(f"IntelliTest: {r2['total_tests']} tests")

f = httpx.get("http://localhost:8560/api/tests/folders").json()
print(f"IntelliTest folders: {f}")

t = httpx.get("http://localhost:8560/api/tests").json()
for tt in t[:5]:
    sql = (tt.get("source_query") or "NONE")[:80]
    print(f"  #{tt['id']} {tt['name'][:60]} | ds={tt['source_datasource_id']} | sql={sql}")
