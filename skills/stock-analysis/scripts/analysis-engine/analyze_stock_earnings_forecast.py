#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
券商盈利预测数据分析脚本

通过 Tushare Pro API 的 report_rc 接口获取券商（卖方）研报的盈利预测数据，
包括预测EPS、净利润、评级、目标价等。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_earnings_forecast.py --stock 000858.SZ --json
  python scripts/analyze_stock_earnings_forecast.py --stock 茅台 --days 90 --json
  python scripts/analyze_stock_earnings_forecast.py --stock 600519 --days 180 --json
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

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
        match = df[df['ts_code'].str.startswith(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
    except Exception:
        pass
    raise ValueError(f"无法识别股票: {stock_input}")


# ======================================================================
#  核心分析逻辑
# ======================================================================

def _safe_float(val):
    """安全转换为浮点数，无效值返回 None"""
    if val is None:
        return None
    try:
        f = float(val)
        if str(val) == 'nan' or f != f:  # nan check
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_str(val):
    """安全转换字符串，nan/None 返回 None"""
    if val is None:
        return None
    s = str(val)
    if s in ('nan', 'None', 'NaT'):
        return None
    return s


def analyze_earnings_forecast(stock_input: str, days: int = 90) -> dict:
    """获取券商盈利预测数据分析"""
    ts_api = _get_tushare_api()
    ts_code = _resolve_stock_code(ts_api, stock_input)

    # 获取公司名称
    basic_df = ts_api.stock_basic(ts_code=ts_code, fields='ts_code,name,industry')
    if basic_df.empty:
        return {"error": f"未找到股票 {ts_code} 的基本信息"}
    stock_name = basic_df.iloc[0]['name']
    industry = basic_df.iloc[0].get('industry', '')

    days = min(max(days, 7), 365)
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    # 获取券商盈利预测数据（report_rc 接口，单次最多3000条）
    all_forecasts = []
    try:
        df = ts_api.report_rc(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                record = {
                    "report_date": _safe_str(row.get('report_date')),
                    "report_title": _safe_str(row.get('report_title')),
                    "report_type": _safe_str(row.get('report_type')),
                    "classify": _safe_str(row.get('classify')),
                    "org_name": _safe_str(row.get('org_name')),
                    "author_name": _safe_str(row.get('author_name')),
                    "quarter": _safe_str(row.get('quarter')),
                    "op_rt": _safe_float(row.get('op_rt')),
                    "op_pr": _safe_float(row.get('op_pr')),
                    "np": _safe_float(row.get('np')),
                    "eps": _safe_float(row.get('eps')),
                    "pe": _safe_float(row.get('pe')),
                    "roe": _safe_float(row.get('roe')),
                    "rating": _safe_str(row.get('rating')),
                    "max_price": _safe_float(row.get('max_price')),
                    "min_price": _safe_float(row.get('min_price')),
                    "rd": _safe_float(row.get('rd')),
                }
                all_forecasts.append(record)
    except Exception as e:
        print(f"  ⚠️ 获取盈利预测数据失败: {e}", file=sys.stderr)

    if not all_forecasts:
        return {
            "stock_code": ts_code,
            "stock_name": stock_name,
            "industry": industry,
            "query_period": f"最近{days}天",
            "total_forecasts": 0,
            "forecasts": [],
            "message": "该时间段内暂无券商盈利预测数据"
        }

    # ── 统计分析 ──

    # 评级分布
    ratings = [r['rating'] for r in all_forecasts if r.get('rating')]
    rating_counter = Counter(ratings)

    # 券商覆盖统计
    org_names = [r['org_name'] for r in all_forecasts if r.get('org_name')]
    org_counter = Counter(org_names)
    covering_orgs = list(org_counter.keys())

    # 最新EPS预测汇总（按 quarter 分组）
    eps_by_quarter = defaultdict(list)
    for r in all_forecasts:
        q = r.get('quarter')
        eps = r.get('eps')
        if q and eps is not None:
            eps_by_quarter[q].append(eps)

    eps_summary = {}
    for q in sorted(eps_by_quarter.keys()):
        vals = eps_by_quarter[q]
        eps_summary[q] = {
            "count": len(vals),
            "avg": round(sum(vals) / len(vals), 4),
            "max": round(max(vals), 4),
            "min": round(min(vals), 4),
        }

    # 最新净利润预测汇总（按 quarter 分组，单位万元）
    np_by_quarter = defaultdict(list)
    for r in all_forecasts:
        q = r.get('quarter')
        np_val = r.get('np')
        if q and np_val is not None:
            np_by_quarter[q].append(np_val)

    np_summary = {}
    for q in sorted(np_by_quarter.keys()):
        vals = np_by_quarter[q]
        np_summary[q] = {
            "count": len(vals),
            "avg_wan": round(sum(vals) / len(vals), 2),
            "max_wan": round(max(vals), 2),
            "min_wan": round(min(vals), 2),
        }

    # 目标价汇总
    max_prices = [r['max_price'] for r in all_forecasts if r.get('max_price') is not None]
    min_prices = [r['min_price'] for r in all_forecasts if r.get('min_price') is not None]

    target_price_summary = {}
    if max_prices:
        target_price_summary["max_price_avg"] = round(sum(max_prices) / len(max_prices), 2)
        target_price_summary["max_price_high"] = round(max(max_prices), 2)
    if min_prices:
        target_price_summary["min_price_avg"] = round(sum(min_prices) / len(min_prices), 2)
        target_price_summary["min_price_low"] = round(min(min_prices), 2)

    # 按报告日期倒序排列
    all_forecasts.sort(key=lambda x: x.get('report_date', ''), reverse=True)
    recent_forecasts = all_forecasts[:30]

    return {
        "stock_code": ts_code,
        "stock_name": stock_name,
        "industry": industry,
        "query_period": f"最近{days}天",
        "total_forecasts": len(all_forecasts),
        "covering_org_count": len(covering_orgs),
        "covering_orgs": covering_orgs[:20],
        "rating_distribution": dict(rating_counter.most_common(10)),
        "eps_summary": eps_summary,
        "np_summary": np_summary,
        "target_price_summary": target_price_summary,
        "recent_forecasts": recent_forecasts,
    }

# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='券商盈利预测数据分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--days', '-d', type=int, default=90,
                        help='查询最近多少天的预测数据（默认90天，最大365天）')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    try:
        result = analyze_earnings_forecast(args.stock, args.days)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        # 格式化文本输出
        print(f"\n{'='*60}")
        print(f"  {result.get('stock_name', '')}（{result.get('stock_code', '')}）券商盈利预测")
        print(f"  所属行业: {result.get('industry', '—')}")
        print(f"  查询范围: {result.get('query_period', '')}")
        print(f"{'='*60}")
        print(f"  预测报告数: {result.get('total_forecasts', 0)}")
        print(f"  覆盖券商数: {result.get('covering_org_count', 0)}")
        print(f"{'─'*60}")

        # 评级分布
        rating_dist = result.get('rating_distribution', {})
        if rating_dist:
            print(f"\n  【评级分布】")
            for rating, cnt in rating_dist.items():
                print(f"    {rating}: {cnt}次")

        # EPS预测汇总
        eps_summary = result.get('eps_summary', {})
        if eps_summary:
            print(f"\n  【EPS预测汇总】（元/股）")
            for q, data in eps_summary.items():
                print(f"    {q}: 均值{data['avg']}  最高{data['max']}  最低{data['min']}  ({data['count']}家)")

        # 净利润预测汇总
        np_summary = result.get('np_summary', {})
        if np_summary:
            print(f"\n  【净利润预测汇总】（万元）")
            for q, data in np_summary.items():
                print(f"    {q}: 均值{data['avg_wan']}  最高{data['max_wan']}  最低{data['min_wan']}  ({data['count']}家)")

        # 目标价汇总
        tp = result.get('target_price_summary', {})
        if tp:
            print(f"\n  【目标价汇总】（元）")
            if 'max_price_avg' in tp:
                print(f"    最高目标价均值: {tp['max_price_avg']}  最高: {tp.get('max_price_high', '—')}")
            if 'min_price_avg' in tp:
                print(f"    最低目标价均值: {tp['min_price_avg']}  最低: {tp.get('min_price_low', '—')}")

        # 覆盖券商
        orgs = result.get('covering_orgs', [])
        if orgs:
            print(f"\n  【覆盖券商】（共{len(orgs)}家）")
            for org in orgs[:15]:
                print(f"    {org}")

        # 最近预测记录
        recent = result.get('recent_forecasts', [])
        if recent:
            print(f"\n  【最近预测记录】（共{len(recent)}条）")
            for i, r in enumerate(recent[:10], 1):
                eps_str = f"EPS={r['eps']}" if r.get('eps') is not None else ""
                rating_str = f"评级={r['rating']}" if r.get('rating') else ""
                print(f"    {i}. [{r.get('report_date', '')}] {r.get('org_name', '')} "
                      f"{r.get('quarter', '')} {eps_str} {rating_str}")
                if r.get('max_price') is not None or r.get('min_price') is not None:
                    print(f"       目标价: {r.get('min_price', '—')} ~ {r.get('max_price', '—')}")

        msg = result.get('message')
        if msg:
            print(f"\n  {msg}")

        print(f"\n{'='*60}")
        print(f"  数据来源: Tushare Pro API (report_rc)")


if __name__ == '__main__':
    main()
