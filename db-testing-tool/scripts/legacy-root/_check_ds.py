"""Check datasource configs in both tools."""
import httpx

# db-testing-tool
c1 = httpx.Client(base_url="http://localhost:8550", timeout=10, follow_redirects=True)
ds = c1.get("/api/datasources").json()
print("=== db-testing-tool datasources ===")
for d in ds:
    print(f"  #{d['id']}: {d.get('name','')} | host={d.get('host','')} | port={d.get('port','')} | db={d.get('database_name','')} | user={d.get('username','')}")

# IntelliTest
c2 = httpx.Client(base_url="http://localhost:8560", timeout=10, follow_redirects=True)
ds2 = c2.get("/api/datasources").json()
print("\n=== IntelliTest datasources ===")
for d in ds2:
    print(f"  #{d['id']}: {d.get('name','')} | host={d.get('host','')} | port={d.get('port','')} | db={d.get('database_name','')} | user={d.get('username','')}")
