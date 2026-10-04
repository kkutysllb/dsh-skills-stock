#!/bin/sh
# Uninstall script for strategy-research
set -e

echo "→ Uninstalling strategy-research..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  strategy-research uninstalled successfully."
