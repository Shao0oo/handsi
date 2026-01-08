#!/bin/bash
#
# Development script for Handsi Tauri app
#
# Runs Tauri in development mode with hot reload.
# Python backend runs from conda environment.
#

set -e

echo "================================"
echo "Handsi Tauri - Development Mode"
echo "================================"

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

# Check if Rust/Cargo is installed
if ! command -v cargo &> /dev/null; then
    echo ""
    echo "Error: Rust/Cargo not found"
    echo ""
    echo "Tauri requires Rust to compile the native app."
    echo ""
    echo "To install Rust, run:"
    echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    echo "  source ~/.cargo/env"
    echo ""
    echo "Or run the setup script:"
    echo "  ./scripts/setup-tauri.sh"
    echo ""
    exit 1
fi

# Check if npm dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo ""
echo "Starting Tauri dev server..."
echo "- Frontend: Hot reload enabled"
echo "- Backend: Python from conda environment"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run Tauri dev
npm run dev
