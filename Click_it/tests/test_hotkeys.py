from __future__ import annotations

import pytest

from task_repeat.core.hotkeys import HotkeyManager, to_hotkey_string


class _FakeGlobalHotKeys:
    instances: list["_FakeGlobalHotKeys"] = []

    def __init__(self, mapping: dict) -> None:
        self.mapping = mapping
        self.started = False
        self.stopped = False
        _FakeGlobalHotKeys.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_to_hotkey_string_valid() -> None:
    assert to_hotkey_string("ctrl", "F2") == "<ctrl>+<f2>"
    assert to_hotkey_string("Ctrl", "F12") == "<ctrl>+<f12>"


def test_to_hotkey_string_rejects_bad_modifier() -> None:
    with pytest.raises(ValueError, match="Ctrl"):
        to_hotkey_string("shift", "F2")


def test_to_hotkey_string_rejects_bad_key() -> None:
    with pytest.raises(ValueError, match="F1"):
        to_hotkey_string("ctrl", "A")


def test_hotkey_manager_install_and_uninstall() -> None:
    _FakeGlobalHotKeys.instances.clear()
    mgr = HotkeyManager(_FakeGlobalHotKeys)
    started_calls = []
    stopped_calls = []
    mgr.install(
        "<ctrl>+<f2>",
        "<ctrl>+<f3>",
        on_start=lambda: started_calls.append(1),
        on_stop=lambda: stopped_calls.append(1),
    )
    assert mgr.active is True
    inst = _FakeGlobalHotKeys.instances[-1]
    assert inst.started is True
    inst.mapping["<ctrl>+<f2>"]()
    inst.mapping["<ctrl>+<f3>"]()
    assert started_calls == [1] and stopped_calls == [1]
    mgr.uninstall()
    assert mgr.active is False
    assert inst.stopped is True


def test_hotkey_manager_rejects_identical_combos() -> None:
    mgr = HotkeyManager(_FakeGlobalHotKeys)
    with pytest.raises(ValueError, match="differ"):
        mgr.install(
            "<ctrl>+<f2>", "<ctrl>+<f2>", on_start=lambda: None, on_stop=lambda: None
        )


def test_hotkey_manager_reinstall_replaces_previous() -> None:
    _FakeGlobalHotKeys.instances.clear()
    mgr = HotkeyManager(_FakeGlobalHotKeys)
    mgr.install("<ctrl>+<f2>", "<ctrl>+<f3>", on_start=lambda: None, on_stop=lambda: None)
    first = _FakeGlobalHotKeys.instances[-1]
    mgr.install("<ctrl>+<f4>", "<ctrl>+<f5>", on_start=lambda: None, on_stop=lambda: None)
    assert first.stopped is True
    assert len(_FakeGlobalHotKeys.instances) == 2
