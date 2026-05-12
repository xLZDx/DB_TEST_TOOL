import sqlite3
conn = sqlite3.connect(r'C:\GIT_Repo\IntelliTest\data\intellitest.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
    print(f"  {t[0]}: {[c[1] for c in cols]}")
# Check test_case for run info
row = conn.execute("SELECT id, name, last_run_status, last_error_message FROM test_cases WHERE id=22").fetchone()
if row:
    print(f"\nTC22: status={row[2]}, err={row[3]}")
conn.close()
