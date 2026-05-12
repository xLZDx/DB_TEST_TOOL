import asyncio
from sqlalchemy import select, func
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import async_session
from app.models.test_case import TestFolder, TestCaseFolder


async def main() -> None:
    prefix = "E2E_20260428_084316_"
    async with async_session() as db:
        folders = (await db.execute(
            select(TestFolder).where(TestFolder.name.like(f"{prefix}%")).order_by(TestFolder.name.asc())
        )).scalars().all()

        if not folders:
            print("No matching folders found")
            return

        for f in folders:
            count = (await db.execute(
                select(func.count()).select_from(TestCaseFolder).where(TestCaseFolder.folder_id == f.id)
            )).scalar_one()
            print(f"{f.id}\t{f.name}\t{count}")


if __name__ == "__main__":
    asyncio.run(main())
