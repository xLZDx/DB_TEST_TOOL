"""Chat API router for IntelliTest."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import logging

from app.services import artifact_memory as mem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class NewConvRequest(BaseModel):
    title: str = "New Conversation"


class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str = ""
    content: str = ""  # frontend alias for message
    artifact_ids: List[str] = []
    jira_context: Optional[dict] = None
    tfs_context: Optional[dict] = None
    mode: str = "test_generation"

    def get_text(self) -> str:
        return self.content or self.message


@router.post("/conversations")
async def new_conversation(body: NewConvRequest):
    conv = mem.create_conversation(body.title)
    return conv  # return directly so frontend can access .id


@router.get("/conversations")
async def list_conversations(limit: int = 50):
    return {"conversations": mem.list_conversations(limit)}


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = mem.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if mem.delete_conversation(conv_id):
        return {"ok": True}
    raise HTTPException(404, "Not found")


class PatchTfsContextRequest(BaseModel):
    tfs_context: Optional[dict] = None
    jira_context: Optional[dict] = None


@router.patch("/conversations/{conv_id}/tfs-context")
async def patch_tfs_context(conv_id: str, body: PatchTfsContextRequest):
    if body.tfs_context is not None:
        mem.set_work_item_context(conv_id, "tfs", body.tfs_context)
    if body.jira_context is not None:
        mem.set_work_item_context(conv_id, "jira", body.jira_context)
    return {"ok": True}


class PatchTitleRequest(BaseModel):
    title: str


@router.patch("/conversations/{conv_id}/title")
async def patch_title(conv_id: str, body: PatchTitleRequest):
    conv = mem.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Not found")
    conv["title"] = body.title
    # Persist by re-saving (artifact_memory saves on add_message; do a direct save here)
    try:
        import json
        from pathlib import Path
        from app.config import settings
        path = settings.get_data_dir() / "chat_history" / f"{conv_id}.json"
        path.write_text(json.dumps(conv, indent=2, default=str))
    except Exception:
        pass
    return {"ok": True}


@router.post("/message")
async def send_message(body: SendMessageRequest):
    from app.services.ai_service import ai_chat

    user_text = body.get_text()
    if not user_text:
        raise HTTPException(400, "No message content")

    conv = mem.get_conversation(body.conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    jira_ctx = body.jira_context or conv.get("jira_context")
    tfs_ctx = body.tfs_context or conv.get("tfs_context")
    if body.jira_context is not None:
        mem.set_work_item_context(body.conversation_id, "jira", body.jira_context)
    if body.tfs_context is not None:
        mem.set_work_item_context(body.conversation_id, "tfs", body.tfs_context)

    all_artifact_ids = list(dict.fromkeys((conv.get("artifact_ids") or []) + body.artifact_ids))
    for art_id in body.artifact_ids:
        mem.link_artifact(body.conversation_id, art_id)

    # Build context + attachments
    context = mem.build_context_string([], jira_ctx, tfs_ctx)

    mode_ctx = {
        "test_generation": (
            "FOCUS: Generate SQL validation test cases. Include multi-layer tests "
            "(staging → aggregation → target), column value checks, NULL checks, "
            "grain/duplicate checks, and aggregate total validations."
        ),
        "sql_compare": "FOCUS: Analyse and compare SQL logic. Identify discrepancies.",
    }
    if body.mode in mode_ctx:
        context = (context + "\n\n" + mode_ctx[body.mode]).strip()

    art_index = {a["id"]: a for a in mem.list_artifacts()}
    attachments = []
    for art_id in all_artifact_ids[:10]:
        content = mem.get_artifact_content(art_id)
        if content:
            meta = art_index.get(art_id, {})
            attachments.append({"name": meta.get("name", art_id), "type": meta.get("type"), "content": content[:4000]})

    history = conv.get("messages", [])[-20:]
    msgs = [{"role": m["role"], "content": m["content"]}
            for m in history if m.get("role") in ("user", "assistant")]
    msgs.append({"role": "user", "content": user_text})

    result = await ai_chat(messages=msgs, system_context=context,
                           attachments=attachments if attachments else None)
    if "error" in result:
        raise HTTPException(500, result["error"])

    reply = result.get("reply", "")
    mem.add_message(body.conversation_id, "user", user_text, body.artifact_ids)
    mem.add_message(body.conversation_id, "assistant", reply)

    return {"role": "assistant", "reply": reply, "content": reply, "conversation_id": body.conversation_id}


@router.post("/artifacts/upload")
async def upload_artifact(file: UploadFile = File(...),
                           conversation_id: Optional[str] = Form(default=None)):
    raw = await file.read()
    filename = file.filename or "upload"
    content = _extract_text(filename, raw)
    art_type = _guess_type(filename)
    art = mem.save_artifact(filename, content, art_type,
                             {"size": len(raw), "content_type": file.content_type})
    if conversation_id:
        mem.link_artifact(conversation_id, art["id"])
    return {"ok": True, "artifact": art}


@router.get("/artifacts")
async def list_artifacts():
    return {"artifacts": mem.list_artifacts()}


@router.delete("/artifacts/{art_id}")
async def delete_artifact(art_id: str):
    if mem.delete_artifact(art_id):
        return {"ok": True}
    raise HTTPException(404, "Not found")


def _extract_text(filename: str, raw: bytes) -> str:
    lower = filename.lower()
    try:
        if lower.endswith((".csv", ".sql", ".txt", ".md", ".json", ".xml")):
            return raw.decode("utf-8", errors="replace")
        if lower.endswith((".xlsx", ".xls")):
            import io, openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f"=== Sheet: {sheet.title} ===")
                for row in sheet.iter_rows(max_row=200, values_only=True):
                    cols = [str(c) for c in row if c is not None]
                    if cols:
                        lines.append("\t".join(cols))
            return "\n".join(lines)
    except Exception as e:
        return f"[Error extracting text: {e}]"
    return raw.decode("utf-8", errors="replace")


def _guess_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        return "drd_excel"
    if lower.endswith(".csv"):
        return "drd_csv"
    if lower.endswith(".sql"):
        return "sql"
    if lower.endswith(".xml"):
        return "etl_config"
    return "file"
