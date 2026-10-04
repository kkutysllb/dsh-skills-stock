#!/bin/sh
# Uninstall script for report-search
set -e

echo "→ Uninstalling report-search..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  report-search uninstalled successfully."
