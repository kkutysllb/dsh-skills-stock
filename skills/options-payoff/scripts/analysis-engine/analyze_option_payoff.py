#!/usr/bin/env python3
"""
期权盈亏分析 CLI

支持三种模式：
1. price  — Black-Scholes 定价 + Greeks
2. iv     — 隐含波动率反解
3. payoff — 多腿组合盈亏分析

使用方式:
  python3 analyze_option_payoff.py --action price --type call --S 100 --K 100 --T 0.25 --r 0.03 --sigma 0.20
  python3 analyze_option_payoff.py --action iv --type call --S 100 --K 100 --T 0.25 --r 0.03 --price 5.0
  python3 analyze_option_payoff.py --action payoff --legs "call,long,100,1,3.5,0.25,0.20" "put,long,100,1,2.8,0.25,0.20" --S 100
"""

import argparse
import json
import os
import sys

# 添加 analysis 目录到 Python 路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_analysis_dir = os.path.join(_project_root, 'analysis')
if _analysis_dir not in sys.path:
    sys.path.insert(0, _analysis_dir)

from bs_model import bs_price, bs_greeks, implied_volatility, put_call_parity_check
from payoff_engine import OptionLeg, analyze_payoff


def parse_leg(leg_str: str) -> OptionLeg:
    """解析腿定义字符串。

    格式: type,direction,strike,quantity,premium,T,sigma
    示例: call,long,100,1,3.5,0.25,0.20
    """
    parts = leg_str.split(',')
    if len(parts) != 7:
        raise ValueError(f"腿定义需要 7 个字段，得到 {len(parts)}: {leg_str}")

    option_type = parts[0].strip().lower()
    direction_str = parts[1].strip().lower()
    K = float(parts[2])
    quantity = float(parts[3])
    premium = float(parts[4])
    T = float(parts[5])
    sigma = float(parts[6])

    if option_type not in ('call', 'put'):
        raise ValueError(f"option_type 必须为 call/put: {option_type}")
    direction = 1 if direction_str == 'long' else -1

    return OptionLeg(
        option_type=option_type,
        K=K,
        direction=direction,
        quantity=quantity,
        premium=premium,
        T=T,
        sigma=sigma,
    )


def action_price(args):
    """BS 定价 + Greeks"""
    result = {
        "action": "price",
        "params": {
            "S": args.S, "K": args.K, "T": args.T,
            "r": args.r, "sigma": args.sigma,
            "type": args.type, "q": args.q,
        },
    }

    price = bs_price(args.S, args.K, args.T, args.r, args.sigma, args.type, args.q)
    greeks = bs_greeks(args.S, args.K, args.T, args.r, args.sigma, args.type, args.q)

    result["price"] = round(price, 6)
    result["greeks"] = greeks

    # 内含价值 + 时间价值
    intrinsic = max(0, args.S - args.K if args.type == 'call' else args.K - args.S)
    result["intrinsic"] = round(intrinsic, 6)
    result["time_value"] = round(price - intrinsic, 6)

    # Put-Call Parity（同时计算对面）
    if args.type == 'call':
        put_price = bs_price(args.S, args.K, args.T, args.r, args.sigma, 'put', args.q)
    else:
        put_price = price
        price_call = bs_price(args.S, args.K, args.T, args.r, args.sigma, 'call', args.q)
        put_price, price_call = put_price, price_call  # reassign for parity

    parity = put_call_parity_check(
        price_call if args.type == 'put' else price,
        put_price if args.type == 'call' else price,
        args.S, args.K, args.T, args.r, args.q,
    )
    result["put_call_parity"] = parity

    return result


def action_iv(args):
    """隐含波动率反解"""
    result = {
        "action": "iv",
        "params": {
            "S": args.S, "K": args.K, "T": args.T,
            "r": args.r, "market_price": args.price,
            "type": args.type, "q": args.q,
        },
    }

    try:
        iv = implied_volatility(args.price, args.S, args.K, args.T, args.r, args.type, args.q)
        result["implied_volatility"] = None if (isinstance(iv, float) and iv != iv) else round(iv, 6)
        result["implied_volatility_pct"] = f"{iv * 100:.2f}%" if iv == iv else "N/A"

        # 用 IV 反算价格验证
        if iv == iv:
            verify_price = bs_price(args.S, args.K, args.T, args.r, iv, args.type, args.q)
            result["verify_price"] = round(verify_price, 6)
            result["verify_diff"] = round(abs(verify_price - args.price), 8)
    except ValueError as e:
        result["error"] = str(e)

    return result


def action_payoff(args):
    """多腿组合盈亏分析"""
    legs = [parse_leg(l) for l in args.legs]
    result = analyze_payoff(legs, args.S, args.r, args.q)
    result["action"] = "payoff"
    return result


