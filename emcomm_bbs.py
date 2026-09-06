#!/usr/bin/env python3
"""
Emcomm BBS - desktop companion for amateur radio emergency communications.

Pulls situational-awareness data from public sources (news, NWS weather,
NOAA space weather, emergency alerts, power outages, social feeds) and writes
compact plain-text bulletins for low-bandwidth HF links. Also hosts the
Welfare Board, which turns incoming check-in files into a live roster.

Layout of this file:
    EmcommApp.__init__ / _build_*      GUI construction (three tabs)
    settings helpers                   widgets <-> AppConfig
    bulletin generation                one _generate_<kind>() per report
    scheduler                          background auto-update loop
    welfare board                      folder watcher and check-in pipeline
"""

import logging
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_config import AppConfig, APP_DIR, MAX_TIME_WINDOWS  # noqa: E402
from data_sources import (  # noqa: E402
    APP_VERSION, FEMA_REGIONS, FEMA_REGION_LABELS,
    WeatherFetcher, SpaceWeatherFetcher, NewsSummarizer, PowerOutageFetcher,
)
from plaintext_generators import PlainTextGenerator  # noqa: E402
import ui_theme  # noqa: E402
from ui_theme import Card, LogPanel, ScrollFrame, StatusBar, field_row, FONTS, PALETTE  # noqa: E402

try:
    from emergency_module import EmergencyDataFetcher, SocialMediaEmergencyFetcher
except ImportError:
    EmergencyDataFetcher = SocialMediaEmergencyFetcher = None

try:
    from nextdoor_module import NextdoorFetcher
except ImportError:
    NextdoorFetcher = None

try:
    from welfare_pipeline import WelfarePipeline
    WELFARE_AVAILABLE, WELFARE_IMPORT_ERROR = True, ""
except ImportError as exc:  # usually: watchdog not installed
    WELFARE_AVAILABLE, WELFARE_IMPORT_ERROR = False, str(exc)

log = logging.getLogger("emcomm_bbs")

# key, label, description, file prefix
REPORTS = [
    ("news",      "News summary",      "BBC and NPR headlines, AI digest with an Anthropic key", "news_"),
    ("weather",   "Weather forecasts", "NWS 7-day outlook, one file per FEMA region",           "wx_"),
    ("space",     "Space weather",     "NOAA solar flux, K-index, HF band estimate",            "space_"),
    ("emergency", "Emergency alerts",  "NWS alerts, USGS quakes, FEMA declarations, wildfires", "emergency_"),
    ("power",     "Power outages",     "DOE / ORNL ODIN live outage counts",                    "power_outages_"),
    ("twitter",   "X / Twitter feed",  "Official emergency accounts (bearer token required)",   "tweets_"),
    ("nextdoor",  "Nextdoor",          "Neighborhood reports (agency API key required)",        "nextdoor_"),
]
REPORT_PREFIX = {key: prefix for key, _, _, prefix in REPORTS}
TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
WELFARE_TEMPLATE = APP_DIR / "welfare_checkin_template.txt"
DEFAULT_TEMPLATE_TEXT = """CALLSIGN: (or leave blank if not a licensed ham)

NAME:

LOCATION:

STATUS: (SAFE / NEED ASSISTANCE / TRAFFIC)

POWER: (ON / OFF / GENERATOR)

CONTACT: (Phone# for SMS or Email to notify family)

MESSAGE:

"""


