# Changelog

All notable changes to Emcomm BBS are recorded here.
This project follows [Semantic Versioning](https://semver.org/).

## [1.4.0] — 2026-09-06

A cleanup release: same bulletins, same file names, much less code, and a
new look for the desktop app.

### Changed

- **Redesigned GUI.** Dark header bar, card-based layout, amber primary
  buttons, a color-coded activity log, a status bar with the output folder
  and next scheduled run, and a Settings tab that scrolls instead of being
  cut off at the bottom of the window. Bulletin checkboxes now carry a
  one-line description of what each one produces.
- **Settings are applied with one "Save settings" button** instead of a
  separate Set/Update button per field. Bulletin and region checkboxes still
  save themselves. A "Show keys" toggle reveals the API keys.
- **Welfare Board folders are now remembered** between runs (they were reset
  to the auto-detected default on every start).
- `emcomm_bbs.py` shrank from 4,000 lines to about 750. Data fetchers moved
  to `data_sources.py`, settings to `app_config.py`, the look and feel to
  `ui_theme.py`, and the welfare check-in pipeline to `welfare_pipeline.py`
  where both GUIs share it.
- Weather forecasts for a region are fetched four cities at a time instead
  of one after another, so a region completes in a fraction of the time.
- The auto-update scheduler uses a single thread with an interruptible wait
  instead of two threads polling every ten seconds. Stopping is immediate.
- Every previous bulletin of a given type is replaced when a new one is
  written. Power-outage and Nextdoor files were previously never cleaned up,
  and no cleanup at all happened if News was unticked.
- Headlines come from the BBC and NPR RSS feeds instead of scraping front
  pages. AP now returns HTTP 403 to automated clients, so the AP source was
  silently empty; RSS is stable and drops the BeautifulSoup dependency.
- AI news digests now use the current `claude-opus-5` model, ask for
  radio-friendly plain text (no markdown), and fall back to a headline digest
  with the reason in the bulletin if the request fails.
- All network fetchers identify as `EmcommBBS/<version>` with the project URL,
  as the NWS API requests, instead of a placeholder e-mail address.
- Word wrapping in the bulletin formatters is one shared helper built on
  `textwrap`; long URLs are no longer split mid-word.
- The standalone `welfare_board.py` can now edit time windows in its settings
  dialog (previously a TODO) and uses the same theme as the main app.
- `emergency_checker.py` includes live ODIN power-outage counts and drops the
  "check your utility website" placeholder sections.
- Nextdoor keyword classification now actually escalates a post's urgency;
  before, its result was computed and never used.
- `parser.py` was renamed to `welfare_parser.py` (the old name shadows a
  standard-library module on Python 3.9 and earlier).
- `RUN.bat` installs everything in `requirements.txt` when a package is
  missing. `RUN_EMERGENCY_SUITE.bat` was merged into it.
- `run_unix.sh` was rewritten; it no longer references files that do not
  exist.

### Fixed

- The wildfire section of the emergency bulletin was always empty: the NASA
  FIRMS endpoint it called now requires an API key and returns HTTP 400.
  Wildfire data now comes from NIFC's public WFIGS feed and lists the
  national incident count plus the largest active fires with acreage and
  containment.
- The app crashed at startup with `NameError: messagebox` when applying
  time windows or when the Welfare Board hit an error, because `messagebox`
  was never imported.
- The app would not start at all without the optional `anthropic` package
  installed; it is now imported only when an API key is used.
- Worker threads updated Tk widgets directly, which can freeze or crash
  Tkinter; every cross-thread update now goes through the event loop.
- The Welfare Board's HTML now escapes operator-supplied text, so a `<` in
  a message cannot break the page.
- Earthquake times were formatted in local time but labelled UTC.
- `_default_varac_dir()` fell back to a *relative* `data/` path, which
  depended on the working directory the app was launched from.
- Duplicate `setup_main_tab` and `select_directory` definitions, the unused
  CNN scraper, the unused mock Nextdoor data, ~1,500 lines of unreachable
  PDF/HTML generators, and the `reportlab` dependency were removed.

### Added

- `tests/test_emcomm.py` — offline unit tests for the parser, validator,
  aggregator, board output, bulletin formatters, config, and data helpers.
  Run with `python -m unittest discover -s tests`.

### Removed

- `SETUP-GITHUB.bat` and `FIX-FIRST-PUSH.bat` (one-time scripts; the
  repository is published). `PUSH-TO-GITHUB.bat` and `PULL-FROM-GITHUB.bat`
  remain.
- `test_time_windows.py` (superseded by the unit tests).

## [1.3.0] — 2026-08-15

First release published to this repository.

### Added

- **Emergency suite launcher** (`RUN_EMERGENCY_SUITE.bat`) with Python,
  module, dependency, and data-folder preflight checks.
- **Standalone emergency checker** (`emergency_checker.py`) — console-only
  current-conditions report, no GUI required.
- **Standalone Welfare Board GUI** (`welfare_board.py`) that runs independently
  of the main application.
- `examples/EXAMPLE_non_ham_welfare.txt` and
  `examples/EXAMPLE_KK4ODA_welfare_with_contact.txt` — check-in samples for
  non-licensed persons and for check-ins carrying contact details.
- `emcomm_bbs_config.example.json` template so a fresh clone can be configured
  without a first run.
- `test_time_windows.py` time-window grouping sanity test.

### Changed

- Welfare Board default folders are now **auto-detected** across common VarAC
  locations under the user profile instead of a hard-coded path, falling back
  to the bundled `data/` directories.
- `run_unix.sh` now launches `emcomm_bbs.py` (it previously pointed at the
  retired `news_summarizer.py` and could not start).
- `requirements.txt` now declares `reportlab` and `watchdog`, which the code
  imports but the previous list omitted.
- Expanded welfare parsing, validation, and output generation.

### Security

- `.gitignore` hardened to exclude `emcomm_bbs_config.json` and any generated
  board or report output, so API keys and check-in data stay local.

## [1.2.0]

- Welfare Board integrated as a tab in the main application.
- Time-window grouping of check-ins.
- HTML board with auto-refresh, plus TXT and CSV output.

## [1.1.0]

- Emergency alerts module: NWS alerts, USGS earthquakes, FEMA disasters.
- Power outage counts.
- Compact plain-text output replacing PDF as the default.

## [1.0.0]

- Initial application: news headlines, NWS weather by FEMA region, NOAA space
  weather, optional AI summaries.
