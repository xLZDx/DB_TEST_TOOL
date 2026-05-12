"""Debug IntelliTest datasource store."""
import httpx

c = httpx.Client(base_url="http://localhost:8560", timeout=10, follow_redirects=True)

# Use the test-connection endpoint to see details
for ds_id in [1, 2]:
    r = c.post(f"/api/datasources/{ds_id}/test")
    print(f"DS {ds_id}: {r.json()}")

# Check internal state via a custom query
# Actually let's just check the /api/datasources endpoint more carefully
r = c.get("/api/datasources")
print(f"\nFull response: {r.json()}")
