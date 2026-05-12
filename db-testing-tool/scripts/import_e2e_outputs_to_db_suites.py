import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import async_session
from app.models.test_case import TestCase, TestFolder, TestCaseFolder


async def _get_or_create_folder(folder_name: str) -> TestFolder:
    async with async_session() as db:
        existing = await db.execute(select(TestFolder).where(TestFolder.name == folder_name))
        folder = existing.scalar_one_or_none()
        if folder:
            return folder

        folder = TestFolder(name=folder_name)
        db.add(folder)
        await db.commit()
        await db.refresh(folder)
        return folder


async def _insert_tests(folder_id: int, tests: List[Dict[str, Any]], source_ds_id: int, target_ds_id: int) -> int:
    inserted = 0
    async with async_session() as db:
        for i, t in enumerate(tests, start=1):
            name = (t.get("name") or f"Imported E2E Test {i}").strip()
            tc = TestCase(
                name=name,
                test_type=(t.get("test_type") or "custom_sql").strip(),
                source_datasource_id=source_ds_id,
                target_datasource_id=target_ds_id,
                source_query=(t.get("source_query") or "").strip(),
                target_query=(t.get("target_query") or "").strip() or None,
                expected_result=str(t.get("expected_result") or "0"),
                severity=(t.get("severity") or "medium").strip(),
                is_active=True,
                is_ai_generated=True,
                description=(t.get("description") or "Imported from E2E batch output").strip(),
            )
            db.add(tc)
            await db.flush()
            db.add(TestCaseFolder(test_case_id=tc.id, folder_id=folder_id))
            inserted += 1

        await db.commit()

    return inserted


def _load_tests_json(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import E2E output tests.json files into DB test suites (folders)")
    parser.add_argument("--run-folder", required=True, help="Absolute or relative path to e2e batch run folder")
    parser.add_argument("--source-ds", type=int, default=2, help="Source datasource id")
    parser.add_argument("--target-ds", type=int, default=2, help="Target datasource id")
    args = parser.parse_args()

    run_folder = Path(args.run_folder)
    if not run_folder.is_absolute():
        run_folder = (ROOT / run_folder).resolve()

    summary_path = run_folder / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary.json not found: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_tag = run_folder.name

    print(f"Importing run: {run_folder}")
    total = 0

    for item in summary:
        scenario = item.get("scenario")
        scenario_folder = run_folder / scenario
        tests_path = scenario_folder / "tests.json"
        if not tests_path.exists():
            print(f"[SKIP] {scenario}: tests.json missing")
            continue

        tests = _load_tests_json(tests_path)
        suite_name = f"E2E_{run_tag}_{scenario}"
        folder = await _get_or_create_folder(suite_name)
        inserted = await _insert_tests(folder.id, tests, args.source_ds, args.target_ds)
        total += inserted
        print(f"[OK] {scenario}: inserted={inserted}, suite={suite_name}")

    print(f"Done. Total inserted test cases: {total}")


if __name__ == "__main__":
    asyncio.run(main())
