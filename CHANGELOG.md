# Changelog

All notable changes to Emcomm BBS are recorded here.
This project follows [Semantic Versioning](https://semver.org/).

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
