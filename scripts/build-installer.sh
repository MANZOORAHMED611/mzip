#!/bin/bash
# Build MZip Installer Package
# Creates a self-extracting installer that includes the executable and all integration files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build/installer"
DATA_DIR="$PROJECT_DIR/src/zipextractor/data"
ICONS_DIR="$PROJECT_DIR/resources/icons"

# Get version from the app
VERSION="1.0.0"

echo "=== Building MZip Installer v$VERSION ==="
echo ""

# Check if executable exists
if [ ! -f "$DIST_DIR/mzip" ]; then
    echo "Error: Executable not found at $DIST_DIR/mzip"
    echo "Please build first with: pyinstaller mzip.spec"
    exit 1
fi

# Clean and create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/mzip-$VERSION"

PACKAGE_DIR="$BUILD_DIR/mzip-$VERSION"

echo "Copying files..."

# Copy executable
mkdir -p "$PACKAGE_DIR/bin"
cp "$DIST_DIR/mzip" "$PACKAGE_DIR/bin/"
chmod +x "$PACKAGE_DIR/bin/mzip"
echo "  - Executable"

# Copy desktop file
mkdir -p "$PACKAGE_DIR/share/applications"
cp "$DATA_DIR/applications/mzip.desktop" "$PACKAGE_DIR/share/applications/"
echo "  - Desktop file"

# Copy MIME types
mkdir -p "$PACKAGE_DIR/share/mime/packages"
cp "$DATA_DIR/mime/mzip-mime.xml" "$PACKAGE_DIR/share/mime/packages/"
echo "  - MIME types"

# Copy metainfo
mkdir -p "$PACKAGE_DIR/share/metainfo"
cp "$DATA_DIR/metainfo/com.github.mzip.metainfo.xml" "$PACKAGE_DIR/share/metainfo/"
echo "  - AppStream metainfo"

# Copy icons
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    icon_src="$ICONS_DIR/hicolor/$size/apps/mzip.png"
    if [ -f "$icon_src" ]; then
        mkdir -p "$PACKAGE_DIR/share/icons/hicolor/$size/apps"
        cp "$icon_src" "$PACKAGE_DIR/share/icons/hicolor/$size/apps/"
    fi
done
echo "  - Icons"

# Create Nautilus extension
mkdir -p "$PACKAGE_DIR/share/nautilus-python/extensions"
cat > "$PACKAGE_DIR/share/nautilus-python/extensions/mzip-nautilus.py" << 'NAUTILUS_EOF'
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
echo "  - Nautilus extension"

# Create the installer script
cat > "$PACKAGE_DIR/install.sh" << 'INSTALL_EOF'
#!/bin/bash
# MZip Installer Script
# Installs MZip and all integrations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
cp "$SCRIPT_DIR/bin/mzip" "$BIN_DIR/mzip"
chmod +x "$BIN_DIR/mzip"
ln -sf "$BIN_DIR/mzip" "$BIN_DIR/mzip-gui"
echo "  Installed: $BIN_DIR/mzip"

# Install desktop file
echo "Installing desktop file..."
cp "$SCRIPT_DIR/share/applications/mzip.desktop" "$PREFIX/share/applications/"
# Update Exec paths in desktop file
sed -i "s|Exec=mzip-gui|Exec=$BIN_DIR/mzip|g" "$PREFIX/share/applications/mzip.desktop"
sed -i "s|Exec=mzip |Exec=$BIN_DIR/mzip |g" "$PREFIX/share/applications/mzip.desktop"
echo "  Installed: $PREFIX/share/applications/mzip.desktop"

# Install MIME types
echo "Installing MIME types..."
cp "$SCRIPT_DIR/share/mime/packages/mzip-mime.xml" "$PREFIX/share/mime/packages/"
echo "  Installed: $PREFIX/share/mime/packages/mzip-mime.xml"

