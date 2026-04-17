#!/bin/bash
# Uninstall MZip GNOME integration files
# Run with: ./scripts/uninstall-gnome-integration.sh

set -e

# Determine installation prefix
if [ "$EUID" -eq 0 ]; then
    PREFIX="/usr"
    NAUTILUS_EXT_DIR="/usr/share/nautilus-python/extensions"
else
    PREFIX="$HOME/.local"
    NAUTILUS_EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
fi

echo "Uninstalling MZip GNOME integration..."
echo "Installation prefix: $PREFIX"
echo ""

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

# Update MIME database
if command -v update-mime-database &> /dev/null; then
    update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
fi

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
fi

echo ""
echo "Uninstallation complete!"
echo ""
echo "Restart Nautilus to apply changes: nautilus -q && nautilus &"
