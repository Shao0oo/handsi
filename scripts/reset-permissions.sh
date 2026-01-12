#!/bin/bash
#
# Reset Handsi macOS Permissions
#
# This script resets all TCC (Transparency, Consent, and Control) permissions
# for Handsi, including camera, accessibility, and automation permissions.
#
# Run this before reinstalling Handsi to get a clean slate.
#

set -e

echo "============================"
echo "Handsi Permission Reset"
echo "============================"
echo ""

# Reset permissions for current bundle ID
echo "Resetting permissions for com.handsi.desktop..."
tccutil reset Camera com.handsi.desktop 2>/dev/null || echo "  (no camera permissions to reset)"
tccutil reset Accessibility com.handsi.desktop 2>/dev/null || echo "  (no accessibility permissions to reset)"
tccutil reset AppleEvents com.handsi.desktop 2>/dev/null || echo "  (no automation permissions to reset)"

# Reset permissions for old bundle ID (if it exists)
echo ""
echo "Resetting permissions for old bundle ID (com.handsi.app)..."
tccutil reset Camera com.handsi.app 2>/dev/null || echo "  (no camera permissions to reset)"
tccutil reset Accessibility com.handsi.app 2>/dev/null || echo "  (no accessibility permissions to reset)"
tccutil reset AppleEvents com.handsi.app 2>/dev/null || echo "  (no automation permissions to reset)"

# Restart cfprefsd to apply changes
echo ""
echo "Restarting System Settings daemon..."
killall cfprefsd 2>/dev/null || true

echo ""
echo "============================"
echo "✓ Permissions reset complete!"
echo "============================"
echo ""
echo "Next steps:"
echo "1. Reinstall Handsi.app"
echo "2. Grant camera permission when prompted"
echo "3. Grant accessibility permission in:"
echo "   System Settings → Privacy & Security → Accessibility"
echo ""
