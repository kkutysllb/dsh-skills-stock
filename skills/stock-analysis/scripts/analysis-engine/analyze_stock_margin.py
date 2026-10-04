#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股融资融券分析脚本

通过 Tushare Pro API 的 margin_detail 接口获取个股融资融券数据，
分析融资/融券余额趋势、净流入方向、活跃度、波动率、风险评估等。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_margin.py --stock 000001.SZ --json
  python scripts/analyze_stock_margin.py --stock 600519.SH --days 60 --json
"""

import numpy as np  # KStock patch: 修复上游遗漏的 numpy 导入
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  Tushare 数据接口
# ======================================================================

def _get_tushare_api():
    from kk_common import get_finance_data_gateway
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, '.env'))
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN，请在 .env 中配置")
    return get_finance_data_gateway()


def _resolve_stock_code(ts_api, stock_input: str) -> str:
    """将用户输入的股票代码/名称解析为 ts_code 格式"""
    code = stock_input.strip()

    if '.' in code and len(code.split('.')[0]) == 6:
        return code

    if code.isdigit() and len(code) == 6:
        suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
        return code + suffix

    try:
        df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        match = df[df['name'] == code]
        if not match.empty:
            return match.iloc[0]['ts_code']
        match = df[df['name'].str.contains(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
    except Exception:
        pass

    suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
    return code + suffix


# ======================================================================
#  核心分析逻辑
# ======================================================================

def fetch_margin_data(ts_api, ts_code: str, days: int = 30) -> pd.DataFrame:
    """获取个股融资融券数据"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(days * 1.8))  # 多取一些确保交易日足够

    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')

    try:
        df = ts_api.margin_detail(
            ts_code=ts_code,
            start_date=start_str,
            end_date=end_str
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.sort_values('trade_date').reset_index(drop=True)
        # 只保留最近 days 天
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[错误] 获取融资融券数据失败: {e}", file=sys.stderr)
        return pd.DataFrame()


def calculate_trend(values) -> str:
    """计算趋势方向"""
    if len(values) < 2:
        return 'stable'
    x = np.arange(len(values))
    y = np.array(values, dtype=float)
    slope = np.polyfit(x, y, 1)[0]
    mean_val = np.mean(y)
    if mean_val == 0:
        return 'stable'
    relative_change = slope / mean_val
    if relative_change > 0.01:
        return 'increasing'
    elif relative_change < -0.01:
        return 'decreasing'
    return 'stable'


def calculate_volatility(values) -> float:
    """计算波动率"""
    if len(values) < 2:
        return 0.0
    arr = np.array(values, dtype=float)
    returns = []
    for i in range(1, len(arr)):
        if arr[i-1] != 0:
            returns.append((arr[i] - arr[i-1]) / arr[i-1])
    return float(np.std(returns)) if returns else 0.0


def analyze_margin(df: pd.DataFrame, ts_code: str, days: int) -> dict:
    """对融资融券数据进行综合分析"""
    if df.empty:
        return {
            "error": f"未找到 {ts_code} 近{days}天的融资融券数据",
            "ts_code": ts_code,
        }

    # 基础数据提取
    financing_balances = df['rzye'].astype(float).tolist()       # 融资余额
    securities_balances = df['rqye'].astype(float).tolist()      # 融券余额
    financing_buys = df['rzmre'].astype(float).tolist()          # 融资买入额
    financing_repays = df['rzche'].astype(float).tolist()        # 融资偿还额
    securities_sells = df['rqmcl'].astype(float).tolist()        # 融券卖出量
    securities_repays = df['rqchl'].astype(float).tolist()       # 融券偿还量

    # 日期序列
    trade_dates = df['trade_date'].tolist()
    latest = df.iloc[-1]

    # ── 1. 最新数据 ──
    latest_data = {
        "trade_date": latest['trade_date'],
        "rzye": float(latest['rzye']),             # 融资余额(元)
        "rqye": float(latest['rqye']),             # 融券余额(元)
        "rzrqye": float(latest.get('rzrqye', latest['rzye'] + latest['rqye'])),  # 融资融券余额
        "rzmre": float(latest['rzmre']),           # 融资买入额(元)
        "rzche": float(latest['rzche']),           # 融资偿还额(元)
        "rqmcl": float(latest['rqmcl']),           # 融券卖出量(股)
        "rqchl": float(latest['rqchl']),           # 融券偿还量(股)
    }

    # ── 2. 趋势分析 ──
    financing_trend = calculate_trend(financing_balances)
    securities_trend = calculate_trend(securities_balances)

    # ── 3. 净流入分析 ──
    # 融资净流入 = 融资买入额 - 融资偿还额
    financing_net_flows = [b - r for b, r in zip(financing_buys, financing_repays)]
    total_financing_net_flow = float(sum(financing_net_flows))
    # 融券净增量 = 融券卖出量 - 融券偿还量
    securities_net_flows = [s - r for s, r in zip(securities_sells, securities_repays)]
    total_securities_net_flow = float(sum(securities_net_flows))

    # ── 4. 活跃度分析 ──
    avg_financing_buy = float(np.mean(financing_buys))
    avg_financing_repay = float(np.mean(financing_repays))
    avg_securities_sell = float(np.mean(securities_sells))
    avg_securities_repay = float(np.mean(securities_repays))

    # 融资周转率 = 平均融资买入额 / 平均融资余额
    avg_financing_balance = float(np.mean(financing_balances))
    avg_securities_balance = float(np.mean(securities_balances))
    financing_turnover_ratio = float(avg_financing_buy / avg_financing_balance) if avg_financing_balance > 0 else 0
    securities_turnover_ratio = float(avg_securities_sell / avg_securities_balance) if avg_securities_balance > 0 else 0

    # ── 5. 波动率分析 ──
    financing_volatility = calculate_volatility(financing_balances)
    securities_volatility = calculate_volatility(securities_balances)

    # ── 6. 变化率分析（近5日 vs 前期） ──
    if len(financing_balances) >= 5:
        recent_5d_rzye = financing_balances[-5:]
        prev_rzye = financing_balances[:-5] if len(financing_balances) > 5 else financing_balances[:1]
        rzye_change_pct = float((np.mean(recent_5d_rzye) - np.mean(prev_rzye)) / np.mean(prev_rzye) * 100) if np.mean(prev_rzye) != 0 else 0

        recent_5d_rqye = securities_balances[-5:]
        prev_rqye = securities_balances[:-5] if len(securities_balances) > 5 else securities_balances[:1]
        rqye_change_pct = float((np.mean(recent_5d_rqye) - np.mean(prev_rqye)) / np.mean(prev_rqye) * 100) if np.mean(prev_rqye) != 0 else 0
    else:
        rzye_change_pct = 0.0
        rqye_change_pct = 0.0

    # ── 7. 风险评估 ──
    risk_factors = []
    risk_score = 0

    if financing_volatility > 0.1:
        risk_factors.append("融资余额波动较大")
        risk_score += 30
    if securities_volatility > 0.15:
        risk_factors.append("融券余额波动较大")
        risk_score += 20
    if total_financing_net_flow < 0 and abs(total_financing_net_flow) > 1e8:
        risk_factors.append("融资大额净流出")
        risk_score += 25
    if total_securities_net_flow > 0 and abs(total_securities_net_flow) > 1e6:
        risk_factors.append("融券大额净增加")
        risk_score += 25

    if risk_score >= 50:
        risk_level = 'high'
    elif risk_score >= 25:
        risk_level = 'medium'
    else:
        risk_level = 'low'

    # ── 8. 综合评分 ──
    score = 50
    if financing_trend == 'increasing':
        score += 15
    elif financing_trend == 'decreasing':
        score -= 10
    if securities_trend == 'decreasing':
        score += 10
    elif securities_trend == 'increasing':
        score -= 15
    if total_financing_net_flow > 0:
        score += 15
    else:
        score -= 10
    if total_securities_net_flow < 0:
        score += 10
    else:
        score -= 10
    if risk_level == 'low':
        score += 10
    elif risk_level == 'high':
        score -= 20

    score = max(0, min(100, score))

    if score >= 70:
        recommendation = 'bullish'
    elif score <= 30:
        recommendation = 'bearish'
    else:
        recommendation = 'neutral'

    # ── 9. 时间序列（供前端图表） ──
    time_series = []
    for _, row in df.iterrows():
        rz_net = float(row['rzmre']) - float(row['rzche'])
        rq_net = float(row['rqmcl']) - float(row['rqchl'])
        time_series.append({
            "trade_date": row['trade_date'],
            "rzye": float(row['rzye']),
            "rqye": float(row['rqye']),
            "rzrqye": float(row.get('rzrqye', float(row['rzye']) + float(row['rqye']))),
            "rzmre": float(row['rzmre']),
            "rzche": float(row['rzche']),
            "rqmcl": float(row['rqmcl']),
            "rqchl": float(row['rqchl']),
            "rz_net_flow": rz_net,
            "rq_net_flow": rq_net,
        })

    return {
        "ts_code": ts_code,
        "analysis_period": f"{trade_dates[0]} 至 {trade_dates[-1]}",
        "data_count": len(df),
        "days": days,

        # 最新数据
        "latest_data": latest_data,

        # 趋势分析
        "financing_trend": financing_trend,
        "securities_trend": securities_trend,

        # 净流入
        "total_financing_net_flow": total_financing_net_flow,
        "total_securities_net_flow": total_securities_net_flow,

        # 活跃度
        "avg_financing_buy": avg_financing_buy,
        "avg_financing_repay": avg_financing_repay,
        "avg_securities_sell": avg_securities_sell,
        "avg_securities_repay": avg_securities_repay,

        # 周转率
        "financing_turnover_ratio": financing_turnover_ratio,
        "securities_turnover_ratio": securities_turnover_ratio,

        # 变化率
        "rzye_change_pct": rzye_change_pct,
        "rqye_change_pct": rqye_change_pct,

        # 波动率
        "financing_volatility": financing_volatility,
        "securities_volatility": securities_volatility,

        # 风险评估
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "risk_score": risk_score,

        # 综合评分
        "overall_score": float(score),
        "recommendation": recommendation,

        # 时间序列
        "time_series": time_series,
    }

# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="个股融资融券分析")
    parser.add_argument("--stock", required=True, help="股票代码或名称，如 000001.SZ、茅台、600519")
    parser.add_argument("--days", type=int, default=30, help="分析天数，默认30天")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出")
    args = parser.parse_args()

    ts_api = _get_tushare_api()
    ts_code = _resolve_stock_code(ts_api, args.stock)

    # 获取数据
    df = fetch_margin_data(ts_api, ts_code, args.days)

    # 分析
    result = analyze_margin(df, ts_code, args.days)

    # 获取股票名称
    try:
        basic_df = ts_api.stock_basic(exchange='', list_status='L',
                                       fields='ts_code,name', ts_code=ts_code)
        if basic_df is not None and not basic_df.empty:
            result['stock_name'] = basic_df.iloc[0]['name']
    except Exception:
        result['stock_name'] = ts_code

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        _print_report(result)


def _fmt_yi(value: float) -> str:
    """格式化为亿元"""
    return f"{value / 1e8:.2f}亿"


def _fmt_wan(value: float) -> str:
    """格式化为万股"""
    return f"{value / 1e4:.2f}万"


def _print_report(result: dict):
    """打印文本格式报告"""
    if 'error' in result:
        print(f"## 融资融券分析\n\n> {result['error']}")
        return

    name = result.get('stock_name', result['ts_code'])
    code = result['ts_code']
    latest = result['latest_data']

    trend_map = {'increasing': '上升', 'decreasing': '下降', 'stable': '平稳'}
    rec_map = {'bullish': '偏多', 'bearish': '偏空', 'neutral': '中性'}
    risk_map = {'high': '高', 'medium': '中', 'low': '低'}

    print(f"\n## {name}({code}) 融资融券分析\n")
    print(f"分析区间: {result['analysis_period']}  |  数据点: {result['data_count']}天\n")

    # 最新数据
    print("### 最新数据\n")
    print("| 指标 | 数值 |")
    print("|------|------|")
    print(f"| 融资余额 | {_fmt_yi(latest['rzye'])} |")
    print(f"| 融券余额 | {_fmt_yi(latest['rqye'])} |")
    print(f"| 两融合计 | {_fmt_yi(latest['rzrqye'])} |")
    print(f"| 融资买入额 | {_fmt_yi(latest['rzmre'])} |")
    print(f"| 融资偿还额 | {_fmt_yi(latest['rzche'])} |")
    print(f"| 融券卖出量 | {_fmt_wan(latest['rqmcl'])}股 |")
    print(f"| 融券偿还量 | {_fmt_wan(latest['rqchl'])}股 |")

    # 趋势分析
    print(f"\n### 趋势分析\n")
    print(f"- 融资趋势: **{trend_map.get(result['financing_trend'], result['financing_trend'])}** (近5日变化 {result['rzye_change_pct']:+.2f}%)")
    print(f"- 融券趋势: **{trend_map.get(result['securities_trend'], result['securities_trend'])}** (近5日变化 {result['rqye_change_pct']:+.2f}%)")
    print(f"- 融资净流入: {_fmt_yi(result['total_financing_net_flow'])}")
    print(f"- 融券净增量: {_fmt_wan(result['total_securities_net_flow'])}股")

    # 活跃度
    print(f"\n### 活跃度\n")
    print(f"- 融资周转率: {result['financing_turnover_ratio']:.4f}")
    print(f"- 融券周转率: {result['securities_turnover_ratio']:.4f}")

    # 风险评估
    print(f"\n### 风险评估\n")
    print(f"- 风险等级: **{risk_map.get(result['risk_level'], result['risk_level'])}**")
    if result['risk_factors']:
        for f in result['risk_factors']:
            print(f"  - ⚠️ {f}")
    else:
        print("  - 无显著风险因子")

    # 综合评分
    print(f"\n### 综合评分\n")
    print(f"- 评分: **{result['overall_score']:.0f}/100**")
    print(f"- 建议: **{rec_map.get(result['recommendation'], result['recommendation'])}**")

if __name__ == '__main__':
    main()
