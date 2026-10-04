#!/usr/bin/env python3
"""
期权波动率分析 CLI

支持四种模式：
1. realized-vol — 从价格序列计算实现波动率
2. iv-rv        — IV vs RV 对比分析
3. surface      — 波动率曲面摘要
4. regime       — 波动率环境判断
5. full         — 完整分析（需价格数据 + IV）

使用方式:
  python3 analyze_option_volatility.py --action realized-vol --prices 100,101,102,...
  python3 analyze_option_volatility.py --action iv-rv --iv 0.25 --rv-20d 0.18
  python3 analyze_option_volatility.py --action surface --atm-1m 0.22 --atm-3m 0.24
  python3 analyze_option_volatility.py --action regime --iv-current 0.25 --iv-52w-low 0.15 --iv-52w-high 0.40
  python3 analyze_option_volatility.py --action full --prices 100,101,... --iv 0.25
"""

import argparse
import json
import os
import sys

import numpy as np

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_analysis_dir = os.path.join(_project_root, 'analysis')
if _analysis_dir not in sys.path:
    sys.path.insert(0, _analysis_dir)

from realized_vol import multi_window_vol
from vol_engine import iv_rv_comparison, vol_surface_summary, vol_regime, full_analysis


def action_realized_vol(args):
    """实现波动率计算"""
    if args.csv:
        import pandas as pd
        df = pd.read_csv(args.csv)
        price_col = args.price_col or 'close'
        prices = df[price_col].values.astype(float)
    elif args.prices:
        prices = np.array([float(p) for p in args.prices.split(',')])
    else:
        return {"error": "需要 --csv 或 --prices 参数"}

    return {"action": "realized-vol", "data_points": len(prices), **multi_window_vol(prices)}


def action_iv_rv(args):
    """IV vs RV 对比"""
    return {
        "action": "iv-rv",
        **iv_rv_comparison(
            iv=args.iv,
            rv_20d=args.rv_20d,
            rv_60d=args.rv_60d,
            rv_90d=args.rv_90d,
            rv_252d=args.rv_252d,
        ),
    }


def action_surface(args):
    """波动率曲面摘要"""
    atm_vols = {}
    rr_vols = {}
    bf_vols = {}

    for tenor in ['1m', '3m', '6m', '1y']:
        atm_val = getattr(args, f'atm_{tenor}', None)
        if atm_val is not None:
            atm_vols[tenor.upper()] = atm_val
        rr_val = getattr(args, f'rr_{tenor}', None)
        if rr_val is not None:
            rr_vols[tenor.upper()] = rr_val
        bf_val = getattr(args, f'bf_{tenor}', None)
        if bf_val is not None:
            bf_vols[tenor.upper()] = bf_val

    if not atm_vols:
        return {"error": "需要至少一个 --atm-* 参数"}

    return {
        "action": "surface",
        **vol_surface_summary(atm_vols, rr_vols if rr_vols else None, bf_vols if bf_vols else None),
    }


def action_regime(args):
    """波动率环境判断"""
    iv_history = None
    if args.iv_history:
        iv_history = [float(v) for v in args.iv_history.split(',')]

    return {
        "action": "regime",
        **vol_regime(args.iv_current, args.iv_52w_low, args.iv_52w_high, iv_history),
    }


def action_full(args):
    """完整分析"""
    if args.csv:
        import pandas as pd
        df = pd.read_csv(args.csv)
        price_col = args.price_col or 'close'
        prices = df[price_col].values.astype(float)
    elif args.prices:
        prices = np.array([float(p) for p in args.prices.split(',')])
    else:
        return {"error": "需要 --csv 或 --prices 参数"}

    iv_history = None
    if args.iv_history:
        iv_history = [float(v) for v in args.iv_history.split(',')]

    return {
        "action": "full",
        **full_analysis(
            prices=prices,
            iv=args.iv,
            iv_52w_low=args.iv_52w_low,
            iv_52w_high=args.iv_52w_high,
            iv_history=iv_history,
        ),
    }


def print_realized_vol(result):
    print(f"\n## 实现波动率\n")
    print(f"**数据点数:** {result.get('data_points', 'N/A')}\n")
    print(f"| 窗口 | 年化波动率 |")
    print(f"|------|-----------|")
    for key in ['20d', '60d', '90d', '252d']:
        if key in result:
            d = result[key]
            vol_str = d.get('vol_pct', 'N/A')
            print(f"| {key} | **{vol_str}** |")
    print()


def print_iv_rv(result):
    print(f"\n## IV vs RV 对比分析\n")
    print(f"**当前 IV:** {result.get('iv_pct', 'N/A')}\n")
    print(f"| 窗口 | RV | IV | Spread | 溢价% | 信号 |")
    print(f"|------|-----|-----|--------|-------|------|")
    for c in result.get('comparisons', []):
        print(f"| {c['window']} | {c['rv_pct']} | {c['iv_pct']} | "
              f"{c['spread']:.4f} | {c['premium_pct']:.1f}% | {c['signal']} |")
    print(f"\n**综合判断:** {result.get('overall_signal', 'N/A')}\n")


