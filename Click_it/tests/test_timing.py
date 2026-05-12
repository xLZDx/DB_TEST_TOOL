from __future__ import annotations

import time

from task_repeat.utils import timing


def test_precise_sleep_nonneg() -> None:
    timing.precise_sleep(0)
    timing.precise_sleep(-0.5)


def test_precise_sleep_close_to_target() -> None:
    target = 0.05
    start = time.perf_counter()
    timing.precise_sleep(target)
    elapsed = time.perf_counter() - start
    assert elapsed >= target - 0.005
    assert elapsed < target + 0.060


def test_timer_resolution_boost_idempotent() -> None:
    timing.boost_timer_resolution()
    timing.boost_timer_resolution()
    timing.release_timer_resolution()
    timing.release_timer_resolution()
