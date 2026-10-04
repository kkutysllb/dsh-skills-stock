#!/bin/sh
# Uninstall script for business-query
set -e

echo "→ Uninstalling business-query..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  business-query uninstalled successfully."
