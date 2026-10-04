#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标信号 (tas = TA-lib Signals)

参考 czsc.signals.tas 的设计，实现基于技术指标的信号函数。
不依赖 ta-lib，纯 numpy/pandas 实现技术指标计算。

信号列表：
1.  tas_macd_cross     - MACD金叉/死叉信号
2.  tas_macd_bc        - MACD背驰信号
3.  tas_macd_dist      - MACD距离信号
4.  tas_ma_system      - 均线系统信号
5.  tas_ma_cohere      - 均线粘合信号
6.  tas_double_ma      - 双均线交叉信号
7.  tas_cross_status   - 交叉状态信号
8.  tas_atr            - ATR波动率信号
9.  tas_boll_status    - 布林带状态信号
10. tas_kdj_cross      - KDJ交叉信号
11. tas_rsi_status     - RSI状态信号
12. tas_cci_status     - CCI状态信号
13. tas_sar_status     - SAR状态信号
14. tas_dif_zero       - DIF零轴信号
15. tas_slope          - 斜率信号
16. tas_accelerate     - 加速信号
17. tas_low_trend      - 低位趋势信号
18. tas_angle          - 角度信号
19. tas_dma_bs         - DMA买卖信号
20. tas_rumi           - RUMI指标信号
21. tas_macd_bs1       - MACD一类买卖信号
22. tas_volume_price   - 量价信号
23. tas_bias_status    - 乖离率信号
24. tas_emv_status     - EMV状态信号
25. tas_obv_status     - OBV状态信号
26. tas_wr_status      - 威廉指标信号
27. tas_dmi_status     - DMI动向指标信号
28. tas_trix_signal    - TRIX三重指数信号
29. tas_roc_signal     - ROC变动率信号
30. tas_mtm_signal     - MTM动量信号
31. tas_psy_status     - PSY心理线信号
32. tas_vr_status      - VR容量比率信号
33. tas_wad_status     - WAD累积/分散信号
34. tas_adx_status     - ADX趋势强度信号
35. tas_tsi_signal     - TSI真实力度指标信号
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any, Tuple
from collections import OrderedDict

from .cxt import create_single_signal, get_sub_elements


# ─── 技术指标计算工具 ────────────────────────────────────────────

def _calc_ma(close: np.ndarray, period: int, ma_type: str = 'SMA') -> np.ndarray:
    """计算均线"""
    if ma_type == 'EMA':
        return pd.Series(close).ewm(span=period, adjust=False).mean().values
    elif ma_type == 'WMA':
        weights = np.arange(1, period + 1, dtype=float)
        return pd.Series(close).rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True).values
    else:  # SMA
        return pd.Series(close).rolling(period).mean().values


def _calc_macd(close: np.ndarray, fast: int = 12, slow: int = 26,
               signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算MACD"""
    ema_fast = pd.Series(close).ewm(span=fast, adjust=False).mean()
    ema_slow = pd.Series(close).ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return dif.values, dea.values, macd.values


def _calc_boll(close: np.ndarray, period: int = 20,
               nbdev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算布林带"""
    mid = pd.Series(close).rolling(period).mean()
    std = pd.Series(close).rolling(period).std()
    upper = mid + nbdev * std
    lower = mid - nbdev * std
    return upper.values, mid.values, lower.values


def _calc_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              period: int = 14) -> np.ndarray:
    """计算ATR"""
    tr = np.maximum(
        np.abs(high - low),
        np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1)))
    )
    tr[0] = high[0] - low[0]
    return pd.Series(tr).rolling(period).mean().values


def _calc_kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算KDJ"""
    low_min = pd.Series(low).rolling(n).min()
    high_max = pd.Series(high).rolling(n).max()
    rsv = (close - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k.values, d.values, j.values


def _calc_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算RSI"""
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))
    return rsi.values


def _calc_cci(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              period: int = 14) -> np.ndarray:
    """计算CCI"""
    tp = (high + low + close) / 3
    ma_tp = pd.Series(tp).rolling(period).mean()
    md = pd.Series(tp).rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - ma_tp) / (0.015 * md)
    return cci.values


