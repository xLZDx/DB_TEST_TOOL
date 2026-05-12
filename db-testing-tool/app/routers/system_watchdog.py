"""System watchdog endpoints for monitoring and manual sweeps."""

from fastapi import APIRouter

from app.services.session_watchdog import (
    get_session_watchdog_status,
    run_watchdog_sweep_now,
)

router = APIRouter(prefix="/api/system/watchdog", tags=["system-watchdog"])


@router.get("/status")
async def watchdog_status():
    return get_session_watchdog_status()


@router.post("/sweep")
async def watchdog_sweep_now():
    return {
        "status": "ok",
        "result": run_watchdog_sweep_now(),
        "watchdog": get_session_watchdog_status(),
    }
