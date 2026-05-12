import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)

# Get latest run for each test 1-20
rows = conn.execute("""
    SELECT tr.test_case_id, tc.name, tr.status, tr.error_message, tr.actual_result
    FROM test_runs tr
    JOIN test_cases tc ON tc.id = tr.test_case_id
    INNER JOIN (
        SELECT test_case_id, MAX(id) as max_id
        FROM test_runs
        WHERE test_case_id BETWEEN 1 AND 20
        GROUP BY test_case_id
    ) latest ON tr.id = latest.max_id
    ORDER BY tr.test_case_id
""").fetchall()

for r in rows:
    status = r[2]
    detail = ''
    if status == 'error':
        detail = (r[3] or '')[:80]
    elif status == 'failed':
        detail = (r[4] or '')[:80]
    print(f"TC={r[0]:2d} [{status:6s}] {r[1][:50]}: {detail}")

conn.close()
