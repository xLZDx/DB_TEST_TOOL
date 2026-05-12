"""GitHub Copilot device-code authentication service for IntelliTest.

Fully independent implementation — no dependency on db-testing-tool.
Implements device-code OAuth flow against GitHub and exchanges the
GitHub access token for a Copilot session token.
"""
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_runtime_state = {
    "github_access_token": "",
    "copilot_token": "",
    "expires_at": 0,
    "last_error": "",
}

_STATE_FILE = Path.home() / ".intellitest" / "copilot_auth_state.json"


def _save_runtime_state() -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "github_access_token": _runtime_state.get("github_access_token", ""),
            "copilot_token": _runtime_state.get("copilot_token", ""),
            "expires_at": int(_runtime_state.get("expires_at", 0) or 0),
            "last_error": _runtime_state.get("last_error", ""),
        }
        _STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def _load_runtime_state() -> None:
    try:
        if not _STATE_FILE.exists():
            return
        payload = json.loads(_STATE_FILE.read_text(encoding="utf-8") or "{}")
        if isinstance(payload, dict):
            _runtime_state["github_access_token"] = str(payload.get("github_access_token", "") or "")
            _runtime_state["copilot_token"] = str(payload.get("copilot_token", "") or "")
            _runtime_state["expires_at"] = int(payload.get("expires_at", 0) or 0)
            _runtime_state["last_error"] = str(payload.get("last_error", "") or "")
    except Exception:
        pass


_load_runtime_state()


def _http_client_kwargs() -> dict:
    verify: bool | str = settings.GITHUB_VERIFY_SSL
    if settings.GITHUB_CA_BUNDLE:
        verify = settings.GITHUB_CA_BUNDLE
    elif settings.OPENAI_CA_BUNDLE:
        verify = settings.OPENAI_CA_BUNDLE
    elif not settings.OPENAI_VERIFY_SSL:
        verify = False
    return {"timeout": 20.0, "verify": verify, "trust_env": True}


def _friendly_http_error(prefix: str, exc: Exception) -> str:
    message = f"{prefix}: {type(exc).__name__}: {exc}"
    lower = message.lower()
    if "certificate" in lower or "ssl" in lower:
        return (
            f"{prefix}: TLS/SSL error while reaching GitHub. "
            "Set GITHUB_CA_BUNDLE to your corporate root CA path, or set GITHUB_VERIFY_SSL=false temporarily."
        )
    if "timeout" in lower:
        return f"{prefix}: request timed out while contacting GitHub."
    if "connect" in lower or "network" in lower:
        return f"{prefix}: network/proxy error while contacting GitHub."
    return message


async def start_device_flow() -> dict:
    client_id = (settings.GITHUB_OAUTH_CLIENT_ID or "").strip()
    if not client_id:
        return {"error": "GITHUB_OAUTH_CLIENT_ID is not configured. Set it in .env to enable Copilot sign-in."}
    payload = {
        "client_id": client_id,
        "scope": settings.GITHUB_OAUTH_SCOPE or "read:user copilot",
    }
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "IntelliTest"}
    try:
        async with httpx.AsyncClient(**_http_client_kwargs()) as client:
            resp = await client.post("https://github.com/login/device/code", data=payload, headers=headers)
    except Exception as exc:
        err = _friendly_http_error("GitHub device-code request failed", exc)
        _runtime_state["last_error"] = err
        return {"error": err}
    if resp.status_code != 200:
        return {"error": f"GitHub device-code request failed: {resp.status_code} {resp.text}"}
    data = resp.json()
    return {
        "device_code": data.get("device_code", ""),
        "user_code": data.get("user_code", ""),
        "verification_uri": data.get("verification_uri", "https://github.com/login/device"),
        "expires_in": data.get("expires_in", 900),
        "interval": data.get("interval", 5),
    }


