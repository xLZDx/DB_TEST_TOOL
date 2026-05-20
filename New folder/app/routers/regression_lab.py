"""Regression Lab endpoints."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.regression_lab_service import (
    add_exclusions_by_filters,
    get_regression_distinct_values,
    get_regression_settings,
    get_regression_groups,
    get_regression_report,
    list_regression_catalog,
    promote_regression_items_to_local_tests,
    run_search_agent,
    run_validation_agent,
    sync_regression_catalog,
    update_regression_settings,
)

router = APIRouter(prefix="/api/regression-lab", tags=["regression-lab"])


class RegressionSyncRequest(BaseModel):
    project: str
    area_paths: List[str] = Field(default_factory=list)
    iteration_paths: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    suite_name_contains: str = ""
    min_changed_date: Optional[str] = None
    max_cases: int = 400


class RegressionSearchRequest(BaseModel):
    project: str
    query: str
    group: str = ""
    status: str = ""
    area_path: str = ""
    iteration_path: str = ""
    plan_name: str = ""
    suite_name: str = ""
    owner: str = ""
    title: str = ""
    tags: str = ""


class RegressionValidateRequest(BaseModel):
    project: str
    datasource_id: int
    item_ids: List[int] = Field(default_factory=list)


class RegressionPromoteRequest(BaseModel):
    item_ids: List[int]
    source_datasource_id: Optional[int] = None
    target_datasource_id: Optional[int] = None


class RegressionSettingsUpdateRequest(BaseModel):
    default_area_paths: Optional[List[str]] = None
    default_iteration_paths: Optional[List[str]] = None
    exclusion_keywords: Optional[List[str]] = None
    min_changed_date: Optional[str] = None
    include_archived: Optional[bool] = None


class RegressionExcludeByFilterRequest(BaseModel):
    project: str
    mode: str = "item"  # item | suite | plan
    group: str = ""
    status: str = ""
    search_text: str = ""
    area_path: str = ""
    iteration_path: str = ""
    plan_name: str = ""
    suite_name: str = ""
    owner: str = ""
    title: str = ""
    tags: str = ""
    min_changed_date: Optional[str] = None


def _parse_optional_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for candidate in [text, text.replace("Z", "+00:00")]:
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    raise HTTPException(400, f"Invalid date format: {value}")


@router.post("/sync")
async def sync_catalog(body: RegressionSyncRequest, db: AsyncSession = Depends(get_db)):
    if not body.project:
        raise HTTPException(400, "Project is required")
    result = await sync_regression_catalog(
        db,
        project=body.project,
        area_paths=body.area_paths,
        iteration_paths=body.iteration_paths,
        tags=body.tags,
        suite_name_contains=body.suite_name_contains,
        min_changed_date=_parse_optional_date(body.min_changed_date),
        max_cases=max(25, min(body.max_cases, 1500)),
    )
    return result


@router.get("/settings/{project}")
async def get_settings(project: str, db: AsyncSession = Depends(get_db)):
    return await get_regression_settings(db, project=project)


@router.patch("/settings/{project}")
async def patch_settings(project: str, body: RegressionSettingsUpdateRequest, db: AsyncSession = Depends(get_db)):
    return await update_regression_settings(
        db,
        project=project,
        default_area_paths=body.default_area_paths,
        default_iteration_paths=body.default_iteration_paths,
        exclusion_keywords=body.exclusion_keywords,
        min_changed_date=_parse_optional_date(body.min_changed_date),
        include_archived=body.include_archived,
    )


@router.post("/exclusions/by-filters")
async def exclude_by_filters(body: RegressionExcludeByFilterRequest, db: AsyncSession = Depends(get_db)):
    return await add_exclusions_by_filters(
        db,
        project=body.project,
        mode=body.mode,
        group=body.group,
        status=body.status,
        search_text=body.search_text,
        area_path=body.area_path,
        iteration_path=body.iteration_path,
        plan_name=body.plan_name,
        suite_name=body.suite_name,
        owner=body.owner,
        title=body.title,
        tags=body.tags,
        min_changed_date=_parse_optional_date(body.min_changed_date),
    )


@router.get("/catalog/{project}")
async def get_catalog(
    project: str,
    group: str = "",
    status: str = "",
    search_text: str = "",
    area_path: str = "",
    iteration_path: str = "",
    plan_name: str = "",
    suite_name: str = "",
    owner: str = "",
    title: str = "",
    tags: str = "",
    min_changed_date: str = "",
    include_excluded: bool = False,
    db: AsyncSession = Depends(get_db),
):
    items = await list_regression_catalog(
        db,
        project=project,
        group=group,
        status=status,
        search_text=search_text,
        area_path=area_path,
        iteration_path=iteration_path,
        plan_name=plan_name,
        suite_name=suite_name,
        owner=owner,
        title=title,
        tags=tags,
        min_changed_date=_parse_optional_date(min_changed_date),
        include_excluded=include_excluded,
    )
    return {"count": len(items), "items": [
        {
            "id": item.id,
            "project": item.project,
            "plan_id": item.plan_id,
            "plan_name": item.plan_name,
            "suite_id": item.suite_id,
            "suite_name": item.suite_name,
            "suite_path": item.suite_path,
            "test_point_id": item.test_point_id,
            "test_case_id": item.test_case_id,
            "title": item.title,
            "state": item.state,
            "priority": item.priority,
            "owner": item.owner,
            "area_path": item.area_path,
            "iteration_path": item.iteration_path,
            "tags": item.tags,
            "domain_group": item.domain_group,
            "domain_context": item.domain_context,
            "validation_status": item.validation_status,
            "validation_score": item.validation_score,
            "validation_summary": item.validation_summary,
            "test_case_web_url": item.test_case_web_url or "",
            "test_plan_web_url": item.test_plan_web_url or "",
            "test_suite_web_url": item.test_suite_web_url or "",
            "created_date": item.created_date.isoformat() if item.created_date else "",
            "changed_date": item.changed_date.isoformat() if item.changed_date else "",
            "promoted_local_test_count": item.promoted_local_test_count or 0,
        }
        for item in items
    ]}


@router.get("/groups/{project}")
async def get_groups(project: str, db: AsyncSession = Depends(get_db)):
    groups = await get_regression_groups(db, project=project)
    return {"groups": groups}


@router.get("/report/{project}")
async def get_report(project: str, db: AsyncSession = Depends(get_db)):
    return await get_regression_report(db, project=project)


@router.post("/search-agent")
async def search_agent(body: RegressionSearchRequest, db: AsyncSession = Depends(get_db)):
    if not body.query.strip():
        raise HTTPException(400, "Search query is required")
    return await run_search_agent(
        db,
        project=body.project,
        query=body.query,
        group=body.group,
        status=body.status,
        area_path=body.area_path,
        iteration_path=body.iteration_path,
        plan_name=body.plan_name,
        suite_name=body.suite_name,
        owner=body.owner,
        title=body.title,
        tags=body.tags,
    )


@router.post("/validate-agent")
async def validate_agent(body: RegressionValidateRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await run_validation_agent(
            db,
            project=body.project,
            datasource_id=body.datasource_id,
            item_ids=body.item_ids,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/promote")
async def promote_items(body: RegressionPromoteRequest, db: AsyncSession = Depends(get_db)):
    return await promote_regression_items_to_local_tests(
        db,
        item_ids=body.item_ids,
        source_datasource_id=body.source_datasource_id,
        target_datasource_id=body.target_datasource_id,
    )


@router.get("/filters/{project}")
async def get_filters(project: str, filter_text: str = "", db: AsyncSession = Depends(get_db)):
    return await get_regression_distinct_values(db, project=project, filter_text=filter_text)
