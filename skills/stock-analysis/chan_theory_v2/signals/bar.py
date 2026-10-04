#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K线基础信号 (bar)

参考 czsc.signals.bar 的设计，实现基于裸K线的信号函数。

信号列表：
1.  bar_single_trend      - 单K趋势信号
2.  bar_triple_accelerate - 三K加速信号
3.  bar_accelerate        - 加速形态信号
4.  bar_reversal          - 反转形态信号
5.  bar_fake_break        - 假突破信号
6.  bar_channel           - 通道信号
7.  bar_zdf               - 涨跌幅信号
8.  bar_vol_grow          - 成交量增长信号
9.  bar_mean_amount       - 均额信号
10. bar_section_momentum  - 截面动量信号
11. bar_zt_count          - 涨停统计信号
12. bar_big_solid         - 大实体信号
13. bar_shuang_fei        - 双飞信号
14. bar_limit_down        - 跌停信号
15. bar_bpm               - BPM信号
16. bar_r_breaker         - R-Breaker信号
17. bar_dual_thrust       - Dual Thrust信号
18. bar_tnr               - TNR信号
19. bar_amount_acc        - 成交额累积信号
20. bar_operate_span      - 操作区间信号
"""

import numpy as np
import pandas as pd
from typing import List, Optional
from collections import OrderedDict

from .cxt import create_single_signal, get_sub_elements


def _get_bar_attrs(bars: list, n: int, di: int = 1):
    """获取最近n根K线的属性"""
    recent = bars[-(n + di - 1):] if di == 1 else bars[-(n + di):-di + 1]
    if len(recent) < n:
        return None

    opens = [b.open if hasattr(b, 'open') else 0 for b in recent]
    highs = [b.high if hasattr(b, 'high') else 0 for b in recent]
    lows = [b.low if hasattr(b, 'low') else 0 for b in recent]
    closes = [b.close if hasattr(b, 'close') else 0 for b in recent]
    vols = [b.volume if hasattr(b, 'volume') else 0 for b in recent]

    # 计算实体和影线
    solids = [abs(c - o) for c, o in zip(closes, opens)]
    uppers = [h - max(c, o) for h, c, o in zip(highs, closes, opens)]
    lowers = [min(c, o) - l for c, o, l in zip(closes, opens, lows)]

    return {
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': vols,
        'solid': solids, 'upper': uppers, 'lower': lowers,
    }


def bar_single_trend(freq: str, bars_raw: list, di: int = 1,
                     n: int = 5, **kwargs) -> OrderedDict:
    """单K趋势信号

    参数模板："{freq}_D{di}单K趋势N{n}"

    信号逻辑：
    计算最近K线的趋势因子（涨幅/成交量），分层判断

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param n: 分层数
    """
    k1, k2, k3 = f"{freq}_D{di}单K趋势N{n}".split("_")
    if len(bars_raw) < 100 + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bars = bars_raw[-(100 + di):-di + 1] if di > 1 else bars_raw[-100:]
    factors = []
    for b in bars:
        if hasattr(b, 'close') and hasattr(b, 'open') and hasattr(b, 'volume') and b.volume > 0:
            factors.append((b.close / b.open - 1) / b.volume)

    if len(factors) < 50:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    try:
        q = pd.qcut(factors, n, labels=list(range(1, n + 1)), duplicates='drop')
        layer = q.iloc[-1]
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    v1 = f"第{layer}层"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_triple_accelerate(freq: str, bars_raw: list, di: int = 1,
                          **kwargs) -> OrderedDict:
    """三K加速信号

    参数模板："{freq}_D{di}三K加速_裸K形态"

    信号逻辑：
    1. 三连涨 + 高低点创新高 → 新高涨
    2. 三连跌 + 高低点创新低 → 新低跌
    3. 加入量能变化判断

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}三K加速_裸K形态".split("_")
    if len(bars_raw) < 7 + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a = _get_bar_attrs(bars_raw, 3, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    b3_close, b2_close, b1_close = a['close']
    b3_open, b2_open, b1_open = a['open']
    b3_high, b2_high, b1_high = a['high']
    b3_low, b2_low, b1_low = a['low']

    v1 = "其他"
    if b1_close > b1_open and b2_close > b2_open and b3_close > b3_open:
        v1 = "三连涨"
        if b1_high > b2_high > b3_high and b1_low > b2_low > b3_low:
            v1 = "新高涨"
    elif b1_close < b1_open and b2_close < b2_open and b3_close < b3_open:
        v1 = "三连跌"
        if b1_high < b2_high < b3_high and b1_low < b2_low < b3_low:
            v1 = "新低跌"

    if v1 == "其他":
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)

    v1_vol = a['volume']
    if v1_vol[-1] > v1_vol[-2] > v1_vol[-3]:
        v2 = "依次放量"
    elif v1_vol[-1] < v1_vol[-2] < v1_vol[-3]:
        v2 = "依次缩量"
    else:
        v2 = "量柱无序"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def bar_accelerate(freq: str, bars_raw: list, di: int = 1,
                   n: int = 5, **kwargs) -> OrderedDict:
    """加速形态信号

    参数模板："{freq}_D{di}加速N{n}_裸K形态"

    信号逻辑：
    最近n根K线的实体逐渐增大

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}加速N{n}_裸K形态".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    solids = a['solid']
    closes = a['close']
    opens = a['open']

    is_up = closes[-1] > opens[-1]
    solids_increasing = all(solids[i] < solids[i + 1] for i in range(len(solids) - 1))

    if solids_increasing and is_up:
        v1 = "加速上涨"
    elif solids_increasing and not is_up:
        v1 = "加速下跌"
    elif not solids_increasing and is_up:
        v1 = "减速上涨"
    else:
        v1 = "减速下跌"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_reversal(freq: str, bars_raw: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """反转形态信号

    参数模板："{freq}_D{di}反转_裸K形态"

    信号逻辑：
    大实体K线方向反转

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}反转_裸K形态".split("_")
    a = _get_bar_attrs(bars_raw, 3, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    prev_up = a['close'][-2] > a['open'][-2]
    curr_up = a['close'][-1] > a['open'][-1]
    curr_solid = a['solid'][-1]
    avg_solid = np.mean(a['solid'])

    if prev_up and not curr_up and curr_solid > avg_solid * 1.5:
        v1 = "顶反转"
    elif not prev_up and curr_up and curr_solid > avg_solid * 1.5:
        v1 = "底反转"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_fake_break(freq: str, bars_raw: list, di: int = 1,
                   n: int = 20, **kwargs) -> OrderedDict:
    """假突破信号

    参数模板："{freq}_D{di}假突破N{n}"

    信号逻辑：
    价格突破前高/前低后又回到区间内

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}假突破N{n}_FKBRK".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a = _get_bar_attrs(bars_raw, n + 1, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    prev_high = max(a['high'][:-1])
    prev_low = min(a['low'][:-1])
    curr_high = a['high'][-1]
    curr_close = a['close'][-1]

    if curr_high > prev_high and curr_close < prev_high:
        v1 = "向上假突破"
    elif a['low'][-1] < prev_low and curr_close > prev_low:
        v1 = "向下假突破"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_channel(freq: str, bars_raw: list, di: int = 1,
                n: int = 20, **kwargs) -> OrderedDict:
    """通道信号

    参数模板："{freq}_D{di}通道N{n}"

    信号逻辑：
    价格在n根K线形成的通道中的位置

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}通道N{n}_CH".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ch_high = max(a['high'])
    ch_low = min(a['low'])
    ch_range = ch_high - ch_low

    if ch_range == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    position = (a['close'][-1] - ch_low) / ch_range
    if position > 0.8:
        v1 = "上轨附近"
    elif position < 0.2:
        v1 = "下轨附近"
    else:
        v1 = "通道中部"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_zdf(freq: str, bars_raw: list, di: int = 1,
            **kwargs) -> OrderedDict:
    """涨跌幅信号

    参数模板："{freq}_D{di}K_涨跌幅"

    信号逻辑：
    最近一根K线的涨跌幅

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}K_涨跌幅".split("_")
    a = _get_bar_attrs(bars_raw, 1, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if a['open'][-1] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (a['close'][-1] - a['open'][-1]) / a['open'][-1] * 100
    if pct > 5:
        v1 = "大涨"
    elif pct > 2:
        v1 = "上涨"
    elif pct > -2:
        v1 = "横盘"
    elif pct > -5:
        v1 = "下跌"
    else:
        v1 = "大跌"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_vol_grow(freq: str, bars_raw: list, di: int = 1,
                 n: int = 5, **kwargs) -> OrderedDict:
    """成交量增长信号

    参数模板："{freq}_D{di}量增N{n}"

    信号逻辑：
    成交量是否连续增长

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}量增N{n}_VG".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    vols = a['volume']
    is_growing = all(vols[i] < vols[i + 1] for i in range(len(vols) - 1))

    v1 = "连续放量" if is_growing else "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_mean_amount(freq: str, bars_raw: list, di: int = 1,
                    n: int = 20, **kwargs) -> OrderedDict:
    """均额信号

    参数模板："{freq}_D{di}均额N{n}"

    信号逻辑：
    最近成交额相对均额的比例

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}均额N{n}_MA".split("_")
    if len(bars_raw) < n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    amounts = [c * v for c, v in zip(a['close'], a['volume'])]
    avg_amount = np.mean(amounts[:-1])
    if avg_amount == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = amounts[-1] / avg_amount
    if ratio > 3:
        v1 = "巨量"
    elif ratio > 2:
        v1 = "大量"
    elif ratio > 1:
        v1 = "放量"
    else:
        v1 = "缩量"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_section_momentum(freq: str, bars_raw: list, di: int = 1,
                         n: int = 20, **kwargs) -> OrderedDict:
    """截面动量信号

    参数模板："{freq}_D{di}动量N{n}"

    信号逻辑：
    最近n根K线的累计涨跌幅

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}动量N{n}_MTM".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None or a['close'][0] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (a['close'][-1] - a['close'][0]) / a['close'][0] * 100
    if pct > 10:
        v1 = "强多"
    elif pct > 3:
        v1 = "偏多"
    elif pct > -3:
        v1 = "中性"
    elif pct > -10:
        v1 = "偏空"
    else:
        v1 = "强空"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_zt_count(freq: str, bars_raw: list, di: int = 1,
                 n: int = 20, zt_threshold: float = 9.5,
                 **kwargs) -> OrderedDict:
    """涨停统计信号

    参数模板："{freq}_D{di}涨停N{n}"

    信号逻辑：
    统计最近n根K线中涨停的次数

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    :param zt_threshold: 涨停阈值（百分比）
    """
    k1, k2, k3 = f"{freq}_D{di}涨停N{n}_ZT".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    zt_count = 0
    for o, c in zip(a['open'], a['close']):
        if o > 0 and (c - o) / o * 100 >= zt_threshold:
            zt_count += 1

    v1 = f"{zt_count}次涨停"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_big_solid(freq: str, bars_raw: list, di: int = 1,
                  threshold: float = 0.03, **kwargs) -> OrderedDict:
    """大实体信号

    参数模板："{freq}_D{di}大实体"

    信号逻辑：
    判断K线实体大小

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}大实体_BGS".split("_")
    a = _get_bar_attrs(bars_raw, 1, di)
    if a is None or a['close'][-1] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    solid_ratio = a['solid'][-1] / a['close'][-1]
    is_up = a['close'][-1] > a['open'][-1]

    if solid_ratio > threshold * 2:
        v1 = "超大阳" if is_up else "超大阴"
    elif solid_ratio > threshold:
        v1 = "大阳" if is_up else "大阴"
    elif solid_ratio < threshold * 0.3:
        v1 = "十字星"
    else:
        v1 = "小阳" if is_up else "小阴"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_shuang_fei(freq: str, bars_raw: list, di: int = 1,
                   **kwargs) -> OrderedDict:
    """双飞信号（跳空缺口）

    参数模板："{freq}_D{di}双飞"

    信号逻辑：
    相邻两根K线出现跳空缺口

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}双飞_GAP".split("_")
    a = _get_bar_attrs(bars_raw, 2, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if a['low'][-1] > a['high'][-2]:
        v1 = "向上跳空"
    elif a['high'][-1] < a['low'][-2]:
        v1 = "向下跳空"
    else:
        v1 = "无缺口"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_limit_down(freq: str, bars_raw: list, di: int = 1,
                   threshold: float = -9.5, **kwargs) -> OrderedDict:
    """跌停信号

    参数模板："{freq}_D{di}跌停"

    信号逻辑：
    检测是否跌停

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}跌停_LDT".split("_")
    a = _get_bar_attrs(bars_raw, 1, di)
    if a is None or a['open'][-1] == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (a['close'][-1] - a['open'][-1]) / a['open'][-1] * 100
    v1 = "跌停" if pct <= threshold else "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_bpm(freq: str, bars_raw: list, di: int = 1,
            n: int = 5, **kwargs) -> OrderedDict:
    """BPM信号（大实体占比）

    参数模板："{freq}_D{di}BPMN{n}"

    信号逻辑：
    最近n根K线中大实体K线的占比

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}BPMN{n}".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    big_count = sum(1 for s, c in zip(a['solid'], a['close']) if c > 0 and s / c > 0.02)
    ratio = big_count / n if n > 0 else 0

    if ratio > 0.6:
        v1 = "高波动"
    elif ratio > 0.3:
        v1 = "中波动"
    else:
        v1 = "低波动"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_r_breaker(freq: str, bars_raw: list, di: int = 1,
                  n: int = 10, **kwargs) -> OrderedDict:
    """R-Breaker信号

    参数模板："{freq}_D{di}RBreakerN{n}"

    信号逻辑：
    基于前日高低价计算突破价位

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}RBreakerN{n}".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None or len(a['high']) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    hh = max(a['high'])
    ll = min(a['low'])
    last_close = a['close'][-1]

    # R-Breaker关键价位
    pivot = (hh + ll + last_close) / 3
    s1 = 2 * pivot - hh
    r1 = 2 * pivot - ll

    current = a['close'][-1]
    if current > r1:
        v1 = "突破买入"
    elif current < s1:
        v1 = "突破卖出"
    else:
        v1 = "区间内"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_dual_thrust(freq: str, bars_raw: list, di: int = 1,
                    n: int = 4, k1_val: float = 0.5,
                    k2_val: float = 0.5, **kwargs) -> OrderedDict:
    """Dual Thrust信号

    参数模板："{freq}_D{di}DualThrustN{n}"

    信号逻辑：
    基于前n日的Range计算上下轨

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1_name, k2_name, k3_name = f"{freq}_D{di}DualThrustN{n}".split("_")
    a = _get_bar_attrs(bars_raw, n, di)
    if a is None or len(a['high']) < 2:
        return create_single_signal(k1=k1_name, k2=k2_name, k3=k3_name, v1="其他")

    hh = max(a['high'])
    hc = max(a['close'])
    lc = min(a['close'])
    ll = min(a['low'])

    range_val = max(hh - lc, hc - ll)
    open_price = a['open'][-1]
    close_price = a['close'][-1]

    upper = open_price + k1_val * range_val
    lower = open_price - k2_val * range_val

    if close_price > upper:
        v1 = "看多"
    elif close_price < lower:
        v1 = "看空"
    else:
        v1 = "中性"
    return create_single_signal(k1=k1_name, k2=k2_name, k3=k3_name, v1=v1)


