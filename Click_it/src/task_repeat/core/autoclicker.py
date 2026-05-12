from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from task_repeat.utils.timing import precise_sleep


class MouseControllerLike(Protocol):
    def click(self, button, count: int = 1) -> None: ...
    def position(self) -> tuple[int, int]: ...
    def __setattr__(self, name: str, value) -> None: ...


@dataclass
class ClickConfig:
    interval_seconds: float
    button: str = "left"
    click_count: int = 1
    use_current_position: bool = True
    target_x: int = 0
    target_y: int = 0
    repeat_count: int = 0


MIN_INTERVAL_SECONDS = 0.010
MAX_REPEAT = 10_000_000


def _resolve_button(controller_module, name: str):
    table = {
        "left": controller_module.Button.left,
        "right": controller_module.Button.right,
        "middle": controller_module.Button.middle,
    }
    if name not in table:
        raise ValueError(f"Unknown button: {name!r}")
    return table[name]


class AutoClicker:
    def __init__(
        self,
        config: ClickConfig,
        controller,
        button_module,
        on_tick: Callable[[int], None] | None = None,
        on_stop: Callable[[int], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if config.interval_seconds < MIN_INTERVAL_SECONDS:
            raise ValueError(
                f"Interval {config.interval_seconds:.4f}s below minimum "
                f"{MIN_INTERVAL_SECONDS:.3f}s"
            )
        if config.repeat_count < 0 or config.repeat_count > MAX_REPEAT:
            raise ValueError(f"repeat_count out of range: {config.repeat_count}")
        if config.click_count not in (1, 2):
            raise ValueError(f"click_count must be 1 or 2, got {config.click_count}")
        self._config = config
        self._controller = controller
        self._button = _resolve_button(button_module, config.button)
        self._on_tick = on_tick
        self._on_stop = on_stop
        self._sleep = sleep_fn or precise_sleep
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._count = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def click_count_so_far(self) -> int:
        return self._count

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._count = 0
        self._thread = threading.Thread(
            target=self._run, name="AutoClicker", daemon=False
        )
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=timeout)
        if t is None or not t.is_alive():
            self._thread = None

    def _run(self) -> None:
        cfg = self._config
        try:
            while not self._stop_event.is_set():
                if not cfg.use_current_position:
                    self._controller.position = (cfg.target_x, cfg.target_y)
                self._controller.click(self._button, cfg.click_count)
                self._count += 1
                if self._on_tick is not None:
                    self._on_tick(self._count)
                if cfg.repeat_count and self._count >= cfg.repeat_count:
                    break
                if self._stop_event.is_set():
                    break
                self._sleep(cfg.interval_seconds)
        finally:
            if self._on_stop is not None:
                self._on_stop(self._count)


def interval_from_hms_ms(hours: int, minutes: int, seconds: int, ms: int) -> float:
    if any(v < 0 for v in (hours, minutes, seconds, ms)):
        raise ValueError("Interval components must be non-negative")
    total = hours * 3600 + minutes * 60 + seconds + ms / 1000.0
    return total
