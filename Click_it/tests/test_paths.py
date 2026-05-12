from __future__ import annotations

from pathlib import Path

import pytest

from task_repeat.utils import paths as paths_mod

_real_assert_on_d_drive = paths_mod.assert_on_d_drive
_real_macros_dir = paths_mod.macros_dir


def test_macros_dir_creates() -> None:
    d = _real_macros_dir()
    assert d.exists()
    assert d.is_dir()
    assert d.name == "macros"


class _FakePath:
    def __init__(self, drive: str) -> None:
        self._drive = drive

    def resolve(self) -> "_FakePath":
        return self

    @property
    def drive(self) -> str:
        return self._drive

    def __str__(self) -> str:
        return f"{self._drive}\\fake.json"


def test_assert_on_d_drive_blocks_c() -> None:
    with pytest.raises(RuntimeError, match="C:"):
        _real_assert_on_d_drive(_FakePath("C:"))


def test_assert_on_d_drive_allows_d() -> None:
    _real_assert_on_d_drive(_FakePath("D:"))
    _real_assert_on_d_drive(_FakePath("E:"))


def test_assert_on_d_drive_blocks_unc() -> None:
    with pytest.raises(RuntimeError, match="UNC|non-fixed"):
        _real_assert_on_d_drive(_FakePath(""))
