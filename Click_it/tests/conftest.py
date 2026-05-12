from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeButton:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Button.{self.name}"


class FakeButtonModule:
    Button = SimpleNamespace(
        left=FakeButton("left"),
        right=FakeButton("right"),
        middle=FakeButton("middle"),
    )


@pytest.fixture
def fake_button_module() -> FakeButtonModule:
    return FakeButtonModule()


class FakeMouseController:
    def __init__(self) -> None:
        self.position = (0, 0)
        self.calls: list[tuple[str, Any]] = []

    def click(self, button: FakeButton, count: int = 1) -> None:
        self.calls.append(("click", (button.name, count, self.position)))

    def press(self, button: FakeButton) -> None:
        self.calls.append(("press", (button.name, self.position)))

    def release(self, button: FakeButton) -> None:
        self.calls.append(("release", (button.name, self.position)))

    def scroll(self, dx: int, dy: int) -> None:
        self.calls.append(("scroll", (dx, dy, self.position)))


@pytest.fixture
def fake_mouse() -> FakeMouseController:
    return FakeMouseController()


class FakeKeyboardController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def press(self, key: str) -> None:
        self.calls.append(("press", key))

    def release(self, key: str) -> None:
        self.calls.append(("release", key))


@pytest.fixture
def fake_keyboard() -> FakeKeyboardController:
    return FakeKeyboardController()


@pytest.fixture
def macros_tmp_dir(tmp_path: Path) -> Path:
    d = tmp_path / "macros"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def stub_d_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    from task_repeat.utils import paths as paths_mod

    monkeypatch.setattr(paths_mod, "assert_on_d_drive", lambda p: None)
