#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成长股策略选股运行脚本

策略特点：
  - 寻找高成长性、高盈利能力的成长股
  - EPS / 营收增速双驱动，PEG 0.2~1.5
  - 分级筛选：成长性(40%) + 盈利能力(35%) + 创新投入(15%) + 财务安全(10%)
  - 适合中长线成长投资

用法：
  python scripts/run_growth_stock.py [选项]

选项：
  --limit      N     返回股票数量（默认 20）
  --market-cap TYPE  市值范围：large / mid / small / all（默认 all）
  --stock-pool TYPE  股票池：all / main / gem / star（默认 all）
  --output     FILE  结果保存到文件（可选，csv 格式）
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

from backtrader_strategies.strategy_adapters.growth_stock_adapter import GrowthStockAdapter


def print_header(strategy_name: str, params: dict):
    print("\n" + "=" * 65)
    print(f"  策略：{strategy_name}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  参数：市值范围={params.get('market_cap')}  股票池={params.get('stock_pool')}  数量限制={params.get('limit')}")
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

    col_w = [6, 10, 8, 8, 8, 8, 8, 8]
    headers = ["排名", "代码", "名称", "综合分", "成长分", "盈利分", "EPS增速%", "营收增速%"]
    print("  " + "  ".join(h.ljust(col_w[i]) for i, h in enumerate(headers)))
    print("  " + "-" * 72)

    for idx, s in enumerate(stocks, 1):
        def _f(v, fmt='.1f'):
            return format(v, fmt) if isinstance(v, (int, float)) else '--'

        row = [
            str(idx),
            s.get('ts_code', '--'),
            (s.get('name', '--'))[:4],
            _f(s.get('total_score', s.get('score'))),
            _f(s.get('growth_score')),
            _f(s.get('profitability_score')),
            _f(s.get('eps_yoy')),
            _f(s.get('revenue_yoy')),
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
    parser = argparse.ArgumentParser(description='成长股策略选股')
    parser.add_argument('--limit',      type=int,   default=20,    help='返回股票数量')
    parser.add_argument('--top',        type=int,   default=None,  help='返回前N只（--limit别名）')
    parser.add_argument('--market-cap', type=str,   default='all', dest='market_cap',
                        choices=['all', 'large', 'mid', 'small'], help='市值范围')
    parser.add_argument('--stock-pool', type=str,   default='all', dest='stock_pool',
                        choices=['all', 'main', 'gem', 'star'],   help='股票池')
    parser.add_argument('--pool',       type=str,   default=None, dest='pool_alias',
                        choices=['all', 'hs300', 'zz500', 'zz1000'], help='股票池(简写)')
    parser.add_argument('--output',     type=str,   default=None,  help='结果保存路径（csv）')
    parser.add_argument('--json',       action='store_true', default=False, help='输出JSON格式')
    args = parser.parse_args()

    # 参数映射
    limit = args.top or args.limit
    stock_pool = args.pool_alias or args.stock_pool

    params = {'market_cap': args.market_cap, 'stock_pool': stock_pool, 'limit': limit}
    print_header("成长股策略", params)

    adapter = GrowthStockAdapter()
    result = await adapter.screen_stocks(
        market_cap=args.market_cap,
        stock_pool=stock_pool,
        limit=limit
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
