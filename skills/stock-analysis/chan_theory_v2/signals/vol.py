#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成交量信号 (vol)

参考 czsc.signals.vol 的设计，实现基于成交量的信号函数。

信号列表：
1.  vol_single_ma        - 量均线信号
2.  vol_double_ma        - 双量均线信号
3.  vol_ti_suo           - 提缩量信号
4.  vol_gao_di           - 高低量柱信号
5.  vol_window           - 窗口能量信号
6.  vol_window_v2        - 窗口能量信号V2
7.  vol_break            - 放量突破信号
8.  vol_shrink           - 缩量信号
9.  vol_ratio_signal     - 量比信号
10. vol_price_divergence - 量价背离信号
11. vol_vwap             - VWAP信号
12. vol_pvt_signal       - PVT价量趋势信号
13. vol_mfi_signal       - MFI资金流量信号
14. vol_volatility_ratio - 量波动率信号
15. vol_adi_signal       - ADI累积离差指标信号
"""

import numpy as np
import pandas as pd
from typing import List, Optional
from collections import OrderedDict

from .cxt import create_single_signal, get_sub_elements


def _calc_vol_ma(vols: np.ndarray, period: int, ma_type: str = 'SMA') -> np.ndarray:
    """计算成交量均线"""
    if ma_type == 'EMA':
        return pd.Series(vols).ewm(span=period, adjust=False).mean().values
    else:
        return pd.Series(vols).rolling(period).mean().values


def vol_single_ma(freq: str, bars_raw: list, di: int = 1,
                  ma_type: str = 'SMA', timeperiod: int = 20,
                  **kwargs) -> OrderedDict:
    """量均线信号

    参数模板："{freq}_D{di}VOL{ma_type}#{timeperiod}_单量线"

    信号逻辑：
    成交量与量均线的相对位置

    信号列表：
    - Signal('15分钟_D1VOLSMA#20_单量线_放量_任意_任意')
    - Signal('15分钟_D1VOLSMA#20_单量线_缩量_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param ma_type: 均线类型
    :param timeperiod: 均线周期
    """
    k1, k2, k3 = f"{freq}_D{di}VOL{ma_type}#{timeperiod}_单量线".split("_")
    if len(bars_raw) < timeperiod + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])
    vol_ma = _calc_vol_ma(vols, timeperiod, ma_type)

    idx = len(vols) - di
    if np.isnan(vol_ma[idx]) or vol_ma[idx] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = vols[idx] / vol_ma[idx]
    if ratio > 2:
        v1 = "巨量"
    elif ratio > 1.5:
        v1 = "放量"
    elif ratio > 0.8:
        v1 = "正常"
    elif ratio > 0.5:
        v1 = "缩量"
    else:
        v1 = "地量"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_double_ma(freq: str, bars_raw: list, di: int = 1,
                  fast: int = 5, slow: int = 20,
                  ma_type: str = 'SMA', **kwargs) -> OrderedDict:
    """双量均线信号

    参数模板："{freq}_D{di}VOL{ma_type}#{fast}#{slow}_双量线"

    信号逻辑：
    快慢量均线交叉

    信号列表：
    - Signal('15分钟_D1VOLSMA#5#20_双量线_金叉_任意_任意')
    - Signal('15分钟_D1VOLSMA#5#20_双量线_死叉_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}VOL{ma_type}#{fast}#{slow}_双量线".split("_")
    if len(bars_raw) < slow + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])
    ma_fast = _calc_vol_ma(vols, fast, ma_type)
    ma_slow = _calc_vol_ma(vols, slow, ma_type)

    idx = len(vols) - di
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


