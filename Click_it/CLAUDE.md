> **Inherits global rules from `D:\test 2\CLAUDE.md`** — approval gate, no-guessing, regression tests, git lifecycle (including todo-in-commits), shell pre-approval, D:-drive-only disk policy, agent review for non-trivial changes. Read that file too.

# Task_Repeat — Project Context

## What this is
A small Windows Tkinter utility that mimics the "Free Mouse Clicker" template. Two features:
1. **Auto-clicker** — H:M:S:ms interval, Ctrl+F2 start / Ctrl+F3 stop global hotkeys, Left/Right/Middle × Single/Double click.
2. **Record / Replay** — secondary "Macros" window opened from the menu; captures mouse events (and optionally keyboard with explicit user opt-in), saves to JSON, replays with N-loop + speed multiplier.

## Layout
- Working directory: `D:\test 2\Task_Repeat\`
- Source: `src/task_repeat/`
- Tests: `tests/`
- Macros (gitignored): `data/macros/*.json`
- Build script: `build.ps1` → `dist/task_repeat.exe`
- Dev launcher: `run.ps1` → `python -m task_repeat`

## Stack
- Python 3.11+ (uses stdlib `tkinter`)
- `pynput` — global mouse/keyboard control + capture + hotkeys
- `pyinstaller==6.15.0` — pinned (lowest 3.14-compatible release, per security review)
- No network calls, no telemetry, no cloud sync.

## Threading model
- Tk mainloop runs on main thread.
- Auto-clicker engine + player run on **non-daemon** threads driven by `threading.Event`.
- Clean shutdown: `WM_DELETE_WINDOW` handler sets stop_event, joins with timeout, then `root.destroy()`.
- UI updates from worker threads marshaled via `root.after(0, …)` with a `_pending` flag to avoid queue flooding.
- `winmm.timeBeginPeriod(1)` + `perf_counter` correction for sub-100 ms interval accuracy on Windows.

## Safety rails (from security review)
- Keyboard recording **defaults OFF** every session; first enable shows a modal warning.
- Replay caps: max 10,000 repetitions, speed clamped 0.1×–10×, max 50,000 events per macro.
- Atomic writes use `Path.with_suffix('.tmp')` on the SAME drive (never `tempfile.mkstemp` to C:).

## Tests
- `pytest tests/` — 0 failures required before push.
- All tests mock pynput controllers/listeners. No test ever drives the real mouse or keyboard.

## Build
- `.\build.ps1` produces `dist/task_repeat.exe` (one-file, windowed).
- All PyInstaller artifacts pinned to D: via `--workpath` / `--distpath`.
