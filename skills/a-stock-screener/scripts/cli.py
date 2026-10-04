#!/usr/bin/env python3
"""a-stock-screener 命令行入口：自然语言选股。

用法:
    python3 cli.py --query "高股息低估蓝筹股" --top 10
    python3 cli.py --query "创业板成长股" --top 20 --mock   # 无网络冒烟

数据源: 问财（IWENCAI_API_KEY）优先，Tushare 兜底；--mock 走内置伪数据。
输出: Top-N 选股结果（代码/名称/价格/得分/关键信号）。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, List, Optional, Tuple

from workflow_engine import FetchStep, ScreeningEngine, Strategy
from data_adapter import DataAdapter, get_data_adapter
from ranking import DataRankStep

logger = logging.getLogger(__name__)


class DataFetchStep(FetchStep):
    """真实数据获取：问财自然语言查询 → 候选股列表（dict records）。"""

    def __init__(self, adapter: Optional[DataAdapter] = None, limit: int = 100, mock_mode: bool = False):
        super().__init__()
        self._adapter = adapter
        self._limit = limit
        self._mock_mode = mock_mode

    def execute(self, strategies: List[Tuple[Strategy, dict]], context: dict) -> List[dict]:
        query = context.get("query", "")
        adapter = self._adapter or get_data_adapter(mock_mode=self._mock_mode)
        df = adapter.query_stocks(query, limit=self._limit)
        if df is None or df.empty:
            logger.warning("query_stocks 返回空，候选为空")
            return []
        records = df.to_dict("records")
        # 统一字段名（问财可能返回 ts_code/name，也可能是中文列名）
        normalized = []
        for rec in records:
            norm = {}
            for k, v in rec.items():
                if k in ("股票代码", "code", "ts_code"):
                    norm["ts_code"] = v
                elif k in ("股票简称", "name"):
                    norm["name"] = v
                elif k in ("最新价", "close"):
                    norm["close"] = v
                elif k in ("最新涨跌幅", "涨跌幅", "pct_chg"):
                    norm["pct_chg"] = v
                elif k in ("最新市盈率ttm", "市盈率TTM", "pe_ttm"):
                    norm["pe_ttm"] = v
                elif k in ("最新市净率", "市净率", "pb"):
                    norm["pb"] = v
                elif k in ("最新a股流通市值", "total_mv"):
                    norm["total_mv"] = v
                else:
                    norm[k] = v
            normalized.append(norm)
        return normalized


def main() -> int:
    ap = argparse.ArgumentParser(description="A 股对话式选股（a-stock-screener）")
    ap.add_argument("--query", required=True, help="自然语言选股条件，如 '高股息低估蓝筹股'")
    ap.add_argument("--top", type=int, default=10, help="返回 Top-N（默认 10）")
    ap.add_argument("--mock", action="store_true", help="Mock 模式（无网络，内置伪数据）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    context: dict[str, Any] = {"query": args.query, "top_n": args.top}
    engine = ScreeningEngine(
        fetch_step=DataFetchStep(limit=max(args.top * 10, 100), mock_mode=args.mock),
        rank_step=DataRankStep(top_n=args.top),
    )
    report = engine.run(args.query)

    if report.errors:
        print(f"错误: {report.errors}", file=sys.stderr)

    if args.json:
        payload = {
            "query": report.query,
            "strategies_used": report.strategies_used,
            "total_candidates": report.total_candidates,
            "top_results": [
                {
                    "code": r.code,
                    "name": r.name,
                    "price": r.price,
                    "change_pct": r.change_pct,
                    "total_score": r.total_score,
                    "scores": r.scores,
                    "signals": r.signals,
                }
                for r in report.top_results
            ],
            "elapsed_ms": report.elapsed_ms,
            "errors": report.errors,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"# 选股结果: {report.query}")
    print(f"策略: {', '.join(report.strategies_used) or '默认'} | 候选: {report.total_candidates} | 耗时: {report.elapsed_ms}ms")
    print()
    print(f"{'排名':<4}{'代码':<12}{'名称':<10}{'价格':>8}{'涨跌%':>8}{'总分':>8}")
    for r in report.top_results:
        print(f"{r.rank:<4}{r.code:<12}{r.name:<10}{r.price:>8.2f}{r.change_pct:>8.2f}{r.total_score:>8.2f}")
    if report.top_results:
        print("\n关键信号（第一只）:", json.dumps(report.top_results[0].signals, ensure_ascii=False))
    if report.errors:
        print("\n警告: 流程部分失败", file=sys.stderr)
    return 0 if not report.errors else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
