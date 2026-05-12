"""Credential service – encrypt/decrypt credential profiles using Fernet (AES-128-CBC + HMAC)."""
import base64
import os
from pathlib import Path
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.config import DATA_DIR
from app.models.credential_profile import CredentialProfile

# ── Key management ─────────────────────────────────────────────────────────────
_KEY_FILE = DATA_DIR / ".credential.key"
_fernet = None


def _get_fernet():
    """Lazily initialize Fernet cipher using a persistent key stored in DATA_DIR."""
    global _fernet
    if _fernet is not None:
        return _fernet

    try:
        from cryptography.fernet import Fernet
    except ImportError:
        # cryptography not installed – use a no-op cipher that just base64-encodes.
        class _NoOpFernet:
            def encrypt(self, data: bytes) -> bytes:
                return base64.urlsafe_b64encode(data)

            def decrypt(self, token: bytes) -> bytes:
                return base64.urlsafe_b64decode(token)

        _fernet = _NoOpFernet()
        return _fernet

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if _KEY_FILE.exists():
            key = _KEY_FILE.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            _KEY_FILE.write_bytes(key)
            # Restrict permissions on platforms that support it
            try:
                _KEY_FILE.chmod(0o600)
            except Exception:
                pass

        from cryptography.fernet import Fernet as _Fernet
        _fernet = _Fernet(key)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Failed to initialise credential encryption key: {exc}") from exc

    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string and return a URL-safe base64 token."""
    if not plaintext:
        return ""
    cipher = _get_fernet()
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted token. Returns empty string on failure."""
    if not token:
        return ""
    try:
        cipher = _get_fernet()
        return cipher.decrypt(token.encode()).decode()
    except Exception:
        return ""


# ── CRUD helpers ───────────────────────────────────────────────────────────────

async def list_credential_profiles(db: AsyncSession) -> List[CredentialProfile]:
    result = await db.execute(select(CredentialProfile).order_by(CredentialProfile.name))
    return list(result.scalars().all())


async def get_credential_profile(db: AsyncSession, profile_id: int) -> Optional[CredentialProfile]:
    result = await db.execute(
        select(CredentialProfile).where(CredentialProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def create_credential_profile(
    db: AsyncSession,
    name: str,
    db_type: str = "any",
    username: str = "",
    password: str = "",
    host_hint: str = "",
    notes: str = "",
) -> CredentialProfile:
    profile = CredentialProfile(
        name=name,
        db_type=db_type or "any",
        username=username or None,
        password_enc=encrypt_value(password) if password else None,
        host_hint=host_hint or None,
        notes=notes or None,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_credential_profile(
    db: AsyncSession,
    profile_id: int,
    name: Optional[str] = None,
    db_type: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    host_hint: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[CredentialProfile]:
    profile = await get_credential_profile(db, profile_id)
    if not profile:
        return None
    if name is not None:
        profile.name = name
    if db_type is not None:
        profile.db_type = db_type
    if username is not None:
        profile.username = username
    if password is not None:
        profile.password_enc = encrypt_value(password) if password else None
    if host_hint is not None:
        profile.host_hint = host_hint
    if notes is not None:
        profile.notes = notes
    await db.commit()
    await db.refresh(profile)
    return profile


async def delete_credential_profile(db: AsyncSession, profile_id: int) -> bool:
    profile = await get_credential_profile(db, profile_id)
    if not profile:
        return False
    await db.delete(profile)
    await db.commit()
    return True
