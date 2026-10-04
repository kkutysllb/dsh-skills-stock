#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股指期货综合分析工具

数据全部来自 Tushare Pro API，不依赖本地数据库。
覆盖维度：
  - 基本信息：活跃合约、主力合约识别
  - 行情趋势：K线趋势、均线、振幅、OI
  - 贴升水分析：基差/基差率/期限结构/市场情绪
  - 机构持仓：前20大席位多空排名、中信风向标、净持仓信号
  - 综合研判：多维度评分 / 品种分化 / 策略建议

用法:
    python scripts/analyze_futures.py
    python scripts/analyze_futures.py --symbols IF IC
    python scripts/analyze_futures.py --type contango
    python scripts/analyze_futures.py --type holding --symbols IF
    python scripts/analyze_futures.py --type all --days 20
    python scripts/analyze_futures.py --json
"""

import sys
import os
import json
import argparse
import io
from typing import Dict, List, Optional
from datetime import datetime


_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  格式化输出工具
# ======================================================================

def _bar(val: float, max_val: float, width: int = 20,
         fill: str = '█', empty: str = '░') -> str:
    if max_val == 0:
        return empty * width
    filled = int(min(abs(val) / max_val, 1.0) * width)
    return fill * filled + empty * (width - filled)


def _pct(val: float, sign: bool = True) -> str:
    prefix = ('+' if val > 0 else '') if sign else ''
    return f"{prefix}{val:.2f}%"


def _num(val: int) -> str:
    """格式化大数字，加千位分隔"""
    if abs(val) >= 10000:
        return f"{val/10000:.1f}万"
    return f"{val:,}"


def _trend_icon(val: float) -> str:
    return '▲' if val > 0 else '▼' if val < 0 else '─'


SYMBOL_NAME = {
    'IF': '沪深300期货',
    'IC': '中证500期货',
    'IH': '上证50期货',
    'IM': '中证1000期货',
}

SPOT_NAME = {
    'IF': '000300.SH 沪深300',
    'IC': '000905.SH 中证500',
    'IH': '000016.SH 上证50',
    'IM': '000852.SH 中证1000',
}


# ======================================================================

def print_market_overview(result: Dict):
    """打印市场概览（模板格式）"""
    comp = result.get('composite', {})
    if not comp:
        return
    
    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    div_sig = comp.get('divergence_signal', '-')
    bar = _bar(avg_score, 100, 20)
    
    print("\n## 一、市场概览\n")
    print(f"**综合评分：{avg_score:.1f}/100**")
    print(f"{bar}")
    print(f"**市场环境：{market_env}**")
    print(f"**品种分化：{div_sig}**")
    
    # 各品种多维评分
    scores = comp.get('symbol_scores', {})
    details = comp.get('details', {})
    
    if scores:
        print("\n### 各品种多维评分\n")
        print("| 品种 | 代码 | 综合评分 | 趋势判断 | 贴升水情绪 | 净持仓信号 | 中信信号 |")
        print("|------|------|----------|----------|------------|------------|----------|")
        
        for sym in ['IF', 'IC', 'IH', 'IM']:
            if sym not in scores:
                continue
            sc = scores[sym]
            d = details.get(sym, {})
            trend = d.get('trend', '-')[:20]
            senti = d.get('sentiment', '-')
            pos = d.get('position_signal', '-')
            citic = d.get('citic_signal', '-')
            
            score_icon = '▼' if sc <= 42 else '▲' if sc >= 58 else '─'
            score_bar = _bar(sc, 100, 8)
            
            print(f"| {SYMBOL_NAME.get(sym, '')} | {sym} | {score_icon} {sc}/100 {score_bar} | {trend} | {senti} | {pos} | {citic} |")


# ======================================================================
#  逐品种详细分析（模板格式）
# ======================================================================

def print_symbol_analysis(sym: str, sym_data: Dict):
    """打印单个品种的详细分析（模板格式）"""
    
    sym_name = SYMBOL_NAME.get(sym, sym)
    
    print(f"\n### {sym_name}（{sym}）\n")
    
    # 合约信息
    print("#### 合约信息\n")
    c = sym_data.get('contracts', {})
    if 'error' not in c:
        main = c.get('main_contract', '-')
        print(f"**主力合约：** {main}\n")
        
        contracts = c.get('contracts', [])
        if contracts:
            print("| 合约代码 | 乘数 | 到期日 |")
            print("|----------|------|--------|")
            for item in contracts[:4]:
                if isinstance(item, str):
                    # 兼容仅含主力合约代码（无乘数/到期日）的情况
                    print(f"| {item} | - | - |")
                else:
                    print(f"| {item['symbol']} | {item['multiplier']:.0f} | {item['delist_date']} |")
    
    # 1. 行情趋势
    print_price_analysis(sym, sym_data)
    
    # 2. 贴升水分析
    print_contango_analysis(sym, sym_data)
    
    # 3. 机构持仓分析
    print_holding_analysis(sym, sym_data)


def print_price_analysis(sym: str, sym_data: Dict):
    """打印行情趋势分析（模板格式）"""
    p = sym_data.get('price', {})
    if 'error' in p:
        return
    
    print("\n#### 1. 行情趋势\n")
    
    # 价格信息
    print("**价格信息：**\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    
    close = p.get('close', 0)
    settle = p.get('settle', 0)
    pct_chg = p.get('pct_chg', 0)
    trend = p.get('trend', '-')
    
    icon = '📉' if pct_chg < 0 else '📈' if pct_chg > 0 else '➡️'
    
    print(f"| 最新日期 | {p.get('latest_date', '-')} | — |")
    print(f"| 收盘价 | **{close:.2f}** | 最新价格 |")
    print(f"| 结算价 | {settle:.2f} | 当日结算 |")
    print(f"| 涨跌幅 | {icon} **{_pct(pct_chg)}** | 日内涨跌 |")
    print(f"| 趋势判断 | {trend} | 技术形态 |")
    
    # 均线分析
    print("\n**均线分析：**\n")
    print("| 均线 | 数值 | 与收盘价关系 |")
    print("|------|------|--------------|")
    
    ma5 = p.get('ma5', 0)
    ma10 = p.get('ma10', 0)
    ma20 = p.get('ma20', 0)
    
    ma5_rel = '高于MA5' if close > ma5 else '低于MA5'
    ma10_rel = '高于MA10' if close > ma10 else '低于MA10'
    ma20_rel = '高于MA20' if close > ma20 else '低于MA20'
    
    print(f"| MA5 | {ma5:.2f} | {ma5_rel} |")
    print(f"| MA10 | {ma10:.2f} | {ma10_rel} |")
    print(f"| MA20 | {ma20:.2f} | {ma20_rel} |")
    
    # 区间与振幅
    print("\n**区间与振幅：**\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    
    h20 = p.get('high20', 0)
    l20 = p.get('low20', 0)
    amp = p.get('avg_amplitude_10d', 0)
    
    print(f"| 20日最高 | {h20:.2f} | 区间上沿 |")
    print(f"| 20日最低 | {l20:.2f} | 区间下沿 |")
    print(f"| 10日均振幅 | {amp:.2f}% | 波动率 |")
    
    # 持仓与成交
    print("\n**持仓与成交：**\n")
    print("| 指标 | 数值 | 变化/信号 |")
    print("|------|------|-----------|")
    
    oi = p.get('oi', 0)
    oi_chg = p.get('oi_chg', 0)
    oi_trend = p.get('oi_trend', '-')
    vol = p.get('vol', 0)
    vol_5d = p.get('vol_5d_avg', 0)
    vol_sig = p.get('vol_signal', '-')
    
    chg_str = f"{oi_chg:+,}" if oi_chg != 0 else "0"
    print(f"| 持仓量 | {_num(oi)} | {chg_str} ({oi_trend}) |")
    print(f"| 成交量 | {_num(vol)} | 5日均 {_num(vol_5d)} [{vol_sig}] |")
    
    # 近10日走势
    history = p.get('history', [])
    if history:
        print("\n**近10日走势：**\n")
        print("| 日期 | 收盘价 | 结算价 | 成交量 | 持仓量 |")
        print("|------|--------|--------|--------|--------|")
        
        recent = history[-10:]
        for h in recent:
            print(f"| {h.get('date', '-')} | {h.get('close', 0):.2f} | {h.get('settle', 0):.2f} | {_num(h.get('vol', 0))} | {_num(h.get('oi', 0))} |")
    
    # 小s解读
    print("\n**小s解读：**\n")
    
    if abs(pct_chg) < 0.5:
        print(f"- 日内波动较小（{_pct(pct_chg)}），多空均衡")
    elif pct_chg < -1:
        print(f"- 日内下跌{_pct(pct_chg)}，空头占优")
    elif pct_chg > 1:
        print(f"- 日内上涨{_pct(pct_chg)}，多头占优")
    else:
        print(f"- 日内涨跌{_pct(pct_chg)}，波动正常")
    
    if '空头排列' in trend:
        print("- 均线呈空头排列，短期趋势偏弱")
    elif '多头排列' in trend:
        print("- 均线呈多头排列，短期趋势偏强")
    
    if oi_chg < 0:
        print("- 持仓量减少，资金流出，动能减弱")
    elif oi_chg > 0:
        print("- 持仓量增加，资金流入，动能增强")


def print_contango_analysis(sym: str, sym_data: Dict):
    """打印贴升水分析（模板格式）"""
    ct = sym_data.get('contango', {})
    if 'error' in ct:
        return
    
    print("\n#### 2. 贴升水分析（基差）\n")
    
    # 基差概况
    print("**基差概况：**\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    
    spot = ct.get('spot_price', 0)
    near_basis = ct.get('near_basis', 0)
    near_rate = ct.get('near_basis_rate', 0)
    avg_rate = ct.get('avg_basis_rate', 0)
    sentiment = ct.get('sentiment', '-')
    term_str = ct.get('term_structure', '-')
    term_slope = ct.get('term_slope', 0)
    
    contango_icon = '▲ 升水' if near_basis > 0 else '▼ 贴水'
    
    print(f"| 最新日期 | {ct.get('latest_date', '-')} | — |")
    print(f"| 现货指数 | {spot:.2f} | 标的指数 |")
    print(f"| 近月合约 | {ct.get('near_contract', '-')} | 主力合约 |")
    print(f"| 近月基差 | **{near_basis:+.2f}** | 期货-现货 |")
    print(f"| 近月基差率 | **{near_rate:+.4f}%** | 基差/现货 |")
    print(f"| 平均基差率 | {avg_rate:+.4f}% | 历史均值 |")
    print(f"| 市场情绪 | {sentiment} | 基于基差 |")
    print(f"| 期限结构 | {term_str} | 远月价格关系 |")
    print(f"| 期限斜率 | {term_slope:+.4f}% | 近→远变化 |")
    
    # 各合约基差明细
    contracts = ct.get('contracts', [])
    if contracts:
        print("\n**各合约基差明细：**\n")
        print("| 合约 | 结算价 | 基差 | 基差率 | 状态 | 到期月份 |")
        print("|------|--------|------|--------|------|----------|")
        
        for c in contracts[:4]:
            status = '▲ 升水' if c['is_contango'] else '▼ 贴水'
            month = c['symbol'][-4:]
            print(f"| {c['symbol']} | {c['settle']:.2f} | {c['basis']:+.2f} | {c['basis_rate']:+.4f}% | {status} | {month} |")
    
    # 小s解读
    print("\n**小s解读：**\n")
    
    if '强贴水' in sentiment:
        print(f"- 当前强贴水（市场悲观），期货大幅低于现货，反映市场极度谨慎情绪")
    elif '贴水' in sentiment:
        print(f"- 当前贴水（偏谨慎），期货低于现货，市场情绪偏谨慎")
    elif '升水' in sentiment:
        print(f"- 当前升水（偏乐观），期货高于现货，市场情绪偏乐观")
    
    if 'Backwardation' in term_str:
        print("- 期限结构为Backwardation（远月贴水），通常反映现货紧张或悲观预期")
    elif 'Contango' in term_str:
        print("- 期限结构为Contango（远月升水），通常反映现货宽松或乐观预期")


def print_holding_analysis(sym: str, sym_data: Dict):
    """打印机构持仓分析（模板格式）"""
    h = sym_data.get('holding', {})
    if 'error' in h:
        return
    
    print("\n#### 3. 机构持仓分析\n")
    
    # 前20大机构汇总
    print("**前20大机构汇总：**\n")
    print("| 指标 | 持仓量 | 变化 | 说明 |")
    print("|------|--------|------|------|")
    
    total_long = h.get('total_long', 0)
    total_short = h.get('total_short', 0)
    net = h.get('net_position', 0)
    net_chg = h.get('net_chg', 0)
    ls_ratio = h.get('ls_ratio', 0)
    pos_sig = h.get('position_signal', '-')
    chg_sig = h.get('chg_signal', '-')
    
    print(f"| 多头合计 | {_num(total_long)} | — | 前20大席位多头 |")
    print(f"| 空头合计 | {_num(total_short)} | — | 前20大席位空头 |")
    print(f"| 净持仓 | **{_num(net)}** | {net_chg:+,} | 多-空 |")
    print(f"| 多空比 | {ls_ratio:.3f} | — | 多/空 |")
    print(f"| 持仓信号 | {pos_sig} | — | 机构态度 |")
    print(f"| 变化信号 | {chg_sig} | — | 变化趋势 |")
    
    # 中信期货持仓
    citic_long = h.get('citic_long', 0)
    citic_short = h.get('citic_short', 0)
    citic_net = h.get('citic_net', 0)
    citic_net_chg = h.get('citic_net_chg', 0)
    citic_sig = h.get('citic_signal', '-')

    # 其他十九家机构
    others_long = h.get('others_long', 0)
    others_short = h.get('others_short', 0)
    others_net = h.get('others_net', 0)
    others_net_chg = h.get('others_net_chg', 0)
    others_sig = h.get('others_signal', '-')

    # 中信 vs 其他十九家对比
    citic_vs_others = h.get('citic_vs_others_signal', '-')

    print("\n**前20大机构持仓概览：**\n")
    print("| 类型 | 多头持仓 | 空头持仓 | 净持仓 | 净持仓变化 | 信号 |")
    print("|------|----------|----------|--------|------------|------|")
    print(f"| **中信期货** | {_num(citic_long)} | {_num(citic_short)} | **{_num(citic_net)}** | {citic_net_chg:+,} | {citic_sig} |")
    print(f"| **其他十九家** | {_num(others_long)} | {_num(others_short)} | **{_num(others_net)}** | {others_net_chg:+,} | {others_sig} |")
    print(f"| **合计** | {_num(h.get('total_long', 0))} | {_num(h.get('total_short', 0))} | **{_num(net)}** | {net_chg:+,} | {pos_sig} |")

    print(f"\n**中信 vs 其他十九家（基于净持仓水平）：** {citic_vs_others}")

    # ── 新增：中信 vs 其他机构 当日多空单操作变化对比 ──
    chg_analysis = h.get('citic_vs_others_chg_analysis', {})
    if chg_analysis:
        citic_chg = chg_analysis.get('citic', {})
        others_chg = chg_analysis.get('others', {})
        comparison = chg_analysis.get('comparison', {})

        print("\n**中信 vs 其他机构 当日多空单操作变化对比：**\n")
        print("| 对比维度 | 中信期货 | 其他19家 | 对比结论 |")
        print("|----------|----------|----------|----------|")

        # 多单操作变化
        c_lc = citic_chg.get('long_chg', 0)
        o_lc = others_chg.get('long_chg', 0)
        c_la = citic_chg.get('long_action', '未变')
        o_la = others_chg.get('long_action', '未变')
        lcc = comparison.get('long_chg_conclusion', '-')
        print(f"| 多单操作 | {c_lc:+,} ({c_la}) | {o_lc:+,} ({o_la}) | {lcc} |")

        # 空单操作变化
        c_sc = citic_chg.get('short_chg', 0)
        o_sc = others_chg.get('short_chg', 0)
        c_sa = citic_chg.get('short_action', '未变')
        o_sa = others_chg.get('short_action', '未变')
        scc = comparison.get('short_chg_conclusion', '-')
        print(f"| 空单操作 | {c_sc:+,} ({c_sa}) | {o_sc:+,} ({o_sa}) | {scc} |")

        # 净变化
        c_nc = citic_chg.get('net_chg', 0)
        o_nc = others_chg.get('net_chg', 0)
        c_nd = citic_chg.get('net_dir', '未变')
        o_nd = others_chg.get('net_dir', '未变')
        ncc = comparison.get('net_chg_conclusion', '-')
        print(f"| 净变化 | {c_nc:+,} ({c_nd}) | {o_nc:+,} ({o_nd}) | {ncc} |")

        # 综合信号
        overall = comparison.get('overall_signal', '-')
        print(f"\n**综合判断：{overall}**")
        if '分歧' in overall:
            print("⚠️ 中信与其他机构操作方向相反，多空分歧加大，市场可能面临方向选择")
        elif '一致' in overall:
            print("✅ 中信与其他机构操作方向一致，信号共振，趋势参考价值较高")
        elif '观望' in overall or '未变' in overall or '不明' in overall:
            print("➖ 中信或其他机构无明显操作，需关注后续变化")

    print("\n**中信期货持仓（市场风向标）：**\n")
    print("| 类型 | 持仓量 | 净持仓 | 变化 | 信号 |")
    print("|------|--------|--------|------|------|")
    print(f"| 多头 | {_num(citic_long)} | — | {h.get('citic_long_chg', 0):+,} | — |")
    print(f"| 空头 | {_num(citic_short)} | — | {h.get('citic_short_chg', 0):+,} | — |")
    print(f"| 净持仓 | — | **{_num(citic_net)}** | {citic_net_chg:+,} | {citic_sig} |")

    print("\n**其他十九家机构持仓：**\n")
    print("| 类型 | 持仓量 | 净持仓 | 变化 | 信号 |")
    print("|------|--------|--------|------|------|")
    print(f"| 多头 | {_num(others_long)} | — | {h.get('others_long_chg', 0):+,} | — |")
    print(f"| 空头 | {_num(others_short)} | — | {h.get('others_short_chg', 0):+,} | — |")
    print(f"| 净持仓 | — | **{_num(others_net)}** | {others_net_chg:+,} | {others_sig} |")

    # 多头前10席位
    top_long = h.get('top10_long', [])
    if top_long:
        print("\n**多头前10席位：**\n")
        print("| 排名 | 机构 | 多头持仓 | 变化 |")
        print("|------|------|----------|------|")
        
        for i, row in enumerate(top_long, 1):
            chg = row['long_chg']
            chg_str = f"{chg:+,}" if chg != 0 else "0"
            print(f"| {i} | {row['broker']} | {_num(row['long_hld'])} | {chg_str} |")
    
    # 空头前10席位
    top_short = h.get('top10_short', [])
    if top_short:
        print("\n**空头前10席位：**\n")
        print("| 排名 | 机构 | 空头持仓 | 变化 |")
        print("|------|------|----------|------|")
        
        for i, row in enumerate(top_short, 1):
            chg = row['short_chg']
            chg_str = f"{chg:+,}" if chg != 0 else "0"
            print(f"| {i} | {row['broker']} | {_num(row['short_hld'])} | {chg_str} |")

    # ── 中信 vs 其余机构每日多空单操作变化对比 ──
    daily_trends = h.get('daily_trends', [])
    if daily_trends and len(daily_trends) > 1:
        print("\n**中信 vs 其余机构每日操作变化对比：**\n")
        print("| 日期 | 中信多单变化 | 中信空单变化 | 中信净变化 | 其余多单变化 | 其余空单变化 | 其余净变化 | 对比信号 |")
        print("|------|-------------|-------------|-----------|-------------|-------------|-----------|----------|")
        for dt in daily_trends:
            dt_date = dt.get('trade_date', '')
            if len(dt_date) == 8:
                dt_date = f"{dt_date[:4]}-{dt_date[4:6]}-{dt_date[6:]}"

            c_lc = dt.get('citic_long_chg', 0)
            c_sc = dt.get('citic_short_chg', 0)
            c_nc = dt.get('citic_net_chg', 0)
            o_lc = dt.get('others_long_chg', 0)
            o_sc = dt.get('others_short_chg', 0)
            o_nc = dt.get('others_net_chg', 0)

            if c_nc > 0 and o_nc < 0:
                dt_signal = '中信偏多/其余偏空'
            elif c_nc < 0 and o_nc > 0:
                dt_signal = '中信偏空/其余偏多'
            elif c_nc > 0 and o_nc > 0:
                dt_signal = '同向偏多'
            elif c_nc < 0 and o_nc < 0:
                dt_signal = '同向偏空'
            else:
                dt_signal = '中性'

            print(f"| {dt_date} | {c_lc:+,} | {c_sc:+,} | **{c_nc:+,}** | {o_lc:+,} | {o_sc:+,} | **{o_nc:+,}** | {dt_signal} |")

    # 小s解读
    print("\n**小s解读：**\n")

    # 中信 vs 其他十九家对比解读
    if '背离' in citic_vs_others:
        print(f"- **中信 vs 其他十九家信号背离**：{citic_vs_others}，需重点关注分歧背后的原因")
    elif '一致' in citic_vs_others:
        print(f"- 中信与其他十九家机构同向操作，信号一致性较强")

    if net < -5000:
        print(f"- 机构净空头{_num(abs(net))}手，净空头显著（机构偏空），做空力量较强")
    elif net < 0:
        print(f"- 机构净空头{_num(abs(net))}手，净空头（偏空）")
    elif net > 5000:
        print(f"- 机构净多头{_num(net)}手，净多头显著（机构偏多），做多力量较强")
    elif net > 0:
        print(f"- 机构净多头{_num(net)}手，净多头（偏多）")
    else:
        print(f"- 机构净持仓接近平衡，多空力量均衡")

    if citic_net < -2000:
        print(f"- 中信期货净持仓{_num(citic_net)}手，偏空信号，作为市场风向标，需警惕")
    elif citic_net > 2000:
        print(f"- 中信期货净持仓{_num(citic_net)}手，偏多信号，作为市场风向标，值得关注")

    if others_net < -2000:
        print(f"- 其他十九家净持仓{_num(others_net)}手，整体偏空，与中信{'一致' if citic_net < 0 else '背离'}")
    elif others_net > 2000:
        print(f"- 其他十九家净持仓{_num(others_net)}手，整体偏多，与中信{'一致' if citic_net > 0 else '背离'}")


# ======================================================================
#  分品种对比输出（中信 vs 其他机构，模板格式）
# ======================================================================

def print_cross_symbol_holding_comparison(result: Dict):
    """打印中信 vs 其他机构 分品种对比分析

    汇总 IF/IC/IH/IM 四个品种的中信 vs 其他机构（汇总）在多空单持仓、
    当日/每周多空单操作变化，形成跨品种对比表，作为最终报告的必含章节。
    """
    symbols = result.get('symbols', {})
    rows = []
    for sym in ['IF', 'IC', 'IH', 'IM']:
        sym_data = symbols.get(sym, {})
        h = sym_data.get('holding', {})
        if not h or 'error' in h:
            continue
        rows.append((sym, h))
    if not rows:
        return

    print("\n## 三、中信 vs 其他机构 分品种对比\n")

    # ── 1. 分品种多空单持仓对比 ──
    print("### 1. 分品种多空单持仓对比\n")
    print("| 品种 | 中信多头 | 中信空头 | 中信净持仓 | 中信信号 | 其他多头 | 其他空头 | 其他净持仓 | 其他信号 | 方向对比 |")
    print("|------|----------|----------|-----------|----------|----------|----------|-----------|----------|----------|")
    for sym, h in rows:
        c_net = h.get('citic_net', 0)
        o_net = h.get('others_net', 0)
        c_sig = h.get('citic_signal', '-')
        o_sig = h.get('others_signal', '-')
        cvo = h.get('citic_vs_others_signal', '-')
        print(f"| **{sym}** | {_num(h.get('citic_long', 0))} | {_num(h.get('citic_short', 0))} | "
              f"**{_num(c_net)}** | {c_sig} | {_num(h.get('others_long', 0))} | "
              f"{_num(h.get('others_short', 0))} | **{_num(o_net)}** | {o_sig} | {cvo} |")

    # ── 2. 分品种当日多空单操作变化对比 ──
    print("\n### 2. 分品种当日多空单操作变化对比\n")
    print("| 品种 | 中信多单 | 中信空单 | 中信净变化 | 其他多单 | 其他空单 | 其他净变化 | 综合判断 |")
    print("|------|----------|----------|-----------|----------|----------|-----------|----------|")
    for sym, h in rows:
        ca = h.get('citic_vs_others_chg_analysis', {})
        c = ca.get('citic', {})
        o = ca.get('others', {})
        overall = ca.get('comparison', {}).get('overall_signal', '-')
        print(f"| **{sym}** | {c.get('long_chg', 0):+,} ({c.get('long_action', '-')}) | "
              f"{c.get('short_chg', 0):+,} ({c.get('short_action', '-')}) | "
              f"**{c.get('net_chg', 0):+,}** ({c.get('net_dir', '-')}) | "
              f"{o.get('long_chg', 0):+,} ({o.get('long_action', '-')}) | "
              f"{o.get('short_chg', 0):+,} ({o.get('short_action', '-')}) | "
              f"**{o.get('net_chg', 0):+,}** ({o.get('net_dir', '-')}) | {overall} |")

    # ── 3. 分品种每周多空单操作变化对比 ──
    print("\n### 3. 分品种每周多空单操作变化对比（近5个交易日累计）\n")
    print("| 品种 | 中信多单 | 中信空单 | 中信净变化 | 其他多单 | 其他空单 | 其他净变化 | 周度综合判断 |")
    print("|------|----------|----------|-----------|----------|----------|-----------|-------------|")
    for sym, h in rows:
        wk = h.get('weekly_chg_analysis', {})
        c = wk.get('citic', {})
        o = wk.get('others', {})
        overall = wk.get('comparison', {}).get('overall_signal', '-')
        print(f"| **{sym}** | {c.get('long_chg', 0):+,} | {c.get('short_chg', 0):+,} | "
              f"**{c.get('net_chg', 0):+,}** | {o.get('long_chg', 0):+,} | {o.get('short_chg', 0):+,} | "
              f"**{o.get('net_chg', 0):+,}** | {overall} |")

    # ── 4. 分品种每日净变化对比（中信 vs 其他） ──
    print("\n### 4. 分品种每日净变化对比（中信/其他）\n")
    print("| 日期 | IF中信 | IF其他 | IC中信 | IC其他 | IH中信 | IH其他 | IM中信 | IM其他 |")
    print("|------|--------|--------|--------|--------|--------|--------|--------|--------|")
    trends = {}
    for sym, h in rows:
        dt = h.get('daily_trends', [])
        for item in dt:
            d = item.get('trade_date', '')
            if len(d) == 8:
                d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            trends.setdefault(d, {})[sym] = item
    for d in sorted(trends.keys()):
        cells = []
        for sym in ['IF', 'IC', 'IH', 'IM']:
            item = trends[d].get(sym)
            if item is None:
                cells.append('-')
                cells.append('-')
            else:
                cells.append(f"{item.get('citic_net_chg', 0):+,}")
                cells.append(f"{item.get('others_net_chg', 0):+,}")
        print(f"| {d} | " + " | ".join(cells) + " |")

    # ── 5. 分品种对比小结 ──
    print("\n### 5. 分品种对比小结\n")
    for sym, h in rows:
        ca = h.get('citic_vs_others_chg_analysis', {})
        overall = ca.get('comparison', {}).get('overall_signal', '-')
        cvo = h.get('citic_vs_others_signal', '-')
        if '分歧' in overall or '分歧' in cvo:
            print(f"- **{sym}**：中信与其他机构操作方向分歧，需重点关注分歧背后的原因")
        elif '一致' in overall or '同向' in cvo:
            print(f"- **{sym}**：中信与其他机构操作方向一致，信号共振，趋势参考价值较高")
        elif '观望' in overall or '未变' in overall or '不明' in overall:
            print(f"- **{sym}**：中信或其他机构无明显操作，需关注后续变化")
        else:
            print(f"- **{sym}**：{cvo}（持仓），当日操作{overall}（变化）")


# ======================================================================
#  综合研判输出（模板格式）
# ======================================================================

def print_composite_analysis(result: Dict):
    """打印综合研判（模板格式）"""
    comp = result.get('composite', {})
    if not comp:
        return
    
    details = comp.get('details', {})
    
    print("\n## 四、综合研判\n")
    
    # 积极信号
    print("### 积极信号\n")
    print("| 品种 | 信号类型 | 说明 |")
    print("|------|----------|------|")
    
    positive_count = 0
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
        
        # 检查是否有积极信号
        if d.get('citic_signal') == '偏多':
            print(f"| {SYMBOL_NAME.get(sym, '')} | 中信信号 | 偏多 |")
            positive_count += 1
        
        if '升水' in d.get('sentiment', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 基差信号 | {d.get('sentiment', '')} |")
            positive_count += 1
        
        if d.get('position_signal') and '多头' in d.get('position_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 持仓信号 | {d.get('position_signal', '')} |")
            positive_count += 1
    
    if positive_count == 0:
        print("| — | — | 当前市场暂无明确积极信号 |")
    
    # 风险信号
    print("\n### 风险信号\n")
    print("| 品种 | 风险类型 | 说明 |")
    print("|------|----------|------|")
    
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
        
        # 检查是否有风险信号
        if '贴水' in d.get('sentiment', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 基差风险 | {d.get('sentiment', '')} |")
        
        if d.get('position_signal') and '空头' in d.get('position_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 持仓风险 | {d.get('position_signal', '')} |")
        
        if d.get('citic_signal') == '偏空':
            print(f"| {SYMBOL_NAME.get(sym, '')} | 中信风险 | {d.get('citic_signal', '')} |")
        
        # 检查价格风险
        p = result['symbols'].get(sym, {}).get('price', {})
        if p.get('pct_chg', 0) < -1:
            print(f"| {SYMBOL_NAME.get(sym, '')} | 价格风险 | 下跌 {_pct(p.get('pct_chg', 0))} |")
        
        if '空头排列' in d.get('trend', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 趋势风险 | {d.get('trend', '')} |")

        # 中信 vs 其他十九家信号
        cvo = d.get('citic_vs_others_signal', '')
        if cvo and cvo != '未知' and '背离' in cvo:
            print(f"| {SYMBOL_NAME.get(sym, '')} | 机构分歧 | {cvo} |")


# ======================================================================
#  投资建议输出（模板格式）
# ======================================================================

def print_investment_suggestions(result: Dict):
    """打印投资建议（模板格式）"""
    comp = result.get('composite', {})
    if not comp:
        return
    
    suggestions = comp.get('suggestions', [])
    
    print("\n## 五、投资建议\n")
    
    if suggestions:
        print("| 序号 | 策略建议 |")
        print("|------|----------|")
        for i, s in enumerate(suggestions, 1):
            print(f"| {i} | {s} |")
    else:
        print("暂无明确策略建议。")


# ======================================================================
#  小s总结输出（模板格式）
# ======================================================================

def print_xiaos_summary(result: Dict):
    """打印小s的总结（模板格式）"""
    comp = result.get('composite', {})
    if not comp:
        return
    
    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    details = comp.get('details', {})
    
    print("\n## 六、小s的总结\n")
    
    print("### 关键结论：\n")
    
    # 各品种结论
    conclusions = []
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
        p = result['symbols'].get(sym, {}).get('price', {})
        
        pct_chg = p.get('pct_chg', 0)
        trend = d.get('trend', '-')
        
        icon = '📉' if pct_chg < 0 else '📈' if pct_chg > 0 else '➡️'
        conclusions.append(f"**{SYMBOL_NAME.get(sym, '')}（{sym}）：** {icon} 涨跌 {_pct(pct_chg)}，{trend}")
    
    for idx, c in enumerate(conclusions, 1):
        print(f"{idx}. {c}")

    # 机构持仓（含中信 vs 其他十九家）
    # 检查是否有背离情况
    divergence_count = 0
    divergence_details = []
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
        cvo = d.get('citic_vs_others_signal', '')
        if cvo and '背离' in cvo:
            divergence_count += 1
            divergence_details.append(f"{sym}: {cvo}")

    citic_info = f"中信期货{'偏空' if avg_score < 50 else '偏多'}信号明显"
    if divergence_count > 0:
        citic_info += f"，且存在机构分歧（{'；'.join(divergence_details)}）"

    print(f"\n2. **机构持仓：** 四大期指全线{'净空头' if avg_score < 50 else '净多头'}，{citic_info}，机构{'做空' if avg_score < 50 else '做多'}意图较强")

    # 基差结构
    print(f"3. **基差结构：** 整体呈现{'强贴水' if avg_score < 50 else '升水'}状态，市场情绪偏{'悲观' if avg_score < 50 else '乐观'}，投资者{'谨慎' if avg_score < 50 else '乐观'}情绪浓厚")
    
    # 综合评分
    print(f"4. **综合评分：** {avg_score:.1f}/100，{market_env}")
    
    # 特别注意
    print("\n### 特别注意：\n")
    
    if avg_score < 30:
        print("- ⚠️ 期指交易杠杆高，风险大，严格止损")
        print("- ⚠️ 关注机构持仓变化，特别是中信期货动向")
        print("- ⚠️ 基差贴水扩大需警惕，可能预示进一步下跌")
        print("- ⚠️ 品种走势一致，无明显分化，系统性风险较高")
    elif avg_score < 50:
        print("- ⚠️ 期指交易杠杆高，风险大，注意止损")
        print("- ⚠️ 关注机构持仓变化，特别是中信期货动向")
        print("- ⚠️ 基差贴水需关注，市场情绪偏谨慎")
    else:
        print("- ✅ 市场情绪偏乐观，但仍需注意风险控制")
        print("- ✅ 关注机构持仓变化，特别是中信期货动向")
        print("- ✅ 基差升水需关注，市场情绪偏乐观")


# ======================================================================
#  图表配置生成
# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='股指期货综合分析工具 — 基于 Tushare Pro API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
分析类型说明:
  all       — 全量分析（行情 + 贴升水 + 持仓 + 综合研判）
  price     — K线行情趋势分析
  contango  — 贴升水/期限结构分析
  holding   — 机构持仓排名分析
  composite — 仅输出综合评分与研判

示例:
  python scripts/analyze_futures.py
  python scripts/analyze_futures.py --symbols IF IC
  python scripts/analyze_futures.py --type contango
  python scripts/analyze_futures.py --type holding --symbols IF
  python scripts/analyze_futures.py --type all --days 30
  python scripts/analyze_futures.py --json
        """
    )
    parser.add_argument('--symbols', '-s', nargs='+', default=['IF', 'IC', 'IH', 'IM'],
                        choices=['IF', 'IC', 'IH', 'IM'],
                        help='分析品种（默认全部）')
    parser.add_argument('--type', '-t', type=str, default='all',
                        choices=['all', 'price', 'contango', 'holding', 'composite'],
                        help='分析类型（默认 all）')
    parser.add_argument('--days', '-d', type=int, default=30,
                        help='行情回溯天数（默认30）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始分析结果')

    args = parser.parse_args()

    # 导入分析模块
    from analysis.futures_analyzer import FuturesDataFetcher, FuturesAnalyzer

    fetcher = FuturesDataFetcher()
    analyzer = FuturesAnalyzer(fetcher)

    print(f"正在采集期货数据...\n")
    result = analyzer.analyze_all(symbols=args.symbols, days=args.days)

    # JSON 输出模式：直接打印原始分析结果并退出
    if args.json:
        def _default_serializer(obj):
            # 处理不可直接序列化的类型（如 datetime/date/Decimal）
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'item'):  # numpy 标量
                return obj.item()
            return str(obj)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default_serializer))
        return

    # 一、市场概览
    print_market_overview(result)

    # 二、逐品种详细分析
    print("\n## 二、逐品种详细分析\n")

    for sym in args.symbols:
        sym_data = result['symbols'].get(sym, {})
        if not sym_data:
            continue

        print_symbol_analysis(sym, sym_data)

    # 三、中信 vs 其他机构 分品种对比
    print_cross_symbol_holding_comparison(result)

    # 四、综合研判
    print_composite_analysis(result)

    # 五、投资建议
    print_investment_suggestions(result)

    # 六、小s的总结
    print_xiaos_summary(result)

    # 免责声明
    print("\n---")
    print("\n*免责声明：以上期货分析仅供参考，不构成投资建议。期货有风险，投资需谨慎。*")
    print("\n---")
    print(f"\n**报告生成：小s 智能体**  ")
    print(f"**数据来源：Tushare Pro API**")

    # 保存报告
if __name__ == '__main__':
    main()
