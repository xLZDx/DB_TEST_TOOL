"""TestRail API service.

Provides:
- Authentication
- Read projects, suites, sections, test cases
- Create test cases (from generated SQL tests)
- Create test runs and update results
- This implements the TestRail integration from AIRA in Python.
"""
import base64
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    if not settings.TESTRAIL_URL or not settings.TESTRAIL_EMAIL or not settings.TESTRAIL_API_KEY:
        raise ValueError("TestRail not configured (TESTRAIL_URL, TESTRAIL_EMAIL, TESTRAIL_API_KEY required)")
    creds = base64.b64encode(f"{settings.TESTRAIL_EMAIL}:{settings.TESTRAIL_API_KEY}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
    }


def _api_url(path: str) -> str:
    base = settings.TESTRAIL_URL.rstrip("/")
    return f"{base}/index.php?/api/v2/{path.lstrip('/')}"


# ── Projects ──────────────────────────────────────────────────────────────

async def list_projects() -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url("get_projects"), headers=_headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
    return data if isinstance(data, list) else data.get("projects", [])


async def get_project(project_id: int) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url(f"get_project/{project_id}"), headers=_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()


# ── Suites ────────────────────────────────────────────────────────────────

async def list_suites(project_id: int) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url(f"get_suites/{project_id}"), headers=_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else []
            return []


# ── Sections ──────────────────────────────────────────────────────────────

async def list_sections(project_id: int, suite_id: Optional[int] = None) -> List[Dict[str, Any]]:
    url = f"get_sections/{project_id}"
    if suite_id:
        url += f"&suite_id={suite_id}"
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url(url), headers=_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else data.get("sections", [])
            return []


async def add_section(project_id: int, name: str, suite_id: Optional[int] = None,
                      parent_id: Optional[int] = None, description: str = "") -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name}
    if suite_id:
        payload["suite_id"] = suite_id
    if parent_id:
        payload["parent_id"] = parent_id
    if description:
        payload["description"] = description
    async with aiohttp.ClientSession() as s:
        async with s.post(_api_url(f"add_section/{project_id}"),
                          headers=_headers(), json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


# ── Test Cases ────────────────────────────────────────────────────────────

async def get_test_cases(project_id: int, suite_id: Optional[int] = None,
                          section_id: Optional[int] = None) -> List[Dict[str, Any]]:
    url = f"get_cases/{project_id}"
    params = []
    if suite_id:
        params.append(f"suite_id={suite_id}")
    if section_id:
        params.append(f"section_id={section_id}")
    if params:
        url += "&" + "&".join(params)
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url(url), headers=_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else data.get("cases", [])
            return []


async def add_test_case(section_id: int, title: str,
                         custom_steps: str = "",
                         custom_expected: str = "",
                         type_id: int = 1,  # 1=Automated
                         priority_id: int = 2,  # 2=Medium
                         refs: str = "") -> Dict[str, Any]:
    """Create a new test case in TestRail.

    For SQL validation tests, we put the SQL queries in custom_steps and
    the expected validation result in custom_expected.
    """
    payload: Dict[str, Any] = {
        "title": title,
        "type_id": type_id,
        "priority_id": priority_id,
        "custom_steps": custom_steps,
        "custom_expected": custom_expected,
    }
    if refs:
        payload["refs"] = refs
    async with aiohttp.ClientSession() as s:
        async with s.post(_api_url(f"add_case/{section_id}"),
                          headers=_headers(), json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def bulk_add_test_cases(section_id: int,
                               test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bulk-add test cases to a section. Returns list of created cases."""
    results = []
    for tc in test_cases:
        try:
            result = await add_test_case(
                section_id=section_id,
                title=tc.get("title", tc.get("name", "Unnamed Test")),
                custom_steps=tc.get("source_query", tc.get("sql", "")),
                custom_expected=tc.get("expected_result", "0 mismatches"),
                refs=tc.get("refs", tc.get("jira_key", "")),
            )
            results.append(result)
        except Exception as e:
            logger.error("Failed to add TestRail case '%s': %s", tc.get("title"), e)
    return results


# ── Test Runs ─────────────────────────────────────────────────────────────

async def add_run(project_id: int, name: str,
                   suite_id: Optional[int] = None,
                   case_ids: Optional[List[int]] = None,
                   description: str = "",
                   milestone_id: Optional[int] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"name": name}
    if suite_id:
        payload["suite_id"] = suite_id
    if case_ids is not None:
        payload["include_all"] = False
        payload["case_ids"] = case_ids
    else:
        payload["include_all"] = True
    if description:
        payload["description"] = description
    if milestone_id:
        payload["milestone_id"] = milestone_id

    async with aiohttp.ClientSession() as s:
        async with s.post(_api_url(f"add_run/{project_id}"),
                          headers=_headers(), json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def close_run(run_id: int) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as s:
        async with s.post(_api_url(f"close_run/{run_id}"), headers=_headers(), json={}) as resp:
            resp.raise_for_status()
            return await resp.json()


async def add_results_for_cases(run_id: int,
                                  results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Post test results for a run.

    results: list of {case_id, status_id (1=Passed,5=Failed), comment, elapsed}
    """
    payload = {"results": results}
    async with aiohttp.ClientSession() as s:
        async with s.post(_api_url(f"add_results_for_cases/{run_id}"),
                          headers=_headers(), json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


# ── Milestones & Plans ────────────────────────────────────────────────────

async def list_milestones(project_id: int) -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as s:
        async with s.get(_api_url(f"get_milestones/{project_id}"), headers=_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data if isinstance(data, list) else data.get("milestones", [])
            return []
