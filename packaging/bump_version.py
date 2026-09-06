"""Set __version__ in version.py.  Used by RELEASE.bat; a script file so the
regex does not depend on cmd/PowerShell quoting.   python packaging/bump_version.py 1.7.0"""
import re
import sys
from pathlib import Path

VERSION_PY = Path(__file__).resolve().parents[1] / "version.py"


def main(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        print(f"bad version {version!r}: expected X.Y.Z")
        return 1
    text = VERSION_PY.read_text(encoding="utf-8")
    new, n = re.subn(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', text, count=1)
    if n != 1:
        print("version line not found in version.py")
        return 1
    VERSION_PY.write_text(new, encoding="utf-8")
    print(f"version.py -> {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
