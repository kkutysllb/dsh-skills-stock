"""
实现波动率计算引擎

支持多种计算方法：
- Close-to-Close（收盘价对收盘价）
- Parkinson（日内高低价）
- Garman-Klass（OHLC）
- Rogers-Satchell（OHLC，对价格漂移不敏感）
- Rolling Close-to-Close（滚动窗口序列）

约定：
- 所有估计器统一使用样本方差（ddof=1），保证横向可比。
- 价格序列须为正；含非正数、NaN、Inf 的输入返回 NaN，不静默传播。
- 年化因子默认 252（交易日）；加密/7×24 市场请传 365。
"""

import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# 输入校验工具
# ---------------------------------------------------------------------------
def _validate_positive_prices(*arrays: np.ndarray) -> bool:
    """校验所有输入数组非空、元素全正、不含 NaN/Inf。

    Returns:
        True 表示数据可用；False 表示存在非法值（调用方应返回 np.nan）。
    """
    for arr in arrays:
        a = np.asarray(arr, dtype=float)
        if a.size == 0:
            return False
        if not np.all(np.isfinite(a)):
            return False
        if np.any(a <= 0):
            return False
    return True


def _validate_window(arr: np.ndarray, window: int, min_window: int = 2) -> bool:
    """校验窗口合法性（ddof=1 要求 window >= 2）。"""
    if window is None or window < min_window:
        return False
    if len(arr) < window:
        return False
    return True


# ---------------------------------------------------------------------------
# 单一窗口估计器
# ---------------------------------------------------------------------------
def close_to_close_vol(
    prices: np.ndarray,
    window: int = 20,
    annualize: int = 252,
) -> float:
    """Close-to-Close 实现波动率（无偏样本方差 ddof=1）。

    Args:
        prices: 收盘价序列（必须全正）
        window: 回溯窗口（天）
        annualize: 年化因子

    Returns:
        年化波动率；数据不足或非法时返回 np.nan
    """
    prices = np.asarray(prices, dtype=float)
    if not _validate_positive_prices(prices):
        return np.nan
    if len(prices) < window + 1 or window < 2:
        return np.nan

    log_returns = np.log(prices[1:] / prices[:-1])
    recent = log_returns[-window:]
    return float(np.std(recent, ddof=1) * np.sqrt(annualize))


def parkinson_vol(
    highs: np.ndarray,
    lows: np.ndarray,
    window: int = 20,
    annualize: int = 252,
) -> float:
    """Parkinson 波动率（日内高低价，无偏样本方差 ddof=1）。

    公式：σ² = (1/(4·ln2)) · Σ ln(H/L)² / (n−1)
    要求 highs >= lows，否则返回 NaN。

    Args:
        highs: 日内最高价序列
        lows: 日内最低价序列
        window: 回溯窗口
        annualize: 年化因子

    Returns:
        年化波动率
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    if not _validate_positive_prices(highs, lows):
        return np.nan
    if len(highs) != len(lows):
        return np.nan
    if not _validate_window(highs, window):
        return np.nan
    if np.any(highs[-window:] < lows[-window:]):
        return np.nan

    hl_ratio = np.log(highs[-window:] / lows[-window:])
    factor = 1.0 / (4.0 * np.log(2))
    # 统一 ddof=1，与 close_to_close 可比
    var = factor * np.sum(hl_ratio ** 2) / (window - 1)
    var = max(var, 0.0)  # 浮点保护
    return float(np.sqrt(var * annualize))


def garman_klass_vol(
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
    closes: np.ndarray,
    window: int = 20,
    annualize: int = 252,
) -> float:
    """Garman-Klass 波动率（OHLC，无偏样本方差 ddof=1）。

    公式：σ² = Σ [0.5·ln(H/L)² − (2·ln2−1)·ln(C/O)²] / (n−1)

    Args:
        highs, lows, opens, closes: OHLC 数据序列（等长，全正）
        window: 回溯窗口
        annualize: 年化因子

    Returns:
        年化波动率
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    opens = np.asarray(opens, dtype=float)
    closes = np.asarray(closes, dtype=float)

    if not _validate_positive_prices(highs, lows, opens, closes):
        return np.nan
    n = min(len(highs), len(lows), len(opens), len(closes))
    if n < window or not _validate_window(np.empty(window + 1), window):
        return np.nan

    h = highs[-window:]
    l = lows[-window:]
    o = opens[-window:]
    c = closes[-window:]

    if np.any(h < l):
        return np.nan

    hl = np.log(h / l)
    co = np.log(c / o)

    gk = 0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2
    var = np.sum(gk) / (window - 1)  # ddof=1
    var = max(var, 0.0)  # 浮点保护，防止负方差
    return float(np.sqrt(var * annualize))


