#!/bin/sh
# Uninstall script for chart-visualization
set -e

echo "→ Uninstalling chart-visualization..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  chart-visualization uninstalled successfully."
