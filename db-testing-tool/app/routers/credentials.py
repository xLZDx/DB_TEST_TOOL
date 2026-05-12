"""Credentials API router – CRUD for named credential profiles."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import credential_service

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CredentialProfileCreate(BaseModel):
    name: str
    db_type: str = "any"
    username: Optional[str] = None
    password: Optional[str] = None
    host_hint: Optional[str] = None
    notes: Optional[str] = None


class CredentialProfileUpdate(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    host_hint: Optional[str] = None
    notes: Optional[str] = None


class CredentialProfileOut(BaseModel):
    id: int
    name: str
    db_type: str
    username: Optional[str] = None
    host_hint: Optional[str] = None
    notes: Optional[str] = None
    has_password: bool = False

    class Config:
        from_attributes = True


class CredentialProfileInject(BaseModel):
    """Safe payload to pre-fill a datasource form (includes decrypted password once)."""
    id: int
    name: str
    db_type: str
    username: Optional[str] = None
    password: Optional[str] = None
    host_hint: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_out(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "db_type": profile.db_type or "any",
        "username": profile.username,
        "host_hint": profile.host_hint,
        "notes": profile.notes,
        "has_password": bool(profile.password_enc),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    profiles = await credential_service.list_credential_profiles(db)
    return [_to_out(p) for p in profiles]


@router.post("", status_code=201)
async def create_profile(body: CredentialProfileCreate, db: AsyncSession = Depends(get_db)):
    try:
        profile = await credential_service.create_credential_profile(
            db,
            name=body.name.strip(),
            db_type=body.db_type or "any",
            username=body.username or "",
            password=body.password or "",
            host_hint=body.host_hint or "",
            notes=body.notes or "",
        )
        return _to_out(profile)
    except Exception as exc:
        if "UNIQUE constraint" in str(exc) or "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"A credential profile named '{body.name}' already exists.")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{profile_id}")
async def get_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    profile = await credential_service.get_credential_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Credential profile not found")
    return _to_out(profile)


@router.get("/{profile_id}/inject")
async def inject_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    """Returns decrypted credentials for use in a pre-fill operation (UI only, no logging).
    
    REMOVED for security: This endpoint previously returned plaintext passwords.
    Client-side encryption/secure storage should be used instead.
    """
    raise HTTPException(status_code=410, detail="This endpoint has been removed for security reasons. Plaintext passwords cannot be returned via HTTP.")


@router.put("/{profile_id}")
async def update_profile(profile_id: int, body: CredentialProfileUpdate, db: AsyncSession = Depends(get_db)):
    profile = await credential_service.update_credential_profile(
        db,
        profile_id,
        name=body.name,
        db_type=body.db_type,
        username=body.username,
        password=body.password,
        host_hint=body.host_hint,
        notes=body.notes,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Credential profile not found")
    return _to_out(profile)


@router.delete("/{profile_id}")
async def delete_profile(profile_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await credential_service.delete_credential_profile(db, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential profile not found")
    return {"deleted": True}