def rogers_satchell_vol(
    highs: np.ndarray,
    lows: np.ndarray,
    opens: np.ndarray,
    closes: np.ndarray,
    window: int = 20,
    annualize: int = 252,
) -> float:
    """Rogers-Satchell 波动率（OHLC，对价格漂移不敏感，ddof=1）。

    标准 Rogers-Satchell (1991) 每周期表达式：
        rs_t = u·(u−c) + d·(d−c)
    其中 u=ln(H/O), d=ln(L/O), c=ln(C/O)。该式对每个 t 恒非负，
    且在含趋势/漂移的序列上无偏，优于 Garman-Klass 在强趋势行情的表现。

    σ² = Σ rs_t / (n−1)

    Args:
        highs, lows, opens, closes: OHLC 数据序列（等长，全正）
        window: 回溯窗口
        annualize: 年化因子

    Returns:
        年化波动率
    """
    highs = np.asarray(highs, dtype=float)
    lows = np.asarray(lows, dtype=float)
    opens = np.asarray(opens, dtype=float)
    closes = np.asarray(closes, dtype=float)

    if not _validate_positive_prices(highs, lows, opens, closes):
        return np.nan
    n = min(len(highs), len(lows), len(opens), len(closes))
    if n < window or not _validate_window(np.empty(window + 1), window):
        return np.nan

    h = highs[-window:]
    l = lows[-window:]
    o = opens[-window:]
    c = closes[-window:]

    if np.any(h < l):
        return np.nan

    # 相对于开盘的对数收益
    u = np.log(h / o)  # high vs open
    d = np.log(l / o)  # low vs open
    cc = np.log(c / o)  # close vs open

    # Rogers-Satchell 恒正表达式：u·(u−cc) + d·(d−cc)
    rs = u * (u - cc) + d * (d - cc)
    var = np.sum(rs) / (window - 1)  # ddof=1
    var = max(var, 0.0)  # 浮点保护
    return float(np.sqrt(var * annualize))


# ---------------------------------------------------------------------------
# 滚动窗口序列版本
# ---------------------------------------------------------------------------
def rolling_close_to_close_vol(
    prices: np.ndarray,
    window: int = 20,
    annualize: int = 252,
) -> np.ndarray:
    """滚动 Close-to-Close 实现波动率序列（向量化）。

    返回长度等于 len(prices) 的数组，前 window 个位置（含构造首收益所需）
    置为 NaN。第 i 个元素对应以 prices[i] 结尾的 window 天波动率。

    Args:
        prices: 收盘价序列
        window: 滚动窗口（天）
        annualize: 年化因子

    Returns:
        年化波动率序列（float 数组），前 window 个为 NaN
    """
    prices = np.asarray(prices, dtype=float)
    out = np.full(len(prices), np.nan, dtype=float)
    if not _validate_positive_prices(prices):
        return out
    if len(prices) < window + 1 or window < 2:
        return out

    log_returns = np.log(prices[1:] / prices[:-1])
    # 滑动窗口方差（ddof=1）使用累积量法，O(n)
    n = len(log_returns)
    k = window
    if n < k:
        return out

    # 使用 sliding sum / sumsq 推导样本方差
    csum = np.concatenate([[0.0], np.cumsum(log_returns)])
    csq = np.concatenate([[0.0], np.cumsum(log_returns ** 2)])

    win_sum = csum[k:] - csum[:-k]      # 长度 n-k+1
    win_sq = csq[k:] - csq[:-k]
    var = (win_sq - win_sum ** 2 / k) / (k - 1)  # ddof=1
    var = np.maximum(var, 0.0)

    # 第 i 个窗口覆盖 log_returns[i : i+k]，对应 prices 索引 i+k
    out[k:] = np.sqrt(var * annualize)
    return out


# ---------------------------------------------------------------------------
# 多窗口聚合视图
# ---------------------------------------------------------------------------
def multi_window_vol(
    prices: np.ndarray,
    windows: Optional[list] = None,
    annualize: int = 252,
) -> dict:
    """多窗口实现波动率。

    Args:
        prices: 收盘价序列
        windows: 窗口列表，默认 [20, 60, 90, 252]
        annualize: 年化因子

    Returns:
        各窗口的年化波动率，vol 字段保留原始 float（不四舍五入）
    """
    if windows is None:
        windows = [20, 60, 90, 252]

    result = {}
    for w in windows:
        vol = close_to_close_vol(prices, w, annualize)
        label = f"{w}d"
        result[label] = {
            "window": w,
            "vol": float(vol) if not np.isnan(vol) else None,  # 保留原始精度
            "vol_pct": f"{vol * 100:.2f}%" if not np.isnan(vol) else "N/A",
            "annualize_factor": annualize,
        }
    return result
