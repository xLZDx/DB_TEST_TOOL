"""ODI operations router: repository profile discovery, package run, and session monitoring."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api/odi", tags=["odi"])

_ODI_PACKAGE_INDEX: set[str] = set()
_ODI_PACKAGE_INDEX_BY_REPO: Dict[str, set[str]] = {}
_ODI_CONTEXT_INDEX_BY_REPO: Dict[str, set[str]] = {}
_ODI_SESSIONS: Dict[str, Dict[str, Any]] = {}
_ODI_SESSION_PROCESSES: Dict[str, asyncio.subprocess.Process] = {}
_ODI_REPO_CONNECTIONS: Dict[str, Dict[str, Any]] = {}

_DEFAULT_CONTEXTS = ["QA", "DEV", "UAT", "PROD", "TAXLOTS"]
_DEFAULT_EXECUTION_AGENTS = ["Oracle", "Local"]
_DEFAULT_LOGICAL_AGENTS = ["OracleDIAgent (ODI Agent)"]


def _default_odi_root() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "odi"
    return Path.home() / "AppData" / "Roaming" / "odi"


def _resolve_root_path(root_path: str = "") -> Path:
    if root_path and root_path.strip():
        return Path(root_path.strip())
    return _default_odi_root()


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return ""


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sanitize_login_payload(payload: Dict[str, str]) -> Dict[str, str]:
    """Never expose password material from ODI login exports."""
    return {
        "login_name": _compact_text(payload.get("LoginName", "")),
        "login_user": _compact_text(payload.get("LoginUser", "")),
        "db_user": _compact_text(payload.get("LoginDbuser", "")),
        "db_url": _compact_text(payload.get("LoginDburl", "")),
        "work_repository": _compact_text(payload.get("LoginWorkRepository", "")),
        "driver": _compact_text(payload.get("LoginDbdriver", "")),
    }


def _extract_login_records_from_xml(xml_text: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    if not xml_text.strip():
        return records
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return records

    for obj in root.findall(".//Object"):
        if "SnpLogin" not in (obj.attrib.get("class") or ""):
            continue
        fields: Dict[str, str] = {}
        for fld in obj.findall("Field"):
            name = fld.attrib.get("name")
            if not name:
                continue
            fields[name] = _compact_text(fld.text)
        rec = _sanitize_login_payload(fields)
        if rec.get("login_name"):
            records.append(rec)
    return records


def _extract_package_name_candidates(text: str) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"\b[A-Z][A-Z0-9_]{6,}\b", text.upper())
    bad_prefixes = ("LOGIN", "PASSWORD", "JDBC", "ORACLE", "SOURCE", "TARGET", "SESSION")
    filtered: List[str] = []
    for t in tokens:
        if t.startswith(bad_prefixes):
            continue
        if "_" not in t:
            continue
        filtered.append(t)
    return filtered


def _normalize_upper(value: str) -> str:
    return _compact_text(value).upper()


def _repo_key(owner_token: str = "", login_name: str = "") -> str:
    token = (owner_token or "").strip()
    login = (login_name or "").strip()
    if token:
        state = _ODI_REPO_CONNECTIONS.get(token) or {}
        root_path = _normalize_upper(str(state.get("root_path") or ""))
        login_from_state = _normalize_upper(str(state.get("login_name") or ""))
        if root_path or login_from_state:
            return f"{root_path}|{login_from_state}".strip("|") or "GLOBAL"
    if login:
        return f"LOGIN|{_normalize_upper(login)}"
    return "GLOBAL"


def _looks_like_context_name(value: str) -> bool:
    token = _compact_text(value)
    if not token:
        return False
    if len(token) > 64:
        return False
    if re.search(r"[^A-Za-z0-9_\- ]", token):
        return False
    upper = token.upper()
    banned = {
        "ALL CONTEXTS",
        "DEFAULT CONTEXT FOR EXECUTION",
        "DEFAULT DESIGNER CONTEXT",
        "DEFAULT CONTEXT FOR GENERATING DATA SERVICES",
    }
    if upper in banned:
        return False
    return bool(re.search(r"[A-Z]", upper))


def _extract_context_candidates(text: str) -> set[str]:
    found: set[str] = set()
    if not text.strip():
        return found

    pattern = r'(?is)<Field\s+name="(?:CtxName|ContextName|ContextCode|Context)"[^>]*>\s*(?:<!\[CDATA\[)?([^<\]]+)'
    for m in re.findall(pattern, text):
        candidate = _compact_text(m)
        if _looks_like_context_name(candidate):
            found.add(candidate.upper())

    return found


def _discover_contexts(root: Path) -> set[str]:
    contexts: set[str] = {c.upper() for c in _DEFAULT_CONTEXTS}
    if not root.exists() or not root.is_dir():
        return contexts

    xml_files = sorted(root.rglob("*.xml"))[:120]
    for p in xml_files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        contexts.update(_extract_context_candidates(text))

    return contexts


def _index_packages(repo_key: str, packages: List[str]) -> None:
    if not packages:
        return
    bucket = _ODI_PACKAGE_INDEX_BY_REPO.setdefault(repo_key, set())
    for name in packages:
        upper = _normalize_upper(name)
        if not upper:
            continue
        _ODI_PACKAGE_INDEX.add(upper)
        bucket.add(upper)


def _session_summary(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "session_id": s["session_id"],
        "package_name": s.get("package_name", ""),
        "status": s.get("status", "pending"),
        "progress": s.get("progress", 0),
        "context": s.get("context", ""),
        "execution_agent": s.get("execution_agent", ""),
        "logical_agent": s.get("logical_agent", ""),
        "login_name": s.get("login_name", ""),
        "repository_connected": bool(s.get("repository_connected")),
        "repository_name": s.get("repository_name", ""),
        "repo_key": s.get("repo_key", "GLOBAL"),
        "source": s.get("source", "simulated"),
        "variables": s.get("variables", {}),
        "started_at": s.get("started_at", 0),
        "ended_at": s.get("ended_at"),
        "error_count": len(s.get("errors", [])),
        "step_count": len(s.get("steps", [])),
    }


def _append_error(session_id: str, message: str, line: str = "") -> None:
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        return
    s.setdefault("errors", []).append({
        "ts": time.time(),
        "message": _compact_text(message),
        "line": (line or "")[:1200],
    })


def _append_step(session_id: str, name: str, status: str, detail: str = "") -> None:
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        return
    step_no = len(s.setdefault("steps", [])) + 1
    s["steps"].append({
        "step_no": step_no,
        "name": _compact_text(name),
        "status": status,
        "detail": (detail or "")[:2000],
        "ts": time.time(),
    })


def sweep_odi_sessions(
    *,
    stale_seconds: int = 600,
    max_runtime_seconds: int = 7200,
    retain_seconds: int = 3600,
) -> Dict[str, int]:
    """Kill stale/zombie ODI sessions and prune completed session history."""
    now = time.time()
    stale_seconds = max(30, int(stale_seconds or 600))
    max_runtime_seconds = max(60, int(max_runtime_seconds or 7200))
    retain_seconds = max(60, int(retain_seconds or 3600))

    killed = 0
    zombie_killed = 0
    pruned = 0

    for session_id, session in list(_ODI_SESSIONS.items()):
        status = str(session.get("status") or "").lower()
        started_at = float(session.get("started_at") or now)
        ended_at = session.get("ended_at")

        steps = session.get("steps") or []
        errors = session.get("errors") or []
        last_step_ts = float(steps[-1].get("ts") or 0) if steps else 0
        last_error_ts = float(errors[-1].get("ts") or 0) if errors else 0
        last_activity_ts = max(started_at, last_step_ts, last_error_ts)
        runtime = max(0.0, now - started_at)
        idle = max(0.0, now - last_activity_ts)

        proc = _ODI_SESSION_PROCESSES.get(session_id)
        is_terminal = status in {"success", "error", "warning", "canceled", "killed_stale"}

        if not is_terminal and (idle >= stale_seconds or runtime >= max_runtime_seconds):
            session["cancel_requested"] = True
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            session["status"] = "killed_stale"
            session["ended_at"] = now
            _append_error(session_id, "Watchdog killed stale ODI session")
            killed += 1

        proc = _ODI_SESSION_PROCESSES.get(session_id)
        if proc and status in {"success", "error", "warning", "canceled", "killed_stale"} and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass
            zombie_killed += 1

        terminal_ts = float(session.get("ended_at") or 0)
        if terminal_ts and (now - terminal_ts) > retain_seconds:
            _ODI_SESSIONS.pop(session_id, None)
            _ODI_SESSION_PROCESSES.pop(session_id, None)
            pruned += 1

    return {
        "killed_stale": killed,
        "killed_zombie_processes": zombie_killed,
        "pruned": pruned,
        "active_sessions": len(_ODI_SESSIONS),
    }


class OdiRunRequest(BaseModel):
    package_name: str
    context: str = ""
    execution_agent: str = ""
    logical_agent: str = ""
    login_name: str = ""
    owner_token: str = ""
    command_template: str = ""
    variables: Dict[str, str] = {}
    require_real_run: bool = False


class OdiRepoConnectRequest(BaseModel):
    login_name: str
    owner_token: str
    root_path: str = ""


async def _simulate_odi_session(session_id: str) -> None:
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        return
    s["status"] = "running"
    phases = [
        "Connect to repository",
        "Resolve scenario/package metadata",
        "Start ODI execution",
        "Execute package steps",
        "Collect execution report",
    ]
    for idx, phase in enumerate(phases, start=1):
        if s.get("cancel_requested"):
            s["status"] = "canceled"
            s["ended_at"] = time.time()
            return
        _append_step(session_id, phase, "ok")
        s["progress"] = int((idx / len(phases)) * 100)
        await asyncio.sleep(1.2)

    s["status"] = "success"
    s["progress"] = 100
    s["ended_at"] = time.time()


async def _run_command_session(session_id: str, command: str) -> None:
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        return
    s["status"] = "running"
    s["source"] = "command"
    s["command"] = command
    _append_step(session_id, "Launch ODI command", "ok", command)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except Exception as exc:
        _append_error(session_id, f"Failed to start ODI command: {exc}")
        s["status"] = "error"
        s["ended_at"] = time.time()
        return

    _ODI_SESSION_PROCESSES[session_id] = proc

    try:
        while True:
            if s.get("cancel_requested"):
                try:
                    proc.terminate()
                except Exception:
                    pass
                s["status"] = "canceled"
                s["ended_at"] = time.time()
                return

            line_raw = await proc.stdout.readline() if proc.stdout else b""
            if not line_raw:
                break
            line = _decode_text(line_raw).strip()
            if not line:
                continue

            s.setdefault("raw_output", []).append(line)
            if len(s["raw_output"]) > 500:
                s["raw_output"] = s["raw_output"][-500:]

            if re.search(r"(ODI-\d+|ORA-\d+|DPY-\d+|\bERROR\b|\bEXCEPTION\b)", line, flags=re.IGNORECASE):
                _append_error(session_id, "ODI runtime error", line)
            if re.search(r"(TASK|STEP|SESSION TASK|COMMAND ON SOURCE)", line, flags=re.IGNORECASE):
                _append_step(session_id, "Runtime step", "ok", line)

        returncode = await proc.wait()
        s["progress"] = 100
        s["ended_at"] = time.time()
        if s.get("cancel_requested"):
            s["status"] = "canceled"
        elif returncode == 0 and not s.get("errors"):
            s["status"] = "success"
        elif returncode == 0:
            s["status"] = "warning"
        else:
            s["status"] = "error"
            _append_error(session_id, f"Command exited with code {returncode}")

    finally:
        _ODI_SESSION_PROCESSES.pop(session_id, None)


def _collect_logins(root_path: str = "") -> List[Dict[str, Any]]:
    root = _resolve_root_path(root_path)
    if not root.exists() or not root.is_dir():
        return []

    login_files = sorted(root.rglob("snps_login*.xml"))
    merged: Dict[str, Dict[str, Any]] = {}

    for p in login_files[:30]:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rec in _extract_login_records_from_xml(text):
            key = rec.get("login_name", "").upper()
            if not key:
                continue
            row = dict(rec)
            row["source_file"] = str(p)
            merged[key] = row

    return sorted(merged.values(), key=lambda x: x.get("login_name", "").lower())


@router.get("/config-files")
async def list_odi_config_files(root_path: str = Query(default=""), max_files: int = Query(default=300, ge=10, le=2000)):
    root = _resolve_root_path(root_path)
    if not root.exists() or not root.is_dir():
        return {"root_path": str(root), "exists": False, "files": []}

    allowed = {".xml", ".txt", ".properties", ".conf", ".cfg", ".ini", ".log"}
    files: List[Dict[str, Any]] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in allowed:
            continue
        try:
            st = p.stat()
            files.append({
                "name": p.name,
                "path": str(p),
                "relative_path": str(p.relative_to(root)),
                "size": st.st_size,
                "modified": st.st_mtime,
            })
        except Exception:
            continue
        if len(files) >= max_files:
            break

    files.sort(key=lambda x: x["relative_path"].lower())
    return {"root_path": str(root), "exists": True, "files": files}


@router.get("/logins")
async def get_odi_logins(root_path: str = Query(default="")):
    root = _resolve_root_path(root_path)
    rows = _collect_logins(root_path)
    return {"root_path": str(root), "exists": root.exists() and root.is_dir(), "logins": rows}


@router.post("/repository/connect")
async def connect_repository(body: OdiRepoConnectRequest):
    owner_token = (body.owner_token or "").strip()
    login_name = (body.login_name or "").strip()
    if not owner_token:
        raise HTTPException(status_code=400, detail="owner_token is required")
    if not login_name:
        raise HTTPException(status_code=400, detail="login_name is required")

    logins = _collect_logins(body.root_path)
    login = next((row for row in logins if (row.get("login_name") or "").strip().upper() == login_name.upper()), None)
    if not login:
        raise HTTPException(status_code=404, detail=f"Login profile '{login_name}' not found")

    state = {
        "connected": True,
        "connected_at": time.time(),
        "root_path": str(_resolve_root_path(body.root_path)),
        "login_name": login.get("login_name") or "",
        "work_repository": login.get("work_repository") or "",
        "db_url": login.get("db_url") or "",
        "db_user": login.get("db_user") or "",
        "login_user": login.get("login_user") or "",
    }
    _ODI_REPO_CONNECTIONS[owner_token] = state
    key = _repo_key(owner_token=owner_token, login_name=state.get("login_name", ""))
    discovered = _discover_contexts(_resolve_root_path(body.root_path))
    if discovered:
        _ODI_CONTEXT_INDEX_BY_REPO[key] = set(discovered)
        state["contexts"] = sorted(discovered)
    return {"connected": True, "connection": _ODI_REPO_CONNECTIONS[owner_token]}


@router.get("/repository/status")
async def repository_status(owner_token: str = Query(default="")):
    token = (owner_token or "").strip()
    if not token:
        return {"connected": False, "connection": None}
    state = _ODI_REPO_CONNECTIONS.get(token)
    if not state:
        return {"connected": False, "connection": None}
    return {"connected": True, "connection": state}


@router.post("/analyze-files")
async def analyze_odi_files(
    files: List[UploadFile] = File(default=[]),
    owner_token: str = Query(default=""),
    login_name: str = Query(default=""),
):
    if not files:
        return {"files": [], "package_candidates": []}

    all_tokens: List[str] = []
    file_summaries: List[Dict[str, Any]] = []

    for f in files:
        raw = await f.read()
        text = _decode_text(raw[:800_000])
        tokens = _extract_package_name_candidates(text)
        all_tokens.extend(tokens)
        file_summaries.append({
            "name": f.filename or "upload",
            "size": len(raw),
            "candidates_found": min(len(tokens), 100),
        })

    counts = Counter(all_tokens)
    candidates = [name for name, _ in counts.most_common(200)]
    repo_key = _repo_key(owner_token=owner_token, login_name=login_name)
    _index_packages(repo_key, candidates[:500])

    return {"files": file_summaries, "package_candidates": candidates}


@router.get("/contexts")
async def get_odi_contexts(
    owner_token: str = Query(default=""),
    login_name: str = Query(default=""),
    root_path: str = Query(default=""),
):
    token = (owner_token or "").strip()
    state = _ODI_REPO_CONNECTIONS.get(token) if token else None
    resolved_root = _resolve_root_path((state or {}).get("root_path") or root_path)
    repo_key = _repo_key(owner_token=token, login_name=(state or {}).get("login_name") or login_name)

    discovered = _discover_contexts(resolved_root)
    if discovered:
        _ODI_CONTEXT_INDEX_BY_REPO[repo_key] = set(discovered)

    rows = sorted(_ODI_CONTEXT_INDEX_BY_REPO.get(repo_key, set()) | {c.upper() for c in _DEFAULT_CONTEXTS})
    return {
        "owner_token": token,
        "repo_key": repo_key,
        "contexts": rows,
        "root_path": str(resolved_root),
    }


@router.get("/agents")
async def get_odi_agents(owner_token: str = Query(default=""), login_name: str = Query(default="")):
    repo_key = _repo_key(owner_token=owner_token, login_name=login_name)
    execution_agents = set(_DEFAULT_EXECUTION_AGENTS)
    logical_agents = set(_DEFAULT_LOGICAL_AGENTS)

    for s in _ODI_SESSIONS.values():
        if _compact_text(s.get("repo_key", "GLOBAL")) != repo_key:
            continue
        execution = _compact_text(s.get("execution_agent", ""))
        logical = _compact_text(s.get("logical_agent", ""))
        if execution:
            execution_agents.add(execution)
        if logical:
            logical_agents.add(logical)

    return {
        "repo_key": repo_key,
        "execution_agents": sorted(execution_agents),
        "logical_agents": sorted(logical_agents),
    }


@router.get("/packages/search")
async def search_odi_packages(
    q: str = Query(default=""),
    owner_token: str = Query(default=""),
    login_name: str = Query(default=""),
    limit: int = Query(default=120, ge=10, le=500),
):
    query = (q or "").strip().upper()
    repo_key = _repo_key(owner_token=owner_token, login_name=login_name)
    pool = set(_ODI_PACKAGE_INDEX_BY_REPO.get(repo_key, set()))
    if repo_key == "GLOBAL":
        pool.update(_ODI_PACKAGE_INDEX)

    for s in _ODI_SESSIONS.values():
        if _compact_text(s.get("repo_key", "GLOBAL")) != repo_key:
            continue
        name = (s.get("package_name") or "").strip().upper()
        if name:
            pool.add(name)

    rows = sorted(pool)
    if query:
        rows = [name for name in rows if query in name]
    return {"query": query, "repo_key": repo_key, "packages": rows[:limit]}


@router.post("/run")
async def run_odi_package(body: OdiRunRequest):
    package_name = (body.package_name or "").strip()
    if not package_name:
        raise HTTPException(status_code=400, detail="package_name is required")

    session_id = uuid.uuid4().hex[:12]
    owner_token = (body.owner_token or "").strip()
    repo_state = _ODI_REPO_CONNECTIONS.get(owner_token, {}) if owner_token else {}
    repo_connected = bool(repo_state.get("connected"))
    selected_login = (body.login_name or "").strip()
    if not selected_login:
        selected_login = str(repo_state.get("login_name") or "")
    if selected_login and repo_connected:
        repo_connected = (selected_login.upper() == str(repo_state.get("login_name") or "").upper())

    repo_key = _repo_key(owner_token=owner_token, login_name=selected_login)
    _index_packages(repo_key, [package_name])
    session_context = (body.context or "").strip() or "QA"
    session_execution_agent = (body.execution_agent or "").strip() or "Oracle"
    session_logical_agent = (body.logical_agent or "").strip() or "OracleDIAgent (ODI Agent)"
    variables = {str(k): str(v) for k, v in (body.variables or {}).items() if _compact_text(k)}

    session = {
        "session_id": session_id,
        "package_name": package_name,
        "status": "queued",
        "progress": 0,
        "context": session_context,
        "execution_agent": session_execution_agent,
        "logical_agent": session_logical_agent,
        "login_name": selected_login,
        "owner_token": owner_token,
        "repo_key": repo_key,
        "repository_connected": repo_connected,
        "repository_name": str(repo_state.get("login_name") or ""),
        "source": "simulated",
        "variables": variables,
        "created_at": time.time(),
        "started_at": time.time(),
        "ended_at": None,
        "steps": [],
        "errors": [],
        "raw_output": [],
        "cancel_requested": False,
    }
    _ODI_SESSIONS[session_id] = session

    command_template = (body.command_template or os.environ.get("ODI_RUNNER_CMD_TEMPLATE", "")).strip()
    if body.require_real_run and not command_template:
        _append_error(session_id, "Real ODI execution requested but command template is missing")
        session["status"] = "error"
        session["ended_at"] = time.time()
        return {
            "session": _session_summary(session),
            "note": "Provide command_template or ODI_RUNNER_CMD_TEMPLATE for real execution",
        }

    if command_template:
        variable_items = sorted(variables.items(), key=lambda x: x[0].upper())
        variables_cli = " ".join([f'\"{k}={v}\"' for k, v in variable_items])
        command = command_template.format(
            package=package_name,
            context=session["context"],
            execution_agent=session["execution_agent"],
            logical_agent=session["logical_agent"],
            login_name=session["login_name"],
            variables_cli=variables_cli,
            variables_json=json.dumps(variables),
        )
        asyncio.create_task(_run_command_session(session_id, command))
    else:
        asyncio.create_task(_simulate_odi_session(session_id))

    return {"session": _session_summary(session), "note": "Use /api/odi/sessions/{session_id} for live progress"}


@router.get("/sessions")
async def list_odi_sessions(
    owner_token: str = Query(default=""),
    only_mine: bool = Query(default=True),
    name_contains: str = Query(default=""),
    status: str = Query(default=""),
    tracked_only: bool = Query(default=False),
    tracked_session_id: str = Query(default=""),
    limit: int = Query(default=200, ge=10, le=1000),
):
    rows = list(_ODI_SESSIONS.values())
    token = (owner_token or "").strip()
    if only_mine and token:
        rows = [r for r in rows if (r.get("owner_token") or "") == token]

    needle = (name_contains or "").strip().upper()
    if needle:
        rows = [r for r in rows if needle in (r.get("package_name") or "").upper()]

    wanted_status = (status or "").strip().lower()
    if wanted_status:
        rows = [r for r in rows if (r.get("status") or "").lower() == wanted_status]

    if tracked_only:
        tracked = (tracked_session_id or "").strip()
        if tracked:
            rows = [r for r in rows if (r.get("session_id") or "") == tracked]
        else:
            rows = []

    rows.sort(key=lambda x: x.get("started_at", 0), reverse=True)
    return {"sessions": [_session_summary(r) for r in rows[:limit]]}


@router.get("/sessions/{session_id}")
async def get_odi_session(session_id: str):
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": _session_summary(s),
        "steps": s.get("steps", []),
        "errors": s.get("errors", []),
        "raw_output": s.get("raw_output", [])[-200:],
    }


@router.get("/sessions/{session_id}/steps")
async def get_odi_session_steps(session_id: str):
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"steps": s.get("steps", [])}


@router.get("/sessions/{session_id}/errors")
async def get_odi_session_errors(session_id: str):
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"errors": s.get("errors", [])}


@router.post("/sessions/{session_id}/cancel")
async def cancel_odi_session(session_id: str):
    s = _ODI_SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    s["cancel_requested"] = True
    proc = _ODI_SESSION_PROCESSES.get(session_id)
    if proc and proc.returncode is None:
        try:
            proc.terminate()
        except Exception:
            pass
    return {"ok": True, "session_id": session_id, "status": "cancel_requested"}
