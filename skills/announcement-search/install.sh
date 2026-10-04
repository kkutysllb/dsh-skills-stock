#!/bin/bash
# announcement-search 安装脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "=== announcement-search 安装 ==="
echo ""

# 1. 检查 python3
echo "[1/4] 检查 Python3..."
if ! command -v "$PYTHON" &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.8+"
    exit 3
fi
echo "  Python: $($PYTHON --version)"

# 2. 安装依赖
echo ""
echo "[2/4] 安装 Python 依赖..."
if [ -f "$SCRIPT_DIR/scripts/requirements.txt" ]; then
    $PYTHON -m pip install -q -r "$SCRIPT_DIR/scripts/requirements.txt"
    echo "  依赖安装完成"
else
    echo "  无第三方依赖，跳过"
fi

# 3. 检查环境变量
echo ""
echo "[3/4] 检查环境变量..."
if [ -z "${IWENCAI_API_KEY:-}" ]; then
    echo "  警告: IWENCAI_API_KEY 未设置（公告搜索将无法运行）"
    echo "  获取方式: https://www.iwencai.com/skillhub"
else
    echo "  IWENCAI_API_KEY: 已设置"
fi

# 4. 验证脚本
echo ""
echo "[4/4] 验证脚本..."
CLI="$SCRIPT_DIR/scripts/__main__.py"
if [ -f "$CLI" ]; then
    echo "  __main__.py: 已就绪"
else
    echo "  警告: scripts/__main__.py 不存在"
fi

echo ""
echo "=== 安装完成 ==="
if [ -z "${IWENCAI_API_KEY:-}" ]; then
    echo ""
    echo "请配置环境变量后使用："
    echo "  export IWENCAI_API_KEY=\"your-api-key\""
fi
