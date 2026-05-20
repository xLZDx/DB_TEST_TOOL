"""Local AI agent profile management endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_profile import AgentProfile

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    role: str
    domains: Optional[str] = ""
    system_prompt: str
    is_active: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    domains: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentProfile).order_by(AgentProfile.name))
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "domains": a.domains or "",
            "system_prompt": a.system_prompt,
            "is_active": bool(a.is_active),
            "updated_at": str(a.updated_at) if a.updated_at else None,
        }
        for a in agents
    ]


@router.post("")
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(AgentProfile).where(AgentProfile.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Agent with this name already exists")

    item = AgentProfile(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": item.id, "created": True}


@router.put("/{agent_id}")
async def update_agent(agent_id: int, body: AgentUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(AgentProfile, agent_id)
    if not item:
        raise HTTPException(404, "Agent not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"updated": True}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(AgentProfile, agent_id)
    if not item:
        raise HTTPException(404, "Agent not found")

    await db.delete(item)
    await db.commit()
    return {"deleted": True}


@router.post("/seed-defaults")
async def seed_default_agents(db: AsyncSession = Depends(get_db)):
    defaults = [
        {
            "name": "Business Analyst",
            "role": "business-analyst",
            "domains": "requirements,mapping,acceptance-criteria",
            "system_prompt": "Derive business intent, edge cases, and acceptance criteria from mapping rules and source/target semantics.",
        },
        {
            "name": "SQL/PLSQL Developer",
            "role": "developer",
            "domains": "sql,plsql,query-optimization,etl",
            "system_prompt": "Produce production-grade SQL/PLSQL with clear assumptions, efficient filtering, and database-specific correctness.",
        },
        {
            "name": "Product Owner",
            "role": "product-owner",
            "domains": "prioritization,scope,mvp,outcomes",
            "system_prompt": "Prioritize by business value, scope the smallest viable increment, and keep deliverables testable.",
        },
        {
            "name": "QA Tester",
            "role": "tester",
            "domains": "test-design,data-quality,regression",
            "system_prompt": "Generate high-value test cases that verify transformation logic, counts, null handling, and reconciliation outcomes.",
        },
        {
            "name": "Regression Search Agent",
            "role": "regression-search",
            "domains": "tfs,test-cases,search,regression,attachments,pbi-context",
            "system_prompt": "Find the best regression candidates by reading indexed TFS test cases, steps, expected results, tags, area/iteration paths, and attachment content. Rank candidates by business fit and reuse quality.",
        },
        {
            "name": "Regression Validation Agent",
            "role": "regression-validation",
            "domains": "pdm,sql-validation,lineage,joins,schemas,columns,regression",
            "system_prompt": "Validate indexed regression SQL against the current PDM/schema catalog, detect missing tables or columns, and rank each test for regression reuse with a clear pass/partial/fail rationale.",
        },
    ]

    created = 0
    for row in defaults:
        existing = await db.execute(select(AgentProfile).where(AgentProfile.name == row["name"]))
        if existing.scalar_one_or_none():
            continue
        db.add(AgentProfile(**row, is_active=True))
        created += 1

    await db.commit()
    return {"created": created}
