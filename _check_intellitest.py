"""Fix IntelliTest manual tests (folder 2) to match the corrected db-tool versions, then run them."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8560", timeout=300, follow_redirects=True)

# Get all tests in folder 2
tests = c.get("/api/tests", params={"folder_id": 2}).json()
print(f"Found {len(tests)} tests in IntelliTest folder 2")

# Map by name pattern to identify which need fixing
for t in sorted(tests, key=lambda x: x["id"]):
    print(f"  #{t['id']}: {t['name'][:60]} | ds={t.get('source_datasource_id')}")
