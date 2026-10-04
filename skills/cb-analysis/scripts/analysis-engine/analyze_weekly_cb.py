#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可转债周度全景分析工具（模板格式）

数据来源：Tushare Pro API（cb_basic / cb_daily / cb_call / index_daily / daily 正股行情）
分析维度：市场温度（中证转债指数）/ 市场规模与结构 / 估值全景 / 资金与情绪 /
          双低策略池 / 综合研判 —— 全市场可转债周度维度

周粒度口径：按 ISO 自然周聚合（周标签形如 2026-W31），默认取最近一周；
  估值口径：转股价值 = 100 / 转股价 × 正股收盘；转股溢价率 = (转债收盘 - 转股价值) / 转股价值；
  双低值 = 转债价格 + 转股溢价率（百分点）；金额单位：cb_daily.amount 万元（换算亿元 ÷1e4），
  index_daily.amount 千元（换算亿元 ÷1e5）；remain_size 单位为元。

用法:
  python3 analyze_weekly_cb.py                 # 分析最近一周（全市场可转债）
  python3 analyze_weekly_cb.py --weeks 2       # 回溯两周（报告附近 N 周指数对比）
  python3 analyze_weekly_cb.py --json          # JSON 输出
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List

_script_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_root = os.path.dirname(_script_dir)
for _p in (_scripts_root, os.path.dirname(_scripts_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TOKEN = os.environ.get("TUSHARE_TOKEN", "")
if not TOKEN:
    print(json.dumps({"error": "TUSHARE_TOKEN 环境变量未设置"}))
    sys.exit(1)

try:
    from kk_common import get_finance_data_gateway
    pro = get_finance_data_gateway()
except Exception as e:
    print(json.dumps({"error": f"kk_common 网关不可用: {e}"}))
    sys.exit(1)


# ======================================================================
#  常量
# ======================================================================

CB_INDEX = "000832.CSI"          # 中证转债指数
CB_INDEX_NAME = "中证转债指数"


# ======================================================================
#  格式化工具
# ======================================================================

def _pct(val, sign=True) -> str:
    if val is None:
        return '-'
    prefix = ('+' if val > 0 else '') if sign else ''
    return f"{prefix}{val:.2f}%"


def _num(val, nd=2) -> str:
    if val is None:
        return '-'
    return f"{val:,.{nd}f}"


def _fmt_date(d) -> str:
    if d and len(str(d)) == 8:
        s = str(d)
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return str(d or '-')


def _chg(v):
    if v is None:
        return '—'
    icon = '▲' if v > 0 else '▼' if v < 0 else '─'
    return f"{icon} {v:+.2f}%"


def _valid(v):
    """NaN 清洗：None / float('nan') 视为无效（返回 False）。"""
    if v is None:
        return False
    try:
        return not (float(v) != float(v))
    except (TypeError, ValueError):
        return True


def _bar(val: float, max_val: float, width: int = 20,
         fill: str = '█', empty: str = '░') -> str:
    if max_val == 0:
        return empty * width
    filled = int(min(abs(val) / max_val, 1.0) * width)
    return fill * filled + empty * (width - filled)


def _score_bar(score, width=20):
    n = max(0, min(width, int(score / 100 * width)))
    return '█' * n + '░' * (width - n)


def _default_serializer(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if hasattr(obj, 'item'):
        return obj.item()
    return str(obj)


# ======================================================================
#  数据获取
# ======================================================================

def get_latest_trade_date() -> str:
    """最新交易日：优先由中证转债指数行情推断。"""
    try:
        df = pro.request("index_daily", ts_code=CB_INDEX)
        if df is not None and not df.empty:
            return str(df["trade_date"].max())
    except Exception:
        pass
    return datetime.now().strftime("%Y%m%d")


def _week_label(d: str) -> str:
    """ISO 自然周标签，如 2026-W31。"""
    dd = datetime.strptime(str(d), "%Y%m%d")
    iso = dd.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def fetch_weekly_data(weeks: int = 1) -> Dict[str, Any]:
    """采集全市场可转债周度数据。

    返回:
        {'week_labels': [...], 'market': {...}, 'index_weekly': {...},
         'valuation': {...}, 'funds': {...}, 'events': [...], 'trade_date': ...}
    """
    end = get_latest_trade_date()
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=weeks * 10 + 7)).strftime("%Y%m%d")
    result: Dict[str, Any] = {
        "trade_date": end,
        "fetch_start": start,
        "week_labels": [],
        "index_weekly": {},
        "market": {},
        "valuation": {},
        "funds": {},
        "events": [],
        "error": None,
    }

    # ── 1. 中证转债指数日线（市场温度） ──
    try:
        idx = pro.request("index_daily", ts_code=CB_INDEX, start_date=start, end_date=end)
    except Exception as e:
        idx = None
        result["error"] = f"index_daily: {e}"
    if idx is None or idx.empty:
        result["error"] = (result["error"] or "") + " 中证转债指数无数据"
        return result
    idx = idx.sort_values("trade_date").copy()
    idx["trade_date"] = idx["trade_date"].astype(str)
    idx["week"] = idx["trade_date"].map(_week_label)
    idx["amount_yi"] = idx["amount"] / 1e5          # 千元 → 亿元

    # ── 1.5 目标周窗口：交易日列表与周标签（日线/估值/条款事件均限定在该窗口内） ──
    all_weeks = sorted({w for w in idx["week"].unique()})
    result["week_labels"] = all_weeks[-max(weeks, 1):]
    week_days = [d for d in sorted(idx["trade_date"].unique())
                 if _week_label(d) in result["week_labels"]]
    result["week_days"] = week_days
    if not week_days:
        result["error"] = (result["error"] or "") + " 目标周窗口无交易日"
        return result

    # ── 2. 转债基础信息（全量，过滤存续） ──
    try:
        basic = pro.request("cb_basic")
    except Exception as e:
        basic = None
        result["error"] = (result["error"] or "") + f" cb_basic: {e}"
    basic_df = basic if (basic is not None and not basic.empty) else None

    # ── 3. 转债日线：按目标周内每个交易日拉全市场 ──
    cb_by_day: Dict[str, Any] = {}
    for td in week_days:
        try:
            d = pro.request("cb_daily", trade_date=td)
            if d is not None and not d.empty:
                d = d.copy()
                d["trade_date"] = d["trade_date"].astype(str)
                d["amount_yi"] = d["amount"] / 1e4  # 万元 → 亿元
                cb_by_day[td] = d
        except Exception:
            pass

    # ── 4. 正股行情：仅拉周首/周末两个交易日（估值快照用） ──
    stk_by_day: Dict[str, Any] = {}
    for td in (week_days[0], week_days[-1]):
        try:
            d = pro.request("daily", trade_date=td)
            if d is not None and not d.empty:
                stk_by_day[td] = d[["ts_code", "close"]]
        except Exception:
            pass

    # ── 5. 条款事件（强赎/到期公告，ann_date 落在目标周内） ──
    try:
        calls = pro.request("cb_call", start_date=start, end_date=end)
        if calls is not None and not calls.empty:
            calls = calls.copy()
            calls["ann_date"] = calls["ann_date"].astype(str)
            in_win = calls[calls["ann_date"].isin(week_days)]
            for _, r in in_win.iterrows():
                result["events"].append({
                    "ann_date": _fmt_date(r["ann_date"]),
                    "ts_code": str(r["ts_code"]),
                    "call_type": str(r.get("call_type", "")),
                    "is_call": str(r.get("is_call", "")),
                    "call_date": _fmt_date(r.get("call_date")) if _valid(r.get("call_date")) else "-",
                    "call_price": r.get("call_price") if _valid(r.get("call_price")) else None,
                })
    except Exception:
        pass

    # ── 周聚合：指数 ──
    week_list = []
    for week, g in idx.groupby("week"):
        days = g.sort_values("trade_date")
        first, last = days.iloc[0], days.iloc[-1]
        week_chg = None
        if float(first["close"]) and float(first["close"]) > 0:
            week_chg = round((float(last["close"]) / float(first["close"]) - 1) * 100, 2)
        week_list.append({
            "week": week,
            "start": str(first["trade_date"]),
            "end": str(last["trade_date"]),
            "days": len(days),
            "close_first": float(first["close"]),
            "close_last": float(last["close"]),
            "week_chg": week_chg,
            "avg_amount_yi": round(float(days["amount_yi"].mean()), 4),
            "sum_amount_yi": round(float(days["amount_yi"].sum()), 4),
            "max_amount_yi": round(float(days["amount_yi"].max()), 4),
            "detail": [
                {"date": _fmt_date(r["trade_date"]), "close": float(r["close"]),
                 "pct_chg": float(r["pct_chg"]), "amount_yi": round(float(r["amount_yi"]), 4)}
                for _, r in days.iterrows()
            ],
        })
    result["index_weekly"] = {w["week"]: w for w in week_list}

    # ── 市场周度汇总（转债日线合并） ──
    if cb_by_day:
        all_cb = []
        for td, d in cb_by_day.items():
            d = d.copy()
            d["week"] = d["trade_date"].map(_week_label)
            all_cb.append(d)
        merged = __import__("pandas").concat(all_cb, ignore_index=True)
        merged = merged[merged["week"].isin(result["week_labels"])]
        # 市场周均日成交：先按（周, 日）汇总全市场总额，再按周平均
        daily_tot = merged.groupby(["week", "trade_date"])["amount_yi"].sum().reset_index()
        week_agg = daily_tot.groupby("week").agg(
            sum_amount_yi=("amount_yi", "sum"),
            avg_amount_yi=("amount_yi", "mean"),
            max_amount_yi=("amount_yi", "max"),
        ).round(4).reset_index()
        result["funds"]["weekly"] = week_agg.to_dict("records")
        result["funds"]["trade_days"] = len(week_days)

    # ── 估值全景（周首/周末快照，双低策略池） ──
    if basic_df is not None and cb_by_day:
        _build_valuation(result, basic_df, cb_by_day, stk_by_day)

    # ── 市场规模与结构 ──
    if basic_df is not None:
        alive = basic_df[basic_df["remain_size"].fillna(0) > 0]
        result["market"]["alive_count"] = int(len(alive))
        result["market"]["total_remain_yi"] = round(
            float(alive["remain_size"].sum()) / 1e8, 2) if len(alive) else 0.0   # 元 → 亿元
        result["market"]["new_listed"] = int(basic_df["list_date"].astype(str).isin(week_days).sum())
        result["market"]["delisted"] = int(basic_df["delist_date"].astype(str).isin(week_days).sum())
    return result


def _build_valuation(result: Dict[str, Any], basic_df, cb_by_day: Dict[str, Any],
                     stk_by_day: Dict[str, Any]) -> None:
    """基于周首/周末快照计算估值全景与双低策略池。"""
    from pandas import Series
    try:
        basic = basic_df[basic_df["remain_size"].fillna(0) > 0].copy()
        basic = basic[basic["conv_price"].notna() & (basic["conv_price"].astype(float) > 0)]
        if basic.empty:
            return
        basic = basic[["ts_code", "bond_short_name", "stk_code", "conv_price", "remain_size"]]
        basic["conv_price"] = basic["conv_price"].astype(float)
        basic["remain_yi"] = basic["remain_size"].astype(float) / 1e8   # 元 → 亿元

        weekly_vals = {}
        for td in cb_by_day:
            cb = cb_by_day[td][["ts_code", "close"]]
            stk = stk_by_day.get(td)
            if stk is None or stk.empty:
                continue
            stk = stk.rename(columns={"ts_code": "stk_code", "close": "stk_close"})
            m = basic.merge(cb, on="ts_code", how="inner").merge(stk, on="stk_code", how="left")
            m = m[m["stk_close"].notna() & (m["stk_close"].astype(float) > 0)]
            if m.empty:
                continue
            m["close"] = m["close"].astype(float)
            m["stk_close"] = m["stk_close"].astype(float)
            m["conv_value"] = 100 / m["conv_price"] * m["stk_close"]
            m["premium_rt"] = (m["close"] - m["conv_value"]) / m["conv_value"] * 100
            m["double_low"] = m["close"] + m["premium_rt"]
            weekly_vals[td] = m
        if not weekly_vals:
            return

        tds = sorted(weekly_vals.keys())
        first_td, last_td = tds[0], tds[-1]
        first, last = weekly_vals[first_td], weekly_vals[last_td]

        def _stat(df):
            return {
                "avg_price": round(float(df["close"].mean()), 2),
                "avg_premium_rt": round(float(df["premium_rt"].mean()), 2),
                "avg_double_low": round(float(df["double_low"].mean()), 2),
                "median_price": round(float(df["close"].median()), 2),
                "lt100": int((df["close"] < 100).sum()),
                "b100_120": int(((df["close"] >= 100) & (df["close"] < 120)).sum()),
                "b120_150": int(((df["close"] >= 120) & (df["close"] < 150)).sum()),
                "ge150": int((df["close"] >= 150).sum()),
                "avg_remain_yi": round(float(df["remain_yi"].mean()), 2),
            }

        result["valuation"] = {
            "first_date": first_td, "last_date": last_td,
            "first": _stat(first), "last": _stat(last),
            "double_low_top10": [
                {"ts_code": r["ts_code"], "name": r["bond_short_name"],
                 "price": round(float(r["close"]), 2),
                 "premium_rt": round(float(r["premium_rt"]), 2),
                 "double_low": round(float(r["double_low"]), 2)}
                for _, r in last.nsmallest(10, "double_low").iterrows()
            ],
        }
    except Exception as e:
        result["error"] = (result["error"] or "") + f" 估值计算: {e}"


# ======================================================================
#  综合研判：评分 / 信号
# ======================================================================

def _score_week(result: Dict[str, Any], week: str) -> Dict[str, Any]:
    """单周聚合信号：指数涨跌 / 溢价率变化 / 成交活跃 / 估值水位 → 评分（0-100）。"""
    score = 50
    signals = []
    iw = result.get("index_weekly", {}).get(week, {})
    val = result.get("valuation", {})
    funds = result.get("funds", {})

    chg = iw.get("week_chg")
    if chg is not None:
        if chg >= 1.0:
            score += 15
            signals.append(f"指数周涨 {_pct(chg)}，转债市场多头占优")
        elif chg <= -1.0:
            score -= 15
            signals.append(f"指数周跌 {_pct(chg)}，转债市场空头占优")
        else:
            signals.append(f"指数周内震荡（{_pct(chg)}）")

    if val and val.get("first") and val.get("last"):
        prem_chg = val["last"]["avg_premium_rt"] - val["first"]["avg_premium_rt"]
        if prem_chg > 2.0:
            score -= 10
            signals.append(f"平均转股溢价率抬升 {prem_chg:+.2f}pct，股性弱化（偏防御）")
        elif prem_chg < -2.0:
            score += 10
            signals.append(f"平均转股溢价率回落 {prem_chg:+.2f}pct，股性修复（偏进攻）")
        else:
            signals.append(f"平均转股溢价率 {val['last']['avg_premium_rt']:.1f}%（周内{prem_chg:+.2f}pct）")
        dl = val["last"]["avg_double_low"]
        if dl < 130:
            score += 8
            signals.append(f"平均双低 {dl:.1f}，估值水位偏低（有安全边际）")
        elif dl > 160:
            score -= 8
            signals.append(f"平均双低 {dl:.1f}，估值水位偏高（需谨慎）")
        else:
            signals.append(f"平均双低 {dl:.1f}，估值中性")

    for w in funds.get("weekly", []):
        if w.get("week") == week:
            avg = float(w.get("avg_amount_yi", 0))
            if avg >= 150:
                score += 8
                signals.append(f"转债周均日成交 {avg:.0f} 亿，交投活跃")
            elif avg < 80:
                score -= 8
                signals.append(f"转债周均日成交 {avg:.0f} 亿，交投清淡")
            else:
                signals.append(f"转债周均日成交 {avg:.0f} 亿，交投中性")
            break

    score = max(0, min(100, score))
    direction = "偏多" if score >= 58 else "偏空" if score <= 42 else "中性震荡"
    return {"score": score, "direction": direction, "signals": signals}


# ======================================================================
#  报告输出（Markdown 模板格式）
# ======================================================================

def print_market_overview(result: Dict[str, Any], week: str):
    iw = result.get("index_weekly", {}).get(week, {})
    if not iw:
        print("\n## 一、市场温度\n")
        print("本周无中证转债指数数据。")
        return
    print("\n## 一、市场温度（中证转债指数 000832.CSI）\n")
    print(f"**分析周：{week}**（{iw['start']} ~ {iw['end']}，{iw['days']} 个交易日；"
          f"{result.get('trade_date', '')} 数据快照）\n")
    print("| 指标 | 数值 | 说明 |")
    print("|------|------|------|")
    print(f"| 周初收盘 | {_num(iw['close_first'])} | 周内首个交易日 |")
    print(f"| 周末收盘 | {_num(iw['close_last'])} | 周内最后交易日 |")
    print(f"| 周涨跌幅 | **{_pct(iw.get('week_chg'))}** | 周首→周末累计 |")
    print(f"| 周均日成交 | {_num(iw.get('avg_amount_yi'))} 亿 | 指数口径（千元÷1e5） |")
    print(f"| 周成交总额 | {_num(iw.get('sum_amount_yi'))} 亿 | 周内累计 |")

    print("\n**周内每日明细：**\n")
    print("| 日期 | 收盘 | 涨跌幅 | 成交额(亿) |")
    print("|------|------|--------|-----------|")
    for r in iw.get("detail", []):
        print(f"| {r['date']} | {_num(r['close'])} | {_pct(r['pct_chg'])} | {_num(r['amount_yi'])} |")

    weeks = [w for w in sorted(result.get("index_weekly", {}).keys())
             if w in result.get("week_labels", [])]
    if len(weeks) > 1:
        print("\n**近 N 周指数走势对比：**\n")
        print("| 周 | 周初 | 周末 | 周涨跌幅 | 周均成交(亿) |")
        print("|----|------|------|----------|--------------|")
        for wk in weeks:
            w = result["index_weekly"][wk]
            mark = " ← 本周" if wk == week else ""
            print(f"| {wk}{mark} | {w['start']} | {w['end']} | {_pct(w.get('week_chg'))} | {_num(w.get('avg_amount_yi'))} |")


def print_market_structure(result: Dict[str, Any], week: str):
    m = result.get("market", {})
    print("\n## 二、市场规模与结构\n")
    print(f"| 指标 | 数值 |")
    print("|------|------|")
    print(f"| 存续可转债 | {m.get('alive_count', '-')} 只 |")
    print(f"| 存续总余额 | {m.get('total_remain_yi', '-')} 亿元 |")
    print(f"| 周内新上市 | {m.get('new_listed', '-')} 只 |")
    print(f"| 周内退市 | {m.get('delisted', '-')} 只 |")

    events = result.get("events", [])
    if events:
        print(f"\n**周内条款事件（强赎/到期公告）：**\n")
        print("| 公告日 | 转债 | 类型 | 状态 | 赎回/到期日 | 赎回价 |")
        print("|--------|------|------|------|-------------|--------|")
        for e in events:
            cp = _num(e.get("call_price")) if e.get("call_price") is not None else "-"
            print(f"| {e['ann_date']} | {e['ts_code']} | {e['call_type']} | {e['is_call']} | "
                  f"{e['call_date']} | {cp} |")
    else:
        print("\n**周内无强赎/到期公告。**")


def print_valuation(result: Dict[str, Any], week: str):
    val = result.get("valuation", {})
    print("\n## 三、估值全景（全市场快照）\n")
    if not val:
        print("估值数据缺失（正股行情或转债日线不可用）。")
        return
    f, l = val.get("first", {}), val.get("last", {})
    print(f"**周初（{_fmt_date(val.get('first_date'))}）→ 周末（{_fmt_date(val.get('last_date'))}）**\n")
    print("| 指标 | 周初 | 周末 | 周变化 |")
    print("|------|------|------|--------|")
    prem_chg = (l.get("avg_premium_rt", 0) - f.get("avg_premium_rt", 0)) if f and l else None
    print(f"| 平均转债价格 | {_num(f.get('avg_price'))} | {_num(l.get('avg_price'))} | "
          f"{_chg((l.get('avg_price', 0) - f.get('avg_price', 0)) / f.get('avg_price', 1) * 100) if f.get('avg_price') else '—'} |")
    print(f"| 平均转股溢价率 | {_num(f.get('avg_premium_rt'))}% | {_num(l.get('avg_premium_rt'))}% | "
          f"{_pct(prem_chg) if prem_chg is not None else '—'}pct |")
    print(f"| 平均双低值 | {_num(f.get('avg_double_low'))} | {_num(l.get('avg_double_low'))} | "
          f"{(l.get('avg_double_low', 0) - f.get('avg_double_low', 0)):+.2f} |")
    print(f"| 中位价格 | {_num(f.get('median_price'))} | {_num(l.get('median_price'))} | — |")
    print(f"| 平均存续余额 | {_num(f.get('avg_remain_yi'))} 亿 | {_num(l.get('avg_remain_yi'))} 亿 | — |")

    print("\n**价格分布（周末，只数）：**\n")
    print("| 区间 | 只数 | 占比 |")
    print("|------|------|------|")
    total = sum(l.get(k, 0) for k in ("lt100", "b100_120", "b120_150", "ge150"))
    for label, key in (("低价 <100", "lt100"), ("100 ≤ P < 120", "b100_120"),
                       ("120 ≤ P < 150", "b120_150"), ("高价 ≥150", "ge150")):
        n = l.get(key, 0)
        pct = f"{n / total * 100:.1f}%" if total else "0.0%"
        print(f"| {label} | {n} | {pct} |")

    top = val.get("double_low_top10", [])
    if top:
        print("\n**双低策略池（周末，双低值 = 价格 + 转股溢价率）：**\n")
        print("| 排名 | 转债 | 价格 | 转股溢价率 | 双低值 |")
        print("|------|------|------|-----------|--------|")
        for i, r in enumerate(top, 1):
            print(f"| {i} | {r['name']} {r['ts_code']} | {_num(r['price'])} | "
                  f"{_pct(r['premium_rt'])} | **{_num(r['double_low'])}** |")


def print_funds(result: Dict[str, Any], week: str):
    funds = result.get("funds", {})
    print("\n## 四、资金与情绪\n")
    weekly = {w.get("week"): w for w in funds.get("weekly", [])}
    w = weekly.get(week)
    if not w:
        print("周度成交数据缺失。")
        return
    print("| 指标 | 数值 |")
    print("|------|------|")
    print(f"| 转债周成交总额 | {_num(w.get('sum_amount_yi'))} 亿 |")
    print(f"| 转债周均日成交 | {_num(w.get('avg_amount_yi'))} 亿 |")
    print(f"| 单日最大成交 | {_num(w.get('max_amount_yi'))} 亿 |")
    print(f"| 周内交易日 | {funds.get('trade_days', '-')} 天 |")


def print_composite_analysis(result: Dict[str, Any], week: str):
    print("\n## 五、综合研判\n")
    sc = _score_week(result, week)
    print(f"**综合评分：{sc['score']}/100**")
    print(f"{_score_bar(sc['score'])}")
    print(f"**市场方向：{sc['direction']}**\n")
    print("**信号明细：**\n")
    for s in sc["signals"]:
        print(f"- {s}")

    pos = [s for s in sc["signals"] if s.startswith("指数周涨") or "修复" in s or "偏低" in s or "活跃" in s]
    risk = [s for s in sc["signals"] if s.startswith("指数周跌") or "弱化" in s or "偏高" in s or "清淡" in s]
    print("\n### 积极信号\n")
    if pos:
        for s in pos:
            print(f"- ✅ {s}")
    else:
        print("- 本周暂无明确积极信号")
    print("\n### 风险信号\n")
    if risk:
        for s in risk:
            print(f"- ⚠️ {s}")
    else:
        print("- 本周暂无明确风险信号")

    events = result.get("events", [])
    if events:
        print("\n### 条款事件提示\n")
        for e in events[:6]:
            rd = f'（赎回日 {e["call_date"]}）' if e['call_date'] != '-' else ''
            print(f"- {e['ann_date']} {e['ts_code']} {e['call_type']}：{e['is_call']}{rd}")


def print_xiaos_summary(result: Dict[str, Any], week: str):
    print("\n## 六、小s的总结\n")
    iw = result.get("index_weekly", {}).get(week, {})
    sc = _score_week(result, week)
    val = result.get("valuation", {}).get("last", {})
    m = result.get("market", {})

    chg = iw.get("week_chg")
    icon = '📉' if chg is not None and chg < 0 else '📈' if chg is not None and chg > 0 else '➡️'
    print(f"### 关键结论（{week}）：\n")
    print(f"1. **市场温度：** {icon} 中证转债指数周{_chg(chg)}，"
          f"周均成交 {_num(iw.get('avg_amount_yi'))} 亿")
    print(f"2. **估值水位：** 平均价格 {_num(val.get('avg_price'))} 元 / 平均转股溢价率 "
          f"{_num(val.get('avg_premium_rt'))}% / 平均双低 {_num(val.get('avg_double_low'))}")
    print(f"3. **市场规模：** 存续 {m.get('alive_count', '-')} 只、总余额 {m.get('total_remain_yi', '-')} 亿，"
          f"周内新增 {m.get('new_listed', '-')} 只 / 退市 {m.get('delisted', '-')} 只")
    print(f"4. **综合评分：** {sc['score']}/100，{sc['direction']}")

    print("\n### 特别注意：\n")
    if sc["score"] >= 58:
        print("- ✅ 转债市场偏强，可关注低溢价进攻型转债与双低策略")
        print("- ✅ 若溢价率持续回落，股性修复行情有望延续")
    elif sc["score"] <= 42:
        print("- ⚠️ 转债市场偏弱，控制仓位，优先低价高YTM防御型转债")
        print("- ⚠️ 关注强赎/到期事件密集区的流动性冲击")
    else:
        print("- ➖ 市场中性震荡，双低策略与条款博弈为主")
    if result.get("events"):
        print("- ⚠️ 本周存在强赎/到期公告，注意持仓转债的条款风险")


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
可转债周度全景分析工具 · Tushare Pro

覆盖全市场存续可转债，按 ISO 自然周聚合：
市场温度 / 市场规模与结构 / 估值全景（均价·溢价率·双低）/ 资金与情绪 / 综合研判。

用法:
  python3 analyze_weekly_cb.py
  python3 analyze_weekly_cb.py --weeks 2
  python3 analyze_weekly_cb.py --json
        """,
    )
    parser.add_argument('--weeks', '-w', type=int, default=1,
                        help='回溯周数（默认 1 = 最近一周）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出原始结果')

    args = parser.parse_args()

    if not args.json:
        print(f"正在采集可转债周度数据（回溯 {args.weeks} 周窗口）...")
    result = fetch_weekly_data(weeks=args.weeks)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=_default_serializer))
        return

    week = result["week_labels"][-1] if result["week_labels"] else None
    if week is None:
        print("未聚合到任何自然周数据。")
        if result.get("error"):
            print(f"数据异常：{result['error']}")
        return

    print_market_overview(result, week)
    print_market_structure(result, week)
    print_valuation(result, week)
    print_funds(result, week)
    print_composite_analysis(result, week)
    print_xiaos_summary(result, week)

    print("\n---")
    print("⚠️ 以上分析基于 Tushare Pro 数据与逻辑推演，不构成投资建议。")


if __name__ == '__main__':
    main()
