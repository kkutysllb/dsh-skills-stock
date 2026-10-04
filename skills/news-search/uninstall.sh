#!/bin/sh
# Uninstall script for news-search
set -e

echo "→ Uninstalling news-search..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  news-search uninstalled successfully."
