"""Copilot authentication service stub."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_runtime_copilot_token() -> Optional[str]:
    """Stub: get Copilot runtime token."""
    logger.warning("Copilot auth service: stub (returning None)")
    return None


async def start_device_flow() -> Dict[str, Any]:
    """Stub: start OAuth device-code flow."""
    logger.warning("start_device_flow: stub (not configured)")
    return {
        "status": "not_configured",
        "message": "Copilot device-flow authentication is not yet configured on this instance.",
    }


async def complete_device_flow(device_code: str) -> Dict[str, Any]:
    """Stub: poll for device-flow token."""
    logger.warning("complete_device_flow: stub (not configured)")
    return {
        "status": "not_configured",
        "message": "Copilot device-flow authentication is not yet configured on this instance.",
    }


async def get_copilot_token(force_refresh: bool = False) -> Optional[str]:
    """Stub: return cached/refreshed Copilot token."""
    logger.warning("get_copilot_token: stub (returning None)")
    return None


async def poll_device_flow(device_code: str) -> Dict[str, Any]:
    """Stub: poll for device-code flow result."""
    logger.warning("poll_device_flow: stub (not configured)")
    return {
        "status": "not_configured",
        "message": "Copilot device-flow authentication is not yet configured on this instance.",
    }


def get_copilot_status() -> Dict[str, Any]:
    """Stub: return current Copilot auth status."""
    return {"authenticated": False, "status": "not_configured", "stub": True}


def logout_copilot() -> Dict[str, Any]:
    """Stub: clear Copilot session."""
    return {"status": "ok", "message": "No active Copilot session (stub)."}
