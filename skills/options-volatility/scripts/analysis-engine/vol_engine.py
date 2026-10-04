"""
波动率分析综合引擎

提供：
- IV vs RV 对比分析
- 波动率曲面摘要
- 波动率环境判断（IV Rank / Percentile）
- 波动率策略推荐
"""

import numpy as np
from typing import Optional

from realized_vol import multi_window_vol


def iv_rv_comparison(
    iv: float,
    rv_20d: Optional[float] = None,
    rv_60d: Optional[float] = None,
    rv_90d: Optional[float] = None,
    rv_252d: Optional[float] = None,
    threshold: float = 0.03,
) -> dict:
    """IV vs RV 对比分析。

    Args:
        iv: 当前隐含波动率
        rv_*: 各窗口实现波动率
        threshold: Rich/Cheap 判断阈值

    Returns:
        对比分析结果
    """
    comparisons = []
    windows = {"20d": rv_20d, "60d": rv_60d, "90d": rv_90d, "252d": rv_252d}

    for tenor, rv in windows.items():
        if rv is None:
            continue
        spread = iv - rv
        premium = (spread / rv) * 100 if rv > 0 else 0

        if spread > threshold:
            signal = "Rich（期权偏贵）"
        elif spread < -threshold:
            signal = "Cheap（期权偏便宜）"
        else:
            signal = "Fair（合理定价）"

        comparisons.append({
            "window": tenor,
            "rv": round(rv, 6),
            "rv_pct": f"{rv * 100:.2f}%",
            "iv": round(iv, 6),
            "iv_pct": f"{iv * 100:.2f}%",
            "spread": round(spread, 6),
            "premium_pct": round(premium, 2),
            "signal": signal,
        })

    return {
        "iv": round(iv, 6),
        "iv_pct": f"{iv * 100:.2f}%",
        "comparisons": comparisons,
        "overall_signal": _overall_signal(comparisons),
    }


def _overall_signal(comparisons: list) -> str:
    """综合信号判断"""
    if not comparisons:
        return "N/A"
    signals = [c["signal"] for c in comparisons]
    rich_count = sum(1 for s in signals if "Rich" in s)
    cheap_count = sum(1 for s in signals if "Cheap" in s)

    if rich_count > cheap_count:
        return "整体偏贵（卖方策略更优）"
    elif cheap_count > rich_count:
        return "整体偏便宜（买方策略更优）"
    else:
        return "整体合理（价差策略为主）"


def vol_surface_summary(
    atm_vols: dict,
    rr_vols: Optional[dict] = None,
    bf_vols: Optional[dict] = None,
) -> dict:
    """波动率曲面摘要。

    Args:
        atm_vols: {tenor: atm_vol} 如 {"1M": 0.22, "3M": 0.24}
        rr_vols: {tenor: 25d_risk_reversal}
        bf_vols: {tenor: 25d_butterfly}

    Returns:
        曲面摘要
    """
    surface = []
    for tenor in atm_vols:
        entry = {
            "tenor": tenor,
            "atm_vol": round(atm_vols[tenor], 6),
            "atm_vol_pct": f"{atm_vols[tenor] * 100:.2f}%",
        }
        if rr_vols and tenor in rr_vols:
            entry["rr_25d"] = round(rr_vols[tenor], 6)
            entry["skew"] = "看涨偏斜" if rr_vols[tenor] > 0 else "看跌偏斜"
        if bf_vols and tenor in bf_vols:
            entry["bf_25d"] = round(bf_vols[tenor], 6)
        surface.append(entry)

    # 期限结构判断
    atm_values = list(atm_vols.values())
    if len(atm_values) >= 2:
        slope = atm_values[-1] - atm_values[0]
        ts_shape = "Contango（远高近低）" if slope > 0 else "Backwardation（远低近高）"
    else:
        ts_shape = "N/A"

    return {
        "surface": surface,
        "term_structure": ts_shape,
        "atm_range": {
            "min": round(min(atm_values), 6),
            "max": round(max(atm_values), 6),
        },
    }


def vol_regime(
    iv_current: float,
    iv_52w_low: Optional[float] = None,
    iv_52w_high: Optional[float] = None,
    iv_history: Optional[list] = None,
) -> dict:
    """波动率环境判断。

    Args:
        iv_current: 当前 IV
        iv_52w_low: 52周 IV 最低
        iv_52w_high: 52周 IV 最高
        iv_history: 历史IV序列（用于计算 Percentile）

    Returns:
        波动率环境分析
    """
    result = {"iv_current": round(iv_current, 6), "iv_current_pct": f"{iv_current * 100:.2f}%"}

    # IV Rank
    if iv_52w_low is not None and iv_52w_high is not None and iv_52w_high > iv_52w_low:
        iv_rank = (iv_current - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
        result["iv_rank"] = round(iv_rank, 2)
        result["iv_52w_range"] = {
            "low": round(iv_52w_low, 6),
            "high": round(iv_52w_high, 6),
        }
    else:
        iv_rank = None
        result["iv_rank"] = "N/A"

    # IV Percentile
    if iv_history and len(iv_history) > 10:
        iv_arr = np.array(iv_history)
        percentile = np.sum(iv_arr < iv_current) / len(iv_arr) * 100
        result["iv_percentile"] = round(float(percentile), 2)
    else:
        result["iv_percentile"] = "N/A"

    # 分类
    if iv_rank is not None:
        if iv_rank < 20:
            regime = "低波动率"
            strategy = "买方策略优先（Long Straddle/Strangle/Back Spread）"
        elif iv_rank < 80:
            regime = "正常波动率"
            strategy = "价差策略优先（Vertical Spreads/Calendar/Diagonal）"
        else:
            regime = "高波动率"
            strategy = "卖方策略优先（Short Straddle/Iron Condor/Covered Call）"
    else:
        regime = "N/A"
        strategy = "N/A"

    result["regime"] = regime
    result["recommended_strategy"] = strategy

    return result


def full_analysis(
    prices: np.ndarray,
    iv: float,
    iv_52w_low: Optional[float] = None,
    iv_52w_high: Optional[float] = None,
    iv_history: Optional[list] = None,
) -> dict:
    """完整波动率分析。

    Args:
        prices: 历史收盘价序列
        iv: 当前隐含波动率
        其余参数同上

    Returns:
        完整分析结果
    """
    # 1. 实现波动率
    rv_result = multi_window_vol(prices)

    # 2. IV vs RV
    rv_map = {}
    for label, data in rv_result.items():
        if data["vol"] is not None:
            rv_map[label] = data["vol"]

    iv_rv = iv_rv_comparison(
        iv=iv,
        rv_20d=rv_map.get("20d"),
        rv_60d=rv_map.get("60d"),
        rv_90d=rv_map.get("90d"),
        rv_252d=rv_map.get("252d"),
    )

    # 3. 波动率环境
    regime = vol_regime(iv, iv_52w_low, iv_52w_high, iv_history)

    return {
        "realized_volatility": rv_result,
        "iv_rv_comparison": iv_rv,
        "vol_regime": regime,
    }
