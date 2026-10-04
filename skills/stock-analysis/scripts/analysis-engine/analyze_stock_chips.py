#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股筹码分布分析脚本

通过 Tushare Pro API 的 cyq_chips 接口获取筹码分布数据，
分析套牢盘/获利盘集中区、支撑压力位、筹码密集度。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_chips.py --stock 000001.SZ --json
  python scripts/analyze_stock_chips.py --stock 600519.SH --date 20260327 --json
"""

import argparse
import json
import os
import re
import sys
import time
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


def _resolve_stock(ts_api, stock_input: str) -> tuple:
    code = stock_input.strip()
    if '.' in code and len(code.split('.')[0]) == 6:
        ts_code = code
        name = _get_stock_name(ts_api, ts_code)
        return ts_code, name

    try:
        df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,name,code')
        match = df[df['name'] == code]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
        match = df[df['name'].str.contains(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
        match = df[df['code'] == code]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
    except Exception:
        pass
    raise ValueError(f"无法识别股票: {stock_input}")


def _get_stock_name(ts_api, ts_code: str) -> str:
    try:
        df = ts_api.stock_basic(ts_code=ts_code, fields='name')
        if not df.empty:
            return df.iloc[0]['name']
    except Exception:
        pass
    return ts_code


def _get_latest_trade_date(ts_api, days: int = 5) -> str:
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    cal = ts_api.trade_cal(exchange='SSE', start_date=start, end_date=end, is_open='1')
    if cal is None or cal.empty:
        return datetime.now().strftime('%Y%m%d')
    dates = sorted(cal['cal_date'].tolist())
    return dates[-1] if dates else datetime.now().strftime('%Y%m%d')


def _fetch_chips_data(ts_api, ts_code: str, trade_date: str) -> pd.DataFrame:
    """获取指定日期的筹码分布数据"""
    try:
        df = ts_api.cyq_chips(ts_code=ts_code, trade_date=trade_date)
        time.sleep(0.3)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _fetch_chips_history(ts_api, ts_code: str, days: int = 60) -> pd.DataFrame:
    """获取近N日的筹码分布用于趋势分析"""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    cal = ts_api.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
    if cal is None or cal.empty:
        return pd.DataFrame()

    all_dates = sorted(cal['cal_date'].tolist())
    sample_dates = all_dates[::5] if len(all_dates) > 20 else all_dates[-10:]

    frames = []
    for d in sample_dates[-15:]:
        chip_df = _fetch_chips_data(ts_api, ts_code, d)
        if not chip_df.empty:
            chip_df['sample_date'] = d
            frames.append(chip_df)
        time.sleep(0.2)

    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()


def _analyze_distribution(chips_df: pd.DataFrame, current_price: float) -> dict:
    """分析筹码分布"""
    if chips_df.empty:
        return {'error': '无筹码分布数据'}

    chips_df = chips_df.copy()
    chips_df = chips_df[chips_df['price'] > 0]

    if 'percent' in chips_df.columns:
        chips_df['ratio'] = chips_df['percent']
    elif 'chip_rate' in chips_df.columns:
        chips_df['ratio'] = chips_df['chip_rate'] * 100
    elif 'ratio' in chips_df.columns:
        chips_df['ratio'] = chips_df['ratio']
    else:
        return {'error': '筹码数据缺少比例字段'}

    chips_df = chips_df.sort_values('price')
    chips_df['cum_ratio'] = chips_df['ratio'].cumsum()

    if current_price:
        below_price = chips_df[chips_df['price'] <= current_price]
        above_price = chips_df[chips_df['price'] > current_price]
        profit_ratio = float(below_price['ratio'].sum())
        loss_ratio = float(above_price['ratio'].sum())
    else:
        profit_ratio = 0
        loss_ratio = 0

    cum = chips_df['cum_ratio'].values
    prices = chips_df['price'].values

    def find_percentile_price(pct):
        for i, c in enumerate(cum):
            if c >= pct:
                return float(prices[i])
        return float(prices[-1]) if len(prices) > 0 else None

    concentration_90_low = find_percentile_price(5)
    concentration_90_high = find_percentile_price(95)
    concentration_70_low = find_percentile_price(15)
    concentration_70_high = find_percentile_price(85)

    if concentration_90_high and concentration_90_low and current_price:
        width = concentration_90_high - concentration_90_low
        density = width / current_price * 100 if current_price else 0
    else:
        width = None
        density = None

    if len(chips_df) > 0:
        total_ratio = float(chips_df['ratio'].sum())
        avg_cost = float((chips_df['price'] * chips_df['ratio']).sum()) / total_ratio if total_ratio else None
    else:
        avg_cost = None

    support = concentration_90_low
    resistance = concentration_90_high

    if avg_cost and current_price:
        deviation = (current_price - avg_cost) / avg_cost * 100
    else:
        deviation = None

    max_ratio_idx = chips_df['ratio'].idxmax() if len(chips_df) > 0 else None
    peak_price = float(chips_df.loc[max_ratio_idx, 'price']) if max_ratio_idx is not None else None

    if len(chips_df) > 0:
        price_min = float(chips_df['price'].min())
        price_max = float(chips_df['price'].max())
        price_range = price_max - price_min
        levels = []
        n_levels = 5
        step = price_range / n_levels if price_range > 0 else 0
        for i in range(n_levels):
            p_low = price_min + i * step
            p_high = price_min + (i + 1) * step
            mask = (chips_df['price'] >= p_low) & (chips_df['price'] < p_high)
            level_ratio = float(chips_df.loc[mask, 'ratio'].sum()) if mask.any() else 0
            levels.append({
                'range': f"{p_low:.2f}~{p_high:.2f}",
                'ratio': round(level_ratio, 2),
            })
    else:
        levels = []

    return {
        'profit_ratio': round(profit_ratio, 2),
        'loss_ratio': round(loss_ratio, 2),
        'avg_cost': round(avg_cost, 2) if avg_cost else None,
        'peak_price': round(peak_price, 2) if peak_price else None,
        'support': round(support, 2) if support else None,
        'resistance': round(resistance, 2) if resistance else None,
        'concentration_90_width': round(width, 2) if width else None,
        'concentration_density_pct': round(density, 2) if density else None,
        'deviation_from_avg': round(deviation, 2) if deviation else None,
        'price_levels': levels,
        'distribution_data': [
            {'price': round(float(row['price']), 2),
             'ratio': round(float(row['ratio']), 3)}
            for _, row in chips_df.iterrows()
        ] if len(chips_df) <= 100 else [],
    }


def _analyze_trend(history_df: pd.DataFrame) -> dict:
    """分析筹码趋势"""
    if history_df.empty or 'sample_date' not in history_df.columns:
        return {}

    dates = sorted(history_df['sample_date'].unique().tolist())
    if len(dates) < 2:
        return {}

    trends = []
    for d in dates:
        day_df = history_df[history_df['sample_date'] == d]
        if day_df.empty:
            continue
        avg = float((day_df['price'] * day_df['ratio']).sum()) / float(day_df['ratio'].sum()) if 'ratio' in day_df.columns and day_df['ratio'].sum() > 0 else None
        cum = day_df['ratio'].cumsum() if 'ratio' in day_df.columns else None
        peak_idx = day_df['ratio'].idxmax() if 'ratio' in day_df.columns else None
        peak = float(day_df.loc[peak_idx, 'price']) if peak_idx is not None else None
        if avg:
            trends.append({
                'date': d,
                'avg_cost': round(avg, 2),
                'peak_price': round(peak, 2) if peak else None,
            })

    if len(trends) >= 2:
        avg_costs = [t['avg_cost'] for t in trends]
        drift = round((avg_costs[-1] - avg_costs[0]) / avg_costs[0] * 100, 2) if avg_costs[0] else None
    else:
        drift = None

    return {
        'trend_points': trends,
        'avg_cost_drift_pct': drift,
    }


def analyze_stock_chips(stock_input: str, trade_date: Optional[str] = None) -> dict:
    """
    分析个股筹码分布。
    """
    ts_api = _get_tushare_api()
    ts_code, stock_name = _resolve_stock(ts_api, stock_input)

    if not trade_date:
        trade_date = _get_latest_trade_date(ts_api)
    else:
        trade_date = str(trade_date)

    try:
        price_df = ts_api.daily(ts_code=ts_code, trade_date=trade_date,
                                fields='close,open,high,low')
        time.sleep(0.2)
        if price_df is not None and not price_df.empty:
            current_price = float(price_df.iloc[0]['close'])
        else:
            recent = ts_api.daily(ts_code=ts_code,
                                  start_date=(datetime.now() - timedelta(days=5)).strftime('%Y%m%d'),
                                  end_date=trade_date,
                                  fields='close')
            current_price = float(recent.iloc[-1]['close']) if recent is not None and not recent.empty else None
    except Exception:
        current_price = None

    chips_df = _fetch_chips_data(ts_api, ts_code, trade_date)
    if chips_df.empty:
        return {
            'ts_code': ts_code,
            'stock_name': stock_name,
            'trade_date': trade_date,
            'error': f'无法获取 {trade_date} 的筹码数据（Tushare cyq_chips 需要较高积分）'
        }

    distribution = _analyze_distribution(chips_df, current_price)

    history_df = _fetch_chips_history(ts_api, ts_code, days=60)
    trend = _analyze_trend(history_df)

    summary = []
    if distribution.get('profit_ratio', 0) > 70:
        summary.append('获利盘偏重，短期有回吐压力')
    elif distribution.get('profit_ratio', 0) < 30:
        summary.append('套牢盘偏重，磨底时间可能较长')
    if distribution.get('deviation_from_avg') and abs(distribution['deviation_from_avg']) > 15:
        if distribution['deviation_from_avg'] > 0:
            summary.append(f'股价高于平均成本 {abs(distribution["deviation_from_avg"]):.1f}%，注意回撤风险')
        else:
            summary.append(f'股价低于平均成本 {abs(distribution["deviation_from_avg"]):.1f}%，关注反弹机会')
    if distribution.get('concentration_density_pct') and distribution['concentration_density_pct'] < 15:
        summary.append('筹码高度集中，可能酝酿变盘')
    if not summary:
        summary.append('筹码分布较为分散，市场换手平稳')

    result = {
        'ts_code': ts_code,
        'stock_name': stock_name,
        'trade_date': trade_date,
        'current_price': current_price,
        'distribution': distribution,
        'trend': trend,
        'analysis_summary': summary,
    }

    return result

# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='个股筹码分布分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--date', '-d', type=str, default=None, help='分析日期 YYYYMMDD')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')

    args = parser.parse_args()

    try:
        result = analyze_stock_chips(args.stock, args.date)
    except Exception as e:
        result = {'error': str(e)}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    if 'error' in result:
        print(f"错误: {result['error']}")
        sys.exit(1)

    # 输出结果
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
