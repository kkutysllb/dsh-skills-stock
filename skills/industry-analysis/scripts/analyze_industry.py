#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行业产业链综合分析命令行工具

基于同花顺i问财实时获取产业链数据（问财网关 CLI 主数据源），覆盖维度：
  - 行业概览：概念股数量、市值分布、行业归属
  - 产业链结构：上中下游环节拆解、核心公司
  - 财务分析：营收、净利润增长、估值水平
  - 风险提示：估值、政策、市场风险

数据来源：同花顺i问财（问财网关）

用法:
    python scripts/analyze_industry.py "商业航天"
    python scripts/analyze_industry.py "新能源汽车" --depth detailed
    python scripts/analyze_industry.py "人工智能" --json
    python scripts/analyze_industry.py "光伏" --save
    python scripts/analyze_industry.py --list
"""

import subprocess
import sys
import os
import json
import argparse
import io
import warnings
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd

warnings.filterwarnings('ignore')

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  问财数据层 - 问财网关 CLI 优先，pywencai 可选
# ======================================================================

class WencaiDataLayer:
    """问财数据层 - 同花顺i问财数据获取（网关 CLI 主，pywencai 可选）

    依赖已安装技能：
    - hithink-industry-query: 问财行业数据查询（CLI），用于产业链推断
    - 产业链解读: 五模块框架参考文档
    """

    def __init__(self):
        # 主数据源是问财网关 CLI（industry-query-cli.py，IWENCAI_API_KEY，
        # 纯标准库无需额外依赖）；pywencai 仅为可选增强，缺失不影响运行，
        # 因此不提示安装（避免误导 Agent 去 pip install 而放弃主路径）。
        try:
            import pywencai
            self.pywencai = pywencai
            self.available = True
        except ImportError:
            self.pywencai = None
            self.available = False

    def query(self, query_str: str, query_type: str = 'stock') -> Optional[pd.DataFrame]:
        """统一查询入口：优先网关 CLI（IWENCAI_API_KEY，稳定），pywencai 降级兜底。

        网关 CLI 不受 Node 版本影响（pywencai 依赖 node 脚本，Node 22 的
        punycode 弃用警告会污染 stdout 导致 JSON 解析失败返回 None）。
        """
        # 层1：网关 CLI（industry-query-cli.py，本项目自带，跨 Node 版本稳定）
        datas = self._query_hithink(query_str, limit=100)
        if datas:
            return pd.DataFrame(datas)
        # 层2：pywencai（若安装且可用）
        if self.available:
            try:
                df = self.pywencai.get(query=query_str, query_type=query_type)
                return df
            except Exception as e:
                print(f"  ⚠️ 问财查询失败 [{query_str}]: {e}", file=sys.stderr)
        return None

    def get_industry_overview(self, industry_name: str) -> dict:
        overview = {"industry_name": industry_name, "total_companies": 0,
                     "market_cap_total": 0, "industry_distribution": {}}
        df = self.query(f"{industry_name}概念")
        if df is None or df.empty:
            return overview
        overview["total_companies"] = len(df.drop_duplicates(subset=['股票代码']))
        cap_cols = [c for c in df.columns if '市值' in c and 'a股' in c.lower()]
        if cap_cols:
            overview["market_cap_total"] = round(pd.to_numeric(df[cap_cols[0]], errors="coerce").sum() / 1e8, 2)
        industry_col = [c for c in df.columns if '同花顺行业' in c]
        if industry_col:
            # 网关返回的行业列为 list（["电子","半导体",...]），需 explode 扁平化
            flat = df[industry_col[0]].explode().dropna()
            dist = flat.astype(str).value_counts().head(10).to_dict()
            overview["industry_distribution"] = {str(k): int(v) for k, v in dist.items()}
        return overview

    @staticmethod
    def _get_cli_path() -> str:
        """获取问财查询 CLI 脚本路径

        查找顺序：
        1. 环境变量 INDUSTRY_QUERY_CLI_PATH（显式指定）
        2. 同目录下的 industry-query-cli.py（技能包自带）
        """
        # 优先：环境变量显式指定
        env_path = os.environ.get('INDUSTRY_QUERY_CLI_PATH', '')
        if env_path and os.path.exists(env_path):
            return env_path
        # 其次：同目录下的 industry-query-cli.py（技能包自带）
        local_cli = os.path.join(_script_dir, 'industry-query-cli.py')
        if os.path.exists(local_cli):
            return local_cli
        return ''

    def _query_hithink(self, query_str: str, limit: int = 20, timeout: int = 30) -> Optional[list]:
        """通过 hithink-industry-query CLI 用自然语言查询行业数据

        利用已安装的同花顺 i问财技能，以自然语言方式获取行业数据，
        替代本地硬编码关键词匹配，实现自适应的行业分类和产业链推断。
        """
        cli_path = self._get_cli_path()
        if not os.path.exists(cli_path):
            return None
        try:
            proc = subprocess.run(
                [sys.executable, cli_path, '--query', query_str,
                 '--limit', str(limit)],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode != 0:
                return None
            result = json.loads(proc.stdout.strip())
            if result.get('success') and result.get('datas'):
                return result['datas']
        except Exception:
            pass
        return None

    def get_chain_structure(self, industry_name: str) -> dict:
        chain = {"upstream": [], "midstream": [], "downstream": []}

        # 层1: 通过统一 query() 查询产业链各环节
        for stage, key in [("上游", "upstream"), ("中游", "midstream"), ("下游", "downstream")]:
            df = self.query(f"{industry_name}概念 产业链{stage}")
            if df is None or df.empty:
                continue
            industry_name_col = [c for c in df.columns if '产业名称' in c]
            if industry_name_col:
                for sub_ind in df[industry_name_col[0]].dropna().unique()[:8]:
                    sub_df = df[df[industry_name_col[0]] == sub_ind]
                    companies = sub_df['股票简称'].dropna().unique().tolist()[:5]
                    chain[key].append({
                        "node_name": str(sub_ind), "position": stage,
                        "key_companies": [str(c) for c in companies],
                        "company_count": len(sub_df.drop_duplicates(subset=['股票代码'])),
                    })

        if not chain["upstream"] and not chain["midstream"] and not chain["downstream"]:
            # 层2: 通过 hithink-industry-query 自然语言查询（替代硬编码推断）
            chain = self._query_chain_via_hithink(industry_name)
            if not chain["upstream"] and not chain["midstream"] and not chain["downstream"]:
                # 层3: 最终回退
                chain = self._infer_chain_from_industry(industry_name)
        return chain

    def _query_chain_via_hithink(self, industry_name: str) -> dict:
        """通过 hithink-industry-query 自然语言查询产业链结构

        逐环节查询：{行业名}产业链上游/中游/下游代表公司
        利用 i问财 的自然语言理解能力自适应获取产业链数据，
        无需本地维护关键词列表。
        """
        chain = {"upstream": [], "midstream": [], "downstream": []}

        for stage, key in [("上游", "upstream"), ("中游", "midstream"), ("下游", "downstream")]:
            datas = self._query_hithink(f"{industry_name}产业链{stage}代表公司")
            if not datas:
                continue

            # 按子行业/环节聚合
            node_map = {}  # node_name -> {"companies": [], "count": 0}
            for item in datas:
                node_name = (
                    item.get('产业名称') or item.get('细分行业') or item.get('行业')
                    or item.get('同花顺行业') or item.get('环节') or ''
                )
                company = str(item.get('股票简称', item.get('公司名称', '')))

                if not node_name:
                    node_name = f"{stage}环节"

                if node_name not in node_map:
                    node_map[node_name] = {"companies": [], "count": 0}
                if company and company not in node_map[node_name]["companies"] and len(node_map[node_name]["companies"]) < 5:
                    node_map[node_name]["companies"].append(company)
                node_map[node_name]["count"] += 1

            for name, info in node_map.items():
                chain[key].append({
                    "node_name": str(name), "position": stage,
                    "key_companies": info["companies"],
                    "company_count": info["count"],
                })

        return chain

    def _infer_chain_from_industry(self, industry_name: str) -> dict:
        """最终回退：通过概念股数据推断产业链

        优先使用 hithink-industry-query 自然语言查询获取子行业位置，
        仅在 hithink 不可用时将未匹配的子行业归入下游（诚实标记"位置待定"）。
        参考"产业链解读"技能双轨制框架：
        - 实体制造型：上游资源→中游制造→下游终端
        - 数字科技型：上游基础设施→中游平台框架→下游终端应用
        """
        chain = {"upstream": [], "midstream": [], "downstream": []}
        df = self.query(f"{industry_name}概念")
        if df is None or df.empty:
            return chain
        industry_col = [c for c in df.columns if '同花顺行业' in c]
        if not industry_col:
            return chain

        sub_industries = [str(name) for name in df[industry_col[0]].dropna().unique()]

        # 优先：通过 hithink 自然语言查询，利用 i问财 公司匹配反向推断子行业位置
        position_map = self._classify_positions_via_hithink(industry_name, df, industry_col[0])

        for ind_name, group in df.groupby(industry_col[0]):
            companies = group['股票简称'].dropna().unique().tolist()[:5]
            ind_str = str(ind_name)
            # 使用 hithink 查询结果，无匹配时默认归入下游并标记位置待定
            key = position_map.get(ind_str, "downstream")
            position_label = {"upstream": "上游", "midstream": "中游", "downstream": "下游"}[key]
            if ind_str not in position_map:
                position_label = "下游（位置待定）"
            chain[key].append({
                "node_name": ind_str, "position": position_label,
                "key_companies": [str(c) for c in companies],
                "company_count": len(group.drop_duplicates(subset=['股票代码'])),
            })
        return chain

    def _classify_positions_via_hithink(self, industry_name: str,
                                        df: pd.DataFrame,
                                        industry_col: str) -> dict:
        """通过 hithink-industry-query 自然语言查询产业链各环节代表公司，
        利用公司匹配反向推断子行业的产业链位置。

        原理：i问财 对 "{行业}产业链上游" 类自然语言查询能返回该环节的公司列表，
        将这些公司映射回其所属子行业，即可确定子行业的产业链位置。
        这比本地硬编码关键词更准确，且能自适应新兴行业。
        """
        position_map = {}

        # 构建 公司名 -> 子行业 映射
        company_to_industry = {}
        for _, row in df.iterrows():
            comp = str(row.get('股票简称', ''))
            ind = str(row.get(industry_col, ''))
            if comp and ind:
                company_to_industry[comp] = ind

        # 逐环节查询，将返回的公司映射到子行业
        for stage, key in [("上游", "upstream"), ("中游", "midstream"), ("下游", "downstream")]:
            datas = self._query_hithink(f"{industry_name}产业链{stage}", limit=15)
            if not datas:
                continue
            for item in datas:
                comp = str(item.get('股票简称', ''))
                if comp in company_to_industry:
                    sub_ind = company_to_industry[comp]
                    if sub_ind not in position_map:  # 优先保留第一次匹配
                        position_map[sub_ind] = key

        return position_map

    def get_key_stocks(self, industry_name: str, top_n: int = 10) -> list:
        df = self.query(f"{industry_name}概念 市值大于50亿")
        if df is None or df.empty:
            return []
        stocks = []
        cap_cols = [c for c in df.columns if '市值' in c]
        industry_col = [c for c in df.columns if '同花顺行业' in c]
        pe_col = [c for c in df.columns if '市盈率' in c and '动' not in c]
        revenue_col = [c for c in df.columns if '营业收入' in c]
        profit_col = [c for c in df.columns if '净利润同比增长' in c or '净利润(同比增长' in c]
        if cap_cols:
            df_sorted = df.sort_values(by=cap_cols[0], ascending=False).head(top_n)
        else:
            df_sorted = df.head(top_n)
        for _, row in df_sorted.iterrows():
            s = {"stock_code": str(row.get('股票代码', '')),
                 "stock_name": str(row.get('股票简称', ''))}
            if '最新价' in df.columns:
                s["current_price"] = round(float(row.get('最新价', 0) or 0), 2)
            if '最新涨跌幅' in df.columns:
                s["change_percent"] = round(float(row.get('最新涨跌幅', 0) or 0), 2)
            if cap_cols:
                v = row.get(cap_cols[0], 0)
                s["market_cap"] = round(float(v or 0) / 1e8, 2) if v else 0
            if industry_col:
                s["industry"] = str(row.get(industry_col[0], ''))
            if pe_col:
                v = row.get(pe_col[0], None)
                s["pe_ratio"] = round(float(v), 2) if v and str(v) != 'nan' else None
            if revenue_col:
                v = row.get(revenue_col[0], None)
                s["revenue"] = round(float(v) / 1e8, 2) if v and str(v) != 'nan' else None
            if profit_col:
                v = row.get(profit_col[0], None)
                s["profit_growth"] = round(float(v), 2) if v and str(v) != 'nan' else None
            stocks.append(s)
        return stocks


# ======================================================================
#  格式化输出
# ======================================================================

W = 66

def _bar(val, max_val, width=20, fill='█', empty='░'):
    if max_val == 0: return empty * width
    return fill * int(min(abs(val) / max_val, 1.0) * width) + empty * (width - int(min(abs(val) / max_val, 1.0) * width))


# ======================================================================
#  核心分析逻辑
# ======================================================================

def analyze_industry(industry_name: str, depth: str = "full") -> dict:
    result = {"industry_name": industry_name,
              "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "analysis_depth": depth, "data_source": "同花顺i问财"}
    wencai = WencaiDataLayer()
    if not wencai.available and not os.path.exists(wencai._get_cli_path()):
        return {"error": "问财数据层不可用（pywencai 未安装且网关 CLI 缺失）"}
    result["overview"] = wencai.get_industry_overview(industry_name)
    result["chain_structure"] = wencai.get_chain_structure(industry_name)
    result["key_stocks"] = wencai.get_key_stocks(industry_name, top_n=15)
    # 摘要
    summary = [f"行业名称：{industry_name}"]
    ov = result["overview"]
    if ov.get("total_companies"): summary.append(f"概念股数量：{ov['total_companies']}只")
    if ov.get("market_cap_total"): summary.append(f"总市值：{ov['market_cap_total']:.0f}亿元")
    ch = result["chain_structure"]
    for k, l in [("upstream","上游"),("midstream","中游"),("downstream","下游")]:
        n = len(ch.get(k, []))
        c = sum(nd.get("company_count", 0) for nd in ch.get(k, []))
        if n: summary.append(f"{l}{n}个环节({c}家)")
    result["analysis_summary"] = summary
    return result


def print_analysis_result(result: dict, markdown: bool = False):
    """输出分析结果。markdown=True 时输出 Markdown 格式，否则终端格式。"""
    overview = result.get("overview", {})
    chain = result.get("chain_structure", {})
    stocks = result.get("key_stocks", [])
    summary = result.get("analysis_summary", [])

    if not markdown:
        # 终端格式（保留原样）
        print("\n" + "=" * W)
        print(f"  📊 {result.get('industry_name', '')} 行业产业链分析报告")
        print("=" * W)
        print(f"\n{'─' * W}\n  📋 行业概览\n{'─' * W}")
        print(f"  行业名称: {overview.get('industry_name', '')}")
        if overview.get('total_companies'): print(f"  概念股数量: {overview['total_companies']}只")
        if overview.get('market_cap_total'):
            cap = overview['market_cap_total']
            print(f"  总市值: {cap:.0f}亿" if cap < 10000 else f"  总市值: {cap/10000:.2f}万亿")
        dist = overview.get('industry_distribution', {})
        if dist:
            print(f"\n  行业分布 (TOP10):")
            max_val = max(dist.values()) or 1
            for name, count in list(dist.items())[:10]:
                print(f"    {name:<20} {count:>3}家  {_bar(count, max_val, 24)}")
        print(f"\n{'─' * W}\n  🔗 产业链结构\n{'─' * W}")
        for sk, sl in [("upstream","⬆️ 上游"),("midstream","➡️ 中游"),("downstream","⬇️ 下游")]:
            nodes = chain.get(sk, [])
            if nodes:
                total = sum(n.get("company_count", 0) for n in nodes)
                print(f"\n  {sl} ({len(nodes)}个环节, {total}家公司):")
                for i, node in enumerate(nodes, 1):
                    comp_str = "、".join(node.get("key_companies", [])[:3])
                    print(f"    {i}. {node.get('node_name', '')}（{node.get('company_count', 0)}家）")
                    if comp_str: print(f"       代表公司: {comp_str}")
        if stocks:
            print(f"\n{'─' * W}\n  📈 重点个股 ({len(stocks)}只)\n{'─' * W}")
            for i, s in enumerate(stocks, 1):
                line = f"    {i}. {s.get('stock_name',''):<8} ({s.get('stock_code','')})"
                if s.get('market_cap'): line += f"  市值:{s['market_cap']:.0f}亿"
                if s.get('change_percent') is not None:
                    flag = '🔴' if s['change_percent'] > 0 else '🟢' if s['change_percent'] < 0 else '⚪'
                    line += f"  {flag}{s['change_percent']:+.2f}%"
                if s.get('pe_ratio') is not None: line += f"  PE:{s['pe_ratio']:.1f}"
                if s.get('profit_growth') is not None: line += f"  利润增长:{s['profit_growth']:+.1f}%"
                if s.get('industry'): line += f"  [{s['industry']}]"
                print(line)
        if summary:
            print(f"\n{'─' * W}\n  📝 分析摘要\n{'─' * W}")
            for item in summary: print(f"    • {item}")
        return

    # ── Markdown 格式 ──
    # 行业概览
    print("## 📋 行业概览\n")
    cap = overview.get('market_cap_total', 0)
    print(f"| 指标 | 数据 |")
    print(f"|------|------|")
    print(f"| 行业名称 | {overview.get('industry_name', '—')} |")
    if overview.get('total_companies'):
        print(f"| 概念股数量 | {overview['total_companies']}只 |")
    if cap:
        cap_str = f"{cap:.0f}亿" if cap < 10000 else f"{cap/10000:.2f}万亿"
        print(f"| 总市值 | {cap_str} |")

    # 行业分布
    dist = overview.get('industry_distribution', {})
    if dist:
        print("\n### 行业归属分布 TOP10\n")
        print("| 排名 | 行业 | 公司数量 |")
        print("|:----:|------|:--------:|")
        for i, (name, count) in enumerate(list(dist.items())[:10], 1):
            print(f"| {i} | {name} | {count} |")

    # 产业链结构
    print("\n## 🔗 产业链结构\n")
    for sk, sl, icon in [("upstream", "上游", "⬆️"), ("midstream", "中游", "➡️"), ("downstream", "下游", "⬇️")]:
        nodes = chain.get(sk, [])
        if not nodes:
            continue
        total = sum(n.get("company_count", 0) for n in nodes)
        print(f"### {icon} {sl}（{len(nodes)}个环节，{total}家公司）\n")
        print("| 序号 | 环节名称 | 公司数量 | 代表公司 |")
        print("|:----:|----------|:--------:|----------|")
        for i, node in enumerate(nodes, 1):
            comp_str = "、".join(node.get("key_companies", [])[:3])
            print(f"| {i} | {node.get('node_name', '')} | {node.get('company_count', 0)} | {comp_str or '—'} |")
        print()

    # 重点个股
    if stocks:
        print(f"## 📈 重点个股（{len(stocks)}只）\n")
        print("| 序号 | 代码 | 名称 | 市值(亿) | 涨跌幅 | PE | 利润增长 | 行业 |")
        print("|:----:|------|------|:--------:|:------:|:--:|:--------:|------|")
        for i, s in enumerate(stocks, 1):
            chg = s.get('change_percent')
            if chg is not None:
                flag = '🔴' if chg > 0 else '🟢' if chg < 0 else '⚪'
                chg_str = f"{flag} {chg:+.2f}%"
            else:
                chg_str = '—'
            print(f"| {i} | {s.get('stock_code', '')} | {s.get('stock_name', '')} | "
                  f"{s.get('market_cap', 0):.0f} | {chg_str} | "
                  f"{s.get('pe_ratio', '—') if s.get('pe_ratio') is not None else '—'} | "
                  f"{s.get('profit_growth', '—') if s.get('profit_growth') is not None else '—'} | "
                  f"{s.get('industry', '—')} |")
        print()

    # 分析摘要
    if summary:
        print("## 📝 分析摘要\n")
        for item in summary:
            print(f"- {item}")


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='行业产业链综合分析工具 — 基于同花顺i问财数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\n示例:\n  python scripts/analyze_industry.py \"商业航天\"\n  python scripts/analyze_industry.py \"人工智能\" --json\n  python scripts/analyze_industry.py \"光伏\" --save\n  python scripts/analyze_industry.py --list\n        """)
    parser.add_argument('industry', nargs='?', help='行业/概念名称')
    parser.add_argument('--depth', choices=['full', 'detailed', 'brief'], default='full', help='分析深度')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')

    parser.add_argument('--save', action='store_true', help='保存报告到文件')
    parser.add_argument('--output-dir', '-o', type=str, default='~/kk_Claw/kkStockClaw/IndustryReport', help='报告输出目录')
    parser.add_argument('--list', action='store_true', help='列出热门行业')
    args = parser.parse_args()

    if args.list:
        print("\n📋 热门行业/概念（动态查询）:")
        print("-" * 40)
        print("  提示：请直接输入行业名称进行分析，如：")
        print("  python scripts/analyze_industry.py \"商业航天\"")
        print("  python scripts/analyze_industry.py \"人工智能\"")
        return

    if not args.industry:
        parser.print_help(); sys.exit(1)

    industry_name = args.industry
    print("=" * W)
    print(f"  行业产业链分析工具  ·  同花顺i问财")
    print("=" * W)
    print(f"  分析行业: {industry_name}  |  深度: {args.depth}")
    print(f"\n正在获取 {industry_name} 行业数据...\n")

    result = analyze_industry(industry_name, depth=args.depth)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False)); sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str)); return

    output_dir = os.path.expanduser(args.output_dir)
    report_date = datetime.now().strftime('%Y-%m-%d')

    if args.save:
        old_stdout = sys.stdout; sys.stdout = captured = io.StringIO()

    print(f"# 🏭 {industry_name} 行业产业链分析报告\n")
    print(f"**分析日期：{report_date}** | **数据来源：同花顺i问财**\n")
    print("---")

    print_analysis_result(result, markdown=True)

    print("\n---\n")
    print("*⚠️ 免责声明：以上分析仅供参考，不构成投资建议。市场有风险，投资需谨慎。*")
    print("\n---\n")
    print(f"**数据来源：同花顺i问财（问财网关）**")

    if args.save:
        sys.stdout = old_stdout; content = captured.getvalue()
        os.makedirs(output_dir, exist_ok=True)
        report_dt = datetime.now().strftime('%Y-%m-%d_%H%M')
        filename = f"{industry_name}_产业链分析_{report_dt}.md"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
        print(content)
        print(f"\n📄 报告已保存: {filepath}")


if __name__ == '__main__':
    main()