class EmcommApp:
    """Main window. All network work runs on worker threads; every widget
    update from those threads goes through ``self.ui()``."""

    def __init__(self, root):
        self.root = root
        self.config = AppConfig.load()

        # generation state
        self._gen_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._scheduler = None
        self._next_run = {}          # kind -> epoch seconds

        # fetchers
        self.summarizer = NewsSummarizer(self.config.anthropic_api_key)
        self.emergency_fetcher = EmergencyDataFetcher() if EmergencyDataFetcher else None
        self.twitter_fetcher = None
        self.nextdoor_fetcher = None

        self.welfare = None          # WelfarePipeline, created in _configure_welfare

        self._build_ui()
        self._apply_config_to_widgets()
        self._rebuild_fetchers(quiet=True)
        self._configure_welfare(quiet=True)
        if WELFARE_AVAILABLE:
            self._welfare_tick()

        self.log(f"Emcomm BBS {APP_VERSION} ready")
        self.log(f"Bulletins are written to {self.config.save_directory}")
        if not self.emergency_fetcher:
            self.log("⚠ emergency_module.py not found - alert reports disabled")
        if not WELFARE_AVAILABLE:
            self.log(f"⚠ Welfare Board disabled ({WELFARE_IMPORT_ERROR}). Run: pip install watchdog")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        p = ui_theme.apply_theme(self.root)
        self.root.title(f"Emcomm BBS {APP_VERSION}")
        # Fit the default size to the screen (laptops at 150% DPI are short)
        # and place the window near the top so the footer clears the taskbar.
        height = min(660, self.root.winfo_screenheight() - 150)
        self.root.geometry(f"820x{height}+40+24")
        self.root.minsize(760, 540)

        bar, self.header_right = ui_theme.header(
            self.root, "Emcomm BBS", "situational-awareness bulletins for HF links")
        bar.pack(fill="x")

        # Packed before the notebook so it is never squeezed off-screen.
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill="x", side="bottom")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(12, 8))

        self.main_tab = ttk.Frame(self.notebook, padding=(0, 12, 0, 0))
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Bulletins")
        self.notebook.add(self.settings_tab, text="Settings")
        self._build_main_tab(self.main_tab)
        self._build_settings_tab(self.settings_tab)
        if WELFARE_AVAILABLE:
            self.welfare_tab = ttk.Frame(self.notebook, padding=(0, 12, 0, 0))
            self.notebook.add(self.welfare_tab, text="Welfare Board")
            self._build_welfare_tab(self.welfare_tab)

        self._tick_clock()

    # ---- Bulletins tab ----------------------------------------------------

    def _build_main_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        # Bulletin selection
        card = Card(top, "Bulletins", "select what to generate")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.report_vars = {}
        row = 0
        for key, label, desc, _ in REPORTS:
            if key == "nextdoor" and NextdoorFetcher is None:
                continue
            var = tk.BooleanVar(value=self.config.checkboxes.get(key, False))
            self.report_vars[key] = var
            ttk.Checkbutton(card.body, text=label, variable=var, style="Card.TCheckbutton",
                            command=self._on_selection_changed).grid(row=row, column=0, sticky="w")
            ttk.Label(card.body, text=desc, style="CardMuted.TLabel").grid(
                row=row, column=1, sticky="w", padx=(10, 0))
            row += 1

        # FEMA regions
        regions = Card(top, "Weather regions", "FEMA")
        regions.grid(row=0, column=1, sticky="nsew")
        self.region_vars = {}
        for i in range(1, 11):
            var = tk.BooleanVar(value=i in self.config.weather_regions)
            self.region_vars[i] = var
            r, c = (i - 1) % 5, (i - 1) // 5
            ttk.Checkbutton(regions.body, text=FEMA_REGION_LABELS[i], variable=var,
                            style="Card.TCheckbutton", command=self._on_selection_changed
                            ).grid(row=r, column=c, sticky="w", padx=(0, 14))
        links = tk.Frame(regions.body, bg=PALETTE["card"])
        links.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(links, text="Select all", style="Link.TButton",
                   command=lambda: self._set_regions(True)).pack(side="left")
        ttk.Button(links, text="Clear", style="Link.TButton",
                   command=lambda: self._set_regions(False)).pack(side="left", padx=(6, 0))

        # Actions
        actions = ttk.Frame(tab)
        actions.grid(row=1, column=0, sticky="ew", pady=12)
        self.generate_btn = ttk.Button(actions, text="Generate now", style="Accent.TButton",
                                       command=self.generate_now)
        self.generate_btn.pack(side="left")
        self.start_btn = ttk.Button(actions, text="Start auto-updates", command=self.start_service)
        self.start_btn.pack(side="left", padx=(10, 0))
        self.stop_btn = ttk.Button(actions, text="Stop", command=self.stop_service, state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 0))
        self.status_var = tk.StringVar(value="Idle")
        self.status_label = ttk.Label(actions, textvariable=self.status_var, style="Muted.TLabel")
        self.status_label.pack(side="right")

        # Log
        logcard = Card(tab, "Activity", padding=10)
        logcard.grid(row=2, column=0, sticky="nsew")
        self.log_panel = LogPanel(logcard.body, height=10)
        self.log_panel.pack(fill="both", expand=True)

    # ---- Settings tab -----------------------------------------------------

    def _build_settings_tab(self, tab):
        scroller = ScrollFrame(tab)
        scroller.pack(fill="both", expand=True)
        body = scroller.body
        body.columnconfigure(0, weight=1)
        pad = dict(sticky="ew", padx=(0, 4), pady=(12, 0))

        # API keys ---------------------------------------------------------
        keys = Card(body, "API keys", "all optional - leave blank to disable that feature")
        keys.grid(row=0, column=0, **pad)
        f = keys.body
        self.secret_entries = []

        self.anthropic_entry = field_row(
            f, "Anthropic API key", lambda m: ttk.Entry(m, show="•"),
            hint="Enables the AI-written news digest. Without it you still get headline lists.", row=0)
        self.secret_entries.append(self.anthropic_entry)

        if self.emergency_fetcher:
            self.twitter_token_entry = field_row(
                f, "X / Twitter bearer token", lambda m: ttk.Entry(m, show="•"),
                hint="Needed for the emergency tweet feed.", row=2)
            self.secret_entries.append(self.twitter_token_entry)
            self.twitter_handles_entry = field_row(
                f, "X accounts to monitor", ttk.Entry,
                hint="Comma-separated, no @ (e.g. NWS,fema,USGS_Quakes)", row=4)
        if NextdoorFetcher:
            self.nextdoor_key_entry = field_row(
                f, "Nextdoor API key", lambda m: ttk.Entry(m, show="•"),
                hint="Requires Nextdoor Public Agency API approval.", row=6)
            self.secret_entries.append(self.nextdoor_key_entry)
            self.nextdoor_zips_entry = field_row(
                f, "ZIP codes", ttk.Entry, hint="Comma-separated (e.g. 30301,30308)", row=8)

        self.show_keys_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Show keys", variable=self.show_keys_var, style="Card.TCheckbutton",
                        command=self._toggle_secrets).grid(row=10, column=1, sticky="w")

        # Output & schedule ---------------------------------------------------
        out = Card(body, "Output and schedule")
        out.grid(row=1, column=0, **pad)
        f = out.body
        self.dir_var = tk.StringVar()
        browse = ttk.Button(f, text="Browse…", command=self._browse_save_dir)
        field_row(f, "Bulletin folder", lambda m: ttk.Entry(m, textvariable=self.dir_var),
                  hint="Usually your VarAC BBS folder so files are served over the air.",
                  button=browse, row=0)

        sched = tk.Frame(f, bg=PALETTE["card"])
        sched.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.main_interval = tk.IntVar(value=6)
        self.twitter_interval = tk.IntVar(value=6)
        self._interval_row(sched, 0, "Regenerate bulletins every", self.main_interval, 1, 24)
        self._interval_row(sched, 1, "Refresh X feed every", self.twitter_interval, 1, 12)
        tk.Label(sched, text="Both apply to auto-updates only. When the two intervals match, "
                 "the X feed rides along with the main run.",
                 bg=PALETTE["card"], fg=PALETTE["muted"], font=FONTS["small"], justify="left"
                 ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # Welfare windows ------------------------------------------------------
        win = Card(body, "Welfare check-in windows",
                   "check-ins outside these times are rejected; blank name disables a row")
        win.grid(row=2, column=0, **pad)
        f = win.body
        for col, text in enumerate(("", "Name", "Start", "End")):
            tk.Label(f, text=text, bg=PALETTE["card"], fg=PALETTE["muted"],
                     font=FONTS["small"]).grid(row=0, column=col, sticky="w", padx=(0, 8))
        self.window_entries = []
        for i in range(MAX_TIME_WINDOWS):
            tk.Label(f, text=f"Window {i + 1}", bg=PALETTE["card"], fg=PALETTE["text"]
                     ).grid(row=i + 1, column=0, sticky="w", padx=(0, 8), pady=3)
            name = ttk.Entry(f, width=22)
            start = ttk.Entry(f, width=8)
            end = ttk.Entry(f, width=8)
            name.grid(row=i + 1, column=1, sticky="w", padx=(0, 8), pady=3)
            start.grid(row=i + 1, column=2, sticky="w", padx=(0, 8), pady=3)
            end.grid(row=i + 1, column=3, sticky="w", pady=3)
            self.window_entries.append((name, start, end))
        tk.Label(f, text="24-hour HH:MM. Use 00:00 to 23:59 to accept check-ins all day.",
                 bg=PALETTE["card"], fg=PALETTE["muted"], font=FONTS["small"]
                 ).grid(row=MAX_TIME_WINDOWS + 1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # Save ---------------------------------------------------------------
        foot = ttk.Frame(body)
        foot.grid(row=3, column=0, sticky="ew", pady=14)
        ttk.Button(foot, text="Save settings", style="Accent.TButton",
                   command=self.save_settings).pack(side="left")
        ttk.Label(foot, text="Stored in emcomm_bbs_config.json next to the app. "
                  "Bulletin and region checkboxes save automatically.",
                  style="Muted.TLabel").pack(side="left", padx=12)

    @staticmethod
    def _interval_row(parent, row, label, var, lo, hi):
        tk.Label(parent, text=label, bg=PALETTE["card"], fg=PALETTE["text"]
                 ).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=4
                    ).grid(row=row, column=1, sticky="w", padx=8, pady=3)
        tk.Label(parent, text="hours", bg=PALETTE["card"], fg=PALETTE["muted"]
                 ).grid(row=row, column=2, sticky="w", pady=3)

    # ---- Welfare tab ------------------------------------------------------

    def _build_welfare_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        folders = Card(top, "Folders", "VarAC drops incoming files in the monitor folder")
        folders.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.welfare_dir_vars = {}
        for r, (key, label) in enumerate((("welfare_monitor_dir", "Monitor"),
                                          ("welfare_archive_dir", "Archive"),
                                          ("welfare_error_dir", "Errors"))):
            var = tk.StringVar()
            self.welfare_dir_vars[key] = var
            tk.Label(folders.body, text=label, bg=PALETTE["card"], fg=PALETTE["text"]
                     ).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Label(folders.body, textvariable=var, style="CardPath.TLabel", wraplength=340
                      ).grid(row=r, column=1, sticky="w", pady=3)
            ttk.Button(folders.body, text="Browse…", command=lambda k=key: self._browse_welfare_dir(k)
                       ).grid(row=r, column=2, sticky="e", padx=(10, 0), pady=3)
        folders.body.columnconfigure(1, weight=1)

        status = Card(top, "Status")
        status.grid(row=0, column=1, sticky="nsew")
        tk.Label(status.body, text="Active window", bg=PALETTE["card"], fg=PALETTE["muted"],
                 font=FONTS["small"]).grid(row=0, column=0, sticky="w")
        self.welfare_window_label = ttk.Label(status.body, text="—", style="CardWarn.TLabel")
        self.welfare_window_label.grid(row=1, column=0, sticky="w", pady=(0, 8))
        tk.Label(status.body, text="Check-ins this window", bg=PALETTE["card"], fg=PALETTE["muted"],
                 font=FONTS["small"]).grid(row=2, column=0, sticky="w")
        self.welfare_count_label = ttk.Label(status.body, text="0", style="CardBig.TLabel")
        self.welfare_count_label.grid(row=3, column=0, sticky="w")

        actions = ttk.Frame(tab)
        actions.grid(row=1, column=0, sticky="ew", pady=12)
        self.welfare_start_btn = ttk.Button(actions, text="Start monitoring", style="Accent.TButton",
                                            command=self.start_welfare_monitoring)
        self.welfare_start_btn.pack(side="left")
        self.welfare_stop_btn = ttk.Button(actions, text="Stop", command=self.stop_welfare_monitoring,
                                           state="disabled")
        self.welfare_stop_btn.pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open board", command=self.view_welfare_board).pack(side="right")
        ttk.Button(actions, text="Check-in template", command=self.open_welfare_template
                   ).pack(side="right", padx=(0, 6))

        logcard = Card(tab, "Check-in activity", padding=10)
        logcard.grid(row=2, column=0, sticky="nsew")
        self.welfare_log_panel = LogPanel(logcard.body, height=10)
        self.welfare_log_panel.pack(fill="both", expand=True)
        self.welfare_log("Welfare Board ready. Start monitoring to watch for check-ins.")

    # ---------------------------------------------------------- UI plumbing

    def ui(self, fn, *args):
        """Run ``fn(*args)`` on the Tk thread."""
        try:
            self.root.after(0, fn, *args)
        except tk.TclError:
            pass  # window already destroyed

    def log(self, message):
        self.log_panel.append(message)

    def welfare_log(self, message):
        self.welfare_log_panel.append(message)

    def set_status(self, text, tone="muted"):
        def _apply():
            self.status_var.set(text)
            self.status_label.configure(foreground=PALETTE.get(tone, PALETTE["muted"]))
            self.status_bar.set(left=text, tone=tone)
        self.ui(_apply)

    def _tick_clock(self):
        service = "auto-updates on" if self._scheduler and self._scheduler.is_alive() else "auto-updates off"
        self.header_right.configure(text=f"{service}   {datetime.now():%a %H:%M}")
        self.status_bar.set(right=f"Output: {self.config.save_directory}")
        self.root.after(15000, self._tick_clock)

    # ------------------------------------------------------------- settings

    def _apply_config_to_widgets(self):
        c = self.config
        self.anthropic_entry.insert(0, c.anthropic_api_key)
        if hasattr(self, "twitter_token_entry"):
            self.twitter_token_entry.insert(0, c.twitter_token)
            self.twitter_handles_entry.insert(0, c.twitter_handles)
        if hasattr(self, "nextdoor_key_entry"):
            self.nextdoor_key_entry.insert(0, c.nextdoor_key)
            self.nextdoor_zips_entry.insert(0, c.nextdoor_zips)
        self.dir_var.set(c.save_directory)
        self.main_interval.set(c.main_interval_hours)
        self.twitter_interval.set(c.twitter_interval_hours)
        for (name, start, end), win in zip(self.window_entries, c.time_windows + [{}] * MAX_TIME_WINDOWS):
            name.insert(0, win.get("name", ""))
            start.insert(0, win.get("start", ""))
            end.insert(0, win.get("end", ""))
        if hasattr(self, "welfare_dir_vars"):
            for key, var in self.welfare_dir_vars.items():
                var.set(getattr(c, key))

    def _collect_settings(self):
        """Read widgets into self.config. Returns an error string or None."""
        c = self.config
        c.anthropic_api_key = self.anthropic_entry.get().strip()
        if hasattr(self, "twitter_token_entry"):
            c.twitter_token = self.twitter_token_entry.get().strip()
            c.twitter_handles = self.twitter_handles_entry.get().strip()
        if hasattr(self, "nextdoor_key_entry"):
            c.nextdoor_key = self.nextdoor_key_entry.get().strip()
            c.nextdoor_zips = self.nextdoor_zips_entry.get().strip()

        directory = self.dir_var.get().strip()
        if not directory:
            return "Choose a bulletin folder."
        c.save_directory = directory

        try:
            c.main_interval_hours = max(1, int(self.main_interval.get()))
            c.twitter_interval_hours = max(1, int(self.twitter_interval.get()))
        except (tk.TclError, ValueError):
            return "Update intervals must be whole hours."

        windows = []
        for name, start, end in self.window_entries:
            n, s, e = name.get().strip(), start.get().strip(), end.get().strip()
            if not n:
                continue
            if not (TIME_RE.match(s) and TIME_RE.match(e)):
                return f"Window '{n}': times must be HH:MM (24-hour)."
            if s >= e:
                return f"Window '{n}': start must be before end."
            windows.append({"name": n, "start": s, "end": e})
        if not windows:
            return "At least one welfare check-in window is required."
        c.time_windows = windows

        c.checkboxes = {k: v.get() for k, v in self.report_vars.items()}
        c.weather_regions = [i for i, v in self.region_vars.items() if v.get()]
        return None

    def save_settings(self):
        error = self._collect_settings()
        if error:
            messagebox.showerror("Settings", error, parent=self.root)
            return
        try:
            self.config.save()
        except OSError as exc:
            messagebox.showerror("Settings", f"Could not write config file:\n{exc}", parent=self.root)
            return
        self._rebuild_fetchers()
        self._configure_welfare()
        self.log("✓ Settings saved")
        self.set_status("Settings saved", "ok")

    def _on_selection_changed(self):
        """Checkbox change: persist silently without validating the rest."""
        self.config.checkboxes = {k: v.get() for k, v in self.report_vars.items()}
        self.config.weather_regions = [i for i, v in self.region_vars.items() if v.get()]
        try:
            self.config.save()
        except OSError as exc:
            self.log(f"⚠ Could not save settings: {exc}")

    def _set_regions(self, value):
        for var in self.region_vars.values():
            var.set(value)
        self._on_selection_changed()

    def _toggle_secrets(self):
        show = "" if self.show_keys_var.get() else "•"
        for entry in self.secret_entries:
            entry.configure(show=show)

    def _browse_save_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.home()),
                                         parent=self.root)
        if chosen:
            self.dir_var.set(chosen)

    def _browse_welfare_dir(self, key):
        var = self.welfare_dir_vars[key]
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()), parent=self.root)
        if chosen:
            var.set(chosen)
            setattr(self.config, key, chosen)
            self.config.save()
            self._configure_welfare(quiet=True)
            self.welfare_log(f"{key.replace('welfare_', '').replace('_dir', '').title()} folder: {chosen}")
            if key == "welfare_monitor_dir" and self.welfare.running:
                self.welfare_log("⚠ Stop and start monitoring to watch the new folder")

    def _rebuild_fetchers(self, quiet=False):
        c = self.config
        self.summarizer.set_api_key(c.anthropic_api_key)

        if SocialMediaEmergencyFetcher and c.twitter_token:
            self.twitter_fetcher = SocialMediaEmergencyFetcher(c.twitter_token,
                                                               c.twitter_handle_list() or None)
            if not quiet:
                self.log(f"✓ X feed configured for {len(self.twitter_fetcher.emergency_accounts)} accounts")
        else:
            self.twitter_fetcher = None

        if NextdoorFetcher and c.nextdoor_key and c.nextdoor_zip_list():
            self.nextdoor_fetcher = NextdoorFetcher(c.nextdoor_key, c.nextdoor_zip_list())
            if not quiet:
                self.log(f"✓ Nextdoor configured for {len(c.nextdoor_zip_list())} ZIP code(s)")
        else:
            self.nextdoor_fetcher = None

    # --------------------------------------------------- bulletin generation

    def _selected_reports(self):
        return [k for k, _, _, _ in REPORTS if k in self.report_vars and self.report_vars[k].get()]

    def generate_now(self):
        kinds = self._selected_reports()
        if not kinds:
            self.log("⚠ Nothing selected - tick at least one bulletin")
            return
        threading.Thread(target=self._run_generation, args=(kinds, "manual"), daemon=True).start()

    def _run_generation(self, kinds, trigger):
        """Worker-thread entry point. Serialised so runs never overlap."""
        if not self._gen_lock.acquire(blocking=False):
            self.log("⚠ A generation run is already in progress")
            return
        self.ui(self.generate_btn.configure, {"state": "disabled"})
        started = time.time()
        try:
            self.log("=" * 12 + f" Generating {len(kinds)} bulletin(s) ({trigger}) " + "=" * 12)
            os.makedirs(self.config.save_directory, exist_ok=True)
            results = {}
            for kind in kinds:
                if self._stop_event.is_set() and trigger == "auto":
                    break
                results[kind] = getattr(self, f"_generate_{kind}")()
            ok = sum(1 for v in results.values() if v)
            elapsed = time.time() - started
            self.log(f"✓ Done: {ok}/{len(results)} bulletin(s) written in {elapsed:.0f}s")
            self.set_status(f"Last run {datetime.now():%H:%M}: {ok}/{len(results)} bulletins",
                            "ok" if ok == len(results) else "warn")
        except OSError as exc:
            self.log(f"✗ Cannot write to {self.config.save_directory}: {exc}")
            self.set_status("Output folder is not writable", "err")
        finally:
            self._gen_lock.release()
            self.ui(self.generate_btn.configure, {"state": "normal"})

    def _write_bulletin(self, prefix, writer):
        """Remove the previous ``prefix*.txt`` and write a fresh one.

        ``writer(path)`` does the actual writing. Returns the new Path.
        """
        out_dir = Path(self.config.save_directory)
        for old in out_dir.glob(f"{prefix}*.txt"):
            try:
                old.unlink()
            except OSError:
                pass
        path = out_dir / f"{prefix}{datetime.now():%m%d_%H%M}.txt"
        writer(str(path))
        self.log(f"✓ {path.name} ({path.stat().st_size:,} bytes)")
        return path

    def _generate_news(self):
        self.set_status("Fetching news…")
        self.log("News: fetching headlines")
        news = self.summarizer.fetch_all_news()
        total = sum(len(h) for h in news.values())
        if not total:
            self.log("⚠ News: no headlines retrieved")
            return False
        self.log(f"  {total} headlines from {len(news)} sources")
        if self.summarizer.api_key:
            self.log("  Asking Claude for a digest…")
        summary = self.summarizer.generate_summary(news)
        if summary.startswith("[AI summary unavailable"):
            self.log("⚠ " + summary.split("]")[0].lstrip("[") + ", using headline digest")
        self._write_bulletin(REPORT_PREFIX["news"],
                             lambda p: PlainTextGenerator.create_news_txt(p, summary, news))
        return True

    def _generate_weather(self):
        regions = [i for i, v in self.region_vars.items() if v.get()]
        if not regions:
            self.log("⚠ Weather: no FEMA regions selected")
            return False
        self.set_status("Fetching weather…")
        self.log(f"Weather: regions {', '.join(f'R{r}' for r in regions)}")
        by_region = WeatherFetcher().get_all_forecasts(regions, self.log, self._stop_event)
        written = 0
        for region in regions:
            forecasts = by_region.get(region, [])
            if not forecasts:
                self.log(f"⚠ Weather: no data for region {region}")
                continue
            self._write_bulletin(
                f"{REPORT_PREFIX['weather']}R{region}_",
                lambda p, r=region, f=forecasts: PlainTextGenerator.create_weather_txt(
                    p, r, f, FEMA_REGIONS.get(r, "")))
            written += 1
        return written > 0

    def _generate_space(self):
        self.set_status("Fetching space weather…")
        self.log("Space weather: querying NOAA SWPC")
        conditions = SpaceWeatherFetcher().get_conditions()
        if conditions.get("solar_flux") is None and conditions.get("k_index") is None:
            self.log("⚠ Space weather: NOAA returned no indices (writing estimate only)")
        self._write_bulletin(REPORT_PREFIX["space"],
                             lambda p: PlainTextGenerator.create_space_txt(p, conditions))
        return True

    def _generate_emergency(self):
        if not self.emergency_fetcher:
            self.log("⚠ Emergency alerts: module not available")
            return False
        self.set_status("Fetching emergency data…")
        self.log("Emergency: querying NWS, USGS, FEMA, NIFC")
        f = self.emergency_fetcher
        data = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        sources = (
            ("nws_alerts", "NWS alerts", f.get_nws_alerts),
            ("usgs_earthquakes", "earthquakes", f.get_recent_earthquakes),
            ("fema_disasters", "FEMA declarations", f.get_fema_disasters),
            ("fire_incidents", "wildfire data", f.get_active_fires),
        )
        for key, label, fetch in sources:
            result = fetch()
            data[key] = result
            if isinstance(result, list):
                if result and result[0].get("error"):
                    self.log(f"⚠   {label}: {result[0]['error']}")
                else:
                    self.log(f"    {label}: {len(result)}")
            elif isinstance(result, dict) and result.get("error"):
                self.log(f"⚠   {label}: {result['error']}")
        self._write_bulletin(REPORT_PREFIX["emergency"],
                             lambda p: PlainTextGenerator.create_emergency_txt(p, data))
        return True

    def _generate_power(self):
        self.set_status("Fetching power outages…")
        self.log("Power: querying DOE / ORNL ODIN")
        outages = PowerOutageFetcher().get_outages(self.log)
        self._write_bulletin(REPORT_PREFIX["power"],
                             lambda p: PlainTextGenerator.create_power_txt(p, outages))
        return not outages.get("error")

    def _generate_twitter(self):
        if not self.twitter_fetcher:
            self.log("⚠ X feed: add a bearer token in Settings")
            return False
        self.set_status("Fetching X feed…")
        self.log("X feed: querying official accounts")
        tweets = self.twitter_fetcher.get_emergency_tweets()
        if isinstance(tweets, dict) and tweets.get("error"):
            self.log(f"⚠   {tweets['error']}")
            for detail in tweets.get("details", [])[:3]:
                self.log(f"      {detail}")
        elif isinstance(tweets, list):
            self.log(f"    {len(tweets)} tweets")
        self._write_bulletin(REPORT_PREFIX["twitter"],
                             lambda p: PlainTextGenerator.create_tweets_txt(p, tweets))
        return isinstance(tweets, list)

    def _generate_nextdoor(self):
        if not self.nextdoor_fetcher:
            self.log("⚠ Nextdoor: add an API key and ZIP codes in Settings")
            return False
        self.set_status("Fetching Nextdoor…")
        self.log("Nextdoor: querying local posts")
        posts = self.nextdoor_fetcher.get_local_posts()
        if isinstance(posts, dict) and posts.get("error"):
            self.log(f"⚠   {posts['error']}")
            return False
        if isinstance(posts, list):
            stats = self.nextdoor_fetcher.get_statistics(posts) or {}
            urg = stats.get("by_urgency", {})
            self.log(f"    {len(posts)} posts - critical {urg.get('critical', 0)}, "
                     f"high {urg.get('high', 0)}, medium {urg.get('medium', 0)}")
        self._write_bulletin(REPORT_PREFIX["nextdoor"],
                             lambda p: PlainTextGenerator.create_nextdoor_txt(
                                 p, posts, self.nextdoor_fetcher.zip_codes))
        return True

    # ------------------------------------------------------------ scheduler

    def start_service(self):
        if self._scheduler and self._scheduler.is_alive():
            return
        error = self._collect_settings()
        if error:
            messagebox.showerror("Settings", error, parent=self.root)
            return
        kinds = self._selected_reports()
        if not kinds:
            self.log("⚠ Nothing selected - tick at least one bulletin")
            return
        self.config.save()
        self._rebuild_fetchers(quiet=True)

        self._stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        main_h, tw_h = self.config.main_interval_hours, self.config.twitter_interval_hours
        separate_twitter = "twitter" in kinds and self.twitter_fetcher and tw_h != main_h
        if separate_twitter:
            self.log(f"Auto-updates started: bulletins every {main_h}h, X feed every {tw_h}h")
        else:
            self.log(f"Auto-updates started: every {main_h}h")
        self._scheduler = threading.Thread(target=self._scheduler_loop, args=(kinds, separate_twitter),
                                           daemon=True, name="scheduler")
        self._scheduler.start()
        self._tick_clock()

    def stop_service(self):
        self._stop_event.set()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.log("Auto-updates stopped")
        self.set_status("Auto-updates stopped")
        self._tick_clock()

    def _scheduler_loop(self, kinds, separate_twitter):
        main_kinds = [k for k in kinds if not (separate_twitter and k == "twitter")]
        now = time.time()
        self._next_run = {"main": now}
        if separate_twitter:
            self._next_run["twitter"] = now

        while not self._stop_event.is_set():
            now = time.time()
            if now >= self._next_run["main"]:
                self._run_generation(main_kinds, "auto")
                self._next_run["main"] = time.time() + self.config.main_interval_hours * 3600
            if "twitter" in self._next_run and now >= self._next_run["twitter"]:
                self._run_generation(["twitter"], "auto")
                self._next_run["twitter"] = time.time() + self.config.twitter_interval_hours * 3600

            soonest = min(self._next_run.values())
            remaining = max(0, soonest - time.time())
            h, m = divmod(int(remaining // 60), 60)
            self.ui(self.status_bar.set, f"Auto-updates on - next run in {h}h {m:02d}m")
            self._stop_event.wait(min(30, remaining or 1))

    # -------------------------------------------------------- welfare board

    def _configure_welfare(self, quiet=False):
        if not WELFARE_AVAILABLE:
            return
        cfg = self.config.welfare_config()
        if self.welfare is None:
            self.welfare = WelfarePipeline(cfg, self.welfare_log, self._on_welfare_update)
        else:
            self.welfare.reconfigure(cfg)
        if not quiet:
            names = ", ".join(f"{w['name']} {w['start']}-{w['end']}" for w in cfg["time_windows"])
            self.welfare_log(f"Windows: {names}")
        self._refresh_welfare_status()

    def start_welfare_monitoring(self):
        try:
            self.welfare.start()
        except OSError as exc:
            messagebox.showerror("Welfare Board",
                                 f"Cannot watch {self.config.welfare_monitor_dir}:\n{exc}",
                                 parent=self.root)
            return
        self.welfare_start_btn.configure(state="disabled")
        self.welfare_stop_btn.configure(state="normal")

    def stop_welfare_monitoring(self):
        self.welfare.stop()
        self.welfare_start_btn.configure(state="normal")
        self.welfare_stop_btn.configure(state="disabled")

    def _on_welfare_update(self, window, count):
        """Pipeline callback (watchdog thread) after a check-in is accepted."""
        self.ui(self.welfare_count_label.configure, {"text": str(count)})

    def _refresh_welfare_status(self):
        if not self.welfare:
            return
        window = self.welfare.current_window()
        if window:
            self.welfare_window_label.configure(
                text=f"{window['name']}  {window['start']}–{window['end']}", style="CardOk.TLabel")
            self.welfare_count_label.configure(text=str(self.welfare.current_count()))
        else:
            self.welfare_window_label.configure(text="None active", style="CardWarn.TLabel")

    def _welfare_tick(self):
        self._refresh_welfare_status()
        self.root.after(60000, self._welfare_tick)

    def view_welfare_board(self):
        board = Path(self.config.save_directory) / "welfare_board.html"
        if board.exists():
            webbrowser.open(board.as_uri())
        else:
            messagebox.showinfo("Welfare Board", "No board has been generated yet.\n"
                                "Start monitoring and drop a check-in file in the monitor folder.",
                                parent=self.root)

    def open_welfare_template(self):
        if not WELFARE_TEMPLATE.exists():
            WELFARE_TEMPLATE.write_text(DEFAULT_TEMPLATE_TEXT, encoding="utf-8")
        try:
            if sys.platform == "win32":
                os.startfile(WELFARE_TEMPLATE)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.call(["open", str(WELFARE_TEMPLATE)])
            else:
                subprocess.call(["xdg-open", str(WELFARE_TEMPLATE)])
        except OSError as exc:
            self.welfare_log(f"⚠ Could not open template: {exc}")

    # ----------------------------------------------------------------- exit

    def _on_close(self):
        self._stop_event.set()
        if self.welfare:
            self.welfare.stop()
        self.root.destroy()


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    root = tk.Tk()
    EmcommApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
