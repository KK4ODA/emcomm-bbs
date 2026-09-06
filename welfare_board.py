#!/usr/bin/env python3
"""
Amateur Radio Welfare Board - standalone GUI

Runs the welfare check-in pipeline on its own, without the bulletin
generator. Settings live in ``settings.json`` next to this file.
"""

import json
import logging
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ui_theme  # noqa: E402
from ui_theme import Card, LogPanel, StatusBar, FONTS, PALETTE  # noqa: E402
from welfare_pipeline import WelfarePipeline  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"
TEMPLATE_FILE = APP_DIR / "welfare_checkin_template.txt"
TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
MAX_WINDOWS = 3

DEFAULT_SETTINGS = {
    "directories": {
        "input": "data/input",
        "archive": "data/archive",
        "output": "data/output",
        "error": "data/error",
    },
    "time_windows": [
        {"name": "Morning Net", "start": "08:00", "end": "10:00"},
        {"name": "Evening Net", "start": "19:00", "end": "21:00"},
    ],
    "output": {"generate_text": True, "generate_html": True, "generate_csv": True,
               "html_auto_refresh": 30},
    "validation": {"require_callsign": False, "require_name": True, "require_location": True,
                   "require_status": True, "valid_statuses": ["SAFE", "NEED ASSISTANCE", "TRAFFIC"]},
}


def load_settings():
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))   # deep copy
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if isinstance(value, dict) and isinstance(settings.get(key), dict):
                    settings[key].update(value)
                else:
                    settings[key] = value
        except (OSError, ValueError) as exc:
            messagebox.showwarning("Settings", f"Could not read settings.json ({exc}); using defaults.")
    # resolve relative folders against the app directory
    settings["directories"] = {k: str((APP_DIR / v) if not Path(v).is_absolute() else Path(v))
                               for k, v in settings["directories"].items()}
    return settings


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


class WelfareBoardApp:

    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self._build_ui()
        self.pipeline = WelfarePipeline(self.settings, self.log, self._on_update)
        self.log("Welfare Board ready")
        self.log(f"Monitor folder: {self.settings['directories']['input']}")
        self._tick()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        ui_theme.apply_theme(self.root)
        self.root.title("Amateur Radio Welfare Board")
        height = min(560, self.root.winfo_screenheight() - 150)
        self.root.geometry(f"780x{height}+60+40")
        self.root.minsize(680, 460)

        bar, self.header_right = ui_theme.header(self.root, "Welfare Board", "amateur radio check-in roster")
        bar.pack(fill="x")
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill="x", side="bottom")

        body = ttk.Frame(self.root, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        status = Card(body, "Status")
        status.grid(row=0, column=0, sticky="ew")
        grid = status.body
        for col, (label, attr) in enumerate((("Active window", "window_label"),
                                             ("Check-ins this window", "count_label"),
                                             ("Monitoring", "monitor_label"))):
            tk.Label(grid, text=label, bg=PALETTE["card"], fg=PALETTE["muted"], font=FONTS["small"]
                     ).grid(row=0, column=col, sticky="w", padx=(0, 32))
            style = "CardBig.TLabel" if attr == "count_label" else "CardWarn.TLabel"
            widget = ttk.Label(grid, text="—", style=style)
            widget.grid(row=1, column=col, sticky="w", padx=(0, 32))
            setattr(self, attr, widget)
        self.count_label.configure(text="0")

        actions = ttk.Frame(body)
        actions.grid(row=1, column=0, sticky="ew", pady=12)
        self.start_btn = ttk.Button(actions, text="Start monitoring", style="Accent.TButton",
                                    command=self.start_monitoring)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Stop", command=self.stop_monitoring, state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open board", command=self.view_board).pack(side="right")
        ttk.Button(actions, text="Check-in template", command=self.open_template).pack(side="right", padx=(0, 6))
        ttk.Button(actions, text="Settings…", command=self.open_settings).pack(side="right", padx=(0, 6))

        logcard = Card(body, "Check-in activity", padding=10)
        logcard.grid(row=2, column=0, sticky="nsew")
        self.log_panel = LogPanel(logcard.body, height=12)
        self.log_panel.pack(fill="both", expand=True)

    def log(self, message):
        self.log_panel.append(message)

    def _tick(self):
        window = self.pipeline.current_window()
        if window:
            self.window_label.configure(text=f"{window['name']}  {window['start']}–{window['end']}",
                                        style="CardOk.TLabel")
            self.count_label.configure(text=str(self.pipeline.current_count()))
        else:
            self.window_label.configure(text="None active", style="CardWarn.TLabel")
        running = self.pipeline.running
        self.monitor_label.configure(text="Running" if running else "Stopped",
                                     style="CardOk.TLabel" if running else "CardWarn.TLabel")
        self.status_bar.set(left=f"Output: {self.settings['directories']['output']}",
                            right=f"{len(self.pipeline.time_windows)} window(s) configured")
        self.root.after(30000, self._tick)

    def _on_update(self, window, count):
        self.root.after(0, self.count_label.configure, {"text": str(count)})

    # ------------------------------------------------------------- actions

    def start_monitoring(self):
        try:
            self.pipeline.start()
        except OSError as exc:
            messagebox.showerror("Welfare Board", f"Cannot watch folder:\n{exc}", parent=self.root)
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._tick()

    def stop_monitoring(self):
        self.pipeline.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def view_board(self):
        board = Path(self.settings['directories']['output']) / "welfare_board.html"
        if board.exists():
            webbrowser.open(board.as_uri())
        else:
            messagebox.showinfo("Welfare Board", "No board generated yet. Start monitoring and "
                                "drop a check-in file in the monitor folder.", parent=self.root)

    def open_template(self):
        try:
            if sys.platform == "win32":
                os.startfile(TEMPLATE_FILE)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.call(["open", str(TEMPLATE_FILE)])
            else:
                subprocess.call(["xdg-open", str(TEMPLATE_FILE)])
        except OSError as exc:
            self.log(f"⚠ Could not open template: {exc}")

    def open_settings(self):
        SettingsDialog(self.root, self.settings, self._apply_settings)

    def _apply_settings(self, settings):
        self.settings = settings
        try:
            save_settings(settings)
        except OSError as exc:
            messagebox.showerror("Settings", f"Could not write settings.json:\n{exc}", parent=self.root)
        self.pipeline.reconfigure(settings)
        self.log("✓ Settings saved")
        self.log(f"Monitor folder: {settings['directories']['input']}")
        self._tick()

    def _on_close(self):
        self.pipeline.stop()
        self.root.destroy()


