#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期指期权联动分析工具（周粒度）

在日粒度基础上按自然周（ISO 周）聚合：
  - 期权维度：周均成交量/持仓量 PCR、周 ATM IV、周加权 IV，
    最新交易日 IV 斜率 / Risk Reversal / 认沽认购 IV 差快照
  - 期指维度：周涨跌幅（周首→周末）、周内持仓变化、周末基差贴升水
  - 联动维度：周均信号 × 周趋势共振/背离，分品种评分

用法:
    python3 analyze_weekly_option_futures.py
    python3 analyze_weekly_option_futures.py --symbols IF IM
    python3 analyze_weekly_option_futures.py --weeks 2
    python3 analyze_weekly_option_futures.py --json
"""

import os
import sys
import json
import argparse
from typing import Dict, Any

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from analysis.option_futures_analyzer import (
    SYMBOL_MAP, OptionFuturesFetcher, OptionFuturesAnalyzer,
)

SYMBOL_NAME = {
    'IF': '沪深300',
    'IC': '中证500',
    'IH': '上证50',
    'IM': '中证1000',
}

OPT_NAME = {
    'IF': '300ETF期权(510300.SH)',
    'IC': '500ETF期权(510500.SH)',
    'IH': '50ETF期权(510050.SH)',
    'IM': 'MO中证1000期权(000852.SH)',
}


def _num(val) -> str:
    if val is None:
        return '-'
    v = float(val)
    if abs(v) >= 10000:
        return f"{v / 10000:.1f}万"
    return f"{v:,.0f}"


def _pct(val, sign=True) -> str:
    if val is None:
        return '-'
    prefix = ('+' if val > 0 else '') if sign else ''
    return f"{prefix}{val:.2f}%"


def _bar(val: float, max_val: float, width: int = 20,
         fill: str = '█', empty: str = '░') -> str:
    if max_val == 0:
        return empty * width
    filled = int(min(abs(val) / max_val, 1.0) * width)
    return fill * filled + empty * (width - filled)


def _fmt_date(d) -> str:
    if d and len(str(d)) == 8:
        s = str(d)
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return str(d or '-')


def _iv_str(v) -> str:
    return '-' if v is None else f"{v:.2f}%"


# ======================================================================
#  市场概览（周）
# ======================================================================

def print_market_overview(result: Dict, week_label: str):
    comp = result.get('composite', {})
    if not comp:
        return

    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    div_sig = comp.get('divergence_signal', '-')

    print("\n## 一、市场概览（周度）\n")
    print(f"**分析周：{week_label}**")
    print(f"**综合评分：{avg_score:.1f}/100**")
    print(f"{_bar(avg_score, 100)}")
    print(f"**市场环境：{market_env}**")
    print(f"**品种分化：{div_sig}**")

    scores = comp.get('symbol_scores', {})
    details = comp.get('details', {})
    if scores:
        print("\n### 各品种周度联动评分\n")
        print("| 品种 | 期权标的 | 综合评分 | 周趋势 | 周基差信号 | 联动方向 | 联动得分 |")
        print("|------|----------|----------|--------|------------|----------|----------|")
        for sym in ['IF', 'IH', 'IC', 'IM']:
            if sym not in scores:
                continue
            sc = scores[sym]
            d = details.get(sym, {})
            icon = '▼' if sc <= 42 else '▲' if sc >= 58 else '─'
            print(f"| **{sym}** {SYMBOL_NAME.get(sym, '')} | {OPT_NAME.get(sym, '-')} | "
                  f"{icon} {sc}/100 {_bar(sc, 100, 8)} | {d.get('trend', '-')} | "
                  f"{d.get('basis_signal', '-')} | {d.get('direction', '-')} | {d.get('linkage', 0):+} |")


# ======================================================================
#  逐品种周度联动分析
# ======================================================================

def print_symbol_analysis(sym: str, sym_data: Dict):
    week_label = sym_data.get('week_label', '-')
    print(f"\n### {SYMBOL_NAME.get(sym, sym)}（{sym}）— 期权标的：{OPT_NAME.get(sym, '-')}（{week_label}）\n")

    opt = sym_data.get('option', {})
    fut = sym_data.get('futures', {})
    link = sym_data.get('linkage', {})

    if opt.get('error'):
        print(f"**期权数据异常：** {opt['error']}")
        print(f"**期指数据异常：** {fut.get('error', '无')}")
        print(f"**联动：** {link.get('direction', '-')}（{link.get('score', 0):+}）")
        return

    # 1. 期权维度（周均）
    print("#### 1. 期权维度（周均认沽认购 / 周均波动率 / 最新IV斜率）\n")
    print("| 指标 | 数值 | 解读 |")
    print("|------|------|------|")
    pcr_v = opt.get('pcr_vol')
    pcr_v_sig = '认沽偏多（周均避险情绪浓）' if pcr_v is not None and pcr_v > 1.2 else \
                '认购偏多（周均看涨情绪浓）' if pcr_v is not None and pcr_v < 0.8 else '中性'
    print(f"| 周均成交量 PCR（认沽/认购） | **{pcr_v if pcr_v is not None else '-'}** | {pcr_v_sig} |")
    pcr_o = opt.get('pcr_oi')
    pcr_o_sig = '保护性认沽持仓多（偏空）' if pcr_o is not None and pcr_o > 1.0 else \
                '认购持仓多（偏多）' if pcr_o is not None and pcr_o < 0.7 else '中性'
    print(f"| 周均持仓量 PCR | {pcr_o if pcr_o is not None else '-'} | {pcr_o_sig} |")
    print(f"| 周 ATM 隐含波动率 | {_iv_str(opt.get('atm_iv'))} | 周内活跃 ATM 合约 IV |")
    wiv = opt.get('weighted_iv')
    wiv_sig = '高波动（恐慌）' if wiv is not None and wiv > 30 else \
              '低波动（平稳）' if wiv is not None and wiv < 18 else '正常'
    print(f"| 周加权 IV | {_iv_str(wiv)} | {wiv_sig} |")
    print(f"| 认沽端 IV 斜率 | {opt.get('iv_slope_put', '-')} ‰ | 最新交易日快照 |")
    print(f"| 认购端 IV 斜率 | {opt.get('iv_slope_call', '-')} ‰ | 最新交易日快照 |")
    rr = opt.get('risk_reversal')
    rr_sig = '认沽端偏贵（偏空）' if rr is not None and rr > 0.5 else \
             '认购端偏贵（偏多）' if rr is not None and rr < -0.5 else '中性'
    print(f"| Risk Reversal（认沽-认购 IV） | {rr if rr is not None else '-'} % | {rr_sig}（快照） |")
    pcd = opt.get('put_call_iv_diff')
    pcd_sig = '认沽IV高（偏空）' if pcd is not None and pcd > 1.5 else \
              '认购IV高（偏多）' if pcd is not None and pcd < -1.5 else '中性'
    print(f"| 认沽认购 IV 差（ATM） | {pcd if pcd is not None else '-'} % | {pcd_sig}（快照） |")
    print(f"| 快照日期 | {_fmt_date(opt.get('snapshot_date'))} | IV斜率/RR数据日 |")

    # 2. 期指维度（周）
    print("\n#### 2. 期指维度（周度）\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    print(f"| 主力合约 | {fut.get('main_contract', '-')} | 期指主力 |")
    print(f"| 周末收盘价 | {fut.get('close', '-')} | 周内最后交易日收盘 |")
    print(f"| 周涨跌幅 | **{_pct(fut.get('pct_chg'))}** | 周首→周末累计 |")
    print(f"| 周趋势判断 | {fut.get('trend', '-')} | 基于周涨跌幅 |")
    print(f"| 周持仓变化 | {_num(fut.get('oi'))}（{fut.get('oi_chg', 0):+,}） | 周内 OI 累计变化 |")
    print(f"| 周末基差 | {fut.get('basis', '-')} | 期指-现货指数 |")
    print(f"| 周末基差率 | {_pct(fut.get('basis_rate'))} | 基差/现货 |")
    print(f"| 基差信号 | {fut.get('basis_signal', '-')} | 贴升水情绪 |")

    # 周内每日明细
    series = sym_data.get('daily_series', [])
    if series:
        print("\n**周内每日期权指标：**\n")
        print("| 日期 | 成交量PCR | 持仓量PCR | ATM IV | 加权IV |")
        print("|------|-----------|-----------|--------|--------|")
        for r in series:
            print(f"| {_fmt_date(r['trade_date'])} | {r.get('pcr_vol', '-')} | "
                  f"{r.get('pcr_oi', '-')} | {_iv_str(r.get('atm_iv'))} | {_iv_str(r.get('weighted_iv'))} |")

    # 3. 联动信号
    print("\n#### 3. 联动信号（周均期权 × 周度期指）\n")
    print("| 联动维度 | 期权信号 | 期指信号 | 结论 | 得分 |")
    print("|----------|----------|----------|------|------|")
    for s in link.get('signals', []):
        score = s.get('score', 0)
        mark = '✅' if score > 0 else '⚠️' if score < 0 else '➖'
        print(f"| {s['name']} | {s['option_signal']} | {s['futures_signal']} | {s['conclusion']} | {mark} {score:+} |")
    print(f"\n**周度联动评分：{link.get('score', 0):+} → 方向：{link.get('direction', '-')}**")
    if link.get('summary'):
        print("**信号要点：**")
        for item in link['summary']:
            print(f"- {item}")


# ======================================================================
#  分品种周度联动对比
# ======================================================================

def print_cross_symbol_comparison(result: Dict):
    symbols = result.get('symbols', {})
    rows = []
    for sym in ['IF', 'IH', 'IC', 'IM']:
        sd = symbols.get(sym, {})
        if not sd:
            continue
        rows.append((sym, sd))
    if not rows:
        return

    print("\n## 三、分品种周度联动对比\n")
    print("| 品种 | 期权标的 | 周PCR(量) | 周ATM IV | RR | 周涨跌 | 周趋势 | 基差信号 | 联动方向 | 评分 |")
    print("|------|----------|-----------|----------|----|--------|--------|----------|----------|------|")
    for sym, sd in rows:
        opt = sd.get('option', {})
        fut = sd.get('futures', {})
        link = sd.get('linkage', {})
        print(f"| **{sym}** {SYMBOL_NAME.get(sym, '')} | {OPT_NAME.get(sym, '-')} | "
              f"{opt.get('pcr_vol', '-')} | {_iv_str(opt.get('atm_iv'))} | "
              f"{opt.get('risk_reversal', '-')} | {_pct(fut.get('pct_chg'))} | "
              f"{fut.get('trend', '-')} | {fut.get('basis_signal', '-')} | "
              f"**{link.get('direction', '-')}** | {result['composite'].get('symbol_scores', {}).get(sym, '-')} |")


# ======================================================================
#  综合研判 / 投资建议 / 小s总结
# ======================================================================

def print_composite_analysis(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return
    details = comp.get('details', {})

    print("\n## 四、综合研判（周度）\n")

    print("### 积极信号\n")
    print("| 品种 | 信号类型 | 说明 |")
    print("|------|----------|------|")
    pos_count = 0
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        if d.get('direction') in ('偏多', '略偏多'):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 联动方向 | {d.get('direction')}（周度联动得分 {d.get('linkage', 0):+}） |")
            pos_count += 1
        if '升水' in d.get('basis_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 基差信号 | {d.get('basis_signal')} |")
            pos_count += 1
        if d.get('trend') and '多头' in d.get('trend', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 周趋势 | {d.get('trend')} |")
            pos_count += 1
    if pos_count == 0:
        print("| — | — | 本周暂无明确积极信号 |")

    print("\n### 风险信号\n")
    print("| 品种 | 风险类型 | 说明 |")
    print("|------|----------|------|")
    risk_count = 0
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        if d.get('direction') in ('偏空', '略偏空'):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 联动风险 | {d.get('direction')}（周度联动得分 {d.get('linkage', 0):+}） |")
            risk_count += 1
        if '贴水' in d.get('basis_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 基差风险 | {d.get('basis_signal')} |")
            risk_count += 1
        if d.get('trend') and '空头' in d.get('trend', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 周趋势 | {d.get('trend')} |")
            risk_count += 1
        if d.get('atm_iv') is not None and d.get('atm_iv') > 30:
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 波动率风险 | 周ATM IV {d.get('atm_iv')}% 偏高 |")
            risk_count += 1
    if risk_count == 0:
        print("| — | — | 本周暂无明确风险信号 |")


def print_investment_suggestions(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return
    print("\n## 五、投资建议（周度）\n")

    details = comp.get('details', {})
    suggestions = []
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        dirn = d.get('direction', '-')
        if '偏多' in dirn:
            suggestions.append(f"{SYMBOL_NAME.get(sym, '')}（{sym}）：周度联动偏多，可关注认购端波段机会")
        elif '偏空' in dirn:
            suggestions.append(f"{SYMBOL_NAME.get(sym, '')}（{sym}）：周度联动偏空，建议认沽保护或降低多头敞口")

    if suggestions:
        print("| 序号 | 策略建议 |")
        print("|------|----------|")
        for i, s in enumerate(suggestions, 1):
            print(f"| {i} | {s} |")
    else:
        print("暂无明确策略建议。")

    print("\n**周度风控提示：**")
    print("- 周均 PCR 与 IV 斜率趋势比单日数值更有参考意义，关注方向性变化")
    print("- 周度联动偏空 + 基差贴水走扩 = 中期避险信号，控制杠杆")
    print("- 周度 IV 抬升后回落（降波）对卖方有利，对买方成本不利")


def print_xiaos_summary(result: Dict, week_label: str):
    comp = result.get('composite', {})
    if not comp:
        return
    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    details = comp.get('details', {})

    print("\n## 六、小s的总结（周度）\n")
    print(f"### 关键结论（{week_label}）：\n")

    for i, sym in enumerate(['IF', 'IH', 'IC', 'IM'], 1):
        d = details.get(sym, {})
        print(f"{i}. **{SYMBOL_NAME.get(sym, '')}（{sym}）：** 周度联动方向 {d.get('direction', '-')}"
              f"（得分 {d.get('linkage', 0):+}），周{d.get('trend', '-')}，"
              f"周均PCR {d.get('pcr_vol', '-')}，周ATM IV {d.get('atm_iv', '-')}%，"
              f"RR {d.get('rr', '-')}%，基差信号{d.get('basis_signal', '-')}")

    print(f"\n### 综合：**{avg_score:.1f}/100，市场环境{market_env}**")

    bearish = sum(1 for sym in ['IF', 'IH', 'IC', 'IM']
                  if '偏空' in details.get(sym, {}).get('direction', ''))
    bullish = sum(1 for sym in ['IF', 'IH', 'IC', 'IM']
                  if '偏多' in details.get(sym, {}).get('direction', ''))
    if bearish >= 3:
        print(f"- {bearish}/4 品种周度联动偏空：认沽端保护需求持续，周度避险情绪占主导")
    elif bullish >= 3:
        print(f"- {bullish}/4 品种周度联动偏多：认购端热情持续，周度风险偏好回升")
    else:
        print(f"- 品种周度联动方向分化（{bullish}偏多 / {bearish}偏空），结构市特征明显")

    print("- 对比上周：关注 PCR 周均与 IV 斜率的边际变化（抬升/走陡 = 避险升温）")
    print("- 周度 IV 高位 + 贴水走扩组合需警惕中期回调风险")

    print("\n### 特别注意：\n")
    if avg_score < 30:
        print("- ⚠️ 周度期权-期指共振偏空，周内反弹宜减仓，优先认沽对冲")
        print("- ⚠️ 基差贴水 + IV 抬升组合，警惕恐慌抛售连锁反应")
    elif avg_score < 50:
        print("- ⚠️ 周度偏谨慎，期权认沽保护成本上升，避免裸卖认购")
        print("- ⚠️ 关注 IC/IM 贴水结构，对冲成本偏高")
    else:
        print("- ✅ 周度联动偏积极，可适度参与认购端机会")
        print("- ✅ 注意周度 IV 回落风险，控制追高成本")


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='期指期权联动分析工具（周粒度）— 基于 Tushare Pro API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 analyze_weekly_option_futures.py
  python3 analyze_weekly_option_futures.py --symbols IF IM
  python3 analyze_weekly_option_futures.py --weeks 2
  python3 analyze_weekly_option_futures.py --json
        """
    )
    parser.add_argument('--symbols', '-s', nargs='+', default=['IF', 'IH', 'IC', 'IM'],
                        choices=['IF', 'IH', 'IC', 'IM'],
                        help='分析品种（默认全部）')
    parser.add_argument('--weeks', '-w', type=int, default=1,
                        help='回溯周数（默认1周）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始分析结果')

    args = parser.parse_args()

    fetcher = OptionFuturesFetcher()
    analyzer = OptionFuturesAnalyzer(fetcher)

    if not args.json:
        print("正在采集期指期权周度数据...\n", flush=True)
    result = analyzer.analyze_weekly(symbols=args.symbols, weeks=args.weeks)

    if args.json:
        def _default_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'item'):
                return obj.item()
            return str(obj)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default_serializer))
        return

    # 取最近一周标签（任一品种）
    week_label = '-'
    for sym in args.symbols:
        sd = result['symbols'].get(sym, {})
        if sd.get('week_label'):
            week_label = sd['week_label']
            break

    print_market_overview(result, week_label)

    print("\n## 二、逐品种周度联动分析\n")
    for sym in args.symbols:
        sym_data = result['symbols'].get(sym, {})
        if not sym_data:
            print(f"\n### {SYMBOL_NAME.get(sym, sym)}（{sym}）\n**无数据**")
            continue
        print_symbol_analysis(sym, sym_data)

    print_cross_symbol_comparison(result)
    print_composite_analysis(result)
    print_investment_suggestions(result)
    print_xiaos_summary(result, week_label)

    print("\n---")
    print("\n*免责声明：以上期指期权联动分析仅供参考，不构成投资建议。衍生品交易风险高，投资需谨慎。*")
    print("\n---")
    print("\n**报告生成：小s 智能体**  ")
    print("**数据来源：Tushare Pro API**")


if __name__ == '__main__':
    main()