def print_price_result(result):
    """格式化打印定价结果"""
    p = result["params"]
    print(f"\n## Black-Scholes 期权定价\n")
    print(f"**标的现价:** {p['S']}  **行权价:** {p['K']}  **到期:** {p['T']}年 ({p['T']*365:.0f}天)")
    print(f"**无风险利率:** {p['r']*100:.1f}%  **波动率:** {p['sigma']*100:.1f}%  **类型:** {p['type'].upper()}")
    if p['q'] > 0:
        print(f"**股息率:** {p['q']*100:.1f}%")
    print()
    print(f"### 定价结果\n")
    print(f"| 指标 | 数值 |")
    print(f"|------|------|")
    print(f"| 理论价格 | **{result['price']:.4f}** |")
    print(f"| 内含价值 | {result['intrinsic']:.4f} |")
    print(f"| 时间价值 | {result['time_value']:.4f} |")
    print()
    print(f"### Greeks\n")
    print(f"| Greek | 数值 | 说明 |")
    print(f"|-------|------|------|")
    g = result['greeks']
    print(f"| Delta | {g['delta']:.6f} | 价格敏感度 |")
    print(f"| Gamma | {g['gamma']:.6f} | Delta变化率 |")
    print(f"| Theta | {g['theta']:.6f} | 每日时间衰减 |")
    print(f"| Vega | {g['vega']:.6f} | 每1%vol变化 |")
    print(f"| Rho | {g['rho']:.6f} | 每1%利率变化 |")
    print()

    parity = result.get('put_call_parity', {})
    if parity:
        print(f"### Put-Call Parity 验证\n")
        print(f"| 项目 | 数值 |")
        print(f"|------|------|")
        print(f"| 理论价差(C-P) | {parity['parity_theoretical']:.6f} |")
        print(f"| 实际价差 | {parity['parity_actual']:.6f} |")
        print(f"| 偏差 | {parity['deviation']:.6f} |")
        print(f"| 验证 | {'✓ 通过' if parity['is_valid'] else '✗ 异常'} |")


def print_iv_result(result):
    """格式化打印 IV 结果"""
    p = result["params"]
    print(f"\n## 隐含波动率反解\n")
    print(f"**标的现价:** {p['S']}  **行权价:** {p['K']}  **到期:** {p['T']}年")
    print(f"**市场价格:** {p['market_price']}  **类型:** {p['type'].upper()}")
    print()
    iv = result.get('implied_volatility')
    if iv is not None:
        print(f"| 指标 | 数值 |")
        print(f"|------|------|")
        print(f"| 隐含波动率 | **{iv:.4f}** ({result['implied_volatility_pct']}) |")
        if 'verify_price' in result:
            print(f"| 反验价格 | {result['verify_price']:.6f} |")
            print(f"| 验证偏差 | {result['verify_diff']:.8f} |")
    else:
        print(f"**结果:** 未收敛")
    print()


def print_payoff_result(result):
    """格式化打印盈亏分析结果"""
    p = result["params"]
    print(f"\n## 多腿期权组合盈亏分析\n")

    # 腿信息
    print(f"### 组合构成\n")
    print(f"| # | 类型 | 方向 | 行权价 | 数量 | 权利金 | T(年) | σ |")
    print(f"|---|------|------|--------|------|--------|-------|---|")
    for i, leg in enumerate(result["legs"], 1):
        print(f"| {i} | {leg['type'].upper()} | {leg['direction']} | {leg['strike']} | "
              f"{leg['quantity']} | {leg['premium']} | {leg['T']} | {leg['sigma']} |")

    print(f"\n**标的现价:** {p['S_current']}  **利率:** {p['r']*100:.1f}%")

    # 盈亏摘要
    print(f"\n### 盈亏摘要\n")
    print(f"| 指标 | 数值 |")
    print(f"|------|------|")
    print(f"| 最大盈利 | **{result['max_profit']}** |")
    print(f"| 最大亏损 | **{result['max_loss']}** |")

    beps = result["breakeven_points"]
    if beps:
        bep_str = ", ".join([str(b) for b in beps])
    else:
        bep_str = "无"
    print(f"| 盈亏平衡点 | {bep_str} |")
    print(f"| 当前理论盈亏 | {result['current_theo_pnl']} |")
    print(f"| 到期盈亏(当前价) | {result['current_expiry_pnl']} |")

    if result.get("profit_range"):
        pr = result["profit_range"]
        print(f"| 盈利区间 | [{pr[0]}, {pr[1]}] |")

    # 波动率情景
    scenarios = result.get("volatility_scenarios", {})
    if scenarios:
        print(f"\n### 波动率情景分析\n")
        print(f"| 情景 | σ | 倍数 | 理论盈亏(中间价) |")
        print(f"|------|---|------|-----------------|")
        for name, sc in scenarios.items():
            print(f"| {name} | {sc['sigma']:.4f} | {sc['multiplier']}x | {sc['pnl_at_current']} |")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="期权盈亏分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--action', choices=['price', 'iv', 'payoff'], required=True,
                        help='分析模式: price(定价) / iv(隐含波动率) / payoff(盈亏分析)')
    parser.add_argument('--type', choices=['call', 'put'], default='call',
                        help='期权类型 (默认: call)')
    parser.add_argument('--S', type=float, default=100.0, help='标的现价 (默认: 100)')
    parser.add_argument('--K', type=float, default=100.0, help='行权价 (默认: 100)')
    parser.add_argument('--T', type=float, default=0.25, help='到期时间/年 (默认: 0.25)')
    parser.add_argument('--r', type=float, default=0.03, help='无风险利率 (默认: 0.03)')
    parser.add_argument('--sigma', type=float, default=0.20, help='波动率 (默认: 0.20)')
    parser.add_argument('--q', type=float, default=0.0, help='连续股息率 (默认: 0)')
    parser.add_argument('--price', type=float, help='市场价格（iv 模式必填）')
    parser.add_argument('--legs', nargs='+', help='多腿定义（payoff 模式必填）')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')

    args = parser.parse_args()

    # 参数校验
    if args.action == 'iv' and args.price is None:
        parser.error("--action iv 需要 --price 参数")
    if args.action == 'payoff' and not args.legs:
        parser.error("--action payoff 需要 --legs 参数")

    # 执行分析
    try:
        if args.action == 'price':
            result = action_price(args)
        elif args.action == 'iv':
            result = action_iv(args)
        else:
            result = action_payoff(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    # 输出
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        if args.action == 'price':
            print_price_result(result)
        elif args.action == 'iv':
            print_iv_result(result)
        else:
            print_payoff_result(result)


if __name__ == '__main__':
    main()
