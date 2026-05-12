"""TestRail router for IntelliTest."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/testrail", tags=["testrail"])


@router.get("/config")
async def get_config():
    from app.config import settings
    return {
        "configured": bool(settings.TESTRAIL_URL and settings.TESTRAIL_EMAIL and settings.TESTRAIL_API_KEY),
        "url": settings.TESTRAIL_URL,
        "default_project_id": settings.TESTRAIL_DEFAULT_PROJECT_ID,
    }


@router.get("/projects")
async def list_projects():
    from app.services.testrail_service import list_projects
    try:
        return {"projects": await list_projects()}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/projects/{project_id}/suites")
async def list_suites(project_id: int):
    from app.services.testrail_service import list_suites
    return {"suites": await list_suites(project_id)}


@router.get("/projects/{project_id}/sections")
async def list_sections(project_id: int, suite_id: Optional[int] = None):
    from app.services.testrail_service import list_sections
    return {"sections": await list_sections(project_id, suite_id)}


@router.get("/projects/{project_id}/suites/{suite_id}/sections")
async def list_sections_by_suite(project_id: int, suite_id: int):
    from app.services.testrail_service import list_sections
    return {"sections": await list_sections(project_id, suite_id)}


class AddSectionRequest(BaseModel):
    name: str
    description: str = ""
    suite_id: Optional[int] = None
    parent_id: Optional[int] = None


@router.post("/projects/{project_id}/sections")
async def add_section(project_id: int, body: AddSectionRequest):
    from app.services.testrail_service import add_section
    try:
        result = await add_section(project_id, body.name, body.suite_id, body.parent_id, body.description)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/projects/{project_id}/suites/{suite_id}/sections")
async def add_section_by_suite(project_id: int, suite_id: int, body: AddSectionRequest):
    from app.services.testrail_service import add_section
    try:
        result = await add_section(project_id, body.name, suite_id, body.parent_id, body.description)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


class BulkAddCasesRequest(BaseModel):
    section_id: Optional[int] = None
    test_cases: Optional[List[dict]] = None
    tests: Optional[List[dict]] = None  # frontend alias for test_cases
    project_id: Optional[int] = None
    suite_id: Optional[int] = None
    milestone_id: Optional[int] = None

    def get_cases(self) -> List[dict]:
        return self.test_cases or self.tests or []


@router.post("/cases/bulk")
async def bulk_add_test_cases_new(body: BulkAddCasesRequest):
    """Bulk-add generated test cases to TestRail."""
    return await _bulk_add_cases(body)


@router.post("/bulk-add-cases")
async def bulk_add_test_cases(body: BulkAddCasesRequest):
    """Bulk-add generated test cases to TestRail. Used after AI test generation."""
    return await _bulk_add_cases(body)


async def _bulk_add_cases(body: BulkAddCasesRequest):
    from app.services.testrail_service import bulk_add_test_cases
    cases = body.get_cases()
    section_id = body.section_id or 0
    if not section_id:
        return {"ok": True, "created": 0, "message": "No section_id provided — use TestrRail Sync page"}
    try:
        results = await bulk_add_test_cases(section_id, cases)
        return {"ok": True, "created": len(results), "cases": results}
    except Exception as e:
        raise HTTPException(500, str(e))


class AddRunRequest(BaseModel):
    project_id: int
    name: str
    suite_id: Optional[int] = None
    case_ids: Optional[List[int]] = None
    description: str = ""


@router.post("/runs")
async def create_run(body: AddRunRequest):
    from app.services.testrail_service import add_run
    try:
        result = await add_run(body.project_id, body.name, body.suite_id, body.case_ids, body.description)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/milestones/{project_id}")
async def list_milestones_legacy(project_id: int):
    from app.services.testrail_service import list_milestones
    return {"milestones": await list_milestones(project_id)}


@router.get("/projects/{project_id}/milestones")
async def list_milestones_by_project(project_id: int):
    from app.services.testrail_service import list_milestones
    return {"milestones": await list_milestones(project_id)}
