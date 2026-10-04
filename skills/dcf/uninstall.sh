#!/bin/sh
# Uninstall script for mcf
set -e

echo "→ Uninstalling mcf..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  mcf uninstalled successfully."
