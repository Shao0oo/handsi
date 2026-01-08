#!/bin/bash
#
# Setup script for Handsi Tauri development environment
#
# Installs all required dependencies for Tauri development.
# Run this ONCE after cloning the repository.
#

set -e

echo "======================================="
echo "Handsi Tauri - Setup Script"
echo "======================================="
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check Python/Conda
echo "Checking Python environment..."
if [[ -z "${CONDA_DEFAULT_ENV}" ]]; then
    echo "❌ Error: Conda environment not active"
    echo "   Please run: conda activate handsi"
    echo "   If 'handsi' environment doesn't exist, create it first:"
    echo "   conda create -n handsi python=3.11"
    exit 1
fi

if [[ "${CONDA_DEFAULT_ENV}" != "handsi" ]]; then
    echo "⚠️  Warning: Not in 'handsi' conda environment"
    echo "   Current: ${CONDA_DEFAULT_ENV}"
    echo "   Expected: handsi"
    read -p "   Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ Python environment: ${CONDA_DEFAULT_ENV}"
echo ""

# Check/Install Node.js
echo "Checking Node.js..."
if ! command_exists node; then
    echo "❌ Node.js not found"
    echo "   Installing Node.js via Homebrew..."
    if ! command_exists brew; then
        echo "   Error: Homebrew not found. Please install from https://brew.sh"
        exit 1
    fi
    brew install node
else
    echo "✅ Node.js: $(node --version)"
fi
echo ""

# Check/Install Rust
echo "Checking Rust..."
if ! command_exists cargo; then
    echo "❌ Rust/Cargo not found"
    echo "   Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "✅ Rust: $(rustc --version)"
    echo "✅ Cargo: $(cargo --version)"
fi
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -e .
echo "✅ Python dependencies installed"
echo ""

# Install npm dependencies
echo "Installing npm dependencies..."
npm install
echo "✅ npm dependencies installed"
echo ""

echo "======================================="
echo "Setup complete!"
echo "======================================="
echo ""
echo "Next steps:"
echo "  1. Run in development mode:"
echo "     ./scripts/dev-tauri.sh"
echo ""
echo "  2. Build for production:"
echo "     ./scripts/build-tauri.sh"
echo ""
echo "See docs/TAURI_MIGRATION.md for more info."
echo ""
