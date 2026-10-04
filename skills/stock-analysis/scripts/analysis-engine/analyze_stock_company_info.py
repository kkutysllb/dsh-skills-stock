#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上市公司基本信息分析脚本

通过 Tushare Pro API 的 stock_basic + stock_company 接口获取公司详细信息，
包括成立时间、上市时间、主营业务、行业分类等。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_company_info.py --stock 000001.SZ --json
  python scripts/analyze_stock_company_info.py --stock 茅台 --json
  python scripts/analyze_stock_company_info.py --stock 600519 --json
"""

import argparse
import json
import os
import sys

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

    # 已经是 ts_code 格式（如 600519.SH）
    if '.' in code and len(code.split('.')[0]) == 6:
        return code

    # 6位纯数字：直接拼接后缀
    if code.isdigit() and len(code) == 6:
        suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
        return code + suffix

    # 尝试从 stock_basic 查找
    try:
        df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        # 精确名称匹配
        match = df[df['name'] == code]
        if not match.empty:
            return match.iloc[0]['ts_code']
        # 模糊名称匹配
        match = df[df['name'].str.contains(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
        # ts_code 前缀匹配（如输入 600519）
        match = df[df['ts_code'].str.startswith(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
    except Exception:
        pass
    raise ValueError(f"无法识别股票: {stock_input}")


# ======================================================================
#  核心分析逻辑
# ======================================================================

def analyze_company_info(stock_input: str) -> dict:
    """获取上市公司基本信息"""
    ts_api = _get_tushare_api()
    ts_code = _resolve_stock_code(ts_api, stock_input)

    # 获取基本信息
    basic_df = ts_api.stock_basic(
        ts_code=ts_code,
        fields='ts_code,name,fullname,industry,area,market,list_date'
    )
    if basic_df.empty:
        return {"error": f"未找到股票 {ts_code} 的基本信息"}

    result = basic_df.iloc[0].to_dict()

    # 获取公司详细信息（stock_company 接口）
    try:
        company_df = ts_api.stock_company(
            ts_code=ts_code,
            fields='ts_code,chairman,manager,secretary,reg_capital,setup_date,'
                   'province,city,introduction,main_business,business_scope,'
                   'website,email,office,employees'
        )
        if not company_df.empty:
            company_info = company_df.iloc[0].to_dict()
            result.update(company_info)
    except Exception as e:
        print(f"  ⚠️ 获取公司详细信息失败: {e}", file=sys.stderr)

    # 格式化日期字段
    for date_field in ['list_date', 'setup_date']:
        val = result.get(date_field)
        if val and str(val) != 'nan':
            try:
                s = str(val)
                if len(s) == 8:
                    result[date_field] = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            except Exception:
                pass
        elif val and str(val) == 'nan':
            result[date_field] = None

    # 清理 nan 值
    for key, val in result.items():
        if isinstance(val, float) and str(val) == 'nan':
            result[key] = None

    return result


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='上市公司基本信息分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    try:
        result = analyze_company_info(args.stock)
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
        print(f"  {result.get('name', '')}（{result.get('ts_code', '')}）公司基本信息")
        print(f"{'='*60}")
        print(f"  公司全称: {result.get('fullname', '—')}")
        print(f"  行业分类: {result.get('industry', '—')}")
        print(f"  所在地区: {result.get('area', '—')} / {result.get('province', '—')}{result.get('city', '')}")
        print(f"  市场类型: {result.get('market', '—')}")
        print(f"  成立日期: {result.get('setup_date', '—')}")
        print(f"  上市日期: {result.get('list_date', '—')}")
        print(f"  董 事 长: {result.get('chairman', '—')}")
        print(f"  总 经 理: {result.get('manager', '—')}")
        print(f"  董    秘: {result.get('secretary', '—')}")
        print(f"  注册资本: {result.get('reg_capital', '—')} 万元")
        print(f"  员工人数: {result.get('employees', '—')}")
        print(f"  公司网址: {result.get('website', '—')}")
        print(f"  公司邮箱: {result.get('email', '—')}")
        print(f"  办公地址: {result.get('office', '—')}")
        print(f"{'─'*60}")
        print(f"  主营业务: {result.get('main_business', '—')}")
        print(f"{'─'*60}")
        print(f"  经营范围: {result.get('business_scope', '—')}")
        print(f"{'─'*60}")
        intro = result.get('introduction', '')
        if intro:
            print(f"  公司简介: {intro[:500]}{'...' if len(intro) > 500 else ''}")
        print(f"{'='*60}")
        print(f"  数据来源: Tushare Pro API")


if __name__ == '__main__':
    main()
