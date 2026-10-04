#!/usr/bin/env python3
"""
strategy-research CLI — 量化策略研究统一入口

支持模式:
  demo     — 用模拟数据运行策略演示回测
  validate — 验证 signal_engine.py 语法
  help     — 显示帮助
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.join(SCRIPT_DIR, "analysis")
sys.path.insert(0, ANALYSIS_DIR)


def cmd_demo(args):
    """用模拟数据运行策略回测演示"""
    import numpy as np
    import pandas as pd
    from strategy_templates import get_strategy
    from backtest_engine import run_backtest, evaluate_strategy

    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", "2024-12-31")
    n = len(dates)

    # 生成模拟行情数据（随机游走）
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.randn() * 0.02))
    close = pd.Series(prices, index=dates)
    df = pd.DataFrame({
        "open": close * (1 + np.random.randn(n) * 0.005),
        "high": close * (1 + abs(np.random.randn(n) * 0.01)),
        "low": close * (1 - abs(np.random.randn(n) * 0.01)),
        "close": close,
        "volume": np.random.uniform(1e6, 1e7, n),
    }, index=dates)

    code = "MOCK001.SZ"
    data_map = {code: df}

    # 获取策略
    strategy_kwargs = {}
    if args.strategy == "dual_ma":
        strategy_kwargs = {"short_window": args.short, "long_window": args.long}
    elif args.strategy == "rsi":
        strategy_kwargs = {"period": args.period, "oversold": args.oversold, "overbought": args.overbought}

    engine = get_strategy(args.strategy, **strategy_kwargs)
    signals = engine.generate(data_map)
    result = run_backtest(
        data_map, signals,
        initial_cash=args.cash,
        commission=args.commission,
        slippage=args.slippage,
        enforce_a_share_rules=not args.no_a_share_rules,
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    # 评估
    evaluation = evaluate_strategy(result["metrics"])

    # 构造输出
    output = {
        "strategy": args.strategy,
        "params": strategy_kwargs,
        "code": code,
        "n_days": len(dates),
        "metrics": result["metrics"],
        "evaluation": evaluation,
        "trade_count": result["trade_count"],
        "rebalance_count": result.get("rebalance_count", 0),
    }

    # 调仓记录（前10条）
    if result.get("rebalance_records"):
        output["rebalance_sample"] = result["rebalance_records"][:10]

    # 持仓快照（首/中/尾 3个时间点）
    snapshots = result.get("position_snapshots", [])
    if snapshots:
        mid = len(snapshots) // 2
        output["position_snapshot_head"] = snapshots[0]
        output["position_snapshot_mid"] = snapshots[mid]
        output["position_snapshot_tail"] = snapshots[-1]
        output["position_snapshot_count"] = len(snapshots)

    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_validate(args):
    """验证 signal_engine.py 语法"""
    import ast
    if not os.path.isfile(args.file):
        print(json.dumps({"error": f"文件不存在: {args.file}"}))
        sys.exit(1)
    try:
        with open(args.file, "r") as f:
            ast.parse(f.read())
        print(json.dumps({"valid": True, "file": args.file}))
    except SyntaxError as e:
        print(json.dumps({"valid": False, "file": args.file, "error": str(e), "line": e.lineno}))
        sys.exit(1)


def cmd_list(args):
    """列出可用策略"""
    from strategy_templates import STRATEGY_REGISTRY
    strategies = []
    for name, cls in STRATEGY_REGISTRY.items():
        strategies.append({
            "name": name,
            "class": cls.__name__,
            "description": cls.__doc__.strip() if cls.__doc__ else "",
        })
    print(json.dumps({"strategies": strategies}, ensure_ascii=False, indent=2))


def show_help():
    help_text = """
strategy-research — 量化策略研究技能包
==========================================

模式1: demo — 策略演示回测（模拟数据）
---------------------------------------
  python cli.py demo --strategy dual_ma --short 5 --long 20
  python cli.py demo --strategy rsi --period 14 --oversold 30 --overbought 70
  python cli.py demo --strategy macd

模式2: validate — 验证策略文件语法
-----------------------------------
  python cli.py validate --file signal_engine.py

模式3: list — 列出可用策略
---------------------------
  python cli.py list

可用策略: dual_ma / rsi / macd
"""
    print(help_text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        show_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(description="strategy-research CLI")
    sub = parser.add_subparsers(dest="mode")

    # demo 模式
    p_demo = sub.add_parser("demo", help="策略演示回测")
    p_demo.add_argument("--strategy", default="dual_ma", choices=["dual_ma", "rsi", "macd"])
    p_demo.add_argument("--short", type=int, default=5, help="短均线周期")
    p_demo.add_argument("--long", type=int, default=20, help="长均线周期")
    p_demo.add_argument("--period", type=int, default=14, help="RSI 周期")
    p_demo.add_argument("--oversold", type=float, default=30.0, help="RSI 超卖阈值")
    p_demo.add_argument("--overbought", type=float, default=70.0, help="RSI 超买阈值")
    p_demo.add_argument("--cash", type=float, default=1_000_000, help="初始资金")
    p_demo.add_argument("--commission", type=float, default=0.001, help="手续费率")
    p_demo.add_argument("--slippage", type=float, default=0.0, help="滑点比例（0.001 = 0.1%）")
    p_demo.add_argument("--no-a-share-rules", action="store_true",
                        help="关闭A股交易规则（T+1/涨跌停/整手/最低佣金/印花税，回到简化回测）")

    # validate 模式
    p_val = sub.add_parser("validate", help="验证策略文件语法")
    p_val.add_argument("--file", required=True, help="signal_engine.py 路径")

    # list 模式
    sub.add_parser("list", help="列出可用策略")

    args = parser.parse_args()
    if args.mode == "demo":
        cmd_demo(args)
    elif args.mode == "validate":
        cmd_validate(args)
    elif args.mode == "list":
        cmd_list(args)
    else:
        show_help()


if __name__ == "__main__":
    main()
