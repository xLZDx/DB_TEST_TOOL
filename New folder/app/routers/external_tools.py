"""External desktop tool launcher endpoints (Windows-focused)."""
from __future__ import annotations

import os
import re
import subprocess
import urllib.error
import urllib.request
import io
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import BASE_DIR, settings

router = APIRouter(prefix="/api/external-tools", tags=["external-tools"])

_ALLOWED_TOOLS = {"odi", "sqldeveloper"}

# Track only processes started by this app instance.
_launched_processes: Dict[str, subprocess.Popen] = {}
_runtime_config_paths: Dict[str, str] = {
    "odi": (settings.ODI_STUDIO_PATH or "").strip(),
    "sqldeveloper": (settings.SQLDEVELOPER_PATH or "").strip(),
}
_runtime_stream_urls: Dict[str, str] = {
    "odi": (settings.ODI_STREAM_URL or "").strip(),
    "sqldeveloper": (settings.SQLDEVELOPER_STREAM_URL or "").strip(),
}


def _stream_tool_label(tool: str) -> str:
    return "ODI" if tool == "odi" else "SQL Developer"


class LaunchToolBody(BaseModel):
    tool: str
    path: Optional[str] = None
    args: Optional[str] = ""


class StopToolBody(BaseModel):
    tool: str


class SaveToolConfigBody(BaseModel):
    odi_path: Optional[str] = ""
    sqldeveloper_path: Optional[str] = ""
    odi_stream_url: Optional[str] = ""
    sqldeveloper_stream_url: Optional[str] = ""


def _tool_label(tool: str) -> str:
    return "ODI Studio" if tool == "odi" else "SQL Developer"


def _default_path_for_tool(tool: str) -> str:
    runtime = (_runtime_config_paths.get(tool) or "").strip()
    if runtime:
        return runtime
    if tool == "odi":
        return settings.ODI_STUDIO_PATH or ""
    if tool == "sqldeveloper":
        return settings.SQLDEVELOPER_PATH or ""
    return ""


def _default_stream_url_for_tool(tool: str) -> str:
    runtime = (_runtime_stream_urls.get(tool) or "").strip()
    if runtime:
        return runtime
    if tool == "odi":
        return settings.ODI_STREAM_URL or ""
    if tool == "sqldeveloper":
        return settings.SQLDEVELOPER_STREAM_URL or ""
    return ""


def _builtin_stream_url_for_tool(tool: str) -> str:
    return f"/api/external-tools/live/mjpeg?tool={tool}"


def _resolved_stream_url_for_tool(tool: str, url: str = "") -> tuple[str, str]:
    manual = _validate_stream_url(url or "")
    if manual:
        return manual, "manual"

    configured = _default_stream_url_for_tool(tool)
    if configured:
        return configured, "configured"

    return _builtin_stream_url_for_tool(tool), "builtin-mjpeg"


def _absolute_stream_check_url(request: Request, candidate: str) -> str:
    if candidate.startswith("/"):
        return str(request.base_url).rstrip("/") + candidate
    return candidate


def _validate_stream_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise HTTPException(400, "Stream URL must start with http:// or https://")
    if not parsed.netloc:
        raise HTTPException(400, "Invalid stream URL")
    return value


def _env_file_path() -> Path:
    return BASE_DIR / ".env"


def _write_env_updates(updates: Dict[str, str]) -> None:
    env_path = _env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    else:
        lines = []

    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
    remaining = dict(updates)
    out_lines = []

    for line in lines:
        match = pattern.match(line)
        if not match:
            out_lines.append(line)
            continue
        key = match.group(1)
        if key in remaining:
            value = remaining.pop(key)
            out_lines.append(f"{key}={value}")
        else:
            out_lines.append(line)

    if remaining:
        if out_lines and out_lines[-1].strip():
            out_lines.append("")
        out_lines.append("# External tools")
        for key, value in remaining.items():
            out_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")


