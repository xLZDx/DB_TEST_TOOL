import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DBTestingTool", "app.db")
conn = sqlite3.connect(db_path)

# Get latest runs for db-tool AI tests (309-348)
rows = conn.execute("""
    SELECT tr.test_case_id, tc.name, tr.status, tr.error_message
    FROM test_runs tr
    JOIN test_cases tc ON tc.id = tr.test_case_id
    INNER JOIN (
        SELECT test_case_id, MAX(id) as max_id
        FROM test_runs
        WHERE test_case_id BETWEEN 309 AND 348
        GROUP BY test_case_id
    ) latest ON tr.id = latest.max_id
    ORDER BY tr.test_case_id
""").fetchall()

for r in rows:
    status = r[2]
    detail = ''
    if status in ('error', 'failed'):
        detail = (r[3] or '')[:80]
    print(f"TC={r[0]:3d} [{status:6s}] {r[1][:55]:55s} {detail}")

print(f"\nSummary: passed={sum(1 for r in rows if r[2]=='passed')}, failed={sum(1 for r in rows if r[2]=='failed')}, error={sum(1 for r in rows if r[2]=='error')}")
conn.close()
