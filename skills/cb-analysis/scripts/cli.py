#!/usr/bin/env python3
"""
cb-analysis CLI — 可转债分析统一入口

三引擎架构：
  selector  — 智能筛选（问财自然语言查询）
  analyzer  — 多维度分析（单只深度/批量对比）
  dashboard — 全景看板（16大模块）

所有引擎基于同花顺问财 OpenAPI，Python3 标准库，无第三方依赖。
"""
import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable or "python3"

# 引擎脚本路径
ENGINES = {
    "selector": os.path.join(SCRIPT_DIR, "selector.py"),
    "analyzer": os.path.join(SCRIPT_DIR, "analyzer.py"),
    "dashboard": os.path.join(SCRIPT_DIR, "dashboard.py"),
}

# Dashboard 可用模块
DASHBOARD_MODULES = [
    "forced-redeem", "downrev-count", "small-scale", "limit-stock",
    "dragon-tiger", "issuance", "top10",
    "bond-cushion", "rights-recovery", "time-option", "hard-redeem",
    "maturity-price", "premium-analysis", "grid-trading", "monster-bond", "arbitrage",
]


def _run_engine(script: str, extra_args: list) -> int:
    """调用引擎脚本并透传输出。"""
    cmd = [PYTHON, script] + extra_args
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    return result.returncode


def cmd_select(args):
    """智能筛选可转债"""
    engine_args = [
        "--query", args.query,
    ]
    if args.page:
        engine_args += ["--page", args.page]
    if args.limit:
        engine_args += ["--limit", args.limit]
    if args.api_key:
        engine_args += ["--api-key", args.api_key]
    if args.call_type:
        engine_args += ["--call-type", args.call_type]
    if args.timeout:
        engine_args += ["--timeout", str(args.timeout)]
    return _run_engine(ENGINES["selector"], engine_args)


def cmd_analyze(args):
    """多维度分析可转债"""
    engine_args = [
        "--mode", args.mode,
        "--bonds", args.bonds,
    ]
    if args.api_key:
        engine_args += ["--api-key", args.api_key]
    if args.call_type:
        engine_args += ["--call-type", args.call_type]
    if args.timeout:
        engine_args += ["--timeout", str(args.timeout)]
    return _run_engine(ENGINES["analyzer"], engine_args)


def cmd_dashboard(args):
    """全景看板"""
    mode = args.module or "dashboard"
    engine_args = ["--mode", mode]
    if args.api_key:
        engine_args += ["--api-key", args.api_key]
    if args.timeout:
        engine_args += ["--timeout", str(args.timeout)]
    if args.limit:
        engine_args += ["--limit", args.limit]
    return _run_engine(ENGINES["dashboard"], engine_args)


def cmd_list(args):
    """列出所有可用模式"""
    output = {
        "engine": "cb-analysis",
        "modes": {
            "select": {
                "description": "智能筛选可转债（自然语言查询）",
                "example": "cli.py select --query '转股溢价率低于10%的可转债'",
            },
            "analyze": {
                "description": "单只深度分析（single）或批量对比（compare）",
                "modes": ["single", "compare"],
                "example": "cli.py analyze --mode single --bonds '精达转债'",
            },
            "dashboard": {
                "description": "全景看板（16大模块）",
                "modules": DASHBOARD_MODULES,
                "example": "cli.py dashboard --module forced-redeem",
            },
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def show_help():
    help_text = """
cb-analysis — 可转债分析统一入口
====================================

引擎1: select — 智能筛选（问财自然语言查询）
---------------------------------------------
  python cli.py select --query "转股溢价率低于10%的可转债"
  python cli.py select --query "AAA级可转债" --limit 20

引擎2: analyze — 多维度深度分析
--------------------------------
  # 单只深度分析
  python cli.py analyze --mode single --bonds "精达转债"

  # 批量横向对比
  python cli.py analyze --mode compare --bonds "精达转债,立讯转债,天业转债"

引擎3: dashboard — 全景看板（16大模块）
----------------------------------------
  # 全景看板
  python cli.py dashboard

  # 单模块
  python cli.py dashboard --module forced-redeem
  python cli.py dashboard --module top10
  python cli.py dashboard --module arbitrage

其他:
  python cli.py list   — 列出所有可用模式
  python cli.py help   — 显示本帮助

公共参数: --api-key / --timeout / --call-type

环境变量: IWENCAI_API_KEY（必填，问财API密钥）
"""
    print(help_text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        show_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="cb-analysis CLI")
    sub = parser.add_subparsers(dest="engine")

    # select 引擎
    p_sel = sub.add_parser("select", help="智能筛选可转债")
    p_sel.add_argument("--query", "-q", required=True, help="查询语句")
    p_sel.add_argument("--page", default="1", help="分页页码")
    p_sel.add_argument("--limit", default="10", help="每页条数")
    p_sel.add_argument("--api-key", default=None, help="问财API密钥")
    p_sel.add_argument("--call-type", choices=["normal", "retry"], default="normal")
    p_sel.add_argument("--timeout", type=int, default=30)

    # analyze 引擎
    p_ana = sub.add_parser("analyze", help="多维度分析")
    p_ana.add_argument("--mode", "-m", required=True, choices=["single", "compare"])
    p_ana.add_argument("--bonds", "-b", required=True, help="可转债名称，逗号分隔")
    p_ana.add_argument("--api-key", default=None)
    p_ana.add_argument("--call-type", choices=["normal", "retry"], default="normal")
    p_ana.add_argument("--timeout", type=int, default=30)

    # dashboard 引擎
    p_dash = sub.add_parser("dashboard", help="全景看板")
    p_dash.add_argument("--module", default=None, choices=DASHBOARD_MODULES + ["dashboard"],
                        help="指定模块（默认: dashboard 全景）")
    p_dash.add_argument("--api-key", default=None)
    p_dash.add_argument("--timeout", type=int, default=30)
    p_dash.add_argument("--limit", default="20", help="每页条数")

    # list 模式
    sub.add_parser("list", help="列出所有可用模式")

    args = parser.parse_args()
    if args.engine == "select":
        rc = cmd_select(args)
    elif args.engine == "analyze":
        rc = cmd_analyze(args)
    elif args.engine == "dashboard":
        rc = cmd_dashboard(args)
    elif args.engine == "list":
        cmd_list(args)
        rc = 0
    else:
        show_help()
        rc = 0

    sys.exit(rc)


if __name__ == "__main__":
    main()
