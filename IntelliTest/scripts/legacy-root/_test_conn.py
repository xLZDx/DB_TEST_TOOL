import sys; sys.path.insert(0, 'C:/GIT_Repo/IntelliTest')
from app.routers.datasources import _datasources
from app.routers.tests import _get_oracle_connection
ds = [d for d in _datasources if d['name'] == 'CDS'][0]
try:
    conn = _get_oracle_connection(ds)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM DUAL')
    print('SUCCESS:', cur.fetchone())
    conn.close()
except Exception as e:
    print('ERROR:', e)
