"""Background automation loop for replaying saved training packs."""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.database import async_session
from app.models.agent_profile import AgentProfile
from app.services.agent_service import build_combined_agent_prompt
from app.services.ai_service import ai_chat


TRAINING_PACK_ROOT = Path(__file__).resolve().parents[2] / "training_packs"
STATE_FILE = TRAINING_PACK_ROOT / "training_automation_state.json"
RUNS_FILE = TRAINING_PACK_ROOT / "training_automation_runs.jsonl"

_DEFAULT_CONFIG = {
    "interval_seconds": 600,
    "mode": "ghc",
    "agent_id": None,
    "target_table": "",
    "max_packs_per_cycle": 3,
}
_STATE: Dict[str, Any] = {
    "enabled": False,
    "running": False,
    "config": dict(_DEFAULT_CONFIG),
    "last_run_at": None,
    "last_error": "",
    "last_result": {},
    "processed": {},
}
_LOOP_TASK: Optional[asyncio.Task] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_root() -> None:
    TRAINING_PACK_ROOT.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    _ensure_root()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _normalize_sql(sql_text: str) -> str:
    return re.sub(r"\s+", " ", (sql_text or "").strip()).upper()


def _pack_signature(pack_dir: Path) -> str:
    parts: List[str] = []
    for name in ("metadata.json", "reference.sql", "validation.sql"):
        path = pack_dir / name
        if not path.exists():
            continue
        stat = path.stat()
        parts.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _normalize_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged = dict(_DEFAULT_CONFIG)
    merged.update(config or {})
    merged["interval_seconds"] = max(30, int(merged.get("interval_seconds") or 600))
    merged["max_packs_per_cycle"] = max(1, min(25, int(merged.get("max_packs_per_cycle") or 3)))
    merged["mode"] = "local" if str(merged.get("mode") or "").strip().lower() == "local" else "ghc"
    merged["agent_id"] = int(merged["agent_id"]) if merged.get("agent_id") else None
    merged["target_table"] = str(merged.get("target_table") or "").strip().upper()
    return merged


def _persist_state() -> None:
    payload = {
        "enabled": bool(_STATE.get("enabled")),
        "running": bool(_STATE.get("running")),
        "config": _normalize_config(_STATE.get("config") or {}),
        "last_run_at": _STATE.get("last_run_at"),
        "last_error": _STATE.get("last_error") or "",
        "last_result": _STATE.get("last_result") or {},
        "processed": _STATE.get("processed") or {},
    }
    _write_json(STATE_FILE, payload)


def _load_state() -> None:
    payload = _read_json(STATE_FILE, {})
    if not isinstance(payload, dict):
        return
    _STATE["enabled"] = bool(payload.get("enabled"))
    _STATE["running"] = False
    _STATE["config"] = _normalize_config(payload.get("config") or {})
    _STATE["last_run_at"] = payload.get("last_run_at")
    _STATE["last_error"] = payload.get("last_error") or ""
    _STATE["last_result"] = payload.get("last_result") or {}
    _STATE["processed"] = payload.get("processed") or {}


def _candidate_pack_dirs(config: Dict[str, Any]) -> List[Path]:
    _ensure_root()
    target_table = config.get("target_table") or ""
    packs: List[Path] = []
    for item in TRAINING_PACK_ROOT.iterdir():
        if not item.is_dir() or not (item / "metadata.json").exists():
            continue
        if target_table:
            metadata = _read_json(item / "metadata.json", {})
            if str(metadata.get("target_table") or "").strip().upper() != target_table:
                continue
        packs.append(item)
    packs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return packs


async def _resolve_agent_prompt(agent_id: Optional[int]) -> str:
    if not agent_id:
        return ""
    async with async_session() as db:
        result = await db.execute(select(AgentProfile).where(AgentProfile.id == int(agent_id)))
        agent = result.scalar_one_or_none()
    if not agent:
        return ""
    return build_combined_agent_prompt([
        {
            "name": agent.name,
            "role": agent.role,
            "domains": agent.domains,
            "system_prompt": agent.system_prompt,
            "is_active": agent.is_active,
        }
    ], task_hint="background training replay")