def bar_tnr(freq: str, bars_raw: list, di: int = 1,
            n: int = 10, **kwargs) -> OrderedDict:
    """TNR信号（真实波幅比率）

    参数模板："{freq}_D{di}TNRN{n}"

    信号逻辑：
    当前K线的真实波幅占最近n日平均真实波幅的比率

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}TNRN{n}".split("_")
    if len(bars_raw) < n + di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a = _get_bar_attrs(bars_raw, n + 1, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    trs = []
    for i in range(1, len(a['high'])):
        tr = max(
            a['high'][i] - a['low'][i],
            abs(a['high'][i] - a['close'][i - 1]),
            abs(a['low'][i] - a['close'][i - 1])
        )
        trs.append(tr)

    if len(trs) < 2 or np.mean(trs[:-1]) == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    avg_tr = np.mean(trs[:-1])
    current_tr = trs[-1]
    ratio = current_tr / avg_tr

    if ratio > 2:
        v1 = "异常波动"
    elif ratio > 1.5:
        v1 = "高波动"
    elif ratio < 0.5:
        v1 = "低波动"
    else:
        v1 = "正常波动"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_amount_acc(freq: str, bars_raw: list, di: int = 1,
                   n: int = 5, **kwargs) -> OrderedDict:
    """成交额累积信号

    参数模板："{freq}_D{di}额累N{n}"

    信号逻辑：
    最近n根K线成交额累计与前n根的比较

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}额累N{n}".split("_")
    if len(bars_raw) < 2 * n + di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    a1 = _get_bar_attrs(bars_raw, n, di)
    a2 = _get_bar_attrs(bars_raw[-(2 * n + di - 1):-(n + di - 1)] if di > 1 else bars_raw[-2 * n:-n], n)
    if a1 is None or a2 is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    amt1 = sum(c * v for c, v in zip(a1['close'], a1['volume']))
    amt2 = sum(c * v for c, v in zip(a2['close'], a2['volume']))

    if amt2 == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    ratio = amt1 / amt2
    if ratio > 2:
        v1 = "显著放量"
    elif ratio > 1.2:
        v1 = "温和放量"
    elif ratio > 0.8:
        v1 = "持平"
    else:
        v1 = "缩量"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def bar_operate_span(freq: str, bars_raw: list, di: int = 1,
                     **kwargs) -> OrderedDict:
    """操作区间信号

    参数模板："{freq}_D{di}操作区间"

    信号逻辑：
    判断当前K线是否适合操作（非集合竞价等）

    :param freq: 周期名称
    :param bars_raw: K线列表
    :param di: 倒数第di根K线
    """
    k1, k2, k3 = f"{freq}_D{di}操作区间_SP".split("_")
    a = _get_bar_attrs(bars_raw, 1, di)
    if a is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if a['close'][-1] > a['open'][-1] and a['volume'][-1] > 0:
        v1 = "可操作"
    elif a['close'][-1] < a['open'][-1] and a['volume'][-1] > 0:
        v1 = "可操作"
    else:
        v1 = "不可操作"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
