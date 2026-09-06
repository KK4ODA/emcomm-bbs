"""
Emcomm BBS - Self-update

Checks the GitHub Releases API for a newer tag than the running version and
installs it in the way that fits how the app was installed:

    installed   Windows installer build (uninstaller beside the exe): download
                Emcomm-BBS-Setup-<ver>.exe, verify size and SHA-256 against the
                release's SHA256SUMS.txt, then hand over to a small batch helper
                that waits for the app to exit, runs the installer silently and
                starts the app again.
    portable    portable zip build: download the new zip, unpack it, and let the
                same kind of helper copy it over the app folder after exit.
    git         source checkout with git on PATH: ``git pull --ff-only``
    zip         plain source folder: download the source zip, back up the files
                it replaces into .update-backup/, copy the new files in.

Operator data is never touched: the config file, ``settings.json``,
``data/`` and ``.git/`` are left alone. For the source modes
``requirements.txt`` is reinstalled and the caller restarts the process; for
the frozen modes the helper does the restart.
"""

import hashlib
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests

from app_config import DATA_DIR, EXE_DIR, FROZEN
from version import __version__

log = logging.getLogger(__name__)

REPO = "KK4ODA/emcomm-bbs"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
USER_AGENT = f"EmcommBBS/{__version__} (+https://github.com/{REPO})"
TIMEOUT = 15
APP_EXE_NAME = "Emcomm BBS.exe"

# Never overwritten or deleted by a source update.
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
    zip_url: str          # source zipball
    published: str        # ISO date
    assets: list = field(default_factory=list)   # [{'name', 'url', 'size'}]

    def asset(self, *needles):
        for a in self.assets:
            name = a.get("name") or ""
            if all(n.lower() in name.lower() for n in needles):
                return a
        return None

    @property
    def installer(self):
        return self.asset("-Setup-", ".exe")

    @property
    def portable_zip(self):
        return self.asset("windows-x64-portable", ".zip")

    @property
    def sums_url(self):
        a = self.asset("SHA256SUMS")
        return a["url"] if a else None


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
        assets=[{"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size")}
                for a in data.get("assets") or [] if a.get("browser_download_url")],
    )


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def _git_available():
    return shutil.which("git") is not None


def install_kind(app_dir):
    """'installed' | 'portable' (frozen builds), 'git' | 'zip' (source)."""
    if FROZEN:
        try:
            has_uninstaller = any(p.name.lower().startswith("unins") and p.suffix.lower() == ".exe"
                                  for p in EXE_DIR.iterdir())
        except OSError:
            has_uninstaller = False
        return "installed" if has_uninstaller else "portable"
    return "git" if (Path(app_dir) / ".git").is_dir() and _git_available() else "zip"


def install_update(info, app_dir, log_callback=None, install_requirements=True):
    """Install ``info``. Returns the method used: 'installer', 'portable',
    'git' or 'zip'.

    For 'installer' and 'portable' a helper batch file has been launched
    that waits for this process to exit, applies the update and restarts
    the app: the caller must exit promptly and must not relaunch itself.
    For the source modes the caller restarts the process.

    Raises UpdateError with a readable message on failure; the previous
    files remain in place (git) or are restored from the backup (zip).
    """
    say = log_callback or (lambda m: log.info(m))
    app_dir = Path(app_dir)
    kind = install_kind(app_dir)

    if kind == "installed":
        return _installer_update(info, say)
    if kind == "portable":
        return _portable_update(info, say)

    method = None
    if kind == "git":
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


# ---- frozen builds ---------------------------------------------------------

