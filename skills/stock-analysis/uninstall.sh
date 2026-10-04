#!/bin/sh
# Uninstall script for stock-analysis
set -e

echo "→ Uninstalling stock-analysis..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  stock-analysis uninstalled successfully."
