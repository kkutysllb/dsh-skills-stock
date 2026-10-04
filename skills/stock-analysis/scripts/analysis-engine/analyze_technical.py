#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股技术分析命令行工具

数据全部来自 Tushare Pro API，不依赖本地数据库。
宏观层：日/周/月线联动，分析趋势强弱、支撑压力、资金流向
微观层：5/15/30/60/90/120分钟联动，量价/动量/背驰三维度择时信号

用法:
    python scripts/analyze_technical.py --stock 宁德时代
    python scripts/analyze_technical.py --stock 600519 --type macro
    python scripts/analyze_technical.py --stock 300750.SZ --type micro
    python scripts/analyze_technical.py --stock 茅台 --type all --json
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Optional
from datetime import datetime
import re
import io

import pandas as pd


# ======================================================================
#  图表生成辅助函数
# ======================================================================

def _ma(series: pd.Series, period: int) -> pd.Series:
    """计算简单移动平均"""
    return series.rolling(window=period, min_periods=1).mean()

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  格式化输出工具
# ======================================================================

def _bar(val: float, max_val: float, width: int = 20, fill: str = '█', empty: str = '░') -> str:
    if max_val == 0:
        return empty * width
    filled = int(abs(val) / max_val * width)
    return fill * filled + empty * (width - filled)


def _score_bar(score: float, max_score: float = 100, width: int = 20) -> str:
    """带颜色语义的评分进度条"""
    return _bar(score, max_score, width)


def _pct(val: float, decimals: int = 2) -> str:
    sign = '+' if val > 0 else ''
    return f"{sign}{val:.{decimals}f}%"


def _signal_cn(direction: str) -> str:
    return {'buy': '买入', 'sell': '卖出', 'neutral': '观望'}.get(direction, '观望')


def _signal_mark(direction: str) -> str:
    return {'buy': '▲', 'sell': '▼', 'neutral': '─'}.get(direction, '─')


def _get_trend_icon(trend: str) -> str:
    """获取趋势图标"""
    if '上升' in trend or '上涨' in trend:
        return '📈'
    elif '下降' in trend or '下跌' in trend:
        return '📉'
    else:
        return '➡️'


def print_section(title: str, width: int = 62):
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")


# ======================================================================
#  图表生成层
# ======================================================================

# ======================================================================
#  LLM 分析层
# ======================================================================

# ======================================================================
#  宏观趋势输出（模板格式 - 详细版）
# ======================================================================

