"""CredentialProfile model – named credential sets (passwords stored encrypted)."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime, timezone
from app.database import Base


class CredentialProfile(Base):
    __tablename__ = "credential_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    db_type = Column(String(50), nullable=False, default="any")   # any | oracle | redshift | sqlserver
    username = Column(String(200), nullable=True)
    password_enc = Column(Text, nullable=True)       # Fernet-encrypted
    host_hint = Column(String(500), nullable=True)   # optional host/DSN hint
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
