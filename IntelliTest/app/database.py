"""SQLAlchemy engine and session setup (async + sync)."""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

_db_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "IntelliTest"
_db_dir.mkdir(parents=True, exist_ok=True)
_db_path = _db_dir / "app.db"

DATABASE_URL = f"sqlite+aiosqlite:///{_db_path}"

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"timeout": 30})
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
