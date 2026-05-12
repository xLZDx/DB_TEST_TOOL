"""Test a single IntelliTest test to verify password works."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8560", timeout=60, follow_redirects=True)

# Run only test 21 (simplest: TXN total row count)
r = c.post("/api/tests/run/21")
if r.status_code == 200:
    d = r.json()
    status = d.get("status", "?")
    err = (d.get("error_message") or "")[:100]
    detail = ""
    if d.get("actual_result"):
        try:
            detail = json.loads(d["actual_result"]).get("detail", "")[:100]
        except:
            pass
    print(f"#{d.get('test_case_id',21)} {status} | {err or detail}")
else:
    print(f"HTTP {r.status_code}: {r.text[:300]}")