# Install metainfo
echo "Installing AppStream metainfo..."
cp "$SCRIPT_DIR/share/metainfo/com.github.mzip.metainfo.xml" "$PREFIX/share/metainfo/"
echo "  Installed: $PREFIX/share/metainfo/com.github.mzip.metainfo.xml"

# Install icons
echo "Installing icons..."
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    icon_src="$SCRIPT_DIR/share/icons/hicolor/$size/apps/mzip.png"
    if [ -f "$icon_src" ]; then
        mkdir -p "$PREFIX/share/icons/hicolor/$size/apps"
        cp "$icon_src" "$PREFIX/share/icons/hicolor/$size/apps/"
        echo "  Installed $size icon"
    fi
done

# Install Nautilus extension
echo "Installing Nautilus extension..."
cp "$SCRIPT_DIR/share/nautilus-python/extensions/mzip-nautilus.py" "$NAUTILUS_EXT_DIR/"
chmod +x "$NAUTILUS_EXT_DIR/mzip-nautilus.py"
echo "  Installed: $NAUTILUS_EXT_DIR/mzip-nautilus.py"

# Update caches
echo ""
echo "Updating system caches..."

if command -v update-mime-database &> /dev/null; then
    echo "  Updating MIME database..."
    update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache &> /dev/null; then
    echo "  Updating icon cache..."
    gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database &> /dev/null; then
    echo "  Updating desktop database..."
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
fi

# Set MZip as default handler for archives
echo "  Setting MZip as default archive handler..."
xdg-mime default mzip.desktop application/zip application/x-zip application/x-zip-compressed \
    application/x-7z-compressed application/x-rar-compressed application/x-tar \
    application/x-compressed-tar application/x-bzip-compressed-tar application/x-xz-compressed-tar \
    application/gzip application/x-gzip application/x-bzip application/x-bzip2 application/x-xz 2>/dev/null || true

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "MZip has been installed with the following features:"
echo "  - Binary executable: $BIN_DIR/mzip"
echo "  - Desktop application entry (shows in app menu)"
echo "  - MIME type associations (double-click archives to open)"
echo "  - Right-click context menu in Nautilus"
echo ""
echo "To apply all changes:"
echo "  1. Log out and log back in, OR"
echo "  2. Restart Nautilus: nautilus -q && nautilus &"
echo ""
if [ "$EUID" -ne 0 ]; then
    echo "NOTE: Make sure $BIN_DIR is in your PATH."
    echo "Add this to your ~/.bashrc if needed:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi
INSTALL_EOF
chmod +x "$PACKAGE_DIR/install.sh"

# Create uninstall script
cat > "$PACKAGE_DIR/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
# MZip Uninstaller
# Removes MZip and all integrations

set -e

# Determine installation prefix
if [ "$EUID" -eq 0 ]; then
    PREFIX="/usr/local"
    BIN_DIR="/usr/local/bin"
    NAUTILUS_EXT_DIR="/usr/share/nautilus-python/extensions"
else
    PREFIX="$HOME/.local"
    BIN_DIR="$HOME/.local/bin"
    NAUTILUS_EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
fi

echo "Uninstalling MZip from $PREFIX..."
echo ""

# Remove files
echo "Removing executable..."
rm -f "$BIN_DIR/mzip"
rm -f "$BIN_DIR/mzip-gui"

echo "Removing desktop file..."
rm -f "$PREFIX/share/applications/mzip.desktop"

echo "Removing MIME types..."
rm -f "$PREFIX/share/mime/packages/mzip-mime.xml"

echo "Removing AppStream metainfo..."
rm -f "$PREFIX/share/metainfo/com.github.mzip.metainfo.xml"

echo "Removing icons..."
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    rm -f "$PREFIX/share/icons/hicolor/$size/apps/mzip.png"
done

echo "Removing Nautilus extension..."
rm -f "$NAUTILUS_EXT_DIR/mzip-nautilus.py"

# Update caches
echo ""
echo "Updating system caches..."
update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true

