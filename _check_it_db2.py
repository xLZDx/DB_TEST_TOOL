import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
    print(f"  {t[0]}: {[c[1] for c in cols]}")

# Count tests and check status
cnt = conn.execute("SELECT COUNT(*) FROM test_cases").fetchone()[0]
print(f"\nTotal tests: {cnt}")

# Check manual tests 21-40
rows = conn.execute("SELECT id, name, last_run_status, last_error_message FROM test_cases WHERE id >= 21 AND id <= 25").fetchall()
for r in rows:
    print(f"  ID={r[0]} Status={r[2]} Err={'(none)' if not r[3] else r[3][:120]}")

conn.close()
