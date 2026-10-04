#!/bin/bash
# chart-visualization 安装脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "=== chart-visualization 安装 ==="
echo ""

# 1. 检查 node
echo "[1/4] 检查 Node.js..."
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 node，请先安装 Node.js 18+"
    exit 3
fi
echo "  Node: $(node --version)"

# 2. 安装依赖（无额外npm依赖）
echo ""
echo "[2/4] 安装依赖..."
echo "  无额外依赖，跳过"

# 3. 检查环境变量
echo ""
echo "[3/4] 检查环境变量..."
echo "  无必需环境变量"

# 4. 验证脚本
echo ""
echo "[4/4] 验证生成脚本..."
GEN_SCRIPT="$SCRIPT_DIR/scripts/generate.js"
if [ -f "$GEN_SCRIPT" ]; then
    echo "  generate.js: 已就绪"
else
    echo "  警告: scripts/generate.js 不存在"
fi

echo ""
echo "=== 安装完成 ==="
