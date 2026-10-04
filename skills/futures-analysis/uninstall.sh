#!/bin/sh
# Uninstall script for futures-analysis
set -e

echo "→ Uninstalling futures-analysis..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  futures-analysis uninstalled successfully."
