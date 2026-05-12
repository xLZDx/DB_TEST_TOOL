from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def macros_dir() -> Path:
    d = project_root() / "data" / "macros"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assets_dir() -> Path:
    return project_root() / "assets"


def assert_on_d_drive(p: Path) -> None:
    drive = p.resolve().drive.upper()
    if drive == "C:":
        raise RuntimeError(
            f"Refusing to write to C:\\ (D:-drive-only policy). Path: {p}"
        )
    if not drive:
        raise RuntimeError(
            f"Refusing to write to non-fixed-drive path (UNC or no drive). Path: {p}"
        )
