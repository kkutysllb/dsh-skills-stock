#!/bin/sh
# Uninstall script for event-query
set -e

echo "→ Uninstalling event-query..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  event-query uninstalled successfully."
