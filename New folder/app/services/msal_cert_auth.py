"""
MSAL certificate-based token acquisition for SharePoint/Graph (long-term solution)
"""
import msal
from app.config import settings
from pathlib import Path
import threading

_token_cache = {
    "access_token": None,
    "expires_at": 0,
}
_token_lock = threading.Lock()

def get_certificate_token(force_refresh=False):
    import time
    if not hasattr(settings, "SHAREPOINT_CERT_PATH") or not settings.SHAREPOINT_CERT_PATH:
        raise RuntimeError("SHAREPOINT_CERT_PATH not configured in settings.")
    if not hasattr(settings, "SHAREPOINT_CERT_THUMBPRINT") or not settings.SHAREPOINT_CERT_THUMBPRINT:
        raise RuntimeError("SHAREPOINT_CERT_THUMBPRINT not configured in settings.")
    if not hasattr(settings, "SHAREPOINT_CLIENT_ID") or not settings.SHAREPOINT_CLIENT_ID:
        raise RuntimeError("SHAREPOINT_CLIENT_ID not configured in settings.")
    if not hasattr(settings, "SHAREPOINT_TENANT_ID") or not settings.SHAREPOINT_TENANT_ID:
        raise RuntimeError("SHAREPOINT_TENANT_ID not configured in settings.")
    
    authority = f"https://login.microsoftonline.com/{settings.SHAREPOINT_TENANT_ID}"
    scope = ["https://graph.microsoft.com/.default"]  # Or SharePoint scope
    cert_path = Path(settings.SHAREPOINT_CERT_PATH)
    thumbprint = settings.SHAREPOINT_CERT_THUMBPRINT
    client_id = settings.SHAREPOINT_CLIENT_ID
    
    now = int(time.time())
    with _token_lock:
        if (
            not force_refresh
            and _token_cache["access_token"]
            and _token_cache["expires_at"] > now + 60
        ):
            return _token_cache["access_token"]
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential={
                "private_key": cert_path.read_text(),
                "thumbprint": thumbprint,
            },
        )
        result = app.acquire_token_for_client(scopes=scope)
        if "access_token" in result:
            _token_cache["access_token"] = result["access_token"]
            _token_cache["expires_at"] = now + int(result.get("expires_in", 3600))
            return result["access_token"]
        else:
            raise RuntimeError(f"Failed to acquire token: {result}")
