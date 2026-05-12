"""Watchdog behavior tests for stale/zombie session cleanup."""

from datetime import datetime, timedelta, timezone

from app.routers import odi
from app.services import operation_control
from app.services.session_watchdog import run_watchdog_sweep_now


def test_watchdog_stops_stale_operation_session():
    op_id = "watchdog_test_stale_op"
    operation_control.register_operation(op_id, "analyze")

    # Force this operation to look stale.
    state = operation_control._OPERATIONS[op_id]
    stale_dt = datetime.now(timezone.utc) - timedelta(minutes=999)
    state["status"] = "running"
    state["updated_at"] = stale_dt
    state["started_at"] = stale_dt

    stats = operation_control.sweep_stale_operations(
        running_stale_minutes=20,
        queued_stale_minutes=30,
        finished_retain_minutes=120,
    )

    assert stats["stale_stopped"] >= 1
    assert operation_control._OPERATIONS[op_id]["status"] == "stopped"
    assert operation_control._OPERATIONS[op_id]["stop_requested"] is True


def test_watchdog_prunes_old_finished_operation_session():
    op_id = "watchdog_test_old_finished"
    operation_control.register_operation(op_id, "analyze")
    state = operation_control._OPERATIONS[op_id]
    old_dt = datetime.now(timezone.utc) - timedelta(minutes=999)
    state["status"] = "completed"
    state["finished_at"] = old_dt
    state["updated_at"] = old_dt

    stats = operation_control.sweep_stale_operations(
        running_stale_minutes=20,
        queued_stale_minutes=30,
        finished_retain_minutes=10,
    )

    assert stats["pruned"] >= 1
    assert op_id not in operation_control._OPERATIONS


def test_watchdog_marks_stale_odi_session_as_killed():
    session_id = "odi_stale_watchdog"
    now = datetime.now(timezone.utc).timestamp()
    stale = now - 9999
    odi._ODI_SESSIONS[session_id] = {
        "session_id": session_id,
        "package_name": "PKG_DEMO",
        "status": "running",
        "progress": 10,
        "context": "QA",
        "execution_agent": "Oracle",
        "logical_agent": "OracleDIAgent",
        "created_at": stale,
        "started_at": stale,
        "ended_at": None,
        "steps": [],
        "errors": [],
        "raw_output": [],
        "cancel_requested": False,
    }

    stats = odi.sweep_odi_sessions(stale_seconds=60, max_runtime_seconds=600, retain_seconds=3600)

    assert stats["killed_stale"] >= 1
    assert odi._ODI_SESSIONS[session_id]["status"] == "killed_stale"
    assert odi._ODI_SESSIONS[session_id]["cancel_requested"] is True


def test_watchdog_prunes_old_terminal_odi_session():
    session_id = "odi_old_terminal"
    now = datetime.now(timezone.utc).timestamp()
    old = now - 9999
    odi._ODI_SESSIONS[session_id] = {
        "session_id": session_id,
        "package_name": "PKG_OLD",
        "status": "success",
        "progress": 100,
        "created_at": old,
        "started_at": old,
        "ended_at": old,
        "steps": [],
        "errors": [],
        "raw_output": [],
        "cancel_requested": False,
    }

    stats = odi.sweep_odi_sessions(stale_seconds=60, max_runtime_seconds=600, retain_seconds=120)

    assert stats["pruned"] >= 1
    assert session_id not in odi._ODI_SESSIONS


def test_watchdog_manual_sweep_returns_both_domains():
    result = run_watchdog_sweep_now()
    assert "operation" in result
    assert "odi" in result
    assert "active" in result["operation"]
    assert "active_sessions" in result["odi"]