def _download(asset, dest_dir, say, sums_url=None):
    """Download a release asset, checking size and (when published) SHA-256."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / asset["name"]
    digest = hashlib.sha256()
    try:
        with requests.get(asset["url"], stream=True, timeout=60,
                          headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    digest.update(chunk)
    except (requests.RequestException, OSError) as exc:
        raise UpdateError(f"download of {asset['name']} failed ({exc.__class__.__name__})") from exc

    size = path.stat().st_size
    if asset.get("size") and size != int(asset["size"]):
        raise UpdateError(f"{asset['name']}: download size mismatch ({size:,} of {asset['size']:,} bytes)")
    if sums_url:
        try:
            sums = requests.get(sums_url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}).text
        except requests.RequestException:
            sums = ""
        expected = next((line.split()[0] for line in sums.splitlines()
                         if line.strip().endswith(asset["name"])), None)
        if expected and expected.lower() != digest.hexdigest().lower():
            path.unlink(missing_ok=True)
            raise UpdateError(f"{asset['name']}: SHA-256 checksum mismatch, download discarded")
        if expected:
            say(f"  Checksum verified for {asset['name']}")
    return path


def _helper_script(pid, body_lines, exe):
    """Batch helper: wait for this process to exit, do ``body_lines``, relaunch."""
    return "\r\n".join([
        "@echo off",
        "title Emcomm BBS update",
        "echo Waiting for Emcomm BBS to close...",
        ":wait",
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto wait)',
        *body_lines,
        f'start "" "{exe}"',
        '(goto) 2>nul & del "%~f0"',
        "",
    ])


def _launch_helper(script_path, script_text):
    with open(script_path, "w", encoding="ascii", errors="replace") as f:
        f.write(script_text)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd.exe", "/c", "start", "Emcomm BBS update", "/min", str(script_path)],  # noqa: S603,S607
                     creationflags=flags, close_fds=True)


def _installer_update(info, say):
    asset = info.installer
    if not asset:
        raise UpdateError(f"release {info.tag} has no Windows installer; download it from {RELEASES_PAGE}")
    updates = DATA_DIR / "updates"
    say(f"Downloading {asset['name']}…")
    path = _download(asset, updates, say, info.sums_url)
    say("Installer downloaded. It runs as soon as the app closes.")
    exe = Path(sys.executable)
    _launch_helper(updates / "apply_update.cmd", _helper_script(os.getpid(), [
        "echo Installing update...",
        f'"{path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /NOCANCEL',
        "if errorlevel 1 (echo Installer reported error %errorlevel%. & pause & exit /b 1)",
    ], exe))
    return "installer"


def _portable_update(info, say):
    asset = info.portable_zip
    if not asset:
        raise UpdateError(f"release {info.tag} has no portable zip; download it from {RELEASES_PAGE}")
    updates = DATA_DIR / "updates"
    say(f"Downloading {asset['name']}…")
    path = _download(asset, updates, say, info.sums_url)
    stage = updates / f"portable-{info.version}"
    shutil.rmtree(stage, ignore_errors=True)
    try:
        with zipfile.ZipFile(path) as z:
            z.extractall(stage)
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError(f"could not unpack {asset['name']}: {exc}") from exc
    # The zip may or may not wrap everything in one top-level folder.
    src = stage
    entries = [p for p in stage.iterdir()]
    if len(entries) == 1 and entries[0].is_dir() and not (stage / APP_EXE_NAME).exists():
        src = entries[0]
    if not (src / APP_EXE_NAME).exists():
        raise UpdateError("portable zip does not contain Emcomm BBS.exe")
    say("New files unpacked. They are copied in as soon as the app closes.")
    exe = Path(sys.executable)
    _launch_helper(updates / "apply_update.cmd", _helper_script(os.getpid(), [
        "echo Copying new files...",
        f'robocopy "{src}" "{EXE_DIR}" /E /NFL /NDL /NJH /NJS /R:5 /W:2 >nul',
        "if errorlevel 8 (echo Copy failed. & pause & exit /b 1)",
        f'rmdir /s /q "{stage}" 2>nul',
    ], exe))
    return "portable"


# ---- source checkouts ------------------------------------------------------

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
    """Launch a fresh copy of the app detached from this process (source modes)."""
    args = [sys.executable] if FROZEN else [sys.executable, str(script)]
    kwargs = {"cwd": str(Path(script).parent), "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)  # noqa: S603


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
