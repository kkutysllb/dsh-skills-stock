#!/usr/bin/env python3
"""
股本股东信息深度分析 + 事件统计引擎

基于已安装的技能：
  - hithink-management-query：股东股本查询（问财 API）
  - hithink-event-query：事件数据查询（问财 API）
  - tushare-data：stk_holdernumber / top10_holders / top10_floatholders / stk_holdertrade

核心功能：
  1. 股本结构分析 — 总股本/流通股/限售股 + 变动历史
  2. 股东户数趋势 — 户数变化 + 户均持股 + 筹码集中度判断
  3. 前十大股东 — 持股比例 + 变动 + 机构/个人分类
  4. 前十大流通股东 — 机构持仓明细
  5. 股东增减持统计 — 大股东/高管增减持金额 + 方向
  6. 实控人信息 — 实际控制人 + 控制链
  7. 股权质押风险 — 质押比例 + 质押方 + 预警线
  8. 事件统计 — 业绩预告/增发/解禁/监管函等分类统计 + 时间线
  9. 综合股东面评分 — 0-100 综合健康度

数据来源：
  - Tushare Pro API（stk_holdernumber / top10_holders / top10_floatholders / stk_holdertrade）
  - 问财 hithink-management-query（股本结构/实控人/质押/高管）
  - 问财 hithink-event-query（事件统计）

用法：
  python3 analyze_stock_shareholder.py --stock 600519.SH --json
  python3 analyze_stock_shareholder.py --stock 贵州茅台 --json
"""

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime

try:
    import numpy as np
except ImportError:
    np = None

# ============================================================
# 路径常量 — 已安装技能 CLI
# ============================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_PROJECT_ROOT)))

# 已安装技能 CLI 路径
_MANAGEMENT_CLI = os.path.join(
    _REPO_ROOT, "server", "skills", "hithink-management-query", "scripts", "cli.py"
)
_EVENT_CLI = os.path.join(
    _REPO_ROOT, "server", "skills", "hithink-event-query", "scripts", "cli.py"
)


def _run_cli(cli_path: str, query: str, limit: str = "10") -> dict:
    """调用问财技能 CLI"""
    if not os.path.isfile(cli_path):
        return {"error": f"CLI脚本不存在: {cli_path}"}
    try:
        result = subprocess.run(
            [sys.executable or "python3", cli_path,
             "--query", query, "--limit", limit],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"error": f"CLI执行失败: {result.stderr[:300]}"}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "CLI执行超时(60s)"}
    except json.JSONDecodeError as e:
        return {"error": f"CLI返回非JSON: {str(e)[:200]}"}
    except Exception as e:
        return {"error": f"CLI异常: {str(e)[:200]}"}


# ============================================================
# Tushare 数据获取
# ============================================================

class TushareShareholderFetcher:
    """Tushare 股东数据获取"""

    def __init__(self):
        self.pro = None
        try:
            from kk_common import get_finance_data_gateway
            token = os.getenv("TUSHARE_TOKEN")
            if token:
                self.pro = get_finance_data_gateway()
        except ImportError:
            pass

    @staticmethod
    def normalize_stock(stock: str) -> str:
        stock = stock.strip()
        if stock.isdigit() and len(stock) == 6:
            return f"{stock}.SH" if stock.startswith('6') else f"{stock}.SZ"
        return stock

    @staticmethod
    def _v(row, col: str, default=0.0):
        val = row.get(col, default)
        if val is None:
            return default
        try:
            f = float(val)
            return 0.0 if math.isnan(f) else f
        except (ValueError, TypeError):
            return default

    def fetch_all(self, ts_code: str) -> dict:
        result = {}
        if not self.pro:
            result["tushare_error"] = "TUSHARE_TOKEN 未设置"
            return result

        # 股票名称
        try:
            df = self.pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry")
            if not df.empty:
                result["stock_name"] = df.iloc[0].get("name", "")
                result["industry"] = df.iloc[0].get("industry", "")
        except Exception:
            pass

        # 1. 股东户数变化
        try:
            df = self.pro.stk_holdernumber(ts_code=ts_code)
            if df is not None and not df.empty:
                result["holder_number"] = df.sort_values("enddate").tail(8)
        except Exception as e:
            result["holder_number_error"] = str(e)

        # 2. 前十大股东
        try:
            df = self.pro.top10_holders(ts_code=ts_code)
            if df is not None and not df.empty:
                latest_date = df["ann_date"].max() if "ann_date" in df.columns else df.iloc[0].get("enddate", "")
                if "ann_date" in df.columns:
                    latest = df[df["ann_date"] == latest_date]
                elif "enddate" in df.columns:
                    latest = df[df["enddate"] == df["enddate"].max()]
                else:
                    latest = df.head(10)
                result["top10_holders"] = latest.head(10)
        except Exception as e:
            result["top10_holders_error"] = str(e)

        # 3. 前十大流通股东
        try:
            df = self.pro.top10_floatholders(ts_code=ts_code)
            if df is not None and not df.empty:
                if "ann_date" in df.columns:
                    latest = df[df["ann_date"] == df["ann_date"].max()]
                elif "enddate" in df.columns:
                    latest = df[df["enddate"] == df["enddate"].max()]
                else:
                    latest = df.head(10)
                result["top10_float_holders"] = latest.head(10)
        except Exception as e:
            result["top10_float_holders_error"] = str(e)

        # 4. 股东增减持
        try:
            df = self.pro.stk_holdertrade(
                ts_code=ts_code,
                start_date=f"{datetime.now().year - 1}0101"
            )
            if df is not None and not df.empty:
                result["holder_trades"] = df.sort_values("ann_date", ascending=False).head(20)
        except Exception as e:
            result["holder_trades_error"] = str(e)

        return result


