"""
小盘成长股挖掘引擎

对齐 references/small-cap-screening-criteria.md：
  - 市值硬门槛：20-200 亿（中小盘 100-200 / 小盘 50-100 / 微盘 20-50），<20 亿排除；
  - 成长硬门槛：营收 3 年 CAGR > 20%（或近 2 年 > 25%）；
  - 成长质量评分（0-100）：营收增速 / 利润率趋势 / 现金流质量 / 资产负债表 /
    实控人持股 / 行业壁垒 / 研发能力 / 估值吸引力 八项加权；
  - 星级评级：80+ ★★★★★ / 65+ ★★★★ / 50+ ★★★ / 35+ ★★ / <35 ★。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 市值分段（亿元）
MARKET_CAP_BANDS = [
    (100.0, 200.0, "中小盘"),
    (50.0, 100.0, "小盘"),
    (20.0, 50.0, "微盘"),
]

# 成长质量评分权重（合计 100）
QUALITY_WEIGHTS = {
    "revenue_growth": 20,   # 营收增速
    "margin_trend": 15,     # 利润率趋势
    "cashflow_quality": 15, # 现金流质量（收现比）
    "balance_sheet": 10,    # 资产负债表
    "holder_ownership": 10, # 实控人持股
    "moat": 10,             # 行业壁垒
    "rnd": 10,              # 研发能力
    "valuation": 10,        # 估值吸引力（PEG）
}

STAR_BANDS = [
    (80, "★★★★★ 极具吸引力"),
    (65, "★★★★ 非常有潜力"),
    (50, "★★★ 值得关注"),
    (35, "★★ 有瑕疵"),
    (0, "★ 不推荐"),
]


def market_cap_band(total_mv_yi: float) -> Optional[str]:
    """市值（亿元）→ 分段；<20 亿或 >200 亿返回 None（排除）。"""
    for lo, hi, name in MARKET_CAP_BANDS:
        if lo <= total_mv_yi <= hi:
            return name
    return None


def pass_growth_gate(revenue_cagr3: float, revenue_cagr2: Optional[float] = None) -> bool:
    """成长硬门槛：3 年 CAGR > 20%，或（上市短）近 2 年 > 25%。"""
    if revenue_cagr3 is not None and revenue_cagr3 > 20.0:
        return True
    if revenue_cagr2 is not None and revenue_cagr2 > 25.0:
        return True
    return False


def _score_component(value: Optional[float], thresholds: List[tuple]) -> int:
    """阈值打分：[(阈值, 得分), ...] 从高到低，value >= 阈值取对应分。"""
    if value is None or np.isnan(value):
        return 0
    for th, score in thresholds:
        if value >= th:
            return score
    return 0


def quality_score(row: Dict[str, float]) -> Dict[str, object]:
    """单只股票的成长质量评分（0-100）+ 明细。字段缺失按 0 计（数据不足自动降权）。"""
    parts: Dict[str, int] = {}

    # 营收增速（%）：>40=20, 30-40=16, 20-30=12, <20=0
    parts["revenue_growth"] = _score_component(row.get("revenue_growth_pct"), [(40, 20), (30, 16), (20, 12), (-np.inf, 0)])
    # 利润率趋势：持续扩大=15, 稳定=10, 轻微收缩=5, 持续收缩=0（用 margin_delta 近似）
    md = row.get("margin_delta")
    if md is None or np.isnan(md):
        parts["margin_trend"] = 0
    elif md > 1.0:
        parts["margin_trend"] = 15
    elif md >= 0:
        parts["margin_trend"] = 10
    elif md >= -2.0:
        parts["margin_trend"] = 5
    else:
        parts["margin_trend"] = 0
    # 现金流质量（收现比%）：>100=15, 80-100=10, 60-80=5, <60=0
    parts["cashflow_quality"] = _score_component(row.get("cash_ratio_pct"), [(100, 15), (80, 10), (60, 5), (-np.inf, 0)])
    # 资产负债表（0-10 分输入或按资产负债率推断）
    bs = row.get("balance_sheet_score")
    if bs is None or np.isnan(bs):
        debt_ratio = row.get("debt_ratio")
        if debt_ratio is None or np.isnan(debt_ratio):
            parts["balance_sheet"] = 0
        elif debt_ratio < 50:
            parts["balance_sheet"] = 10
        elif debt_ratio < 60:
            parts["balance_sheet"] = 7
        elif debt_ratio < 70:
            parts["balance_sheet"] = 4
        else:
            parts["balance_sheet"] = 0
    else:
        parts["balance_sheet"] = int(min(10, max(0, bs)))
    # 实控人持股（%）：>40=10, 25-40=7, 15-25=4, <15=2
    parts["holder_ownership"] = _score_component(row.get("holder_pct"), [(40, 10), (25, 7), (15, 4), (-np.inf, 2)])
    # 行业壁垒（0-10 输入，默认中=6）
    moat = row.get("moat_score")
    parts["moat"] = 6 if moat is None or np.isnan(moat) else int(min(10, max(0, moat)))
    # 研发能力（0-10 输入，默认中=6）
    rnd = row.get("rnd_score")
    parts["rnd"] = 6 if rnd is None or np.isnan(rnd) else int(min(10, max(0, rnd)))
    # 估值吸引力（PEG）：<0.8=10, 0.8-1.2=7, 1.2-1.5=4, >1.5=2
    parts["valuation"] = _score_component(row.get("peg"), [(0.8, 10), (1.2, 7), (1.5, 4), (np.inf, 2)])

    total = sum(parts.get(k, 0) for k in QUALITY_WEIGHTS)
    rating = "★ 不推荐"
    for lo, label in STAR_BANDS:
        if total >= lo:
            rating = label
            break
    return {"total": total, "parts": parts, "rating": rating}


def screen(data: pd.DataFrame) -> pd.DataFrame:
    """小盘成长全市场筛选。

    Parameters
    ----------
    data : DataFrame，index=股票代码，需包含列：
        total_mv_yi（市值亿元）、revenue_cagr3_pct（营收3年CAGR%）、
        revenue_cagr2_pct（近2年营收增速%，可选）、以及 quality_score 所需字段（可选）。

    Returns
    -------
    通过硬门槛的标的：市值分段 / 成长评分 / 评级 / 明细，按评分降序。
    """
    if data is None or data.empty:
        return pd.DataFrame()
    rows = []
    for code, row in data.iterrows():
        mv = float(row.get("total_mv_yi", np.nan))
        if np.isnan(mv):
            continue
        band = market_cap_band(mv)
        if band is None:
            continue
        cagr3 = float(row.get("revenue_cagr3_pct", np.nan))
        cagr2 = row.get("revenue_cagr2_pct")
        cagr2 = float(cagr2) if pd.notna(cagr2) else None
        if not pass_growth_gate(cagr3, cagr2):
            continue
        q = quality_score(row.to_dict())
        rows.append({
            "code": code,
            "name": row.get("name", code),
            "total_mv_yi": round(mv, 1),
            "band": band,
            "revenue_cagr3_pct": round(cagr3, 1) if not np.isnan(cagr3) else None,
            "quality_score": q["total"],
            "rating": q["rating"],
            "score_parts": q["parts"],
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("quality_score", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    demo = pd.DataFrame([
        {"total_mv_yi": 80.0, "revenue_cagr3_pct": 30.0, "revenue_cagr2_pct": 28.0,
         "revenue_growth_pct": 35.0, "margin_delta": 1.5, "cash_ratio_pct": 90.0,
         "debt_ratio": 45.0, "holder_pct": 30.0, "moat_score": 8, "rnd_score": 7, "peg": 0.9},
        {"total_mv_yi": 15.0, "revenue_cagr3_pct": 35.0, "revenue_cagr2_pct": 30.0,
         "revenue_growth_pct": 40.0, "margin_delta": 2.0, "cash_ratio_pct": 110.0,
         "debt_ratio": 40.0, "holder_pct": 45.0, "moat_score": 9, "rnd_score": 8, "peg": 0.7},
        {"total_mv_yi": 120.0, "revenue_cagr3_pct": 8.0, "revenue_cagr2_pct": 10.0,
         "revenue_growth_pct": 10.0, "margin_delta": -1.0, "cash_ratio_pct": 70.0,
         "debt_ratio": 55.0, "holder_pct": 20.0, "moat_score": 5, "rnd_score": 5, "peg": 1.5},
        {"total_mv_yi": 300.0, "revenue_cagr3_pct": 25.0, "revenue_cagr2_pct": 22.0,
         "revenue_growth_pct": 25.0, "margin_delta": 0.5, "cash_ratio_pct": 85.0,
         "debt_ratio": 50.0, "holder_pct": 25.0, "moat_score": 6, "rnd_score": 6, "peg": 1.1},
    ], index=["GROW01", "MICRO01", "SLOW01", "BIG01"])
    result = screen(demo)
    print(result[["code", "total_mv_yi", "band", "revenue_cagr3_pct", "quality_score", "rating"]].to_string(index=False))
