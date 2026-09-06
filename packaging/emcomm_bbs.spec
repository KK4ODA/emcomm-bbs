# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Emcomm BBS.

    pyinstaller packaging/emcomm_bbs.spec   -> one-folder build in dist/Emcomm BBS/

The folder is what the Windows installer (packaging/emcomm_bbs.iss) and the
portable zip ship. Bundled read-only files land in _internal/ and are found
through app_config.RESOURCE_DIR; operator data goes to %LOCALAPPDATA%.
"""
import os

root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(root, "welfare_checkin_template.txt"), "."),
    (os.path.join(root, "emcomm_bbs_config.example.json"), "."),
    (os.path.join(root, "settings.json"), "."),
    (os.path.join(root, "examples"), "examples"),
    (os.path.join(root, "docs", "Emcomm_BBS_User_Guide.txt"), "docs"),
    (os.path.join(root, "packaging", "emcomm_bbs.ico"), "packaging"),
]

hidden = [
    "watchdog.observers.read_directory_changes",   # Windows observer is imported dynamically
    "watchdog.observers.polling",
]

a = Analysis(
    [os.path.join(root, "emcomm_bbs.py")],
    pathex=[root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "unittest", "PyInstaller", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Emcomm BBS",
    icon=os.path.join(root, "packaging", "emcomm_bbs.ico"),
    debug=False, strip=False, upx=False,
    console=False,                      # GUI app: no console window
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Emcomm BBS")
