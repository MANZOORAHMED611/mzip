#!/bin/bash
# Install MZip - Modern Archive Manager
# Run with: ./scripts/install.sh
# For system-wide install, run with sudo: sudo ./scripts/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/src/zipextractor/data"
ICONS_DIR="$PROJECT_DIR/resources/icons"
DIST_DIR="$PROJECT_DIR/dist"

# Check if executable exists
if [ ! -f "$DIST_DIR/mzip" ]; then
    echo "Error: Executable not found at $DIST_DIR/mzip"
    echo "Please build first with: pyinstaller mzip.spec"
    exit 1
fi

# Determine installation prefix
if [ "$EUID" -eq 0 ]; then
    PREFIX="/usr/local"
    BIN_DIR="/usr/local/bin"
    NAUTILUS_EXT_DIR="/usr/share/nautilus-python/extensions"
    echo "Installing system-wide to $PREFIX"
else
    PREFIX="$HOME/.local"
    BIN_DIR="$HOME/.local/bin"
    NAUTILUS_EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
    echo "Installing for current user to $PREFIX"
fi

echo ""
echo "=== Installing MZip ==="
echo ""

# Create directories
mkdir -p "$BIN_DIR"
mkdir -p "$PREFIX/share/applications"
mkdir -p "$PREFIX/share/mime/packages"
mkdir -p "$PREFIX/share/metainfo"
mkdir -p "$NAUTILUS_EXT_DIR"

# Install executable
echo "Installing executable..."
cp "$DIST_DIR/mzip" "$BIN_DIR/mzip"
chmod +x "$BIN_DIR/mzip"

# Create mzip-gui symlink (GUI entry point)
ln -sf "$BIN_DIR/mzip" "$BIN_DIR/mzip-gui"

echo "  Installed: $BIN_DIR/mzip"

# Install desktop file
echo "Installing desktop file..."
cp "$DATA_DIR/applications/mzip.desktop" "$PREFIX/share/applications/"
# Update Exec paths in desktop file
sed -i "s|Exec=mzip-gui|Exec=$BIN_DIR/mzip|g" "$PREFIX/share/applications/mzip.desktop"
sed -i "s|Exec=mzip |Exec=$BIN_DIR/mzip |g" "$PREFIX/share/applications/mzip.desktop"
echo "  Installed: $PREFIX/share/applications/mzip.desktop"

# Install MIME types
echo "Installing MIME types..."
cp "$DATA_DIR/mime/mzip-mime.xml" "$PREFIX/share/mime/packages/"
echo "  Installed: $PREFIX/share/mime/packages/mzip-mime.xml"

# Install metainfo
echo "Installing AppStream metainfo..."
cp "$DATA_DIR/metainfo/com.github.mzip.metainfo.xml" "$PREFIX/share/metainfo/"
echo "  Installed: $PREFIX/share/metainfo/com.github.mzip.metainfo.xml"

# Install icons
echo "Installing icons..."
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    icon_src="$ICONS_DIR/hicolor/$size/apps/mzip.png"
    if [ -f "$icon_src" ]; then
        mkdir -p "$PREFIX/share/icons/hicolor/$size/apps"
        cp "$icon_src" "$PREFIX/share/icons/hicolor/$size/apps/"
        echo "  Installed $size icon"
    fi
done

# Install Nautilus extension for right-click menu
echo "Installing Nautilus extension (right-click menu)..."
mkdir -p "$NAUTILUS_EXT_DIR"

