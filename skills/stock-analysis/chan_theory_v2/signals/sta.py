#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计信号 (sta = Statistics)

参考 czsc.signals.sta 的设计，实现基于统计特征的信号函数。
利用统计方法（均值回归、波动率聚类、自相关等）识别市场状态。

信号列表：
1.  sta_mean_revert      - 均值回归信号
2.  sta_volatility       - 波动率状态信号
3.  sta_vol_ratio        - 波动率比率信号
4.  sta_autocorr         - 自相关信号
5.  sta_skewness         - 偏度信号
6.  sta_kurtosis         - 峰度信号
7.  sta_hurst            - 赫斯特指数信号
8.  sta_z_score          - Z-Score信号
9.  sta_percentile       - 百分位信号
10. sta_regime           - 市场状态信号
11. sta_consecutive      - 连续涨跌信号
12. sta_momentum_roc     - 动量ROC信号
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from collections import OrderedDict

from .cxt import create_single_signal


def _calc_returns(close: np.ndarray) -> np.ndarray:
    """计算收益率"""
    returns = np.diff(close) / close[:-1]
    return np.concatenate([[0], returns])


def sta_mean_revert(freq: str, bars_raw: list, di: int = 1,
                    n: int = 20, **kwargs) -> OrderedDict:
    """均值回归信号

    参数模板："{freq}_D{di}MRN{n}_均值回归"

    信号逻辑：
    价格偏离均值过多时倾向于回归

    信号列表：
    - Signal('15分钟_D1MRN20_均值回归_超买_任意')
    - Signal('15分钟_D1MRN20_均值回归_超卖_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 均值计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}MRN{n}_均值回归".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    z_score = (close[idx] - mean) / std
    if z_score > 2:
        v1 = "超买"
    elif z_score > 1:
        v1 = "偏多"
    elif z_score > -1:
        v1 = "中性"
    elif z_score > -2:
        v1 = "偏空"
    else:
        v1 = "超卖"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_volatility(freq: str, bars_raw: list, di: int = 1,
                   n: int = 20, **kwargs) -> OrderedDict:
    """波动率状态信号

    参数模板："{freq}_D{di}VOLN{n}_波动率"

    信号逻辑：
    根据收益率的标准差判断当前波动率水平

    信号列表：
    - Signal('15分钟_D1VOLN20_波动率_高波_任意')
    - Signal('15分钟_D1VOLN20_波动率_低波_任意')

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}VOLN{n}_波动率".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    returns = _calc_returns(close[idx - n:idx + 1])

    if len(returns) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vol = np.std(returns)
    # 长期波动率对比
    long_returns = _calc_returns(close[max(0, idx - n * 3):idx + 1])
    long_vol = np.std(long_returns) if len(long_returns) > n else vol

    if long_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = vol / long_vol
    if ratio > 1.5:
        v1 = "高波"
    elif ratio > 1.2:
        v1 = "波率上升"
    elif ratio > 0.8:
        v1 = "正常波率"
    elif ratio > 0.5:
        v1 = "波率下降"
    else:
        v1 = "低波"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_vol_ratio(freq: str, bars_raw: list, di: int = 1,
                  fast: int = 5, slow: int = 20,
                  **kwargs) -> OrderedDict:
    """波动率比率信号

    参数模板："{freq}_D{di}VRF{fast}S{slow}_波动率比"

    信号逻辑：
    短期波动率与长期波动率的比率

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}VRF{fast}S{slow}_波动率比".split("_")
    if len(bars_raw) < slow + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    returns = _calc_returns(close)

    fast_vol = np.std(returns[idx - fast:idx + 1]) if idx >= fast else 0
    slow_vol = np.std(returns[idx - slow:idx + 1]) if idx >= slow else 0

    if slow_vol == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = fast_vol / slow_vol
    if ratio > 1.5:
        v1 = "波动扩大"
    elif ratio > 1.0:
        v1 = "波动略增"
    elif ratio > 0.7:
        v1 = "波动平稳"
    else:
        v1 = "波动收窄"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_autocorr(freq: str, bars_raw: list, di: int = 1,
                 n: int = 20, lag: int = 1,
                 **kwargs) -> OrderedDict:
    """自相关信号

    参数模板："{freq}_D{di}ACN{n}L{lag}_自相关"

    信号逻辑：
    收益率的自相关系数反映趋势性/均值回归性

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    :param lag: 滞后期数
    """
    k1, k2, k3 = f"{freq}_D{di}ACN{n}L{lag}_自相关".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    returns = _calc_returns(close[idx - n:idx + 1])

    if len(returns) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    try:
        ac = pd.Series(returns).autocorr(lag=lag)
        if np.isnan(ac):
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if ac > 0.3:
        v1 = "正相关"
    elif ac > 0.1:
        v1 = "弱正相关"
    elif ac > -0.1:
        v1 = "不相关"
    elif ac > -0.3:
        v1 = "弱负相关"
    else:
        v1 = "负相关"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_skewness(freq: str, bars_raw: list, di: int = 1,
                 n: int = 30, **kwargs) -> OrderedDict:
    """偏度信号

    参数模板："{freq}_D{di}SKWN{n}_偏度"

    信号逻辑：
    收益率偏度反映分布的不对称性

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}SKWN{n}_偏度".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    returns = _calc_returns(close[idx - n:idx + 1])

    if len(returns) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    try:
        sk = pd.Series(returns).skew()
        if np.isnan(sk):
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if sk > 1:
        v1 = "右偏极强"
    elif sk > 0.5:
        v1 = "右偏"
    elif sk > -0.5:
        v1 = "对称"
    elif sk > -1:
        v1 = "左偏"
    else:
        v1 = "左偏极强"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_kurtosis(freq: str, bars_raw: list, di: int = 1,
                 n: int = 30, **kwargs) -> OrderedDict:
    """峰度信号

    参数模板："{freq}_D{di}KURT{n}_峰度"

    信号逻辑：
    收益率峰度反映尾部风险

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}KURT{n}_峰度".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    returns = _calc_returns(close[idx - n:idx + 1])

    if len(returns) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    try:
        kurt = pd.Series(returns).kurtosis()
        if np.isnan(kurt):
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 超额峰度：正态分布为0
    if kurt > 5:
        v1 = "尖峰厚尾"
    elif kurt > 2:
        v1 = "轻厚尾"
    elif kurt > -1:
        v1 = "近似正态"
    else:
        v1 = "平坦薄尾"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_hurst(freq: str, bars_raw: list, di: int = 1,
              n: int = 100, **kwargs) -> OrderedDict:
    """赫斯特指数信号

    参数模板："{freq}_D{di}HURST{n}_长期记忆"

    信号逻辑：
    H > 0.5 趋势持续，H < 0.5 均值回归，H ≈ 0.5 随机游走

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}HURST{n}_长期记忆".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n + 1:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # R/S法计算赫斯特指数
    try:
        returns = np.diff(np.log(window))
        max_k = min(20, len(returns) // 2)
        if max_k < 5:
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

        rs_list = []
        ns = []
        for k in range(5, max_k + 1):
            m = len(returns) // k
            if m < 1:
                continue
            rs = []
            for i in range(k):
                chunk = returns[i * m:(i + 1) * m]
                if len(chunk) < 2:
                    continue
                mean_chunk = np.mean(chunk)
                cumsum = np.cumsum(chunk - mean_chunk)
                r = np.max(cumsum) - np.min(cumsum)
                s = np.std(chunk)
                if s > 0:
                    rs.append(r / s)
            if rs:
                rs_list.append(np.log(np.mean(rs)))
                ns.append(np.log(k * m / len(returns) * len(returns)))

        if len(ns) < 3:
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

        h = np.polyfit(ns, rs_list, 1)[0]
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if h > 0.6:
        v1 = "趋势持续"
    elif h > 0.5:
        v1 = "弱趋势"
    elif h > 0.4:
        v1 = "随机游走"
    else:
        v1 = "均值回归"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_z_score(freq: str, bars_raw: list, di: int = 1,
                n: int = 20, **kwargs) -> OrderedDict:
    """Z-Score信号

    参数模板："{freq}_D{di}ZSN{n}_Z分数"

    信号逻辑：
    当前价格的Z-Score（标准化分数）

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}ZSN{n}_Z分数".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n + 1:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    z = (close[idx] - mean) / std
    if z > 2:
        v1 = "Z>2"
    elif z > 1:
        v1 = "Z>1"
    elif z > 0:
        v1 = "0<Z<1"
    elif z > -1:
        v1 = "-1<Z<0"
    elif z > -2:
        v1 = "Z<-1"
    else:
        v1 = "Z<-2"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_percentile(freq: str, bars_raw: list, di: int = 1,
                   n: int = 60, **kwargs) -> OrderedDict:
    """百分位信号

    参数模板："{freq}_D{di}PCTN{n}_百分位"

    信号逻辑：
    当前价格在n根K线中的百分位

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}PCTN{n}_百分位".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n + 1:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = np.sum(window < close[idx]) / len(window) * 100
    if pct > 90:
        v1 = "极高百分位"
    elif pct > 70:
        v1 = "高百分位"
    elif pct > 30:
        v1 = "中百分位"
    elif pct > 10:
        v1 = "低百分位"
    else:
        v1 = "极低百分位"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_regime(freq: str, bars_raw: list, di: int = 1,
               n: int = 60, **kwargs) -> OrderedDict:
    """市场状态信号

    参数模板："{freq}_D{di}REGIMEN{n}_市场状态"

    信号逻辑：
    综合波动率和趋势判断市场状态

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 计算窗口
    """
    k1, k2, k3 = f"{freq}_D{di}REGIMEN{n}_市场状态".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n + 1:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 趋势强度
    x = np.arange(len(window))
    try:
        slope = np.polyfit(x, window, 1)[0]
        trend_pct = slope / np.mean(window) * 100
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 波动率
    returns = _calc_returns(window)
    vol = np.std(returns) * 100

    if abs(trend_pct) > 2 and vol < 2:
        v1 = "低波趋势"
    elif abs(trend_pct) > 2 and vol >= 2:
        v1 = "高波趋势"
    elif abs(trend_pct) <= 2 and vol < 1.5:
        v1 = "低波盘整"
    else:
        v1 = "高波盘整"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_consecutive(freq: str, bars_raw: list, di: int = 1,
                    n: int = 10, **kwargs) -> OrderedDict:
    """连续涨跌信号

    参数模板："{freq}_D{di}CONSN{n}_连续涨跌"

    信号逻辑：
    统计最近n根K线中连续上涨/下跌的次数

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 观察窗口
    """
    k1, k2, k3 = f"{freq}_D{di}CONSN{n}_连续涨跌".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di
    window = close[idx - n:idx + 1]

    if len(window) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 当前连续涨/跌
    consec = 0
    direction = 0
    for i in range(len(window) - 1, 0, -1):
        if window[i] > window[i - 1]:
            if direction == 0:
                direction = 1
                consec = 1
            elif direction == 1:
                consec += 1
            else:
                break
        elif window[i] < window[i - 1]:
            if direction == 0:
                direction = -1
                consec = 1
            elif direction == -1:
                consec += 1
            else:
                break
        else:
            break

    if direction > 0:
        v1 = f"连涨{consec}"
    elif direction < 0:
        v1 = f"连跌{consec}"
    else:
        v1 = "无连续"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def sta_momentum_roc(freq: str, bars_raw: list, di: int = 1,
                     n: int = 12, **kwargs) -> OrderedDict:
    """动量ROC信号

    参数模板："{freq}_D{di}ROCN{n}_动量"

    信号逻辑：
    变动率指标(ROC)，当前价格与n根K线前的价格变动百分比

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 回溯周期
    """
    k1, k2, k3 = f"{freq}_D{di}ROCN{n}_动量".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    idx = len(close) - di

    if close[idx - n] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    roc = (close[idx] - close[idx - n]) / close[idx - n] * 100
    if roc > 10:
        v1 = "强多"
    elif roc > 3:
        v1 = "偏多"
    elif roc > -3:
        v1 = "中性"
    elif roc > -10:
        v1 = "偏空"
    else:
        v1 = "强空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
