"""Microsoft device-code authentication helpers for PP_BOT."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import msal
import requests

from app.config import settings


DEFAULT_PUBLIC_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"


@dataclass
class MicrosoftAuthState:
    access_token: str = ""
    account_username: str = ""
    tenant_id: str = ""
    scopes: List[str] | None = None
    last_message: str = ""
    last_device_flow: Optional[Dict[str, Any]] = None


_auth_state = MicrosoftAuthState(scopes=[])


def _authority() -> str:
    configured = settings.MICROSOFT_AUTHORITY.strip()
    if configured:
        return configured
    tenant = (settings.MICROSOFT_TENANT_ID or "common").strip()
    return f"https://login.microsoftonline.com/{tenant}"


def _client_id() -> str:
    configured = settings.MICROSOFT_CLIENT_ID.strip()
    if configured:
        return configured
    return DEFAULT_PUBLIC_CLIENT_ID


def _scopes() -> List[str]:
    raw = (settings.MICROSOFT_SCOPES or "").strip()
    return [item for item in raw.split() if item]


def _ca_bundle() -> str | None:
    value = (settings.MICROSOFT_CA_BUNDLE or "").strip()
    return value or None


def _bearer_token() -> str:
    value = (getattr(settings, "SHAREPOINT_BEARER_TOKEN", "") or "").strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    return value


def _verify_ssl() -> bool:
    return bool(settings.MICROSOFT_VERIFY_SSL)


def _verify_value() -> str | bool:
    bundle = _ca_bundle()
    if _verify_ssl() and bundle:
        resolved = Path(bundle).resolve()
        if resolved.exists():
            os.environ["REQUESTS_CA_BUNDLE"] = str(resolved)
            os.environ["SSL_CERT_FILE"] = str(resolved)
            return str(resolved)
    if _verify_ssl():
        return True
    if getattr(settings, "MICROSOFT_ALLOW_INSECURE_SSL", False):
        return False
    return False


def _build_http_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = True
    session.verify = _verify_value()
    return session


def _build_app() -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=_client_id(),
        authority=_authority(),
        http_client=_build_http_session(),
    )


def status() -> Dict[str, Any]:
    bearer_token = _bearer_token()
    return {
        "authenticated": bool(_auth_state.access_token or bearer_token),
        "username": _auth_state.account_username,
        "tenant_id": _auth_state.tenant_id,
        "client_id": _client_id(),
        "authority": _authority(),
        "scopes": list(_auth_state.scopes or []),
        "has_device_flow": bool(_auth_state.last_device_flow),
        "has_bearer_token": bool(bearer_token),
        "message": _auth_state.last_message or ("SharePoint bearer token loaded." if bearer_token else ""),
        "using_default_public_client": not bool(settings.MICROSOFT_CLIENT_ID.strip()),
        "ca_bundle": _ca_bundle(),
        "verify_ssl": _verify_ssl(),
    }


def clear() -> Dict[str, Any]:
    _auth_state.access_token = ""
    _auth_state.account_username = ""
    _auth_state.tenant_id = ""
    _auth_state.scopes = []
    _auth_state.last_message = "Authentication state cleared."
    _auth_state.last_device_flow = None
    return status()


def start_device_flow() -> Dict[str, Any]:
    app = _build_app()
    scopes = _scopes()
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise RuntimeError(flow.get("error_description") or "Failed to start Microsoft device-code flow.")
    _auth_state.last_device_flow = flow
    _auth_state.scopes = scopes
    _auth_state.last_message = flow.get("message", "Device-code flow started.")
    return {
        "ok": True,
        "message": flow.get("message", ""),
        "user_code": flow.get("user_code", ""),
        "verification_uri": flow.get("verification_uri", ""),
        "expires_in": flow.get("expires_in", 0),
        "interval": flow.get("interval", 5),
        "status": status(),
    }


def complete_device_flow() -> Dict[str, Any]:
    flow = _auth_state.last_device_flow
    if not flow:
        raise RuntimeError("No active Microsoft device-code flow. Start one first.")
    app = _build_app()
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        description = result.get("error_description") or result.get("error") or "Microsoft login failed."
        _auth_state.last_message = description
        return {
            "ok": False,
            "message": description,
            "status": status(),
            "raw": {
                "error": result.get("error"),
                "suberror": result.get("suberror"),
                "correlation_id": result.get("correlation_id"),
            },
        }
    _auth_state.access_token = result["access_token"]
    _auth_state.account_username = ((result.get("id_token_claims") or {}).get("preferred_username") or "")
    _auth_state.tenant_id = ((result.get("id_token_claims") or {}).get("tid") or "")
    _auth_state.last_message = "Microsoft authentication successful."
    return {
        "ok": True,
        "message": _auth_state.last_message,
        "status": status(),
    }


def get_access_token() -> str:
    return _auth_state.access_token or _bearer_token()
