"""Directly test IntelliTest Oracle connection."""
import sqlite3, os, oracledb

# Get password from db-tool
db = os.path.join(os.environ['LOCALAPPDATA'], 'DBTestingTool', 'app.db')
conn = sqlite3.connect(db)
cur = conn.execute("SELECT password FROM datasources WHERE name='CDS'")
pw = cur.fetchone()[0]
conn.close()

print(f"Password: {'*' * len(pw)} ({len(pw)} chars)")

# Try connecting with the correct password
dsn = "orgds01aplqa:1571/gl_odiCCALqa_main.rjf.com"
try:
    cx = oracledb.connect(user="ikorostelev", password=pw, dsn=dsn, tcp_connect_timeout=8)
    cur = cx.cursor()
    cur.execute("SELECT COUNT(*) FROM CCAL_OWNER.TXN WHERE TD = DATE '2026-03-30' AND SRC_STM_ID IN (29,30,71,72)")
    print(f"Direct connection works! Count = {cur.fetchone()[0]}")
    cx.close()
except Exception as e:
    print(f"Direct connection failed: {e}")
