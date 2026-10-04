#!/bin/sh
# Uninstall script for etf-analysis
set -e

echo "→ Uninstalling etf-analysis..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  etf-analysis uninstalled successfully."
