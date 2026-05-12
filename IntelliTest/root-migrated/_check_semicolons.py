import sqlite3, os
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT id, source_query FROM test_cases WHERE id BETWEEN 1 AND 5").fetchall()
for r in rows:
    q = r[1]
    print(f"TC={r[0]} ends_with_semicolon={q.rstrip().endswith(';')} last_char='{q.rstrip()[-1]}'")
    print(f"  SQL={q[:100]}")
conn.close()
