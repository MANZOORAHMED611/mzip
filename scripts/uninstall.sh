#!/bin/bash
# Uninstall MZip
# Run with: ./scripts/uninstall.sh
# For system-wide uninstall, run with sudo: sudo ./scripts/uninstall.sh

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

# Remove executable
echo "Removing executable..."
rm -f "$BIN_DIR/mzip"
rm -f "$BIN_DIR/mzip-gui"

# Remove desktop file
echo "Removing desktop file..."
rm -f "$PREFIX/share/applications/mzip.desktop"

# Remove MIME types
echo "Removing MIME types..."
rm -f "$PREFIX/share/mime/packages/mzip-mime.xml"

# Remove metainfo
echo "Removing AppStream metainfo..."
rm -f "$PREFIX/share/metainfo/com.github.mzip.metainfo.xml"

# Remove icons
echo "Removing icons..."
for size in 16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512; do
    rm -f "$PREFIX/share/icons/hicolor/$size/apps/mzip.png"
done

# Remove Nautilus extension
echo "Removing Nautilus extension..."
rm -f "$NAUTILUS_EXT_DIR/mzip-nautilus.py"

# Update caches
echo ""
echo "Updating system caches..."

if command -v update-mime-database &> /dev/null; then
    update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
fi

if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
fi

echo ""
echo "Uninstallation complete!"
echo ""
echo "Restart Nautilus to apply changes: nautilus -q && nautilus &"
