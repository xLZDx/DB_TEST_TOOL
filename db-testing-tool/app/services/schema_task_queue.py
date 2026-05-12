"""Schema task queue — real asyncio background task implementation."""
from __future__ import annotations
import asyncio
import logging
import threading
from collections import deque
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# In-process task registry  {operation_id: asyncio.Task}
_active_tasks: dict[str, asyncio.Task] = {}
_queue: deque = deque()
_lock = threading.Lock()


async def ensure_schema_task_workers() -> None:
    """No-op — tasks run as individual asyncio Tasks, no persistent workers needed."""
    pass


async def enqueue_schema_task(
    operation_id: str,
    label: str,
    fn: Callable,
    *args: Any,
    **kwargs: Any,
) -> int:
    """Schedule fn() as a background asyncio Task and return current active count."""
    logger.info("enqueue_schema_task: scheduling %s (op=%s) in background", label, operation_id)

    async def _wrapper():
        try:
            result = fn(*args, **kwargs)
            # Support both coroutines and plain callables
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # noqa: BLE001
            logger.error("Background task %s failed: %s", label, exc, exc_info=True)
        finally:
            with _lock:
                _active_tasks.pop(operation_id, None)

    loop = asyncio.get_event_loop()
    task = loop.create_task(_wrapper())
    with _lock:
        _active_tasks[operation_id] = task

    return len(_active_tasks)


def get_queue_depth() -> int:
    """Return number of actively running background tasks."""
    return len(_active_tasks)


def get_queue_health() -> dict:
    """Return health payload for the background task system."""
    with _lock:
        active = list(_active_tasks.keys())
    return {
        "status": "ok",
        "queue_depth": len(active),
        "worker_count": len(active),
        "active_workers": len(active),
        "active_operation_ids": active,
        "workers_started": len(active) > 0,
    }
