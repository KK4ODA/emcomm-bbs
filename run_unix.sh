#!/usr/bin/env bash
# Emcomm BBS - Linux / macOS launcher
# Checks Python and tkinter, installs missing packages, starts the GUI.
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else
    echo "Python 3.8+ is required. Install it with your package manager or from python.org." >&2
    exit 1
fi

if ! $PY -c "import tkinter" 2>/dev/null; then
    echo "tkinter is missing." >&2
    echo "  Debian/Ubuntu: sudo apt-get install python3-tk" >&2
    echo "  Fedora:        sudo dnf install python3-tkinter" >&2
    echo "  macOS (brew):  brew install python-tk" >&2
    exit 1
fi

if ! $PY -c "import requests, watchdog" 2>/dev/null; then
    echo "Installing dependencies from requirements.txt ..."
    $PY -m pip install --quiet -r requirements.txt || {
        echo "Dependency install failed. Try: $PY -m pip install -r requirements.txt" >&2
        exit 1
    }
fi

exec $PY emcomm_bbs.py
