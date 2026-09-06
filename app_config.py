"""
Emcomm BBS - Configuration

All operator settings live in ``emcomm_bbs_config.json`` next to the
application. The file holds API keys, so it is git-ignored; see
``emcomm_bbs_config.example.json`` for a template.
"""

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "emcomm_bbs_config.json"

DEFAULT_TWITTER_HANDLES = "NWS,fema,USGS_Quakes,NWSAlerts,CDCgov,NHC_Atlantic"
DEFAULT_TIME_WINDOWS = [{"name": "All Day", "start": "00:00", "end": "23:59"}]
DEFAULT_CHECKBOXES = {
    "news": True,
    "weather": True,
    "space": True,
    "emergency": True,
    "power": True,
    "twitter": False,
    "nextdoor": False,
}
VALID_STATUSES = ["SAFE", "NEED ASSISTANCE", "TRAFFIC"]
MAX_TIME_WINDOWS = 3


def default_save_directory():
    """Where bulletins go unless the operator picks somewhere else."""
    if sys.platform == "win32":
        return r"C:\VarAC BBS"
    return str(Path.home() / "VarAC BBS")


def default_varac_dir(subfolder=""):
    """Best-effort guess at the VarAC "Files in" folder.

    Falls back to the bundled ``data/`` directories so the app works on any
    machine; the operator can always override with Browse.
    """
    home = Path.home()
    candidates = [
        *home.glob("Dropbox*/Ham Radio/Digital Modes/VarAC/Files in"),
        home / "Documents" / "VarAC" / "Files in",
        Path("C:/VarAC/Files in"),
    ]
    for base in candidates:
        try:
            if base.is_dir():
                return str(base / subfolder if subfolder else base)
        except OSError:
            continue
    fallback = {"": "input", "welfare_archive": "archive", "welfare_error": "error"}
    return str(APP_DIR / "data" / fallback.get(subfolder, "input"))


def _csv_list(value):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass
class AppConfig:
    save_directory: str = field(default_factory=default_save_directory)
    anthropic_api_key: str = ""
    twitter_token: str = ""
    twitter_handles: str = DEFAULT_TWITTER_HANDLES
    nextdoor_key: str = ""
    nextdoor_zips: str = ""
    main_interval_hours: int = 6
    twitter_interval_hours: int = 6
    weather_regions: list = field(default_factory=lambda: [4])
    checkboxes: dict = field(default_factory=lambda: dict(DEFAULT_CHECKBOXES))
    time_windows: list = field(default_factory=lambda: [dict(w) for w in DEFAULT_TIME_WINDOWS])
    welfare_monitor_dir: str = field(default_factory=default_varac_dir)
    welfare_archive_dir: str = field(default_factory=lambda: default_varac_dir("welfare_archive"))
    welfare_error_dir: str = field(default_factory=lambda: default_varac_dir("welfare_error"))
    check_updates: bool = True          # look for a new GitHub release at startup
    skipped_version: str = ""           # release the operator chose to ignore
    last_update_check: str = ""         # YYYY-MM-DD of the last automatic check

    # ------------------------------------------------------------------ I/O

    @classmethod
    def load(cls, path=CONFIG_FILE):
        """Load settings, tolerating a missing file or unknown keys."""
        cfg = cls()
        path = Path(path)
        if not path.exists():
            return cfg
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            log.warning("Could not read %s: %s", path, exc)
            return cfg

        known = {f for f in cfg.__dataclass_fields__}
        for key, value in data.items():
            if key not in known or value is None:
                continue
            if key == "checkboxes" and isinstance(value, dict):
                cfg.checkboxes.update({k: bool(v) for k, v in value.items() if k in cfg.checkboxes})
            elif key == "time_windows" and isinstance(value, list):
                cfg.time_windows = [dict(w) for w in value if isinstance(w, dict)] or cfg.time_windows
            elif key == "weather_regions" and isinstance(value, list):
                cfg.weather_regions = [int(r) for r in value if str(r).isdigit()]
            elif key.endswith("_hours"):
                try:
                    setattr(cfg, key, max(1, int(value)))
                except (TypeError, ValueError):
                    pass
            elif key == "check_updates":
                cfg.check_updates = bool(value)
            else:
                setattr(cfg, key, value)
        return cfg

    def save(self, path=CONFIG_FILE):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    # ------------------------------------------------------------- helpers

    def twitter_handle_list(self):
        return _csv_list(self.twitter_handles)

    def nextdoor_zip_list(self):
        return _csv_list(self.nextdoor_zips)

    def welfare_config(self):
        """Config dict expected by the welfare validator/aggregator/output modules."""
        return {
            "time_windows": [dict(w) for w in self.time_windows],
            "validation": {
                "require_callsign": False,
                "require_name": True,
                "require_location": True,
                "require_status": True,
                "valid_statuses": list(VALID_STATUSES),
            },
            "output": {
                "generate_text": True,
                "generate_html": True,
                "generate_csv": True,
                "html_auto_refresh": 30,
            },
            "directories": {
                "input": self.welfare_monitor_dir,
                "archive": self.welfare_archive_dir,
                "error": self.welfare_error_dir,
                "output": self.save_directory,
            },
        }
