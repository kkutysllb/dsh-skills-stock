"""
因子择时与拥挤度评估

对齐 references/factor-methodology.md：
  - 经济周期因子图谱：复苏初期 / 扩张中期 / 扩张末期 / 下行衰退 / 触底回升
    各阶段对应利好/不利因子与建议权重（单因子偏离等权不超过 ±10%）；
  - 拥挤度评估：基于因子收益序列的 IC 自相关 / 动量衰减检测，
    以及估值价差收窄提示（可选输入）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

FACTORS = ["value", "momentum", "quality", "low_vol", "size", "growth"]

FACTOR_CN = {
    "value": "价值",
    "momentum": "动量",
    "quality": "质量",
    "low_vol": "低波动",
    "size": "规模",
    "growth": "成长",
}

# 经济周期 → 因子建议权重（references/factor-methodology.md 表）
CYCLE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "recovery_early":   {"value": 0.15, "momentum": 0.20, "quality": 0.10, "low_vol": 0.05, "size": 0.25, "growth": 0.25},
    "expansion_mid":    {"value": 0.10, "momentum": 0.25, "quality": 0.20, "low_vol": 0.05, "size": 0.15, "growth": 0.25},
    "expansion_late":   {"value": 0.25, "momentum": 0.10, "quality": 0.25, "low_vol": 0.20, "size": 0.10, "growth": 0.10},
    "downturn":         {"value": 0.15, "momentum": 0.05, "quality": 0.25, "low_vol": 0.30, "size": 0.05, "growth": 0.20},
    "trough_rebound":   {"value": 0.30, "momentum": 0.15, "quality": 0.10, "low_vol": 0.05, "size": 0.25, "growth": 0.15},
}

CYCLE_CN = {
    "recovery_early": "复苏初期",
    "expansion_mid": "扩张中期",
    "expansion_late": "扩张末期",
    "downturn": "下行/衰退",
    "trough_rebound": "触底回升",
}

# 各阶段利好 / 不利因子
CYCLE_FAVORABLE: Dict[str, Dict[str, List[str]]] = {
    "recovery_early": {"favorable": ["size", "momentum", "growth"], "unfavorable": ["low_vol"]},
    "expansion_mid": {"favorable": ["momentum", "quality"], "unfavorable": ["value"]},
    "expansion_late": {"favorable": ["quality", "value"], "unfavorable": ["size", "growth"]},
    "downturn": {"favorable": ["low_vol", "quality"], "unfavorable": ["momentum", "size"]},
    "trough_rebound": {"favorable": ["value", "size"], "unfavorable": ["low_vol"]},
}


def timing_weights(cycle: str, cap_delta: float = 0.10) -> Dict[str, float]:
    """返回指定经济周期下的因子权重。

    Parameters
    ----------
    cycle : 经济周期阶段键（recovery_early / expansion_mid / expansion_late / downturn / trough_rebound）
    cap_delta : 单因子偏离等权的上限（默认 ±10%），超出被截断到 ±10% 后重归一。
    """
    if cycle not in CYCLE_WEIGHTS:
        raise ValueError(f"未知经济周期: {cycle}，可选 {list(CYCLE_WEIGHTS)}")
    w = dict(CYCLE_WEIGHTS[cycle])
    equal = 1.0 / len(FACTORS)
    capped = {f: min(max(v, equal - cap_delta), equal + cap_delta) for f, v in w.items()}
    total = sum(capped.values())
    return {f: round(v / total, 4) for f, v in capped.items()}


def timing_advice(cycle: str) -> Dict[str, object]:
    """返回某周期的择时建议：权重 + 利好/不利因子 + 中文说明。"""
    fav = CYCLE_FAVORABLE.get(cycle, {"favorable": [], "unfavorable": []})
    return {
        "cycle": cycle,
        "cycle_cn": CYCLE_CN.get(cycle, cycle),
        "weights": timing_weights(cycle),
        "favorable": fav["favorable"],
        "unfavorable": fav["unfavorable"],
        "favorable_cn": [FACTOR_CN[f] for f in fav["favorable"]],
        "unfavorable_cn": [FACTOR_CN[f] for f in fav["unfavorable"]],
    }


def _detect_cycle(gdp_trend: float, inflation: float, interest_trend: float) -> str:
    """基于宏观三要素的启发式周期判定（供无显式输入时的兜底）。

    Parameters
    ----------
    gdp_trend : GDP 环比趋势（>0 加速，<0 减速）
    inflation : 通胀水平（>0 上升）
    interest_trend : 利率趋势（>0 上行）
    """
    if gdp_trend > 0 and inflation <= 0 and interest_trend <= 0:
        return "recovery_early"
    if gdp_trend > 0 and inflation <= 0.5 and abs(interest_trend) < 0.3:
        return "expansion_mid"
    if gdp_trend <= 0.3 and inflation > 0.5 and interest_trend > 0:
        return "expansion_late"
    if gdp_trend < 0:
        return "downturn"
    return "trough_rebound"


def detect_cycle(gdp_trend: float, inflation: float, interest_trend: float) -> Dict[str, object]:
    """宏观三要素 → 周期判定 + 择时建议。"""
    cycle = _detect_cycle(gdp_trend, inflation, interest_trend)
    advice = timing_advice(cycle)
    advice["inputs"] = {"gdp_trend": gdp_trend, "inflation": inflation, "interest_trend": interest_trend}
    return advice


def crowding_analysis(factor_returns: pd.DataFrame, window: int = 60) -> Dict[str, object]:
    """因子拥挤度评估：基于因子收益序列的动量自相关与 IC 衰减。

    Parameters
    ----------
    factor_returns : 因子日收益面板（index=日期, columns=因子名），
        每列即某因子的多空组合日收益（或单因子 IC 序列亦可）。
    window : 自相关观察窗口（默认 60 日）。

    Returns
    -------
    {因子名: {lag1_autocorr, ic_decay (近window IC均值 - 全期IC均值), crowding 等级, 说明}}
    """
    if factor_returns is None or factor_returns.empty:
        return {"error": "无因子收益数据"}
    out = {}
    for col in factor_returns.columns:
        s = factor_returns[col].dropna()
        if len(s) < window + 2:
            out[col] = {"crowding": "数据不足", "detail": f"样本 {len(s)} < {window}+2"}
            continue
        lag1 = s.autocorr(lag=1)
        if np.isnan(lag1):
            lag1 = 0.0
        recent_mean = s.iloc[-window:].mean()
        full_mean = s.mean()
        decay = recent_mean - full_mean

        # 拥挤等级：自相关强正 + 近期收益转弱 → 高拥挤
        if lag1 > 0.3 and decay < 0:
            level, desc = "高", "近期因子收益转弱且呈正自相关，拥挤迹象明显，有急剧反转风险"
        elif lag1 > 0.3:
            level, desc = "中", "因子收益正自相关（趋势跟随），预期收益可能压缩"
        elif decay < -0.0005:
            level, desc = "中", "近期收益低于历史均值，需关注是否拥挤"
        else:
            level, desc = "低", "未观测到明显拥挤迹象"
        out[col] = {
            "lag1_autocorr": round(float(lag1), 4),
            "ic_decay_recent_vs_full": round(float(decay), 6),
            "crowding": level,
            "desc": desc,
        }
    return out


def timing_report(cycle: str, factor_returns: Optional[pd.DataFrame] = None) -> Dict[str, object]:
    """综合择时报告：周期权重 + 利好/不利因子 + 拥挤度。"""
    report = timing_advice(cycle)
    if factor_returns is not None and not factor_returns.empty:
        report["crowding"] = crowding_analysis(factor_returns)
    return report


if __name__ == "__main__":
    np.random.seed(11)
    print("=== 各周期权重 ===")
    for c in CYCLE_WEIGHTS:
        print(f"  {CYCLE_CN[c]:6s} {timing_weights(c)}")

    print("\n=== 宏观判定 → 择时 ===")
    adv = detect_cycle(gdp_trend=0.8, inflation=0.2, interest_trend=-0.1)
    print(f"  周期: {adv['cycle_cn']} | 利好: {adv['favorable_cn']} | 不利: {adv['unfavorable_cn']}")

    print("\n=== 拥挤度（mock 因子收益）===")
    dates = pd.bdate_range("2024-01-01", periods=120)
    # 动量因子近期转弱 + 正自相关 → 高拥挤
    trend = np.concatenate([np.random.normal(0.001, 0.01, 80), np.random.normal(-0.001, 0.01, 40)])
    rets = pd.DataFrame({"momentum": trend, "quality": np.random.normal(0.0008, 0.008, 120)}, index=dates)
    print(" ", crowding_analysis(rets))
