from __future__ import annotations

import time

import pytest

from task_repeat.core.macro import Event, Macro
from task_repeat.core.player import MAX_LOOPS, MAX_SPEED, MIN_SPEED, PlayConfig, Player


def _wait_until_stopped(player: Player, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while player.running and time.time() < deadline:
        time.sleep(0.005)


def test_player_replays_mouse_events(fake_mouse, fake_button_module, fake_keyboard) -> None:
    macro = Macro(
        events=[
            Event(t=0.0, type="move", x=10, y=20),
            Event(t=0.05, type="click", x=10, y=20, button="left", pressed=True),
            Event(t=0.06, type="click", x=10, y=20, button="left", pressed=False),
        ]
    )
    cfg = PlayConfig(speed=1.0, loop_count=2)
    player = Player(
        macro=macro,
        config=cfg,
        mouse_controller=fake_mouse,
        button_module=fake_button_module,
        keyboard_controller=fake_keyboard,
        sleep_fn=lambda _s: None,
    )
    player.start()
    _wait_until_stopped(player)
    assert fake_mouse.position == (10, 20)
    presses = [c for c in fake_mouse.calls if c[0] == "press"]
    releases = [c for c in fake_mouse.calls if c[0] == "release"]
    assert len(presses) == 2 and len(releases) == 2
    assert all(p[1][0] == "left" for p in presses)
    assert player.events_played == 6


def test_player_speed_scales_sleeps(fake_mouse, fake_button_module) -> None:
    sleeps: list[float] = []
    macro = Macro(
        events=[
            Event(t=0.0, type="move", x=0, y=0),
            Event(t=1.0, type="move", x=1, y=1),
        ]
    )
    cfg = PlayConfig(speed=2.0, loop_count=1)
    player = Player(
        macro=macro,
        config=cfg,
        mouse_controller=fake_mouse,
        button_module=fake_button_module,
        sleep_fn=sleeps.append,
    )
    player.start()
    _wait_until_stopped(player)
    nonzero = [s for s in sleeps if s > 0]
    assert nonzero, "expected at least one positive sleep"
    assert nonzero[0] == pytest.approx(0.5, abs=1e-6)


def test_player_keyboard_skipped_when_disabled(
    fake_mouse, fake_button_module, fake_keyboard
) -> None:
    macro = Macro(events=[Event(t=0.0, type="key_press", key="a")])
    cfg = PlayConfig(speed=1.0, loop_count=1, capture_keyboard=False)
    player = Player(
        macro=macro,
        config=cfg,
        mouse_controller=fake_mouse,
        button_module=fake_button_module,
        keyboard_controller=fake_keyboard,
        sleep_fn=lambda _s: None,
    )
    player.start()
    _wait_until_stopped(player)
    assert fake_keyboard.calls == []


def test_player_keyboard_replays_when_enabled(
    fake_mouse, fake_button_module, fake_keyboard
) -> None:
    macro = Macro(
        events=[
            Event(t=0.0, type="key_press", key="x"),
            Event(t=0.0, type="key_release", key="x"),
        ]
    )
    cfg = PlayConfig(speed=1.0, loop_count=1, capture_keyboard=True)
    player = Player(
        macro=macro,
        config=cfg,
        mouse_controller=fake_mouse,
        button_module=fake_button_module,
        keyboard_controller=fake_keyboard,
        sleep_fn=lambda _s: None,
    )
    player.start()
    _wait_until_stopped(player)
    assert fake_keyboard.calls == [("press", "x"), ("release", "x")]


def test_player_rejects_speed_out_of_range(fake_mouse, fake_button_module) -> None:
    macro = Macro(events=[])
    with pytest.raises(ValueError, match="speed"):
        Player(
            macro=macro,
            config=PlayConfig(speed=MAX_SPEED + 0.1, loop_count=1),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )
    with pytest.raises(ValueError, match="speed"):
        Player(
            macro=macro,
            config=PlayConfig(speed=MIN_SPEED - 0.01, loop_count=1),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )


def test_player_rejects_loop_out_of_range(fake_mouse, fake_button_module) -> None:
    macro = Macro(events=[])
    with pytest.raises(ValueError, match="loop_count"):
        Player(
            macro=macro,
            config=PlayConfig(speed=1.0, loop_count=MAX_LOOPS + 1),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )
    with pytest.raises(ValueError, match="loop_count"):
        Player(
            macro=macro,
            config=PlayConfig(speed=1.0, loop_count=0),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )


def test_player_rejects_unknown_button_at_construction(
    fake_mouse, fake_button_module
) -> None:
    macro = Macro(
        events=[Event(t=0.0, type="click", x=0, y=0, button="ghost", pressed=True)]
    )
    with pytest.raises(ValueError, match="unknown button"):
        Player(
            macro=macro,
            config=PlayConfig(speed=1.0, loop_count=1),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )


def test_player_rejects_unknown_event_type_at_construction(
    fake_mouse, fake_button_module
) -> None:
    macro = Macro(events=[Event(t=0.0, type="quantum_tunneling")])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown type"):
        Player(
            macro=macro,
            config=PlayConfig(speed=1.0, loop_count=1),
            mouse_controller=fake_mouse,
            button_module=fake_button_module,
        )


def test_player_stop_event_interrupts(fake_mouse, fake_button_module) -> None:
    macro = Macro(
        events=[Event(t=0.01 * i, type="move", x=i, y=i) for i in range(200)]
    )
    cfg = PlayConfig(speed=1.0, loop_count=1)
    player = Player(
        macro=macro,
        config=cfg,
        mouse_controller=fake_mouse,
        button_module=fake_button_module,
        sleep_fn=lambda _s: time.sleep(0.005),
    )
    player.start()
    time.sleep(0.03)
    player.stop(timeout=1.0)
    assert not player.running
    assert player.events_played < 200
