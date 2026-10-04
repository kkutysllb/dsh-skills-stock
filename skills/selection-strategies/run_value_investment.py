#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
价值投资策略选股运行脚本

策略特点：
  - 寻找低估值、高ROE、稳定增长的优质股票
  - PE < 35, PB < 5, ROE >= 8%
  - 综合基本面评分筛选，适合长线价值投资

用法：
  python scripts/run_value_investment.py [选项]

选项：
  --limit      N     返回股票数量（默认 20）
  --market-cap TYPE  市值范围：large / mid / small / all（默认 all）
  --stock-pool TYPE  股票池：all / main / gem / star（默认 all）
  --date       DATE  指定交易日期 YYYYMMDD（默认最新交易日）
  --output     FILE  结果保存到文件（可选，csv 格式）
"""

import sys
import os
import asyncio
import argparse
import json
import csv
from datetime import datetime

# ── 路径设置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(SCRIPT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
# ─────────────────────────────────────────────────────────

from backtrader_strategies.strategy_adapters.value_investment_adapter import ValueInvestmentAdapter


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

    # 表头
    col_w = [6, 10, 8, 7, 7, 7, 7, 6, 8]
    headers = ["排名", "代码", "名称", "PE", "PB", "ROE%", "综合分", "市值(亿)", "涨跌幅%"]
    header_line = "  ".join(h.ljust(col_w[i]) for i, h in enumerate(headers))
    print("  " + header_line)
    print("  " + "-" * 75)

    for idx, s in enumerate(stocks, 1):
        row = [
            str(idx),
            s.get('ts_code', '--'),
            (s.get('name', '--'))[:4],
            f"{s.get('pe_ttm', s.get('pe', '--')):.1f}" if isinstance(s.get('pe_ttm', s.get('pe')), (int, float)) else '--',
            f"{s.get('pb', '--'):.2f}" if isinstance(s.get('pb'), (int, float)) else '--',
            f"{s.get('roe', '--'):.1f}" if isinstance(s.get('roe'), (int, float)) else '--',
            f"{s.get('total_score', s.get('score', '--')):.1f}" if isinstance(s.get('total_score', s.get('score')), (int, float)) else '--',
            f"{s.get('total_mv', '--')/10000:.1f}" if isinstance(s.get('total_mv'), (int, float)) else '--',
            f"{s.get('pct_chg', '--'):.2f}" if isinstance(s.get('pct_chg'), (int, float)) else '--',
        ]
        print("  " + "  ".join(str(v).ljust(col_w[i]) for i, v in enumerate(row)))

    print()


def save_to_csv(result: dict, filepath: str):
    stocks = result.get('stocks', [])
    if not stocks:
        print(f"  无数据，跳过保存")
        return
    keys = list(stocks[0].keys())
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(stocks)
    print(f"  结果已保存至：{filepath}")


async def main():
    parser = argparse.ArgumentParser(description='价值投资策略选股')
    parser.add_argument('--limit',      type=int,   default=20,    help='返回股票数量')
    parser.add_argument('--top',        type=int,   default=None,  help='返回前N只（--limit别名）')
    parser.add_argument('--market-cap', type=str,   default='all', dest='market_cap',
                        choices=['all', 'large', 'mid', 'small'], help='市值范围')
    parser.add_argument('--stock-pool', type=str,   default='all', dest='stock_pool',
                        choices=['all', 'main', 'gem', 'star'],   help='股票池')
    parser.add_argument('--pool',       type=str,   default=None, dest='pool_alias',
                        choices=['all', 'hs300', 'zz500', 'zz1000'], help='股票池(简写)')
    parser.add_argument('--date',       type=str,   default=None,  help='交易日期 YYYYMMDD')
    parser.add_argument('--output',     type=str,   default=None,  help='结果保存路径（csv）')
    parser.add_argument('--json',       action='store_true', default=False, help='输出JSON格式')
    args = parser.parse_args()

    # 参数映射
    limit = args.top or args.limit
    stock_pool = args.pool_alias or args.stock_pool

    params = {'market_cap': args.market_cap, 'stock_pool': stock_pool, 'limit': limit}
    print_header("价值投资策略", params)

    adapter = ValueInvestmentAdapter()
    result = await adapter.screen_stocks(
        trade_date=args.date,
        market_cap=args.market_cap,
        stock_pool=stock_pool,
        limit=limit
    )

    if args.json:
        # JSON 输出模式（供工具调用）
        print(json.dumps(result, ensure_ascii=False, default=str))
        return result

    print_results(result)

    if args.output:
        save_to_csv(result, args.output)

    return result


if __name__ == '__main__':
    asyncio.run(main())
