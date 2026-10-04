#!/bin/sh
# Uninstall script for macro-query
set -e

echo "→ Uninstalling macro-query..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  macro-query uninstalled successfully."
