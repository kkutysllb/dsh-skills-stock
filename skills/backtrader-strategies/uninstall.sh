#!/bin/sh
# Uninstall script for backtrader_strategies
set -e

echo "→ Uninstalling backtrader_strategies..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  backtrader_strategies uninstalled successfully."
