"""Background watchdog for stale/zombie session cleanup."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import settings
from app.routers.odi import sweep_odi_sessions
from app.services.operation_control import sweep_stale_operations


_STATE: Dict[str, Any] = {
    "enabled": False,
    "running": False,
    "last_sweep_at": None,
    "last_result": {},
    "last_error": "",
}
_LOOP_TASK: Optional[asyncio.Task] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sweep_once() -> Dict[str, Any]:
    operation_stats = sweep_stale_operations(
        running_stale_minutes=settings.WATCHDOG_OPERATION_STALE_MINUTES,
        queued_stale_minutes=settings.WATCHDOG_OPERATION_QUEUE_STALE_MINUTES,
        finished_retain_minutes=settings.WATCHDOG_OPERATION_RETAIN_MINUTES,
    )
    odi_stats = sweep_odi_sessions(
        stale_seconds=settings.WATCHDOG_ODI_STALE_SECONDS,
        max_runtime_seconds=settings.WATCHDOG_ODI_MAX_RUNTIME_SECONDS,
        retain_seconds=settings.WATCHDOG_ODI_RETAIN_SECONDS,
    )
    return {
        "operation": operation_stats,
        "odi": odi_stats,
    }


async def _watchdog_loop() -> None:
    global _LOOP_TASK
    _STATE["running"] = True
    _STATE["last_error"] = ""
    try:
        while _STATE.get("enabled"):
            try:
                result = _sweep_once()
                _STATE["last_result"] = result
                _STATE["last_sweep_at"] = _utc_now()
            except Exception as exc:  # Keep watchdog alive even if one sweep fails
                _STATE["last_error"] = str(exc)
            await asyncio.sleep(max(3, int(settings.WATCHDOG_INTERVAL_SECONDS or 15)))
    except asyncio.CancelledError:
        pass
    finally:
        _STATE["running"] = False
        _LOOP_TASK = None


async def start_session_watchdog() -> Dict[str, Any]:
    global _LOOP_TASK
    _STATE["enabled"] = bool(settings.WATCHDOG_ENABLED)
    if not _STATE["enabled"]:
        _STATE["running"] = False
        return get_session_watchdog_status()
    if _LOOP_TASK is None or _LOOP_TASK.done():
        _LOOP_TASK = asyncio.create_task(_watchdog_loop(), name="session-watchdog-loop")
    return get_session_watchdog_status()


async def stop_session_watchdog() -> Dict[str, Any]:
    global _LOOP_TASK
    _STATE["enabled"] = False
    if _LOOP_TASK is not None and not _LOOP_TASK.done():
        _LOOP_TASK.cancel()
        try:
            await _LOOP_TASK
        except asyncio.CancelledError:
            pass
    _LOOP_TASK = None
    _STATE["running"] = False
    return get_session_watchdog_status()


def run_watchdog_sweep_now() -> Dict[str, Any]:
    result = _sweep_once()
    _STATE["last_result"] = result
    _STATE["last_sweep_at"] = _utc_now()
    return result


def get_session_watchdog_status() -> Dict[str, Any]:
    return {
        "enabled": bool(_STATE.get("enabled")),
        "running": bool(_STATE.get("running")),
        "interval_seconds": int(settings.WATCHDOG_INTERVAL_SECONDS or 15),
        "last_sweep_at": _STATE.get("last_sweep_at"),
        "last_result": _STATE.get("last_result") or {},
        "last_error": _STATE.get("last_error") or "",
    }
