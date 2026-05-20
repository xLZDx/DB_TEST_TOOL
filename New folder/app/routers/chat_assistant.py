"""AI Chat Assistant API router.

Provides endpoints for a persistent, multi-artifact chatbot powered by GitHub Copilot
(via the existing ai_service.py integration). Conversations and uploaded artifacts are
stored in the local filesystem via artifact_memory_service.py.
"""
import logging
import json
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.artifact_memory_service import (
    create_conversation,
    list_conversations,
    get_conversation,
    add_message,
    delete_conversation,
    update_conversation_title,
    update_tfs_context,
    update_pending_orchestration,
    get_pending_orchestration,
    link_artifact_to_conversation,
    save_artifact,
    list_artifacts,
    get_artifact_content,
    delete_artifact,
    build_system_context,
)
from app.database import get_db
from app.models.test_case import TestCase, TestFolder, TestCaseFolder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Request / Response models ──────────────────────────────────────────────

class NewConversationRequest(BaseModel):
    title: str = "New Conversation"


class SendMessageRequest(BaseModel):
    conversation_id: str
    message: str
    artifact_ids: List[str] = []
    tfs_context: Optional[dict] = None
    mode: str = "test_generation"  # test_generation | general | sql_compare
    agent_mode: str = "auto"       # auto | semi_manual
    validation_datasource_id: Optional[int] = None


class UpdateTitleRequest(BaseModel):
    title: str


class UpdateTfsContextRequest(BaseModel):
    tfs_context: Optional[dict] = None


class SaveSqlTestsRequest(BaseModel):
    source_datasource_id: int
    target_datasource_id: Optional[int] = None
    folder_name: str = "AI Chat SQL"
    message_index: Optional[int] = None  # defaults to latest assistant message
    severity: str = "high"
    expected_result: str = "0"
    only_select: bool = True


# ── Conversation endpoints ─────────────────────────────────────────────────

@router.post("/conversations")
async def new_conversation(body: NewConversationRequest):
    """Create a new chat conversation."""
    conv = create_conversation(body.title)
    return {"ok": True, "conversation": conv}


@router.get("/conversations")
async def get_conversations(limit: int = 50):
    """List all conversations (newest first), without full message content."""
    return {"conversations": list_conversations(limit=limit)}


