#!/bin/sh
# Uninstall script for a-stock-screener
set -e

echo "→ Uninstalling a-stock-screener..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  a-stock-screener uninstalled successfully."