def vol_ti_suo(freq: str, bars_raw: list, di: int = 1,
               n: int = 5, **kwargs) -> OrderedDict:
    """提缩量信号

    参数模板："{freq}_D{di}量柱N{n}_提缩"

    信号逻辑：
    判断量柱是否递增（提）或递减（缩）

    信号列表：
    - Signal('15分钟_D1量柱N5_提缩_递增_任意_任意')
    - Signal('15分钟_D1量柱N5_提缩_递减_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 取K线数量
    """
    k1, k2, k3 = f"{freq}_D{di}量柱N{n}_提缩".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(vols) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    is_increasing = all(vols[i] < vols[i + 1] for i in range(len(vols) - 1))
    is_decreasing = all(vols[i] > vols[i + 1] for i in range(len(vols) - 1))

    if is_increasing:
        v1 = "递增"
    elif is_decreasing:
        v1 = "递减"
    else:
        v1 = "无序"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_gao_di(freq: str, bars_raw: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """高低量柱信号

    参数模板："{freq}_D{di}K_量柱"

    信号逻辑：
    判断当前K线量柱类型（高量柱/低量柱/黄金柱）

    信号列表：
    - Signal('15分钟_D1K_量柱_高量柱_任意_任意')
    - Signal('15分钟_D1K_量柱_低量柱_任意_任意')
    - Signal('15分钟_D1K_量柱_高量黄金柱_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}K_量柱".split("_")

    for n in (10, 9, 8, 7, 6):
        if len(bars_raw) < n + di:
            continue
        recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
        vols = [b.volume for b in recent if hasattr(b, 'volume')]

        if len(vols) != n:
            continue

        max_vol = max(vols)
        min_vol = min(vols)

        if vols[-1] == max_vol:
            v1 = "高量柱"
            v2 = f"{n}K"
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)
        elif vols[-2] == max_vol and vols[-1] < vols[-2] * 0.5:
            v1 = "高量黄金柱"
            v2 = f"{n}K"
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)
        elif vols[-1] == min_vol:
            v1 = "低量柱"
            v2 = f"{n}K"
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)

    return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")


def vol_window(freq: str, bars_raw: list, di: int = 1,
               w: int = 5, m: int = 30, n: int = 10,
               **kwargs) -> OrderedDict:
    """窗口能量信号

    参数模板："{freq}_D{di}W{w}M{m}N{n}_窗口能量"

    信号逻辑：
    取最近m根K线成交量分层，观察窗口w内的成交量层级

    信号列表：
    - Signal('60分钟_D1W5M30N10_窗口能量_高量N9_低量N4_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param w: 观察窗口大小
    :param m: 分层取K线数量
    :param n: 分层数量
    """
    k1, k2, k3 = f"{freq}_D{di}W{w}M{m}N{n}_窗口能量".split("_")
    if len(bars_raw) < di + m:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = [b.volume for b in bars_raw[-(di + m - 1):] if hasattr(b, 'volume')][-m:]
    if len(vols) < m:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    try:
        vol_layer = pd.qcut(vols, n, labels=False, duplicates='drop')
        max_vol_layer = max(vol_layer[-w:]) + 1
        min_vol_layer = min(vol_layer[-w:]) + 1
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    v1 = f"高量N{max_vol_layer}"
    v2 = f"低量N{min_vol_layer}"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def vol_window_v2(freq: str, bars_raw: list, di: int = 1,
                  w: int = 5, **kwargs) -> OrderedDict:
    """窗口能量信号V2

    参数模板："{freq}_D{di}W{w}_窗口能量V2"

    信号逻辑：
    观察窗口内最大量与最小量的先后顺序

    信号列表：
    - Signal('60分钟_D1W5_窗口能量V2_先缩后放_任意_任意')
    - Signal('60分钟_D1W5_窗口能量V2_先放后缩_任意_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param w: 观察窗口大小
    """
    k1, k2, k3 = f"{freq}_D{di}W{w}_窗口能量V2".split("_")
    if len(bars_raw) < di + w:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = [b.volume for b in bars_raw[-(di + w - 1):] if hasattr(b, 'volume')][-w:]
    if len(vols) < w:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    min_i = vols.index(min(vols))
    max_i = vols.index(max(vols))
    v1 = "先放后缩" if min_i > max_i else "先缩后放"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_break(freq: str, bars_raw: list, di: int = 1,
              n: int = 20, threshold: float = 2.0,
              **kwargs) -> OrderedDict:
    """放量突破信号

    参数模板："{freq}_D{di}放量突破N{n}"

    信号逻辑：
    当前成交量突破均量的threshold倍

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 均量计算周期
    :param threshold: 突破倍数
    """
    k1, k2, k3 = f"{freq}_D{di}放量突破N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(vols) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    avg_vol = np.mean(vols[:-1])
    if avg_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = vols[-1] / avg_vol
    v1 = "放量突破" if ratio >= threshold else "未突破"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_shrink(freq: str, bars_raw: list, di: int = 1,
               n: int = 5, threshold: float = 0.5,
               **kwargs) -> OrderedDict:
    """缩量信号

    参数模板："{freq}_D{di}缩量N{n}"

    信号逻辑：
    连续n根K线缩量

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 连续K线数量
    :param threshold: 缩量阈值（当前量/前量 < threshold）
    """
    k1, k2, k3 = f"{freq}_D{di}缩量N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(vols) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    shrink_count = sum(1 for i in range(1, len(vols)) if vols[i] < vols[i - 1] * threshold)

    if shrink_count >= n - 1:
        v1 = "持续缩量"
    elif shrink_count >= n // 2:
        v1 = "部分缩量"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_ratio_signal(freq: str, bars_raw: list, di: int = 1,
                     n: int = 5, **kwargs) -> OrderedDict:
    """量比信号

    参数模板："{freq}_D{di}量比N{n}"

    信号逻辑：
    当前成交量与n根K线平均成交量的比值

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 均量计算周期
    """
    k1, k2, k3 = f"{freq}_D{di}量比N{n}".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n + di - 1):] if di == 1 else bars_raw[-(n + di):-di + 1]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(vols) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    avg_vol = np.mean(vols[:-1])
    if avg_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = vols[-1] / avg_vol
    if ratio > 3:
        v1 = "巨量"
    elif ratio > 2:
        v1 = "大量"
    elif ratio > 1:
        v1 = "放量"
    elif ratio > 0.7:
        v1 = "正常"
    elif ratio > 0.3:
        v1 = "缩量"
    else:
        v1 = "地量"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_price_divergence(freq: str, bars_raw: list, di: int = 1,
                         n: int = 10, **kwargs) -> OrderedDict:
    """量价背离信号

    参数模板："{freq}_D{di}量价背离N{n}"

    信号逻辑：
    价格创新高但成交量未创新高 → 量价顶背离
    价格创新低但成交量未创新低 → 量价底背离

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}量价背离N{n}".split("_")
    if len(bars_raw) < n * 2 + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-(n * 2 + di - 1):] if di == 1 else bars_raw[-(n * 2 + di):-di + 1]
    if len(recent) < n * 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    closes = [b.close for b in recent if hasattr(b, 'close')]
    vols = [b.volume for b in recent if hasattr(b, 'volume')]

    if len(closes) < n * 2 or len(vols) < n * 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 前半段和后半段
    first_close = closes[:n]
    second_close = closes[n:]
    first_vol = vols[:n]
    second_vol = vols[n:]

    price_new_high = max(second_close) > max(first_close)
    price_new_low = min(second_close) < min(first_close)
    vol_new_high = max(second_vol) > max(first_vol)
    vol_new_low = min(second_vol) < min(first_vol)

    if price_new_high and not vol_new_high:
        v1 = "量价顶背离"
    elif price_new_low and not vol_new_low:
        v1 = "量价底背离"
    else:
        v1 = "量价配合"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_vwap(freq: str, bars_raw: list, di: int = 1,
             **kwargs) -> OrderedDict:
    """VWAP信号

    参数模板："{freq}_D{di}_VWAP"

    信号逻辑：
    成交量加权平均价格与当前价格的比较

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}_VWAP".split("_")
    if len(bars_raw) < di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent = bars_raw[-di:] if di == 1 else bars_raw[-di:-di + 1]
    if not recent:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 简化VWAP计算：使用全部数据
    typical_prices = [(b.high + b.low + b.close) / 3 for b in bars_raw if hasattr(b, 'close')]
    volumes = [b.volume for b in bars_raw if hasattr(b, 'volume')]

    total_vol = sum(volumes)
    if total_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vwap = sum(tp * v for tp, v in zip(typical_prices, volumes)) / total_vol
    current = recent[-1].close if hasattr(recent[-1], 'close') else 0

    if vwap == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (current - vwap) / vwap * 100
    if pct > 2:
        v1 = "VWAP上方"
    elif pct > 0:
        v1 = "VWAP略上方"
    elif pct > -2:
        v1 = "VWAP略下方"
    else:
        v1 = "VWAP下方"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_pvt_signal(freq: str, bars_raw: list, di: int = 1,
                   n: int = 20, **kwargs) -> OrderedDict:
    """PVT价量趋势信号

    参数模板："{freq}_D{di}PVTN{n}_价量趋势"

    信号逻辑：
    PVT上升多头，PVT下降空头

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 均线周期
    """
    k1, k2, k3 = f"{freq}_D{di}PVTN{n}_价量趋势".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    volume = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])

    # PVT计算
    pct_change = np.diff(close) / (close[:-1] + 1e-10)
    pvt = np.cumsum(pct_change * volume[1:])
    pvt = np.concatenate([[0], pvt])
    pvt_ma = pd.Series(pvt).rolling(n).mean().values

    idx = len(close) - di
    if np.isnan(pvt_ma[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if pvt[idx] > pvt_ma[idx]:
        v1 = "多头"
    else:
        v1 = "空头"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_mfi_signal(freq: str, bars_raw: list, di: int = 1,
                   period: int = 14, **kwargs) -> OrderedDict:
    """MFI资金流量信号

    参数模板："{freq}_D{di}MFI{period}_资金流量"

    信号逻辑：
    MFI > 80 超买，MFI < 20 超卖

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param period: MFI周期
    """
    k1, k2, k3 = f"{freq}_D{di}MFI{period}_资金流量".split("_")
    if len(bars_raw) < period + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    lows = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    closes = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    volumes = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])

    # MFI计算
    tp = (highs + lows + closes) / 3
    mf = tp * volumes

    positive_mf = np.zeros(len(mf))
    negative_mf = np.zeros(len(mf))
    for i in range(1, len(mf)):
        if tp[i] > tp[i - 1]:
            positive_mf[i] = mf[i]
        else:
            negative_mf[i] = mf[i]

    pos_sum = pd.Series(positive_mf).rolling(period).sum()
    neg_sum = pd.Series(negative_mf).rolling(period).sum()
    mfi = 100 - 100 / (1 + pos_sum / (neg_sum + 1e-10))

    idx = len(closes) - di
    if np.isnan(mfi[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    val = mfi[idx]
    if val > 80:
        v1 = "超买"
    elif val > 60:
        v1 = "偏多"
    elif val > 40:
        v1 = "中性"
    elif val > 20:
        v1 = "偏空"
    else:
        v1 = "超卖"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_volatility_ratio(freq: str, bars_raw: list, di: int = 1,
                         n: int = 20, **kwargs) -> OrderedDict:
    """量波动率信号

    参数模板："{freq}_D{di}VVOLN{n}_量波动率"

    信号逻辑：
    成交量自身的波动率

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}VVOLN{n}_量波动率".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])
    idx = len(vols) - di

    vol_series = pd.Series(vols[idx - n + 1:idx + 1])
    vol_mean = vol_series.mean()
    vol_std = vol_series.std()

    if vol_mean == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    cv = vol_std / vol_mean
    if cv > 0.8:
        v1 = "量极不稳定"
    elif cv > 0.5:
        v1 = "量波动较大"
    elif cv > 0.3:
        v1 = "量波动正常"
    else:
        v1 = "量波动较小"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def vol_adi_signal(freq: str, bars_raw: list, di: int = 1,
                   n: int = 20, **kwargs) -> OrderedDict:
    """ADI累积离差指标信号

    参数模板："{freq}_D{di}ADIN{n}_累积离差"

    信号逻辑：
    ADI上升资金流入，ADI下降资金流出

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 均线周期
    """
    k1, k2, k3 = f"{freq}_D{di}ADIN{n}_累积离差".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    high = np.array([b.high for b in bars_raw if hasattr(b, 'high')])
    low = np.array([b.low for b in bars_raw if hasattr(b, 'low')])
    volume = np.array([b.volume for b in bars_raw if hasattr(b, 'volume')])

    # ADI计算
    clv = ((close - low) - (high - close)) / (high - low + 1e-10)
    adi = np.cumsum(clv * volume)
    adi_ma = pd.Series(adi).rolling(n).mean().values

    idx = len(close) - di
    if np.isnan(adi_ma[idx]):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if adi[idx] > adi_ma[idx]:
        v1 = "资金流入"
    else:
        v1 = "资金流出"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
