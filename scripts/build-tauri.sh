#!/bin/bash
#
# Build script for Handsi Tauri app
#
# Creates a production-ready Tauri app bundle with Python backend.
#

set -e

echo "============================"
echo "Handsi Tauri - Build Script"
echo "============================"

# Check if conda environment is active
if [[ -z "${CONDA_DEFAULT_ENV}" ]]; then
    echo "Error: Conda environment not active"
    echo "Please run: conda activate handsi"
    exit 1
fi

# Check if in handsi environment
if [[ "${CONDA_DEFAULT_ENV}" != "handsi" ]]; then
    echo "Warning: Not in 'handsi' conda environment"
    echo "Current environment: ${CONDA_DEFAULT_ENV}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found"
    echo "Please install Node.js: brew install node"
    exit 1
fi

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "Error: Rust/Cargo not found"
    echo "Please install Rust: curl --proto '=https' --tlsf1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo ""
echo "Step 1: Installing/updating npm dependencies..."
npm install

echo ""
echo "Step 2: Building Python backend (PyInstaller)..."

# Detect macOS architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    TARGET_TRIPLE="aarch64-apple-darwin"
    echo "Detected architecture: Apple Silicon (M-series)"
else
    TARGET_TRIPLE="x86_64-apple-darwin"
    echo "Detected architecture: Intel"
fi

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: PyInstaller not found"
    echo "Please install: pip install pyinstaller"
    exit 1
fi

# Build Python backend binary
echo "Building handsi-backend-${TARGET_TRIPLE}..."
pyinstaller src-tauri/bundle/handsi-backend.spec \
    --distpath src-tauri/bin \
    --workpath build/pyinstaller \
    --clean

# Verify binary was created
BINARY_PATH="src-tauri/bin/handsi-backend-${TARGET_TRIPLE}"
if [ ! -f "$BINARY_PATH" ]; then
    echo "Error: Binary not created at $BINARY_PATH"
    exit 1
fi

BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
echo "✓ Python backend built successfully ($BINARY_SIZE)"

echo ""
echo "Step 3: Building Tauri app..."
npm run build

echo ""
echo "Step 4: Creating DMG..."
APP_PATH="src-tauri/target/release/bundle/macos/Handsi.app"
DMG_PATH="src-tauri/target/release/bundle/macos/Handsi_0.1.0_aarch64.dmg"

if [ -f "$APP_PATH/Contents/MacOS/Handsi" ]; then
    # Remove old DMG if exists
    rm -f "$DMG_PATH"

    # Create a simple DMG without fancy UI (no Finder permissions needed)
    echo "Creating DMG from .app bundle..."
    hdiutil create -volname "Handsi" \
        -srcfolder "$APP_PATH" \
        -ov -format UDZO \
        "$DMG_PATH"

    DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
    echo "✓ DMG created successfully ($DMG_SIZE)"
else
    echo "Warning: .app bundle not found at $APP_PATH"
fi

echo ""
echo "============================"
echo "Build complete!"
echo "============================"
echo ""
echo "Output:"
echo "  .app: $APP_PATH"
if [ -f "$DMG_PATH" ]; then
    echo "  DMG:  $DMG_PATH"
fi
echo ""
echo "To run: open \"$APP_PATH\""
echo ""
