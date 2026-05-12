"""TFS / Azure DevOps service for IntelliTest.

Provides read access to work items, attachments, and hyperlinks.
Adapted from db-testing-tool/app/services/tfs_service.py but standalone
(no SQLAlchemy dependency — uses direct HTTP calls only).
"""
import base64
import logging
import re
from typing import Any, Dict, List, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    token = base64.b64encode(f":{settings.TFS_PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def _get_projects() -> List[str]:
    return settings.get_tfs_projects()


def _api_url(path: str, project: Optional[str] = None) -> str:
    base = settings.TFS_BASE_URL.rstrip("/")
    collection = settings.TFS_COLLECTION
    proj = project or (_get_projects()[0] if _get_projects() else "")
    return f"{base}/{collection}/{proj}/_apis/{path}"


def _html_to_text(html_content: str) -> str:
    if not html_content:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(html_content))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Work Item Context ──────────────────────────────────────────────────────

async def fetch_work_item_context(item_id: int, project: str = "") -> Dict[str, Any]:
    """Fetch a TFS work item with full field expansion, attachments, and hyperlinks."""
    if not settings.TFS_BASE_URL or not settings.TFS_PAT:
        raise ValueError("TFS not configured (TFS_BASE_URL / TFS_PAT missing)")

    proj = project or (_get_projects()[0] if _get_projects() else "")
    url = _api_url(f"wit/workitems/{item_id}?$expand=all&api-version=7.0", project=proj)

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(), ssl=False) as resp:
            if resp.status == 404:
                raise ValueError(f"Work item {item_id} not found in '{proj}'")
            if not resp.ok:
                body = await resp.text()
                raise ValueError(f"TFS HTTP {resp.status}: {body[:200]}")
            data = await resp.json()

    fields = data.get("fields", {})
    assigned_raw = fields.get("System.AssignedTo", "")
    assigned_to = (
        assigned_raw.get("displayName", "") if isinstance(assigned_raw, dict)
        else str(assigned_raw)
    )

    result: Dict[str, Any] = {
        "id": item_id,
        "work_item_type": fields.get("System.WorkItemType", ""),
        "title": fields.get("System.Title", ""),
        "state": fields.get("System.State", ""),
        "description_html": fields.get("System.Description", ""),
        "description_text": _html_to_text(fields.get("System.Description", "")),
        "acceptance_criteria": _html_to_text(
            fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
        ),
        "tags": fields.get("System.Tags", ""),
        "assigned_to": assigned_to,
        "area_path": fields.get("System.AreaPath", ""),
        "iteration_path": fields.get("System.IterationPath", ""),
        "priority": fields.get("Microsoft.VSTS.Common.Priority", None),
        "attachments": [],
        "hyperlinks": [],
    }

    for rel in data.get("relations", []):
        rel_type = rel.get("rel", "")
        attrs = rel.get("attributes", {})
        rel_url = rel.get("url", "")
        if rel_type == "AttachedFile":
            result["attachments"].append({
                "name": attrs.get("name", "attachment"),
                "url": rel_url,
                "size": attrs.get("resourceSize", 0),
            })
        elif rel_type == "Hyperlink":
            result["hyperlinks"].append({
                "url": rel_url,
                "comment": attrs.get("comment", ""),
            })

    # Extract embedded URLs from description HTML
    desc_html = fields.get("System.Description", "") or ""
    for m in re.finditer(r'href="([^"]+)"', desc_html):
        link = m.group(1)
        if link not in [h["url"] for h in result["hyperlinks"]]:
            result["hyperlinks"].append({"url": link, "comment": "(embedded in description)"})

    return result


async def download_tfs_attachment(attachment_url: str) -> bytes:
    """Download a TFS attachment by its API URL. Returns raw bytes."""
    if not settings.TFS_PAT:
        raise ValueError("TFS not configured")
    async with aiohttp.ClientSession() as session:
        async with session.get(attachment_url, headers=_headers(), ssl=False) as resp:
            if not resp.ok:
                raise ValueError(f"Failed to download attachment: HTTP {resp.status}")
            return await resp.read()


async def download_tfs_attachment_text(attachment_url: str, filename: str = "") -> str:
    """Download a TFS attachment and extract text content."""
    raw = await download_tfs_attachment(attachment_url)
    lower = filename.lower()
    try:
        if lower.endswith((".txt", ".sql", ".csv", ".json", ".xml", ".md", ".log")):
            return raw.decode("utf-8", errors="replace")
        if lower.endswith((".xlsx", ".xls")):
            import io, openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            lines = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                lines.append(f"\n=== Sheet: {sheet_name} ===")
                for row in ws.iter_rows(values_only=True):
                    vals = [str(c) if c is not None else "" for c in row]
                    lines.append(" | ".join(vals))
            wb.close()
            return "\n".join(lines)
        if lower.endswith(".msg"):
            text = raw.decode("utf-8", errors="replace")
            cleaned = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
            cleaned = re.sub(r' {3,}', '  ', cleaned)
            return cleaned[:8000]
        return raw.decode("utf-8", errors="replace")[:8000]
    except Exception as e:
        return f"[Could not extract text from {filename}: {e}]"


async def fetch_work_item_full_context(item_id: int, project: str = "") -> dict:
    """Enhanced: fetches work item + downloads all attachment text content."""
    context = await fetch_work_item_context(item_id, project)
    for att in context.get("attachments", []):
        try:
            text = await download_tfs_attachment_text(att["url"], att.get("name", ""))
            att["content_text"] = text
        except Exception as e:
            att["content_text"] = f"[Download failed: {e}]"
    return context


# ── WIQL ──────────────────────────────────────────────────────────────────

async def run_wiql(project: str, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """Execute a WIQL query and return work item summaries."""
    url = _api_url("wit/wiql?api-version=7.0", project=project)
    payload = {"query": query}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=_headers(), json=payload, ssl=False) as resp:
            if not resp.ok:
                body = await resp.text()
                raise ValueError(f"WIQL error {resp.status}: {body[:200]}")
            wiql_result = await resp.json()

    work_item_refs = wiql_result.get("workItems", [])[:max_results]
    if not work_item_refs:
        return []

    ids = [str(wi["id"]) for wi in work_item_refs]
    fields_url = _api_url(
        f"wit/workitems?ids={','.join(ids)}&fields=System.Id,System.Title,"
        "System.WorkItemType,System.State,System.AssignedTo,Microsoft.VSTS.Common.Priority"
        "&api-version=7.0",
        project=project,
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(fields_url, headers=_headers(), ssl=False) as resp:
            if not resp.ok:
                return [{"id": int(r["id"])} for r in work_item_refs]
            batch = await resp.json()

    results = []
    for wi in batch.get("value", []):
        f = wi.get("fields", {})
        assigned = f.get("System.AssignedTo", {})
        results.append({
            "id": wi.get("id"),
            "title": f.get("System.Title", ""),
            "type": f.get("System.WorkItemType", ""),
            "state": f.get("System.State", ""),
            "assigned_to": assigned.get("displayName", "") if isinstance(assigned, dict) else str(assigned),
            "priority": f.get("Microsoft.VSTS.Common.Priority"),
        })
    return results


# ── Projects ──────────────────────────────────────────────────────────────

def list_projects() -> List[str]:
    return _get_projects()
