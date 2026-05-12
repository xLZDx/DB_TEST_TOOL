"""Artifact Memory Service – persistent storage for chat conversations, uploaded artifacts,
and cross-session context (DRDs, mapping docs, SQL snippets, TFS context).

All data is stored as JSON files in data/chat_history/ and data/chat_artifacts/.
No additional database schema changes are required.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    """Base data directory for the application."""
    from app.config import BASE_DIR
    return BASE_DIR / "data"


def _history_dir() -> Path:
    d = _data_dir() / "chat_history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    d = _data_dir() / "chat_artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifact_index_path() -> Path:
    return _artifacts_dir() / "_artifact_index.json"


# ── Conversation CRUD ──────────────────────────────────────────────────────

def create_conversation(title: str = "New Conversation") -> Dict[str, Any]:
    """Create a new conversation and persist it. Returns the conversation dict."""
    conv_id = str(uuid.uuid4())
    now = _utc_now()
    conv = {
        "id": conv_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "artifact_ids": [],
        "tfs_context": None,
    }
    _save_conversation(conv)
    return conv


def list_conversations(limit: int = 50) -> List[Dict[str, Any]]:
    """Return a list of all conversations (metadata only, no messages) sorted newest first."""
    convs = []
    hist_dir = _history_dir()
    for f in sorted(hist_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            convs.append({
                "id": data.get("id", f.stem),
                "title": data.get("title", "Conversation"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
                "artifact_ids": data.get("artifact_ids", []),
            })
        except Exception:
            pass
        if len(convs) >= limit:
            break
    return convs


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    """Return full conversation dict including messages, or None if not found."""
    path = _history_dir() / f"{conv_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def add_message(conv_id: str, role: str, content: str,
                artifact_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Append a message to an existing conversation and persist. Returns updated conv."""
    conv = get_conversation(conv_id)
    if conv is None:
        raise ValueError(f"Conversation {conv_id} not found")
    msg = {
        "role": role,
        "content": content,
        "timestamp": _utc_now(),
        "artifact_ids": artifact_ids or [],
    }
    conv["messages"].append(msg)
    conv["updated_at"] = _utc_now()
    # Auto-title: use first 80 chars of first user message
    if role == "user" and conv["title"] == "New Conversation":
        conv["title"] = content[:80].replace("\n", " ").strip() or "Conversation"
    _save_conversation(conv)
    return conv


def update_conversation_title(conv_id: str, title: str) -> bool:
    conv = get_conversation(conv_id)
    if conv is None:
        return False
    conv["title"] = title[:120]
    conv["updated_at"] = _utc_now()
    _save_conversation(conv)
    return True


def update_tfs_context(conv_id: str, tfs_context: Optional[Dict]) -> bool:
    conv = get_conversation(conv_id)
    if conv is None:
        return False
    conv["tfs_context"] = tfs_context
    conv["updated_at"] = _utc_now()
    _save_conversation(conv)
    return True


def update_pending_orchestration(conv_id: str, state: Optional[Dict]) -> bool:
    """Store or clear the pending semi-manual orchestration checkpoint for a conversation."""
    conv = get_conversation(conv_id)
    if conv is None:
        return False
    conv["pending_orchestration"] = state
    conv["updated_at"] = _utc_now()
    _save_conversation(conv)
    return True


def get_pending_orchestration(conv_id: str) -> Optional[Dict]:
    conv = get_conversation(conv_id)
    if conv is None:
        return None
    return conv.get("pending_orchestration")


def delete_conversation(conv_id: str) -> bool:
    path = _history_dir() / f"{conv_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def link_artifact_to_conversation(conv_id: str, artifact_id: str) -> bool:
    conv = get_conversation(conv_id)
    if conv is None:
        return False
    if artifact_id not in conv["artifact_ids"]:
        conv["artifact_ids"].append(artifact_id)
        conv["updated_at"] = _utc_now()
        _save_conversation(conv)
    return True


# ── Artifact CRUD ──────────────────────────────────────────────────────────

def save_artifact(name: str, content_text: str, artifact_type: str = "file",
                  metadata: Optional[Dict] = None) -> Dict[str, Any]:
    """Save an uploaded artifact (DRD, SQL, mapping doc, etc.). Returns artifact info."""
    art_id = str(uuid.uuid4())
    now = _utc_now()
    art = {
        "id": art_id,
        "name": name,
        "type": artifact_type,
        "created_at": now,
        "content_preview": content_text[:500],
        "content_length": len(content_text),
        "metadata": metadata or {},
    }
    # Save full content separate from index
    content_path = _artifacts_dir() / f"{art_id}.txt"
    content_path.write_text(content_text, encoding="utf-8")
    # Update index
    index = _load_artifact_index()
    index[art_id] = art
    _save_artifact_index(index)
    logger.debug("Saved artifact %s (%s, %d chars)", art_id, name, len(content_text))
    return art


