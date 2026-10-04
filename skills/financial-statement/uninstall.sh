#!/bin/sh
# Uninstall script for financial-statement
set -e

echo "→ Uninstalling financial-statement..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  financial-statement uninstalled successfully."
