# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for MZip.

This creates a standalone executable for the MZip archive manager.
"""

import os
import sys
from pathlib import Path

# Get the project root
PROJECT_ROOT = Path(SPECPATH)
SRC_DIR = PROJECT_ROOT / "src"

block_cipher = None

# Collect data files
datas = [
    # CSS styles
    (str(SRC_DIR / "zipextractor" / "data" / "style.css"), "zipextractor/data"),
    # Icons (if they exist in the package)
    (str(PROJECT_ROOT / "resources" / "icons"), "share/icons"),
]

# Add desktop file and mime types for Linux integration
linux_data = [
    (str(SRC_DIR / "zipextractor" / "data" / "applications"), "share/applications"),
    (str(SRC_DIR / "zipextractor" / "data" / "mime"), "share/mime/packages"),
    (str(SRC_DIR / "zipextractor" / "data" / "metainfo"), "share/metainfo"),
]

# Only add if they exist
for src, dst in linux_data:
    if os.path.exists(src):
        datas.append((src, dst))

# Hidden imports for GTK4 and GObject introspection
hiddenimports = [
    "gi",
    "gi.repository.Gtk",
    "gi.repository.Gdk",
    "gi.repository.GdkPixbuf",
    "gi.repository.Gio",
    "gi.repository.GLib",
    "gi.repository.GObject",
    "gi.repository.Pango",
    "gi.repository.Adw",
    "cairo",
    "zipfile",
    "tarfile",
    "gzip",
    "bz2",
    "lzma",
    "hashlib",
    "threading",
    "concurrent.futures",
    "click",
    "rich",
    "rich.console",
    "rich.table",
    "rich.progress",
    "rich.panel",
]

# Analysis
a = Analysis(
    [str(SRC_DIR / "zipextractor" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "wx",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="mzip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "resources" / "icons" / "hicolor" / "256x256" / "apps" / "mzip.png"),
)
