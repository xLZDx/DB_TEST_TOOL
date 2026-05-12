"""Artifact Memory Service for IntelliTest.

Stores chat conversations, uploaded files, Jira/TFS work item context,
and generated tests as local JSON files. Provides the persistent memory
that allows the AI to learn from past interactions.

Storage layout:
  data/chat_history/{conversation_id}.json
  data/chat_artifacts/{artifact_id}.txt
  data/chat_artifacts/_artifact_index.json
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _history_dir() -> Path:
    d = settings.get_data_dir() / "chat_history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _artifacts_dir() -> Path:
    d = settings.get_data_dir() / "chat_artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Conversations ──────────────────────────────────────────────────────────

def create_conversation(title: str = "New Conversation") -> Dict[str, Any]:
    conv_id = str(uuid.uuid4())
    now = _utc_now()
    conv = {
        "id": conv_id, "title": title, "created_at": now, "updated_at": now,
        "messages": [], "artifact_ids": [], "jira_context": None, "tfs_context": None,
    }
    _save_conversation(conv)
    return conv


def list_conversations(limit: int = 50) -> List[Dict[str, Any]]:
    convs = []
    for f in sorted(_history_dir().glob("*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            data = json.loads(f.read_text("utf-8"))
            convs.append({k: data.get(k) for k in
                          ("id", "title", "created_at", "updated_at", "artifact_ids")})
            convs[-1]["message_count"] = len(data.get("messages", []))
        except Exception:
            pass
    return convs


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    path = _history_dir() / f"{conv_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text("utf-8"))


def add_message(conv_id: str, role: str, content: str,
                artifact_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    conv = get_conversation(conv_id)
    if not conv:
        return None
    msg = {"role": role, "content": content, "timestamp": _utc_now(), "artifact_ids": artifact_ids or []}
    conv["messages"].append(msg)
    conv["updated_at"] = _utc_now()
    if role == "user" and conv["title"] == "New Conversation":
        conv["title"] = content[:80].replace("\n", " ").strip()
    _save_conversation(conv)
    return conv


def set_work_item_context(conv_id: str, source: str,
                           context: Optional[Dict]) -> bool:
    """source: 'jira' or 'tfs'"""
    conv = get_conversation(conv_id)
    if not conv:
        return False
    conv[f"{source}_context"] = context
    conv["updated_at"] = _utc_now()
    _save_conversation(conv)
    return True


def delete_conversation(conv_id: str) -> bool:
    path = _history_dir() / f"{conv_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def link_artifact(conv_id: str, artifact_id: str) -> bool:
    conv = get_conversation(conv_id)
    if not conv:
        return False
    if artifact_id not in conv["artifact_ids"]:
        conv["artifact_ids"].append(artifact_id)
        conv["updated_at"] = _utc_now()
        _save_conversation(conv)
    return True


# ── Artifacts ──────────────────────────────────────────────────────────────

def save_artifact(name: str, content_text: str, artifact_type: str = "file",
                  metadata: Optional[Dict] = None) -> Dict[str, Any]:
    art_id = str(uuid.uuid4())
    art = {
        "id": art_id, "name": name, "type": artifact_type,
        "created_at": _utc_now(),
        "content_preview": content_text[:500],
        "content_length": len(content_text),
        "metadata": metadata or {},
    }
    (_artifacts_dir() / f"{art_id}.txt").write_text(content_text, "utf-8")
    index = _load_artifact_index()
    index[art_id] = art
    _save_artifact_index(index)
    return art


def get_artifact_content(art_id: str) -> Optional[str]:
    path = _artifacts_dir() / f"{art_id}.txt"
    return path.read_text("utf-8") if path.exists() else None


def list_artifacts(limit: int = 100) -> List[Dict[str, Any]]:
    index = _load_artifact_index()
    return sorted(index.values(), key=lambda a: a.get("created_at", ""), reverse=True)[:limit]


def delete_artifact(art_id: str) -> bool:
    index = _load_artifact_index()
    if art_id not in index:
        return False
    del index[art_id]
    _save_artifact_index(index)
    p = _artifacts_dir() / f"{art_id}.txt"
    if p.exists():
        p.unlink()
    return True


def build_context_string(artifact_ids: Optional[List[str]] = None,
                          jira_context: Optional[Dict] = None,
                          tfs_context: Optional[Dict] = None) -> str:
    """Build a system context string combining work item context and artifacts."""
    parts = []
    if jira_context:
        parts.append(
            f"## Jira: {jira_context.get('key', '')} — {jira_context.get('summary', '')}\n"
            f"Type: {jira_context.get('issue_type', '')} | Status: {jira_context.get('status', '')}\n"
            f"Description: {jira_context.get('description_text', '')[:800]}\n"
            + (f"Acceptance Criteria: {jira_context.get('acceptance_criteria', '')[:600]}\n"
               if jira_context.get("acceptance_criteria") else "")
        )
    if tfs_context:
        parts.append(
            f"## TFS #{tfs_context.get('id', '')} — {tfs_context.get('title', '')}\n"
            f"Type: {tfs_context.get('work_item_type', '')} | State: {tfs_context.get('state', '')}\n"
            f"Description: {tfs_context.get('description_text', '')[:800]}\n"
            + (f"Acceptance Criteria: {tfs_context.get('acceptance_criteria', '')[:600]}\n"
               if tfs_context.get("acceptance_criteria") else "")
        )
    if artifact_ids:
        for art_id in artifact_ids[:8]:
            content = get_artifact_content(art_id)
            if not content:
                continue
            index = _load_artifact_index()
            meta = index.get(art_id, {})
            parts.append(f"## Artifact: {meta.get('name', art_id)} ({meta.get('type', '')})\n"
                         f"{content[:3000]}")
    return "\n\n".join(parts)


# ── Private helpers ────────────────────────────────────────────────────────

def _save_conversation(conv: Dict) -> None:
    (_history_dir() / f"{conv['id']}.json").write_text(
        json.dumps(conv, ensure_ascii=False, indent=2), "utf-8")


def _load_artifact_index() -> Dict:
    p = _artifacts_dir() / "_artifact_index.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else {}


def _save_artifact_index(index: Dict) -> None:
    (_artifacts_dir() / "_artifact_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), "utf-8")