async def _process_pack(pack_dir: Path, config: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _read_json(pack_dir / "metadata.json", {})
    reference_sql = _read_text(pack_dir / "reference.sql")
    validation_sql = _read_text(pack_dir / "validation.sql")
    signature = _pack_signature(pack_dir)
    pack_id = pack_dir.name

    if _STATE.get("processed", {}).get(pack_id) == signature:
        return {"pack_id": pack_id, "status": "skipped", "reason": "unchanged"}

    target_table = str(metadata.get("target_table") or "").strip().upper()
    source_tables = metadata.get("source_tables") or []
    normalized_match = bool(reference_sql and validation_sql and _normalize_sql(reference_sql) == _normalize_sql(validation_sql))

    ai_summary = ""
    ai_error = ""
    if reference_sql or validation_sql:
        try:
            mode = config.get("mode") or "ghc"
            agent_prompt = await _resolve_agent_prompt(config.get("agent_id") if mode == "local" else None)
            context = json.dumps({
                "target_table": target_table,
                "source_tables": source_tables,
                "notes": metadata.get("notes") or "",
                "match_status": "match" if normalized_match else "mismatch",
            }, indent=2)
            prompt = (
                f"Review this saved SQL training pack for {target_table or 'the target table'}. "
                "Summarize reusable transformation patterns, likely failure modes, and concise remediation guidance.\n\n"
                f"Reference SQL:\n{reference_sql or '[missing]'}\n\n"
                f"Validation SQL:\n{validation_sql or '[missing]'}"
            )
            response = await ai_chat(
                [{"role": "user", "content": prompt}],
                context,
                "githubcopilot",
                agent_prompt,
                [],
            )
            ai_summary = str(response.get("message") or response.get("response") or response.get("content") or "").strip()
        except Exception as exc:
            ai_error = str(exc)

    record = {
        "created_at": _utc_now(),
        "pack_id": pack_id,
        "target_table": target_table,
        "source_tables": source_tables,
        "status": "processed",
        "normalized_match": normalized_match,
        "mode": config.get("mode") or "ghc",
        "agent_id": config.get("agent_id"),
        "notes": metadata.get("notes") or "",
        "ai_summary": ai_summary,
        "ai_error": ai_error,
    }
    _ensure_root()
    with RUNS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    _STATE.setdefault("processed", {})[pack_id] = signature
    return record


async def _run_single_cycle() -> Dict[str, Any]:
    config = _normalize_config(_STATE.get("config") or {})
    _STATE["config"] = config
    _STATE["running"] = True
    _STATE["last_error"] = ""

    processed_count = 0
    skipped_count = 0
    last_record: Dict[str, Any] = {}
    try:
        packs = _candidate_pack_dirs(config)
        for pack_dir in packs[: config.get("max_packs_per_cycle") or 3]:
            result = await _process_pack(pack_dir, config)
            last_record = result
            if result.get("status") == "processed":
                processed_count += 1
            else:
                skipped_count += 1
        summary = {
            "status": "completed",
            "processed_count": processed_count,
            "skipped_count": skipped_count,
            "target_table": config.get("target_table") or "",
            "last_pack": last_record.get("pack_id") or "",
        }
        _STATE["last_run_at"] = _utc_now()
        _STATE["last_result"] = summary
        return summary
    except Exception as exc:
        _STATE["last_error"] = str(exc)
        _STATE["last_result"] = {"status": "failed", "error": str(exc)}
        return _STATE["last_result"]
    finally:
        _STATE["running"] = False
        _persist_state()


async def _automation_loop() -> None:
    global _LOOP_TASK
    try:
        while _STATE.get("enabled"):
            await _run_single_cycle()
            interval = int((_STATE.get("config") or {}).get("interval_seconds") or 600)
            for _ in range(interval):
                if not _STATE.get("enabled"):
                    break
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        _STATE["running"] = False
        _LOOP_TASK = None
        _persist_state()


def get_training_automation_status() -> Dict[str, Any]:
    return {
        "enabled": bool(_STATE.get("enabled")),
        "running": bool(_STATE.get("running")),
        "config": _normalize_config(_STATE.get("config") or {}),
        "last_run_at": _STATE.get("last_run_at"),
        "last_error": _STATE.get("last_error") or "",
        "last_result": _STATE.get("last_result") or {},
    }


async def start_training_automation_loop(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    global _LOOP_TASK
    _load_state()
    _STATE["config"] = _normalize_config(config or _STATE.get("config") or {})
    _STATE["enabled"] = True
    _persist_state()
    if _LOOP_TASK is None or _LOOP_TASK.done():
        _LOOP_TASK = asyncio.create_task(_automation_loop(), name="training-automation-loop")
    return get_training_automation_status()


async def stop_training_automation_loop() -> Dict[str, Any]:
    global _LOOP_TASK
    _STATE["enabled"] = False
    if _LOOP_TASK is not None and not _LOOP_TASK.done():
        _LOOP_TASK.cancel()
        try:
            await _LOOP_TASK
        except asyncio.CancelledError:
            pass
    _LOOP_TASK = None
    _STATE["running"] = False
    _persist_state()
    return get_training_automation_status()


async def run_training_automation_cycle(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _load_state()
    if config:
        _STATE["config"] = _normalize_config(config)
    return await _run_single_cycle()


async def restore_training_automation_loop() -> None:
    _load_state()
    if _STATE.get("enabled"):
        await start_training_automation_loop(_STATE.get("config") or {})