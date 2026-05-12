from __future__ import annotations

import time

import pytest

from task_repeat.core.autoclicker import (
    AutoClicker,
    ClickConfig,
    MIN_INTERVAL_SECONDS,
    interval_from_hms_ms,
)


def test_interval_from_hms_ms_basic() -> None:
    assert interval_from_hms_ms(0, 0, 1, 0) == 1.0
    assert interval_from_hms_ms(0, 0, 0, 250) == pytest.approx(0.25)
    assert interval_from_hms_ms(1, 2, 3, 4) == pytest.approx(3723.004)


def test_interval_rejects_negative() -> None:
    with pytest.raises(ValueError):
        interval_from_hms_ms(0, 0, -1, 0)


def test_autoclicker_runs_repeat_count(fake_mouse, fake_button_module) -> None:
    cfg = ClickConfig(interval_seconds=0.01, button="left", click_count=1, repeat_count=5)
    clicker = AutoClicker(
        cfg, fake_mouse, fake_button_module, sleep_fn=lambda _s: None
    )
    clicker.start()
    deadline = time.time() + 2.0
    while clicker.running and time.time() < deadline:
        time.sleep(0.01)
    assert not clicker.running, "AutoClicker should have stopped after repeat_count"
    clicks = [c for c in fake_mouse.calls if c[0] == "click"]
    assert len(clicks) == 5
    assert clicks[0][1] == ("left", 1, (0, 0))


def test_autoclicker_double_click(fake_mouse, fake_button_module) -> None:
    cfg = ClickConfig(
        interval_seconds=0.01, button="right", click_count=2, repeat_count=2
    )
    clicker = AutoClicker(cfg, fake_mouse, fake_button_module, sleep_fn=lambda _s: None)
    clicker.start()
    deadline = time.time() + 1.0
    while clicker.running and time.time() < deadline:
        time.sleep(0.01)
    clicks = [c for c in fake_mouse.calls if c[0] == "click"]
    assert all(c[1][0] == "right" and c[1][1] == 2 for c in clicks)
    assert len(clicks) == 2


def test_autoclicker_stop_event_breaks_loop(fake_mouse, fake_button_module) -> None:
    cfg = ClickConfig(interval_seconds=0.01, button="left", click_count=1, repeat_count=0)
    clicker = AutoClicker(cfg, fake_mouse, fake_button_module, sleep_fn=lambda _s: None)
    clicker.start()
    time.sleep(0.05)
    clicker.stop(timeout=1.0)
    assert not clicker.running
    before = clicker.click_count_so_far
    time.sleep(0.05)
    assert clicker.click_count_so_far == before


def test_autoclicker_rejects_interval_below_min(fake_mouse, fake_button_module) -> None:
    with pytest.raises(ValueError, match="below minimum"):
        AutoClicker(
            ClickConfig(interval_seconds=MIN_INTERVAL_SECONDS / 2),
            fake_mouse,
            fake_button_module,
        )


def test_autoclicker_rejects_bad_click_count(fake_mouse, fake_button_module) -> None:
    with pytest.raises(ValueError, match="click_count"):
        AutoClicker(
            ClickConfig(interval_seconds=0.05, click_count=3),
            fake_mouse,
            fake_button_module,
        )


def test_autoclicker_rejects_unknown_button(fake_mouse, fake_button_module) -> None:
    with pytest.raises(ValueError, match="button"):
        AutoClicker(
            ClickConfig(interval_seconds=0.05, button="ghost"),
            fake_mouse,
            fake_button_module,
        )


def test_autoclicker_uses_target_position(fake_mouse, fake_button_module) -> None:
    cfg = ClickConfig(
        interval_seconds=0.01,
        button="left",
        click_count=1,
        repeat_count=2,
        use_current_position=False,
        target_x=400,
        target_y=500,
    )
    clicker = AutoClicker(cfg, fake_mouse, fake_button_module, sleep_fn=lambda _s: None)
    clicker.start()
    deadline = time.time() + 1.0
    while clicker.running and time.time() < deadline:
        time.sleep(0.01)
    clicks = [c for c in fake_mouse.calls if c[0] == "click"]
    assert all(c[1][2] == (400, 500) for c in clicks)
