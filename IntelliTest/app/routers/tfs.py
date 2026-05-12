"""TFS / Azure DevOps router for IntelliTest."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/tfs", tags=["tfs"])


@router.get("/config")
async def get_config():
    from app.config import settings
    return {
        "configured": bool(settings.TFS_BASE_URL and settings.TFS_PAT),
        "base_url": settings.TFS_BASE_URL,
        "projects": settings.get_tfs_projects(),
    }


@router.get("/work-item/{item_id}")
async def get_work_item(item_id: int, project: str = ""):
    from app.services.tfs_service import fetch_work_item_context
    try:
        return await fetch_work_item_context(item_id, project=project)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# Alias used by frontend
@router.get("/work-item-context/{item_id}")
async def get_work_item_context(item_id: int, project: str = "", refresh: str = ""):
    from app.services.tfs_service import fetch_work_item_context
    try:
        return await fetch_work_item_context(item_id, project=project)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/work-item-full-context/{item_id}")
async def get_work_item_full_context(item_id: int, project: str = ""):
    """Fetch work item + download all attachment text content."""
    from app.services.tfs_service import fetch_work_item_full_context
    try:
        return await fetch_work_item_full_context(item_id, project=project)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/projects")
async def list_tfs_projects():
    from app.services.tfs_service import list_projects
    try:
        projects = await list_projects()
        return {"projects": projects}
    except Exception as e:
        # Fall back to configured project list
        from app.config import settings
        return {"projects": settings.get_tfs_projects()}


class WiqlRequest(BaseModel):
    query: str
    project: str = ""
    max_results: int = 50


@router.post("/wiql")
async def wiql_query(body: WiqlRequest):
    from app.services.tfs_service import run_wiql
    try:
        items = await run_wiql(body.project, body.query, body.max_results)
        return {"items": items, "count": len(items)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/query")
async def wiql_query_legacy(body: WiqlRequest):
    """Legacy alias for /wiql."""
    return await wiql_query(body)
