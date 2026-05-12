"""Run tests 363-368 individually."""
import httpx, json

c = httpx.Client(base_url="http://localhost:8550", timeout=120)

for tid in range(363, 369):
    r = c.post(f"/api/tests/run/{tid}")
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
