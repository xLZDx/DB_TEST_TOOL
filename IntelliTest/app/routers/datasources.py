"""Datasource management router for IntelliTest.

Provides in-memory datasource management loaded from DATASOURCES_JSON environment variable.
For a production deployment, this would persist to a database.
"""
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/datasources", tags=["datasources"])

# In-memory store seeded from env
_datasources: List[dict] = []
_next_id = 1


def _init_from_env():
    global _datasources, _next_id
    from app.config import settings
    raw = settings.get_datasources()

    # Try to read passwords from db-testing-tool's SQLite DB if not in env
    db_tool_passwords = {}
    try:
        import sqlite3, os
        db_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DBTestingTool", "app.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            for row in conn.execute("SELECT name, password FROM datasources WHERE password IS NOT NULL"):
                db_tool_passwords[row[0]] = row[1]
            conn.close()
    except Exception:
        pass

    for i, ds in enumerate(raw, start=1):
        pw = ds.get("password")
        if not pw:
            pw = db_tool_passwords.get(ds.get("name", ""))
        _datasources.append({
            "id": i, "name": ds.get("name", f"DS{i}"), "type": ds.get("type", ds.get("db_type", "unknown")),
            "host": ds.get("host", ""), "port": ds.get("port", 0),
            "service": ds.get("service", ds.get("database", "")),
            "database_name": ds.get("database_name", ds.get("service", ds.get("database", ""))),
            "username": ds.get("username", ""), "password": pw,
            "status": "configured",
        })
    _next_id = len(_datasources) + 1


_init_from_env()


class AddDataSourceRequest(BaseModel):
    name: str
    connection_string: str = ""  # direct connection string (settings page)
    type: str = "unknown"
    host: str = ""
    port: int = 0
    service: str = ""
    username: str = ""
    password: str = ""


@router.get("/")
async def list_datasources():
    return {"datasources": [{k: v for k, v in ds.items() if k != "password"} for ds in _datasources]}


@router.post("/")
async def add_datasource(body: AddDataSourceRequest):
    global _next_id
    ds = {
        "id": _next_id, "name": body.name, "type": body.type,
        "host": body.host, "port": body.port, "service": body.service,
        "username": body.username, "password": body.password,
        "connection_string": body.connection_string, "status": "configured",
    }
    _datasources.append(ds)
    _next_id += 1
    return {k: v for k, v in ds.items() if k not in ("password",)}


@router.post("/{ds_id}/test")
async def test_connection(ds_id: str):
    """Test a datasource connection by ID or name."""
    # Try integer ID first, then name
    ds = None
    try:
        id_int = int(ds_id)
        ds = next((d for d in _datasources if d["id"] == id_int), None)
    except ValueError:
        ds = next((d for d in _datasources if d["name"] == ds_id), None)
    if not ds:
        raise HTTPException(404, "Datasource not found")
    return {"ok": True, "message": f"Connection to {ds['name']} ({ds.get('type','?')}) configured — run a test query to verify live connectivity"}
