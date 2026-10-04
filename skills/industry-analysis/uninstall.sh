#!/bin/sh
# Uninstall script for industry-analysis
set -e

echo "→ Uninstalling industry-analysis..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  industry-analysis uninstalled successfully."
