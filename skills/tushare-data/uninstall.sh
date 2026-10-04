#!/bin/sh
# Uninstall script for tushare-data
set -e

echo "→ Uninstalling tushare-data..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  tushare-data uninstalled successfully."
