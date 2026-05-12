from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from task_repeat.core.macro import Macro, VALID_BUTTON_NAMES, VALID_EVENT_TYPES
from task_repeat.utils.timing import precise_sleep


MIN_SPEED = 0.1
MAX_SPEED = 10.0
MAX_LOOPS = 10_000


@dataclass
class PlayConfig:
    speed: float = 1.0
    loop_count: int = 1
    capture_keyboard: bool = False


class Player:
    def __init__(
        self,
        macro: Macro,
        config: PlayConfig,
        mouse_controller,
        button_module,
        keyboard_controller=None,
        on_event: Callable[[int], None] | None = None,
        on_stop: Callable[[int], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if not (MIN_SPEED <= config.speed <= MAX_SPEED):
            raise ValueError(
                f"speed {config.speed} out of range [{MIN_SPEED}, {MAX_SPEED}]"
            )
        if not (1 <= config.loop_count <= MAX_LOOPS):
            raise ValueError(
                f"loop_count {config.loop_count} out of range [1, {MAX_LOOPS}]"
            )
        _validate_macro_for_replay(macro)
        self._macro = macro
        self._config = config
        self._mouse = mouse_controller
        self._button_module = button_module
        self._keyboard = keyboard_controller
        self._on_event = on_event
        self._on_stop = on_stop
        self._sleep = sleep_fn or precise_sleep
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._events_played = 0

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def events_played(self) -> int:
        return self._events_played

    def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._events_played = 0
        self._thread = threading.Thread(
            target=self._run, name="Player", daemon=False
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
        try:
            for _ in range(self._config.loop_count):
                if self._stop_event.is_set():
                    break
                self._play_once()
        finally:
            if self._on_stop is not None:
                self._on_stop(self._events_played)

    def _play_once(self) -> None:
        prev_t = 0.0
        for event in self._macro.events:
            if self._stop_event.is_set():
                return
            dt = max(0.0, event.t - prev_t) / self._config.speed
            if dt > 0:
                self._sleep(dt)
            self._dispatch(event)
            prev_t = event.t
            self._events_played += 1
            if self._on_event is not None:
                self._on_event(self._events_played)

    def _dispatch(self, event) -> None:
        if event.type == "move":
            self._mouse.position = (event.x, event.y)
        elif event.type == "click":
            self._mouse.position = (event.x, event.y)
            btn = _resolve_button(self._button_module, event.button or "left")
            if event.pressed:
                self._mouse.press(btn)
            else:
                self._mouse.release(btn)
        elif event.type == "scroll":
            self._mouse.position = (event.x, event.y)
            self._mouse.scroll(event.dx, event.dy)
        elif event.type == "key_press":
            if self._keyboard is not None and self._config.capture_keyboard:
                self._keyboard.press(event.key)
        elif event.type == "key_release":
            if self._keyboard is not None and self._config.capture_keyboard:
                self._keyboard.release(event.key)


def _resolve_button(button_module, name: str):
    table = {
        "left": button_module.Button.left,
        "right": button_module.Button.right,
        "middle": button_module.Button.middle,
    }
    if name not in table:
        raise ValueError(f"Unknown button in macro event: {name!r}")
    return table[name]


def _validate_macro_for_replay(macro: Macro) -> None:
    for i, event in enumerate(macro.events):
        if event.type not in VALID_EVENT_TYPES:
            raise ValueError(f"Event #{i}: unknown type {event.type!r}")
        if event.type == "click":
            btn = event.button or "left"
            if btn not in VALID_BUTTON_NAMES:
                raise ValueError(f"Event #{i}: unknown button {btn!r}")
