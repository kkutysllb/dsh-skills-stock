#!/bin/sh
# Uninstall script for cb-analysis
set -e

echo "→ Uninstalling cb-analysis..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  cb-analysis uninstalled successfully."
