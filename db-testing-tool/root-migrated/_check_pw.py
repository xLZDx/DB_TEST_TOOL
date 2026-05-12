import sqlite3, os
db = os.path.join(os.environ['LOCALAPPDATA'], 'DBTestingTool', 'app.db')
conn = sqlite3.connect(db)
cur = conn.execute("SELECT id, name, password FROM datasources WHERE name='CDS'")
row = cur.fetchone()
has_pw = "SET" if row[2] else "NULL"
print(f"id={row[0]}, name={row[1]}, password={has_pw}")
if row[2]:
    print(f"  pw length={len(row[2])}")
conn.close()
