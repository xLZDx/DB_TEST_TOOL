from __future__ import annotations

import queue
import time
from typing import Callable

from task_repeat.core.macro import Event, Macro


class Recorder:
    def __init__(
        self,
        listener_factory: Callable[..., "ListenerPair"],
        capture_keyboard: bool = False,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._factory = listener_factory
        self._capture_keyboard = capture_keyboard
        self._clock = clock
        self._queue: queue.Queue[Event] = queue.Queue()
        self._listeners: ListenerPair | None = None
        self._t0: float | None = None
        self._recording = False

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def capture_keyboard(self) -> bool:
        return self._capture_keyboard

    def start(self) -> None:
        if self._recording:
            return
        self._queue = queue.Queue()
        self._t0 = self._clock()
        self._listeners = self._factory(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
            on_press=self._on_press if self._capture_keyboard else None,
            on_release=self._on_release if self._capture_keyboard else None,
        )
        self._listeners.start()
        self._recording = True

    def stop(self) -> Macro:
        if not self._recording:
            return Macro(events=[])
        self._listeners.stop()
        self._listeners = None
        self._recording = False
        events: list[Event] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return Macro(events=events)

    def _t(self) -> float:
        if self._t0 is None:
            return 0.0
        return self._clock() - self._t0

    def _on_move(self, x: int, y: int) -> None:
        self._queue.put(Event(t=self._t(), type="move", x=int(x), y=int(y)))

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        self._queue.put(
            Event(
                t=self._t(),
                type="click",
                x=int(x),
                y=int(y),
                button=_button_name(button),
                pressed=bool(pressed),
            )
        )

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._queue.put(
            Event(t=self._t(), type="scroll", x=int(x), y=int(y), dx=int(dx), dy=int(dy))
        )

    def _on_press(self, key) -> None:
        self._queue.put(Event(t=self._t(), type="key_press", key=_key_repr(key)))

    def _on_release(self, key) -> None:
        self._queue.put(Event(t=self._t(), type="key_release", key=_key_repr(key)))


class ListenerPair:
    def start(self) -> None: ...
    def stop(self) -> None: ...


def _button_name(button) -> str:
    name = getattr(button, "name", None)
    if name in ("left", "right", "middle"):
        return name
    s = str(button).rsplit(".", 1)[-1]
    return s if s in ("left", "right", "middle") else "left"


def _key_repr(key) -> str:
    char = getattr(key, "char", None)
    if char is not None:
        return char
    name = getattr(key, "name", None)
    if name:
        return name
    return str(key)
