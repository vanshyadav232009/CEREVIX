# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PROJECT_DIR = Path.cwd()

# Collect all application assets.
datas = []

for folder in ["assets", "third_party/LibreHardwareMonitor"]:
    source = PROJECT_DIR / folder

    for file in source.rglob("*"):
        if file.is_file():
            destination = file.parent.relative_to(PROJECT_DIR)
            datas.append((str(file), str(destination)))

# Include the separately compiled elevated helper.
helper_exe = PROJECT_DIR / "dist" / "LHMHelper.exe"

if not helper_exe.is_file():
    raise FileNotFoundError(f"LHMHelper.exe not found: {helper_exe}")

datas.append((str(helper_exe), "."))


a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CEREVIX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(PROJECT_DIR / "assets" / "cerevix_icon.ico"),
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CEREVIX",
)