def _normalize_path(raw: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser((raw or "").strip().strip('"')))
    return Path(expanded)


def _validate_tool(tool: str) -> str:
    normalized = (tool or "").strip().lower()
    if normalized not in _ALLOWED_TOOLS:
        raise HTTPException(400, f"Unsupported tool: {tool}")
    return normalized


def _validate_executable(path: Path) -> None:
    if not path.exists():
        raise HTTPException(400, f"Executable not found: {path}")
    if path.is_dir():
        raise HTTPException(400, f"Path is a directory, expected executable file: {path}")
    if path.suffix.lower() not in {".exe", ".bat", ".cmd"}:
        raise HTTPException(400, f"Unsupported executable type: {path.suffix}")


def _build_launch_command(path: Path, args: str) -> list[str]:
    safe_args = (args or "").strip()
    if path.suffix.lower() in {".bat", ".cmd"}:
        if safe_args:
            return ["cmd", "/c", str(path), *safe_args.split()]
        return ["cmd", "/c", str(path)]
    if safe_args:
        return [str(path), *safe_args.split()]
    return [str(path)]


def _is_running(proc: Optional[subprocess.Popen]) -> bool:
    return bool(proc) and proc.poll() is None


def _status_for_tool(tool: str) -> dict:
    configured_path = _default_path_for_tool(tool)
    configured_exists = False
    if configured_path:
        try:
            configured_exists = _normalize_path(configured_path).exists()
        except Exception:
            configured_exists = False

    proc = _launched_processes.get(tool)
    running = _is_running(proc)

    return {
        "tool": tool,
        "label": _tool_label(tool),
        "configured_path": configured_path,
        "configured_exists": configured_exists,
        "running": running,
        "pid": (proc.pid if running else None),
    }


@router.get("/status")
async def get_status():
    return {
        "tools": [
            _status_for_tool("odi"),
            _status_for_tool("sqldeveloper"),
        ]
    }


@router.get("/detect")
async def detect_common_install_paths():
    candidates = {
        "odi": [
            r"C:\Oracle\Middleware\Oracle_Home\odi\studio\odi.exe",
            r"C:\Oracle\Middleware\Oracle_Home\odi\studio\odi.bat",
            r"C:\Oracle\Middleware\odi\studio\odi.exe",
            r"C:\Oracle\Middleware\odi\studio\odi.bat",
        ],
        "sqldeveloper": [
            r"C:\sqldeveloper\sqldeveloper.exe",
            r"C:\sqldeveloper\sqldeveloper64W.exe",
            r"C:\Program Files\sqldeveloper\sqldeveloper.exe",
            r"C:\Program Files\sqldeveloper\sqldeveloper64W.exe",
            r"C:\Tools\sqldeveloper\sqldeveloper.exe",
            r"C:\Tools\sqldeveloper\sqldeveloper64W.exe",
        ],
    }

    result = {}
    for tool, paths in candidates.items():
        found = []
        for raw in paths:
            p = Path(raw)
            if p.exists():
                found.append(str(p))
        result[tool] = found

    return result


@router.get("/config")
async def get_tool_config():
    return {
        "odi_path": _default_path_for_tool("odi"),
        "sqldeveloper_path": _default_path_for_tool("sqldeveloper"),
        "odi_stream_url": _default_stream_url_for_tool("odi"),
        "sqldeveloper_stream_url": _default_stream_url_for_tool("sqldeveloper"),
        "env_file": str(_env_file_path()),
    }


@router.post("/config/save")
async def save_tool_config(body: SaveToolConfigBody):
    """REMOVED for security: This endpoint allowed modifying what executables get launched.
    
    Host configuration endpoints have been disabled. Local tool launching must be
    configured securely through environment variables by system administrators only.
    """
    raise HTTPException(status_code=410, detail="This endpoint has been removed for security reasons. Host tool configuration cannot be modified via HTTP.")


