#!/bin/sh
# Install script for selection-strategies
set -e

echo "→ Installing selection-strategies..."

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

echo "  ✓  selection-strategies installed successfully."
echo ""
echo "  Dependent skill packages (install separately):"
echo "    - stock/backtrader_strategies  (strategy adapters, add to PYTHONPATH)"
echo "    - stock/stock-analysis         (chan_theory_v2 engine, for chan stock selection)"
echo "    - stock/common                 (kk_common data gateway)"
echo "  Environment variables needed:"
echo "    TUSHARE_TOKEN"
