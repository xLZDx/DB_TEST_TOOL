"""Jira API router for IntelliTest."""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/jira", tags=["jira"])


@router.get("/config")
async def get_config():
    from app.config import settings
    return {
        "configured": bool(settings.JIRA_BASE_URL and settings.JIRA_EMAIL and settings.JIRA_API_TOKEN),
        "base_url": settings.JIRA_BASE_URL,
        "default_project": settings.JIRA_DEFAULT_PROJECT,
    }


@router.get("/projects")
async def list_projects():
    from app.services.jira_service import list_projects
    try:
        return {"projects": await list_projects()}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/issue/{issue_key}")
async def get_issue(issue_key: str):
    from app.services.jira_service import get_issue
    try:
        return await get_issue(issue_key.upper())
    except ValueError as e:
        raise HTTPException(400, str(e))


class JqlRequest(BaseModel):
    jql: str
    max_results: int = 50


@router.post("/search")
async def search_issues(body: JqlRequest):
    from app.services.jira_service import search_issues
    try:
        return {"issues": await search_issues(body.jql, body.max_results)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/issue/{issue_key}/attachment/{attachment_id}")
async def get_attachment_text(issue_key: str, attachment_id: str,
                               content_url: str = "", mime_type: str = ""):
    from app.services.jira_service import download_attachment_text
    if not content_url:
        raise HTTPException(400, "content_url query param required")
    try:
        text = await download_attachment_text(content_url, mime_type)
        return {"text": text, "length": len(text)}
    except Exception as e:
        raise HTTPException(500, str(e))
