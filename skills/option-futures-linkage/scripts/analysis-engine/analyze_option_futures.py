#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期指期权联动分析工具（日粒度）

数据全部来自 Tushare Pro API，不依赖本地数据库。
覆盖维度：
  - 期权维度：认沽认购（成交量/持仓量 PCR）、波动率（ATM IV/加权 IV，BS 反解）、
    IV 斜率（认沽端/认购端回归）、Risk Reversal、认沽认购 IV 差
  - 期指维度：主力合约行情、均线趋势、持仓变化、基差贴升水
  - 联动维度：期权信号 × 期指信号共振/背离，5 维联动信号 + 分品种评分

品种映射（期指 → 期权标的）：
  IF → SSE 300ETF 期权（510300.SH）
  IH → SSE 50ETF 期权（510050.SH）
  IC → SSE 500ETF 期权（510500.SH）
  IM → CFFEX MO 中证1000 股指期权（000852.SH 指数为标的）

用法:
    python3 analyze_option_futures.py
    python3 analyze_option_futures.py --symbols IF IM
    python3 analyze_option_futures.py --days 30
    python3 analyze_option_futures.py --json
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
#  市场概览
# ======================================================================

def print_market_overview(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return

    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    div_sig = comp.get('divergence_signal', '-')

    print("\n## 一、市场概览\n")
    print(f"**综合评分：{avg_score:.1f}/100**")
    print(f"{_bar(avg_score, 100)}")
    print(f"**市场环境：{market_env}**")
    print(f"**品种分化：{div_sig}**")

    scores = comp.get('symbol_scores', {})
    details = comp.get('details', {})
    if scores:
        print("\n### 各品种联动评分\n")
        print("| 品种 | 期权标的 | 综合评分 | 期指趋势 | 基差信号 | 联动方向 | 联动得分 |")
        print("|------|----------|----------|----------|----------|----------|----------|")
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
#  逐品种联动分析
# ======================================================================

def print_symbol_analysis(sym: str, sym_data: Dict):
    print(f"\n### {SYMBOL_NAME.get(sym, sym)}（{sym}）— 期权标的：{OPT_NAME.get(sym, '-')}\n")

    opt = sym_data.get('option', {})
    fut = sym_data.get('futures', {})
    link = sym_data.get('linkage', {})

    if opt.get('error'):
        print(f"**期权数据异常：** {opt['error']}")
        print(f"**期指数据异常：** {fut.get('error', '无')}")
        print(f"**联动：** {link.get('direction', '-')}（{link.get('score', 0):+}）")
        return

    # 1. 期权维度
    print("#### 1. 期权维度（认沽认购 / 波动率 / IV斜率 / PCR）\n")
    print("| 指标 | 数值 | 解读 |")
    print("|------|------|------|")
    pcr_v = opt.get('pcr_vol')
    pcr_v_sig = '认沽偏多（避险情绪浓）' if pcr_v is not None and pcr_v > 1.2 else \
                '认购偏多（看涨情绪浓）' if pcr_v is not None and pcr_v < 0.8 else '中性'
    print(f"| 成交量 PCR（认沽/认购） | **{pcr_v if pcr_v is not None else '-'}** | {pcr_v_sig} |")
    pcr_o = opt.get('pcr_oi')
    pcr_o_sig = '保护性认沽持仓多（偏空）' if pcr_o is not None and pcr_o > 1.0 else \
                '认购持仓多（偏多）' if pcr_o is not None and pcr_o < 0.7 else '中性'
    print(f"| 持仓量 PCR | {pcr_o if pcr_o is not None else '-'} | {pcr_o_sig} |")
    atm = opt.get('atm_iv')
    print(f"| ATM 隐含波动率 | {_iv_str(atm)} | 近月平值期权 IV |")
    wiv = opt.get('weighted_iv')
    wiv_sig = '高波动（恐慌）' if wiv is not None and wiv > 30 else \
              '低波动（平稳）' if wiv is not None and wiv < 18 else '正常'
    print(f"| 加权 IV（按成交量） | {_iv_str(wiv)} | {wiv_sig} |")
    sp = opt.get('iv_slope_put')
    sc = opt.get('iv_slope_call')
    print(f"| 认沽端 IV 斜率 | {sp if sp is not None else '-'} ‰ | 认沽 OTM IV~K 回归斜率 |")
    print(f"| 认购端 IV 斜率 | {sc if sc is not None else '-'} ‰ | 认购 OTM IV~K 回归斜率 |")
    rr = opt.get('risk_reversal')
    rr_sig = '认沽端偏贵（偏空）' if rr is not None and rr > 0.5 else \
             '认购端偏贵（偏多）' if rr is not None and rr < -0.5 else '中性'
    print(f"| Risk Reversal（认沽-认购 IV） | {rr if rr is not None else '-'} % | {rr_sig} |")
    pcd = opt.get('put_call_iv_diff')
    pcd_sig = '认沽IV高（偏空）' if pcd is not None and pcd > 1.5 else \
              '认购IV高（偏多）' if pcd is not None and pcd < -1.5 else '中性'
    print(f"| 认沽认购 IV 差（ATM） | {pcd if pcd is not None else '-'} % | {pcd_sig} |")
    print(f"| 标的收盘 | {opt.get('underlying_price', '-')} | 期权标的资产价格 |")
    print(f"| 交易日 | {_fmt_date(opt.get('trade_date'))} | 数据日期 |")

    rows = opt.get('detail_rows', [])
    if rows:
        print("\n**活跃合约 IV 明细（成交量前8）：**\n")
        print("| 合约 | 类型 | 行权价 | IV | 成交量 |")
        print("|------|------|--------|----|--------|")
        for r in rows:
            cp = '认购' if r['call_put'] in ('C', '认购', 'c') else '认沽'
            print(f"| {r['ts_code']} | {cp} | {r['K']:.0f} | {r['iv']:.2f}% | {_num(r['vol'])} |")

    # 2. 期指维度
    print("\n#### 2. 期指维度\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    print(f"| 主力合约 | {fut.get('main_contract', '-')} | 期指主力 |")
    print(f"| 收盘价 | {fut.get('close', '-')} | 最新收盘 |")
    print(f"| 涨跌幅 | {_pct(fut.get('pct_chg'))} | 当日涨跌 |")
    print(f"| 趋势判断 | {fut.get('trend', '-')} | 均线排列 |")
    print(f"| 持仓量 | {_num(fut.get('oi'))} | {fut.get('oi_chg', 0):+,} |")
    print(f"| 基差 | {fut.get('basis', '-')} | 期指-现货指数 |")
    print(f"| 基差率 | {_pct(fut.get('basis_rate'))} | 基差/现货 |")
    print(f"| 基差信号 | {fut.get('basis_signal', '-')} | 贴升水情绪 |")
    print(f"| 交易日 | {_fmt_date(fut.get('trade_date'))} | 数据日期 |")

    # 3. 联动信号
    print("\n#### 3. 联动信号（期权 × 期指）\n")
    print("| 联动维度 | 期权信号 | 期指信号 | 结论 | 得分 |")
    print("|----------|----------|----------|------|------|")
    for s in link.get('signals', []):
        score = s.get('score', 0)
        mark = '✅' if score > 0 else '⚠️' if score < 0 else '➖'
        print(f"| {s['name']} | {s['option_signal']} | {s['futures_signal']} | {s['conclusion']} | {mark} {score:+} |")
    print(f"\n**联动评分：{link.get('score', 0):+} → 方向：{link.get('direction', '-')}**")
    if link.get('summary'):
        print("**信号要点：**")
        for item in link['summary']:
            print(f"- {item}")


# ======================================================================
#  分品种联动对比
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

    print("\n## 三、分品种联动对比\n")
    print("| 品种 | 期权标的 | PCR(量) | ATM IV | RR | 期指涨跌 | 趋势 | 基差信号 | 联动方向 | 评分 |")
    print("|------|----------|---------|--------|----|----------|------|----------|----------|------|")
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

    print("\n## 四、综合研判\n")

    print("### 积极信号\n")
    print("| 品种 | 信号类型 | 说明 |")
    print("|------|----------|------|")
    pos_count = 0
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        if d.get('direction') in ('偏多', '略偏多'):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 联动方向 | {d.get('direction')}（联动得分 {d.get('linkage', 0):+}） |")
            pos_count += 1
        if '升水' in d.get('basis_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 基差信号 | {d.get('basis_signal')} |")
            pos_count += 1
        if d.get('trend') and '多头' in d.get('trend', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 趋势信号 | {d.get('trend')} |")
            pos_count += 1
    if pos_count == 0:
        print("| — | — | 当前市场暂无明确积极信号 |")

    print("\n### 风险信号\n")
    print("| 品种 | 风险类型 | 说明 |")
    print("|------|----------|------|")
    risk_count = 0
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        if d.get('direction') in ('偏空', '略偏空'):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 联动风险 | {d.get('direction')}（联动得分 {d.get('linkage', 0):+}） |")
            risk_count += 1
        if '贴水' in d.get('basis_signal', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 基差风险 | {d.get('basis_signal')} |")
            risk_count += 1
        if d.get('trend') and '空头' in d.get('trend', ''):
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 趋势风险 | {d.get('trend')} |")
            risk_count += 1
        if d.get('atm_iv') is not None and d.get('atm_iv') > 30:
            print(f"| {SYMBOL_NAME.get(sym, '')}({sym}) | 波动率风险 | ATM IV {d.get('atm_iv')}% 偏高 |")
            risk_count += 1
    if risk_count == 0:
        print("| — | — | 当前市场暂无明确风险信号 |")


def print_investment_suggestions(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return
    print("\n## 五、投资建议\n")

    details = comp.get('details', {})
    suggestions = []
    for sym in ['IF', 'IH', 'IC', 'IM']:
        d = details.get(sym, {})
        dirn = d.get('direction', '-')
        if '偏多' in dirn:
            suggestions.append(f"{SYMBOL_NAME.get(sym, '')}（{sym}）：期权-期指联动偏多，可关注认购端机会（注意 IV 高位回落风险）")
        elif '偏空' in dirn:
            suggestions.append(f"{SYMBOL_NAME.get(sym, '')}（{sym}）：期权-期指联动偏空，可关注认沽端保护或对冲（注意基差贴水扩大）")

    if suggestions:
        print("| 序号 | 策略建议 |")
        print("|------|----------|")
        for i, s in enumerate(suggestions, 1):
            print(f"| {i} | {s} |")
    else:
        print("暂无明确策略建议。")

    print("\n**风控提示：**")
    print("- 期权为高杠杆衍生品，注意 IV 波动带来的价格非线性风险")
    print("- 认沽认购 PCR 与 IV 斜率变化领先于价格，需结合期指趋势共振确认")
    print("- 期指基差贴水扩大 + 认沽 IV 上行 = 市场避险情绪升温，减仓或对冲")


def print_xiaos_summary(result: Dict):
    comp = result.get('composite', {})
    if not comp:
        return
    avg_score = comp.get('avg_score', 50)
    market_env = comp.get('market_env', '-')
    details = comp.get('details', {})

    print("\n## 六、小s的总结\n")
    print("### 关键结论：\n")

    for i, sym in enumerate(['IF', 'IH', 'IC', 'IM'], 1):
        d = details.get(sym, {})
        print(f"{i}. **{SYMBOL_NAME.get(sym, '')}（{sym}）：** 联动方向 {d.get('direction', '-')}"
              f"（得分 {d.get('linkage', 0):+}），期指{d.get('trend', '-')}，"
              f"PCR {d.get('pcr_vol', '-')}，ATM IV {d.get('atm_iv', '-')}%，"
              f"RR {d.get('rr', '-')}%，基差信号{d.get('basis_signal', '-')}")

    print(f"\n### 综合：**{avg_score:.1f}/100，市场环境{market_env}**")

    bearish = sum(1 for sym in ['IF', 'IH', 'IC', 'IM']
                  if '偏空' in details.get(sym, {}).get('direction', ''))
    bullish = sum(1 for sym in ['IF', 'IH', 'IC', 'IM']
                  if '偏多' in details.get(sym, {}).get('direction', ''))
    if bearish >= 3:
        print(f"- {bearish}/4 品种期权-期指联动偏空：认沽端保护需求强，市场避险情绪占主导")
    elif bullish >= 3:
        print(f"- {bullish}/4 品种期权-期指联动偏多：认购端热情高，市场风险偏好回升")
    else:
        print(f"- 品种联动方向分化（{bullish}偏多 / {bearish}偏空），结构市特征明显，宜精选品种")

    print("- 关注认沽认购 PCR 与 IV 斜率的边际变化：PCR 抬升 + 认沽斜率走陡 = 避险升温")
    print("- 期权 IV 处于高位时注意降波风险（卖方回补 / 买方成本高）")

    print("\n### 特别注意：\n")
    if avg_score < 30:
        print("- ⚠️ 期权-期指共振偏空，严格控制仓位，优先用认沽对冲")
        print("- ⚠️ 期指基差贴水扩大 + IV 上行，警惕恐慌抛售连锁")
    elif avg_score < 50:
        print("- ⚠️ 市场偏谨慎，期权端认沽保护成本上升，避免裸卖认购")
        print("- ⚠️ 关注 IC/IM 贴水结构，对冲成本偏高")
    else:
        print("- ✅ 期权-期指联动偏积极，可适度参与认购端机会")
        print("- ✅ 注意 IV 回落对期权买方的影响，控制追高成本")


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='期指期权联动分析工具（日粒度）— 基于 Tushare Pro API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 analyze_option_futures.py
  python3 analyze_option_futures.py --symbols IF IM
  python3 analyze_option_futures.py --days 30
  python3 analyze_option_futures.py --json
        """
    )
    parser.add_argument('--symbols', '-s', nargs='+', default=['IF', 'IH', 'IC', 'IM'],
                        choices=['IF', 'IH', 'IC', 'IM'],
                        help='分析品种（默认全部）')
    parser.add_argument('--days', '-d', type=int, default=30,
                        help='行情回溯天数（默认30）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始分析结果')

    args = parser.parse_args()

    fetcher = OptionFuturesFetcher()
    analyzer = OptionFuturesAnalyzer(fetcher)

    if not args.json:
        print("正在采集期指期权数据...\n", flush=True)
    result = analyzer.analyze_all(symbols=args.symbols, days=args.days)

    if args.json:
        def _default_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            if hasattr(obj, 'item'):
                return obj.item()
            return str(obj)

        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default_serializer))
        return

    print_market_overview(result)

    print("\n## 二、逐品种联动分析\n")
    for sym in args.symbols:
        sym_data = result['symbols'].get(sym, {})
        if not sym_data:
            print(f"\n### {SYMBOL_NAME.get(sym, sym)}（{sym}）\n**无数据**")
            continue
        print_symbol_analysis(sym, sym_data)

    print_cross_symbol_comparison(result)
    print_composite_analysis(result)
    print_investment_suggestions(result)
    print_xiaos_summary(result)

    print("\n---")
    print("\n*免责声明：以上期指期权联动分析仅供参考，不构成投资建议。衍生品交易风险高，投资需谨慎。*")
    print("\n---")
    print("\n**报告生成：小s 智能体**  ")
    print("**数据来源：Tushare Pro API**")


if __name__ == '__main__':
    main()