# ============================================================
# 1. 股本结构分析（问财 management-query）
# ============================================================

def analyze_share_structure(stock_name: str) -> dict:
    """股本结构：总股本/流通股/限售股"""
    r = _run_cli(_MANAGEMENT_CLI, f"{stock_name}股本结构", "5")
    if "error" in r:
        return {"error": r["error"]}
    datas = r.get("datas", [])
    if not datas:
        return {"data_available": False, "note": "问财未返回股本结构数据"}
    return {
        "data_available": True,
        "source": "问财 hithink-management-query",
        "records": datas[:3],
    }


# ============================================================
# 2. 股东户数趋势分析（Tushare）
# ============================================================

def analyze_holder_trend(data: dict) -> dict:
    """股东户数变化趋势 + 筹码集中度"""
    df = data.get("holder_number")
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {"error": "无股东户数数据"}

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "enddate": str(r.get("enddate", "")),
            "holder_num": int(TushareShareholderFetcher._v(r, "holder_num")),
        })

    if len(rows) < 2:
        return {"holder_number_history": rows, "trend": "数据不足"}

    # 趋势判断
    recent = rows[-1]["holder_num"]
    prev = rows[-2]["holder_num"] if len(rows) >= 2 else recent
    change_pct = (recent - prev) / prev if prev > 0 else 0

    if change_pct < -0.05:
        trend = "集中（股东户数减少>5%，筹码趋向集中）"
        signal = "bullish"
    elif change_pct < -0.02:
        trend = "小幅集中"
        signal = "slightly_bullish"
    elif change_pct > 0.05:
        trend = "分散（股东户数增加>5%，筹码趋向分散）"
        signal = "bearish"
    elif change_pct > 0.02:
        trend = "小幅分散"
        signal = "slightly_bearish"
    else:
        trend = "稳定"
        signal = "neutral"

    return {
        "holder_number_history": rows,
        "latest_holder_num": recent,
        "change_pct": round(change_pct, 4),
        "trend": trend,
        "signal": signal,
    }


# ============================================================
# 3. 前十大股东分析（Tushare）
# ============================================================

def analyze_top10_holders(data: dict) -> dict:
    """前十大股东分析"""
    df = data.get("top10_holders")
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {"error": "无前十大股东数据"}

    holders = []
    total_hold = 0
    for _, r in df.iterrows():
        name = str(r.get("holder_name", ""))
        hold_ratio = TushareShareholderFetcher._v(r, "hold_ratio")
        total_hold += hold_ratio
        holders.append({
            "name": name,
            "hold_ratio": round(hold_ratio, 2),
            "hold_amount": TushareShareholderFetcher._v(r, "hold_amount"),
        })

    # 判断机构 vs 个人
    institution_keywords = ["基金", "社保", "保险", "信托", "证券", "银行", "公司", "集团",
                            "有限", "股份", "资本", "投资", "资产管理", "理财", "QFII", "香港"]
    inst_count = sum(1 for h in holders if any(k in h["name"] for k in institution_keywords))

    return {
        "holders": holders,
        "total_hold_ratio": round(total_hold, 2),
        "institution_count": inst_count,
        "individual_count": len(holders) - inst_count,
        "concentration": "高度集中" if total_hold > 60 else "中等集中" if total_hold > 40 else "分散",
    }


