#!/bin/bash
# Build a standalone Type 2 AppImage for ReadComics.
# Usage: bash build-appimage.sh
#
# Requirements: appimagetool, zsyncmake, curl, python3 (with Pillow for icon)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="ReadComics"
APP_VERSION="$(cat "$SCRIPT_DIR/VERSION")"
ARCH="x86_64"
BUILD_DIR="$SCRIPT_DIR/appimage-build"
APPDIR="$BUILD_DIR/${APP_NAME}.AppDir"
CACHE_DIR="$BUILD_DIR/cache"
OUTPUT_NAME="${APP_NAME}-${ARCH}.AppImage"
OUTPUT="$SCRIPT_DIR/$OUTPUT_NAME"

PYTHON_PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260510/cpython-3.12.13%2B20260510-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PYTHON_PBS_ARCHIVE="cpython-3.12.13-linux-x86_64-stripped.tar.gz"

echo "============================================"
echo " ReadComics v${APP_VERSION} AppImage Build"
echo "============================================"

# ── Step 1: Create directory structure ───────────────────────────────────────
echo
echo "--> Creating AppDir structure..."
mkdir -p "$CACHE_DIR"
mkdir -p "$APPDIR/opt/readcomics/src"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR/usr/share/metainfo"

# ── Step 2: Bundle Python 3.12 (python-build-standalone, stripped) ───────────
if [ ! -f "$CACHE_DIR/$PYTHON_PBS_ARCHIVE" ]; then
    echo "--> Downloading Python 3.12 standalone (stripped)..."
    curl -L --progress-bar -o "$CACHE_DIR/$PYTHON_PBS_ARCHIVE" "$PYTHON_PBS_URL"
else
    echo "--> Using cached Python 3.12 archive."
fi
echo "--> Extracting Python..."
tar -xzf "$CACHE_DIR/$PYTHON_PBS_ARCHIVE" -C "$APPDIR/opt/readcomics/"
PYTHON="$APPDIR/opt/readcomics/python/bin/python3.12"

# ── Step 3: Install pip packages ─────────────────────────────────────────────
echo "--> Upgrading pip..."
"$PYTHON" -m pip install --upgrade pip --quiet

echo "--> Installing runtime packages (this takes a few minutes)..."
"$PYTHON" -m pip install \
    httpx \
    playwright \
    rich \
    Pillow \
    PySide6 \
    --quiet

# ── Step 4: Install Playwright Firefox browser ────────────────────────────────
PW_BROWSERS="$APPDIR/opt/readcomics/pw-browsers"
echo "--> Installing Playwright Firefox into AppDir..."
PLAYWRIGHT_BROWSERS_PATH="$PW_BROWSERS" "$PYTHON" -m playwright install firefox

# ── Step 5: Copy application source files ────────────────────────────────────
echo "--> Copying source files..."
cp "$SCRIPT_DIR/gui.py"          "$APPDIR/opt/readcomics/"
cp "$SCRIPT_DIR/main.py"         "$APPDIR/opt/readcomics/"
cp "$SCRIPT_DIR/requirements.txt" "$APPDIR/opt/readcomics/"
cp "$SCRIPT_DIR/VERSION"          "$APPDIR/opt/readcomics/"
cp -r "$SCRIPT_DIR/src"           "$APPDIR/opt/readcomics/"

# ── Step 6: Generate icon ─────────────────────────────────────────────────────
echo "--> Generating application icon..."
"$PYTHON" - << 'PYICON'
import math
from PIL import Image, ImageDraw

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Catppuccin Mocha palette
BG    = "#1e1e2e"
BLUE  = "#89b4fa"
TEAL  = "#74c7ec"
TEXT  = "#cdd6f4"
GOLD  = "#f9e2af"
RING  = "#b4befe"

# Outer ring
d.ellipse([4, 4, 252, 252], fill=BG)
d.ellipse([4, 4, 252, 252], outline=RING, width=7)