@router.get("/conversations/{conv_id}")
async def get_conversation_detail(conv_id: str):
    """Return a full conversation including all messages."""
    conv = get_conversation(conv_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def remove_conversation(conv_id: str):
    """Delete a conversation."""
    if delete_conversation(conv_id):
        return {"ok": True}
    raise HTTPException(404, "Conversation not found")


@router.patch("/conversations/{conv_id}/title")
async def rename_conversation(conv_id: str, body: UpdateTitleRequest):
    if update_conversation_title(conv_id, body.title):
        return {"ok": True}
    raise HTTPException(404, "Conversation not found")


@router.patch("/conversations/{conv_id}/tfs-context")
async def set_tfs_context(conv_id: str, body: UpdateTfsContextRequest):
    if update_tfs_context(conv_id, body.tfs_context):
        return {"ok": True}
    raise HTTPException(404, "Conversation not found")


@router.get("/diagnostics/tfs/{item_id}")
async def diagnose_tfs_download(item_id: int):
    """Diagnostic: download and inspect all attachments + hyperlinks from a TFS work item.

    Returns a structured report showing every attachment (name, size, first 500 chars),
    every hyperlink (URL, status, size), and the raw TFS description so you can verify
    the tool is reading all documents before the AI pipeline runs.
    """
    from app.services.tfs_service import fetch_work_item_full_context
    try:
        data = await fetch_work_item_full_context(item_id)
    except Exception as e:
        raise HTTPException(500, f"TFS fetch failed: {e}")

    attachments = []
    for att in data.get("attachments", []):
        text = att.get("content_text", "")
        ok = bool(text) and not text.startswith("[Download failed") and not text.startswith("[Could not")
        attachments.append({
            "name": att.get("name"),
            "url": att.get("url"),
            "size_chars": len(text) if ok else 0,
            "status": "✅ downloaded" if ok else f"❌ {text[:200]}",
            "preview": text[:500] if ok else "",
        })

    hyperlinks = []
    for lnk in data.get("hyperlinks", []):
        text = lnk.get("content_text", "")
        ok = bool(text) and not text.startswith("[Failed") and not text.startswith("[HTTP")
        hyperlinks.append({
            "url": lnk.get("url"),
            "comment": lnk.get("comment", ""),
            "size_chars": len(text) if ok else 0,
            "status": "✅ downloaded" if ok else (f"❌ {text[:200]}" if text else "⏭️ not fetched"),
            "preview": text[:500] if ok else "",
        })

    return {
        "work_item_id": item_id,
        "title": data.get("title"),
        "description_chars": len(data.get("description_text") or ""),
        "acceptance_criteria_chars": len(data.get("acceptance_criteria") or ""),
        "attachments": attachments,
        "hyperlinks": hyperlinks,
        "total_content_chars": sum(a["size_chars"] for a in attachments) + sum(h["size_chars"] for h in hyperlinks),
    }


# ── Agent phase formatting helpers ────────────────────────────────────────

def _format_phase_report(report) -> str:
    """Render an AgentPhaseReport as human-readable markdown for chat display."""
    phase_labels = {
        "context_builder": "📋 Phase 1: Context Builder",
        "analysis":        "🔍 Phase 2: Analysis Agent",
        "design":          "🛠️ Phase 3: Design Agent",
        "validation":      "✅ Phase 4: Validation Agent",
    }
    label = phase_labels.get(report.phase, f"Phase: {report.phase}")
    lines = [f"## {label}\n"]
    lines.append(f"**Summary:** {report.result_summary}\n")

    if report.documents_reviewed:
        lines.append("**Documents Reviewed:**")
        for d in report.documents_reviewed:
            lines.append(f"  - {d}")

    if report.tables_identified:
        lines.append("**Tables Identified:**")
        for t in report.tables_identified:
            lines.append(f"  - `{t}`")

    if report.decisions:
        lines.append("**Decisions Made:**")
        for d in report.decisions:
            lines.append(f"  - {d}")

    if report.warnings:
        lines.append("⚠️ **Warnings:**")
        for w in report.warnings:
            lines.append(f"  - ⚠️ {w}")

    return "\n".join(lines)


def _next_phase_prompt(current_phase: str) -> str:
    phase_next = {
        "context_done":   ("Analysis", "I will extract all source/target tables and ETL mapping rules from the documents."),
        "analysis_done":  ("Design", "I will generate Oracle SQL validation tests based on the mapping spec."),
        "design_done":    ("Validation", "I will validate generated SQL against Oracle using EXPLAIN PLAN and auto-repair errors."),
    }
    info = phase_next.get(current_phase)
    if not info:
        return ""
    phase_name, description = info
    return (
        f"\n\n---\n\n"
        f"**Next: {phase_name} Phase** — {description}\n\n"
        "Type **proceed** to continue, or describe any corrections you want made before the next phase runs.\n"
        "_(Example: \"proceed\" or \"the source is CDS_STG_OWNER.TXN_TRLR_STCCCALQ_STG not STCCCALQ_GG_VW\")_"
    )


# ── Message endpoint ───────────────────────────────────────────────────────

@router.post("/message")
async def send_message(body: SendMessageRequest):
    """Send a user message and get an AI response.

    The AI receives the full conversation history, uploaded artifact content,
    TFS work item context, and schema KB summary in its system context.
    """
    from app.services.ai_service import ai_chat, _local_schema_kb_context
    from app.services.artifact_memory_service import _format_tfs_context_for_prompt

    conv = get_conversation(body.conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")

    # Merge TFS context if provided with this message
    tfs_ctx = body.tfs_context or conv.get("tfs_context")
    if body.tfs_context is not None:
        update_tfs_context(body.conversation_id, body.tfs_context)

    # Collect all artifact IDs (conversation's + this message's)
    all_artifact_ids = list(dict.fromkeys(
        (conv.get("artifact_ids") or []) + body.artifact_ids
    ))
    for art_id in body.artifact_ids:
        link_artifact_to_conversation(body.conversation_id, art_id)

    # Build context string (schema KB + TFS + mode instructions)
    context_parts: List[str] = []
    try:
        kb_summary = _local_schema_kb_context(max_tables=30)
        if kb_summary:
            context_parts.append(f"Schema Knowledge Base:\n{kb_summary}")
    except Exception:
        pass

    if tfs_ctx:
        context_parts.append(_format_tfs_context_for_prompt(tfs_ctx))

    mode_instructions = {
        "test_generation": (
            "FOCUS: The user wants to generate SQL validation test cases. "
            "Output ONLY Oracle SQL in ```sql fenced code blocks. NEVER output JSON for test generation. "
            "Generate executable SELECT statements that validate transformation logic, joins, and lookup mapping rules. "
            "Group tests by category: grain validation, null checks, aggregate totals, "
            "lookup joins, transformation logic. When the mapping has aggregation steps, "
            "generate multi-layer tests covering each stage (staging -> intermediate -> target). "
            "For trailer parsing scenarios, prioritize join-based tests using CDS_STG_OWNER.STCCCALQ_GG_VW, "
            "CCAL_OWNER.CDSM_RULE_MAP, and CCAL_OWNER.TXN/APA/FIP/TXN_RLTNP with mismatch-count assertions."
        ),
        "sql_compare": (
            "FOCUS: The user wants to compare or validate SQL logic. "
            "Analyse the provided SQL and mapping rules, identify discrepancies, suggest corrections."
        ),
    }
    if body.mode in mode_instructions:
        context_parts.append(mode_instructions[body.mode])

    context = "\n\n".join(context_parts)

    # Build attachments list for ai_chat (content passed separately from context)
    art_index = {a["id"]: a for a in list_artifacts()}
    attachments = []
    for art_id in all_artifact_ids[:10]:  # limit to avoid context overflow
        content = get_artifact_content(art_id)
        if not content:
            continue
        meta = art_index.get(art_id, {})
        attachments.append({
            "name": meta.get("name", art_id),
            "type": meta.get("type", "file"),
            # No truncation: full file content is passed to the agent pipeline.
            # The 4-phase orchestrator handles large artifacts internally (12KB per doc to AI).
            "content": content,
        })

    # Build message history (last 20 messages stays within context limits)
    history = conv.get("messages", [])[-20:]
    history_messages = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in history
        if m.get("role") in ("user", "assistant")
    ]
    history_messages.append({"role": "user", "content": body.message})

    try:
        if body.mode == "test_generation":
            from app.services.ai_service import orchestrate_test_generation, run_orchestration_phase

            tfs_id = str(tfs_ctx.get("id")) if tfs_ctx and "id" in tfs_ctx else None
            # Always prefix each artifact with its real filename so agents display and anchor it correctly
            art_contents = [
                f"[File: {att['name']}]\n{att['content']}"
                for att in attachments if "content" in att
            ]

            if body.agent_mode == "semi_manual":
                # ── SEMI-MANUAL MODE ──────────────────────────────────────────────
                # Each phase runs separately. The user reviews the report and
                # types "proceed" (or a correction) to continue.
                pending = get_pending_orchestration(body.conversation_id)
                msg_lower = body.message.lower().strip()
                is_proceed = any(kw in msg_lower for kw in [
                    "proceed", "continue", "next phase", "next step",
                    "looks good", "looks ok", "ok proceed", "ok, proceed",
                ])

                if pending and pending.get("phase") != "complete":
                    # Determine next phase to run
                    phase_map = {
                        "context_done": "analysis",
                        "analysis_done": "design",
                        "design_done": "validation",
                    }
                    current_phase = pending.get("phase", "")
                    next_phase = phase_map.get(current_phase)
                    if not next_phase:
                        # Shouldn't happen, but reset and restart
                        update_pending_orchestration(body.conversation_id, None)
                        assistant_content = "⚠️ Orchestration state is unclear. Please start again with your requirement."
                        add_message(body.conversation_id, "user", body.message, body.artifact_ids)
                        add_message(body.conversation_id, "assistant", assistant_content)
                        return {"role": "assistant", "content": assistant_content, "conversation_id": body.conversation_id}

                    # Correction text = the user's message if they didn't just say "proceed"
                    correction = "" if is_proceed else body.message

                    updated_state, report = await run_orchestration_phase(next_phase, pending, correction=correction)
                    update_pending_orchestration(body.conversation_id, updated_state)

                    if updated_state.get("phase") == "complete":
                        # Validation done — format final tests for display
                        final_tests = updated_state.get("final_tests_json", [])
                        assistant_content = _format_phase_report(report)
                        assistant_content += f"\n\n---\n\n✅ **All phases complete.** {len(final_tests)} test(s) ready to save.\n\n"
                        for i, t in enumerate(final_tests, start=1):
                            assistant_content += f"### {i}. {t.get('name','')}\n"
                            assistant_content += f"**Type:** {t.get('test_type','')} | **Severity:** {t.get('severity','')}\n\n"
                            assistant_content += f"```sql\n{t.get('source_query','')}\n```\n\n"
                        assistant_content += f"\n<details><summary>Structured Data (For Saving)</summary>\n\n```json\n{json.dumps(final_tests, indent=2)}\n```\n</details>"
                        update_pending_orchestration(body.conversation_id, None)
                    else:
                        assistant_content = _format_phase_report(report)
                        assistant_content += _next_phase_prompt(updated_state.get("phase", ""))
                else:
                    # Start from the beginning
                    initial_state: dict = {
                        "phase": "pending_context",
                        "tfs_item_id": tfs_id,
                        "artifact_contents": art_contents,
                        "user_prompt": body.message,
                        "db_dialect": "oracle",
                        "validation_datasource_id": body.validation_datasource_id,
                    }
                    updated_state, report = await run_orchestration_phase("context", initial_state)
                    update_pending_orchestration(body.conversation_id, updated_state)
                    assistant_content = _format_phase_report(report)
                    assistant_content += _next_phase_prompt(updated_state.get("phase", ""))

            else:
                # ── AUTOMATIC MODE ────────────────────────────────────────────────
                from app.services.ai_service import (
                    build_tfs_and_schema_context,
                    analyze_etl_requirements,
                    design_sql_tests,
                    validate_and_fix_sql_tests,
                )
                all_reports: list = []

                context_obj = await build_tfs_and_schema_context(
                    tfs_item_id=tfs_id, artifact_contents=art_contents, user_prompt=body.message
                )

                # ── Phase 1 report (Context Builder) ──────────────────────────
                import re as _re
                _raw_arts = context_obj.artifact_contents
                _doc_names = []
                for _a in _raw_arts:
                    _first = _a.splitlines()[0] if _a else ""
                    if _first.startswith("[File:"):
                        _label = _first[len("[File:"):].rstrip("]").strip()
                    elif _first.startswith("TFS Attachment (") or _first.startswith("TFS Linked"):
                        _label = _first.split("(", 1)[-1].rstrip(")").rstrip(":")
                    else:
                        _label = _first[:80] if _first else f"artifact"
                    _doc_names.append(f"{_label} ({len(_a):,} chars)")
                _schema_tables = _re.findall(r"- ([A-Z][\w]+\.[A-Z][\w]+)", context_obj.schema_ddl)
                _dl = context_obj.__dict__.get("_tfs_download_log", [])
                from app.models.agent_contracts import AgentPhaseReport as _APR
                all_reports.append(_APR(
                    phase="context_builder",
                    documents_reviewed=_doc_names,
                    tables_identified=_schema_tables,
                    decisions=[
                        f"TFS work item: {context_obj.work_item_id}",
                        f"Title: {context_obj.title[:120]}",
                        f"User-uploaded artifacts: {len(art_contents)}",
                        f"Total artifacts (incl TFS downloads): {len(_raw_arts)}",
                        f"Schema KB tables matched: {len(_schema_tables)}",
                    ] + _dl,
                    warnings=[d for d in _dl if d.startswith("❌")],
                    result_summary=(
                        f"Context collected: {len(_raw_arts)} document(s) — "
                        + ", ".join(_doc_names[:5])
                        + (f" (+{len(_doc_names)-5} more)" if len(_doc_names) > 5 else "")
                        + f". Schema KB: {len(_schema_tables)} table(s) matched."
                        + (f" TFS: {len(_dl)} download event(s)." if _dl else "")
                    ),
                    result_payload={"work_item_id": context_obj.work_item_id, "title": context_obj.title},
                ))
                # ──────────────────────────────────────────────────────────────

                spec = await analyze_etl_requirements(context_obj, reports=all_reports)
                draft_tests = await design_sql_tests(
                    spec, "oracle",
                    artifact_contents=context_obj.artifact_contents,
                    schema_ddl=context_obj.schema_ddl,
                    reports=all_reports,
                )
                test_designs = await validate_and_fix_sql_tests(
                    draft_tests, spec, "oracle", body.validation_datasource_id
                )

                # Build response: phase reports first, then tests
                assistant_content = "## 🤖 Agent Pipeline Report\n\n"
                for r in all_reports:
                    assistant_content += _format_phase_report(r) + "\n\n"

                assistant_content += "---\n\n## ✅ Generated Test Cases\n\n"
                json_payload = []
                for t in test_designs:
                    assistant_content += f"### {t.name}\n"
                    assistant_content += f"**Type:** {t.test_type} | **Severity:** {t.severity}\n"
                    assistant_content += f"**Description:** {t.description}\n\n"
                    assistant_content += f"```sql\n{t.source_query}\n```\n\n"
                    if t.target_query:
                        assistant_content += f"**Target Query:**\n```sql\n{t.target_query}\n```\n\n"
                    assistant_content += f"**Expected Result:** `{t.expected_result}`\n\n---\n"
                    json_payload.append(t.model_dump())

                assistant_content += f"\n<details><summary>Structured Data (For Saving)</summary>\n\n```json\n{json.dumps(json_payload, indent=2)}\n```\n</details>"
        else:
            # Standard conversational chat
            result = await ai_chat(messages=history_messages, context=context, attachments=attachments if attachments else None)
            if "error" in result:
                raise ValueError(result["error"])
            assistant_content = result.get("reply", "")
    except Exception as e:
        logger.error("Chat AI error: %s", e)
        raise HTTPException(500, f"AI provider error: {e}")

    # Persist both messages to conversation history
    add_message(body.conversation_id, "user", body.message, body.artifact_ids)
    add_message(body.conversation_id, "assistant", assistant_content)

    return {
        "role": "assistant",
        "content": assistant_content,
        "conversation_id": body.conversation_id,
    }


# ── Artifact endpoints ─────────────────────────────────────────────────────

@router.post("/artifacts/upload")
async def upload_artifact(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(default=None),
):
    """Upload a file (DRD CSV/Excel, SQL, PDF text, mapping doc) as context artifact.

    The file content is extracted as text and stored for use in AI prompts.
    """
    raw = await file.read()
    filename = file.filename or "upload"

    # Extract text content depending on file type
    content_text = _extract_text_from_upload(filename, raw)

    art_type = _guess_artifact_type(filename)
    art = save_artifact(
        name=filename,
        content_text=content_text,
        artifact_type=art_type,
        metadata={"original_size": len(raw), "content_type": file.content_type or ""},
    )

    if conversation_id:
        link_artifact_to_conversation(conversation_id, art["id"])

    return {"ok": True, "artifact": art}


@router.get("/artifacts")
async def get_artifacts():
    """List all stored artifacts."""
    return {"artifacts": list_artifacts()}


@router.delete("/artifacts/{artifact_id}")
async def remove_artifact(artifact_id: str):
    if delete_artifact(artifact_id):
        return {"ok": True}
    raise HTTPException(404, "Artifact not found")


@router.get("/artifacts/{artifact_id}/preview")
async def preview_artifact(artifact_id: str, max_chars: int = 2000):
    """Return a preview of artifact content."""
    content = get_artifact_content(artifact_id)
    if content is None:
        raise HTTPException(404, "Artifact not found")
    return {"preview": content[:max_chars], "total_length": len(content)}


@router.post("/conversations/{conv_id}/save-sql-tests")
async def save_sql_tests_from_conversation(
    conv_id: str,
    body: SaveSqlTestsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Extract SQL code blocks from an assistant reply and save them as test cases."""
    conv = get_conversation(conv_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")

    messages = conv.get("messages") or []
    assistant_msgs = [m for m in messages if m.get("role") == "assistant" and (m.get("content") or "").strip()]
    if not assistant_msgs:
        raise HTTPException(400, "No assistant messages found in conversation")

    if body.message_index is None:
        selected_msg = assistant_msgs[-1]
    else:
        idx = body.message_index
        if idx < 0:
            idx = len(assistant_msgs) + idx
        if idx < 0 or idx >= len(assistant_msgs):
            raise HTTPException(400, f"message_index out of range (assistant messages={len(assistant_msgs)})")
        selected_msg = assistant_msgs[idx]

    assistant_text = selected_msg.get("content") or ""

    # NEW: Try to parse structured Agent JSON block first to preserve metadata
    json_blocks = re.findall(r"```json\s*([\s\S]*?)```", assistant_text, flags=re.IGNORECASE)
    if json_blocks:
        try:
            payload = json.loads(json_blocks[-1])
            if isinstance(payload, list) and len(payload) > 0 and "source_query" in payload[0]:
                folder = await _ensure_chat_folder(db, body.folder_name)
                created = []
                for i, item in enumerate(payload, start=1):
                    tc = TestCase(
                        name=item.get("name", f"AI Agent Test {i}"),
                        test_type=item.get("test_type", "value_match"),
                        source_datasource_id=body.source_datasource_id,
                        target_datasource_id=body.target_datasource_id,
                        source_query=item.get("source_query"),
                        target_query=item.get("target_query"),
                        expected_result=item.get("expected_result", body.expected_result),
                        severity=item.get("severity", body.severity),
                        is_active=True,
                        is_ai_generated=True,
                        description=item.get("description", "Saved from Multi-Agent response"),
                    )
                    db.add(tc)
                    await db.flush()
                    if folder:
                        db.add(TestCaseFolder(test_case_id=tc.id, folder_id=folder.id))
                    created.append({"id": tc.id, "name": tc.name})
                await db.commit()
                return {"ok": True, "conversation_id": conv_id, "folder": folder.name if folder else None, "saved_count": len(created), "tests": created}
        except json.JSONDecodeError:
            pass

    # Fallback to existing regex extraction for raw SQL
    sql_blocks = _extract_sql_blocks(assistant_text)
    if not sql_blocks:
        raise HTTPException(400, "No SQL code blocks found in selected assistant message")

    statements: List[str] = []
    for block in sql_blocks:
        for stmt in _split_sql_statements(block):
            trimmed = stmt.strip()
            if not trimmed:
                continue
            if body.only_select and not re.match(r"^(SELECT|WITH)\b", trimmed, flags=re.IGNORECASE):
                continue
            statements.append(trimmed)

    if not statements:
        raise HTTPException(400, "No eligible SQL SELECT statements found to save")

    folder = await _ensure_chat_folder(db, body.folder_name)
    created = []

    for i, sql in enumerate(statements, start=1):
        tc = TestCase(
            name=f"AI Chat SQL Test {i}",
            test_type="custom_sql",
            source_datasource_id=body.source_datasource_id,
            target_datasource_id=body.target_datasource_id,
            source_query=sql,
            target_query=None,
            expected_result=body.expected_result,
            tolerance=0.0,
            severity=body.severity,
            is_active=True,
            is_ai_generated=True,
            description="Saved from Chat Assistant SQL response",
        )
        db.add(tc)
        await db.flush()

        if folder:
            db.add(TestCaseFolder(test_case_id=tc.id, folder_id=folder.id))
        created.append({"id": tc.id, "name": tc.name})

    await db.commit()

    return {
        "ok": True,
        "conversation_id": conv_id,
        "folder": folder.name if folder else None,
        "saved_count": len(created),
        "tests": created,
    }


# ── Private helpers ────────────────────────────────────────────────────────

def _extract_text_from_upload(filename: str, raw: bytes) -> str:
    """Best-effort text extraction from uploaded file bytes."""
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            return raw.decode("utf-8", errors="replace")
        elif lower.endswith(".sql"):
            return raw.decode("utf-8", errors="replace")
        elif lower.endswith(".txt") or lower.endswith(".md"):
            return raw.decode("utf-8", errors="replace")
        elif lower.endswith((".xlsx", ".xls")):
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
        elif lower.endswith(".json"):
            return raw.decode("utf-8", errors="replace")
        elif lower.endswith(".xml"):
            return raw.decode("utf-8", errors="replace")
        else:
            # Try plain text decode for unknown types
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Could not extract text from %s: %s", filename, e)
        return f"[Binary file: {filename} — could not extract text]"


def _guess_artifact_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        return "drd_excel"
    if lower.endswith(".csv"):
        return "drd_csv"
    if lower.endswith(".sql"):
        return "sql"
    if lower.endswith(".xml"):
        return "etl_config"
    if lower.endswith(".json"):
        return "json_config"
    if lower.endswith(".md"):
        return "documentation"
    return "file"


def _extract_sql_blocks(text: str) -> List[str]:
    src = text or ""
    blocks = re.findall(r"```sql\s*([\s\S]*?)```", src, flags=re.IGNORECASE)
    if blocks:
        return [b.strip() for b in blocks if b.strip()]
    generic = re.findall(r"```\s*([\s\S]*?)```", src)
    
    # Filter out known non-SQL code blocks if falling back to generic fences
    valid_blocks = []
    for b in generic:
        header = b.split('\n', 1)[0].strip().lower()
        if header not in ('json', 'python', 'xml', 'csv', 'bash', 'sh'):
            valid_blocks.append(b.strip())
    return valid_blocks


def _split_sql_statements(sql_text: str) -> List[str]:
    text = (sql_text or "").strip()
    if not text:
        return []
    statements: List[str] = []
    current: List[str] = []
    in_single = False
    in_double = False
    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == ";" and not in_single and not in_double:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


async def _ensure_chat_folder(db: AsyncSession, folder_name: str) -> Optional[TestFolder]:
    name = (folder_name or "").strip()
    if not name:
        return None
    existing = await db.execute(select(TestFolder).where(TestFolder.name == name))
    folder = existing.scalar_one_or_none()
    if folder:
        return folder
    folder = TestFolder(name=name)
    db.add(folder)
    await db.flush()
    return folder
