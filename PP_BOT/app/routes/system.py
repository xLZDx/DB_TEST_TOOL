"""System and connectivity endpoints for PP_BOT."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ai_service import ai_service, clear_runtime_ai_config, set_runtime_ai_config
from app.services.microsoft_auth_service import (
    clear as clear_microsoft_auth,
    complete_device_flow,
    get_access_token,
    start_device_flow,
    status as microsoft_status,
)

router = APIRouter(tags=["system"])


class AIConnectRequest(BaseModel):
    provider: Optional[str] = Field(default=None, description="AI provider name, e.g. githubcopilot or openai")
    api_key: Optional[str] = Field(default=None, description="API key or token to use at runtime")
    base_url: Optional[str] = Field(default=None, description="OpenAI-compatible base URL")
    model: Optional[str] = Field(default=None, description="Model name to use")
    test_connection: bool = Field(default=True, description="Run a probe after updating the runtime config")


class SourceAccessTestRequest(BaseModel):
    sources: List[str] = Field(default_factory=list, description="HTTP URLs, wiki URLs, SharePoint URLs, or local paths")
    timeout_seconds: int = Field(default=10, ge=3, le=60)


class SourceAccessCheck(BaseModel):
    source: str
    source_type: str = "unknown"
    reachable: bool = False
    access_granted: bool = False
    status_code: Optional[int] = None
    final_url: Optional[str] = None
    elapsed_ms: int = 0
    message: str = ""


class SourceAccessTestResult(BaseModel):
    ok: bool = False
    message: str = ""
    checked_sources: int = 0
    accessible_sources: int = 0
    results: List[SourceAccessCheck] = Field(default_factory=list)


def _classify_source(source: str) -> str:
    text = (source or "").strip().lower()
    if text.startswith("http://") or text.startswith("https://"):
        if "sharepoint" in text:
            return "sharepoint"
        if "wiki" in text or "confluence" in text:
            return "wiki"
        return "web"
    path = Path(source)
    if path.exists() and path.is_dir():
        return "folder"
    if path.exists() and path.is_file():
        return "file"
    if text.startswith("sharepoint://"):
        return "sharepoint"
    if text.startswith("wiki://"):
        return "wiki"
    if text.startswith("file://"):
        return "file"
    return "unknown"


def _http_verify_setting() -> Any:
    bundle = (settings.MICROSOFT_CA_BUNDLE or "").strip()
    if settings.MICROSOFT_VERIFY_SSL and bundle:
        return bundle
    return settings.MICROSOFT_VERIFY_SSL


def _wiki_headers() -> Dict[str, str]:
    token = (settings.WIKI_BEARER_TOKEN or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _is_confluence_login_page(response: httpx.Response) -> bool:
    final_url = str(response.url).lower()
    if "login.action" in final_url:
        return True
    body = (response.text or "").lower()
    return "log in - confluence" in body or "permissionviolation=true" in final_url


def _sharepoint_graph_site_url(source: str) -> Optional[str]:
    parsed = urlparse(source)
    if "sharepoint.com" not in (parsed.netloc or "").lower():
        return None
    site_path = parsed.path.rstrip("/")
    if not site_path:
        return None
    encoded_path = quote(site_path, safe="/")
    return f"https://graph.microsoft.com/v1.0/sites/{parsed.netloc}:{encoded_path}"


async def _probe_sharepoint_source(source: str, timeout_seconds: int) -> SourceAccessCheck:
    token = get_access_token()
    if not token:
        return SourceAccessCheck(
            source=source,
            source_type="sharepoint",
            reachable=True,
            access_granted=False,
            message="SharePoint requires Microsoft sign-in. Start and complete the device-code SSO flow first.",
        )

    graph_url = _sharepoint_graph_site_url(source)
    if not graph_url:
        return SourceAccessCheck(
            source=source,
            source_type="sharepoint",
            reachable=False,
            access_granted=False,
            message="Could not derive a SharePoint site path from the URL.",
        )

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_seconds,
        verify=_http_verify_setting(),
        trust_env=True,
    ) as client:
        try:
            response = await client.get(graph_url, headers=headers)
            if response.status_code >= 400:
                return SourceAccessCheck(
                    source=source,
                    source_type="sharepoint",
                    reachable=True,
                    access_granted=False,
                    status_code=response.status_code,
                    final_url=str(response.url),
                    message=f"Graph returned HTTP {response.status_code}. Check scopes/site permissions.",
                )
            payload = response.json()
            return SourceAccessCheck(
                source=source,
                source_type="sharepoint",
                reachable=True,
                access_granted=True,
                status_code=response.status_code,
                final_url=str(response.url),
                message=f"Authenticated SharePoint access OK: {payload.get('displayName') or payload.get('name') or 'site resolved'}.",
            )
        except Exception as exc:
            return SourceAccessCheck(
                source=source,
                source_type="sharepoint",
                reachable=False,
                access_granted=False,
                message=str(exc),
            )


async def _probe_wiki_source(source: str, timeout_seconds: int) -> SourceAccessCheck:
    headers = _wiki_headers()
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_seconds,
        verify=_http_verify_setting(),
        trust_env=True,
    ) as client:
        try:
            response = await client.get(source, headers=headers)
            if response.status_code >= 400 or _is_confluence_login_page(response):
                return SourceAccessCheck(
                    source=source,
                    source_type="wiki",
                    reachable=True,
                    access_granted=False,
                    status_code=response.status_code,
                    final_url=str(response.url),
                    message="Confluence login page returned. Wiki token is missing, invalid, or insufficient.",
                )
            return SourceAccessCheck(
                source=source,
                source_type="wiki",
                reachable=True,
                access_granted=True,
                status_code=response.status_code,
                final_url=str(response.url),
                message="Authenticated wiki access OK.",
            )
        except Exception as exc:
            return SourceAccessCheck(
                source=source,
                source_type="wiki",
                reachable=False,
                access_granted=False,
                message=str(exc),
            )


async def _probe_http_source(source: str, timeout_seconds: int) -> SourceAccessCheck:
    source_type = _classify_source(source)
    if source_type == "sharepoint":
        return await _probe_sharepoint_source(source, timeout_seconds)
    if source_type == "wiki":
        return await _probe_wiki_source(source, timeout_seconds)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout_seconds,
        verify=_http_verify_setting(),
        trust_env=True,
    ) as client:
        try:
            response = await client.head(source)
            if response.status_code in {405, 501}:
                response = await client.get(source)
            return SourceAccessCheck(
                source=source,
                source_type=source_type,
                reachable=True,
                access_granted=response.status_code < 400,
                status_code=response.status_code,
                final_url=str(response.url),
                message="OK" if response.status_code < 400 else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return SourceAccessCheck(
                source=source,
                source_type=source_type,
                reachable=False,
                access_granted=False,
                message=str(exc),
            )


def _probe_local_source(source: str) -> SourceAccessCheck:
    path = Path(source).expanduser()
    source_type = _classify_source(source)

    if path.exists() and path.is_file():
        return SourceAccessCheck(
            source=source,
            source_type=source_type,
            reachable=True,
            access_granted=True,
            message="Local file is readable.",
        )

    if path.exists() and path.is_dir():
        readable_files = 0
        try:
            for candidate in path.rglob("*"):
                if candidate.is_file():
                    readable_files += 1
                    if readable_files >= 1:
                        break
            return SourceAccessCheck(
                source=source,
                source_type=source_type,
                reachable=True,
                access_granted=readable_files > 0,
                message="Local folder is accessible." if readable_files > 0 else "Folder exists but no readable files were found.",
            )
        except Exception as exc:
            return SourceAccessCheck(
                source=source,
                source_type=source_type,
                reachable=False,
                access_granted=False,
                message=str(exc),
            )

    return SourceAccessCheck(
        source=source,
        source_type=source_type,
        reachable=False,
        access_granted=False,
        message="Path does not exist.",
    )


@router.get("/api/ai/status")
async def ai_status() -> Dict[str, Any]:
    return {"ok": True, "status": ai_service.status()}


@router.post("/api/ai/connect")
async def ai_connect(request: AIConnectRequest) -> Dict[str, Any]:
    set_runtime_ai_config(
        provider=request.provider,
        api_key=request.api_key,
        base_url=request.base_url,
        model=request.model,
    )
    result = ai_service.test_connection() if request.test_connection else {
        "ok": True,
        "connected": False,
        "message": "Runtime AI config updated.",
        "status": ai_service.status(),
    }
    result["runtime_config"] = ai_service.status()
    return result


@router.post("/api/ai/test")
async def ai_test() -> Dict[str, Any]:
    return ai_service.test_connection()


@router.post("/api/ai/clear")
async def ai_clear() -> Dict[str, Any]:
    clear_runtime_ai_config()
    return {"ok": True, "status": ai_service.status(), "message": "Runtime AI config cleared."}


@router.get("/api/microsoft/status")
async def microsoft_auth_status() -> Dict[str, Any]:
    return {"ok": True, "status": microsoft_status()}


@router.post("/api/microsoft/device/start")
async def microsoft_device_start() -> Dict[str, Any]:
    return start_device_flow()


@router.post("/api/microsoft/device/complete")
async def microsoft_device_complete() -> Dict[str, Any]:
    return complete_device_flow()


@router.post("/api/microsoft/clear")
async def microsoft_clear() -> Dict[str, Any]:
    return {"ok": True, "status": clear_microsoft_auth()}


@router.post("/api/source/test")
async def source_test(request: SourceAccessTestRequest) -> SourceAccessTestResult:
    results: List[SourceAccessCheck] = []
    accessible_sources = 0

    for source in request.sources:
        if not source or not source.strip():
            continue
        normalized = source.strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            check = await _probe_http_source(normalized, request.timeout_seconds)
        else:
            check = _probe_local_source(normalized)
        results.append(check)
        if check.access_granted:
            accessible_sources += 1

    ok = bool(results) and accessible_sources == len(results)
    message = "All checked sources are reachable." if ok else "Some sources are not reachable or require access."
    return SourceAccessTestResult(
        ok=ok,
        message=message,
        checked_sources=len(results),
        accessible_sources=accessible_sources,
        results=results,
    )