# ============================================================
# 4. 前十大流通股东分析（Tushare）
# ============================================================

def analyze_top10_float_holders(data: dict) -> dict:
    """前十大流通股东"""
    df = data.get("top10_float_holders")
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {"error": "无前十大流通股东数据"}

    holders = []
    for _, r in df.iterrows():
        holders.append({
            "name": str(r.get("holder_name", "")),
            "hold_ratio": round(TushareShareholderFetcher._v(r, "hold_ratio"), 2),
            "change": str(r.get("change", "")),
        })

    return {
        "holders": holders,
        "source": "Tushare Pro API",
    }


# ============================================================
# 5. 股东增减持统计（Tushare）
# ============================================================

def analyze_holder_trades(data: dict) -> dict:
    """股东增减持统计"""
    df = data.get("holder_trades")
    if df is None or (hasattr(df, 'empty') and df.empty):
        return {"data_available": False, "note": "近一年无股东增减持记录"}

    buys = []
    sells = []
    total_buy = 0
    total_sell = 0

    for _, r in df.iterrows():
        change_vol = TushareShareholderFetcher._v(r, "change_vol")
        record = {
            "holder_name": str(r.get("holder_name", "")),
            "ann_date": str(r.get("ann_date", "")),
            "change_vol": round(change_vol, 0),
            "change_ratio": round(TushareShareholderFetcher._v(r, "change_ratio"), 4),
            "holder_type": str(r.get("holder_type", "")),
        }
        if change_vol > 0:
            buys.append(record)
            total_buy += change_vol
        elif change_vol < 0:
            sells.append(record)
            total_sell += abs(change_vol)

    net = total_buy - total_sell
    direction = "净增持" if net > 0 else "净减持" if net < 0 else "平衡"

    return {
        "data_available": True,
        "buy_count": len(buys),
        "sell_count": len(sells),
        "total_buy_volume": round(total_buy, 0),
        "total_sell_volume": round(total_sell, 0),
        "net_volume": round(net, 0),
        "direction": direction,
        "recent_trades": (buys + sells)[:10],
    }


# ============================================================
# 6. 实控人信息（问财 management-query）
# ============================================================

def analyze_controller(stock_name: str) -> dict:
    """实际控制人"""
    r = _run_cli(_MANAGEMENT_CLI, f"{stock_name}实控人", "5")
    if "error" in r:
        return {"error": r["error"]}
    datas = r.get("datas", [])
    return {
        "source": "问财 hithink-management-query",
        "records": datas[:3],
        "data_available": len(datas) > 0,
    }


# ============================================================
# 7. 股权质押风险（问财 management-query）
# ============================================================

def analyze_pledge(stock_name: str) -> dict:
    """股权质押"""
    r = _run_cli(_MANAGEMENT_CLI, f"{stock_name}股权质押", "10")
    if "error" in r:
        return {"error": r["error"]}
    datas = r.get("datas", [])

    risk_level = "low"
    if datas:
        # 尝试从返回数据中提取质押比例
        for d in datas[:3]:
            for key in ["质押比例", "质押股数", "质押占股本比"]:
                val = d.get(key, "")
                if val:
                    try:
                        ratio = float(str(val).replace("%", ""))
                        if ratio > 50:
                            risk_level = "high"
                        elif ratio > 30:
                            risk_level = "medium"
                    except (ValueError, TypeError):
                        pass

    return {
        "source": "问财 hithink-management-query",
        "records": datas[:5],
        "data_available": len(datas) > 0,
        "risk_level": risk_level,
    }


# ============================================================
# 8. 事件统计（问财 event-query）
# ============================================================

