#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股指期货周度综合分析工具（模板格式）

数据来源：Tushare Pro API
分析维度：行情趋势 / 贴升水分析 / 机构持仓 / 综合研判

用法:
  python scripts/analyze_weekly_futures.py              # 分析上周（自动推算）
  python scripts/analyze_weekly_futures.py --weeks 1    # 分析上上周
  python scripts/analyze_weekly_futures.py --json       # JSON 输出
"""

import sys
import os
import json
import argparse
import io
import re
from datetime import datetime
from typing import Dict


_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 复用日度脚本的分品种对比章节（中信 vs 其他机构）
try:
    from analyze_futures import print_cross_symbol_holding_comparison
except Exception:
    def print_cross_symbol_holding_comparison(result):  # 兜底：不输出
        pass


# ======================================================================
#  颜色配置
# ======================================================================


SYMBOL_NAME = {
    'IF': '沪深300期货',
    'IC': '中证500期货',
    'IH': '上证50期货',
    'IM': '中证1000期货',
}


# ======================================================================
#  格式化工具
# ======================================================================

def _bar(val, max_val, width=20, fill='█', empty='░'):
    if max_val == 0:
        return empty * width
    filled = int(min(abs(val) / max_val, 1.0) * width)
    return fill * filled + empty * (width - filled)


def _num(val):
    if abs(val) >= 10000:
        return f"{val / 10000:.1f}万"
    return f"{val:,}"


def _chg(v):
    if v is None:
        return '—'
    icon = '▲' if v > 0 else '▼' if v < 0 else '─'
    return f"{icon} {v:+.2f}%"


def _pct(val, sign=True):
    prefix = ('+' if val > 0 else '') if sign else ''
    return f"{prefix}{val:.2f}%"


def _score_bar(score, width=20):
    n = max(0, min(width, int(score / 100 * width)))
    return '█' * n + '░' * (width - n)


def _detect_contract_switch(fetcher, sym: str, week_days: list):
    """检测周窗口内主力合约是否切换

    fut_mapping 返回全市场合约映射（ts_code 为连续合约代码，mapping_ts_code
    为该连续合约映射的实际合约），同一交易日有多行映射，按日取众数作为当日
    主力，窗口内主力序列多于 1 个即视为周内切换。
    """
    pro = getattr(fetcher, 'pro', None)
    if pro is None or not week_days:
        return None
    try:
        df = pro.fut_mapping(symbol=sym)
        if df is None or df.empty or 'mapping_ts_code' not in df.columns:
            return None
        filtered = df[df['ts_code'].astype(str).str.startswith(sym)].copy()
        if filtered.empty:
            return None

        def _fmt(td):
            td = str(td)
            return f"{td[:4]}-{td[4:6]}-{td[6:]}" if len(td) == 8 else td

        filtered['_date'] = filtered['trade_date'].map(_fmt)
        in_window = filtered[(filtered['_date'] >= week_days[0]) &
                             (filtered['_date'] <= week_days[-1])]
        if in_window.empty:
            return None
        from collections import Counter
        daily_codes = in_window.groupby('_date')['mapping_ts_code'].apply(
            lambda s: Counter(s.dropna().tolist()).most_common(1)[0][0]
            if s.notna().any() else None)
        codes = [c for c in daily_codes.tolist() if c]
        if not codes:
            return None
        if len(set(codes)) > 1:
            return f"周内主力切换：{' → '.join(dict.fromkeys(codes))}"
        return f"主力合约 {codes[0]}，周内未切换"
    except Exception:
        return None


# ======================================================================
#  模板格式打印 — 市场概览
# ======================================================================

def print_market_overview(result: Dict, week_start: str, week_end: str, week_days: list):
    comp = result.get('composite', {})
    if not comp:
        return

    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    div_sig = comp.get('divergence_signal', '-')
    bar = _score_bar(avg_score)

    print("\n## 一、市场概览\n")
    print(f"**分析周期：{week_start} ~ {week_end}（{len(week_days)}个交易日）**\n")
    print(f"**综合评分：{avg_score:.1f}/100**")
    print(f"{bar}")
    print(f"**市场环境：{market_env}**")
    print(f"**品种分化：{div_sig}**")

    scores = comp.get('symbol_scores', {})
    details = comp.get('details', {})

    if scores:
        print("\n### 各品种多维评分\n")
        print("| 品种 | 代码 | 综合评分 | 周涨跌 | 贴升水情绪 | 净持仓信号 | 中信信号 |")
        print("|------|------|----------|--------|------------|------------|----------|")

        for sym in ['IF', 'IC', 'IH', 'IM']:
            if sym not in scores:
                continue
            sc = scores[sym]
            d = details.get(sym, {})
            trend = d.get('trend', '-')[:20]
            senti = d.get('sentiment', '-')
            pos = d.get('position_signal', '-')
            citic = d.get('citic_signal', '-')
            week_chg = d.get('week_chg')  # 缺失时输出 —（不再包装为 0）

            score_icon = '▼' if sc <= 42 else '▲' if sc >= 58 else '─'
            score_bar = _bar(sc, 100, 8)

            print(f"| {SYMBOL_NAME.get(sym, '')} | {sym} | {score_icon} {sc}/100 {score_bar} "
                  f"| {_chg(week_chg)} | {senti} | {pos} | {citic} |")


# ======================================================================
#  模板格式打印 — 逐品种详细分析
# ======================================================================

def print_symbol_analysis(sym: str, sym_data: Dict, week_days: list):
    sym_name = SYMBOL_NAME.get(sym, sym)
    print(f"\n### {sym_name}（{sym}）\n")

    # 1. 行情趋势
    print_price_analysis(sym, sym_data, week_days)
    # 2. 贴升水分析
    print_contango_analysis(sym, sym_data)
    # 3. 机构持仓
    print_holding_analysis(sym, sym_data)


def print_price_analysis(sym: str, sym_data: Dict, week_days: list):
    p = sym_data.get('price', {})
    if 'error' in p:
        return

    print("\n#### 1. 行情趋势\n")

    week_chg = p.get('week_chg', 0)
    trend = p.get('trend', '-')
    oi_trend = p.get('oi_trend', '-')
    week_oi_chg = p.get('week_oi_chg', 0)

    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    print(f"| 全周涨跌幅 | {_chg(week_chg)} | 周度涨跌 |")
    print(f"| 趋势判断 | {trend} | 技术形态 |")
    print(f"| OI变化 | {week_oi_chg:+,} 手 | {oi_trend} |")
    main_contract = p.get('main_contract', '-')
    contract_switch = p.get('contract_switch')
    switch_str = contract_switch if contract_switch else '主力合约信息缺失'
    print(f"| 主力合约 | {main_contract} | {switch_str} |")

    # 逐日走势
    daily = p.get('daily', [])
    if daily:
        daily = daily[-5:]  # 周度：仅最近 5 个交易日
        print("\n**逐日走势（最近5个交易日）：**\n")
        print("| 日期 | 收盘价 | 结算价 | 涨跌幅 | 成交量 | 持仓量 | OI变化 |")
        print("|------|--------|--------|--------|--------|--------|--------|")
        for d in daily:
            print(f"| {d['date']} | {d['close']:.2f} | {d['settle']:.2f} "
                  f"| {_chg(d['pct_chg'])} | {_num(d['vol'])} | {_num(d['oi'])} "
                  f"| {d['oi_chg']:+,} |")

    # 小s解读
    print("\n**小s解读：**\n")
    if week_chg > 2:
        print(f"- 全周强势上涨{_chg(week_chg)}，多头主导")
    elif week_chg > 0:
        print(f"- 全周小幅上涨{_chg(week_chg)}，多空拉锯")
    elif week_chg > -2:
        print(f"- 全周小幅下跌{_chg(week_chg)}，偏弱震荡")
    else:
        print(f"- 全周明显下跌{_chg(week_chg)}，空头主导")

    if '增仓' in oi_trend and week_chg > 0:
        print("- 价升量增，趋势动能较强")
    elif '减仓' in oi_trend and week_chg < 0:
        print("- 价跌量减，空头动能减弱但方向未改")


def print_contango_analysis(sym: str, sym_data: Dict):
    ct = sym_data.get('contango', {})
    if 'error' in ct:
        return

    print("\n#### 2. 贴升水分析（基差）\n")

    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")

    spot = ct.get('spot_price', 0)
    near_basis = ct.get('near_basis', 0)
    near_rate = ct.get('near_basis_rate', 0)
    avg_rate = ct.get('avg_basis_rate', 0)
    week_avg = ct.get('week_avg_basis_pct')
    sentiment = ct.get('sentiment', '-')
    term_str = ct.get('term_structure', '-')
    basis_sig = ct.get('basis_signal', '-')

    print(f"| 现货指数 | {spot:.2f} | 标的指数 |")
    print(f"| 近月基差 | **{near_basis:+.2f}** | 期货-现货 |")
    print(f"| 近月基差率 | **{near_rate:+.4f}%** | 基差/现货 |")
    if week_avg is not None:
        print(f"| 周均基差率 | **{week_avg:+.3f}%** | 全周均值（5个交易日） |")
    else:
        print("| 周均基差率 | — | 数据缺失 |")
    print(f"| 市场情绪 | {sentiment} | 基于基差 |")
    print(f"| 期限结构 | {term_str} | 远月关系 |")
    print(f"| 基差信号 | {basis_sig} | — |")

    # 逐日基差
    daily = ct.get('daily', [])
    if daily:
        print("\n**逐日基差率：**\n")
        print("| 日期 | 基差 | 基差率 |")
        print("|------|------|--------|")
        for d in daily:
            print(f"| {d['date']} | {d['basis']:+.2f} | {d['basis_pct']:+.4f}% |")

    # 小s解读
    print("\n**小s解读：**\n")
    if '强贴水' in sentiment:
        print("- 当前强贴水，期货大幅低于现货，市场极度谨慎")
    elif '贴水' in sentiment:
        print("- 当前贴水，期货低于现货，市场情绪偏谨慎")
    elif '升水' in sentiment:
        print("- 当前升水，期货高于现货，市场情绪偏乐观")


def print_holding_analysis(sym: str, sym_data: Dict):
    h = sym_data.get('holding', {})
    if 'error' in h:
        return

    print("\n#### 3. 机构持仓分析\n")

    net = h.get('net_position', 0)
    net_chg = h.get('net_chg', 0)
    ls_ratio = h.get('ls_ratio', 0)
    pos_sig = h.get('position_signal', '-')

    # 中信期货
    citic_long = h.get('citic_long', 0)
    citic_short = h.get('citic_short', 0)
    citic_net = h.get('citic_net', 0)
    citic_net_chg = h.get('citic_net_chg', 0)
    citic_sig = h.get('citic_signal', '-')

    # 其他十九家
    others_long = h.get('others_long', 0)
    others_short = h.get('others_short', 0)
    others_net = h.get('others_net', 0)
    others_net_chg = h.get('others_net_chg', 0)
    others_sig = h.get('others_signal', '-')

    # 中信 vs 其他十九家
    citic_vs_others = h.get('citic_vs_others_signal', '-')

    print("**前20大机构持仓概览：**\n")
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

        c_lc = citic_chg.get('long_chg', 0)
        o_lc = others_chg.get('long_chg', 0)
        c_la = citic_chg.get('long_action', '未变')
        o_la = others_chg.get('long_action', '未变')
        lcc = comparison.get('long_chg_conclusion', '-')
        print(f"| 多单操作 | {c_lc:+,} ({c_la}) | {o_lc:+,} ({o_la}) | {lcc} |")

        c_sc = citic_chg.get('short_chg', 0)
        o_sc = others_chg.get('short_chg', 0)
        c_sa = citic_chg.get('short_action', '未变')
        o_sa = others_chg.get('short_action', '未变')
        scc = comparison.get('short_chg_conclusion', '-')
        print(f"| 空单操作 | {c_sc:+,} ({c_sa}) | {o_sc:+,} ({o_sa}) | {scc} |")

        c_nc = citic_chg.get('net_chg', 0)
        o_nc = others_chg.get('net_chg', 0)
        c_nd = citic_chg.get('net_dir', '未变')
        o_nd = others_chg.get('net_dir', '未变')
        ncc = comparison.get('net_chg_conclusion', '-')
        print(f"| 净变化 | {c_nc:+,} ({c_nd}) | {o_nc:+,} ({o_nd}) | {ncc} |")

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

    # ── 中信 vs 其余机构每周多空单操作变化对比（近5个交易日累计） ──
    wk = h.get('weekly_chg_analysis', {})
    if wk:
        c_w = wk.get('citic', {})
        o_w = wk.get('others', {})
        w_comp = wk.get('comparison', {})
        print("\n**中信 vs 其余机构每周操作变化对比（近5个交易日累计）：**\n")
        print("| 类型 | 多单累计 | 空单累计 | 净变化累计 | 结论 |")
        print("|------|----------|----------|-----------|------|")
        print(f"| 中信期货 | {c_w.get('long_chg', 0):+,} | {c_w.get('short_chg', 0):+,} | "
              f"**{c_w.get('net_chg', 0):+,}** | {w_comp.get('net_chg_conclusion', '-')} |")
        print(f"| 其他19家 | {o_w.get('long_chg', 0):+,} | {o_w.get('short_chg', 0):+,} | "
              f"**{o_w.get('net_chg', 0):+,}** | — |")
        overall = w_comp.get('overall_signal', '-')
        print(f"\n**周度综合判断：{overall}**")
        if '分歧' in overall:
            print("⚠️ 本周中信与其他机构操作方向相反，多空分歧加大")
        elif '一致' in overall:
            print("✅ 本周中信与其他机构操作方向一致，信号共振")
        elif '观望' in overall or '未变' in overall or '不明' in overall:
            print("➖ 中信或其他机构本周无明显操作，需关注后续变化")

    # 小s解读
    print("\n**小s解读：**\n")

    # 中信 vs 其他十九家对比解读
    if '背离' in citic_vs_others:
        print(f"- **中信 vs 其他十九家信号背离**：{citic_vs_others}，需重点关注分歧背后的原因")
    elif '一致' in citic_vs_others:
        print(f"- 中信与其他十九家机构同向操作，信号一致性较强")

    if net < -5000:
        print(f"- 机构净空头{_num(abs(net))}手，净空头显著，做空力量较强")
    elif net < 0:
        print(f"- 机构净空头{_num(abs(net))}手，偏空")
    elif net > 5000:
        print(f"- 机构净多头{_num(net)}手，净多头显著，做多力量较强")
    elif net > 0:
        print(f"- 机构净多头{_num(net)}手，偏多")
    else:
        print("- 机构净持仓接近平衡")

    if citic_net < -2000:
        print(f"- 中信期货净持仓{_num(citic_net)}手，偏空信号，作为市场风向标，需警惕")
    elif citic_net > 2000:
        print(f"- 中信期货净持仓{_num(citic_net)}手，偏多信号，作为市场风向标，值得关注")

    if others_net < -2000:
        print(f"- 其他十九家净持仓{_num(others_net)}手，整体偏空，与中信{'一致' if citic_net < 0 else '背离'}")
    elif others_net > 2000:
        print(f"- 其他十九家净持仓{_num(others_net)}手，整体偏多，与中信{'一致' if citic_net > 0 else '背离'}")


# ======================================================================
#  模板格式打印 — 综合研判
# ======================================================================

def print_composite_analysis(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return

    details = comp.get('details', {})

    print("\n## 三、综合研判\n")

    # 积极信号
    print("### 积极信号\n")
    print("| 品种 | 信号类型 | 说明 |")
    print("|------|----------|------|")

    positive_count = 0
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
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
        if '贴水' in d.get('sentiment', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 基差风险 | {d.get('sentiment', '')} |")
        if d.get('position_signal') and '空头' in d.get('position_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')} | 持仓风险 | {d.get('position_signal', '')} |")
        if d.get('citic_signal') == '偏空':
            print(f"| {SYMBOL_NAME.get(sym, '')} | 中信风险 | {d.get('citic_signal', '')} |")
        week_chg = d.get('week_chg', 0)
        if week_chg < -2:
            print(f"| {SYMBOL_NAME.get(sym, '')} | 价格风险 | 全周下跌 {_pct(week_chg)} |")
        # 中信 vs 其他十九家信号
        cvo = d.get('citic_vs_others_signal', '')
        if cvo and cvo != '未知' and '背离' in cvo:
            print(f"| {SYMBOL_NAME.get(sym, '')} | 机构分歧 | {cvo} |")


# ======================================================================
#  模板格式打印 — 投资建议
# ======================================================================

def print_investment_suggestions(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return

    suggestions = comp.get('suggestions', [])

    print("\n## 四、投资建议\n")

    if suggestions:
        print("| 序号 | 策略建议 |")
        print("|------|----------|")
        for i, s in enumerate(suggestions, 1):
            print(f"| {i} | {s} |")
    else:
        print("暂无明确策略建议。")


# ======================================================================
#  模板格式打印 — 小s总结
# ======================================================================

def print_xiaos_summary(result: Dict, week_start: str, week_end: str):
    comp = result.get('composite', {})
    if not comp:
        return

    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    details = comp.get('details', {})

    print("\n## 五、小s的总结\n")

    print("### 关键结论：\n")

    conclusions = []
    for sym in ['IF', 'IC', 'IH', 'IM']:
        d = details.get(sym, {})
        week_chg = d.get('week_chg', 0)
        trend = d.get('trend', '-')
        icon = '📉' if week_chg < 0 else '📈' if week_chg > 0 else '➡️'
        conclusions.append(f"1. **{SYMBOL_NAME.get(sym, '')}（{sym}）：** {icon} 全周{_chg(week_chg)}，{trend}")

    for c in conclusions:
        print(c)

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

    print(f"\n2. **机构持仓：** 四大期指{'净空头' if avg_score < 50 else '净多头'}，{citic_info}")
    print(f"3. **基差结构：** 整体{'贴水' if avg_score < 50 else '升水'}，市场情绪偏{'悲观' if avg_score < 50 else '乐观'}")
    print(f"4. **综合评分：** {avg_score:.1f}/100，{market_env}")

    print("\n### 特别注意：\n")

    if avg_score < 30:
        print("- ⚠️ 期指交易杠杆高，风险大，严格止损")
        print("- ⚠️ 关注机构持仓变化，特别是中信期货动向")
        print("- ⚠️ 基差贴水扩大需警惕")
    elif avg_score < 50:
        print("- ⚠️ 期指交易杠杆高，风险大，注意止损")
        print("- ⚠️ 关注机构持仓变化，特别是中信期货动向")
        print("- ⚠️ 基差贴水需关注，市场情绪偏谨慎")
    else:
        print("- ✅ 市场情绪偏乐观，但仍需注意风险控制")
        print("- ✅ 关注机构持仓变化，特别是中信期货动向")


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
股指期货周度综合分析工具 · Tushare Pro

分析维度: 行情趋势 / 贴升水分析 / 机构持仓 / 综合研判

用法:
  python scripts/analyze_weekly_futures.py
  python scripts/analyze_weekly_futures.py --weeks 1
  python scripts/analyze_weekly_futures.py --json
  python scripts/analyze_weekly_futures.py --no-llm --no-chart
        """
    )
    parser.add_argument('--weeks', '-w', type=int, default=0,
                        help='回溯周数（0=上周，1=上上周，默认0）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始结果')

    args = parser.parse_args()

    # Reuse the daily analyzer with a wider time window (weeks_ago=0 → last 7 days,
    # weeks_ago=1 → last 14 days, etc.). The FuturesAnalyzer.analyze_all() already
    # supports a `days` parameter and produces the same result structure.
    from analysis.futures_analyzer import FuturesDataFetcher, FuturesAnalyzer

    days = (args.weeks + 1) * 14  # 取数窗口放大，保证覆盖完整 5 交易日窗口
    fetcher = FuturesDataFetcher()
    analyzer = FuturesAnalyzer(fetcher)

    print(f"正在采集周度期货数据（回溯 {days} 天）...")
    result = analyzer.analyze_all(symbols=['IF', 'IC', 'IH', 'IM'], days=days)

    # ── 周窗口：以实际交易日为准（最近 5 个交易日），而非自然日 ──
    week_days = []
    for sym in ['IF', 'IC', 'IH', 'IM']:
        daily = result.get('symbols', {}).get(sym, {}).get('price', {}).get('daily', [])
        if daily:
            week_days = [d['date'] for d in daily][-5:]
            break
    if not week_days:
        # 兜底：行情缺失时退化为自然日（如实展示，数据本身缺失）
        from datetime import timedelta
        week_days = [(datetime.now() - timedelta(days=6 - i)).strftime('%Y-%m-%d')
                     for i in range(7)]
    week_start, week_end = week_days[0], week_days[-1]

    # ── 逐品种周度指标：周涨跌幅 / 周OI变化 / 主力合约切换 / 持仓表窗口过滤 ──
    for sym, sym_data in result.get('symbols', {}).items():
        price = sym_data.get('price', {})
        daily = price.get('daily', [])
        week_daily = [d for d in daily if d['date'] in week_days]
        if len(week_daily) >= 2:
            first_close = float(week_daily[0]['close'])
            last_close = float(week_daily[-1]['close'])
            if first_close:
                # 周涨跌幅 = 周内末收盘 / 周内首收盘 - 1（与期权联动脚本口径一致）
                price['week_chg'] = round((last_close / first_close - 1) * 100, 2)
            # 周 OI 变化 = 周内末持仓量 - 周内首持仓量
            price['week_oi_chg'] = (int(week_daily[-1].get('oi', 0))
                                    - int(week_daily[0].get('oi', 0)))
            price['oi_trend'] = ('增仓' if price['week_oi_chg'] > 0 else
                                 '减仓' if price['week_oi_chg'] < 0 else '持平')
        # 主力合约与周内切换信息
        contracts = sym_data.get('contracts', {})
        price['main_contract'] = contracts.get('main_contract', '-')
        price['contract_switch'] = _detect_contract_switch(fetcher, sym, week_days)
        # 同步到综合研判 details（评分表周涨跌列）
        details = result.get('composite', {}).get('details', {})
        if sym in details and 'week_chg' in price:
            details[sym]['week_chg'] = price['week_chg']
        # 持仓每日变化表只保留窗口内交易日（剔除回溯混入的上周数据）
        holding = sym_data.get('holding', {})
        dt = holding.get('daily_trends', [])
        if dt:
            wd_raw = set(d.replace('-', '') for d in week_days)
            holding['daily_trends'] = [x for x in dt
                                       if str(x.get('trade_date', '')) in wd_raw]

    # JSON 输出模式
    if args.json:
        def _default_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'item'):
                return obj.item()
            return str(obj)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default_serializer))
        return

    # 一、市场概览
    print_market_overview(result, week_start, week_end, week_days)

    # 二、逐品种详细分析
    print("\n## 二、逐品种详细分析\n")
    for sym in ['IF', 'IC', 'IH', 'IM']:
        sym_data = result.get('symbols', {}).get(sym, {})
        if sym_data:
            print_symbol_analysis(sym, sym_data, week_days)

    # 三、中信 vs 其他机构 分品种对比
    print_cross_symbol_holding_comparison(result)

    # 四、综合研判
    comp = result.get('composite', {})
    if comp:
        print("\n## 四、综合研判\n")
        print(f"**综合评分：{comp.get('avg_score', 50):.1f}/100**")
        print(f"**市场环境：{comp.get('market_env', '-')}**")
        print(f"**品种分化：{comp.get('divergence_signal', '-')}**")

    # 五、投资建议
    suggestions = comp.get('suggestions', [])
    if suggestions:
        print("\n## 五、投资建议\n")
        for s in suggestions:
            print(f"- {s}")

    # 免责声明
    print("\n---")
    print("⚠️ 以上分析基于 Tushare Pro 数据与逻辑推演，不构成投资建议。")


if __name__ == '__main__':
    main()