def _calc_sar(high: np.ndarray, low: np.ndarray,
              af_step: float = 0.02, af_max: float = 0.2) -> np.ndarray:
    """计算SAR（简化版）"""
    n = len(high)
    sar = np.zeros(n)
    trend = np.ones(n)  # 1=上涨, -1=下跌
    af = af_step
    ep = high[0]
    sar[0] = low[0]

    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if trend[i - 1] == 1:  # 上涨趋势
            sar[i] = min(sar[i], low[i - 1], low[max(0, i - 2)])
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = af_step
            else:
                trend[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:  # 下跌趋势
            sar[i] = max(sar[i], high[i - 1], high[max(0, i - 2)])
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = af_step
            else:
                trend[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)
    return sar


# ─── 技术指标信号函数 ─────────────────────────────────────────────

def tas_macd_cross(freq: str, bars_raw: list, di: int = 1,
                   fastperiod: int = 12, slowperiod: int = 26,
                   signalperiod: int = 9, **kwargs) -> OrderedDict:
    """MACD金叉/死叉信号

    参数模板："{freq}_D{di}MACD{fast}#{slow}#{signal}_金叉死叉"

    信号逻辑：
    1. DIF上穿DEA → 金叉，看多
    2. DIF下穿DEA → 死叉，看空

    信号列表：
    - Signal('15分钟_D1MACD12#26#9_金叉死叉_金叉_任意_任意')
    - Signal('15分钟_D1MACD12#26#9_金叉死叉_死叉_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}MACD{fastperiod}#{slowperiod}#{signalperiod}_金叉死叉".split("_")
    if len(bars_raw) < slowperiod + signalperiod + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    dif, dea, macd = _calc_macd(close, fastperiod, slowperiod, signalperiod)

    idx = len(dif) - di
    if idx < 1 or np.isnan(dif[idx]) or np.isnan(dea[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if dif[idx] > dea[idx] and dif[idx - 1] <= dea[idx - 1]:
        v1 = "金叉"
    elif dif[idx] < dea[idx] and dif[idx - 1] >= dea[idx - 1]:
        v1 = "死叉"
    elif dif[idx] > dea[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_macd_bc(freq: str, bars_raw: list, bi_list: list = None,
                di: int = 1, fastperiod: int = 12,
                slowperiod: int = 26, signalperiod: int = 9,
                **kwargs) -> OrderedDict:
    """MACD背驰信号

    参数模板："{freq}_D{di}MACD{fast}#{slow}#{signal}_背驰"

    信号逻辑：
    1. 价格创新高但MACD不创新高 → 顶背驰
    2. 价格创新低但MACD不创新低 → 底背驰

    信号列表：
    - Signal('15分钟_D1MACD12#26#9_背驰_顶背驰_任意_任意')
    - Signal('15分钟_D1MACD12#26#9_背驰_底背驰_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}MACD{fastperiod}#{slowperiod}#{signalperiod}_背驰".split("_")
    if len(bars_raw) < slowperiod + signalperiod + 20:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    dif, dea, macd = _calc_macd(close, fastperiod, slowperiod, signalperiod)

    n = len(close)
    # 取最近两段上涨/下跌比较
    window = min(30, n - 1)
    recent_close = close[-window:]
    recent_macd = np.abs(macd[-window:])

    # 检测局部高低点
    try:
        from scipy.signal import argrelextrema
    except Exception:
        argrelextrema = None
    try:
        price_max_idx = argrelextrema(recent_close, np.greater, order=5)[0]
        price_min_idx = argrelextrema(recent_close, np.less, order=5)[0]
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    v1 = "无背驰"
    if len(price_max_idx) >= 2:
        i1, i2 = price_max_idx[-2], price_max_idx[-1]
        if recent_close[i2] > recent_close[i1] and recent_macd[i2] < recent_macd[i1]:
            v1 = "顶背驰"
    elif len(price_min_idx) >= 2:
        i1, i2 = price_min_idx[-2], price_min_idx[-1]
        if recent_close[i2] < recent_close[i1] and recent_macd[i2] < recent_macd[i1]:
            v1 = "底背驰"

    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_macd_dist(freq: str, bars_raw: list, di: int = 1,
                  fastperiod: int = 12, slowperiod: int = 26,
                  signalperiod: int = 9, **kwargs) -> OrderedDict:
    """MACD距离零轴信号

    参数模板："{freq}_D{di}MACD{fast}#{slow}#{signal}_距离零轴"

    信号逻辑：
    根据DIF与零轴的距离判断多空

    信号列表：
    - Signal('15分钟_D1MACD12#26#9_距离零轴_远高于零轴_任意_任意')
    - Signal('15分钟_D1MACD12#26#9_距离零轴_远低于零轴_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}MACD{fastperiod}#{slowperiod}#{signalperiod}_距离零轴".split("_")
    if len(bars_raw) < slowperiod + signalperiod + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    dif, dea, macd = _calc_macd(close, fastperiod, slowperiod, signalperiod)

    idx = len(dif) - di
    if np.isnan(dif[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    dif_std = np.nanstd(dif)
    if dif_std == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = dif[idx] / dif_std
    if ratio > 2:
        v1 = "远高于零轴"
    elif ratio > 0:
        v1 = "高于零轴"
    elif ratio > -2:
        v1 = "低于零轴"
    else:
        v1 = "远低于零轴"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_ma_system(freq: str, bars_raw: list, di: int = 1,
                  ma_periods: tuple = (5, 10, 20, 60),
                  **kwargs) -> OrderedDict:
    """均线系统信号

    参数模板："{freq}_D{di}均线系统_MA_SYS"

    信号逻辑：
    1. 短期均线 > 长期均线 → 多头排列
    2. 短期均线 < 长期均线 → 空头排列

    信号列表：
    - Signal('15分钟_D1均线系统_MA_SYS_多头排列_任意_任意')
    - Signal('15分钟_D1均线系统_MA_SYS_空头排列_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param ma_periods: 均线周期列表
    """
    k1, k2, k3 = f"{freq}_D{di}均线系统_MA_SYS".split("_")
    if len(bars_raw) < max(ma_periods) + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    mas = [_calc_ma(close, p) for p in ma_periods]

    idx = len(close) - di
    ma_vals = [m[idx] for m in mas if idx < len(m) and not np.isnan(m[idx])]
    if len(ma_vals) < len(ma_periods):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 检查排列
    is_bull = all(ma_vals[i] > ma_vals[i + 1] for i in range(len(ma_vals) - 1))
    is_bear = all(ma_vals[i] < ma_vals[i + 1] for i in range(len(ma_vals) - 1))

    if is_bull:
        v1 = "多头排列"
    elif is_bear:
        v1 = "空头排列"
    else:
        v1 = "交叉排列"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_ma_cohere(freq: str, bars_raw: list, di: int = 1,
                  ma_periods: tuple = (5, 10, 20, 60),
                  threshold: float = 0.02, **kwargs) -> OrderedDict:
    """均线粘合信号

    参数模板："{freq}_D{di}均线粘合_MA_CH"

    信号逻辑：
    多条均线接近时产生粘合，变盘信号

    信号列表：
    - Signal('15分钟_D1均线粘合_MA_CH_粘合_任意_任意')
    - Signal('15分钟_D1均线粘合_MA_CH_分散_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param threshold: 粘合阈值
    """
    k1, k2, k3 = f"{freq}_D{di}均线粘合_MA_CH".split("_")
    if len(bars_raw) < max(ma_periods) + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    mas = [_calc_ma(close, p) for p in ma_periods]

    idx = len(close) - di
    ma_vals = [m[idx] for m in mas if idx < len(m) and not np.isnan(m[idx])]
    if len(ma_vals) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ma_range = (max(ma_vals) - min(ma_vals)) / np.mean(ma_vals) if np.mean(ma_vals) > 0 else 1
    v1 = "粘合" if ma_range < threshold else "分散"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_double_ma(freq: str, bars_raw: list, di: int = 1,
                  fast: int = 5, slow: int = 20,
                  ma_type: str = 'EMA', **kwargs) -> OrderedDict:
    """双均线交叉信号

    参数模板："{freq}_D{di}双均线F{fast}S{slow}_交叉"

    信号逻辑：
    1. 快线上穿慢线 → 金叉
    2. 快线下穿慢线 → 死叉

    信号列表：
    - Signal('15分钟_D1双均线F5S20_交叉_金叉_任意_任意')
    - Signal('15分钟_D1双均线F5S20_交叉_死叉_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}双均线F{fast}S{slow}_交叉".split("_")
    if len(bars_raw) < slow + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma_fast = _calc_ma(close, fast, ma_type)
    ma_slow = _calc_ma(close, slow, ma_type)

    idx = len(close) - di
    if idx < 1 or np.isnan(ma_fast[idx]) or np.isnan(ma_slow[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if ma_fast[idx] > ma_slow[idx] and ma_fast[idx - 1] <= ma_slow[idx - 1]:
        v1 = "金叉"
    elif ma_fast[idx] < ma_slow[idx] and ma_fast[idx - 1] >= ma_slow[idx - 1]:
        v1 = "死叉"
    elif ma_fast[idx] > ma_slow[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_cross_status(freq: str, bars_raw: list, di: int = 1,
                     fast: int = 5, slow: int = 20,
                     **kwargs) -> OrderedDict:
    """交叉状态信号

    参数模板："{freq}_D{di}均线F{fast}S{slow}_交叉状态"

    信号逻辑：
    判断快慢均线的相对位置和距离

    信号列表：
    - Signal('15分钟_D1均线F5S20_交叉状态_多头贴近_任意_任意')
    - Signal('15分钟_D1均线F5S20_交叉状态_空头远离_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}均线F{fast}S{slow}_交叉状态".split("_")
    if len(bars_raw) < slow + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma_fast = _calc_ma(close, fast)
    ma_slow = _calc_ma(close, slow)

    idx = len(close) - di
    if np.isnan(ma_fast[idx]) or np.isnan(ma_slow[idx]) or ma_slow[idx] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    diff_pct = (ma_fast[idx] - ma_slow[idx]) / ma_slow[idx] * 100

    if diff_pct > 3:
        v1 = "多头远离"
    elif diff_pct > 0:
        v1 = "多头贴近"
    elif diff_pct > -3:
        v1 = "空头贴近"
    else:
        v1 = "空头远离"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_atr(freq: str, bars_raw: list, di: int = 1,
            period: int = 14, **kwargs) -> OrderedDict:
    """ATR波动率信号

    参数模板："{freq}_D{di}ATR{period}_波动率"

    信号逻辑：
    根据ATR值判断波动率水平

    信号列表：
    - Signal('15分钟_D1ATR14_波动率_高波动_任意_任意')
    - Signal('15分钟_D1ATR14_波动率_低波动_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: ATR周期
    """
    k1, k2, k3 = f"{freq}_D{di}ATR{period}_波动率".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    atr = _calc_atr(high, low, close, period)
    idx = len(close) - di

    if np.isnan(atr[idx]) or close[idx] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    atr_pct = atr[idx] / close[idx] * 100
    if atr_pct > 3:
        v1 = "高波动"
    elif atr_pct > 1.5:
        v1 = "中波动"
    else:
        v1 = "低波动"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_boll_status(freq: str, bars_raw: list, di: int = 1,
                    period: int = 20, nbdev: float = 2.0,
                    **kwargs) -> OrderedDict:
    """布林带状态信号

    参数模板："{freq}_D{di}BOLL{period}S{nbdev}_状态"

    信号逻辑：
    1. 价格在布林带上轨之上 → 超买
    2. 价格在布林带下轨之下 → 超卖
    3. 布林带收窄 → 变盘信号

    信号列表：
    - Signal('15分钟_D1BOLL20S2_状态_上轨上方_任意_任意')
    - Signal('15分钟_D1BOLL20S2_状态_下轨下方_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    nbdev_int = int(nbdev * 10)
    k1, k2, k3 = f"{freq}_D{di}BOLL{period}S{nbdev_int}_状态".split("_")
    if len(bars_raw) < period + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    upper, mid, lower = _calc_boll(close, period, nbdev)

    idx = len(close) - di
    if np.isnan(upper[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    price = close[idx]
    if price > upper[idx]:
        v1 = "上轨上方"
    elif price < lower[idx]:
        v1 = "下轨下方"
    elif price > mid[idx]:
        v1 = "中轨上方"
    else:
        v1 = "中轨下方"

    # 布林带宽度
    bw = (upper[idx] - lower[idx]) / mid[idx] if mid[idx] > 0 else 0
    v2 = "收窄" if bw < 0.05 else "扩张"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def tas_kdj_cross(freq: str, bars_raw: list, di: int = 1,
                  n: int = 9, m1: int = 3, m2: int = 3,
                  **kwargs) -> OrderedDict:
    """KDJ交叉信号

    参数模板："{freq}_D{di}KDJ{n}#{m1}#{m2}_交叉"

    信号逻辑：
    1. K上穿D → 金叉看多
    2. K下穿D → 死叉看空
    3. J > 100 或 J < 0 → 超买/超卖

    信号列表：
    - Signal('15分钟_D1KDJ9#3#3_交叉_金叉_任意_任意')
    - Signal('15分钟_D1KDJ9#3#3_交叉_死叉_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}KDJ{n}#{m1}#{m2}_交叉".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    k, d, j = _calc_kdj(high, low, close, n, m1, m2)
    idx = len(close) - di

    if idx < 1 or np.isnan(k[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if k[idx] > d[idx] and k[idx - 1] <= d[idx - 1]:
        v1 = "金叉"
    elif k[idx] < d[idx] and k[idx - 1] >= d[idx - 1]:
        v1 = "死叉"
    elif j[idx] > 100:
        v1 = "超买"
    elif j[idx] < 0:
        v1 = "超卖"
    elif k[idx] > d[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_rsi_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """RSI状态信号

    参数模板："{freq}_D{di}RSI{period}_状态"

    信号逻辑：
    1. RSI > 70 → 超买
    2. RSI < 30 → 超卖
    3. RSI在30-70之间 → 正常

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}RSI{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    rsi = _calc_rsi(close, period)
    idx = len(close) - di

    if np.isnan(rsi[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = rsi[idx]
    if val > 80:
        v1 = "极度超买"
    elif val > 70:
        v1 = "超买"
    elif val > 50:
        v1 = "偏强"
    elif val > 30:
        v1 = "偏弱"
    elif val > 20:
        v1 = "超卖"
    else:
        v1 = "极度超卖"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_cci_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """CCI状态信号

    参数模板："{freq}_D{di}CCI{period}_状态"

    信号逻辑：
    CCI > 100 看多，CCI < -100 看空

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}CCI{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    cci = _calc_cci(high, low, close, period)
    idx = len(close) - di

    if np.isnan(cci[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = cci[idx]
    if val > 200:
        v1 = "极度看多"
    elif val > 100:
        v1 = "看多"
    elif val > -100:
        v1 = "中性"
    elif val > -200:
        v1 = "看空"
    else:
        v1 = "极度看空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_sar_status(freq: str, bars_raw: list, di: int = 1,
                   **kwargs) -> OrderedDict:
    """SAR状态信号

    参数模板："{freq}_D{di}SAR_状态"

    信号逻辑：
    收盘价在SAR上方看多，下方看空

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}SAR_状态".split("_")
    if len(bars_raw) < 20 + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    sar = _calc_sar(high, low)
    idx = len(close) - di

    v1 = "看多" if close[idx] > sar[idx] else "看空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_dif_zero(freq: str, bars_raw: list, di: int = 1,
                 fastperiod: int = 12, slowperiod: int = 26,
                 signalperiod: int = 9, **kwargs) -> OrderedDict:
    """DIF零轴信号

    参数模板："{freq}_D{di}DIF零轴"

    信号逻辑：
    DIF > 0 多头，DIF < 0 空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}DIF零轴".split("_")
    if len(bars_raw) < slowperiod + signalperiod + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    dif, dea, macd = _calc_macd(close, fastperiod, slowperiod, signalperiod)

    idx = len(dif) - di
    if idx < 1 or np.isnan(dif[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if dif[idx] > 0 and dif[idx - 1] <= 0:
        v1 = "上穿零轴"
    elif dif[idx] < 0 and dif[idx - 1] >= 0:
        v1 = "下穿零轴"
    elif dif[idx] > 0:
        v1 = "零轴上方"
    else:
        v1 = "零轴下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_slope(freq: str, bars_raw: list, di: int = 1,
              n: int = 5, **kwargs) -> OrderedDict:
    """斜率信号

    参数模板："{freq}_D{di}斜率N{n}"

    信号逻辑：
    最近n根K线收盘价的线性回归斜率

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 回归K线数量
    """
    k1, k2, k3 = f"{freq}_D{di}斜率N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    recent = close[idx - n + 1:idx + 1]

    if len(recent) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    x = np.arange(n)
    slope = np.polyfit(x, recent, 1)[0]
    slope_pct = slope / np.mean(recent) * 100 if np.mean(recent) > 0 else 0

    if slope_pct > 1:
        v1 = "上升"
    elif slope_pct > 0:
        v1 = "微升"
    elif slope_pct > -1:
        v1 = "微降"
    else:
        v1 = "下降"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_accelerate(freq: str, bars_raw: list, di: int = 1,
                   n: int = 10, **kwargs) -> OrderedDict:
    """加速信号

    参数模板："{freq}_D{di}加速N{n}"

    信号逻辑：
    最近n根K线的涨幅/跌幅加速或减速

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}加速N{n}".split("_")
    if len(bars_raw) < n * 2 + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di

    # 前半段和后半段的涨幅
    first_half = close[idx - n:idx - n // 2]
    second_half = close[idx - n // 2:idx]

    if len(first_half) == 0 or len(second_half) == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    chg1 = (first_half[-1] - first_half[0]) / first_half[0] if first_half[0] > 0 else 0
    chg2 = (second_half[-1] - second_half[0]) / second_half[0] if second_half[0] > 0 else 0

    if chg2 > chg1 > 0:
        v1 = "加速上涨"
    elif chg2 < chg1 < 0:
        v1 = "加速下跌"
    elif chg1 > 0 > chg2:
        v1 = "上涨减速"
    elif chg1 < 0 < chg2:
        v1 = "下跌减速"
    else:
        v1 = "匀速"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_low_trend(freq: str, bars_raw: list, di: int = 1,
                  n: int = 20, m: int = 5, **kwargs) -> OrderedDict:
    """低位趋势信号

    参数模板："{freq}_D{di}低位趋势N{n}M{m}"

    信号逻辑：
    判断是否处于低位趋势

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}低位趋势N{n}M{m}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n:idx + 1]

    current = close[idx]
    window_low = np.min(window)
    window_high = np.max(window)
    window_range = window_high - window_low

    if window_range == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    position = (current - window_low) / window_range
    ma = _calc_ma(close, m)

    if position < 0.2 and current > ma[idx]:
        v1 = "低位反转"
    elif position < 0.2:
        v1 = "低位弱势"
    elif position > 0.8 and current < ma[idx]:
        v1 = "高位反转"
    elif position > 0.8:
        v1 = "高位强势"
    else:
        v1 = "中位震荡"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_angle(freq: str, bars_raw: list, di: int = 1,
              n: int = 5, **kwargs) -> OrderedDict:
    """角度信号

    参数模板："{freq}_D{di}角度N{n}"

    信号逻辑：
    收盘价变化的角度

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}角度N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    recent = close[idx - n + 1:idx + 1]

    if len(recent) < 2 or recent[0] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (recent[-1] - recent[0]) / recent[0] * 100
    if pct > 5:
        v1 = "陡峭上升"
    elif pct > 1:
        v1 = "平缓上升"
    elif pct > -1:
        v1 = "横盘"
    elif pct > -5:
        v1 = "平缓下降"
    else:
        v1 = "陡峭下降"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_dma_bs(freq: str, bars_raw: list, di: int = 1,
               fast: int = 10, slow: int = 50,
               signal_period: int = 10, **kwargs) -> OrderedDict:
    """DMA买卖信号

    参数模板："{freq}_D{di}DMAF{fast}S{slow}_BS"

    信号逻辑：
    DMA交叉判断买卖

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}DMAF{fast}S{slow}_BS".split("_")
    if len(bars_raw) < slow + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma_fast = _calc_ma(close, fast)
    ma_slow = _calc_ma(close, slow)
    dma = ma_fast - ma_slow
    ama = _calc_ma(dma, signal_period)

    idx = len(close) - di
    if idx < 1 or np.isnan(dma[idx]) or np.isnan(ama[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if dma[idx] > ama[idx] and dma[idx - 1] <= ama[idx - 1]:
        v1 = "看多"
    elif dma[idx] < ama[idx] and dma[idx - 1] >= ama[idx - 1]:
        v1 = "看空"
    elif dma[idx] > ama[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_rumi(freq: str, bars_raw: list, di: int = 1,
             fast: int = 3, slow: int = 20,
             **kwargs) -> OrderedDict:
    """RUMI指标信号

    参数模板："{freq}_D{di}RUMIF{fast}S{slow}"

    信号逻辑：
    快慢均线差值的移动平均与零轴关系

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}RUMIF{fast}S{slow}".split("_")
    if len(bars_raw) < slow + di + 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma_fast = _calc_ma(close, fast, 'EMA')
    ma_slow = _calc_ma(close, slow, 'EMA')
    diff = ma_fast - ma_slow
    rumi = _calc_ma(diff, 5, 'EMA')

    idx = len(close) - di
    if np.isnan(rumi[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    v1 = "看多" if rumi[idx] > 0 else "看空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_macd_bs1(freq: str, bars_raw: list, di: int = 1,
                 fastperiod: int = 12, slowperiod: int = 26,
                 signalperiod: int = 9, **kwargs) -> OrderedDict:
    """MACD一类买卖信号

    参数模板："{freq}_D{di}MACD_BS1"

    信号逻辑：
    DIF从零轴下方金叉 + DEA也在零轴下方 → 一类买
    DIF从零轴上方死叉 + DEA也在零轴上方 → 一类卖

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}MACD_BS1".split("_")
    if len(bars_raw) < slowperiod + signalperiod + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    dif, dea, macd = _calc_macd(close, fastperiod, slowperiod, signalperiod)

    idx = len(dif) - di
    if idx < 1 or np.isnan(dif[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if dif[idx] > dea[idx] and dif[idx - 1] <= dea[idx - 1] and dif[idx] < 0:
        v1 = "一类买"
    elif dif[idx] < dea[idx] and dif[idx - 1] >= dea[idx - 1] and dif[idx] > 0:
        v1 = "一类卖"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_volume_price(freq: str, bars_raw: list, di: int = 1,
                     n: int = 5, **kwargs) -> OrderedDict:
    """量价信号

    参数模板："{freq}_D{di}量价N{n}"

    信号逻辑：
    价格涨跌与成交量变化的配合关系

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}量价N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    if len(recent) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    prices = [b.close for b in recent if hasattr(b, 'close')]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(prices) < 2 or len(vols) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    price_up = prices[-1] > prices[0]
    vol_up = vols[-1] > vols[0]

    if price_up and vol_up:
        v1 = "量价齐升"
    elif not price_up and not vol_up:
        v1 = "量价齐跌"
    elif price_up and not vol_up:
        v1 = "价涨量缩"
    else:
        v1 = "价跌量增"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_bias_status(freq: str, bars_raw: list, di: int = 1,
                    period: int = 20, **kwargs) -> OrderedDict:
    """乖离率信号

    参数模板："{freq}_D{di}乖离率N{period}"

    信号逻辑：
    价格偏离均线的程度

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}乖离率N{period}".split("_")
    if len(bars_raw) < period + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma = _calc_ma(close, period)

    idx = len(close) - di
    if np.isnan(ma[idx]) or ma[idx] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bias = (close[idx] - ma[idx]) / ma[idx] * 100
    if bias > 5:
        v1 = "严重正乖离"
    elif bias > 2:
        v1 = "正乖离"
    elif bias > -2:
        v1 = "正常"
    elif bias > -5:
        v1 = "负乖离"
    else:
        v1 = "严重负乖离"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_emv_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """EMV状态信号

    参数模板："{freq}_D{di}EMV{period}"

    信号逻辑：
    EMV > 0 多头，EMV < 0 空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}EMV{period}".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    lows = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    vols = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    # 简化EMV计算
    dm = (highs + lows) / 2 - (np.roll(highs, 1) + np.roll(lows, 1)) / 2
    br = vols / (highs - lows + 0.001) * 10000
    emv = dm * br
    emv_ma = _calc_ma(emv, period)

    idx = len(close) - di
    if np.isnan(emv_ma[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    v1 = "看多" if emv_ma[idx] > 0 else "看空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_obv_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 20, **kwargs) -> OrderedDict:
    """OBV状态信号

    参数模板："{freq}_D{di}OBV{period}"

    信号逻辑：
    OBV与价格配合判断多空

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}OBV{period}".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    vols = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])

    # 计算OBV
    direction = np.where(np.diff(close) > 0, 1, np.where(np.diff(close) < 0, -1, 0))
    obv = np.zeros(len(close))
    obv[1:] = np.cumsum(direction * vols[1:])
    obv_ma = _calc_ma(obv, period)

    idx = len(close) - di
    if idx < 1 or np.isnan(obv_ma[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if obv[idx] > obv_ma[idx] and obv[idx - 1] <= obv_ma[idx - 1]:
        v1 = "看多"
    elif obv[idx] < obv_ma[idx] and obv[idx - 1] >= obv_ma[idx - 1]:
        v1 = "看空"
    elif obv[idx] > obv_ma[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


# ─── 扩展技术指标信号函数 ──────────────────────────────────────────

def _calc_wr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
             period: int = 14) -> np.ndarray:
    """计算威廉指标(WR)"""
    high_max = pd.Series(high).rolling(period).max()
    low_min = pd.Series(low).rolling(period).min()
    wr = (high_max - close) / (high_max - low_min + 1e-10) * 100
    return wr.values


def _calc_dmi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算DMI指标(+DI, -DI, ADX)"""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)

    # 真实波幅
    tr1 = h - l
    tr2 = abs(h - c.shift(1))
    tr3 = abs(l - c.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 方向移动
    up_move = h - h.shift(1)
    down_move = l.shift(1) - l

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_di = pd.Series(plus_dm).rolling(period).mean() / tr.rolling(period).mean() * 100
    minus_di = pd.Series(minus_dm).rolling(period).mean() / tr.rolling(period).mean() * 100

    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
    adx = dx.rolling(period).mean()

    return plus_di.values, minus_di.values, adx.values


def _calc_trix(close: np.ndarray, period: int = 12) -> np.ndarray:
    """计算TRIX三重指数平滑"""
    ema1 = pd.Series(close).ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    trix = (ema3 - ema3.shift(1)) / (ema3.shift(1) + 1e-10) * 100
    return trix.values


def _calc_roc(close: np.ndarray, period: int = 12) -> np.ndarray:
    """计算ROC变动率"""
    roc = (pd.Series(close) - pd.Series(close).shift(period)) / (pd.Series(close).shift(period) + 1e-10) * 100
    return roc.values


def _calc_mtm(close: np.ndarray, period: int = 12) -> np.ndarray:
    """计算MTM动量"""
    return (pd.Series(close) - pd.Series(close).shift(period)).values


def _calc_psy(close: np.ndarray, period: int = 12) -> np.ndarray:
    """计算PSY心理线"""
    diff = pd.Series(close).diff()
    psy = diff.rolling(period).apply(lambda x: sum(x > 0) / len(x) * 100, raw=True)
    return psy.values


def _calc_vr(close: np.ndarray, volume: np.ndarray,
             period: int = 26) -> np.ndarray:
    """计算VR容量比率"""
    diff = pd.Series(close).diff()
    up_vol = pd.Series(np.where(diff > 0, volume, 0)).rolling(period).sum()
    down_vol = pd.Series(np.where(diff < 0, volume, 0)).rolling(period).sum()
    eq_vol = pd.Series(np.where(diff == 0, volume, 0)).rolling(period).sum()
    vr = (up_vol + eq_vol / 2) / (down_vol + eq_vol / 2 + 1e-10) * 100
    return vr.values


def tas_wr_status(freq: str, bars_raw: list, di: int = 1,
                  period: int = 14, **kwargs) -> OrderedDict:
    """威廉指标信号

    参数模板："{freq}_D{di}WR{period}_状态"

    信号逻辑：
    WR > 80 超卖，WR < 20 超买

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: WR周期
    """
    k1, k2, k3 = f"{freq}_D{di}WR{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    wr = _calc_wr(high, low, close, period)
    idx = len(close) - di

    if np.isnan(wr[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = wr[idx]
    if val > 80:
        v1 = "超卖"
    elif val > 50:
        v1 = "偏弱"
    elif val > 20:
        v1 = "偏强"
    else:
        v1 = "超买"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_dmi_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """DMI动向指标信号

    参数模板："{freq}_D{di}DMI{period}_状态"

    信号逻辑：
    +DI > -DI 多头，-DI > +DI 空头，ADX判断趋势强度

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: DMI周期
    """
    k1, k2, k3 = f"{freq}_D{di}DMI{period}_状态".split("_")
    if len(bars_raw) < period * 2 + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    plus_di, minus_di, adx = _calc_dmi(high, low, close, period)
    idx = len(close) - di

    if np.isnan(plus_di[idx]) or np.isnan(minus_di[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if plus_di[idx] > minus_di[idx]:
        v1 = "多头"
    else:
        v1 = "空头"

    adx_val = adx[idx] if not np.isnan(adx[idx]) else 0
    if adx_val > 40:
        v2 = "强趋势"
    elif adx_val > 25:
        v2 = "有趋势"
    else:
        v2 = "无趋势"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def tas_trix_signal(freq: str, bars_raw: list, di: int = 1,
                    period: int = 12, **kwargs) -> OrderedDict:
    """TRIX三重指数信号

    参数模板："{freq}_D{di}TRIX{period}_信号"

    信号逻辑：
    TRIX > 0 多头，TRIX < 0 空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: TRIX周期
    """
    k1, k2, k3 = f"{freq}_D{di}TRIX{period}_信号".split("_")
    if len(bars_raw) < period * 3 + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    trix = _calc_trix(close, period)

    idx = len(close) - di
    if idx < 1 or np.isnan(trix[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if trix[idx] > 0 and trix[idx - 1] <= 0:
        v1 = "金叉"
    elif trix[idx] < 0 and trix[idx - 1] >= 0:
        v1 = "死叉"
    elif trix[idx] > 0:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_roc_signal(freq: str, bars_raw: list, di: int = 1,
                   period: int = 12, **kwargs) -> OrderedDict:
    """ROC变动率信号

    参数模板："{freq}_D{di}ROC{period}_信号"

    信号逻辑：
    ROC > 0 上涨动量，ROC < 0 下跌动量

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: ROC周期
    """
    k1, k2, k3 = f"{freq}_D{di}ROC{period}_信号".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    roc = _calc_roc(close, period)

    idx = len(close) - di
    if np.isnan(roc[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = roc[idx]
    if val > 10:
        v1 = "强多"
    elif val > 3:
        v1 = "偏多"
    elif val > -3:
        v1 = "中性"
    elif val > -10:
        v1 = "偏空"
    else:
        v1 = "强空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_mtm_signal(freq: str, bars_raw: list, di: int = 1,
                   period: int = 12, **kwargs) -> OrderedDict:
    """MTM动量信号

    参数模板："{freq}_D{di}MTM{period}_信号"

    信号逻辑：
    MTM > 0 上涨动量，MTM < 0 下跌动量

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: MTM周期
    """
    k1, k2, k3 = f"{freq}_D{di}MTM{period}_信号".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    mtm = _calc_mtm(close, period)

    idx = len(close) - di
    if np.isnan(mtm[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if mtm[idx] > 0:
        v1 = "多头动量"
    elif mtm[idx] < 0:
        v1 = "空头动量"
    else:
        v1 = "动量平衡"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_psy_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 12, **kwargs) -> OrderedDict:
    """PSY心理线信号

    参数模板："{freq}_D{di}PSY{period}_状态"

    信号逻辑：
    PSY > 75 超买，PSY < 25 超卖

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: PSY周期
    """
    k1, k2, k3 = f"{freq}_D{di}PSY{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    psy = _calc_psy(close, period)

    idx = len(close) - di
    if np.isnan(psy[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = psy[idx]
    if val > 75:
        v1 = "超买"
    elif val > 50:
        v1 = "偏强"
    elif val > 25:
        v1 = "偏弱"
    else:
        v1 = "超卖"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_vr_status(freq: str, bars_raw: list, di: int = 1,
                  period: int = 26, **kwargs) -> OrderedDict:
    """VR容量比率信号

    参数模板："{freq}_D{di}VR{period}_状态"

    信号逻辑：
    VR > 350 超买，VR < 70 超卖

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: VR周期
    """
    k1, k2, k3 = f"{freq}_D{di}VR{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    volume = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])

    vr = _calc_vr(close, volume, period)
    idx = len(close) - di

    if np.isnan(vr[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = vr[idx]
    if val > 350:
        v1 = "超买"
    elif val > 200:
        v1 = "偏多"
    elif val > 70:
        v1 = "正常"
    elif val > 40:
        v1 = "偏空"
    else:
        v1 = "超卖"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_wad_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 20, **kwargs) -> OrderedDict:
    """WAD累积/分散信号

    参数模板："{freq}_D{di}WAD{period}_状态"

    信号逻辑：
    WAD上升多头，WAD下降空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: WAD周期
    """
    k1, k2, k3 = f"{freq}_D{di}WAD{period}_状态".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])

    # WAD计算
    prev_close = np.roll(close, 1)
    trh = np.maximum(high, prev_close)
    trl = np.minimum(low, prev_close)
    ad = np.where(close > close[0], close - trl, np.where(close < close[0], close - trh, 0))
    ad[0] = 0
    wad = np.cumsum(ad)
    wad_ma = pd.Series(wad).rolling(period).mean().values

    idx = len(close) - di
    if np.isnan(wad_ma[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if wad[idx] > wad_ma[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_adx_status(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """ADX趋势强度信号

    参数模板："{freq}_D{di}ADX{period}_趋势强度"

    信号逻辑：
    ADX > 40 强趋势，ADX < 20 无趋势

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: ADX周期
    """
    k1, k2, k3 = f"{freq}_D{di}ADX{period}_趋势强度".split("_")
    if len(bars_raw) < period * 2 + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    _, _, adx = _calc_dmi(high, low, close, period)
    idx = len(close) - di

    if np.isnan(adx[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = adx[idx]
    if val > 50:
        v1 = "极强趋势"
    elif val > 40:
        v1 = "强趋势"
    elif val > 25:
        v1 = "有趋势"
    else:
        v1 = "无趋势"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def tas_tsi_signal(freq: str, bars_raw: list, di: int = 1,
                   fast: int = 13, slow: int = 25,
                   signal_period: int = 13, **kwargs) -> OrderedDict:
    """TSI真实力度指标信号

    参数模板："{freq}_D{di}TSIF{fast}S{slow}_信号"

    信号逻辑：
    TSI > 0 多头，TSI < 0 空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}TSIF{fast}S{slow}_信号".split("_")
    if len(bars_raw) < slow * 2 + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])

    # TSI计算
    momentum = pd.Series(close).diff()
    abs_momentum = momentum.abs()
    ema_mom = momentum.ewm(span=slow, adjust=False).mean()
    ema_abs_mom = abs_momentum.ewm(span=slow, adjust=False).mean()
    double_ema_mom = ema_mom.ewm(span=fast, adjust=False).mean()
    double_ema_abs_mom = ema_abs_mom.ewm(span=fast, adjust=False).mean()
    tsi = (double_ema_mom / (double_ema_abs_mom + 1e-10)) * 100

    idx = len(close) - di
    if np.isnan(tsi[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = tsi[idx]
    if val > 20:
        v1 = "强多"
    elif val > 0:
        v1 = "多头"
    elif val > -20:
        v1 = "空头"
    else:
        v1 = "强空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