def analyze_events(stock_name: str) -> dict:
    """多类型事件统计"""
    event_types = [
        ("业绩预告", "业绩预告"),
        ("增发配股", "增发"),
        ("限售解禁", "解禁"),
        ("监管函", "监管函"),
        ("股权质押变动", "质押变动"),
        ("机构调研", "调研"),
    ]

    results = {}
    total_events = 0

    for label, query_keyword in event_types:
        r = _run_cli(_EVENT_CLI, f"{stock_name}{query_keyword}", "5")
        if "error" in r:
            results[label] = {"count": 0, "error": r["error"]}
            continue

        datas = r.get("datas", [])
        count = len(datas)
        total_events += count
        results[label] = {
            "count": count,
            "records": datas[:3],
        }

    return {
        "event_categories": results,
        "total_events": total_events,
        "source": "问财 hithink-event-query",
    }


# ============================================================
# 9. 综合股东面评分
# ============================================================

def compute_shareholder_score(
    holder_trend: dict,
    top10: dict,
    trades: dict,
    pledge: dict,
    events: dict,
) -> dict:
    """股东面综合评分（0-100）"""

    score = 50  # 基础分
    details = []

    # 1. 股东户数趋势（±15分）
    trend_signal = holder_trend.get("signal", "neutral")
    if trend_signal == "bullish":
        score += 15
        details.append("股东户数显著集中 (+15)")
    elif trend_signal == "slightly_bullish":
        score += 8
        details.append("股东户数小幅集中 (+8)")
    elif trend_signal == "bearish":
        score -= 15
        details.append("股东户数显著分散 (-15)")
    elif trend_signal == "slightly_bearish":
        score -= 8
        details.append("股东户数小幅分散 (-8)")

    # 2. 前十大股东集中度（±10分）
    total_hold = top10.get("total_hold_ratio", 0)
    if total_hold > 60:
        score += 10
        details.append(f"前十大持股{total_hold:.1f}%高度集中 (+10)")
    elif total_hold > 40:
        score += 5
        details.append(f"前十大持股{total_hold:.1f}%中等集中 (+5)")
    elif total_hold < 20:
        score -= 5
        details.append(f"前十大持股{total_hold:.1f}%过于分散 (-5)")

    # 3. 股东增减持方向（±15分）
    direction = trades.get("direction", "平衡")
    if direction == "净增持":
        score += 15
        details.append("股东净增持 (+15)")
    elif direction == "净减持":
        score -= 15
        details.append("股东净减持 (-15)")

    # 4. 质押风险（-10~+5分）
    pledge_risk = pledge.get("risk_level", "low")
    if pledge_risk == "high":
        score -= 10
        details.append("质押风险高 (-10)")
    elif pledge_risk == "medium":
        score -= 5
        details.append("质押风险中等 (-5)")
    else:
        score += 5
        details.append("质押风险低 (+5)")

    # 5. 负面事件（-10~0分）
    total_events = events.get("total_events", 0)
    reg_count = events.get("event_categories", {}).get("监管函", {}).get("count", 0)
    if reg_count > 0:
        score -= min(reg_count * 3, 10)
        details.append(f"监管函{reg_count}条 (-{min(reg_count * 3, 10)})")

    score = max(0, min(100, score))

    if score >= 80:
        rating = "优秀"
    elif score >= 65:
        rating = "良好"
    elif score >= 50:
        rating = "中性"
    elif score >= 35:
        rating = "较弱"
    else:
        rating = "较差"

    return {
        "score": round(score, 1),
        "rating": rating,
        "details": details,
    }


# ============================================================
# 主分析流程
# ============================================================