def print_macro_analysis(result: Dict, stock_name: str, ts_code: str,
):
    """格式化打印宏观趋势分析结果（详细模板格式）"""

    macro = result.get('macro_trend', {})
    score = result.get('composite_score', 0)
    conclusion = result.get('trend_conclusion', '')

    # 一、宏观趋势分析
    print("\n## 一、宏观趋势分析\n")
    
    # 综合评分
    bar = _score_bar(score)
    print(f"**综合评分：{score:.1f}/100**")
    print(f"{bar}")
    print(f"**趋势结论：{conclusion}**")
    
    # 插入宏观评分对比图和LLM分析

    # 各周期详细分析
    period_configs = [
        ('月线', 'monthly', '📊'),
        ('周线', 'weekly', '📈'),
        ('日线', 'daily', '📉'),
    ]
    
    for label, key, icon in period_configs:
        p = macro.get(key, {})
        if not p or 'error' in p:
            print(f"\n### {label}趋势（数据不足）\n")
            continue
        
        s = p.get('score', 50)
        trend = p.get('trend', '未知')
        ma_align = p.get('ma_alignment', '')
        close = p.get('close', 0)
        chg = p.get('recent_change_pct', 0)
        macd_sig = p.get('macd_signal', '')
        rsi = p.get('rsi', 0)
        rsi_zone = p.get('rsi_zone', '')
        kdj_sig = p.get('kdj_signal', '')
        boll_zone = p.get('boll_zone', '')
        atr_pct = p.get('atr_pct', 0)
        obv_trend = p.get('obv_trend', '')
        
        # 周期标题
        print(f"\n### {label}趋势（评分：{s}/100）\n")
        
        # 指标表格
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        print(f"| 收盘价 | {close:.2f}元 | {label}收盘 |")
        print(f"| 均线排列 | {ma_align} | 趋势明确 |")
        print(f"| 趋势方向 | {trend} | {label}级别{trend} |")
        print(f"| 近期变化 | {_pct(chg)} | 涨幅{'较大' if abs(chg) > 20 else '正常'} |")
        print(f"| MACD | {macd_sig} | 动能变化 |")
        print(f"| RSI | {rsi:.1f} | {rsi_zone} |")
        print(f"| KDJ | {kdj_sig} | — |")
        print(f"| 布林带 | {boll_zone} | 位置{'偏高' if '上' in boll_zone else '偏低' if '下' in boll_zone else '适中'} |")
        print(f"| ATR波动 | {atr_pct:.2f}% | 波动{'较大' if atr_pct > 10 else '正常'} |")
        print(f"| OBV | {obv_trend} | 量能{'增强' if '上升' in obv_trend else '减弱' if '下降' in obv_trend else '平稳'} |")
        
        # 均线详情
        ma5 = p.get('ma5', 0)
        ma10 = p.get('ma10', 0)
        ma20 = p.get('ma20', 0)
        ma60 = p.get('ma60', 0)
        
        print("\n**均线详情：**")
        print(f"1. **MA5:** {ma5:.2f}元")
        print(f"2. **MA10:** {ma10:.2f}元")
        print(f"3. **MA20:** {ma20:.2f}元")
        print(f"4. **MA60:** {ma60:.2f}元 ← 当前在MA60{'上方' if close > ma60 else '下方'}")
        print(f"5. **当前价:** {close:.2f}元（在MA20{'上方' if close > ma20 else '下方'}）")
        
        # 周期结论
        trend_icon = _get_trend_icon(trend)
        if s >= 70:
            period_conclusion = f"{label}{trend}，近期{_pct(chg)}，较为强势。"
        elif s >= 50:
            period_conclusion = f"{label}{trend}，近期{_pct(chg)}，正常波动。"
        else:
            period_conclusion = f"{label}{trend}，近期{_pct(chg)}，需谨慎。"
        
        print(f"\n**{label}结论：** {trend_icon} {period_conclusion}")
        
        # 插入该周期LLM分析

    # 支撑压力位
    sr = result.get('support_resistance', {})
    if sr:
        cur = sr.get('current', 0)
        sup = sr.get('support', 0)
        res = sr.get('resistance', 0)
        sup_dist = sr.get('distance_to_support_pct', 0)
        res_dist = sr.get('distance_to_resistance_pct', 0)
        
        print("\n## 二、关键价位参考\n")
        print("| 类型 | 价位 | 距离 |")
        print("|------|------|------|")
        print(f"| 压力位 | {res:.2f}元 | +{res_dist:.2f}% |")
        print(f"| 当前价 | **{cur:.2f}元** | — |")
        print(f"| 支撑位 | {sup:.2f}元 | -{sup_dist:.2f}% |")
        
        # 插入均线图和支撑压力图

    # 资金流向
    mf = result.get('moneyflow', {})
    if mf:
        direction = mf.get('direction', '')
        net5 = mf.get('net_mf_vol_5d', 0)
        large = mf.get('large_order_net', 0)
        
        print("\n## 三、资金流向分析\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        
        if direction == 'inflow':
            dir_str = '净流入'
        elif direction == 'outflow':
            dir_str = '净流出'
        else:
            dir_str = '平衡'
        
        print(f"| 近5日流向 | {dir_str} | 主力动向 |")
        print(f"| 净流入量 | {net5:.0f}手 | 5日累计 |")
        print(f"| 大单净买 | {large:.0f}手 | 大资金态度 |")
        

    # 换手率/估值
    tr = result.get('turnover', {})
    if tr:
        print("\n## 四、换手率与估值\n")
        print("| 指标 | 数值 | 说明 |")
        print("|------|------|------|")
        print(f"| 近10日均换手 | {tr.get('avg10', 0):.2f}% | 活跃度 |")
        print(f"| 今日换手 | {tr.get('latest', 0):.2f}% | 流动性 |")
        if tr.get('pe_ttm'):
            print(f"| PE(TTM) | {tr.get('pe_ttm', 0):.2f} | 估值水平 |")
            print(f"| PB | {tr.get('pb', 0):.2f} | 市净率 |")
        

    # 投资评级
    print("\n## 五、投资评级\n")
    print(f"**技术面评分：{score:.1f}/100**")
    bar = _score_bar(score)
    print(f"{bar}")
    
    print("\n| 维度 | 评分 | 说明 |")
    print("|------|------|------|")
    
    # 各维度评分
    for label, key, _ in period_configs:
        p = macro.get(key, {})
        if not p or 'error' in p:
            continue
        s = p.get('score', 50)
        trend = p.get('trend', '未知')
        ma_align = p.get('ma_alignment', '')
        print(f"| {label}趋势 | {s}/100 | {trend}，均线{ma_align} |")
    
    if mf:
        print(f"| 资金流向 | — | {mf.get('direction', '平衡')} |")
    
    # 综合评级
    if score >= 70:
        rating = "偏多"
    elif score >= 50:
        rating = "中性偏多"
    else:
        rating = "偏空"
    
    print(f"\n**综合评级：{rating}**")
    
    # 插入评分仪表盘

    # 操作建议
    print("\n## 六、操作建议\n")
    print("| 周期 | 策略 | 入场 | 止损 |")
    print("|------|------|------|------|")
    
    # 根据评分给出建议
    daily = macro.get('daily', {})
    if daily and 'error' not in daily:
        ma20 = daily.get('ma20', 0)
        ma60 = daily.get('ma60', 0)
        close = daily.get('close', 0)
        sup = sr.get('support', 0) if sr else ma60
        res = sr.get('resistance', 0) if sr else close * 1.1
        
        if score >= 70:
            print(f"| 短线 | 逢低试多 | {sup:.2f}-{ma20:.2f}元 | {ma60:.2f}元下方 |")
            print(f"| 中线 | 积极布局 | 回调买入 | {sup * 0.95:.2f}元下方 |")
            print(f"| 长线 | 持有观察 | 月线趋势向上 | 注意波动 |")
        elif score >= 50:
            print(f"| 短线 | 轻仓试探 | {sup:.2f}元附近 | {ma60:.2f}元下方 |")
            print(f"| 中线 | 观望为主 | 等待信号 | — |")
            print(f"| 长线 | 持有观察 | 趋势中性 | 注意风险 |")
        else:
            print(f"| 短线 | 观望为主 | — | — |")
            print(f"| 中线 | 谨慎观察 | 等待企稳 | — |")
            print(f"| 长线 | 减仓为主 | 趋势偏弱 | 控制风险 |")
    else:
        print("| 短线 | 观望 | — | — |")
        print("| 中线 | 观望 | — | — |")
        print("| 长线 | 观望 | — | — |")


# ======================================================================
#  微观择时输出（模板格式 - 详细版）
# ======================================================================

def print_micro_analysis(result: Dict, stock_name: str, ts_code: str,
):
    """格式化打印微观择时分析结果（详细模板格式）"""

    signals = result.get('signals', {})
    composite = result.get('composite_signal', 'neutral')
    strength = result.get('signal_strength', 5.0)
    conclusion = result.get('timing_conclusion', '')
    alerts = result.get('divergence_alerts', [])

    print("\n## 七、微观择时分析\n")
    
    # 1. 多周期信号汇总
    print("### 1. 多周期信号汇总\n")
    print("| 周期 | 方向 | 量价关系 | MACD | RSI6 | 背离信号 | 评分 |")
    print("|------|------|----------|------|------|----------|------|")
    
    freq_order = ['5min', '15min', '30min', '60min', '90min', '120min']
    freq_names = {
        '5min': '5min',
        '15min': '15min',
        '30min': '30min',
        '60min': '60min',
        '90min': '90min',
        '120min': '120min',
    }
    
    for freq in freq_order:
        sig = signals.get(freq, {})
        if not sig or 'error' in sig:
            print(f"| {freq_names[freq]} | — | — | — | — | — | — |")
            continue
        
        direction = sig.get('direction', 'neutral')
        mark = _signal_mark(direction)
        dir_cn = _signal_cn(direction)
        vp = sig.get('volume_price', '')
        bar_sign = sig.get('macd_bar_sign', '-')
        bar_expand = '扩张' if sig.get('macd_bar_expanding') else '收缩'
        rsi = sig.get('rsi6', 50.0)
        div = sig.get('divergence') or '-'
        score = sig.get('score', 5.0)
        
        print(f"| {freq_names[freq]} | {mark} {dir_cn} | {vp} | {bar_sign} {bar_expand} | {rsi:.1f} | {div} | {score:.1f} |")
    
    # 插入微观信号图
    
    # 2. 综合信号
    print("\n### 2. 综合信号\n")
    composite_cn = _signal_cn(composite)
    composite_mark = _signal_mark(composite)
    strength_bar = _bar(strength, 10.0, 20)
    
    print(f"**综合信号：{composite_mark} {composite_cn}**")
    print(f"**信号强度：{strength:.1f}/10**")
    print(f"{strength_bar}")
    print(f"**择时结论：** {conclusion}")
    
    
    # 3. 背驰告警
    if alerts:
        print("\n### 3. 背驰告警\n")
        print("| 周期 | 背驰类型 | 说明 |")
        print("|------|----------|------|")
        
        # 解析告警信息
        for a in alerts:
            # 简单解析告警信息
            if '底背驰' in a:
                print(f"| — | 底背驰 | 可能反弹 |")
            elif '顶背驰' in a:
                print(f"| — | 顶背驰 | 可能回调 |")
            else:
                print(f"| — | {a} | — |")
        
        # 统计背驰类型
        bottom_div = sum(1 for a in alerts if '底背驰' in a)
        top_div = sum(1 for a in alerts if '顶背驰' in a)
        print(f"\n检测到{bottom_div}个底背驰、{top_div}个顶背驰，{'多空信号交织' if bottom_div > 0 and top_div > 0 else '信号偏多' if bottom_div > top_div else '信号偏空'}。")
    
    # 4. 动量详情
    print("\n### 4. 动量详情\n")
    print("| 周期 | ROC5 | 量比 | RSI12 | 状态 |")
    print("|------|------|------|-------|------|")
    
    for freq in freq_order:
        sig = signals.get(freq, {})
        if not sig or 'error' in sig:
            print(f"| {freq_names[freq]} | — | — | — | — |")
            continue
        
        roc = sig.get('roc5', 0.0)
        vol_ratio = sig.get('vol_ratio', 1.0)
        rsi12 = sig.get('rsi12', 50.0)
        
        # 判断状态
        if vol_ratio > 1.2:
            status = '放量'
        elif vol_ratio < 0.8:
            status = '缩量'
        else:
            status = '正常'
        
        print(f"| {freq_names[freq]} | {_pct(roc)} | {vol_ratio:.2f}x | {rsi12:.1f} | {status} |")


# ======================================================================
#  综合结论输出
# ======================================================================

def print_comprehensive_conclusion(macro_result: Dict, micro_result: Dict):
    """打印综合结论"""
    
    print("\n## 八、综合结论\n")
    
    macro = macro_result.get('macro_trend', {})
    score = macro_result.get('composite_score', 0)
    
    # 积极信号
    print("### 积极信号\n")
    print("| 信号 | 说明 |")
    print("|------|------|")
    
    positive_signals = []
    
    # 检查各周期
    for label, key in [('月线', 'monthly'), ('周线', 'weekly'), ('日线', 'daily')]:
        p = macro.get(key, {})
        if not p or 'error' in p:
            continue
        
        trend = p.get('trend', '')
        chg = p.get('recent_change_pct', 0)
        macd_sig = p.get('macd_signal', '')
        ma_align = p.get('ma_alignment', '')
        
        if '上升' in trend:
            positive_signals.append((f"{label}上升", f"近期{_pct(chg)}，{'大趋势强势' if label == '月线' else '中期趋势向好' if label == '周线' else '短线反弹'}"))
        
        if '扩张' in macd_sig and '红' in macd_sig:
            positive_signals.append((f"{label}MACD扩张", "多头信号明确"))
        
        if '多头' in ma_align:
            positive_signals.append((f"{label}多头排列", "趋势明确"))
    
    # 检查资金流向
    mf = macro_result.get('moneyflow', {})
    if mf and mf.get('direction') == 'inflow':
        positive_signals.append(("资金流入", "主力资金配合良好"))
    
    # 检查背驰
    if micro_result:
        alerts = micro_result.get('divergence_alerts', [])
        for a in alerts:
            if '底背驰' in a:
                positive_signals.append(("底背驰信号", "短期看多信号"))
    
    if positive_signals:
        for sig, desc in positive_signals:
            print(f"| {sig} | {desc} |")
    else:
        print("| — | 暂无明显积极信号 |")
    
    # 风险信号
    print("\n### 风险信号\n")
    print("| 风险 | 说明 |")
    print("|------|------|")
    
    risk_signals = []
    
    # 检查超买
    for label, key in [('月线', 'monthly'), ('周线', 'weekly'), ('日线', 'daily')]:
        p = macro.get(key, {})
        if not p or 'error' in p:
            continue
        
        rsi = p.get('rsi', 0)
        kdj_sig = p.get('kdj_signal', '')
        
        if rsi > 70:
            risk_signals.append((f"{label}RSI超买", "短期有回调风险"))
        
        if '超买' in kdj_sig:
            risk_signals.append((f"{label}KDJ超买", "短期或有调整"))
    
    # 检查背驰
    if micro_result:
        alerts = micro_result.get('divergence_alerts', [])
        for a in alerts:
            if '顶背驰' in a:
                risk_signals.append(("顶背驰信号", "短期或有回调压力"))
    
    # 检查趋势
    if score < 50:
        risk_signals.append(("趋势偏弱", "注意风险控制"))
    
    if risk_signals:
        for sig, desc in risk_signals:
            print(f"| {sig} | {desc} |")
    else:
        print("| — | 暂无明显风险信号 |")


# ======================================================================
#  小s总结输出
# ======================================================================

def print_xiaos_summary(stock_name: str, ts_code: str, macro_result: Dict, micro_result: Dict):
    """打印小s的总结"""
    
    print("\n## 九、小s的总结\n")
    
    macro = macro_result.get('macro_trend', {})
    score = macro_result.get('composite_score', 0)
    conclusion = macro_result.get('trend_conclusion', '')
    
    print(f"**{stock_name}（{ts_code}）技术面分析：**\n")
    
    # 关键结论
    print("### 关键结论：\n")
    
    conclusions = []
    
    # 月线
    monthly = macro.get('monthly', {})
    if monthly and 'error' not in monthly:
        trend = monthly.get('trend', '')
        chg = monthly.get('recent_change_pct', 0)
        conclusions.append(f"1. **月线：** {trend}趋势，近期{_pct(chg)}，{'大趋势强势' if '上升' in trend else '大趋势偏弱'}")
    
    # 周线
    weekly = macro.get('weekly', {})
    if weekly and 'error' not in weekly:
        trend = weekly.get('trend', '')
        conclusions.append(f"2. **周线：** {trend}趋势，{'中期向好' if '上升' in trend else '中期偏弱'}")
    
    # 日线
    daily = macro.get('daily', {})
    if daily and 'error' not in daily:
        trend = daily.get('trend', '')
        macd_sig = daily.get('macd_signal', '')
        conclusions.append(f"3. **日线：** {'反弹中' if '上升' in trend else '调整中'}，MACD{macd_sig}，{'多头信号明确' if '扩张' in macd_sig else '信号不明确'}")
    
    # 资金
    mf = macro_result.get('moneyflow', {})
    if mf:
        direction = mf.get('direction', '')
        conclusions.append(f"4. **资金：** 整体{'净流入' if direction == 'inflow' else '净流出' if direction == 'outflow' else '平衡'}，资金{'配合良好' if direction == 'inflow' else '需关注'}")
    
    # 微观信号
    if micro_result:
        composite = micro_result.get('composite_signal', 'neutral')
        strength = micro_result.get('signal_strength', 5.0)
        composite_cn = _signal_cn(composite)
        conclusions.append(f"5. **信号：** {composite_cn}信号，强度{strength:.1f}/10")
    
    for c in conclusions:
        print(c)
    
    # 特别注意
    print("\n### 特别注意：")
    
    warnings = []
    
    # RSI超买
    if daily and 'error' not in daily:
        rsi = daily.get('rsi', 0)
        if rsi > 70:
            warnings.append(f"- 日线RSI超买（{rsi:.1f}），短期注意回调风险")
    
    # KDJ超买
    if weekly and 'error' not in weekly:
        kdj_sig = weekly.get('kdj_signal', '')
        if '超买' in kdj_sig:
            warnings.append(f"- 周线KDJ超买，中期或有调整")
    
    # 背驰
    if micro_result:
        alerts = micro_result.get('divergence_alerts', [])
        if alerts:
            warnings.append(f"- 检测到背驰信号，需密切关注")
    
    # 趋势偏弱
    if score < 50:
        warnings.append(f"- 综合评分{score:.1f}/100，趋势偏弱，建议谨慎")
    
    if warnings:
        for w in warnings:
            print(w)
    else:
        print("- 暂无明显风险提示")


# ======================================================================
#  图表配置生成
# ======================================================================

# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='个股技术分析工具 — 宏观趋势 + 微观择时',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/analyze_technical.py
  python scripts/analyze_technical.py --stock 宁德时代
  python scripts/analyze_technical.py --stock 600519 --type macro
  python scripts/analyze_technical.py --stock 300750.SZ --type micro --days 5
  python scripts/analyze_technical.py --stock 茅台 --type all --json
        """
    )
    parser.add_argument('--stock', '-s', type=str, default=None,
                        help='股票名称或代码（支持: 中文名称 / 6位数字 / 标准代码）')
    parser.add_argument('--type', '-t', type=str, default='all',
                        choices=['all', 'macro', 'micro'],
                        help='分析类型: all-全部 macro-宏观 micro-微观（默认all）')
    parser.add_argument('--days', '-d', type=int, default=10,
                        help='微观分钟线回溯天数（默认10天）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始分析结果')

    args = parser.parse_args()

    # 交互式输入
    stock_input = args.stock
    if not stock_input:
        print("=" * 62)
        print("  个股技术分析工具")
        print("=" * 62)
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

    # 导入分析模块（analysis-engine 目录即分析包所在位置）
    _engine_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analysis-engine')
    if _engine_dir not in sys.path:
        sys.path.insert(0, _engine_dir)
    from technical_analyzer import TechnicalDataFetcher, TechnicalAnalyzer

    # 股票解析
    print(f"\n正在查询股票信息: {stock_input!r} ...")
    try:
        import re as _re
        from dotenv import load_dotenv
        load_dotenv()
        token = os.getenv('TUSHARE_TOKEN')
        if not token:
            raise ValueError('未找到 TUSHARE_TOKEN')
        from kk_common import get_finance_data_gateway
        _pro = get_finance_data_gateway()

        stock_input = stock_input.strip()
        if _re.match(r'^\d{6}\.(SH|SZ)$', stock_input, _re.IGNORECASE):
            ts_code = stock_input.upper()
        elif _re.match(r'^\d{6}$', stock_input):
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

        df_name = _pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
        stock_name = df_name.iloc[0]['name'] if not df_name.empty else ts_code
        print(f"✓ 识别到: {stock_name}（{ts_code}）")
    except ValueError as e:
        print(f"\n[错误] {e}")
        sys.exit(1)

    # 初始化分析引擎
    fetcher = TechnicalDataFetcher()
    analyzer = TechnicalAnalyzer(fetcher)

    show_macro = args.type in ('all', 'macro')
    show_micro = args.type in ('all', 'micro')

    macro_result = None
    micro_result = None

    # 采集 + 分析
    if show_macro:
        print(f"\n正在进行宏观趋势分析（日/周/月线联动）...")
        macro_result = analyzer.analyze_macro(ts_code)

    if show_micro:
        print(f"\n正在进行微观择时分析（5~120分钟联动，回溯{args.days}天）...")
        micro_result = analyzer.analyze_micro(ts_code, n_days=args.days)

    # JSON 模式
    if args.json:
        output = {
            'ts_code': ts_code,
            'stock_name': stock_name,
        }
        if macro_result:
            output['macro'] = macro_result
        if micro_result:
            output['micro'] = micro_result
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
        return

    # 报告日期
    report_date = datetime.now().strftime('%Y-%m-%d')

    # ==================== 报告输出 ====================

    # 报告头
    print(f"# 📈 {stock_name}（{ts_code}）技术分析报告")
    print(f"**分析日期：{report_date}**")
    print("\n---")
    
    
    # 格式化输出
    if macro_result:
        print_macro_analysis(macro_result, stock_name, ts_code)

    if micro_result:
        print_micro_analysis(micro_result, stock_name, ts_code)

    # 综合结论
    if macro_result:
        print_comprehensive_conclusion(macro_result, micro_result or {})
    
    # 小s总结
    if macro_result:
        print_xiaos_summary(stock_name, ts_code, macro_result, micro_result or {})

    # 免责声明
    print("\n---")
    print("\n*免责声明：技术分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。*")
    print("\n---")
    print(f"\n**报告生成：小s 智能体**  ")
    print(f"**数据来源：Tushare Pro API**")


if __name__ == '__main__':
    main()
