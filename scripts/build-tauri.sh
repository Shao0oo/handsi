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
# TODO: Create PyInstaller spec for Python-only backend (no Qt!)
# This will be much smaller than the old bundle
# For now, we'll use the system Python in development mode

echo ""
echo "Step 3: Building Tauri app..."
npm run build

echo ""
echo "============================"
echo "Build complete!"
echo "============================"
echo ""
echo "Output:"
echo "  macOS: dist/Handsi.app"
echo "  DMG:   dist/Handsi.dmg"
echo ""
echo "To run: open dist/Handsi.app"
echo ""
