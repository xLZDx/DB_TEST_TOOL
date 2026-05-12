import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)

# Get latest runs for tests 1-20
rows = conn.execute("""
    SELECT tr.test_case_id, tr.status, tr.error_message
    FROM test_runs tr
    INNER JOIN (
        SELECT test_case_id, MAX(id) as max_id
        FROM test_runs
        WHERE test_case_id BETWEEN 1 AND 20
        GROUP BY test_case_id
    ) latest ON tr.id = latest.max_id
    ORDER BY tr.test_case_id
""").fetchall()

for r in rows:
    err = r[2][:120] if r[2] else '(none)'
    print(f"TC={r[0]:2d} Status={r[1]:6s} Err={err}")

conn.close()
