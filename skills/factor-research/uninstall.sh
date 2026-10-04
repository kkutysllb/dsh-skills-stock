#!/bin/sh
# Uninstall script for factor-research
set -e

echo "→ Uninstalling factor-research..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  factor-research uninstalled successfully."
