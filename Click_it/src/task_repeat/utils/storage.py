from __future__ import annotations

import json
import os
from pathlib import Path

from task_repeat.core.macro import Macro
from task_repeat.utils.paths import assert_on_d_drive


MAX_EVENTS_PER_MACRO = 50_000


def save_macro(macro: Macro, path: Path) -> None:
    path = Path(path)
    assert_on_d_drive(path)
    if len(macro.events) > MAX_EVENTS_PER_MACRO:
        raise ValueError(
            f"Macro has {len(macro.events)} events; max is {MAX_EVENTS_PER_MACRO}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    assert_on_d_drive(tmp)
    payload = json.dumps(macro.to_dict(), indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_macro(path: Path) -> Macro:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    macro = Macro.from_dict(data)
    if len(macro.events) > MAX_EVENTS_PER_MACRO:
        raise ValueError(
            f"Macro has {len(macro.events)} events; max is {MAX_EVENTS_PER_MACRO}"
        )
    return macro
