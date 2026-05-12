"""Check tests 362-368 SQL."""
import httpx

c = httpx.Client(base_url="http://localhost:8550", timeout=60)

for tid in range(362, 369):
    t = c.get(f"/api/tests/{tid}").json()
    print(f"#{tid}: {t.get('name','')}")
    print(f"  SQL: {t.get('source_query','')[:300]}")
    print(f"  Expected: {t.get('expected_result','')}")
    print()
