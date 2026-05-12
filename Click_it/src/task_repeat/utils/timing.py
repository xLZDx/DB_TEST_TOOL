from __future__ import annotations

import platform
import time

_TIMER_ACTIVE = False


def boost_timer_resolution() -> None:
    global _TIMER_ACTIVE
    if _TIMER_ACTIVE or platform.system() != "Windows":
        return
    try:
        import ctypes
        ctypes.WinDLL("winmm").timeBeginPeriod(1)
        _TIMER_ACTIVE = True
    except (OSError, AttributeError):
        pass


def release_timer_resolution() -> None:
    global _TIMER_ACTIVE
    if not _TIMER_ACTIVE or platform.system() != "Windows":
        return
    try:
        import ctypes
        ctypes.WinDLL("winmm").timeEndPeriod(1)
    except (OSError, AttributeError):
        pass
    finally:
        _TIMER_ACTIVE = False


def precise_sleep(seconds: float) -> None:
    if seconds <= 0:
        return
    target = time.perf_counter() + seconds
    coarse = seconds - 0.002
    if coarse > 0:
        time.sleep(coarse)
    while time.perf_counter() < target:
        time.sleep(0)
