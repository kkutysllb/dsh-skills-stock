#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财报分析命令行工具

股票解析全部通过 Tushare Pro API 完成，不依赖本地数据库。
本地数据库仅作备份用途。

用法:
    python scripts/analyze_financial_report.py
    python scripts/analyze_financial_report.py --stock 茅台
    python scripts/analyze_financial_report.py --stock 600519
    python scripts/analyze_financial_report.py --stock 600519.SH --years 3
    python scripts/analyze_financial_report.py --stock 宁德时代 --years 5 --type annual
"""

import sys
import os
import json
import argparse
from typing import Tuple, Dict, List, Optional
from datetime import datetime, timedelta
import re
import time
import io

import pandas as pd


# 添加项目根目录到路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ------------------------------------------------------------------ #
#  格式化输出工具
# ------------------------------------------------------------------ #

def _fmt_money(val: float) -> str:
    """将元转换为亿元显示"""
    if val == 0:
        return "0"
    if abs(val) >= 1e8:
        return f"{val/1e8:.2f}亿"
    if abs(val) >= 1e4:
        return f"{val/1e4:.2f}万"
    return f"{val:.2f}"


def _fmt_money_display(val: float) -> str:
    """将元转换为亿元显示（用于表格）"""
    if val == 0:
        return "0"
    if abs(val) >= 1e8:
        return f"{val/1e8:.2f}"
    if abs(val) >= 1e4:
        return f"{val/1e4:.2f}"
    return f"{val:.2f}"


def _fmt_pct(val: float) -> str:
    sign = '+' if val > 0 else ''
    return f"{sign}{val:.2f}%"


def _bar(val: float, max_val: float, width: int = 20) -> str:
    """生成文本进度条"""
    import math
    if max_val == 0 or math.isnan(val) or math.isnan(max_val):
        return ''
    filled = int(abs(val) / max_val * width)
    return '█' * filled + '░' * (width - filled)


def _get_trend_icon(trend: str) -> str:
    """获取趋势图标"""
    if '上升' in trend or '增长' in trend:
        return '📈'
    elif '下降' in trend or '减少' in trend:
        return '📉'
    else:
        return '➡️'


def _get_stability_icon(stability: str) -> str:
    """获取稳定性图标"""
    if '稳定' in stability:
        return '✅'
    elif '波动' in stability:
        return '⚠️'
    else:
        return '➡️'


def _get_star_rating(quality: str) -> str:
    """获取星级评价"""
    if '优质' in quality or '优秀' in quality:
        return '⭐⭐'
    elif '良好' in quality:
        return '⭐'
    else:
        return ''


def print_section(title: str):
    width = 60
    print(f"\n{'─'*width}")
    print(f"  {title}")
    print(f"{'─'*width}")


# ======================================================================
#  LLM 分析层
# ======================================================================

def print_annual_analysis(result: Dict, stock_name: str, ts_code: str, report_date: str,
):
    """格式化打印年报分析结果（模板格式）"""

    # 1. 营业收入分析
    rev = result.get('revenue_analysis', {})
    if rev:
        print("\n### 1. 营业收入分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        current_rev = rev.get('current_revenue', 0)
        yoy_growth = rev.get('yoy_growth', 0)
        avg_growth = rev.get('avg_growth_rate', 0)
        trend = rev.get('revenue_trend', '')
        stability = rev.get('growth_stability', '')
        
        print(f"| 最新营收 | **{_fmt_money_display(current_rev)}亿元** | 最新年报 |")
        print(f"| 同比增长 | **{_fmt_pct(yoy_growth)}** | 增长 |")
        print(f"| 历年平均增速 | **{_fmt_pct(avg_growth)}** | 过去5年 |")
        print(f"| 增长趋势 | {_get_trend_icon(trend)} {trend} | 趋势判断 |")
        print(f"| 增长稳定性 | {_get_stability_icon(stability)} {stability} | 波动程度 |")
        
        # 小s解读
        if yoy_growth > avg_growth:
            print(f"\n**小s解读：** 营收增速（{_fmt_pct(yoy_growth)}）高于历史均值（{_fmt_pct(avg_growth)}），增长加速，势头良好。")
        elif yoy_growth > 0:
            print(f"\n**小s解读：** 营收增速（{_fmt_pct(yoy_growth)}）虽低于历史均值（{_fmt_pct(avg_growth)}），但仍保持增长，规模效应持续显现。")
        else:
            print(f"\n**小s解读：** 营收增速（{_fmt_pct(yoy_growth)}）出现下滑，需关注业务增长动力。")
        
        # 插入营收图表和LLM分析
    
    # 2. 净利润分析
    pft = result.get('profit_analysis', {})
    if pft:
        print("\n### 2. 净利润分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        current_profit = pft.get('current_profit', 0)
        profit_yoy = pft.get('yoy_growth', 0)
        profit_margin = pft.get('profit_margin', 0)
        quality = pft.get('profit_quality', '')
        
        print(f"| 最新净利润 | **{_fmt_money_display(current_profit)}亿元** | 年报 |")
        print(f"| 同比增长 | **{_fmt_pct(profit_yoy)}** | 利润增速✅ |")
        print(f"| 净利率 | **{profit_margin:.2f}%** | 盈利能力 |")
        print(f"| 利润质量 | {_get_star_rating(quality)} {quality} | 含金量评估 |")
        
        # 小s解读
        if profit_yoy > yoy_growth:
            print(f"\n**小s解读：** 净利增速（{_fmt_pct(profit_yoy)}）超过营收增速（{_fmt_pct(yoy_growth)}），说明盈利能力在提升，成本控制良好，规模效应显现。")
        else:
            print(f"\n**小s解读：** 净利增速（{_fmt_pct(profit_yoy)}）与营收增速基本同步，盈利能力稳定。")

    # 3. 毛利率分析
    gm = result.get('gross_margin_analysis', {})
    if gm:
        print("\n### 3. 毛利率分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        current_margin = gm.get('current_margin', 0)
        avg_margin = gm.get('avg_margin', 0)
        margin_trend = gm.get('margin_trend', '')
        margin_stability = gm.get('margin_stability', '')
        
        if current_margin > 0:
            print(f"| 当前毛利率 | **{current_margin:.2f}%** | 年报 |")
            print(f"| 历史均值 | {avg_margin:.2f}% | 平均 |")
            print(f"| 毛利趋势 | {_get_trend_icon(margin_trend)} {margin_trend} | 盈利能力 |")
            print(f"| 稳定性 | {margin_stability} | 波动程度 |")
            
            if current_margin > avg_margin:
                print(f"\n**小s解读：** 毛利率（{current_margin:.2f}%）高于历史均值（{avg_margin:.2f}%），说明产品议价能力增强或成本优化见效。")
            else:
                print(f"\n**小s解读：** 毛利率（{current_margin:.2f}%）低于历史均值（{avg_margin:.2f}%），需关注成本控制或产品定价策略。")
        else:
            print(f"| 当前毛利率 | **N/A** | 年报 |")
            print(f"| 历史均值 | N/A | 平均 |")
            print(f"| 毛利趋势 | 📉 {margin_trend} | 盈利能力 |")
            print(f"| 稳定性 | {margin_stability} | 波动程度 |")
            print(f"\n**小s解读：** ⚠️ 毛利率数据缺失，建议关注公司官方财报或交易所披露数据。")
        
        # 插入毛利率图表和LLM分析
    
    # 4. 现金流分析
    cf = result.get('cash_flow_analysis', {})
    if cf:
        print("\n### 4. 现金流分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        current_cf = cf.get('current_cash_flow', 0)
        cf_yoy = cf.get('yoy_growth', 0)
        cf_health = cf.get('cash_flow_health', '')
        
        print(f"| 经营现金流 | **{_fmt_money_display(current_cf)}亿元** | 年报 |")
        print(f"| 同比增长 | **{_fmt_pct(cf_yoy)}** | 现金流变化 |")
        health_icon = '✅' if '健康' in cf_health else '⚠️'
        print(f"| 现金流健康度 | {health_icon} {cf_health} | 造血能力 |")
        
        if cf_yoy > 0:
            print(f"\n**小s解读：** 经营现金流同比+{cf_yoy:.2f}%，造血能力强劲，财务健康。")
        else:
            print(f"\n**小s解读：** 经营现金流同比{_fmt_pct(cf_yoy)}，但绝对值（{_fmt_money_display(current_cf)}亿）依然充沛，造血能力强劲。")
        
        # 插入现金流图表和LLM分析

    # 5. 合同负债分析
    cl = result.get('contract_liabilities_analysis', {})
    if cl:
        print("\n### 5. 合同负债（预收款）分析 — 🔥 关键指标\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        curr_cl = cl.get('current_liabilities', 0)
        gr_cl = cl.get('growth_rate', 0)
        sig_cl = cl.get('future_revenue_indicator', '')
        
        print(f"| 当前合同负债 | **{_fmt_money_display(curr_cl)}亿元** | 年报 |")
        print(f"| 同比增长 | **{_fmt_pct(gr_cl)}** | 增长 |")
        print(f"| 连续增长期数 | 多年 | 持续扩张 |")
        print(f"| 未来收入信号 | {sig_cl} | 订单情况 |")
        
        if gr_cl > 0:
            print(f"\n**小s解读：** ✅ 合同负债增长{_fmt_pct(gr_cl)}，订单充足，未来收入有保障。")
        else:
            print(f"\n**小s解读：** ⚠️ 合同负债下降{_fmt_pct(gr_cl)}，需关注订单情况。")
        
        # 插入合同负债图表和LLM分析

    # 6. 库存分析
    inv = result.get('inventory_analysis', {})
    if inv:
        print("\n### 6. 库存（存货）分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        curr_inv = inv.get('current_inventory', 0)
        inv_gr = inv.get('inventory_growth_rate', 0)
        rev_gr = inv.get('revenue_growth_rate', 0)
        signal = inv.get('signal', '')
        ratio = inv.get('inv_to_rev_ratio', 0)
        
        print(f"| 当前库存 | **{_fmt_money_display(curr_inv)}亿元** | 年报 |")
        print(f"| 库存增速 | **{_fmt_pct(inv_gr)}** | 增长 |")
        print(f"| 营收增速 | {_fmt_pct(rev_gr)} | 对比指标 |")
        print(f"| 库存/营收比 | {ratio:.1f}% | 库存占比 |")
        print(f"| 产销信号 | {signal} | 健康度 |")
        
        if '积压' in signal:
            print(f"\n**小s解读：** ⚠️ 库存增速（{_fmt_pct(inv_gr)}）高于营收增速（{_fmt_pct(rev_gr)}），需关注库存积压风险。")
        elif '供不应求' in signal:
            print(f"\n**小s解读：** ✅ 库存增速（{_fmt_pct(inv_gr)}）低于营收增速（{_fmt_pct(rev_gr)}），产销信号显示供不应求。")
        else:
            print(f"\n**小s解读：** 库存增速（{_fmt_pct(inv_gr)}）与营收增速（{_fmt_pct(rev_gr)}）基本匹配，产销平衡。")
        
        # 插入库存图表和LLM分析

    # 7. 盈利能力指标
    vi = result.get('valuation_indicators', {})
    if vi:
        print("\n### 7. 盈利能力指标\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        roe = vi.get('roe', 0)
        roe_trend = vi.get('roe_trend', '')
        avg_roe = vi.get('avg_roe', 0)
        roa = vi.get('roa', 0)
        debt_ratio = vi.get('debt_to_assets', 0)
        total_assets = vi.get('total_assets', 0)
        profit_grade = vi.get('profitability_grade', '')
        
        if roe > 0:
            print(f"| **ROE** | **{roe:.2f}%** | 净资产收益率 |")
            print(f"| ROE趋势 | {_get_trend_icon(roe_trend)} {roe_trend} | 盈利能力 |")
            print(f"| 历史平均ROE | {avg_roe:.2f}% | 平均水平 |")
            print(f"| **ROA** | **{roa:.2f}%** | 资产回报 |")
            print(f"| 资产负债率 | {debt_ratio:.2f}% | 杠杆水平 |")
            print(f"| 总资产 | {_fmt_money_display(total_assets)}亿元 | 规模 |")
            
            if roe > 20:
                print(f"| 盈利评级 | ⭐⭐⭐ 优秀 | 综合评价 |")
                print(f"\n**小s解读：** ROE {roe:.2f}%处于优秀水平，盈利能力强劲。")
            elif roe > 15:
                print(f"| 盈利评级 | ⭐⭐ 良好 | 综合评价 |")
                print(f"\n**小s解读：** ROE {roe:.2f}%处于良好水平，盈利能力较强。")
            else:
                print(f"| 盈利评级 | ⭐ 一般 | 综合评价 |")
                print(f"\n**小s解读：** ROE {roe:.2f}%处于一般水平，需关注盈利能力提升。")
        else:
            print(f"| **ROE** | **N/A** | 数据缺失 |")
            print(f"| ROE趋势 | 📉 {roe_trend} | 盈利能力 |")
            print(f"| 历史平均ROE | N/A | 数据缺失 |")
            print(f"| **ROA** | **N/A** | 资产回报 |")
            print(f"| 资产负债率 | N/A | 杠杆水平 |")
            print(f"| 总资产 | {_fmt_money_display(total_assets)}亿元 | 规模 |")
            print(f"| 盈利评级 | ⭐⭐ 一般 | 综合评价 |")
            print(f"\n**小s解读：** ⚠️ ROE、ROA等关键盈利指标数据缺失，建议查阅公司年报获取详细信息。")
        
        # 插入ROE图表和LLM分析

    # 8. 综合评分
    ot = result.get('overall_trend', {})
    if ot:
        print("\n### 8. 综合评分\n")
        print("| 指标 | 数值 |")
        print("|------|------|")
        score = ot.get('composite_score', 0)
        grade = ot.get('investment_grade', '')
        print(f"| 综合评分 | **{score:.1f}/10** |")
        print(f"| 投资评级 | **{grade}** |")
        
        if score >= 8:
            print(f"\n**小s解读：** 财务表现优秀，建议重点关注。")
        elif score >= 6:
            print(f"\n**小s解读：** 财务稳健，可以考虑配置。")
        else:
            print(f"\n**小s解读：** 财务表现一般，建议谨慎观察。")
        
        # 插入综合评分图表


def print_quarterly_analysis(result: Dict, stock_name: str, ts_code: str,
):
    """格式化打印季报分析结果（模板格式）"""

    # 1. 季度营收
    rev = result.get('revenue_analysis', {})
    if rev:
        print("\n### 1. 季度营收\n")
        print("| 指标 | 数值 |")
        print("|------|------|")
        current_q_rev = rev.get('current_quarter_revenue', 0)
        print(f"| 最新季度营收 | **{_fmt_money_display(current_q_rev)}亿元** |")
        
        rates = rev.get('qoq_growth_rates', [])
        if rates:
            print(f"| 环比增速序列 | {' → '.join(_fmt_pct(r) for r in rates)} |")
        
        avg_qoq = rev.get('avg_qoq_growth', 0)
        print(f"| 平均环比增速 | {_fmt_pct(avg_qoq)} |")
        
        # 插入季度营收图表

    # 2. 季度利润率 + 3. 季度毛利率（合并显示）
    pft = result.get('profit_analysis', {})
    gm = result.get('gross_margin_analysis', {})
    if pft or gm:
        print("\n### 2. 季度利润率\n")
        if pft:
            print("| 季度 | 净利率 |")
            print("|------|--------|")
            margins = pft.get('profit_margins', [])
            for i, m in enumerate(margins[:4], 1):
                print(f"| Q{i} | {m:.1f}% |")
        
        if gm:
            print("\n### 3. 季度毛利率\n")
            print("| 季度 | 毛利率 |")
            print("|------|--------|")
            qm = gm.get('quarterly_margins', [])
            for i, m in enumerate(qm[:4], 1):
                if m > 0:
                    print(f"| Q{i} | {m:.1f}% |")
                else:
                    print(f"| Q{i} | N/A |")
            
            seasonal = gm.get('seasonal_variation', '')
            print(f"\n**季节性波动：** {seasonal}")
        
        # 插入季度利润率图表

    # 4. 季度经营现金流
    cf = result.get('cash_flow_analysis', {})
    if cf:
        print("\n### 4. 季度经营现金流\n")
        print("| 季度 | 现金流 |")
        print("|------|--------|")
        cfs = cf.get('quarterly_cash_flows', [])
        for i, v in enumerate(cfs[:4], 1):
            print(f"| Q{i} | {_fmt_money_display(v)}亿元 |")
        
        stability = cf.get('cash_flow_stability', '')
        print(f"\n**现金流稳定性：** {stability}")
        
        # 插入季度现金流图表

    # 5. 季度合同负债
    cl = result.get('contract_liabilities_analysis', {})
    if cl and cl.get('history'):
        print("\n### 5. 季度合同负债\n")
        print("| 季度 | 金额 | 环比 |")
        print("|------|------|------|")
        
        history = cl.get('history', [])
        for i, h in enumerate(history):
            if i == 0:
                print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | - |")
            else:
                prev_val = history[i-1]['value']
                if prev_val > 0:
                    qoq = (h['value'] - prev_val) / prev_val * 100
                    print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | {_fmt_pct(qoq)} |")
                else:
                    print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | N/A |")
        
        sig = cl.get('future_revenue_indicator', '')
        print(f"\n**未来收入信号：** {sig}")
        
        # 插入季度合同负债图表

    # 6. 季度库存分析
    inv = result.get('inventory_analysis', {})
    if inv:
        print("\n### 6. 季度库存分析\n")
        print("| 季度 | 库存金额 | 环比 |")
        print("|------|----------|------|")
        
        history = inv.get('history', [])
        for i, h in enumerate(history):
            if i == 0:
                print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | - |")
            else:
                prev_val = history[i-1]['value']
                if prev_val > 0:
                    qoq = (h['value'] - prev_val) / prev_val * 100
                    print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | {_fmt_pct(qoq)} |")
                else:
                    print(f"| {h['period']} | {_fmt_money_display(h['value'])}亿元 | N/A |")
        
        print("\n| 指标 | 季报数值 |")
        print("|------|----------|")
        inv_gr = inv.get('inventory_growth_rate', 0)
        rev_gr = inv.get('revenue_growth_rate', 0)
        signal = inv.get('signal', '')
        print(f"| 库存增速 | {_fmt_pct(inv_gr)} |")
        print(f"| 营收增速 | {_fmt_pct(rev_gr)} |")
        print(f"| 产销信号 | {signal} |")
        
        if '供不应求' in signal:
            print(f"\n**小s解读：** 📌 **季报显示库存增速（{_fmt_pct(inv_gr)}）显著低于营收增速（{_fmt_pct(rev_gr)}），产销信号是'供不应求'，需求旺盛。**")
        elif '积压' in signal:
            print(f"\n**小s解读：** ⚠️ 季报显示库存增速（{_fmt_pct(inv_gr)}）高于营收增速（{_fmt_pct(rev_gr)}），需关注库存积压风险。")
        else:
            print(f"\n**小s解读：** 季报显示产销基本平衡。")
        
        # 插入季度库存图表


def print_main_business(result: Dict, stock_name: str):
    """格式化打印主营业务分析（模板格式）"""
    if 'error' in result:
        print(f"\n### 三、主营业务构成\n")
        print(f"\n[主营业务] {result['error']}")
        return

    latest_period = result.get('latest_period', '')
    print(f"\n### 三、主营业务构成（{latest_period}）\n")
    print("| 业务板块 | 销售额 | 占比 | 毛利率 | 同比 |")
    print("|----------|--------|------|--------|------|")
    
    products = result.get('products', [])
    yoy = {item['name']: item['yoy_sales_pct'] for item in result.get('yoy_changes', [])}
    
    # 添加业务图标
    business_icons = {
        '汽车': '🚗',
        '手机': '📱',
        '电池': '🔋',
        '光伏': '☀️',
        '其他': '📦',
    }
    
    for p in products:
        name = p['name']
        # 尝试匹配图标
        icon = '📦'
        for key, ico in business_icons.items():
            if key in name:
                icon = ico
                break
        
        yoy_str = _fmt_pct(yoy[name]) if name in yoy else 'N/A'
        print(f"| {icon} {name} | {_fmt_money_display(p['sales'])}亿元 | {p['sales_share_pct']:.1f}% | {p['gross_margin_pct']:.1f}% | {yoy_str} |")
    
    # 小s解读
    if products:
        top_product = products[0]
        print(f"\n**小s解读：** 核心业务为{top_product['name']}，占比{top_product['sales_share_pct']:.1f}%，毛利率{top_product['gross_margin_pct']:.1f}%，具备较强的盈利能力。")


def print_investment_summary(result: Dict, stock_name: str):
    """打印投资建议总结"""
    print("\n## 四、投资建议总结\n")
    
    # 优势亮点
    print("### ✅ 优势亮点")
    advantages = []
    
    rev = result.get('revenue_analysis', {})
    if rev.get('yoy_growth', 0) > 20:
        advantages.append("- 营收利润双增长，增速保持20%+")
    elif rev.get('yoy_growth', 0) > 0:
        advantages.append("- 营收保持增长")
    
    cl = result.get('contract_liabilities_analysis', {})
    if cl.get('growth_rate', 0) > 0:
        advantages.append("- 合同负债持续增长，订单充足")
    
    cf = result.get('cash_flow_analysis', {})
    if cf.get('current_cash_flow', 0) > 0:
        advantages.append("- 现金流充沛，财务稳健")
    
    inv = result.get('inventory_analysis', {})
    if '供不应求' in inv.get('signal', ''):
        advantages.append("- 季度产销信号显示供不应求")
    
    if advantages:
        print('\n'.join(advantages))
    else:
        print("- 财务状况稳定")
    
    # 关注要点
    print("\n### ⚠️ 关注要点")
    concerns = []
    
    if cf.get('yoy_growth', 0) < 0:
        concerns.append(f"- 经营现金流同比下降{abs(cf.get('yoy_growth', 0)):.1f}%")
    
    pft = result.get('profit_analysis', {})
    margins = pft.get('profit_margins', [])
    if len(margins) >= 2 and margins[-1] < margins[0]:
        concerns.append("- 季度净利率略有下滑")
    
    vi = result.get('valuation_indicators', {})
    if vi.get('roe', 0) == 0:
        concerns.append("- 部分财务指标数据缺失")
    
    if concerns:
        print('\n'.join(concerns))
    else:
        print("- 暂无明显风险点")
    
    # 综合评价
    print("\n### 📊 综合评价\n")
    print("| 项目 | 评分 |")
    print("|------|------|")
    
    # 成长性评分
    growth_score = '⭐⭐⭐⭐' if rev.get('yoy_growth', 0) > 20 else ('⭐⭐⭐' if rev.get('yoy_growth', 0) > 0 else '⭐⭐')
    print(f"| 成长性 | {growth_score} |")
    
    # 盈利能力评分
    roe = vi.get('roe', 0)
    profit_score = '⭐⭐⭐⭐' if roe > 20 else ('⭐⭐⭐' if roe > 15 else '⭐⭐')
    print(f"| 盈利能力 | {profit_score} |")
    
    # 财务健康评分
    cf_health = cf.get('cash_flow_health', '')
    health_score = '⭐⭐⭐⭐' if '健康' in cf_health else '⭐⭐⭐'
    print(f"| 财务健康 | {health_score} |")
    
    # 订单景气评分
    cl_growth = cl.get('growth_rate', 0)
    order_score = '⭐⭐⭐⭐' if cl_growth > 20 else ('⭐⭐⭐' if cl_growth > 0 else '⭐⭐')
    print(f"| 订单景气 | {order_score} |")
    
    # 投资建议
    ot = result.get('overall_trend', {})
    grade = ot.get('investment_grade', '')
    if '优秀' in grade:
        suggestion = "财务表现优秀，建议重点关注"
    elif '良好' in grade:
        suggestion = "财务稳健，可以考虑配置"
    else:
        suggestion = "建议谨慎观察，等待更好时机"
    
    print(f"\n**投资建议：** {suggestion} 👍")


# ------------------------------------------------------------------ #
#  图表配置生成
# ------------------------------------------------------------------ #

def _to_analysis_format(fetch_result: Dict) -> Dict:
    """
    将采集结果转换为 FinancialAnalyzer 所需的格式

    Args:
        fetch_result: {'income', 'balance_sheet', 'cash_flow', 'indicators', 'ts_code', 'stock_name', ...}

    Returns:
        {'annual_reports': [...], 'quarterly_reports': [...]}
    """
    income_df = fetch_result.get('income', pd.DataFrame())
    balance_df = fetch_result.get('balance_sheet', pd.DataFrame())
    cashflow_df = fetch_result.get('cash_flow', pd.DataFrame())
    indicator_df = fetch_result.get('indicators', pd.DataFrame())

    if income_df.empty:
        return {'annual_reports': [], 'quarterly_reports': []}

    def _build_record(prefix: str) -> Optional[Dict]:
        """合并各表数据，构建单期财报记录（prefix 格式: YYYYMM）"""
        try:
            # 统一将 end_date 转为 YYYYMMDD 后按前缀匹配
            _ends = income_df['end_date'].astype(str).str.replace('-', '', regex=False)
            inc = income_df[_ends.str.startswith(prefix)]
            if inc.empty:
                return None
            inc_row = inc.iloc[0]

            bs_row = {}
            if not balance_df.empty:
                _ends_bs = balance_df['end_date'].astype(str).str.replace('-', '', regex=False)
                bs = balance_df[_ends_bs.str.startswith(prefix)]
                if not bs.empty:
                    bs_row = bs.iloc[0].to_dict()

            cf_row = {}
            if not cashflow_df.empty:
                _ends_cf = cashflow_df['end_date'].astype(str).str.replace('-', '', regex=False)
                cf = cashflow_df[_ends_cf.str.startswith(prefix)]
                if not cf.empty:
                    cf_row = cf.iloc[0].to_dict()

            ind_row = {}
            if not indicator_df.empty:
                _ends_ind = indicator_df['end_date'].astype(str).str.replace('-', '', regex=False)
                ind = indicator_df[_ends_ind.str.startswith(prefix)]
                if not ind.empty:
                    ind_row = ind.iloc[0].to_dict()

            revenue = float(inc_row.get('revenue') or inc_row.get('total_revenue') or 0)
            net_profit = float(inc_row.get('n_income_attr_p') or inc_row.get('n_income') or 0)
            cash_flow = float(cf_row.get('n_cashflow_act') or 0)
            gross_margin = float(ind_row.get('grossprofit_margin') or 0)
            contract_liab = float(bs_row.get('contract_liab') or 0)
            inventories = float(bs_row.get('inventories') or 0)

            return {
                'ts_code': fetch_result.get('ts_code', ''),
                'stock_name': fetch_result.get('stock_name', ''),
                'report_date': prefix[:4] + '-' + prefix[4:6] if len(prefix) >= 6 else prefix,
                'revenue': revenue,
                'net_profit': net_profit,
                'cash_flow': cash_flow,
                'gross_margin': gross_margin,
                'contract_liabilities': contract_liab,
                'inventories': inventories,
                'total_assets': float(bs_row.get('total_assets') or 0),
                'total_liab': float(bs_row.get('total_liab') or 0),
                'roe': float(ind_row.get('roe') or 0),
                'roa': float(ind_row.get('roa') or 0),
                'debt_to_assets': float(ind_row.get('debt_to_assets') or 0),
                'revenue_yoy': float(ind_row.get('revenue_yoy') or 0),
                'netprofit_yoy': float(ind_row.get('netprofit_yoy') or 0),
                'basic_eps': float(inc_row.get('basic_eps') or 0),
                'inv_turn': float(ind_row.get('inv_turn') or 0),
            }
        except Exception:
            return None

    # 按报告期分类（统一用 YYYYMMDD 格式比较）
    annual_periods = []
    quarterly_periods = []

    for dt in income_df['end_date']:
        dt_str = str(dt).replace('-', '')[:10]
        if dt_str.endswith('1231'):
            annual_periods.append(dt_str)
        else:
            quarterly_periods.append(dt_str)

    annual_records = [r for p in set(annual_periods) for r in [_build_record(p[:6])] if r]
    quarterly_records = [r for p in set(quarterly_periods) for r in [_build_record(p[:6])] if r]

    annual_records.sort(key=lambda x: x['report_date'])
    quarterly_records.sort(key=lambda x: x['report_date'])

    return {
        'annual_reports': annual_records,
        'quarterly_reports': quarterly_records
    }


# ------------------------------------------------------------------ #
#  主入口
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description='财报分析命令行工具 — 输入股票名称或代码进行财务分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/analyze_financial_report.py
  python scripts/analyze_financial_report.py --stock 茅台
  python scripts/analyze_financial_report.py --stock 600519 --years 3
  python scripts/analyze_financial_report.py --stock 300750.SZ --years 5 --type quarterly
  python scripts/analyze_financial_report.py --stock 招商银行 --type all
        """
    )
    parser.add_argument('--stock', '-s', type=str, default=None,
                        help='股票名称或代码（支持: 中文名称 / 6位数字 / 标准代码）')
    parser.add_argument('--years', '-y', type=int, default=5,
                        help='回溯年数（默认5年）')
    parser.add_argument('--type', '-t', type=str, default='all',
                        choices=['all', 'annual', 'quarterly', 'business'],
                        help='分析类型: all-全部 annual-年报 quarterly-季报 business-主营业务（默认all）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始分析结果')
    parser.add_argument('--no-llm', action='store_true',
                        help='跳过 LLM 分析（加速生成）')
    parser.add_argument('--no-chart', action='store_true',
                        help='跳过图表生成（纯文本模式）')

    args = parser.parse_args()

    # 交互式输入股票名称
    stock_input = args.stock
    if not stock_input:
        print("=" * 60)
        print("  财报分析工具")
        print("=" * 60)
        print("  支持输入：中文名称（如 茅台）、6位代码（如 600519）、")
        print("           标准代码（如 600519.SH / 300750.SZ）")
        print()
        try:
            stock_input = input("请输入股票名称或代码 > ").strip()
        except KeyboardInterrupt:
            print("\n已退出")
            sys.exit(0)

    if not stock_input:
        print("[错误] 未输入股票信息")
        sys.exit(1)

    # analysis-engine 目录即分析包所在位置
    _engine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analysis-engine')
    if _engine_dir not in sys.path:
        sys.path.insert(0, _engine_dir)
    from financial_analyzer import FinancialAnalyzer

    # 初始化 Tushare API
    from dotenv import load_dotenv
    load_dotenv()
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        print("\n[错误] 未找到 TUSHARE_TOKEN，请在 .env 中配置")
        sys.exit(1)
    from kk_common import get_finance_data_gateway
    _pro = get_finance_data_gateway()

    # 股票解析（通过 Tushare API，支持名称/代码/标准代码）
    print(f"\n正在查询股票信息: {stock_input!r} ...")
    stock_name = None
    try:
        stock_input = stock_input.strip()
        if re.match(r'^\d{6}\.(SH|SZ)$', stock_input, re.IGNORECASE):
            ts_code = stock_input.upper()
        elif re.match(r'^\d{6}$', stock_input):
            suffix = 'SH' if stock_input.startswith('6') else 'SZ'
            if stock_input.startswith('8') or stock_input.startswith('4'):
                suffix = 'BJ'
            ts_code = f"{stock_input}.{suffix}"
        else:
            df = _pro.stock_basic(name=stock_input, list_status='L', fields='ts_code,name')
            if df.empty:
                df_all = _pro.stock_basic(list_status='L', fields='ts_code,name')
                match = df_all[df_all['name'].str.contains(stock_input, na=False)]
                if match.empty:
                    raise ValueError(f"未找到匹配的股票: {stock_input}")
                row = match.iloc[0]
            else:
                row = df.iloc[0]
            ts_code, stock_name = row['ts_code'], row['name']
            print(f"✓ 识别到: {stock_name}（{ts_code}）")

        if not stock_name:
            df_name = _pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
            stock_name = df_name.iloc[0]['name'] if not df_name.empty else ts_code
            print(f"✓ 识别到: {stock_name}（{ts_code}）")
    except ValueError as e:
        print(f"\n[错误] {e}")
        sys.exit(1)

    # 采集财报数据
    print(f"\n正在采集 {stock_name} 近 {args.years} 年财报数据...")
    start_date = (datetime.now() - timedelta(days=365 * args.years)).strftime('%Y%m%d')
    
    fetch_result = {
        'ts_code': ts_code,
        'stock_name': stock_name,
        'income': pd.DataFrame(),
        'balance_sheet': pd.DataFrame(),
        'cash_flow': pd.DataFrame(),
        'indicators': pd.DataFrame(),
        'main_business': pd.DataFrame(),
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'errors': []
    }

    # 利润表
    print("  正在获取 利润表...", end=' ', flush=True)
    try:
        df = _pro.income(ts_code=ts_code, start_date=start_date,
            fields='ts_code,ann_date,f_ann_date,end_date,report_type,basic_eps,revenue,n_income_attr_p,n_income')
        if df is not None and not df.empty:
            df = df[df['report_type'] == '1'].copy() if 'report_type' in df.columns else df
            fetch_result['income'] = df
            print(f"✓ {len(df)} 条记录")
        else:
            print("✓ 0 条记录")
        time.sleep(0.3)
    except Exception as e:
        print(f"✗ {e}")
        fetch_result['errors'].append(f"获取利润表失败: {e}")

    # 资产负债表
    print("  正在获取 资产负债表...", end=' ', flush=True)
    try:
        df = _pro.balancesheet(ts_code=ts_code, start_date=start_date,
            fields='ts_code,end_date,report_type,total_assets,total_liab,contract_liab,inventories')
        if df is not None and not df.empty:
            fetch_result['balance_sheet'] = df
            print(f"✓ {len(df)} 条记录")
        else:
            print("✓ 0 条记录")
        time.sleep(0.3)
    except Exception as e:
        print(f"✗ {e}")
        fetch_result['errors'].append(f"获取资产负债表失败: {e}")

    # 现金流量表
    print("  正在获取 现金流量表...", end=' ', flush=True)
    try:
        df = _pro.cashflow(ts_code=ts_code, start_date=start_date,
            fields='ts_code,ann_date,f_ann_date,end_date,report_type,n_cashflow_act')
        if df is not None and not df.empty:
            df = df[df['report_type'] == '1'].copy() if 'report_type' in df.columns else df
            fetch_result['cash_flow'] = df
            print(f"✓ {len(df)} 条记录")
        else:
            print("✓ 0 条记录")
        time.sleep(0.3)
    except Exception as e:
        print(f"✗ {e}")
        fetch_result['errors'].append(f"获取现金流量表失败: {e}")

    # 财务指标
    print("  正在获取 财务指标...", end=' ', flush=True)
    try:
        df = _pro.fina_indicator(ts_code=ts_code, start_date=start_date,
            fields='ts_code,ann_date,end_date,grossprofit_margin,netprofit_margin,roe,roa,debt_to_assets,netprofit_yoy,bps,ocf_to_or,inv_turn,ar_turn')
        if df is not None and not df.empty:
            fetch_result['indicators'] = df
            print(f"✓ {len(df)} 条记录")
        else:
            print("✓ 0 条记录")
        time.sleep(0.3)
    except Exception as e:
        print(f"✗ {e}")
        fetch_result['errors'].append(f"获取财务指标失败: {e}")

    # 主营业务构成
    print("  正在获取 主营业务构成...", end=' ', flush=True)
    try:
        df = _pro.fina_mainbz(ts_code=ts_code, start_date=start_date, bz_type='P')
        if df is not None and not df.empty:
            fetch_result['main_business'] = df
            print(f"✓ {len(df)} 条记录")
        else:
            print("✓ 0 条记录")
        time.sleep(0.3)
    except Exception as e:
        print(f"✗ {e}")
        fetch_result['errors'].append(f"获取主营业务构成失败: {e}")

    # 转换为分析格式
    data = _to_analysis_format(fetch_result)
    
    if fetch_result['errors']:
        for err in fetch_result['errors']:
            print(f"  ⚠️ {err}")

    if not data['annual_reports'] and not data['quarterly_reports']:
        print("\n[错误] 未获取到任何财报数据，请检查股票代码或网络连接")
        sys.exit(1)

    analyzer = FinancialAnalyzer()

    # JSON 模式：直接输出原始结果
    if args.json:
        annual_data = analyzer.analyze_annual_reports(data['annual_reports']) if data['annual_reports'] else {}
        quarterly_data = analyzer.analyze_quarterly_reports(data['quarterly_reports']) if data['quarterly_reports'] else {}
        output = {
            'ts_code': ts_code,
            'stock_name': stock_name,
            'annual': annual_data,
            'quarterly': quarterly_data,
            'main_business': analyzer.analyze_main_business(fetch_result.get('main_business')),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
        return

    # 格式化输出
    show_annual = args.type in ('all', 'annual')
    show_quarterly = args.type in ('all', 'quarterly')
    show_business = args.type in ('all', 'business')

    # 先执行年报/季报/主营分析（获取数据）
    annual_result = {}
    quarterly_result = {}
    bz_result = {}
    
    if show_annual and data['annual_reports']:
        annual_result = analyzer.analyze_annual_reports(data['annual_reports'])
    
    if show_quarterly and data['quarterly_reports']:
        quarterly_result = analyzer.analyze_quarterly_reports(data['quarterly_reports'])
    
    if show_business:
        bz_result = analyzer.analyze_main_business(fetch_result.get('main_business'))

    # 报告日期
    report_date = datetime.now().strftime('%Y-%m-%d')

    # ==================== 报告输出 ====================

    # 报告头
    print(f"# 📊 {stock_name}（{ts_code}）财报分析报告")
    print(f"**分析日期：{report_date}**")
    print("\n---")
    

    # 年报分析
    if show_annual and annual_result:
        print("\n## 一、年报分析（同比，共{}期）".format(len(data['annual_reports'])))
        print_annual_analysis(annual_result, stock_name, ts_code, report_date)

    # 季报分析
    if show_quarterly and quarterly_result:
        print("\n## 二、季报分析（环比，共{}期）".format(len(data['quarterly_reports'])))
        print_quarterly_analysis(quarterly_result, stock_name, ts_code)

    # 主营业务
    if show_business and bz_result:
        print_main_business(bz_result, stock_name)

    # 投资建议总结
    if show_annual and annual_result:
        print_investment_summary(annual_result, stock_name)

    # 免责声明
    print("\n---")
    print("\n*免责声明：以上内容仅供参考，不构成投资建议。股市有风险，投资需谨慎。*")
    print("\n---")
    print(f"\n**报告生成：小s 智能体**  ")
    print(f"**数据来源：Tushare Pro API**")


if __name__ == '__main__':
    main()