# Create Nautilus extension with correct paths
cat > "$NAUTILUS_EXT_DIR/mzip-nautilus.py" << 'NAUTILUS_EOF'
#!/usr/bin/env python3
"""Nautilus extension for MZip archive manager.

This extension adds context menu items for archive operations in
GNOME Files (Nautilus).

Copyright 2026 Green Olive Tech
Licensed under GPL-3.0-or-later
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from gi.repository import GObject, Nautilus

if TYPE_CHECKING:
    from collections.abc import Sequence

# Get mzip path from environment or use default
MZIP_PATH = os.environ.get("MZIP_PATH", "mzip")

# Archive extensions that MZip can handle
ARCHIVE_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz",
    ".tar.bz2", ".tbz2", ".tbz", ".tar.xz", ".txz",
    ".gz", ".bz2", ".xz",
}


def get_file_path(file_info: Nautilus.FileInfo) -> Path | None:
    """Extract file path from Nautilus FileInfo."""
    uri = file_info.get_uri()
    if not uri:
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def is_archive(file_info: Nautilus.FileInfo) -> bool:
    """Check if file is a supported archive."""
    path = get_file_path(file_info)
    if not path:
        return False
    name_lower = path.name.lower()
    return any(name_lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def is_directory(file_info: Nautilus.FileInfo) -> bool:
    """Check if file info represents a directory."""
    return bool(file_info.is_directory())


class MZipMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    """Nautilus menu provider for MZip operations."""

    def __init__(self) -> None:
        super().__init__()

    def get_file_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for selected files."""
        if not files:
            return []

        items: list[Nautilus.MenuItem] = []
        all_archives = all(is_archive(f) for f in files)
        has_files = any(not is_directory(f) or is_directory(f) for f in files)

        if all_archives:
            items.extend(self._get_archive_menu_items(files))
        elif has_files:
            items.extend(self._get_compression_menu_items(files))

        return items

    def _get_archive_menu_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for archive files."""
        items: list[Nautilus.MenuItem] = []

        # Extract Here
        extract_here = Nautilus.MenuItem(
            name="MZip::ExtractHere",
            label="Extract Here",
            tip="Extract archive contents to current directory",
            icon="extract-archive",
        )
        extract_here.connect("activate", self._on_extract_here, files)
        items.append(extract_here)

        # Extract To...
        extract_to = Nautilus.MenuItem(
            name="MZip::ExtractTo",
            label="Extract To...",
            tip="Extract archive contents to a chosen directory",
            icon="extract-archive",
        )
        extract_to.connect("activate", self._on_extract_to, files)
        items.append(extract_to)

        # Open with MZip
        open_mzip = Nautilus.MenuItem(
            name="MZip::Open",
            label="Open with MZip",
            tip="Open archive in MZip for browsing",
            icon="mzip",
        )
        open_mzip.connect("activate", self._on_open_mzip, files)
        items.append(open_mzip)

        return items

    def _get_compression_menu_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for compressing files."""
        items: list[Nautilus.MenuItem] = []

        # Compress to ZIP
        compress_zip = Nautilus.MenuItem(
            name="MZip::CompressZip",
            label="Compress to ZIP...",
            tip="Create a ZIP archive from selected files",
            icon="package-x-generic",
        )
        compress_zip.connect("activate", self._on_compress, files, "zip")
        items.append(compress_zip)

        return items

    def _on_extract_here(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Extract Here' action."""
        for file_info in files:
            path = get_file_path(file_info)
            if path:
                subprocess.Popen(
                    [MZIP_PATH, str(path)],
                    start_new_session=True,
                )

    def _on_extract_to(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Extract To...' action."""
        paths = [str(get_file_path(f)) for f in files if get_file_path(f)]
        if paths:
            subprocess.Popen(
                [MZIP_PATH, *paths],
                start_new_session=True,
            )

    def _on_open_mzip(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Open with MZip' action."""
        paths = [str(get_file_path(f)) for f in files if get_file_path(f)]
        if paths:
            subprocess.Popen(
                [MZIP_PATH, *paths],
                start_new_session=True,
            )

    def _on_compress(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
        format_ext: str,
    ) -> None:
        """Handle compress action."""
        paths = [str(get_file_path(f)) for f in files if get_file_path(f)]
        if paths:
            subprocess.Popen(
                [MZIP_PATH, *paths],
                start_new_session=True,
            )


def get_extension_types() -> list[type]:
    """Return extension types provided by this module."""
    return [MZipMenuProvider]
NAUTILUS_EOF

chmod +x "$NAUTILUS_EXT_DIR/mzip-nautilus.py"
echo "  Installed: $NAUTILUS_EXT_DIR/mzip-nautilus.py"

# Update caches
echo ""
echo "Updating system caches..."

# Update MIME database
if command -v update-mime-database &> /dev/null; then
    echo "  Updating MIME database..."
    update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
fi

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    echo "  Updating icon cache..."
    gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    echo "  Updating desktop database..."
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
fi

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "MZip has been installed with the following features:"
echo "  - Binary executable: $BIN_DIR/mzip"
echo "  - Desktop application entry (shows in app menu)"
echo "  - MIME type associations (double-click archives to open)"
echo "  - Right-click context menu in Nautilus (Extract Here, Open with MZip)"
echo ""
echo "To apply all changes:"
echo "  1. Log out and log back in, OR"
echo "  2. Restart Nautilus: nautilus -q && nautilus &"
echo ""
if [ "$EUID" -ne 0 ]; then
    echo "NOTE: Make sure $BIN_DIR is in your PATH."
    echo "Add this to your ~/.bashrc if needed:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo ""
echo "To uninstall, run: ./scripts/uninstall.sh"
