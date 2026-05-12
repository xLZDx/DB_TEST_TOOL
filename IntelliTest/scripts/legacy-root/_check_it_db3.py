import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)

# Check test_cases 21-25
rows = conn.execute("SELECT id, name, source_query FROM test_cases WHERE id BETWEEN 21 AND 25").fetchall()
for r in rows:
    print(f"ID={r[0]} Name={r[1]}")
    print(f"  SQL={r[2][:120]}")

# Check test_runs for tests 21-40
runs = conn.execute("""
    SELECT tr.test_case_id, tr.status, tr.error_message, tr.execution_time_ms
    FROM test_runs tr
    WHERE tr.test_case_id BETWEEN 21 AND 40
    ORDER BY tr.test_case_id, tr.id DESC
""").fetchall()
print(f"\nTest runs for IDs 21-40: {len(runs)}")
seen = set()
for r in runs:
    if r[0] not in seen:
        seen.add(r[0])
        err = r[2][:100] if r[2] else '(none)'
        print(f"  TC={r[0]} Status={r[1]} Time={r[3]}ms Err={err}")

conn.close()
