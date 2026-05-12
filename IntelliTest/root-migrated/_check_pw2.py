import sys; sys.path.insert(0, 'C:/GIT_Repo/IntelliTest')
from app.routers.datasources import _datasources
for ds in _datasources:
    pw = ds.get('password') or ''
    print(f"DS {ds['name']}: pw_len={len(pw)}")
