#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
位置信号 (pos = Position)

参考 czsc.signals.pos 的设计，实现基于价格位置关系的信号函数。
判断价格在关键支撑/阻力位、均线、通道、前高前低等位置。

信号列表：
1.  pos_above_ma          - 均线上方位置信号
2.  pos_ma_cross          - 均线穿越位置信号
3.  pos_support_resistance- 支撑阻力位信号
4.  pos_high_low          - 前高前低位置信号
5.  pos_gap_fill          - 缺口回补信号
6.  pos_trend_line        - 趋势线位置信号
7.  pos_fibonacci         - 斐波那契回撤信号
8.  pos_pivot             - 枢轴点位置信号
9.  pos_channel_position  - 通道位置信号
10. pos_price_zone        - 价格区间位置信号
11. pos_ma_band           - 均线带位置信号
12. pos_round_number      - 整数关口信号
13. pos_volume_profile    - 成交量分布位置信号
14. pos_boll_position     - 布林带位置信号
15. pos_kelt_position     - 凯尔特纳通道位置信号
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from collections import OrderedDict

from .cxt import create_single_signal, get_sub_elements
from .tas import _calc_ma, _calc_boll


def _calc_keltner(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                  period: int = 20, atr_period: int = 10,
                  multiplier: float = 1.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算凯尔特纳通道"""
    ema = pd.Series(close).ewm(span=period, adjust=False).mean().values
    tr = np.maximum(
        np.abs(high - low),
        np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1)))
    )
    tr[0] = high[0] - low[0]
    atr = pd.Series(tr).rolling(atr_period).mean().values
    upper = ema + multiplier * atr
    lower = ema - multiplier * atr
    return upper, ema, lower


def _calc_pivot(high: np.ndarray, low: np.ndarray, close: np.ndarray):
    """计算枢轴点"""
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return pivot, r1, s1, r2, s2, r3, s3


def _calc_fibonacci(high: float, low: float):
    """计算斐波那契回撤位"""
    diff = high - low
    return {
        0.0: high,
        0.236: high - 0.236 * diff,
        0.382: high - 0.382 * diff,
        0.5: high - 0.5 * diff,
        0.618: high - 0.618 * diff,
        0.786: high - 0.786 * diff,
        1.0: low,
    }


def pos_above_ma(freq: str, bars_raw: list, di: int = 1,
                 ma_period: int = 20, ma_type: str = 'EMA',
                 **kwargs) -> OrderedDict:
    """均线上方位置信号

    参数模板："{freq}_D{di}MA{ma_type}#{ma_period}_上方位置"

    信号逻辑：
    当前价格在均线上方/下方，以及距离均线的远近

    信号列表：
    - Signal('15分钟_D1MAEMA#20_上方位置_远高于_任意')
    - Signal('15分钟_D1MAEMA#20_上方位置_远低于_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param ma_period: 均线周期
    :param ma_type: 均线类型
    """
    k1, k2, k3 = f"{freq}_D{di}MA{ma_type}#{ma_period}_上方位置".split("_")
    if len(bars_raw) < ma_period + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma = _calc_ma(close, ma_period, ma_type)

    idx = len(close) - di
    if np.isnan(ma[idx]) or ma[idx] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (close[idx] - ma[idx]) / ma[idx] * 100
    if pct > 5:
        v1 = "远高于"
    elif pct > 2:
        v1 = "偏高于"
    elif pct > 0:
        v1 = "略高于"
    elif pct > -2:
        v1 = "略低于"
    elif pct > -5:
        v1 = "偏低于"
    else:
        v1 = "远低于"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_ma_cross(freq: str, bars_raw: list, di: int = 1,
                 ma_period: int = 60, **kwargs) -> OrderedDict:
    """均线穿越位置信号

    参数模板："{freq}_D{di}MA{ma_period}_穿越位置"

    信号逻辑：
    价格从哪个方向穿越均线

    信号列表：
    - Signal('15分钟_D1MA60_穿越位置_上穿_任意')
    - Signal('15分钟_D1MA60_穿越位置_下穿_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param ma_period: 均线周期
    """
    k1, k2, k3 = f"{freq}_D{di}MA{ma_period}_穿越位置".split("_")
    if len(bars_raw) < ma_period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma = _calc_ma(close, ma_period)

    idx = len(close) - di
    if idx < 1 or np.isnan(ma[idx]) or np.isnan(ma[idx - 1]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if close[idx] > ma[idx] and close[idx - 1] <= ma[idx - 1]:
        v1 = "上穿"
    elif close[idx] < ma[idx] and close[idx - 1] >= ma[idx - 1]:
        v1 = "下穿"
    elif close[idx] > ma[idx]:
        v1 = "均线上方"
    else:
        v1 = "均线下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_support_resistance(freq: str, bars_raw: list, di: int = 1,
                           n: int = 30, **kwargs) -> OrderedDict:
    """支撑阻力位信号

    参数模板："{freq}_D{di}SRN{n}_支撑阻力"

    信号逻辑：
    根据最近n根K线的高低点判断支撑阻力

    信号列表：
    - Signal('15分钟_D1SRN30_支撑阻力_接近阻力_任意')
    - Signal('15分钟_D1SRN30_支撑阻力_接近支撑_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}SRN{n}_支撑阻力".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    highs = [b.high for b in recent if hasattr(b, 'high')]
    lows = [b.low for b in recent if hasattr(b, 'low')]
    closes = [b.close for b in recent if hasattr(b, 'close')]

    if not highs or not lows:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    resistance = max(highs[:-1]) if len(highs) > 1 else highs[0]
    support = min(lows[:-1]) if len(lows) > 1 else lows[0]
    current = closes[-1]

    if resistance == support:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 计算当前价格在支撑阻力之间的位置
    position = (current - support) / (resistance - support)
    if position > 0.9:
        v1 = "接近阻力"
    elif position < 0.1:
        v1 = "接近支撑"
    elif position > 0.5:
        v1 = "中上区间"
    else:
        v1 = "中下区间"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_high_low(freq: str, bars_raw: list, di: int = 1,
                 n: int = 60, **kwargs) -> OrderedDict:
    """前高前低位置信号

    参数模板："{freq}_D{di}HLN{n}_前高前低"

    信号逻辑：
    当前价格相对前高前低的位置

    信号列表：
    - Signal('15分钟_D1HLN60_前高前低_创新高_任意')
    - Signal('15分钟_D1HLN60_前高前低_创新低_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}HLN{n}_前高前低".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    highs = [b.high for b in recent if hasattr(b, 'high')]
    lows = [b.low for b in recent if hasattr(b, 'low')]
    closes = [b.close for b in recent if hasattr(b, 'close')]

    if not highs or not lows or not closes:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    prev_high = max(highs[:-1]) if len(highs) > 1 else highs[0]
    prev_low = min(lows[:-1]) if len(lows) > 1 else lows[0]
    current = closes[-1]

    if current > prev_high:
        v1 = "创新高"
    elif current < prev_low:
        v1 = "创新低"
    elif current > (prev_high + prev_low) / 2:
        v1 = "前高附近"
    else:
        v1 = "前低附近"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_gap_fill(freq: str, bars_raw: list, di: int = 1,
                 n: int = 30, **kwargs) -> OrderedDict:
    """缺口回补信号

    参数模板："{freq}_D{di}GAPN{n}_缺口回补"

    信号逻辑：
    检测最近的跳空缺口是否被回补

    信号列表：
    - Signal('15分钟_D1GAPN30_缺口回补_向上缺口未补_任意')
    - Signal('15分钟_D1GAPN30_缺口回补_向下缺口已补_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}GAPN{n}_缺口回补".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    if len(recent) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 查找缺口
    gaps = []
    for i in range(1, len(recent)):
        prev = recent[i - 1]
        curr = recent[i]
        if not hasattr(prev, 'high') or not hasattr(curr, 'low'):
            continue
        if curr.low > prev.high:
            gaps.append(('up', curr.low, prev.high, i))
        elif curr.high < prev.low:
            gaps.append(('down', prev.low, curr.high, i))

    if not gaps:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="无缺口")

    current = recent[-1].close if hasattr(recent[-1], 'close') else 0
    last_gap = gaps[-1]

    if last_gap[0] == 'up':
        if current < last_gap[1]:
            v1 = "向上缺口已补"
        else:
            v1 = "向上缺口未补"
    else:
        if current > last_gap[1]:
            v1 = "向下缺口已补"
        else:
            v1 = "向下缺口未补"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_trend_line(freq: str, bars_raw: list, di: int = 1,
                   n: int = 20, **kwargs) -> OrderedDict:
    """趋势线位置信号

    参数模板："{freq}_D{di}TLN{n}_趋势线"

    信号逻辑：
    用最近n根K线的低点拟合上升趋势线，判断当前价格与趋势线的关系

    信号列表：
    - Signal('15分钟_D1TLN20_趋势线_趋势线上方_任意')
    - Signal('15分钟_D1TLN20_趋势线_趋势线下方_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 拟合K线数量
    """
    k1, k2, k3 = f"{freq}_D{di}TLN{n}_趋势线".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    if len(recent) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    lows = np.array([b.low for b in recent if hasattr(b, 'low')])
    closes = np.array([b.close for b in recent if hasattr(b, 'close')])

    if len(lows) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 拟合低点趋势线
    x = np.arange(len(lows))
    try:
        slope, intercept = np.polyfit(x, lows, 1)
        trend_line_now = slope * (len(lows) - 1) + intercept
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    current = closes[-1]
    if trend_line_now == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (current - trend_line_now) / abs(trend_line_now) * 100
    if pct > 3:
        v1 = "远高于趋势线"
    elif pct > 0:
        v1 = "趋势线上方"
    elif pct > -3:
        v1 = "趋势线下方"
    else:
        v1 = "远低于趋势线"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_fibonacci(freq: str, bars_raw: list, di: int = 1,
                  n: int = 60, **kwargs) -> OrderedDict:
    """斐波那契回撤信号

    参数模板："{freq}_D{di}FIBN{n}_回撤"

    信号逻辑：
    根据最近n根K线的高低点计算斐波那契回撤位，判断当前价格所处位置

    信号列表：
    - Signal('15分钟_D1FIBN60_回撤_0.382_任意')
    - Signal('15分钟_D1FIBN60_回撤_0.618_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}FIBN{n}_回撤".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    highs = [b.high for b in recent if hasattr(b, 'high')]
    lows = [b.low for b in recent if hasattr(b, 'low')]
    closes = [b.close for b in recent if hasattr(b, 'close')]

    if not highs or not lows:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    high = max(highs)
    low = min(lows)
    current = closes[-1]
    fib_levels = _calc_fibonacci(high, low)

    # 判断价格最接近哪个回撤位
    closest_level = None
    min_dist = float('inf')
    for ratio, price in fib_levels.items():
        dist = abs(current - price)
        if dist < min_dist:
            min_dist = dist
            closest_level = ratio

    if closest_level is not None:
        v1 = f"{closest_level:.3f}"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_pivot(freq: str, bars_raw: list, di: int = 1,
              **kwargs) -> OrderedDict:
    """枢轴点位置信号

    参数模板："{freq}_D{di}_枢轴点"

    信号逻辑：
    根据前一根K线计算枢轴点，判断当前价格在枢轴点的位置

    信号列表：
    - Signal('15分钟_D1_枢轴点_R1上方_任意')
    - Signal('15分钟_D1_枢轴点_S1下方_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}_枢轴点".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    if len(recent) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    prev = recent[-2] if len(recent) >= 2 else recent[0]
    curr = recent[-1]

    if not all(hasattr(prev, attr) for attr in ['high', 'low', 'close']):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pivot, r1, s1, r2, s2, r3, s3 = _calc_pivot(
        np.array([prev.high]), np.array([prev.low]), np.array([prev.close])
    )

    current = curr.close if hasattr(curr, 'close') else 0
    p = pivot[0]
    r1_val = r1[0]
    s1_val = s1[0]
    r2_val = r2[0]
    s2_val = s2[0]

    if current > r2_val:
        v1 = "R2上方"
    elif current > r1_val:
        v1 = "R1上方"
    elif current > p:
        v1 = "枢轴上方"
    elif current > s1_val:
        v1 = "枢轴下方"
    elif current > s2_val:
        v1 = "S1下方"
    else:
        v1 = "S2下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_channel_position(freq: str, bars_raw: list, di: int = 1,
                         n: int = 20, **kwargs) -> OrderedDict:
    """通道位置信号

    参数模板："{freq}_D{di}CHN{n}_通道位置"

    信号逻辑：
    用线性回归计算价格通道，判断当前价格在通道中的位置

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 通道计算K线数量
    """
    k1, k2, k3 = f"{freq}_D{di}CHN{n}_通道位置".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    recent = close[idx - n:idx + 1]

    if len(recent) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    x = np.arange(len(recent))
    try:
        slope, intercept = np.polyfit(x, recent, 1)
        residuals = recent - (slope * x + intercept)
        std_resid = np.std(residuals)
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    mid = slope * (len(recent) - 1) + intercept
    upper = mid + 2 * std_resid
    lower = mid - 2 * std_resid

    current = close[idx]
    if upper == lower:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    position = (current - lower) / (upper - lower)
    if position > 1:
        v1 = "通道上方"
    elif position > 0.8:
        v1 = "上轨附近"
    elif position < 0:
        v1 = "通道下方"
    elif position < 0.2:
        v1 = "下轨附近"
    else:
        v1 = "通道中部"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_price_zone(freq: str, bars_raw: list, di: int = 1,
                   n: int = 60, threshold: float = 0.3,
                   **kwargs) -> OrderedDict:
    """价格区间位置信号

    参数模板："{freq}_D{di}PZN{n}_价格区间"

    信号逻辑：
    当前价格在n根K线高低点范围中的位置

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}PZN{n}_价格区间".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n + 1:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    w_high = np.max(window)
    w_low = np.min(window)
    w_range = w_high - w_low

    if w_range == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    position = (close[idx] - w_low) / w_range
    if position > 0.9:
        v1 = "高位区"
    elif position > 0.7:
        v1 = "偏高区"
    elif position > threshold:
        v1 = "中间区"
    elif position > 0.1:
        v1 = "偏低区"
    else:
        v1 = "低位区"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_ma_band(freq: str, bars_raw: list, di: int = 1,
                fast: int = 5, slow: int = 20,
                **kwargs) -> OrderedDict:
    """均线带位置信号

    参数模板："{freq}_D{di}MABF{fast}S{slow}_均线带"

    信号逻辑：
    当前价格在快慢均线带中的位置

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}MABF{fast}S{slow}_均线带".split("_")
    if len(bars_raw) < slow + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    ma_fast = _calc_ma(close, fast, 'EMA')
    ma_slow = _calc_ma(close, slow, 'EMA')

    idx = len(close) - di
    if np.isnan(ma_fast[idx]) or np.isnan(ma_slow[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    current = close[idx]
    upper = max(ma_fast[idx], ma_slow[idx])
    lower = min(ma_fast[idx], ma_slow[idx])

    if current > upper:
        v1 = "均线上方"
    elif current < lower:
        v1 = "均线下方"
    else:
        v1 = "均线之间"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_round_number(freq: str, bars_raw: list, di: int = 1,
                     **kwargs) -> OrderedDict:
    """整数关口信号

    参数模板："{freq}_D{di}_整数关口"

    信号逻辑：
    判断当前价格是否接近整数关口（百/千/万等）

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}_整数关口".split("_")
    if len(bars_raw) < di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-di:] if di == 1 else bars_raw[-di:-di + 1]
    if not recent:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    current = recent[-1].close if hasattr(recent[-1], 'close') else 0
    if current <= 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 判断接近哪个整数关口
    magnitude = 10 ** int(np.log10(current))
    if magnitude < 1:
        magnitude = 1
    round_base = magnitude / 10

    nearest_round = round(current / round_base) * round_base
    dist_pct = abs(current - nearest_round) / current * 100

    if dist_pct < 0.5:
        v1 = f"接近{int(nearest_round)}关口"
    elif dist_pct < 2:
        v1 = f"临近{int(nearest_round)}关口"
    else:
        v1 = "远离关口"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_volume_profile(freq: str, bars_raw: list, di: int = 1,
                       n: int = 30, bins: int = 5,
                       **kwargs) -> OrderedDict:
    """成交量分布位置信号

    参数模板："{freq}_D{di}VPN{n}B{bins}_量分布"

    信号逻辑：
    根据成交量分布判断当前价格在高量区还是低量区

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    :param bins: 分层数量
    """
    k1, k2, k3 = f"{freq}_D{di}VPN{n}B{bins}_量分布".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    closes = [b.close for b in recent if hasattr(b, 'close')]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(closes) < n or len(vols) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    price_range = max(closes) - min(closes)
    if price_range == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 按价格区间统计成交量
    vol_by_bin = [0] * bins
    for c, v in zip(closes, vols):
        bin_idx = min(int((c - min(closes)) / price_range * bins), bins - 1)
        vol_by_bin[bin_idx] += v

    current = closes[-1]
    bin_idx = min(int((current - min(closes)) / price_range * bins), bins - 1)
    bin_vol = vol_by_bin[bin_idx]
    max_vol = max(vol_by_bin) if vol_by_bin else 1

    if max_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = bin_vol / max_vol
    if ratio > 0.8:
        v1 = "高量区"
    elif ratio > 0.5:
        v1 = "中量区"
    else:
        v1 = "低量区"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_boll_position(freq: str, bars_raw: list, di: int = 1,
                      period: int = 20, nbdev: float = 2.0,
                      **kwargs) -> OrderedDict:
    """布林带位置信号

    参数模板："{freq}_D{di}BOLLP{period}_位置"

    信号逻辑：
    当前价格在布林带中的精确位置百分比

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}BOLLP{period}_位置".split("_")
    if len(bars_raw) < period + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    upper, mid, lower = _calc_boll(close, period, nbdev)

    idx = len(close) - di
    if np.isnan(upper[idx]) or np.isnan(lower[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bw = upper[idx] - lower[idx]
    if bw == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (close[idx] - lower[idx]) / bw
    if pct > 1:
        v1 = "上轨上方"
    elif pct > 0.8:
        v1 = "上轨附近"
    elif pct > 0.5:
        v1 = "中轨上方"
    elif pct > 0.2:
        v1 = "中轨下方"
    elif pct > 0:
        v1 = "下轨附近"
    else:
        v1 = "下轨下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def pos_kelt_position(freq: str, bars_raw: list, di: int = 1,
                      period: int = 20, atr_period: int = 10,
                      **kwargs) -> OrderedDict:
    """凯尔特纳通道位置信号

    参数模板："{freq}_D{di}KELTP{period}_位置"

    信号逻辑：
    当前价格在凯尔特纳通道中的位置

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}KELTP{period}_位置".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])

    upper, mid, lower = _calc_keltner(close, high, low, period, atr_period)

    idx = len(close) - di
    if np.isnan(upper[idx]) or np.isnan(lower[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    current = close[idx]
    if current > upper[idx]:
        v1 = "通道上方"
    elif current > mid[idx]:
        v1 = "中轨上方"
    elif current > lower[idx]:
        v1 = "中轨下方"
    else:
        v1 = "通道下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