def print_surface(result):
    print(f"\n## 波动率曲面摘要\n")
    print(f"**期限结构:** {result.get('term_structure', 'N/A')}\n")
    print(f"| Tenor | ATM Vol | 25d RR | 25d BF |")
    print(f"|-------|---------|--------|--------|")
    for s in result.get('surface', []):
        rr = s.get('rr_25d', '-')
        bf = s.get('bf_25d', '-')
        print(f"| {s['tenor']} | **{s['atm_vol_pct']}** | {rr} | {bf} |")
    r = result.get('atm_range', {})
    if r:
        print(f"\n**ATM Range:** {r.get('min', 'N/A')} ~ {r.get('max', 'N/A')}")
    print()


def print_regime(result):
    print(f"\n## 波动率环境判断\n")
    print(f"**当前 IV:** {result.get('iv_current_pct', 'N/A')}\n")
    print(f"| 指标 | 数值 |")
    print(f"|------|------|")
    print(f"| IV Rank | **{result.get('iv_rank', 'N/A')}** |")
    print(f"| IV Percentile | {result.get('iv_percentile', 'N/A')} |")
    r52 = result.get('iv_52w_range')
    if r52:
        print(f"| 52周区间 | {r52['low']} ~ {r52['high']} |")
    print(f"| 波动率环境 | **{result.get('regime', 'N/A')}** |")
    print(f"\n**策略建议:** {result.get('recommended_strategy', 'N/A')}\n")


def print_full(result):
    print(f"\n## 期权波动率完整分析\n")
    rv = result.get('realized_volatility', {})
    if rv:
        print(f"### 实现波动率\n")
        print(f"| 窗口 | 年化波动率 |")
        print(f"|------|-----------|")
        for key in ['20d', '60d', '90d', '252d']:
            if key in rv:
                print(f"| {key} | **{rv[key].get('vol_pct', 'N/A')}** |")
        print()

    iv_rv = result.get('iv_rv_comparison', {})
    if iv_rv:
        print(f"### IV vs RV\n")
        print(f"| 窗口 | RV | IV | 信号 |")
        print(f"|------|-----|-----|------|")
        for c in iv_rv.get('comparisons', []):
            print(f"| {c['window']} | {c['rv_pct']} | {c['iv_pct']} | {c['signal']} |")
        print(f"\n**综合:** {iv_rv.get('overall_signal', 'N/A')}\n")

    regime = result.get('vol_regime', {})
    if regime:
        print(f"### 波动率环境\n")
        print(f"- IV Rank: **{regime.get('iv_rank', 'N/A')}**")
        print(f"- 环境: **{regime.get('regime', 'N/A')}**")
        print(f"- 策略: {regime.get('recommended_strategy', 'N/A')}\n")


def main():
    parser = argparse.ArgumentParser(description="期权波动率分析工具")
    parser.add_argument('--action', choices=['realized-vol', 'iv-rv', 'surface', 'regime', 'full'],
                        required=True, help='分析模式')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')

    # 价格数据
    parser.add_argument('--prices', type=str, help='逗号分隔的价格序列')
    parser.add_argument('--csv', type=str, help='CSV 文件路径')
    parser.add_argument('--date-col', type=str, default='date', help='CSV 日期列名')
    parser.add_argument('--price-col', type=str, default='close', help='CSV 价格列名')

    # IV / RV
    parser.add_argument('--iv', type=float, help='隐含波动率')
    parser.add_argument('--rv-20d', type=float, help='20日实现波动率')
    parser.add_argument('--rv-60d', type=float, help='60日实现波动率')
    parser.add_argument('--rv-90d', type=float, help='90日实现波动率')
    parser.add_argument('--rv-252d', type=float, help='252日实现波动率')

    # 曲面
    for tenor in ['1m', '3m', '6m', '1y']:
        parser.add_argument(f'--atm-{tenor}', type=float, help=f'ATM Vol {tenor}')
        parser.add_argument(f'--rr-{tenor}', type=float, help=f'25d RR {tenor}')
        parser.add_argument(f'--bf-{tenor}', type=float, help=f'25d BF {tenor}')

    # 环境
    parser.add_argument('--iv-current', type=float, help='当前 IV')
    parser.add_argument('--iv-52w-low', type=float, help='52周 IV 最低')
    parser.add_argument('--iv-52w-high', type=float, help='52周 IV 最高')
    parser.add_argument('--iv-history', type=str, help='逗号分隔的历史IV序列')

    args = parser.parse_args()

    try:
        if args.action == 'realized-vol':
            result = action_realized_vol(args)
        elif args.action == 'iv-rv':
            result = action_iv_rv(args)
        elif args.action == 'surface':
            result = action_surface(args)
        elif args.action == 'regime':
            result = action_regime(args)
        else:
            result = action_full(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        printers = {
            'realized-vol': print_realized_vol,
            'iv-rv': print_iv_rv,
            'surface': print_surface,
            'regime': print_regime,
            'full': print_full,
        }
        printers[args.action](result)


if __name__ == '__main__':
    main()
