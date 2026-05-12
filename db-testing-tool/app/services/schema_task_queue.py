"""Schema task queue service stub."""
from __future__ import annotations
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


async def ensure_schema_task_workers() -> None:
    """Stub: ensure schema task workers are running (no-op)."""
    logger.info("Schema task queue: stub (no-op)")


async def enqueue_schema_task(
    operation_id: str,
    label: str,
    fn: Callable,
    *args: Any,
    **kwargs: Any,
) -> int:
    """Stub: enqueue a background schema task.

    Immediately runs the callable inline and returns queue depth 0.
    """
    logger.info("enqueue_schema_task: running %s inline (stub)", label)
    try:
        await fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("enqueue_schema_task inline run failed: %s", exc)
    return 0


def get_queue_depth() -> int:
    """Stub: always returns 0."""
    return 0


def get_queue_health() -> dict:
    """Stub: returns a minimal health payload."""
    return {"status": "ok", "depth": 0, "workers": 0, "stub": True}