class SettingsDialog:
    """Folders and time windows."""

    def __init__(self, parent, settings, on_save):
        self.settings = json.loads(json.dumps(settings))
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Welfare Board settings")
        self.win.configure(bg=PALETTE["bg"])
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        body = ttk.Frame(self.win, padding=14)
        body.pack(fill="both", expand=True)

        dirs = Card(body, "Folders")
        dirs.pack(fill="x")
        self.dir_vars = {}
        labels = {"input": "Monitor", "archive": "Archive", "error": "Errors", "output": "Board output"}
        for r, key in enumerate(("input", "archive", "error", "output")):
            var = tk.StringVar(value=self.settings["directories"].get(key, ""))
            self.dir_vars[key] = var
            tk.Label(dirs.body, text=labels[key], bg=PALETTE["card"], fg=PALETTE["text"]
                     ).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Entry(dirs.body, textvariable=var, width=48).grid(row=r, column=1, sticky="ew", pady=3)
            ttk.Button(dirs.body, text="Browse…", command=lambda v=var: self._browse(v)
                       ).grid(row=r, column=2, padx=(8, 0), pady=3)
        dirs.body.columnconfigure(1, weight=1)

        wins = Card(body, "Check-in windows", "blank name disables a row")
        wins.pack(fill="x", pady=(12, 0))
        for col, text in enumerate(("", "Name", "Start", "End")):
            tk.Label(wins.body, text=text, bg=PALETTE["card"], fg=PALETTE["muted"], font=FONTS["small"]
                     ).grid(row=0, column=col, sticky="w", padx=(0, 8))
        self.window_entries = []
        windows = self.settings.get("time_windows", []) + [{}] * MAX_WINDOWS
        for i in range(MAX_WINDOWS):
            tk.Label(wins.body, text=f"Window {i + 1}", bg=PALETTE["card"], fg=PALETTE["text"]
                     ).grid(row=i + 1, column=0, sticky="w", padx=(0, 8), pady=3)
            entries = (ttk.Entry(wins.body, width=22), ttk.Entry(wins.body, width=8), ttk.Entry(wins.body, width=8))
            for col, (entry, key) in enumerate(zip(entries, ("name", "start", "end")), start=1):
                entry.insert(0, windows[i].get(key, ""))
                entry.grid(row=i + 1, column=col, sticky="w", padx=(0, 8), pady=3)
            self.window_entries.append(entries)

        foot = ttk.Frame(body)
        foot.pack(fill="x", pady=(14, 0))
        ttk.Button(foot, text="Save", style="Accent.TButton", command=self._save).pack(side="right")
        ttk.Button(foot, text="Cancel", command=self.win.destroy).pack(side="right", padx=(0, 6))

    def _browse(self, var):
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()), parent=self.win)
        if chosen:
            var.set(chosen)

    def _save(self):
        windows = []
        for name, start, end in self.window_entries:
            n, s, e = name.get().strip(), start.get().strip(), end.get().strip()
            if not n:
                continue
            if not (TIME_RE.match(s) and TIME_RE.match(e)) or s >= e:
                messagebox.showerror("Settings", f"Window '{n}': use HH:MM and start before end.",
                                     parent=self.win)
                return
            windows.append({"name": n, "start": s, "end": e})
        if not windows:
            messagebox.showerror("Settings", "At least one check-in window is required.", parent=self.win)
            return
        for key, var in self.dir_vars.items():
            if not var.get().strip():
                messagebox.showerror("Settings", "Every folder needs a path.", parent=self.win)
                return
            self.settings["directories"][key] = var.get().strip()
        self.settings["time_windows"] = windows
        self.win.destroy()
        self.on_save(self.settings)


def main():
    logging.basicConfig(level=logging.WARNING)
    root = tk.Tk()
    WelfareBoardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
