#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
融资追踪策略选股运行脚本

策略特点：
  - 追踪融资买入趋势与融资余额增长情况
  - 筛选资金持续流入、机构增仓迹象明显的标的
  - 适合中线布局，捕捉资金驱动行情

用法：
  python scripts/run_fund_flow_tracking.py [选项]

选项：
  --limit                 N   返回股票数量（默认 20）
  --market-cap          TYPE  市值范围：large / mid / small / all（默认 all）
  --stock-pool          TYPE  股票池：all / main / gem / star（默认 all）
  --margin-buy-trend    NUM   融资买入趋势最小值（默认 50.0）
  --margin-bal-growth   NUM   融资余额增长最小值（默认 50.0）
  --output              FILE  结果保存到文件（可选，csv 格式）
"""

import sys
import os
import asyncio
import argparse
import csv
from datetime import datetime

# ── 路径设置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(SCRIPT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
# ─────────────────────────────────────────────────────────

from backtrader_strategies.strategy_adapters.fund_flow_tracking_adapter import FundFlowTrackingAdapter


def print_header(strategy_name: str, params: dict):
    print("\n" + "=" * 65)
    print(f"  策略：{strategy_name}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  参数：融资买入趋势≥{params.get('margin_buy_trend_min')}  "
          f"融资余额增长≥{params.get('margin_balance_growth_min')}")
    print("=" * 65)


def print_results(result: dict):
    if result.get('error'):
        print(f"\n❌ 选股失败：{result['error']}")
        return

    stocks = result.get('stocks', [])
    total = result.get('total_count', 0)
    print(f"\n共筛选出 {total} 只股票（显示全部）：\n")

    if not stocks:
        print("  暂无符合条件的股票")
        return

    col_w = [6, 10, 8, 8, 10, 10, 8]
    headers = ["排名", "代码", "名称", "综合分", "融资买入趋势", "融资余额增长", "涨跌幅%"]
    print("  " + "  ".join(h.ljust(col_w[i]) for i, h in enumerate(headers)))
    print("  " + "-" * 74)

    for idx, s in enumerate(stocks, 1):
        def _f(v, fmt='.2f'):
            return format(v, fmt) if isinstance(v, (int, float)) else '--'

        row = [
            str(idx),
            s.get('ts_code', '--'),
            (s.get('name', '--'))[:4],
            _f(s.get('total_score', s.get('score'))),
            _f(s.get('margin_buy_trend', s.get('buy_trend'))),
            _f(s.get('margin_balance_growth', s.get('bal_growth'))),
            _f(s.get('pct_chg'), '.2f'),
        ]
        print("  " + "  ".join(str(v).ljust(col_w[i]) for i, v in enumerate(row)))

    print()


def save_to_csv(result: dict, filepath: str):
    stocks = result.get('stocks', [])
    if not stocks:
        print("  无数据，跳过保存")
        return
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(stocks[0].keys()))
        writer.writeheader()
        writer.writerows(stocks)
    print(f"  结果已保存至：{filepath}")


async def main():
    parser = argparse.ArgumentParser(description='融资追踪策略选股')
    parser.add_argument('--limit',             type=int,   default=20,   help='返回股票数量')
    parser.add_argument('--top',                type=int,   default=None,  help='返回前N只（--limit别名）')
    parser.add_argument('--market-cap',        type=str,   default='all', dest='market_cap',
                        choices=['all', 'large', 'mid', 'small'], help='市值范围')
    parser.add_argument('--stock-pool',        type=str,   default='all', dest='stock_pool',
                        choices=['all', 'main', 'gem', 'star'],   help='股票池')
    parser.add_argument('--pool',              type=str,   default=None, dest='pool_alias',
                        choices=['all', 'hs300', 'zz500', 'zz1000'], help='股票池(简写)')
    parser.add_argument('--margin-buy-trend',  type=float, default=50.0, dest='margin_buy_trend_min',
                        help='融资买入趋势最小值（默认 50.0）')
    parser.add_argument('--margin-bal-growth', type=float, default=50.0, dest='margin_balance_growth_min',
                        help='融资余额增长最小值（默认 50.0）')
    parser.add_argument('--output',            type=str,   default=None, help='结果保存路径（csv）')
    parser.add_argument('--json',              action='store_true', default=False, help='输出JSON格式')
    args = parser.parse_args()

    # 参数映射
    limit = args.top or args.limit
    stock_pool = args.pool_alias or args.stock_pool

    params = {
        'margin_buy_trend_min': args.margin_buy_trend_min,
        'margin_balance_growth_min': args.margin_balance_growth_min,
    }
    print_header("融资追踪策略", params)

    adapter = FundFlowTrackingAdapter()
    result = await adapter.screen_stocks(
        market_cap=args.market_cap,
        stock_pool=stock_pool,
        limit=limit,
        margin_buy_trend_min=args.margin_buy_trend_min,
        margin_balance_growth_min=args.margin_balance_growth_min,
    )

    if args.json:
        import json as _json
        print(_json.dumps(result, ensure_ascii=False, default=str))
        return result

    print_results(result)

    if args.output:
        save_to_csv(result, args.output)

    return result


if __name__ == '__main__':
    asyncio.run(main())
