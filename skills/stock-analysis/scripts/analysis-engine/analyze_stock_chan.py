#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股缠论买卖点分析脚本（自包含版）

内嵌 chan_theory_v2 引擎，基于缠论理论对个股进行完整的形态学和动力学分析。
数据通过 Tushare Pro API 实时获取，不依赖本地数据库。

核心功能：
  - 形态学分析：K线处理、分型识别、笔构建、线段构建、中枢识别
  - 动力学分析：MACD背驰、三类买卖点识别
  - 多级别联立：5分钟/30分钟/日线递归关系和区间套策略
  - 交易建议：入场价、止损位、止盈位

用法:
    python scripts/analysis-engine/analyze_stock_chan.py --stock 600519.SH --json
    python scripts/analysis-engine/analyze_stock_chan.py --stock 宁德时代 --multi-level --json
    python scripts/analysis-engine/analyze_stock_chan.py --stock 300750.SZ --level 30min --json
"""

import sys
import os
import subprocess
import json
import argparse

# ── 路径解析 ──────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))

# 内嵌缠论引擎路径
_CHAN_ENGINE_SCRIPT = os.path.join(_SKILL_ROOT, "scripts", "analyze_stock_chan.py")

# 兼容：如果在主项目内运行，也尝试主项目脚本
_PROJECT_ROOT = os.path.dirname(_SKILL_ROOT)
_MAIN_PROJECT_SCRIPT = os.path.join(_PROJECT_ROOT, "scripts", "analyze_stock_chan.py")


def _resolve_script():
    """解析可用的缠论分析脚本"""
    # 优先使用内嵌引擎
    if os.path.exists(_CHAN_ENGINE_SCRIPT):
        return _CHAN_ENGINE_SCRIPT, _SKILL_ROOT
    # 回退到主项目脚本
    if os.path.exists(_MAIN_PROJECT_SCRIPT):
        return _MAIN_PROJECT_SCRIPT, _PROJECT_ROOT
    return None, None


def main():
    parser = argparse.ArgumentParser(description="个股缠论买卖点分析")
    parser.add_argument("--stock", required=True, help="股票代码或名称")
    parser.add_argument("--level", default="daily", help="分析级别: 5min/15min/30min/60min/daily/weekly")
    parser.add_argument("--multi-level", action="store_true", help="多级别联立分析")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    script, cwd = _resolve_script()

    if not script:
        print(json.dumps({
            "error": "缠论分析引擎不可用",
            "hint": "请确保 scripts/chan_engine/ 目录存在且包含缠论引擎代码"
        }, ensure_ascii=False))
        sys.exit(1)

    cmd = [sys.executable, script, "--stock", args.stock, "--json"]
    if args.multi_level:
        cmd.append("--multi-level")
    if args.level and args.level != "daily":
        cmd.extend(["--level", args.level])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=300)

    if result.stdout:
        print(result.stdout)
    else:
        print(json.dumps({"error": result.stderr or "缠论分析无输出"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
