import sqlite3, os, oracledb

# Get password from db-tool
dbt_db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DBTestingTool", "app.db")
conn2 = sqlite3.connect(dbt_db)
row = conn2.execute("SELECT password FROM datasources WHERE name='CDS'").fetchone()
pw = row[0]
conn2.close()

# Get SQL from IntelliTest
it_db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn3 = sqlite3.connect(it_db)
row = conn3.execute("SELECT source_query FROM test_cases WHERE id=1").fetchone()
sql = row[0]
conn3.close()

cleaned = sql.rstrip().rstrip(";")
print(f"Executing: {cleaned}")

dsn = "orgds01aplqa:1571/gl_odiCCALqa_main.rjf.com"
c = oracledb.connect(user="ikorostelev", password=pw, dsn=dsn)
cur = c.cursor()
cur.execute(cleaned)
rows = cur.fetchall()
print(f"Result: {rows}")
c.close()
