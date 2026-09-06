"""
Emcomm BBS - Welfare Board pipeline

Ties the welfare modules together so both GUIs share one implementation:

    incoming .txt  ->  WelfareParser  ->  WelfareValidator  ->  WelfareAggregator
                                                                     |
                   archive/ or error/  <-  move file  <-  OutputGenerator (TXT/HTML/CSV)

``WelfarePipeline.process_file`` is invoked on the watchdog thread; the
``log`` and ``on_update`` callbacks must therefore be thread-safe (the Tk
GUIs marshal them onto the event loop).
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from welfare_parser import WelfareParser
from validator import WelfareValidator
from aggregator import WelfareAggregator
from output_generator import OutputGenerator
from file_watcher import WelfareFileWatcher

log = logging.getLogger(__name__)


class WelfarePipeline:
    """Watches a folder for check-ins and keeps the board outputs current.

    ``config`` is the welfare config dict (see ``AppConfig.welfare_config``
    or ``settings.json``): ``time_windows``, ``validation``, ``output`` and
    ``directories`` with ``input``, ``archive``, ``error`` and ``output``.
    """

    def __init__(self, config, log_callback=None, on_update=None):
        self.log = log_callback or (lambda msg: log.info(msg))
        self.on_update = on_update
        self.parser = WelfareParser()
        self.watcher = None
        self.aggregator = None
        self.reconfigure(config)

    # ------------------------------------------------------------ config

    def reconfigure(self, config):
        """Apply new settings. Today's check-ins survive the reconfigure."""
        self.config = config
        self.dirs = {k: Path(v) for k, v in config.get('directories', {}).items()}
        self.validator = WelfareValidator(config)
        previous = self.aggregator
        self.aggregator = WelfareAggregator(config)
        if previous is not None:
            self.aggregator.checkins = previous.checkins
        self.output = OutputGenerator(config)

    @property
    def time_windows(self):
        return self.aggregator.time_windows

    def current_window(self):
        return self.aggregator.get_current_window()

    def current_count(self):
        window = self.current_window()
        return self.aggregator.get_window_count(window['key']) if window else 0

    # ----------------------------------------------------------- watcher

    @property
    def running(self):
        return bool(self.watcher and self.watcher.is_running())

    def start(self):
        """Begin watching the input folder. Raises OSError if it can't be created."""
        if self.running:
            return
        monitor = self.dirs['input']
        monitor.mkdir(parents=True, exist_ok=True)
        self.watcher = WelfareFileWatcher(monitor, self.process_file)
        self.watcher.start()
        self.log(f"✓ Monitoring {monitor}")
        window = self.current_window()
        if window:
            self.log(f"  Active window: {window['name']} ({window['start']}-{window['end']})")
        else:
            self.log("⚠ No window is active right now - check-ins will be rejected until one opens")

    def stop(self):
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
            self.log("Monitoring stopped")

    # -------------------------------------------------------- processing

    def process_file(self, filepath):
        """Parse, validate, aggregate and publish one check-in file."""
        filepath = Path(filepath)
        if not filepath.exists():
            return  # already handled by an earlier filesystem event
        self.log(f"New file: {filepath.name}")
        try:
            parsed = self.parser.parse_file(filepath)
            if not parsed:
                self._move(filepath, error="Parse failed")
                return

            valid, errors = self.validator.validate(parsed)
            if not valid:
                for err in errors:
                    self.log(f"  ✗ {err}")
                self._move(filepath, error="; ".join(errors))
                return

            ok, message, window = self.aggregator.add_checkin(parsed)
            if not ok:
                if "identical" in message.lower():
                    self.log(f"  Duplicate ignored: {message}")
                    self._move(filepath)
                else:
                    self.log(f"  ⚠ {message}")
                    self._move(filepath, error=message)
                return

            self.log(f"  ✓ {message}")
            checkins = self.aggregator.get_window_checkins(window['key'])
            generated = self.output.generate_all(window, checkins)
            if generated:
                self.log("  Board updated: " + ", ".join(Path(p).name for p in generated.values()))
            self._move(filepath)
            if self.on_update:
                self.on_update(window, len(checkins))
        except Exception as exc:  # noqa: BLE001 - keep the watcher alive
            log.exception("Welfare processing failed for %s", filepath)
            self.log(f"  ✗ Error: {exc}")
            self._move(filepath, error=str(exc))

    def _move(self, filepath, error=None):
        """Archive a processed file, or park it in the error folder with a
        companion ``.error.txt`` explaining why."""
        target_dir = self.dirs['error'] if error else self.dirs['archive']
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = target_dir / filepath.name
            if dest.exists():
                dest = target_dir / f"{filepath.stem}_{datetime.now():%Y%m%d_%H%M%S}{filepath.suffix}"
            shutil.move(str(filepath), str(dest))
            if error:
                dest.with_suffix(".error.txt").write_text(
                    f"Error: {error}\nTime: {datetime.now()}\n", encoding="utf-8")
                self.log(f"  ✗ Moved to error folder: {error}")
            else:
                self.log(f"  Archived as {dest.name}")
        except OSError as exc:
            self.log(f"  ✗ Could not move {filepath.name}: {exc}")
