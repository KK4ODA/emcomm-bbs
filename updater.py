"""
Emcomm BBS - Self-update

Checks the GitHub Releases API for a newer tag than the running version and
installs it in place:

* if the app folder is a git clone and git is on PATH: ``git pull --ff-only``
* otherwise: download the release zip, back up the files it replaces, and
  copy the new files over the old ones

Operator data is never touched: ``emcomm_bbs_config.json``, ``settings.json``,
``data/`` and ``.git/`` are left alone. After a successful update
``requirements.txt`` is reinstalled and the caller restarts the process.
"""

import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from version import __version__

log = logging.getLogger(__name__)

REPO = "KK4ODA/emcomm-bbs"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
USER_AGENT = f"EmcommBBS/{__version__} (+https://github.com/{REPO})"
TIMEOUT = 15

# Never overwritten or deleted by an update.
PRESERVE = {"emcomm_bbs_config.json", "settings.json", "data", ".git", ".update-backup",
            "__pycache__", "welfare_board.html"}
BACKUP_DIR = ".update-backup"


class UpdateError(Exception):
    """Raised when a check or install cannot complete; message is operator-friendly."""


@dataclass
class UpdateInfo:
    version: str          # "1.5.0"
    tag: str              # "v1.5.0"
    title: str
    notes: str            # release body (markdown)
    html_url: str
    zip_url: str
    published: str        # ISO date


def parse_version(text):
    """'v1.4.0' -> (1, 4, 0). Non-numeric suffixes are ignored."""
    parts = re.findall(r"\d+", text or "")
    return tuple(int(p) for p in parts[:4]) or (0,)


def is_newer(candidate, current=__version__):
    return parse_version(candidate) > parse_version(current)


