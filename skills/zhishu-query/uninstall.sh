#!/bin/sh
# Uninstall script for zhishu-query
set -e

echo "→ Uninstalling zhishu-query..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  zhishu-query uninstalled successfully."