def get_artifact_content(artifact_id: str) -> Optional[str]:
    """Return full text content of an artifact."""
    content_path = _artifacts_dir() / f"{artifact_id}.txt"
    if not content_path.exists():
        return None
    try:
        return content_path.read_text(encoding="utf-8")
    except Exception:
        return None


def list_artifacts(limit: int = 100) -> List[Dict[str, Any]]:
    """Return all artifacts from index (without full content)."""
    index = _load_artifact_index()
    items = sorted(index.values(), key=lambda a: a.get("created_at", ""), reverse=True)
    return items[:limit]


def delete_artifact(artifact_id: str) -> bool:
    index = _load_artifact_index()
    if artifact_id not in index:
        return False
    del index[artifact_id]
    _save_artifact_index(index)
    content_path = _artifacts_dir() / f"{artifact_id}.txt"
    if content_path.exists():
        content_path.unlink()
    return True


# ── Context Assembly ───────────────────────────────────────────────────────

def build_system_context(
    artifact_ids: Optional[List[str]] = None,
    tfs_context: Optional[Dict] = None,
    schema_kb_summary: Optional[str] = None,
) -> str:
    """Build a system prompt that combines:
    - Instructions for the AI test generation assistant
    - Uploaded artifact content (DRD, SQL, mapping docs, etc.)
    - TFS work item context (if provided)
    - Schema KB summary (if available)
    """
    parts: List[str] = [
        "You are an expert data quality engineer and test case designer. "
        "Your role is to help users create SQL-based validation tests for ETL pipelines, "
        "data warehouses, and financial data systems. "
        "When generating test cases, produce precise, executable SQL queries. "
        "Use the provided mapping documents, DRDs, and TFS requirements to guide test scope. "
        "Always reference specific column names, transformations, and business rules from the provided documents."
    ]

    if schema_kb_summary:
        parts.append(f"\n\n## Available Schema Knowledge Base\n{schema_kb_summary}")

    if tfs_context:
        parts.append(_format_tfs_context_for_prompt(tfs_context))

    if artifact_ids:
        art_parts = []
        for art_id in artifact_ids[:10]:  # Max 10 artifacts to avoid context overflow
            content = get_artifact_content(art_id)
            if not content:
                continue
            index = _load_artifact_index()
            meta = index.get(art_id, {})
            name = meta.get("name", art_id)
            art_type = meta.get("type", "file")
            # Truncate large content to avoid context overflow
            truncated = content[:4000]
            if len(content) > 4000:
                truncated += f"\n... [truncated, {len(content) - 4000} more chars]"
            art_parts.append(f"### {name} ({art_type})\n{truncated}")
        if art_parts:
            parts.append("\n\n## Uploaded Context Files\n" + "\n\n".join(art_parts))

    return "\n".join(parts)


def _format_tfs_context_for_prompt(tfs_ctx: Dict) -> str:
    lines = [
        f"\n\n## TFS Work Item Context",
        f"**Type:** {tfs_ctx.get('work_item_type', '')}  "
        f"**ID:** {tfs_ctx.get('id', '')}  "
        f"**State:** {tfs_ctx.get('state', '')}",
        f"**Title:** {tfs_ctx.get('title', '')}",
    ]
    if tfs_ctx.get("description_text"):
        lines.append(f"\n**Description:**\n{tfs_ctx['description_text'][:1500]}")
    if tfs_ctx.get("acceptance_criteria"):
        lines.append(f"\n**Acceptance Criteria:**\n{tfs_ctx['acceptance_criteria'][:1500]}")
    if tfs_ctx.get("tags"):
        lines.append(f"**Tags:** {tfs_ctx['tags']}")
    attachments = tfs_ctx.get("attachments", [])
    if attachments:
        att_names = ", ".join(a.get("name", "") for a in attachments[:10])
        lines.append(f"**Attachments referenced:** {att_names}")
    return "\n".join(lines)


# ── Private helpers ────────────────────────────────────────────────────────

def _save_conversation(conv: Dict[str, Any]) -> None:
    path = _history_dir() / f"{conv['id']}.json"
    path.write_text(json.dumps(conv, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_artifact_index() -> Dict[str, Any]:
    idx_path = _artifact_index_path()
    if not idx_path.exists():
        return {}
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_artifact_index(index: Dict[str, Any]) -> None:
    _artifact_index_path().write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
