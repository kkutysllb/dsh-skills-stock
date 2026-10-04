#!/bin/bash
# chart-visualization 打包脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_NAME="chart-visualization"
DIST_DIR="$SKILL_DIR/dist"

VERSION=$(grep '^version:' "$SKILL_DIR/SKILL.md" | head -1 | sed 's/version: *//' | tr -d '"' | tr -d "'")
if [ -z "$VERSION" ]; then
    VERSION="1.0.0"
fi

echo "=== chart-visualization 打包 ==="
echo "版本: $VERSION"
echo "源目录: $SKILL_DIR"
echo "输出目录: $DIST_DIR"
echo ""

# 创建输出目录
mkdir -p "$DIST_DIR"

# 验证 SKILL.md 存在
if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
    echo "错误: SKILL.md 不存在"
    exit 1
fi

# 验证 name
NAME=$(grep '^name:' "$SKILL_DIR/SKILL.md" | head -1 | sed 's/name: *//' | tr -d '"' | tr -d "'")
if [ -z "$NAME" ]; then
    echo "错误: SKILL.md 缺少 name 字段"
    exit 1
fi
echo "技能名称: $NAME"

# 验证图表生成脚本
GENERATE="$SKILL_DIR/scripts/generate.js"
if [ -f "$GENERATE" ]; then
    echo "图表生成脚本: ✓"
else
    echo "警告: scripts/generate.js 不存在"
fi

# 验证参考文档
REF_DIR="$SKILL_DIR/references"
if [ -d "$REF_DIR" ]; then
    REF_COUNT=$(ls -1 "$REF_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
    echo "参考文档: ${REF_COUNT} 个"
fi

echo ""

# 1. 打包为 .skill (ZIP)
SKILL_FILE="$DIST_DIR/${SKILL_NAME}.skill"
echo "[1/2] 打包 .skill (ZIP)..."
cd "$SKILL_DIR"
zip -r -q "$SKILL_FILE" . \
    -x "*.pyc" \
    -x "__pycache__/*" \
    -x ".DS_Store" \
    -x "__MACOSX/*" \
    -x "node_modules/*"
echo "  输出: $SKILL_FILE ($(du -h "$SKILL_FILE" | cut -f1))"

# 2. 打包为 .tar.gz
TAR_FILE="$DIST_DIR/${SKILL_NAME}-${VERSION}.tar.gz"
echo "[2/2] 打包 .tar.gz ..."
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$TAR_FILE" \
    -C "$(dirname "$SKILL_DIR")" \
    "$(basename "$SKILL_DIR")"/SKILL.md \
    "$(basename "$SKILL_DIR")"/install.sh \
    "$(basename "$SKILL_DIR")"/scripts/ \
    "$(basename "$SKILL_DIR")"/references/ \
    2>/dev/null
echo "  输出: $TAR_FILE ($(du -h "$TAR_FILE" | cut -f1))"

echo ""
echo "=== 打包完成 ==="
echo ""
echo "文件列表:"
echo "  $SKILL_FILE  (Qoder/OpenClaw 技能包)"
echo "  $TAR_FILE    (通用发布包)"

# 验证 ZIP 内容
echo ""
echo "=== .skill 包内容 ==="
unzip -l "$SKILL_FILE" | tail -1
