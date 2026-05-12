# Task_Repeat

A small Tkinter utility for Windows that mimics the "Free Mouse Clicker" template. Two features:

1. **Auto-clicker** — fixed-interval clicks at the current mouse position. `H:M:S:ms` interval, `Left / Right / Middle Button × Single / Double Click`. Global hotkeys `Ctrl+F2` (start) and `Ctrl+F3` (stop) — configurable in the UI.
2. **Record / Replay macros** — opens from the `Macros` menu. Records mouse events (and optionally keyboard, off by default), saves to JSON, replays N times at 0.5×/1×/2× speed.

## Quick start

```powershell
# 1. install deps
python -m pip install -r requirements.txt

# 2. run from source
.\run.ps1

# 3. or build a one-file .exe
.\build.ps1
# -> dist\task_repeat.exe
```

## Hotkeys

- `Ctrl + F2` — start auto-clicker (configurable, `F1..F12`)
- `Ctrl + F3` — stop auto-clicker (configurable, `F1..F12`)

Hotkeys are global — they work even when the Task_Repeat window is not focused.

## Macros

- Menu `Macros → Open Macros window` opens the record/replay dialog.
- **Record / Stop** capture mouse moves, clicks, and scrolls. Keyboard capture is off by default; enabling it shows a warning that keystrokes (including passwords) will be recorded.
- **Save / Load** round-trips through a JSON file (default location: `data/macros/`).
- **Replay** runs the macro `loop` times at the selected speed. Hard caps: max **10,000 loops**, speed **0.1×–10×**, max **50,000 events** per macro file.

## Safety

- Keyboard recording is **off** every session and only turns on after you confirm a warning modal.
- Macros are stored as plain JSON. Treat saved macros that captured keyboard like passwords — don't commit them.
- No network calls. No telemetry. Everything stays on disk.

## Disk policy

Per the operator's global disk policy, all installs and build artifacts stay on `D:\` or above — `C:\` is off-limits. The build script aborts if you try to build from `C:\`. Atomic writes use same-drive temp files so cross-device renames never fall back to `C:\`.

## Tests

```powershell
$env:PYTHONPATH = "src"
pytest tests/ -v
```

All tests mock `pynput` — no test ever moves the real mouse or watches the real keyboard.

## Layout

```
src/task_repeat/
  app.py                 # root Tk window + wiring
  __main__.py            # python -m task_repeat
  core/
    autoclicker.py       # AutoClicker engine (non-daemon thread + Event)
    recorder.py          # Recorder backed by a listener factory
    player.py            # Player with speed/loop/cap enforcement
    macro.py             # @dataclass Macro / Event (version=1)
    hotkeys.py           # GlobalHotKeys wrapper (Ctrl+F? combos)
  ui/
    autoclicker_panel.py # main window (1:1 with template)
    macros_window.py     # secondary Toplevel
  utils/
    paths.py             # path helpers + D:-drive guard
    storage.py           # atomic JSON save/load + bounds check
    timing.py            # winmm timer boost + precise_sleep()
tests/                   # pytest, mocked pynput
build.ps1                # PyInstaller wrapper
run.ps1                  # dev launcher
```
