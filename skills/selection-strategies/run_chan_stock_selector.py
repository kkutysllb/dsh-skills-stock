#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论MACD背驰选股脚本（跨技能调用版）

本脚本为薄封装（wrapper），实际引擎位于独立技能包 `stock/stock-analysis/`：
  - 引擎脚本：stock-analysis/scripts/run_chan_stock_selector.py（完整实现）
  - 缠论模块：stock-analysis/chan_theory_v2/（simple_backchi / dynamics / kline / signals）
  - 数据网关：stock/common/（kk_common，Tushare Pro 数据入口）

依赖技能包（安装 selection-strategies 前需先安装）：
  1. stock/stock-analysis   —— 缠论引擎与 chan_theory_v2 模块
  2. stock/common           —— kk_common 金融数据网关
  3. TUSHARE_TOKEN 环境变量 —— 数据访问凭证（见 SKILL.md required-secrets）

算法核心：
  底背驰 = 绿柱面积扩张 + 价格创新低 + MACD金叉确认 → 买入信号
  顶背驰 = 红柱面积萎缩 + 价格创新高 + MACD死叉确认 → 卖出信号

用法:
    python run_chan_stock_selector.py --json
    python run_chan_stock_selector.py --pool hs300 --json
    python run_chan_stock_selector.py --freq 30min --signal buy --json
    python run_chan_stock_selector.py --pool zz500 --top 30 --json
"""

import sys
import os
import subprocess
import json
import argparse

# ── 路径解析 ──────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_STOCK_ROOT = os.path.dirname(_SCRIPT_DIR)

# 引擎位于独立技能 stock/stock-analysis/ 中
_CHAN_ENGINE_SCRIPT = os.path.join(_STOCK_ROOT, "stock-analysis", "scripts", "run_chan_stock_selector.py")
_CHAN_ENGINE_CWD = os.path.join(_STOCK_ROOT, "stock-analysis")


def _resolve_script():
    """解析缠论选股引擎脚本及其工作目录"""
    if os.path.exists(_CHAN_ENGINE_SCRIPT):
        return _CHAN_ENGINE_SCRIPT, _CHAN_ENGINE_CWD
    return None, None


def main():
    parser = argparse.ArgumentParser(description="缠论MACD背驰选股")
    parser.add_argument("--pool", default=None, help="股票池: hs300/zz500/zz1000/all（默认全市场）")
    parser.add_argument("--freq", default=None, help="时间周期: 30min/daily（默认daily）")
    parser.add_argument("--top", type=int, default=None, help="返回数量（默认50）")
    parser.add_argument("--signal", default=None, help="信号类型: buy/sell/all（默认all）")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    script, cwd = _resolve_script()

    if not script:
        print(json.dumps({
            "error": "缠论选股引擎不可用",
            "hint": "引擎位于独立技能 stock/stock-analysis/，请先安装该技能包（含 chan_theory_v2 模块）及 stock/common（kk_common 数据网关），并设置 TUSHARE_TOKEN"
        }, ensure_ascii=False))
        sys.exit(1)

    cmd = [sys.executable, script, "--json"]
    if args.pool:
        cmd.extend(["--pool", args.pool])
    if args.freq:
        cmd.extend(["--freq", args.freq])
    if args.top:
        cmd.extend(["--top", str(args.top)])
    if args.signal:
        cmd.extend(["--signal", args.signal])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=600)

    if result.stdout:
        print(result.stdout)
    else:
        print(json.dumps({"error": result.stderr or "缠论选股无输出"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
