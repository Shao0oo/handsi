#!/usr/bin/env bash
# bump-version.sh - Update version across all project files
#
# Usage:
#   ./scripts/bump-version.sh 0.2.0           # Update all files
#   ./scripts/bump-version.sh 0.2.0 --dry-run # Preview changes
#   ./scripts/bump-version.sh 0.2.0 --commit  # Update + git commit
#   ./scripts/bump-version.sh 0.2.0 --tag     # Update + commit + tag

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Files to update
FILES=(
    "package.json"
    "pyproject.toml"
    "src-tauri/tauri.conf.json"
    "src-tauri/Cargo.toml"
    "src/handsi/__init__.py"
)

# Parse arguments
VERSION=""
DRY_RUN=false
DO_COMMIT=false
DO_TAG=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --commit)
            DO_COMMIT=true
            shift
            ;;
        --tag)
            DO_TAG=true
            DO_COMMIT=true  # --tag implies --commit
            shift
            ;;
        -h|--help)
            echo "Usage: $0 <version> [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run  Preview changes without writing"
            echo "  --commit   Create git commit after updating"
            echo "  --tag      Create git tag (implies --commit)"
            echo ""
            echo "Examples:"
            echo "  $0 0.2.0           # Update all files"
            echo "  $0 0.2.0 --dry-run # Preview changes"
            echo "  $0 0.2.0 --commit  # Update + commit"
            echo "  $0 0.2.0 --tag     # Update + commit + tag"
            exit 0
            ;;
        *)
            if [[ -z "$VERSION" ]]; then
                VERSION="$1"
            else
                echo -e "${RED}Error: Unknown argument '$1'${NC}"
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate version argument
if [[ -z "$VERSION" ]]; then
    echo -e "${RED}Error: Version argument required${NC}"
    echo "Usage: $0 <version> [--dry-run] [--commit] [--tag]"
    exit 1
fi

# Validate semver format (X.Y.Z or X.Y.Z-suffix)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo -e "${RED}Error: Invalid version format '$VERSION'${NC}"
    echo "Expected format: X.Y.Z or X.Y.Z-suffix (e.g., 0.2.0, 1.0.0-beta)"
    exit 1
fi

cd "$PROJECT_ROOT"

echo -e "${BLUE}Bumping version to ${GREEN}$VERSION${NC}"
echo ""

# Function to get current version from a file
get_current_version() {
    local file="$1"
    case "$file" in
        package.json|src-tauri/tauri.conf.json)
            grep -o '"version": *"[^"]*"' "$file" | head -1 | sed 's/.*"\([^"]*\)"/\1/'
            ;;
        pyproject.toml)
            grep -E '^version *= *"' "$file" | sed 's/version *= *"\([^"]*\)"/\1/'
            ;;
        src-tauri/Cargo.toml)
            grep -E '^version *= *"' "$file" | head -1 | sed 's/version *= *"\([^"]*\)"/\1/'
            ;;
        src/handsi/__init__.py)
            grep '^__version__' "$file" | sed 's/__version__ *= *"\([^"]*\)"/\1/'
            ;;
    esac
}

# Function to update version in a file
update_file() {
    local file="$1"
    local old_version="$2"
    local new_version="$3"

    case "$file" in
        package.json|src-tauri/tauri.conf.json)
            # JSON: update "version": "X.Y.Z"
            sed -i '' "s/\"version\": *\"$old_version\"/\"version\": \"$new_version\"/" "$file"
            ;;
        pyproject.toml)
            # TOML: update version = "X.Y.Z"
            sed -i '' "s/^version *= *\"$old_version\"/version = \"$new_version\"/" "$file"
            ;;
        src-tauri/Cargo.toml)
            # Cargo.toml: update first version = "X.Y.Z" (package version)
            sed -i '' "0,/^version *= *\"$old_version\"/{s/^version *= *\"$old_version\"/version = \"$new_version\"/}" "$file"
            ;;
        src/handsi/__init__.py)
            # Python: update __version__ = "X.Y.Z"
            sed -i '' "s/__version__ *= *\"$old_version\"/__version__ = \"$new_version\"/" "$file"
            ;;
    esac
}

# Check all files exist and show current versions
echo -e "${YELLOW}Current versions:${NC}"
CURRENT_VERSION=""
for file in "${FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}Error: File not found: $file${NC}"
        exit 1
    fi

    ver=$(get_current_version "$file")
    echo "  $file: $ver"

    # Track if versions are consistent
    if [[ -z "$CURRENT_VERSION" ]]; then
        CURRENT_VERSION="$ver"
    elif [[ "$ver" != "$CURRENT_VERSION" ]]; then
        echo -e "${YELLOW}Warning: Version mismatch detected!${NC}"
    fi
done

echo ""

# Dry run - just show what would change
if $DRY_RUN; then
    echo -e "${YELLOW}Dry run - no changes made${NC}"
    echo ""
    echo "Would update:"
    for file in "${FILES[@]}"; do
        old_ver=$(get_current_version "$file")
        echo -e "  $file: ${RED}$old_ver${NC} -> ${GREEN}$VERSION${NC}"
    done
    exit 0
fi

# Update all files
echo -e "${BLUE}Updating files...${NC}"
for file in "${FILES[@]}"; do
    old_ver=$(get_current_version "$file")
    update_file "$file" "$old_ver" "$VERSION"
    echo -e "  ${GREEN}Updated${NC} $file"
done

# Update package-lock.json
if [[ -f "package-lock.json" ]]; then
    echo -e "  ${BLUE}Updating${NC} package-lock.json..."
    npm install --package-lock-only --silent 2>/dev/null || true
    echo -e "  ${GREEN}Updated${NC} package-lock.json"
fi

echo ""
echo -e "${GREEN}Version updated to $VERSION${NC}"

# Git commit
if $DO_COMMIT; then
    echo ""
    echo -e "${BLUE}Creating git commit...${NC}"
    git add "${FILES[@]}" package-lock.json 2>/dev/null || git add "${FILES[@]}"
    git commit -m "Bump version to $VERSION"
    echo -e "${GREEN}Committed${NC}"
fi

# Git tag
if $DO_TAG; then
    echo ""
    echo -e "${BLUE}Creating git tag v$VERSION...${NC}"
    git tag "v$VERSION"
    echo -e "${GREEN}Tagged v$VERSION${NC}"
    echo ""
    echo -e "${YELLOW}To push the tag and trigger release:${NC}"
    echo "  git push origin main"
    echo "  git push origin v$VERSION"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
