"""Print the CHANGELOG section for one version (used by RELEASE.bat as the
GitHub release notes).  Usage:  python packaging/release_notes.py 1.7.0"""
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def section(version):
    text = CHANGELOG.read_text(encoding="utf-8")
    m = re.search(rf"## \[{re.escape(version)}\][^\n]*\n(.*?)(?=\n## \[|\Z)", text, re.S)
    if not m:
        return None
    body = re.sub(r"^### ", "## ", m.group(1).strip(), flags=re.M)
    body += ("\n\n**Windows:** download `Emcomm-BBS-Setup-" + version + ".exe` and run it (per-user, no admin "
             "needed), or unzip the portable zip anywhere. Running copies offer this update themselves. "
             "`SHA256SUMS.txt` lists the checksums. **Source:** unzip and double-click `RUN.bat`.\n")
    return body


if __name__ == "__main__":
    ver = sys.argv[1] if len(sys.argv) > 1 else ""
    out = section(ver)
    if out is None:
        print(f"no CHANGELOG section for {ver!r}", file=sys.stderr)
        sys.exit(1)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(out)
