#!/usr/bin/env python3
"""参数网格扫描：对策略参数做笛卡尔积回测，输出指标汇总与最优组合。

用法（agent 推荐）：在自己的驱动脚本中 import 本模块，传入真实 data_map：

    import sys; sys.path.insert(0, "<strategy-research-技能根>/scripts/analysis")
    from param_sweep import run_param_sweep
    sweep = run_param_sweep(
        "dual_ma",                       # strategy-research 内置策略名
        {"short_window": [3, 5, 8], "long_window": [20, 30, 60]},
        data_map,                        # {code: DataFrame(open/high/low/close/volume)}
        backtest_kwargs={"initial_cash": 1_000_000},   # 其余走 A 股规则默认
    )
    print(json.dumps(sweep, ensure_ascii=False))

也支持自定义 SignalEngine：传 strategy_factory（callable(**params) -> 带
generate(data_map) 的对象）代替内置策略名。

CLI 冒烟：python3 param_sweep.py --strategy dual_ma --grid '{"short_window":[3,5],"long_window":[10,20]}'
（用确定性随机游走数据，仅供链路验证，不代表真实市场）。

数据纪律：结果表按 sort_by 降序；所有指标由 backtest_engine（A 股规则默认
开启）产出，禁止改写。
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_engine import run_backtest  # noqa: E402

METRIC_KEYS = (
    "total_return_pct",
    "annual_return_pct",
    "sharpe_ratio",
    "max_drawdown_pct",
    "win_rate_pct",
    "trade_count",
)


def run_param_sweep(
    strategy: Any,
    param_grid: Dict[str, List[Any]],
    data_map: Dict[str, Any],
    *,
    backtest_kwargs: Optional[Dict[str, Any]] = None,
    sort_by: str = "sharpe_ratio",
) -> Dict[str, Any]:
    """对参数笛卡尔积逐组合回测。

    Args:
        strategy: 内置策略名（strategy_templates.get_strategy）或
            strategy_factory（callable(**params) -> SignalEngine）。
        param_grid: {参数名: 候选值列表}；为空时退化为单组合基线回测。
        data_map: code -> DataFrame（columns: open/high/low/close/volume）。
        backtest_kwargs: 透传 run_backtest（initial_cash/slippage/
            enforce_a_share_rules 等；默认 A 股规则全开）。
        sort_by: 排序指标（降序）。
    """
    factory = _resolve_factory(strategy)
    backtest_kwargs = dict(backtest_kwargs or {})
    keys = list(param_grid.keys())
    combos: List[Dict[str, Any]] = (
        [dict(zip(keys, values)) for values in itertools.product(*param_grid.values())]
        if keys
        else [{}]
    )

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for params in combos:
        try:
            engine = factory(**params)
            signals = engine.generate(data_map)
            outcome = run_backtest(data_map, signals, **backtest_kwargs)
            if "error" in outcome:
                errors.append({**params, "error": outcome["error"]})
                continue
            metrics = outcome["metrics"]
            results.append({
                **params,
                **{key: metrics.get(key) for key in METRIC_KEYS},
                "rules_enabled": (outcome.get("a_share_rules") or {}).get("enabled"),
            })
        except Exception as exc:  # noqa: BLE001 单组合失败不拖垮整个扫描
            errors.append({**params, "error": str(exc)})

    results.sort(key=lambda row: (row.get(sort_by) is not None, row.get(sort_by) or 0), reverse=True)
    return {
        "sweep": {
            "combinations": len(combos),
            "succeeded": len(results),
            "failed": len(errors),
            "sort_by": sort_by,
            "backtest_kwargs": backtest_kwargs,
        },
        "results": results,
        "best": results[0] if results else None,
        "errors": errors,
    }


def _resolve_factory(strategy: Any) -> Callable[..., Any]:
    if isinstance(strategy, str):
        from strategy_templates import get_strategy

        return lambda **params: get_strategy(strategy, **params)
    if callable(strategy):
        return strategy
    raise ValueError("strategy 需为内置策略名（str）或 strategy_factory（callable）")


# ── CLI 冒烟（确定性随机游走数据）────────────────────────────────────


def _demo_data(days: int = 160):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-01", periods=days)
    close = pd.Series(100.0, index=dates)
    returns = rng.normal(0.0004, 0.015, days)
    close = close * (1 + returns).cumprod()
    frame = pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.004, days)),
            "high": close * (1 + np.abs(rng.normal(0, 0.008, days))),
            "low": close * (1 - np.abs(rng.normal(0, 0.008, days))),
            "close": close,
            "volume": rng.uniform(1e6, 5e6, days),
        },
        index=dates,
    )
    return {"MOCK001.SZ": frame}


def main() -> None:
    parser = argparse.ArgumentParser(description="策略参数网格扫描（冒烟 CLI）")
    parser.add_argument("--strategy", default="dual_ma", choices=["dual_ma", "rsi", "macd"])
    parser.add_argument("--grid", required=True, help='参数网格 JSON，如 \'{"short":[3,5],"long":[10,20]}\'')
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--sort-by", default="sharpe_ratio")
    args = parser.parse_args()

    sweep = run_param_sweep(
        args.strategy,
        json.loads(args.grid),
        _demo_data(),
        backtest_kwargs={"initial_cash": args.cash},
        sort_by=args.sort_by,
    )
    print(json.dumps(sweep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
