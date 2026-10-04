#!/bin/sh
# Uninstall script for options-volatility
set -e

echo "→ Uninstalling options-volatility..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  options-volatility uninstalled successfully."
