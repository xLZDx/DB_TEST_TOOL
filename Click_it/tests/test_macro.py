from __future__ import annotations

import json
from pathlib import Path

import pytest

from task_repeat.core.macro import Event, Macro
from task_repeat.utils.storage import MAX_EVENTS_PER_MACRO, load_macro, save_macro


def test_macro_round_trip(tmp_path: Path) -> None:
    macro = Macro(
        events=[
            Event(t=0.0, type="move", x=10, y=20),
            Event(t=0.5, type="click", x=10, y=20, button="left", pressed=True),
            Event(t=0.6, type="click", x=10, y=20, button="left", pressed=False),
            Event(t=1.0, type="scroll", x=10, y=20, dx=0, dy=-1),
        ]
    )
    path = tmp_path / "m.json"
    save_macro(macro, path)
    loaded = load_macro(path)
    assert loaded.version == 1
    assert len(loaded.events) == 4
    assert loaded.events[1].type == "click"
    assert loaded.events[1].button == "left"
    assert loaded.events[1].pressed is True
    assert loaded.events[3].dy == -1


def test_save_uses_atomic_replace(tmp_path: Path) -> None:
    macro = Macro(events=[Event(t=0.0, type="move", x=1, y=1)])
    path = tmp_path / "m.json"
    save_macro(macro, path)
    assert not (path.with_suffix(path.suffix + ".tmp")).exists()
    assert path.exists()


def test_load_rejects_wrong_version(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 99, "events": []}))
    with pytest.raises(ValueError, match="version"):
        load_macro(path)


def test_load_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        load_macro(path)


def test_save_rejects_too_many_events(tmp_path: Path) -> None:
    macro = Macro(
        events=[Event(t=0.0, type="move", x=0, y=0)] * (MAX_EVENTS_PER_MACRO + 1)
    )
    with pytest.raises(ValueError, match="max"):
        save_macro(macro, tmp_path / "big.json")


def test_event_to_dict_drops_unused_fields() -> None:
    ev = Event(t=1.0, type="move", x=5, y=6)
    d = ev.to_dict()
    assert d == {"t": 1.0, "type": "move", "x": 5, "y": 6}
    assert "button" not in d and "pressed" not in d and "key" not in d


def test_load_rejects_unknown_event_type(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1, "events": [{"t": 0.0, "type": "../etc/passwd"}]}))
    with pytest.raises(ValueError, match="unknown type"):
        load_macro(path)


def test_load_rejects_unknown_button(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {"version": 1, "events": [{"t": 0.0, "type": "click", "button": "evil"}]}
        )
    )
    with pytest.raises(ValueError, match="unknown button"):
        load_macro(path)


def test_load_rejects_non_dict_event(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1, "events": ["not_an_object"]}))
    with pytest.raises(ValueError, match="must be an object"):
        load_macro(path)


def test_load_rejects_non_numeric_t(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"version": 1, "events": [{"t": "abc", "type": "move"}]})
    )
    with pytest.raises(ValueError, match="invalid field"):
        load_macro(path)
