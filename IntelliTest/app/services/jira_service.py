"""Jira REST API service.

Python port of AIRA's Jira integration (originally in PowerShell + Aira.JiraText.psm1).
Provides:
- Authentication via API token
- Read issues (PBIs, Stories, Bugs, Epics) with full field expansion
- Download attachments
- Execute JQL queries
- Extract plain text from Atlassian Document Format (ADF) or Jira Wiki Markup
"""
import base64
import re
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> Dict[str, str]:
    """Build Jira Basic Auth headers from configured credentials."""
    email = settings.JIRA_EMAIL
    token = settings.JIRA_API_TOKEN
    if not email or not token:
        raise ValueError("Jira not configured (JIRA_EMAIL and JIRA_API_TOKEN required)")
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _api_url(path: str) -> str:
    base = settings.JIRA_BASE_URL.rstrip("/")
    return f"{base}/rest/api/3/{path.lstrip('/')}"


# ── Text extraction (port of Aira.JiraText.psm1) ──────────────────────────

def adf_to_text(node: Any, _depth: int = 0) -> str:
    """Recursively convert Atlassian Document Format (ADF) node to plain text.
    Port of AIRA's Convert-JiraContentToText PowerShell function."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text_parts = []
        # Direct text node
        if "text" in node:
            text_parts.append(str(node["text"]))
        # Recurse into content nodes
        for child in node.get("content", []):
            text_parts.append(adf_to_text(child, _depth + 1))
        # Add newlines after block types
        node_type = node.get("type", "")
        joined = " ".join(t for t in text_parts if t.strip())
        if node_type in ("paragraph", "heading", "codeBlock", "blockquote", "listItem", "bulletList", "orderedList"):
            return joined + "\n"
        return joined
    if isinstance(node, list):
        return "\n".join(adf_to_text(n, _depth + 1) for n in node if n)
    return str(node)


def wiki_to_text(wiki: str) -> str:
    """Convert Jira Wiki Markup to plain text (simplified).
    Port of AIRA's Convert-JiraWikiToMarkdown PowerShell function."""
    if not wiki:
        return ""
    text = wiki
    # Remove formatting marks
    text = re.sub(r'\*([^*]+)\*', r'\1', text)       # bold
    text = re.sub(r'_([^_]+)_', r'\1', text)          # italic
    text = re.sub(r'\+([^+]+)\+', r'\1', text)        # underline
    text = re.sub(r'\?\?([^?]+)\?\?', r'\1', text)    # citation
    text = re.sub(r'-([^-]+)-', r'\1', text)          # strikethrough
    text = re.sub(r'\^([^^]+)\^', r'\1', text)        # superscript
    text = re.sub(r'~([^~]+)~', r'\1', text)          # subscript
    text = re.sub(r'\{\{([^}]+)\}\}', r'\1', text)    # monospace
    # Headers
    text = re.sub(r'^h[1-6]\. ', '', text, flags=re.MULTILINE)
    # Table separators
    text = re.sub(r'\|\|', ' | ', text)
    text = re.sub(r'\|', ' | ', text)
    # Links [text|url] or [url]
    text = re.sub(r'\[([^|\]]+)\|[^\]]+\]', r'\1', text)
    text = re.sub(r'\[[^\]]+\]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_description_text(desc_field: Any) -> str:
    """Extract plain text from a Jira description field (handles ADF or wiki string)."""
    if not desc_field:
        return ""
    if isinstance(desc_field, str):
        return wiki_to_text(desc_field)
    if isinstance(desc_field, dict):
        return adf_to_text(desc_field).strip()
    return str(desc_field)


# ── Issue reading ──────────────────────────────────────────────────────────

async def get_issue(issue_key: str) -> Dict[str, Any]:
    """Fetch a single Jira issue with all fields, comments, and attachments."""
    url = _api_url(f"issue/{issue_key}?expand=renderedFields,names,changelog&fields=*all")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(), ssl=settings.OPENAI_VERIFY_SSL) as resp:
            if resp.status == 404:
                raise ValueError(f"Jira issue '{issue_key}' not found")
            if not resp.ok:
                body = await resp.text()
                raise ValueError(f"Jira returned HTTP {resp.status}: {body[:200]}")
            raw = await resp.json()

    return _normalize_issue(raw)


