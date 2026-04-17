#!/bin/bash
# Install MZip GNOME integration files
# Run with: ./scripts/install-gnome-integration.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/src/zipextractor/data"
ICONS_DIR="$PROJECT_DIR/resources/icons"

# Determine installation prefix
if [ "$EUID" -eq 0 ]; then
    PREFIX="/usr"
    NAUTILUS_EXT_DIR="/usr/share/nautilus-python/extensions"
else
    PREFIX="$HOME/.local"
    NAUTILUS_EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
fi

echo "Installing MZip GNOME integration..."
echo "Installation prefix: $PREFIX"
echo ""

# Install desktop file
echo "Installing desktop file..."
mkdir -p "$PREFIX/share/applications"
cp "$DATA_DIR/applications/mzip.desktop" "$PREFIX/share/applications/"

# Install MIME types
echo "Installing MIME types..."
mkdir -p "$PREFIX/share/mime/packages"
cp "$DATA_DIR/mime/mzip-mime.xml" "$PREFIX/share/mime/packages/"

# Install metainfo
echo "Installing AppStream metainfo..."
mkdir -p "$PREFIX/share/metainfo"
cp "$DATA_DIR/metainfo/com.github.mzip.metainfo.xml" "$PREFIX/share/metainfo/"

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

# Install Nautilus extension
echo "Installing Nautilus extension..."
mkdir -p "$NAUTILUS_EXT_DIR"
cp "$DATA_DIR/nautilus/mzip-nautilus.py" "$NAUTILUS_EXT_DIR/"
chmod +x "$NAUTILUS_EXT_DIR/mzip-nautilus.py"

# Update caches
echo ""
echo "Updating system caches..."

# Update MIME database
if command -v update-mime-database &> /dev/null; then
    echo "Updating MIME database..."
    update-mime-database "$PREFIX/share/mime" 2>/dev/null || true
fi

# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    echo "Updating icon cache..."
    gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    echo "Updating desktop database..."
    update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
fi

echo ""
echo "Installation complete!"
echo ""
echo "To apply changes:"
echo "  - Log out and log back in, or"
echo "  - Restart Nautilus: nautilus -q && nautilus &"
echo ""
echo "To uninstall, run: ./scripts/uninstall-gnome-integration.sh"
