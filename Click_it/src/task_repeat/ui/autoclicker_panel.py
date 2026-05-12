from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from task_repeat.core.hotkeys import VALID_FUNCTION_KEYS


MOUSE_LABELS = {"Left Button": "left", "Right Button": "right", "Middle Button": "middle"}
ACTION_LABELS = {"Single Click": 1, "Double Click": 2}


class AutoclickerPanel(ttk.Frame):
    def __init__(
        self,
        master,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_exit: Callable[[], None],
        on_hotkey_change: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=10)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_exit = on_exit
        self._on_hotkey_change = on_hotkey_change

        self.var_hours = tk.IntVar(value=0)
        self.var_minutes = tk.IntVar(value=0)
        self.var_seconds = tk.IntVar(value=1)
        self.var_ms = tk.IntVar(value=0)
        self.var_start_key = tk.StringVar(value="F2")
        self.var_stop_key = tk.StringVar(value="F3")
        self.var_mouse = tk.StringVar(value="Left Button")
        self.var_action = tk.StringVar(value="Single Click")
        self.var_status = tk.StringVar(value="Idle")

        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)

        self._mascot_label = ttk.Label(top, text="🐭", font=("Segoe UI Emoji", 64))
        self._mascot_label.grid(row=0, column=0, rowspan=2, padx=(0, 16), sticky="n")

        interval = ttk.LabelFrame(top, text="Click Interval", padding=8)
        interval.grid(row=0, column=1, sticky="ew")
        for i, (label, var, hi) in enumerate(
            [
                ("Hours", self.var_hours, 23),
                ("Minutes", self.var_minutes, 59),
                ("Seconds", self.var_seconds, 59),
                ("MilliSeconds", self.var_ms, 999),
            ]
        ):
            ttk.Label(interval, text=label).grid(row=0, column=i, padx=4)
            ttk.Spinbox(interval, from_=0, to=hi, width=6, textvariable=var).grid(
                row=1, column=i, padx=4
            )

        bottom = ttk.Frame(self)
        bottom.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        hotkeys = ttk.LabelFrame(bottom, text="Hot Key", padding=8)
        hotkeys.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ttk.Label(hotkeys, text="Start: CTRL +").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            hotkeys,
            values=VALID_FUNCTION_KEYS,
            textvariable=self.var_start_key,
            state="readonly",
            width=5,
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(hotkeys, text="Stop: CTRL +").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            hotkeys,
            values=VALID_FUNCTION_KEYS,
            textvariable=self.var_stop_key,
            state="readonly",
            width=5,
        ).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(6, 0))
        self.var_start_key.trace_add("write", lambda *_: self._on_hotkey_change())
        self.var_stop_key.trace_add("write", lambda *_: self._on_hotkey_change())

        action = ttk.LabelFrame(bottom, text="Mouse Action", padding=8)
        action.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ttk.Label(action, text="Mouse").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            action,
            values=list(MOUSE_LABELS.keys()),
            textvariable=self.var_mouse,
            state="readonly",
            width=14,
        ).grid(row=0, column=1, padx=(4, 0))
        ttk.Label(action, text="Action").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            action,
            values=list(ACTION_LABELS.keys()),
            textvariable=self.var_action,
            state="readonly",
            width=14,
        ).grid(row=1, column=1, padx=(4, 0), pady=(6, 0))

        footer = ttk.Frame(self)
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(2, weight=1)
        ttk.Button(footer, text="Start", width=10, command=self._on_start).grid(row=0, column=0)
        ttk.Button(footer, text="Stop", width=10, command=self._on_stop).grid(
            row=0, column=1, padx=(6, 0)
        )
        ttk.Button(footer, text="Exit", width=10, command=self._on_exit).grid(row=0, column=3)

        status = ttk.Frame(self)
        status.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(status, textvariable=self.var_status, anchor="w").grid(
            row=0, column=0, sticky="ew"
        )

    def set_status(self, text: str) -> None:
        self.var_status.set(text)

    def get_interval_components(self) -> tuple[int, int, int, int]:
        return (
            int(self.var_hours.get()),
            int(self.var_minutes.get()),
            int(self.var_seconds.get()),
            int(self.var_ms.get()),
        )

    def get_mouse_button(self) -> str:
        return MOUSE_LABELS[self.var_mouse.get()]

    def get_click_count(self) -> int:
        return ACTION_LABELS[self.var_action.get()]

    def get_start_key(self) -> str:
        return self.var_start_key.get()

    def get_stop_key(self) -> str:
        return self.var_stop_key.get()
