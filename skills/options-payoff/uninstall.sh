#!/bin/sh
# Uninstall script for options-payoff
set -e

echo "→ Uninstalling options-payoff..."

if [ -f package.json ]; then
    rm -rf node_modules 2>/dev/null || true
    echo "  → Removed node_modules"
fi

echo "  ✓  options-payoff uninstalled successfully."
