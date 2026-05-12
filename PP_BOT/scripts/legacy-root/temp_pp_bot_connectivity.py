from __future__ import annotations

import pathlib
import sys

import requests

sys.path.insert(0, r"PP_BOT")

import config as top_config  # type: ignore
from app.config import settings as app_config  # type: ignore


URLS = [
    ("sharepoint", "https://raymondjamesprod.sharepoint.com/sites/CDSProgram"),
    ("wiki", "https://wiki.rjf.com/"),
]


def resolve_verify_setting() -> str | bool:
    bundle = (app_config.MICROSOFT_CA_BUNDLE or "").strip()
    if app_config.MICROSOFT_VERIFY_SSL and bundle:
        resolved = pathlib.Path(bundle).resolve()
        if resolved.exists():
            return str(resolved)
    return bool(app_config.MICROSOFT_VERIFY_SSL)


def build_headers() -> dict[str, str]:
    token = (getattr(top_config.settings, "SHAREPOINT_BEARER_TOKEN", "") or "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def probe(url: str, headers: dict[str, str], verify: str | bool) -> None:
    print(f"URL: {url}")
    print(f"  headers_present: {bool(headers)}")
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20,
            verify=verify,
            allow_redirects=True,
        )
        print(f"  status_code: {response.status_code}")
        print(f"  final_url: {response.url}")
        print(f"  content_type: {response.headers.get('content-type', '')}")
        snippet = response.text[:240].replace("\r", " ").replace("\n", " ")
        print(f"  body_snippet: {snippet}")
    except Exception as exc:
        print(f"  error: {type(exc).__name__}: {exc}")


def main() -> None:
    verify = resolve_verify_setting()
    headers = build_headers()

    print("TOP_CONFIG")
    print(f"  sharepoint_token_present: {bool((getattr(top_config.settings, 'SHAREPOINT_BEARER_TOKEN', '') or '').strip())}")
    print(f"  sharepoint_client_id: {(getattr(top_config.settings, 'SHAREPOINT_CLIENT_ID', '') or '').strip()}")
    print(f"  sharepoint_tenant_id: {(getattr(top_config.settings, 'SHAREPOINT_TENANT_ID', '') or '').strip()}")
    print(f"  sharepoint_cert_path: {(getattr(top_config.settings, 'SHAREPOINT_CERT_PATH', '') or '').strip()}")
    print(f"  sharepoint_thumbprint: {(getattr(top_config.settings, 'SHAREPOINT_CERT_THUMBPRINT', '') or '').strip()}")

    print("APP_CONFIG")
    print(f"  microsoft_client_id: {app_config.MICROSOFT_CLIENT_ID}")
    print(f"  microsoft_tenant_id: {app_config.MICROSOFT_TENANT_ID}")
    print(f"  microsoft_scopes: {app_config.MICROSOFT_SCOPES}")
    print(f"  microsoft_ca_bundle: {app_config.MICROSOFT_CA_BUNDLE}")
    print(f"  microsoft_verify_ssl: {app_config.MICROSOFT_VERIFY_SSL}")
    print(f"  verify_setting: {verify}")

    for _, url in URLS:
        probe(url, headers, verify)


if __name__ == "__main__":
    main()
