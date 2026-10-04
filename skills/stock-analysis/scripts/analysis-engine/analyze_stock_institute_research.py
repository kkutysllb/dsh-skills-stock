#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司机构调研数据分析脚本

通过 Tushare Pro API 的 stk_surv 接口获取机构调研记录，
分析调研频率、参与机构、调研方式、接待地点等。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_institute_research.py --stock 002223.SZ --json
  python scripts/analyze_stock_institute_research.py --stock 茅台 --days 90 --json
  python scripts/analyze_stock_institute_research.py --stock 600519 --days 180 --json
"""

import argparse
import json
import os
import sys
from collections import Counter
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

def analyze_institute_research(stock_input: str, days: int = 90) -> dict:
    """获取上市公司机构调研数据分析"""
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

    # 获取机构调研数据（stk_surv 接口，单次最多100条）
    all_records = []
    try:
        df = ts_api.stk_surv(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            fields='ts_code,name,surv_date,fund_visitors,rece_place,rece_mode,rece_org,org_type,comp_rece'
        )
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                record = {
                    "surv_date": str(row.get('surv_date', '')),
                    "rece_mode": str(row.get('rece_mode', '')),
                    "rece_place": str(row.get('rece_place', '')),
                    "rece_org": str(row.get('rece_org', '')),
                    "org_type": str(row.get('org_type', '')),
                    "fund_visitors": str(row.get('fund_visitors', '')),
                    "comp_rece": str(row.get('comp_rece', '')),
                }
                # 清理 nan
                for k, v in record.items():
                    if v == 'nan' or v == 'None':
                        record[k] = None
                all_records.append(record)
    except Exception as e:
        print(f"  ⚠️ 获取机构调研数据失败: {e}", file=sys.stderr)

    # 统计分析
    surv_dates = [r['surv_date'] for r in all_records if r.get('surv_date')]
    org_names = [r['rece_org'] for r in all_records if r.get('rece_org')]
    modes = [r['rece_mode'] for r in all_records if r.get('rece_mode')]
    org_types = [r['org_type'] for r in all_records if r.get('org_type')]

    # 最近调研日期
    latest_surv_date = max(surv_dates) if surv_dates else None

    # 按调研日期去重统计调研次数
    unique_surv_days = len(set(surv_dates))

    # 机构类型分布
    org_type_counter = Counter(org_types)

    # 调研方式分布
    mode_counter = Counter(modes)

    # 高频调研机构（出现2次以上）
    org_counter = Counter(org_names)
    frequent_orgs = [
        {"org_name": org, "count": cnt}
        for org, cnt in org_counter.most_common(20)
        if cnt >= 2
    ]

    # 按调研日期倒序排列，取最近20条详情
    all_records.sort(key=lambda x: x.get('surv_date', ''), reverse=True)
    recent_records = all_records[:50]

    return {
        "stock_code": ts_code,
        "stock_name": stock_name,
        "industry": industry,
        "query_period": f"最近{days}天",
        "query_start_date": start_date,
        "query_end_date": end_date,
        "total_records": len(all_records),
        "unique_surv_days": unique_surv_days,
        "latest_surv_date": latest_surv_date,
        "org_type_distribution": dict(org_type_counter.most_common(10)),
        "mode_distribution": dict(mode_counter.most_common(10)),
        "frequent_orgs": frequent_orgs,
        "recent_records": recent_records,
    }


# ======================================================================
#  chart_configs 生成（前端 ECharts 交互图表）
# ======================================================================

# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='上市公司机构调研数据分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--days', '-d', type=int, default=90,
                        help='查询最近多少天的调研记录（默认90天，最大365天）')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    try:
        result = analyze_institute_research(args.stock, args.days)
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
        print(f"  {result.get('stock_name', '')}（{result.get('stock_code', '')}）机构调研分析")
        print(f"  所属行业: {result.get('industry', '—')}")
        print(f"  查询范围: {result.get('query_period', '')}")
        print(f"{'='*60}")
        print(f"  调研总记录数: {result.get('total_records', 0)}")
        print(f"  调研天数:     {result.get('unique_surv_days', 0)}")
        print(f"  最近调研日期: {result.get('latest_surv_date', '—')}")
        print(f"{'─'*60}")

        # 机构类型分布
        print(f"\n  【机构类型分布】")
        for org_type, cnt in result.get('org_type_distribution', {}).items():
            print(f"    {org_type}: {cnt}次")

        # 调研方式分布
        print(f"\n  【调研方式分布】")
        for mode, cnt in result.get('mode_distribution', {}).items():
            print(f"    {mode}: {cnt}次")

        # 高频调研机构
        frequent_orgs = result.get('frequent_orgs', [])
        if frequent_orgs:
            print(f"\n  【高频调研机构】（2次以上）")
            for item in frequent_orgs[:15]:
                print(f"    {item['org_name']}: {item['count']}次")

        # 最近调研记录
        recent = result.get('recent_records', [])
        if recent:
            print(f"\n  【最近调研记录】（共{len(recent)}条）")
            for i, r in enumerate(recent[:10], 1):
                print(f"    {i}. [{r.get('surv_date', '')}] {r.get('rece_org', '')} "
                      f"({r.get('org_type', '')}) - {r.get('rece_mode', '')}")
                if r.get('rece_place'):
                    print(f"       地点: {r['rece_place']}")
        else:
            print(f"\n  暂无机构调研记录")

        print(f"\n{'='*60}")
        print(f"  数据来源: Tushare Pro API (stk_surv)")


if __name__ == '__main__':
    main()
