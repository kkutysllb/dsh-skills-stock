#!/usr/bin/env python3
"""Walk-forward 滚动验证：训练窗选参、测试窗评估，拼接样本外净值。

解决「全样本调参 = 用未来信息选参数」的前视偏差：每个测试窗只用其之前
的训练窗数据选择参数（若不给 param_grid 则退化为固定参数的滚动一致性
检验），测试窗结果拼接为样本外总收益。

用法（agent 推荐，import 本模块传真实 data_map）：

    import sys; sys.path.insert(0, "<strategy-research-技能根>/scripts/analysis")
    from walk_forward import run_walk_forward
    wf = run_walk_forward(
        "dual_ma",
        {"short": [3, 5], "long": [10, 20]},
        data_map,
        train_bars=120, test_bars=20,     # 训练 120 交易日、测试 20 交易日滚动
    )
    print(json.dumps(wf, ensure_ascii=False))

语义要点：
- 信号生成使用截至测试窗末的完整历史（保证均线等指标的回看窗口完整），
  但**参数选择与指标评估只发生在各自窗口内**；
- 样本外总收益 = 各测试窗收益的几何拼接；win_windows 统计盈利测试窗数；
- param_stability 反映选参稳定性（同一参数组合被选中的次数）——参数在
  相邻窗口间频繁翻转通常意味着过拟合。
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_engine import run_backtest  # noqa: E402
from param_sweep import _demo_data, _resolve_factory  # noqa: E402


def _all_dates(data_map: Dict[str, Any]) -> List[Any]:
    return sorted(set().union(*(data_map[code].index for code in data_map)))


def _slice_map(data_map: Dict[str, Any], lo: Any, hi: Any) -> Dict[str, Any]:
    return {code: frame.loc[lo:hi] for code, frame in data_map.items()}


def _slice_signals(signals: Dict[str, Any], lo: Any, hi: Any) -> Dict[str, Any]:
    return {code: series.loc[lo:hi] for code, series in signals.items()}


def run_walk_forward(
    strategy: Any,
    param_grid: Optional[Dict[str, List[Any]]],
    data_map: Dict[str, Any],
    *,
    train_bars: int = 120,
    test_bars: int = 20,
    metric_key: str = "sharpe_ratio",
    backtest_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """滚动训练/测试评估。

    Args:
        strategy: 内置策略名或 strategy_factory（同 param_sweep）。
        param_grid: 训练窗内的候选参数网格；None = 不选参（固定默认参数）。
        train_bars / test_bars: 训练与测试窗口长度（交易日）。
        metric_key: 训练窗选参依据的指标（run_backtest metrics 键）。
        backtest_kwargs: 透传 run_backtest（A 股规则默认全开）。
    """
    if train_bars < 10 or test_bars < 1:
        raise ValueError("train_bars >= 10 且 test_bars >= 1")
    factory = _resolve_factory(strategy)
    backtest_kwargs = dict(backtest_kwargs or {})
    dates = _all_dates(data_map)
    if len(dates) <= train_bars + test_bars:
        raise ValueError(f"数据不足：{len(dates)} 根 <= train({train_bars})+test({test_bars})")

    keys = list((param_grid or {}).keys())
    combos = (
        [dict(zip(keys, values)) for values in itertools.product(*param_grid.values())]
        if keys
        else [{}]
    )

    windows: List[Dict[str, Any]] = []
    equity = 1.0
    param_votes: Counter = Counter()
    start = train_bars
    while start + test_bars <= len(dates):
        train_lo, train_hi = dates[start - train_bars], dates[start - 1]
        test_lo, test_hi = dates[start], dates[min(start + test_bars, len(dates)) - 1]

        # 训练窗选参（无网格时用默认参数）
        chosen: Dict[str, Any] = {}
        if keys:
            best_score = None
            for params in combos:
                train_signals = factory(**params).generate(
                    _slice_map(data_map, dates[0], train_hi)
                )
                outcome = run_backtest(
                    _slice_map(data_map, train_lo, train_hi),
                    _slice_signals(train_signals, train_lo, train_hi),
                    **backtest_kwargs,
                )
                if "error" in outcome:
                    continue
                score = outcome["metrics"].get(metric_key)
                if score is not None and (best_score is None or score > best_score):
                    best_score, chosen = score, params
            if chosen:
                param_votes[json.dumps(chosen, sort_keys=True)] += 1

        # 测试窗评估：信号用完整历史生成（回看窗口完整），评估只取测试窗
        test_signals = factory(**chosen).generate(_slice_map(data_map, dates[0], test_hi))
        outcome = run_backtest(
            _slice_map(data_map, test_lo, test_hi),
            _slice_signals(test_signals, test_lo, test_hi),
            **backtest_kwargs,
        )
        if "error" in outcome:
            windows.append({
                "train": f"{train_lo.date()}~{train_hi.date()}",
                "test": f"{test_lo.date()}~{test_hi.date()}",
                "params": chosen,
                "error": outcome["error"],
            })
        else:
            test_return = float(outcome["metrics"].get("total_return_pct") or 0.0)
            equity *= 1.0 + test_return / 100.0
            windows.append({
                "train": f"{train_lo.date()}~{train_hi.date()}",
                "test": f"{test_lo.date()}~{test_hi.date()}",
                "params": chosen,
                "test_return_pct": round(test_return, 2),
                **{key: outcome["metrics"].get(key) for key in ("sharpe_ratio", "max_drawdown_pct", "trade_count")},
            })
        start += test_bars

    evaluated = [w for w in windows if "test_return_pct" in w]
    total_return = (equity - 1.0) * 100
    stability = [
        {"params": json.loads(params_json), "times": times}
        for params_json, times in param_votes.most_common()
    ]
    return {
        "walk_forward": {
            "train_bars": train_bars,
            "test_bars": test_bars,
            "metric_key": metric_key,
            "windows": len(windows),
            "evaluated": len(evaluated),
            "oos_total_return_pct": round(total_return, 2),
            "win_windows": sum(1 for w in evaluated if w["test_return_pct"] > 0),
            "param_stability": stability,
            "backtest_kwargs": backtest_kwargs,
        },
        "windows": windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward 滚动验证（冒烟 CLI）")
    parser.add_argument("--strategy", default="dual_ma", choices=["dual_ma", "rsi", "macd"])
    parser.add_argument("--grid", default='{"short_window":[3,5],"long_window":[10,20]}')
    parser.add_argument("--train", type=int, default=120)
    parser.add_argument("--test", type=int, default=20)
    args = parser.parse_args()

    result = run_walk_forward(
        args.strategy,
        json.loads(args.grid),
        _demo_data(),
        train_bars=args.train,
        test_bars=args.test,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
