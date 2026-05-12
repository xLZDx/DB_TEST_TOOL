from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

import pytest

from task_repeat.core.recorder import Recorder


class _FakeListenerPair:
    def __init__(
        self,
        on_move: Callable | None,
        on_click: Callable | None,
        on_scroll: Callable | None,
        on_press: Callable | None,
        on_release: Callable | None,
    ) -> None:
        self.on_move = on_move
        self.on_click = on_click
        self.on_scroll = on_scroll
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def _make_clock():
    t = [0.0]

    def clock() -> float:
        return t[0]

    def advance(delta: float) -> None:
        t[0] += delta

    return clock, advance


def test_recorder_captures_mouse_events_in_order() -> None:
    pair: list[_FakeListenerPair] = []

    def factory(**kwargs) -> _FakeListenerPair:
        p = _FakeListenerPair(**kwargs)
        pair.append(p)
        return p

    clock, advance = _make_clock()
    rec = Recorder(listener_factory=factory, capture_keyboard=False, clock=clock)
    rec.start()
    assert rec.recording is True
    listener = pair[0]
    assert listener.started

    advance(0.1)
    listener.on_move(10, 20)
    advance(0.2)
    listener.on_click(10, 20, SimpleNamespace(name="left"), True)
    advance(0.05)
    listener.on_click(10, 20, SimpleNamespace(name="left"), False)
    advance(0.1)
    listener.on_scroll(15, 25, 0, -1)

    macro = rec.stop()
    assert listener.stopped is True
    assert rec.recording is False
    assert len(macro.events) == 4
    assert macro.events[0].type == "move"
    assert macro.events[0].t == pytest.approx(0.1, abs=1e-6)
    assert macro.events[1].type == "click" and macro.events[1].pressed is True
    assert macro.events[2].pressed is False
    assert macro.events[3].type == "scroll" and macro.events[3].dy == -1


def test_recorder_keyboard_disabled_by_default() -> None:
    pair: list[_FakeListenerPair] = []

    def factory(**kwargs) -> _FakeListenerPair:
        p = _FakeListenerPair(**kwargs)
        pair.append(p)
        return p

    rec = Recorder(listener_factory=factory, capture_keyboard=False)
    rec.start()
    assert pair[0].on_press is None
    assert pair[0].on_release is None
    rec.stop()


def test_recorder_keyboard_enabled() -> None:
    pair: list[_FakeListenerPair] = []

    def factory(**kwargs) -> _FakeListenerPair:
        p = _FakeListenerPair(**kwargs)
        pair.append(p)
        return p

    clock, advance = _make_clock()
    rec = Recorder(listener_factory=factory, capture_keyboard=True, clock=clock)
    rec.start()
    listener = pair[0]
    advance(0.1)
    listener.on_press(SimpleNamespace(char="a"))
    advance(0.1)
    listener.on_release(SimpleNamespace(char="a"))
    macro = rec.stop()
    assert macro.events[0].type == "key_press"
    assert macro.events[0].key == "a"
    assert macro.events[1].type == "key_release"


def test_recorder_stop_when_not_running_is_safe() -> None:
    def factory(**kwargs) -> _FakeListenerPair:
        return _FakeListenerPair(**kwargs)

    rec = Recorder(listener_factory=factory, capture_keyboard=False)
    macro = rec.stop()
    assert macro.events == []
