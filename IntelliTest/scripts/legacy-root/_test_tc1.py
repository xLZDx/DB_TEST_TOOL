import sqlite3, os, sys
sys.path.insert(0, r'C:\GIT_Repo\IntelliTest')

db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "IntelliTest", "app.db")
conn = sqlite3.connect(db_path)
row = conn.execute("SELECT source_query FROM test_cases WHERE id=1").fetchone()
sql = row[0]
print(f"Raw SQL repr: {repr(sql)}")
cleaned = sql.rstrip().rstrip(";")
print(f"Cleaned repr: {repr(cleaned)}")
conn.close()

# Now test with Oracle
from app.routers.datasources import _ds_store
# Initialize datasources
import asyncio
from app.routers.datasources import _init_from_env
asyncio.run(_init_from_env())

ds = _ds_store.get("1")
if not ds:
    print("No datasource 1!")
    sys.exit(1)

import oracledb
dsn = f"{ds['host']}:{ds['port']}/{ds['service']}"
print(f"Connecting to {dsn} as {ds['user']}")
c = oracledb.connect(user=ds['user'], password=ds['password'], dsn=dsn)
cur = c.cursor()
print(f"Executing: {cleaned}")
cur.execute(cleaned)
rows = cur.fetchall()
print(f"Result: {rows}")
c.close()
