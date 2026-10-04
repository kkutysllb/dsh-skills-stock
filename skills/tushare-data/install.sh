#!/bin/sh
# Install script for tushare-data
set -e

echo "→ Installing tushare-data..."

# Check Python
if ! command -v python3 > /dev/null 2>&1; then
    echo "  ⚠  Python 3 is required but not found."
    exit 1
fi

# Install Python dependencies
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
    echo "  → Python dependencies installed"
fi

echo "  ✓  tushare-data installed successfully."
echo ""
echo "  Environment variables needed:"
echo "    See SKILL.md frontmatter for details."
