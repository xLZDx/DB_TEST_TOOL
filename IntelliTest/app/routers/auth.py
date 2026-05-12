"""Copilot authentication router for IntelliTest."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.copilot_auth import (
    start_device_flow,
    poll_device_flow,
    get_copilot_status,
    logout_copilot,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class CopilotPollInput(BaseModel):
    device_code: str


@router.get("/copilot/status")
async def copilot_status():
    return get_copilot_status()


@router.post("/copilot/device/start")
async def copilot_device_start():
    return await start_device_flow()


@router.post("/copilot/device/poll")
async def copilot_device_poll(body: CopilotPollInput):
    return await poll_device_flow(body.device_code)


@router.post("/copilot/logout")
async def copilot_logout():
    return logout_copilot()
