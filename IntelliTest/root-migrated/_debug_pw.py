"""Check if IntelliTest loads password properly."""
import os, sys, sqlite3

# Simulate what IntelliTest does
db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DBTestingTool", "app.db")
print(f"DB exists: {os.path.exists(db_path)}")
print(f"DB path: {db_path}")

conn = sqlite3.connect(db_path)
db_tool_passwords = {}
for row in conn.execute("SELECT name, password FROM datasources WHERE password IS NOT NULL"):
    db_tool_passwords[row[0]] = row[1]
conn.close()

print(f"Passwords found: {list(db_tool_passwords.keys())}")
for name, pw in db_tool_passwords.items():
    print(f"  {name}: length={len(pw)}, has_value={bool(pw)}")

# Check IntelliTest internal state via import
sys.path.insert(0, "C:\\GIT_Repo\\IntelliTest")
# Check the datasource store
from app.routers.datasources import _datasources
for ds in _datasources:
    pw_status = "SET" if ds.get("password") else "EMPTY"
    pw_len = len(ds.get("password", "")) if ds.get("password") else 0
    print(f"\nDS #{ds['id']} {ds['name']}: password={pw_status} len={pw_len}")