echo ""
echo "Uninstallation complete!"
echo "Restart Nautilus to apply changes: nautilus -q && nautilus &"
UNINSTALL_EOF
chmod +x "$PACKAGE_DIR/uninstall.sh"

# Create README
cat > "$PACKAGE_DIR/README.txt" << 'README_EOF'
MZip - Modern Archive Manager for Linux
========================================

Copyright 2026 Green Olive Tech
Licensed under GPL-3.0-or-later

INSTALLATION
------------

For current user only (recommended):
    ./install.sh

For system-wide installation:
    sudo ./install.sh

UNINSTALLATION
--------------

For current user:
    ./uninstall.sh

For system-wide:
    sudo ./uninstall.sh

FEATURES
--------

- Extract ZIP, 7z, RAR, TAR, GZ, BZ2, XZ archives
- Create ZIP and TAR archives
- Modern GTK4/libadwaita interface
- Right-click context menu in Nautilus
- File associations for all archive types
- Batch extraction support

For more information, visit:
https://github.com/MANZOORAHMED611/mzip
README_EOF

echo ""
echo "Creating installer package..."

# Create the tarball
cd "$BUILD_DIR"
tar -czf "mzip-$VERSION-linux-x86_64.tar.gz" "mzip-$VERSION"

# Create self-extracting installer
INSTALLER="$DIST_DIR/mzip-$VERSION-linux-x86_64-installer.sh"

cat > "$INSTALLER" << 'HEADER_EOF'
#!/bin/bash
# MZip Self-Extracting Installer
# Copyright 2026 Green Olive Tech
# Licensed under GPL-3.0-or-later

set -e

echo ""
echo "  __  __ ______(_)        "
echo " |  \/  |___  / _ _ __    "
echo " | |\/| |  / / | | '_ \   "
echo " | |  | | / /| | | |_) |  "
echo " |_|  |_/___|_|_| .__/   "
echo "                | |       "
echo "  Archive Manager |_| v1.0.0"
echo ""
echo "  by Green Olive Tech"
echo ""

# Create temp directory
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "Extracting files..."

# Find the line where the archive starts
ARCHIVE_START=$(awk '/^__ARCHIVE_START__$/{print NR + 1; exit 0; }' "$0")

# Extract the archive
tail -n +$ARCHIVE_START "$0" | tar -xzf - -C "$TMPDIR"

# Find the extracted directory
EXTRACT_DIR=$(find "$TMPDIR" -maxdepth 1 -type d -name "mzip-*" | head -1)

if [ -z "$EXTRACT_DIR" ]; then
    echo "Error: Could not find extracted files"
    exit 1
fi

# Run the installer
cd "$EXTRACT_DIR"
./install.sh

exit 0

__ARCHIVE_START__
HEADER_EOF

# Append the tarball
cat "$BUILD_DIR/mzip-$VERSION-linux-x86_64.tar.gz" >> "$INSTALLER"
chmod +x "$INSTALLER"

# Also copy the tarball to dist
cp "$BUILD_DIR/mzip-$VERSION-linux-x86_64.tar.gz" "$DIST_DIR/"

# Calculate sizes
INSTALLER_SIZE=$(du -h "$INSTALLER" | cut -f1)
TARBALL_SIZE=$(du -h "$DIST_DIR/mzip-$VERSION-linux-x86_64.tar.gz" | cut -f1)

echo ""
echo "=== Build Complete! ==="
echo ""
echo "Created installer packages in $DIST_DIR:"
echo ""
echo "  1. Self-extracting installer (recommended):"
echo "     $INSTALLER"
echo "     Size: $INSTALLER_SIZE"
echo "     Usage: ./mzip-$VERSION-linux-x86_64-installer.sh"
echo ""
echo "  2. Tarball archive:"
echo "     $DIST_DIR/mzip-$VERSION-linux-x86_64.tar.gz"
echo "     Size: $TARBALL_SIZE"
echo "     Usage: tar -xzf mzip-$VERSION-linux-x86_64.tar.gz && cd mzip-$VERSION && ./install.sh"
echo ""
