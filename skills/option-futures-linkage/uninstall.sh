#!/bin/sh
# Uninstall script for option-futures-linkage
set -e

echo "→ Uninstalling option-futures-linkage..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  option-futures-linkage uninstalled successfully."
