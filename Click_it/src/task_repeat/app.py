from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from task_repeat.core.autoclicker import (
    AutoClicker,
    ClickConfig,
    MIN_INTERVAL_SECONDS,
    interval_from_hms_ms,
)
from task_repeat.core.hotkeys import HotkeyManager, to_hotkey_string
from task_repeat.core.macro import Macro
from task_repeat.core.player import PlayConfig, Player
from task_repeat.core.recorder import Recorder
from task_repeat.ui.autoclicker_panel import AutoclickerPanel
from task_repeat.ui.macros_window import MacrosWindow
from task_repeat.utils.timing import boost_timer_resolution, release_timer_resolution


SHUTDOWN_JOIN_TIMEOUT = 1.5


class App:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._root.title("Task Repeat")
        self._root.resizable(False, False)

        self._mouse = None
        self._keyboard = None
        self._button_module = None
        self._mouse_listener_cls = None
        self._keyboard_listener_cls = None
        self._hotkey_cls = None

        self._init_pynput()

        self._autoclicker: AutoClicker | None = None
        self._recorder: Recorder | None = None
        self._player: Player | None = None
        self._macros_window: MacrosWindow | None = None
        self._pending_status_update = False
        self._pending_status_text = ""

        self._hotkeys = HotkeyManager(self._hotkey_cls) if self._hotkey_cls else None

        self._build_menu()
        self._panel = AutoclickerPanel(
            root,
            on_start=self._start_autoclicker,
            on_stop=self._stop_autoclicker,
            on_exit=self._on_quit,
            on_hotkey_change=self._refresh_hotkeys,
        )
        self._panel.grid(row=0, column=0)

        root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self._refresh_hotkeys()

    def _init_pynput(self) -> None:
        try:
            from pynput import keyboard as _kb, mouse as _ms
        except Exception as exc:
            messagebox.showwarning(
                "pynput unavailable",
                f"pynput failed to import: {exc}\n"
                "Run `pip install -r requirements.txt`.",
            )
            return
        self._mouse = _ms.Controller()
        self._keyboard = _kb.Controller()
        self._button_module = _ms
        self._mouse_listener_cls = _ms.Listener
        self._keyboard_listener_cls = _kb.Listener
        self._hotkey_cls = _kb.GlobalHotKeys

    def _build_menu(self) -> None:
        bar = tk.Menu(self._root)
        macros_menu = tk.Menu(bar, tearoff=False)
        macros_menu.add_command(label="Open Macros window", command=self._open_macros)
        bar.add_cascade(label="Macros", menu=macros_menu)
        self._root.config(menu=bar)

    def _open_macros(self) -> None:
        if self._mouse is None:
            messagebox.showerror(
                "Unavailable",
                "pynput is not installed; record/replay requires it.",
            )
            return
        if self._macros_window is not None and self._macros_window.winfo_exists():
            self._macros_window.deiconify()
            self._macros_window.lift()
            return
        self._macros_window = MacrosWindow(
            self._root,
            on_record=self._start_recording,
            on_stop_record=self._stop_recording,
            on_replay=self._start_replay,
            on_stop_replay=self._stop_replay,
        )

    def _refresh_hotkeys(self) -> None:
        if self._hotkeys is None:
            return
        try:
            start = to_hotkey_string("ctrl", self._panel.get_start_key())
            stop = to_hotkey_string("ctrl", self._panel.get_stop_key())
        except ValueError as exc:
            self._panel.set_status(f"Hotkey error: {exc}")
            return
        if start == stop:
            self._panel.set_status("Start/Stop hotkeys must differ.")
            return
        try:
            self._hotkeys.install(start, stop, self._start_autoclicker, self._stop_autoclicker)
            self._panel.set_status(f"Idle. Hotkeys: {start} / {stop}")
        except Exception as exc:
            self._panel.set_status(f"Hotkey install failed: {exc}")

    def _start_autoclicker(self) -> None:
        if self._mouse is None:
            return
        if self._autoclicker is not None and self._autoclicker.running:
            return
        h, m, s, ms = self._panel.get_interval_components()
        interval = interval_from_hms_ms(h, m, s, ms)
        if interval < MIN_INTERVAL_SECONDS:
            self._panel.set_status(
                f"Interval too small (min {int(MIN_INTERVAL_SECONDS * 1000)} ms)."
            )
            return
        try:
            cfg = ClickConfig(
                interval_seconds=interval,
                button=self._panel.get_mouse_button(),
                click_count=self._panel.get_click_count(),
                use_current_position=True,
            )
            self._autoclicker = AutoClicker(
                cfg,
                self._mouse,
                self._button_module,
                on_tick=self._on_click_tick,
                on_stop=self._on_click_done,
            )
            self._autoclicker.start()
            self._panel.set_status(f"Running… interval {interval:.3f}s")
        except Exception as exc:
            self._panel.set_status(f"Start failed: {exc}")

    def _stop_autoclicker(self) -> None:
        if self._autoclicker is None:
            return
        self._autoclicker.stop(timeout=SHUTDOWN_JOIN_TIMEOUT)
        self._panel.set_status("Stopped.")

    def _on_click_tick(self, count: int) -> None:
        self._schedule_status(f"Running… {count} clicks")

    def _on_click_done(self, count: int) -> None:
        self._schedule_status(f"Stopped after {count} clicks.")

    def _schedule_status(self, text: str) -> None:
        self._pending_status_text = text
        if self._pending_status_update:
            return
        self._pending_status_update = True

        def apply():
            self._pending_status_update = False
            self._panel.set_status(self._pending_status_text)

        self._root.after(0, apply)

    def _start_recording(self, capture_keyboard: bool) -> None:
        if self._mouse_listener_cls is None:
            return

        def factory(on_move, on_click, on_scroll, on_press, on_release):
            return _PynputListenerPair(
                mouse_cls=self._mouse_listener_cls,
                keyboard_cls=self._keyboard_listener_cls,
                on_move=on_move,
                on_click=on_click,
                on_scroll=on_scroll,
                on_press=on_press,
                on_release=on_release,
            )

        self._recorder = Recorder(
            listener_factory=factory, capture_keyboard=capture_keyboard
        )
        self._recorder.start()

    def _stop_recording(self) -> Macro | None:
        if self._recorder is None or not self._recorder.recording:
            return None
        macro = self._recorder.stop()
        return macro

    def _start_replay(self, macro: Macro, speed: float, loop: int) -> None:
        if self._mouse is None:
            return
        if self._player is not None and self._player.running:
            return
        try:
            cfg = PlayConfig(speed=speed, loop_count=loop, capture_keyboard=False)
            self._player = Player(
                macro=macro,
                config=cfg,
                mouse_controller=self._mouse,
                button_module=self._button_module,
                keyboard_controller=self._keyboard,
                on_stop=lambda played: self._schedule_macro_status(
                    f"Replay finished. {played} events played."
                ),
            )
            self._player.start()
        except Exception as exc:
            self._schedule_macro_status(f"Replay failed: {exc}")

    def _stop_replay(self) -> None:
        if self._player is None:
            return
        self._player.stop(timeout=SHUTDOWN_JOIN_TIMEOUT)
        self._schedule_macro_status("Replay stopped.")

    def _schedule_macro_status(self, text: str) -> None:
        win = self._macros_window
        if win is None or not win.winfo_exists():
            return
        self._root.after(0, lambda: win.set_status(text))

    def _on_quit(self) -> None:
        try:
            if self._autoclicker is not None:
                self._autoclicker.stop(timeout=SHUTDOWN_JOIN_TIMEOUT)
            if self._player is not None:
                self._player.stop(timeout=SHUTDOWN_JOIN_TIMEOUT)
            if self._recorder is not None and self._recorder.recording:
                self._recorder.stop()
            if self._hotkeys is not None:
                self._hotkeys.uninstall()
        finally:
            release_timer_resolution()
            self._root.destroy()


def main() -> None:
    boost_timer_resolution()
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


class _PynputListenerPair:
    def __init__(
        self,
        mouse_cls,
        keyboard_cls,
        on_move,
        on_click,
        on_scroll,
        on_press,
        on_release,
    ) -> None:
        self._mouse = mouse_cls(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        self._keyboard = None
        if on_press is not None and on_release is not None and keyboard_cls is not None:
            self._keyboard = keyboard_cls(on_press=on_press, on_release=on_release)

    def start(self) -> None:
        self._mouse.start()
        if self._keyboard is not None:
            self._keyboard.start()

    def stop(self) -> None:
        try:
            self._mouse.stop()
        finally:
            if self._keyboard is not None:
                self._keyboard.stop()
