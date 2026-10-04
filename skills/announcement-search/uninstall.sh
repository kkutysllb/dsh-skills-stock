#!/bin/sh
# Uninstall script for announcement-search
set -e

echo "→ Uninstalling announcement-search..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  announcement-search uninstalled successfully."