@router.get("/stream/check")
async def check_stream(request: Request, tool: str = "", url: str = ""):
    normalized_tool = _validate_tool(tool or "")
    candidate, source = _resolved_stream_url_for_tool(normalized_tool, url or "")
    if source == "builtin-mjpeg":
        result = _probe_builtin_stream(normalized_tool)
        return {
            **result,
            "tool": normalized_tool,
            "url": candidate,
            "source": source,
        }

    probe_url = _absolute_stream_check_url(request, candidate)

    req = urllib.request.Request(probe_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            return {
                "ok": status < 400,
                "tool": normalized_tool,
                "url": candidate,
                "source": source,
                "status_code": status,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "tool": normalized_tool,
            "url": candidate,
            "source": source,
            "status_code": int(getattr(exc, "code", 0) or 0),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "tool": normalized_tool,
            "url": candidate,
            "source": source,
            "status_code": 0,
            "error": str(exc),
        }


@router.get("/stream/default-url")
async def get_default_stream_url(tool: str = ""):
    normalized_tool = _validate_tool(tool or "")
    resolved, source = _resolved_stream_url_for_tool(normalized_tool)
    return {
        "tool": normalized_tool,
        "url": resolved,
        "source": source,
    }


def _mjpeg_frame_generator(tool: str):
    # Lazy import so the app still starts even if ImageGrab is unavailable.
    try:
        from PIL import ImageGrab
    except Exception:
        err = b"--frame\r\nContent-Type: text/plain\r\n\r\nPillow ImageGrab is not available\r\n"
        yield err
        return

    label = _stream_tool_label(tool)
    while True:
        try:
            img = ImageGrab.grab(all_screens=True)
            # Keep bandwidth moderate for browser streaming.
            img.thumbnail((1600, 900))

            bio = io.BytesIO()
            img.save(bio, format="JPEG", quality=65, optimize=True)
            frame = bio.getvalue()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"X-Stream-Tool: " + label.encode("utf-8", errors="ignore") + b"\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.35)
        except GeneratorExit:
            break
        except Exception as exc:
            msg = f"{label} stream error: {exc}".encode("utf-8", errors="ignore")
            yield b"--frame\r\nContent-Type: text/plain\r\n\r\n" + msg + b"\r\n"
            time.sleep(1.0)


def _probe_builtin_stream(tool: str) -> dict:
    label = _stream_tool_label(tool)
    try:
        from PIL import ImageGrab
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 503,
            "error": f"Pillow ImageGrab unavailable: {exc}",
            "detail": f"{label} local desktop capture is unavailable",
        }

    try:
        img = ImageGrab.grab(all_screens=True)
        img.thumbnail((320, 180))
        bio = io.BytesIO()
        img.save(bio, format="JPEG", quality=30, optimize=True)
        return {
            "ok": True,
            "status_code": 200,
            "detail": f"{label} local desktop capture is available",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 503,
            "error": str(exc),
            "detail": f"{label} local desktop capture failed",
        }


@router.get("/live/mjpeg")
async def live_mjpeg(tool: str = ""):
    normalized_tool = _validate_tool(tool or "")
    return StreamingResponse(
        _mjpeg_frame_generator(normalized_tool),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/launch")
async def launch_tool(body: LaunchToolBody):
    """REMOVED for security: This endpoint allowed launching arbitrary executables.
    
    Host process launching has been disabled via HTTP API. Local tools must be
    started manually or through secure administrative channels only.
    """
    raise HTTPException(status_code=410, detail="This endpoint has been removed for security reasons. Process launching is not available via HTTP.")


@router.post("/stop")
async def stop_tool(body: StopToolBody):
    """REMOVED for security: This endpoint allowed terminating processes.
    
    Process control has been disabled via HTTP API.
    """
    raise HTTPException(status_code=410, detail="This endpoint has been removed for security reasons. Process control is not available via HTTP.")
