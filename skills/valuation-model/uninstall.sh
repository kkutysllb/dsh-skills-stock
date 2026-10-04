#!/bin/sh
# Uninstall script for valuation-model
set -e

echo "→ Uninstalling valuation-model..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  valuation-model uninstalled successfully."
