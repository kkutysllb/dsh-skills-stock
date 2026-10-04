#!/usr/bin/env python3
"""
etf-analysis CLI — ETF 全维度分析统一入口

支持两种引擎：
  tushare  — Tushare Pro ETF 分析（行情/净值/份额/规模/分类/指数/对比/持仓/经理/分红）
  selector — 问财智能选ETF（自然语言筛选，实时数据）

用法:
  python cli.py tushare <action> [--params key=value ...]
  python cli.py selector --query "沪深300ETF"
  python cli.py help
"""
import os
import sys
import json
import subprocess


def run_tushare(args):
    """调用 Tushare ETF 分析引擎。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_analyzer.py")
    if not os.path.isfile(script):
        print(json.dumps({"error": "Tushare 引擎脚本 etf_analyzer.py 不存在"}))
        sys.exit(1)
    cmd = [sys.executable, script] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr and result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)


def run_selector(args):
    """调用问财 ETF 筛选引擎。"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etf_selector.py")
    if not os.path.isfile(script):
        print(json.dumps({"error": "问财引擎脚本 etf_selector.py 不存在"}))
        sys.exit(1)
    cmd = [sys.executable, script] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr and result.returncode != 0:
        print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)


def show_help():
    help_text = """
etf-analysis — ETF 全维度分析技能包
======================================

引擎1: tushare — Tushare Pro ETF 分析（T+1 数据）
---------------------------------------------------
  python cli.py tushare list --params market=E limit=20
  python cli.py tushare daily --params ts_code=510300.SH start_date=2026-01-01
  python cli.py tushare nav --params ts_code=510300.SH limit=60
  python cli.py tushare shares --params ts_code=510300.SH limit=60
  python cli.py tushare scale --params ts_code=510300.SH
  python cli.py tushare classify --params limit=5
  python cli.py tushare screen --params etf_type=宽基ETF limit=10
  python cli.py tushare index --params ts_code=510300.SH
  python cli.py tushare sector --params sector=半导体 limit=10
  python cli.py tushare compare --params ts_codes=510300.SH,159919.SZ,510500.SH
  python cli.py tushare portfolio --params ts_code=510300.SH
  python cli.py tushare managers --params ts_code=510300.SH
  python cli.py tushare dividends --params ts_code=510300.SH

  操作: list|daily|nav|shares|scale|classify|screen|index|sector|compare|portfolio|managers|dividends

引擎2: selector — 问财智能选ETF（实时数据）
---------------------------------------------
  python cli.py selector --query "沪深300ETF有哪些？"
  python cli.py selector --query "规模最大的ETF" --page 1 --limit 20
  python cli.py selector --query "创业板ETF" --call-type retry --timeout 60

环境变量:
  TUSHARE_TOKEN      — Tushare Pro API Token（tushare 引擎必需）
  IWENCAI_API_KEY    — 问财 API Key（selector 引擎必需）
"""
    print(help_text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        show_help()
        sys.exit(0)

    engine = sys.argv[1].lower()
    rest_args = sys.argv[2:]

    if engine == "tushare":
        run_tushare(rest_args)
    elif engine == "selector":
        run_selector(rest_args)
    else:
        print(json.dumps({
            "error": f"未知引擎: {engine}",
            "available_engines": ["tushare", "selector"],
            "usage": "python cli.py <tushare|selector> [args...]"
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