# Book body
d.rounded_rectangle([48, 52, 208, 192], radius=8, fill=BLUE, outline=RING, width=2)
# Spine
d.rounded_rectangle([48, 52, 82, 192], radius=8, fill=TEAL)
d.line([(82, 52), (82, 192)], fill=RING, width=2)

# Page lines
for y in [85, 104, 123, 142, 161]:
    d.line([(94, y), (196, y)], fill=BG, width=3)

# Gold star / sparkle below book
cx, cy, ro, ri = 128, 220, 18, 9
pts = []
for i in range(10):
    angle = math.radians(i * 36 - 90)
    r = ro if i % 2 == 0 else ri
    pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
d.polygon(pts, fill=GOLD, outline=GOLD)

img.save("/tmp/readcomics-icon.png", "PNG")
print("    Icon saved: /tmp/readcomics-icon.png")
PYICON

cp /tmp/readcomics-icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/readcomics.png"
cp /tmp/readcomics-icon.png "$APPDIR/readcomics.png"

# ── Step 7: Create .desktop file ─────────────────────────────────────────────
echo "--> Creating .desktop file..."
cat > "$APPDIR/readcomics.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=ReadComics
GenericName=Comic Downloader
Comment=Browse and download comics from rcostation.xyz
Exec=readcomics
Icon=readcomics
Categories=Network;Graphics;
Terminal=false
StartupWMClass=readcomics
Keywords=comic;comics;manga;download;
DESKTOP

# ── Step 8: Create AppRun launcher ───────────────────────────────────────────
echo "--> Creating AppRun launcher..."
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
# AppRun — entry point for the ReadComics AppImage.
HERE="$(dirname "$(readlink -f "${0}")")"
PYTHON="$HERE/opt/readcomics/python/bin/python3.12"
SITE="$HERE/opt/readcomics/python/lib/python3.12/site-packages"

# Tell Playwright where the bundled Firefox lives.
export PLAYWRIGHT_BROWSERS_PATH="$HERE/opt/readcomics/pw-browsers"

# Isolate the bundled Python so it does not pick up host site-packages.
export PYTHONHOME="$HERE/opt/readcomics/python"
export PYTHONPATH="$HERE/opt/readcomics"

# Qt / PySide6 — prefer bundled Qt libs and platform plugins.
export QT_QPA_PLATFORM_PLUGIN_PATH="$SITE/PySide6/Qt/plugins/platforms"
export LD_LIBRARY_PATH="$SITE/PySide6/Qt/lib:$HERE/opt/readcomics/python/lib:${LD_LIBRARY_PATH:-}"

# Pass AppDir path so app code can locate bundled assets if needed.
export APPDIR="$HERE"

exec "$PYTHON" "$HERE/opt/readcomics/gui.py" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# ── Step 9: Package into AppImage (Type 2) ────────────────────────────────────
echo "--> Running appimagetool..."
cd "$SCRIPT_DIR"
ARCH="$ARCH" appimagetool \
    --updateinformation \
    "gh-releases-zsync|Tamalero|readcomics-cli|latest|${OUTPUT_NAME}.zsync" \
    "$APPDIR" \
    "$OUTPUT"

chmod +x "$OUTPUT"

# ── Step 10: Generate zsync metadata for delta updates ───────────────────────
# appimagetool auto-generates zsync when zsyncmake is present; if not, run manually.
if [ ! -f "${OUTPUT}.zsync" ]; then
    echo "--> Generating zsync metadata..."
    zsyncmake "$OUTPUT" -o "${OUTPUT}.zsync" -u "$OUTPUT_NAME"
fi

echo
echo "============================================"
printf " AppImage : %s\n" "$OUTPUT"
printf " zsync    : %s.zsync\n" "$OUTPUT"
printf " Size     : %s\n" "$(du -sh "$OUTPUT" | cut -f1)"
echo "============================================"
echo " Done!"
