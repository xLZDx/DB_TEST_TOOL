from __future__ import annotations

from typing import Callable


VALID_FUNCTION_KEYS = tuple(f"F{i}" for i in range(1, 13))


def to_hotkey_string(modifier: str, key: str) -> str:
    if modifier.lower() != "ctrl":
        raise ValueError("Only Ctrl modifier is supported (matches template)")
    if key not in VALID_FUNCTION_KEYS:
        raise ValueError(f"Key must be one of {VALID_FUNCTION_KEYS}, got {key!r}")
    return f"<ctrl>+<{key.lower()}>"


class HotkeyManager:
    def __init__(self, hotkey_class) -> None:
        self._hotkey_class = hotkey_class
        self._handle = None

    @property
    def active(self) -> bool:
        return self._handle is not None

    def install(
        self,
        start_combo: str,
        stop_combo: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        if start_combo == stop_combo:
            raise ValueError("Start and stop hotkeys must differ")
        self.uninstall()
        mapping = {start_combo: on_start, stop_combo: on_stop}
        self._handle = self._hotkey_class(mapping)
        self._handle.start()

    def uninstall(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.stop()
        finally:
            self._handle = None
