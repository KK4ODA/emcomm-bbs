# Emcomm BBS

**A desktop companion for amateur radio emergency communications.** It pulls
situational-awareness data from public sources and renders it as ultra-compact
plain-text bulletins sized for low-bandwidth HF links — VarAC, Winlink, packet —
plus a Welfare Board that turns incoming check-in files into a live roster.

Typical bulletin is **5–15 KB**, roughly 90% smaller than the equivalent PDF.

---

## Modules

| Module | What it gives you | Source |
|---|---|---|
| **News Summary** | Top headlines, optionally condensed by AI | BBC, AP |
| **Weather** | 7-day forecasts, selectable by FEMA region | NWS |
| **Space Weather** | Solar flux, K-index, HF band conditions | NOAA SWPC |
| **Emergency Alerts** | Active alerts, earthquakes, declared disasters, wildfires | NWS, USGS, FEMA |
| **Power Outages** | Live outage counts by state/county | DOE / ORNL ODIN |
| **Social Feed** | Posts from official emergency accounts | X/Twitter API |
| **Nextdoor** | Local neighborhood reports (agency API required) | Nextdoor |
| **Welfare Board** | Watches a folder for check-in files, publishes HTML/TXT/CSV roster | Local files |

Everything except the AI summary, social feed, and Nextdoor works with **no API
keys at all**.

---

## Quick start — Windows

1. Install [Python 3.8+](https://www.python.org/downloads/) and tick **"Add Python to PATH"**.
2. Download this repository (green **Code** button → **Download ZIP**) and extract it.
3. Double-click **`RUN.bat`**. It installs what's missing and launches the app.
4. Pick your modules and click **Generate Now**.

Reports land in `C:\VarAC BBS\` by default — change it on the Settings tab.

For the full launcher with dependency checks and data-folder setup, use
**`RUN_EMERGENCY_SUITE.bat`** instead.

## Quick start — Linux / macOS

```bash
chmod +x run_unix.sh
./run_unix.sh
```

## Manual install

```bash
pip install -r requirements.txt
python emcomm_bbs.py
```

On Linux you may also need tkinter: `sudo apt-get install python3-tk`.

---

## Configuration

On first run the app writes **`emcomm_bbs_config.json`** next to the script.
This file holds your API keys and is **excluded from version control** — see
`.gitignore`.

To start from a template:

```bash
cp emcomm_bbs_config.example.json emcomm_bbs_config.json
```

| Key | Needed for | Where to get it |
|---|---|---|
| `anthropic_api_key` | AI news summaries | [console.anthropic.com](https://console.anthropic.com/) |
| `twitter_token` | Social emergency feed | X/Twitter developer portal |
| `nextdoor_key` | Nextdoor reports | Nextdoor agency program |

Leave any of them blank to disable that feature. Without an Anthropic key you
still get plain headline lists.

> **Never commit `emcomm_bbs_config.json`.** If a key ever lands in a commit,
> revoke it at the provider immediately — rewriting history is not enough.

---

## Welfare Board

The Welfare Board watches a folder (typically your VarAC **Files in**
directory) for `.txt` check-in messages, validates them, groups them into
configurable time windows, and publishes a self-refreshing
`welfare_board.html` alongside TXT and CSV versions.

Operators fill out `welfare_checkin_template.txt`:

```
CALLSIGN: W1ABC
NAME: Jane Doe
LOCATION: Springfield, MA
STATUS: SAFE
MESSAGE: All well here, no damage.
```

Valid statuses are `SAFE`, `NEED ASSISTANCE`, and `TRAFFIC` — configurable in
`settings.json`. See `examples/` for complete samples and
`docs/Emcomm_BBS_User_Guide.txt` for the full setup walkthrough.

Processed files move to an archive folder; files that fail validation move to
an error folder with a companion `.error.txt` explaining why.

---

## Repository layout

```
emcomm_bbs.py                  Main GUI application
emergency_module.py            NWS / USGS / FEMA / wildfire / social fetchers
emergency_checker.py           Standalone CLI emergency check (no GUI)
nextdoor_module.py             Nextdoor integration
plaintext_generators.py        Compact .txt bulletin formatters

welfare_board.py               Standalone Welfare Board GUI
parser.py                      Check-in file parser
validator.py                   Check-in field validation
aggregator.py                  Time-window grouping
output_generator.py            HTML / TXT / CSV board output
file_watcher.py                Directory watcher
test_time_windows.py           Time-window sanity test

settings.json                  Welfare Board settings (no secrets)
emcomm_bbs_config.example.json Template for your own config
welfare_checkin_template.txt   Template operators fill out
examples/                      Sample check-in files
docs/                          Full user guide

RUN.bat                        Windows launcher
RUN_EMERGENCY_SUITE.bat        Windows launcher with full preflight checks
run_unix.sh                    Linux / macOS launcher
```

---

## Standalone emergency check

No GUI, prints current conditions to the console:

```bash
python emergency_checker.py
```

---

## Data sources and terms

All feeds are public government or public-media sources. Respect their rate
limits and terms of use. This software is provided for amateur radio emergency
communications support — **it is not an official alerting system**. Always
confirm life-safety information through official channels.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

## Author

**KK4ODA** · <https://github.com/KK4ODA>
