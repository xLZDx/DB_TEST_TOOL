from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Callable

from task_repeat.core.macro import Macro
from task_repeat.core.player import MAX_LOOPS, MAX_SPEED, MIN_SPEED
from task_repeat.utils.paths import macros_dir
from task_repeat.utils.storage import load_macro, save_macro


SPEED_CHOICES = ("0.5", "1.0", "2.0")


class MacrosWindow(tk.Toplevel):
    def __init__(
        self,
        master,
        on_record: Callable[[bool], None],
        on_stop_record: Callable[[], Macro | None],
        on_replay: Callable[[Macro, float, int], None],
        on_stop_replay: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("Macros — Record / Replay")
        self.resizable(False, False)
        self._on_record = on_record
        self._on_stop_record = on_stop_record
        self._on_replay = on_replay
        self._on_stop_replay = on_stop_replay
        self._loaded_macro: Macro | None = None
        self._keyboard_warned = False

        self.var_capture_keyboard = tk.BooleanVar(value=False)
        self.var_loop = tk.IntVar(value=1)
        self.var_speed = tk.StringVar(value="1.0")
        self.var_file = tk.StringVar(value="")
        self.var_status = tk.StringVar(value="Idle. Press Record to begin.")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        record_box = ttk.LabelFrame(frm, text="Record", padding=8)
        record_box.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(
            record_box,
            text="Also capture keyboard (passwords WILL be recorded!)",
            variable=self.var_capture_keyboard,
            command=self._on_capture_kb_toggle,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(record_box, text="● Record", width=12, command=self._do_record).grid(
            row=1, column=0, pady=(6, 0)
        )
        ttk.Button(record_box, text="■ Stop", width=12, command=self._do_stop_record).grid(
            row=1, column=1, padx=(6, 0), pady=(6, 0)
        )

        replay_box = ttk.LabelFrame(frm, text="Replay", padding=8)
        replay_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(replay_box, text="Loop count:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            replay_box, from_=1, to=MAX_LOOPS, textvariable=self.var_loop, width=8
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(replay_box, text="Speed:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Combobox(
            replay_box,
            values=SPEED_CHOICES,
            textvariable=self.var_speed,
            state="readonly",
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 0))
        ttk.Button(replay_box, text="▶ Replay", width=12, command=self._do_replay).grid(
            row=1, column=0, pady=(6, 0)
        )
        ttk.Button(replay_box, text="■ Stop", width=12, command=self._on_stop_replay).grid(
            row=1, column=1, padx=(6, 0), pady=(6, 0)
        )

        file_box = ttk.LabelFrame(frm, text="File", padding=8)
        file_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(file_box, textvariable=self.var_file, width=40, state="readonly").grid(
            row=0, column=0, columnspan=2, sticky="ew"
        )
        ttk.Button(file_box, text="Save", width=12, command=self._do_save).grid(
            row=1, column=0, pady=(6, 0)
        )
        ttk.Button(file_box, text="Load", width=12, command=self._do_load).grid(
            row=1, column=1, padx=(6, 0), pady=(6, 0)
        )

        ttk.Label(frm, textvariable=self.var_status, anchor="w", wraplength=380).grid(
            row=3, column=0, sticky="ew", pady=(8, 0)
        )

    def _on_capture_kb_toggle(self) -> None:
        if not self.var_capture_keyboard.get():
            return
        if self._keyboard_warned:
            return
        proceed = messagebox.askokcancel(
            "Keyboard capture warning",
            "Enabling keyboard recording will capture ALL keystrokes,\n"
            "including passwords. Use only when you are certain no\n"
            "password prompt or sensitive field will receive input.\n\n"
            "Macro files are stored as plain JSON on disk.\n\n"
            "Continue?",
            parent=self,
        )
        if not proceed:
            self.var_capture_keyboard.set(False)
        else:
            self._keyboard_warned = True

    def _do_record(self) -> None:
        self._on_record(self.var_capture_keyboard.get())
        self.set_status("Recording…")

    def _do_stop_record(self) -> None:
        macro = self._on_stop_record()
        if macro is None:
            self.set_status("Not recording.")
            return
        self._loaded_macro = macro
        self.set_status(f"Recorded {len(macro.events)} events. Use Save to keep.")

    def _do_replay(self) -> None:
        if self._loaded_macro is None or not self._loaded_macro.events:
            self.set_status("No macro loaded. Record or Load one first.")
            return
        try:
            speed = float(self.var_speed.get())
        except (ValueError, tk.TclError):
            self.set_status("Invalid speed value.")
            return
        if not (MIN_SPEED <= speed <= MAX_SPEED):
            self.set_status(f"Speed must be between {MIN_SPEED} and {MAX_SPEED}.")
            return
        try:
            loop = int(self.var_loop.get())
        except (ValueError, tk.TclError):
            self.set_status("Invalid loop count.")
            return
        if not (1 <= loop <= MAX_LOOPS):
            self.set_status(f"Loop count must be 1..{MAX_LOOPS}.")
            return
        self._on_replay(self._loaded_macro, speed, loop)
        self.set_status(f"Replaying {len(self._loaded_macro.events)} events × {loop} (speed {speed}×)…")

    def _do_save(self) -> None:
        if self._loaded_macro is None:
            self.set_status("Nothing to save.")
            return
        path_str = filedialog.asksaveasfilename(
            parent=self,
            title="Save macro",
            initialdir=str(macros_dir()),
            defaultextension=".json",
            filetypes=[("Task_Repeat macro", "*.json")],
        )
        if not path_str:
            return
        try:
            save_macro(self._loaded_macro, Path(path_str))
            self.var_file.set(path_str)
            self.set_status(f"Saved {len(self._loaded_macro.events)} events.")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)

    def _do_load(self) -> None:
        path_str = filedialog.askopenfilename(
            parent=self,
            title="Load macro",
            initialdir=str(macros_dir()),
            filetypes=[("Task_Repeat macro", "*.json")],
        )
        if not path_str:
            return
        try:
            macro = load_macro(Path(path_str))
            self._loaded_macro = macro
            self.var_file.set(path_str)
            self.set_status(f"Loaded {len(macro.events)} events.")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc), parent=self)

    def set_status(self, text: str) -> None:
        self.var_status.set(text)