def analyze_stock_shareholder(stock: str) -> dict:
    fetcher = TushareShareholderFetcher()
    ts_code = fetcher.normalize_stock(stock)
    data = fetcher.fetch_all(ts_code)

    stock_name = data.get("stock_name", ts_code.split(".")[0])

    result = {
        "stock": ts_code,
        "stock_name": stock_name,
        "industry": data.get("industry", ""),
        "analysis_type": "shareholder_and_events",
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 1. 股本结构（问财）
    result["share_structure"] = analyze_share_structure(stock_name)

    # 2. 股东户数趋势（Tushare）
    result["holder_trend"] = analyze_holder_trend(data)

    # 3. 前十大股东（Tushare）
    result["top10_holders"] = analyze_top10_holders(data)

    # 4. 前十大流通股东（Tushare）
    result["top10_float_holders"] = analyze_top10_float_holders(data)

    # 5. 股东增减持（Tushare）
    result["holder_trades"] = analyze_holder_trades(data)

    # 6. 实控人（问财）
    result["controller"] = analyze_controller(stock_name)

    # 7. 股权质押（问财）
    result["pledge"] = analyze_pledge(stock_name)

    # 8. 事件统计（问财）
    result["events"] = analyze_events(stock_name)

    # 9. 综合评分
    result["shareholder_score"] = compute_shareholder_score(
        result["holder_trend"],
        result["top10_holders"],
        result["holder_trades"],
        result["pledge"],
        result["events"],
    )

    result["data_sources"] = [
        "Tushare Pro API（股东户数/前十大股东/流通股东/增减持）",
        "问财 hithink-management-query（股本结构/实控人/质押）",
        "问财 hithink-event-query（事件统计）",
    ]
    result["disclaimer"] = "部分数据来源于同花顺问财，分析结果仅供参考，不构成投资建议"
    return result


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="股本股东信息+事件统计分析")
    parser.add_argument("--stock", "-s", required=True, help="股票代码或名称")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    result = analyze_stock_shareholder(args.stock)

    if args.json:
        # 序列化 pandas DataFrame
        def _default(obj):
            try:
                import pandas as pd
                if isinstance(obj, pd.DataFrame):
                    return obj.to_dict(orient="records")
            except ImportError:
                pass
            return str(obj)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default))
    else:
        _print_report(result)


def _print_report(r):
    print(f"\n{'='*60}")
    print(f"  股本股东分析 — {r.get('stock_name','')} ({r.get('stock','')})")
    print(f"  行业: {r.get('industry','')} | 时间: {r.get('analysis_time','')}")
    print(f"{'='*60}")

    # 股本结构
    ss = r.get("share_structure", {})
    if ss.get("data_available"):
        print(f"\n📊 股本结构: [数据来自问财]")
        for rec in ss.get("records", [])[:2]:
            print(f"  {rec}")
    else:
        print(f"\n📊 股本结构: {ss.get('note', ss.get('error', '无数据'))}")

    # 股东户数趋势
    ht = r.get("holder_trend", {})
    if "error" not in ht:
        print(f"\n📈 股东户数: 最新 {ht.get('latest_holder_num','N/A')} 户 ({ht.get('trend','')})")
        print(f"  变化率: {ht.get('change_pct',0):.2%}")
    else:
        print(f"\n📈 股东户数: {ht.get('error','')}")

    # 前十大股东
    t10 = r.get("top10_holders", {})
    if "error" not in t10:
        print(f"\n👥 前十大股东: 合计持股 {t10.get('total_hold_ratio',0):.1f}% ({t10.get('concentration','')})")
        print(f"  机构 {t10.get('institution_count',0)} / 个人 {t10.get('individual_count',0)}")
        for h in t10.get("holders", [])[:5]:
            print(f"    {h['name']}: {h['hold_ratio']:.2f}%")
    else:
        print(f"\n👥 前十大股东: {t10.get('error','')}")

    # 增减持
    tr = r.get("holder_trades", {})
    if tr.get("data_available"):
        print(f"\n💰 股东增减持: {tr.get('direction','')} | 增持{tr.get('buy_count',0)}次 减持{tr.get('sell_count',0)}次")
    else:
        print(f"\n💰 股东增减持: {tr.get('note','无数据')}")

    # 质押
    pl = r.get("pledge", {})
    print(f"\n🏦 股权质押: 风险等级 {pl.get('risk_level','N/A')}")

    # 实控人
    ct = r.get("controller", {})
    if ct.get("data_available"):
        print(f"\n👤 实控人: [问财数据]")
        for rec in ct.get("records", [])[:2]:
            print(f"  {rec}")

    # 事件统计
    ev = r.get("events", {})
    cats = ev.get("event_categories", {})
    print(f"\n📋 事件统计: 共 {ev.get('total_events',0)} 条")
    for label, info in cats.items():
        count = info.get("count", 0)
        if count > 0:
            print(f"  {label}: {count}条")

    # 综合评分
    sc = r.get("shareholder_score", {})
    print(f"\n⭐ 股东面综合评分: {sc.get('score',0):.1f}/100 ({sc.get('rating','')})")
    for d in sc.get("details", []):
        print(f"  · {d}")

    print(f"\n{'='*60}")
    print(f"  数据来源: {' / '.join(r.get('data_sources', []))}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
