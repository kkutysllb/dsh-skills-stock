#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高股息策略选股运行脚本

策略特点：
  - 寻找高股息收益、分红稳定的优质股票
  - 综合股息率、分红持续性、现金流质量评分
  - 适合稳健收益型投资

用法：
  python scripts/run_high_dividend.py [选项]

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

from backtrader_strategies.strategy_adapters.high_dividend_adapter import HighDividendAdapter


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

    col_w = [6, 10, 8, 8, 8, 7, 8, 7]
    headers = ["排名", "代码", "名称", "综合分", "股息分", "股息率%", "市值(亿)", "涨跌幅%"]
    print("  " + "  ".join(h.ljust(col_w[i]) for i, h in enumerate(headers)))
    print("  " + "-" * 72)

    for idx, s in enumerate(stocks, 1):
        def _f(v, fmt='.2f'):
            return format(v, fmt) if isinstance(v, (int, float)) else '--'

        row = [
            str(idx),
            s.get('ts_code', '--'),
            (s.get('name', '--'))[:4],
            _f(s.get('total_score', s.get('score')), '.1f'),
            _f(s.get('dividend_score'), '.1f'),
            _f(s.get('dv_ratio', s.get('dv_ttm'))),
            _f(s.get('total_mv', 0) / 10000, '.1f') if isinstance(s.get('total_mv'), (int, float)) else '--',
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
    parser = argparse.ArgumentParser(description='高股息策略选股')
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
    print_header("高股息策略", params)

    adapter = HighDividendAdapter()
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
