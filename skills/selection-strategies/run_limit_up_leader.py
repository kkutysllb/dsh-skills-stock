#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连板龙头策略选股运行脚本

策略特点：
  - 基于真实涨跌停数据分析连板股票
  - 筛选连续涨停次数 2~10 次、封板稳定的龙头品种
  - 适合短线强势股跟踪

用法：
  python scripts/run_limit_up_leader.py [选项]

选项：
  --limit             N   返回股票数量（默认 20）
  --market-cap      TYPE  市值范围：large / mid / small / all（默认 all）
  --stock-pool      TYPE  股票池：all / main / gem / star（默认 all）
  --min-limit-times   N   最少连板次数（默认 2）
  --max-limit-times   N   最多连板次数（默认 10）
  --max-open-times    N   最多炸板次数（默认 3）
  --output          FILE  结果保存到文件（可选，csv 格式）
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

from backtrader_strategies.strategy_adapters.limit_up_leader_adapter_simple import LimitUpLeaderAdapter


def print_header(strategy_name: str, params: dict):
    print("\n" + "=" * 65)
    print(f"  策略：{strategy_name}")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  参数：连板次数={params.get('min_limit_times')}~{params.get('max_limit_times')}  最多炸板={params.get('max_open_times')}")
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

    col_w = [6, 10, 8, 8, 6, 6, 8, 8]
    headers = ["排名", "代码", "名称", "综合分", "连板数", "炸板数", "换手率%", "涨跌幅%"]
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
            str(s.get('limit_times', s.get('up_stat', '--'))),
            str(s.get('open_times', '--')),
            _f(s.get('turnover_rate', s.get('turnover'))),
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
    parser = argparse.ArgumentParser(description='连板龙头策略选股')
    parser.add_argument('--limit',           type=int,   default=20,  help='返回股票数量')
    parser.add_argument('--top',              type=int,   default=None, help='返回前N只（--limit别名）')
    parser.add_argument('--market-cap',       type=str,   default='all', dest='market_cap',
                        choices=['all', 'large', 'mid', 'small'], help='市值范围')
    parser.add_argument('--stock-pool',       type=str,   default='all', dest='stock_pool',
                        choices=['all', 'main', 'gem', 'star'],   help='股票池')
    parser.add_argument('--pool',             type=str,   default=None, dest='pool_alias',
                        choices=['all', 'hs300', 'zz500', 'zz1000'], help='股票池(简写)')
    parser.add_argument('--min-limit-times',  type=int,   default=2,   dest='min_limit_times', help='最少连板次数')
    parser.add_argument('--max-limit-times',  type=int,   default=10,  dest='max_limit_times', help='最多连板次数')
    parser.add_argument('--max-open-times',   type=int,   default=3,   dest='max_open_times',  help='最多炸板次数')
    parser.add_argument('--output',           type=str,   default=None,                         help='结果保存路径（csv）')
    parser.add_argument('--json',             action='store_true', default=False, help='输出JSON格式')
    args = parser.parse_args()

    # 参数映射
    limit = args.top or args.limit
    stock_pool = args.pool_alias or args.stock_pool

    params = {
        'min_limit_times': args.min_limit_times,
        'max_limit_times': args.max_limit_times,
        'max_open_times': args.max_open_times,
    }
    print_header("连板龙头策略", params)

    adapter = LimitUpLeaderAdapter()
    result = await adapter.screen_stocks(
        market_cap=args.market_cap,
        stock_pool=stock_pool,
        limit=limit,
        min_limit_times=args.min_limit_times,
        max_limit_times=args.max_limit_times,
        max_open_times=args.max_open_times,
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