async def _exchange_for_copilot_token(github_access_token: str) -> dict:
    headers = {"Authorization": f"token {github_access_token}", "Accept": "application/json", "User-Agent": "IntelliTest"}
    try:
        async with httpx.AsyncClient(**_http_client_kwargs()) as client:
            resp = await client.get("https://api.github.com/copilot_internal/v2/token", headers=headers)
    except Exception as exc:
        err = _friendly_http_error("Copilot token exchange failed", exc)
        _runtime_state["last_error"] = err
        return {"error": err}
    if resp.status_code != 200:
        return {"error": f"Copilot token exchange failed. HTTP {resp.status_code}: {resp.text}"}
    data = resp.json()
    token = data.get("token", "")
    if not token:
        return {"error": "Copilot token exchange succeeded but no token was returned."}
    expires_at_epoch = int(data.get("expires_at", int(time.time()) + 1800))
    _runtime_state["github_access_token"] = github_access_token
    _runtime_state["copilot_token"] = token
    _runtime_state["expires_at"] = expires_at_epoch
    _runtime_state["last_error"] = ""
    _save_runtime_state()
    return {"connected": True, "expires_at": datetime.fromtimestamp(expires_at_epoch, tz=timezone.utc).isoformat()}


async def poll_device_flow(device_code: str) -> dict:
    client_id = (settings.GITHUB_OAUTH_CLIENT_ID or "").strip()
    if not client_id:
        return {"error": "GITHUB_OAUTH_CLIENT_ID is not configured."}
    payload = {
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "IntelliTest"}
    try:
        async with httpx.AsyncClient(**_http_client_kwargs()) as client:
            resp = await client.post("https://github.com/login/oauth/access_token", data=payload, headers=headers)
    except Exception as exc:
        err = _friendly_http_error("GitHub OAuth poll failed", exc)
        _runtime_state["last_error"] = err
        return {"error": err}
    if resp.status_code != 200:
        return {"error": f"GitHub OAuth poll failed: {resp.status_code} {resp.text}"}
    data = resp.json()
    if data.get("error"):
        err = data["error"]
        if err in {"authorization_pending", "slow_down"}:
            return {"status": err}
        if err == "expired_token":
            return {"error": "Device code expired. Start sign-in again."}
        return {"error": f"GitHub OAuth error: {err}"}
    gh_access_token = data.get("access_token", "")
    if not gh_access_token:
        return {"error": "No GitHub access token returned."}
    return await _exchange_for_copilot_token(gh_access_token)


def get_copilot_token() -> str:
    """Return a valid GitHub Copilot session token, auto-refreshing if needed."""
    # 1. Static token from env
    if settings.GITHUBCOPILOT_TOKEN:
        return settings.GITHUBCOPILOT_TOKEN

    # 2. Runtime state (device flow)
    token = _runtime_state.get("copilot_token", "")
    exp = int(_runtime_state.get("expires_at", 0) or 0)
    if token and exp <= int(time.time()):
        gh = (_runtime_state.get("github_access_token") or "").strip()
        if gh:
            try:
                headers = {"Authorization": f"token {gh}", "Accept": "application/json", "User-Agent": "IntelliTest"}
                with httpx.Client(**_http_client_kwargs()) as client:
                    resp = client.get("https://api.github.com/copilot_internal/v2/token", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    refreshed = data.get("token", "")
                    refreshed_exp = int(data.get("expires_at", int(time.time()) + 1800))
                    if refreshed:
                        _runtime_state["copilot_token"] = refreshed
                        _runtime_state["expires_at"] = refreshed_exp
                        _runtime_state["last_error"] = ""
                        _save_runtime_state()
                        token = refreshed
                        exp = refreshed_exp
            except Exception as exc:
                _runtime_state["last_error"] = _friendly_http_error("Copilot auto-refresh failed", exc)
                _save_runtime_state()
    if not token or exp <= int(time.time()):
        return ""
    return token


def get_copilot_status() -> dict:
    token = get_copilot_token()
    connected = bool(token)
    exp = int(_runtime_state.get("expires_at", 0) or 0)
    return {
        "connected": connected,
        "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat() if exp else None,
        "base_url": settings.GITHUBCOPILOT_ENDPOINT or "https://api.githubcopilot.com",
        "model": settings.GITHUBCOPILOT_MODEL or settings.AI_MODEL or settings.OPENAI_MODEL,
        "last_error": _runtime_state.get("last_error", ""),
        "auth_mode": settings.COPILOT_AUTH_MODE or "manual",
    }


def logout_copilot() -> dict:
    _runtime_state["github_access_token"] = ""
    _runtime_state["copilot_token"] = ""
    _runtime_state["expires_at"] = 0
    _runtime_state["last_error"] = ""
    _save_runtime_state()
    return {"connected": False}