def _normalize_issue(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw Jira issue API response into a flat, useful structure."""
    fields = raw.get("fields", {})
    key = raw.get("key", "")
    issue_id = raw.get("id", "")

    # Description
    desc_raw = fields.get("description") or fields.get("renderedFields", {}).get("description", "")
    description_text = extract_description_text(desc_raw)

    # Acceptance criteria (custom field — common field name)
    ac_field = None
    for fname in ("customfield_10016", "customfield_10014", "customfield_10018",
                  "customfield_11001", "customfield_11002"):
        if fname in fields and fields[fname]:
            ac_field = fields[fname]
            break
    acceptance_criteria = extract_description_text(ac_field) if ac_field else ""

    # Reporter / Assignee
    reporter = (fields.get("reporter") or {}).get("displayName", "")
    assignee = (fields.get("assignee") or {}).get("displayName", "")

    # Status / Priority / Labels
    status = (fields.get("status") or {}).get("name", "")
    priority = (fields.get("priority") or {}).get("name", "")
    labels = fields.get("labels", [])

    # Story points (common custom fields)
    story_points = None
    for sp_field in ("story_points", "customfield_10016", "customfield_10028"):
        if sp_field in fields and isinstance(fields[sp_field], (int, float)):
            story_points = fields[sp_field]
            break

    # Sprint
    sprints: List[str] = []
    for sprint_field in ("customfield_10020", "customfield_10018"):
        val = fields.get(sprint_field)
        if val and isinstance(val, list):
            for s in val:
                if isinstance(s, dict) and s.get("name"):
                    sprints.append(s["name"])
            break

    # Attachments
    attachments = []
    for att in fields.get("attachment", []):
        attachments.append({
            "id": att.get("id", ""),
            "filename": att.get("filename", ""),
            "content_url": att.get("content", ""),
            "mime_type": att.get("mimeType", ""),
            "size": att.get("size", 0),
            "author": (att.get("author") or {}).get("displayName", ""),
        })

    # Linked issues
    links = []
    for link in fields.get("issuelinks", []):
        linked = link.get("outwardIssue") or link.get("inwardIssue") or {}
        link_type = (link.get("type") or {}).get("name", "")
        direction = "outward" if "outwardIssue" in link else "inward"
        if linked:
            links.append({
                "type": link_type,
                "direction": direction,
                "key": linked.get("key", ""),
                "summary": (linked.get("fields") or {}).get("summary", ""),
                "status": ((linked.get("fields") or {}).get("status") or {}).get("name", ""),
            })

    # Comments
    comments = []
    comment_data = (fields.get("comment") or {}).get("comments", [])
    for c in comment_data[:10]:  # limit to last 10
        body_text = extract_description_text(c.get("body") or "")
        comments.append({
            "author": (c.get("author") or {}).get("displayName", ""),
            "body": body_text,
            "created": c.get("created", ""),
        })

    return {
        "key": key,
        "id": issue_id,
        "summary": fields.get("summary", ""),
        "issue_type": (fields.get("issuetype") or {}).get("name", ""),
        "status": status,
        "priority": priority,
        "assignee": assignee,
        "reporter": reporter,
        "labels": labels,
        "story_points": story_points,
        "sprints": sprints,
        "description_text": description_text,
        "acceptance_criteria": acceptance_criteria,
        "attachments": attachments,
        "linked_issues": links,
        "comments": comments,
        "project": (fields.get("project") or {}).get("key", ""),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
    }


# ── JQL Search ────────────────────────────────────────────────────────────

async def search_issues(jql: str, max_results: int = 50,
                        fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Execute a JQL query and return a list of normalized issue summaries."""
    default_fields = ["summary", "status", "issuetype", "assignee", "priority",
                      "labels", "attachment", "description"]
    url = _api_url("search")
    payload = {
        "jql": jql,
        "maxResults": min(max_results, 100),
        "fields": fields or default_fields,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=_headers(), json=payload,
                                ssl=settings.OPENAI_VERIFY_SSL) as resp:
            if not resp.ok:
                body = await resp.text()
                raise ValueError(f"Jira JQL error {resp.status}: {body[:200]}")
            raw = await resp.json()
    return [_normalize_issue_summary(i) for i in raw.get("issues", [])]


def _normalize_issue_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight normalization for JQL search results."""
    fields = raw.get("fields", {})
    return {
        "key": raw.get("key", ""),
        "summary": fields.get("summary", ""),
        "issue_type": (fields.get("issuetype") or {}).get("name", ""),
        "status": (fields.get("status") or {}).get("name", ""),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "assignee": (fields.get("assignee") or {}).get("displayName", ""),
        "has_attachments": len(fields.get("attachment", [])) > 0,
    }


# ── Projects ──────────────────────────────────────────────────────────────

async def list_projects() -> List[Dict[str, Any]]:
    """Return all Jira projects accessible to the configured user."""
    url = _api_url("project?expand=description")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_headers(), ssl=settings.OPENAI_VERIFY_SSL) as resp:
            if not resp.ok:
                raise ValueError(f"Jira projects error {resp.status}")
            raw = await resp.json()
    return [
        {"key": p.get("key", ""), "name": p.get("name", ""),
         "type": p.get("projectTypeKey", ""), "id": p.get("id", "")}
        for p in (raw if isinstance(raw, list) else [])
    ]


# ── Attachment Download ───────────────────────────────────────────────────

async def download_attachment_text(content_url: str, mime_type: str = "") -> str:
    """Download a Jira attachment and return its text content (best-effort)."""
    if not content_url:
        return ""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(content_url, headers=_headers(),
                                   ssl=settings.OPENAI_VERIFY_SSL) as resp:
                if not resp.ok:
                    return f"[Could not download: HTTP {resp.status}]"
                raw = await resp.read()

        filename_hint = content_url.split("/")[-1].split("?")[0].lower()
        return _bytes_to_text(raw, filename_hint, mime_type)
    except Exception as e:
        logger.warning("Attachment download failed: %s", e)
        return f"[Download error: {e}]"


def _bytes_to_text(raw: bytes, filename: str, mime_type: str) -> str:
    """Best-effort text extraction from attachment bytes."""
    if filename.endswith(".csv") or "text/csv" in mime_type:
        return raw.decode("utf-8", errors="replace")
    if filename.endswith(".txt") or filename.endswith(".md"):
        return raw.decode("utf-8", errors="replace")
    if filename.endswith(".sql"):
        return raw.decode("utf-8", errors="replace")
    if filename.endswith(".json"):
        return raw.decode("utf-8", errors="replace")
    if filename.endswith(".xml"):
        return raw.decode("utf-8", errors="replace")
    if filename.endswith((".xlsx", ".xls")):
        try:
            import io
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"=== Sheet: {sheet.title} ===")
                for row in sheet.iter_rows(max_row=200, values_only=True):
                    non_null = [str(c) for c in row if c is not None]
                    if non_null:
                        lines.append("\t".join(non_null))
            return "\n".join(lines)
        except Exception as e:
            return f"[Excel parse error: {e}]"
    # Default: try UTF-8 text
    try:
        text = raw.decode("utf-8", errors="replace")
        if text.isprintable() or len(text) < 100:
            return text[:10000]
    except Exception:
        pass
    return f"[Binary file — {len(raw)} bytes, cannot display]"
