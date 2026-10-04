#!/bin/sh
# Uninstall script for hithink-futures
set -e

echo "→ Uninstalling hithink-futures..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  hithink-futures uninstalled successfully."