def check_for_update(current=__version__):
    """Return an UpdateInfo when a newer release exists, else None.

    Raises UpdateError when GitHub cannot be reached.
    """
    try:
        r = requests.get(LATEST_URL, timeout=TIMEOUT, headers={
            "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
        if r.status_code == 404:
            return None                     # no releases published yet
        if r.status_code == 403 and "rate limit" in r.text.lower():
            raise UpdateError("GitHub rate limit reached - try again in an hour")
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        raise UpdateError(f"could not reach GitHub ({exc.__class__.__name__})") from exc
    except ValueError as exc:
        raise UpdateError("unexpected response from GitHub") from exc

    tag = data.get("tag_name", "")
    if not tag or not is_newer(tag, current):
        return None
    return UpdateInfo(
        version=".".join(str(p) for p in parse_version(tag)),
        tag=tag,
        title=data.get("name") or tag,
        notes=(data.get("body") or "").strip(),
        html_url=data.get("html_url") or RELEASES_PAGE,
        zip_url=data.get("zipball_url") or f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip",
        published=(data.get("published_at") or "")[:10],
    )


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def _git_available():
    return shutil.which("git") is not None


def install_update(info, app_dir, log_callback=None, install_requirements=True):
    """Install ``info`` into ``app_dir``. Returns 'git' or 'zip'.

    Raises UpdateError with a readable message on failure; the previous
    files remain in place (git) or are restored from the backup (zip).
    """
    say = log_callback or (lambda m: log.info(m))
    app_dir = Path(app_dir)

    method = None
    if (app_dir / ".git").is_dir() and _git_available():
        say("Updating with git pull…")
        try:
            _git_pull(app_dir, info.tag, say)
            method = "git"
        except UpdateError as exc:
            say(f"⚠ git update failed ({exc}); falling back to the release zip")

    if method is None:
        say(f"Downloading {info.tag} from GitHub…")
        method = "zip"
        _zip_update(info, app_dir, say)

    if install_requirements and (app_dir / "requirements.txt").exists():
        say("Installing requirements…")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r",
                            str(app_dir / "requirements.txt")],
                           cwd=str(app_dir), check=False, timeout=600,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            say(f"⚠ Could not install requirements automatically: {exc}")
    return method


def _git_pull(app_dir, tag, say):
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=str(app_dir), capture_output=True,
                                  text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpdateError(f"git {args[0]}: {exc}") from exc

    status = run("status", "--porcelain")
    if status.returncode != 0:
        raise UpdateError(status.stderr.strip() or "git status failed")
    dirty = [l for l in status.stdout.splitlines() if l.strip()]
    if dirty:
        raise UpdateError(f"{len(dirty)} locally modified file(s) would be overwritten")

    fetch = run("fetch", "--tags", "origin")
    if fetch.returncode != 0:
        raise UpdateError(fetch.stderr.strip() or "git fetch failed")
    pull = run("pull", "--ff-only", "origin")
    if pull.returncode != 0:
        raise UpdateError(pull.stderr.strip().splitlines()[-1] if pull.stderr.strip() else "git pull failed")
    say(f"✓ Repository at {tag}")


def _zip_update(info, app_dir, say):
    try:
        r = requests.get(info.zip_url, timeout=60, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(r.content))
    except requests.RequestException as exc:
        raise UpdateError(f"download failed ({exc.__class__.__name__})") from exc
    except zipfile.BadZipFile as exc:
        raise UpdateError("downloaded file is not a valid zip") from exc

    with tempfile.TemporaryDirectory(prefix="emcomm_update_") as tmp:
        archive.extractall(tmp)
        roots = [p for p in Path(tmp).iterdir() if p.is_dir()]
        source = roots[0] if len(roots) == 1 and not (Path(tmp) / "emcomm_bbs.py").exists() else Path(tmp)
        if not (source / "emcomm_bbs.py").exists():
            raise UpdateError("release zip does not look like Emcomm BBS")
        apply_tree(source, app_dir, say)
    say(f"✓ Files updated to {info.tag}")


def apply_tree(source, app_dir, say=None):
    """Copy ``source`` over ``app_dir`` (skipping PRESERVE), backing up every
    file that gets replaced into ``app_dir/.update-backup/``.

    On any copy error the backed-up files are restored before re-raising.
    """
    say = say or (lambda m: None)
    source, app_dir = Path(source), Path(app_dir)
    backup = app_dir / BACKUP_DIR
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "README.txt").write_text(
        f"Files replaced by the update on {datetime.now():%Y-%m-%d %H:%M}.\n"
        "Copy them back over the app folder to roll back.\n", encoding="utf-8")

    copied = []
    try:
        for src in source.rglob("*"):
            rel = src.relative_to(source)
            if any(part in PRESERVE for part in rel.parts):
                continue
            dest = app_dir / rel
            if src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            if dest.exists():
                bak = backup / rel
                bak.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, bak)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(rel)
    except OSError as exc:
        for rel in copied:
            bak = backup / rel
            if bak.exists():
                shutil.copy2(bak, app_dir / rel)
        raise UpdateError(f"could not write {exc.filename or 'files'}: {exc.strerror or exc}") from exc
    say(f"  {len(copied)} file(s) written, previous copies in {BACKUP_DIR}/")
    return copied


def restart_app(script):
    """Launch a fresh copy of ``script`` detached from this process."""
    args = [sys.executable, str(script)]
    kwargs = {"cwd": str(Path(script).parent), "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)  # noqa: S603


def install_kind(app_dir):
    """'git' when the folder is a clone with git available, else 'zip'."""
    return "git" if (Path(app_dir) / ".git").is_dir() and _git_available() else "zip"


if __name__ == "__main__":
    # Command-line check:  python updater.py
    try:
        info = check_for_update()
    except UpdateError as exc:
        print(f"Update check failed: {exc}")
        sys.exit(1)
    if info is None:
        print(f"Emcomm BBS {__version__} is up to date.")
    else:
        print(f"Update available: {info.version} (you have {__version__})\n{info.html_url}\n")
        print(info.notes)
