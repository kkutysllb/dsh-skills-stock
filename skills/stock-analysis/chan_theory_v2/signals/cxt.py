#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论形态信号 (cxt = Chan Xing Tai)

参考 czsc.signals.cxt 的设计，实现基于缠论形态学的信号函数。
所有信号返回 OrderedDict，格式为 {signal_key: signal_value}。

信号命名规范：{freq}_{信号标识}_{信号子类}
信号值格式：v1_v2_v3

信号列表：
1. cxt_bi_base        - 笔基础信号（方向+状态）
2. cxt_fx_power       - 分型强弱信号
3. cxt_bi_end         - 笔结束信号
4. cxt_bi_status      - 笔状态信号（延伸长度）
5. cxt_bi_trend       - 笔趋势信号
6. cxt_bi_zdf         - 笔涨跌幅信号
7. cxt_bi_stop        - 笔停顿信号
8. cxt_three_bi       - 三笔形态信号
9. cxt_five_bi        - 五笔形态信号
10. cxt_seven_bi      - 七笔形态信号
11. cxt_nine_bi       - 九笔形态信号
12. cxt_eleven_bi     - 十一笔形态信号
13. cxt_first_buy     - 一类买点信号
14. cxt_first_sell    - 一类卖点信号
15. cxt_second_bs     - 二类买卖点信号
16. cxt_third_buy     - 三类买点信号
17. cxt_third_bs      - 三类买卖点信号
18. cxt_zs_breakout   - 中枢突破信号
19. cxt_zs_status     - 中枢状态信号
20. cxt_zs_overlap    - 中枢重叠信号
21. cxt_zs_gongzhen   - 中枢共振信号
22. cxt_double_zs     - 双中枢信号
23. cxt_range_oscillation - 区间震荡信号
24. cxt_decision      - 综合决策信号
25. cxt_bs_signal     - 买卖点综合信号
26. cxt_ubi_end       - 未完成笔结束信号
27. cxt_seg_status    - 线段状态信号
28. cxt_seg_direction - 线段方向信号
29. cxt_trend_type_signal - 走势类型信号
30. cxt_backchi_signal - 背驰信号
31. cxt_thirteen_bi      - 十三笔形态信号
32. cxt_zs_level        - 中枢级别信号
33. cxt_bi_macd_diverge - 笔MACD背驰信号
34. cxt_seg_zs          - 线段中枢信号
35. cxt_multi_level_bs  - 多级别买卖点信号
"""

import numpy as np
from typing import List, Optional, Dict, Any
from collections import OrderedDict
from dataclasses import dataclass

from chan_theory_v2.models.enums import (
    TimeLevel, BiDirection, SegDirection, FenXingType,
    BuySellPointType, DivergenceType
)


# ─── 信号基础工具 ─────────────────────────────────────────────────

def create_single_signal(k1: str, k2: str, k3: str,
                         v1: str = "其他", v2: str = "任意",
                         v3: str = "任意") -> OrderedDict:
    """创建单个信号，统一格式输出"""
    key = f"{k1}_{k2}_{k3}"
    value = f"{v1}_{v2}_{v3}"
    return OrderedDict({key: value})


def get_sub_elements(lst: list, di: int = 1, n: int = 1) -> list:
    """从列表末尾取子元素，参考 czsc.utils.sig.get_sub_elements

    Args:
        lst: 列表
        di: 从倒数第di个元素开始
        n: 取n个元素
    """
    if di < 1 or n < 1:
        return []
    end = len(lst) - di + 1
    start = max(0, end - n)
    if end > len(lst):
        end = len(lst)
    return lst[start:end]


# ─── 缠论形态信号函数 ─────────────────────────────────────────────

def cxt_bi_base(freq: str, bi_list: list, bars_ubi: list,
                bi_init_length: int = 9, **kwargs) -> OrderedDict:
    """笔基础信号

    参数模板："{freq}_D0BL{bi_init_length}_笔基础"

    信号逻辑：
    1. 取最后一个笔，判断当前笔方向
    2. 根据延伸K线数量判断当前笔的状态：中继或转折

    信号列表：
    - Signal('15分钟_D0BL9_笔基础_向下_中继_任意')
    - Signal('15分钟_D0BL9_笔基础_向上_转折_任意')
    - Signal('15分钟_D0BL9_笔基础_向下_转折_任意')
    - Signal('15分钟_D0BL9_笔基础_向上_中继_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param bars_ubi: 未完成笔的K线
    :param bi_init_length: 笔的初始延伸长度
    """
    k1, k2, k3 = f"{freq}_D0BL{bi_init_length}_笔基础".split("_")
    v1 = "其他"
    if len(bi_list) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)

    last_bi = bi_list[-1]
    # 判断方向：最后一笔向下，当前笔向上；反之亦然
    bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
    if bi_dir == BiDirection.DOWN or bi_dir == "down":
        v1 = "向上"
    elif bi_dir == BiDirection.UP or bi_dir == "up":
        v1 = "向下"
    else:
        # 用价格高低判断方向
        if hasattr(last_bi, 'high') and hasattr(last_bi, 'low'):
            v1 = "向上" if last_bi.low < (bi_list[-2].low if len(bi_list) > 1 else last_bi.low) else "向下"

    v2 = "中继" if len(bars_ubi) >= bi_init_length else "转折"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_fx_power(freq: str, fx_list: list, di: int = 1,
                 zhongshus: list = None, **kwargs) -> OrderedDict:
    """倒数第di个分型的强弱信号

    参数模板："{freq}_D{di}F_分型强弱"

    信号逻辑：
    1. 取倒数第di个分型，判断强弱（强/中/弱）
    2. 判断是否有中枢支撑

    信号列表：
    - Signal('15分钟_D1F_分型强弱_强顶_有中枢_任意')
    - Signal('15分钟_D1F_分型强弱_弱底_有中枢_任意')
    - Signal('15分钟_D1F_分型强弱_强底_无中枢_任意')

    :param freq: 周期名称
    :param fx_list: 分型列表
    :param di: 倒数第di个分型
    :param zhongshus: 中枢列表
    """
    k1, k2, k3 = f"{freq}_D{di}F_分型强弱".split("_")
    if len(fx_list) < di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    fx = fx_list[-di]
    fx_type = fx.fx_type if hasattr(fx, 'fx_type') else fx.fenxing_type if hasattr(fx, 'fenxing_type') else None
    fx_mark = "顶" if (fx_type == FenXingType.TOP or fx_type == "top") else "底"

    # 判断分型强弱：基于中间K线与左右K线的价差
    power = "中"
    if hasattr(fx, 'power') and fx.power:
        power = fx.power
    elif hasattr(fx, 'power_str') and fx.power_str:
        power = fx.power_str
    else:
        # 自行计算强弱
        if hasattr(fx, 'middle_kline') and fx.middle_kline:
            mid = fx.middle_kline
            if fx_mark == "顶":
                if hasattr(mid, 'solid') and mid.solid > 0:
                    power = "强" if mid.solid / mid.close > 0.02 else "弱" if mid.solid / mid.close < 0.005 else "中"
            else:
                if hasattr(mid, 'solid') and mid.solid > 0:
                    power = "强" if mid.solid / mid.close > 0.02 else "弱" if mid.solid / mid.close < 0.005 else "中"

    v1 = f"{power}{fx_mark}"
    v2 = "有中枢" if zhongshus and len(zhongshus) > 0 else "无中枢"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_bi_end(freq: str, bi_list: list, fx_list: list,
               bars_ubi: list, macd_confirms: bool = False,
               **kwargs) -> OrderedDict:
    """笔结束信号

    参数模板："{freq}_D0BL笔结束_BE辅助"

    信号逻辑：
    1. 未完成笔K线数量较少（<7），说明新笔刚形成
    2. 检查最新分型是否确认笔的结束方向
    3. MACD是否配合确认

    信号列表：
    - Signal('15分钟_D0BL笔结束_BE辅助_向上_结束_MACD确认')
    - Signal('15分钟_D0BL笔结束_BE辅助_向下_延续_MACD未确认')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param fx_list: 分型列表
    :param bars_ubi: 未完成笔的K线
    :param macd_confirms: MACD是否确认
    """
    k1, k2, k3 = f"{freq}_D0BL笔结束_BE辅助".split("_")
    if len(bi_list) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_bi = bi_list[-1]
    bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
    v1 = "向上" if (bi_dir == BiDirection.DOWN or bi_dir == "down") else "向下"

    # 笔结束判断：未完成笔K线少 + 分型确认
    is_ending = len(bars_ubi) < 7 and len(fx_list) >= 2
    v2 = "结束" if is_ending else "延续"
    v3 = "MACD确认" if macd_confirms else "MACD未确认"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2, v3=v3)


def cxt_bi_status(freq: str, bi_list: list, bars_ubi: list,
                  **kwargs) -> OrderedDict:
    """笔状态信号

    参数模板："{freq}_D0BL笔状态"

    信号逻辑：
    1. 判断当前笔的方向
    2. 判断当前笔的状态（延伸/转折/新笔）
    3. 统计当前笔的K线数量

    信号列表：
    - Signal('15分钟_D0BL笔状态_向上_延伸_任意')
    - Signal('15分钟_D0BL笔状态_向下_转折_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param bars_ubi: 未完成笔的K线
    """
    k1, k2, k3 = f"{freq}_D0BL笔状态".split("_")
    if len(bi_list) < 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_bi = bi_list[-1]
    bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
    v1 = "向上" if (bi_dir == BiDirection.DOWN or bi_dir == "down") else "向下"

    ubi_len = len(bars_ubi)
    if ubi_len < 3:
        v2 = "新笔"
    elif ubi_len < 7:
        v2 = "转折"
    else:
        v2 = "延伸"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_bi_trend(freq: str, bi_list: list, di: int = 1,
                 n: int = 5, **kwargs) -> OrderedDict:
    """笔趋势信号

    参数模板："{freq}_D{di}BLN{n}_笔趋势"

    信号逻辑：
    1. 取最近n笔，用线性回归判断笔价格序列的趋势方向
    2. 回归斜率 > 0 为上涨趋势，< 0 为下跌趋势

    信号列表：
    - Signal('15分钟_D1BLN5_笔趋势_上涨_任意_任意')
    - Signal('15分钟_D1BLN5_笔趋势_下跌_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔
    :param n: 取笔数量
    """
    k1, k2, k3 = f"{freq}_D{di}BLN{n}_笔趋势".split("_")
    bis = get_sub_elements(bi_list, di=di, n=n)
    if len(bis) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    # 用笔的高低点拟合趋势
    highs = [b.high if hasattr(b, 'high') else b.end_price for b in bis]
    lows = [b.low if hasattr(b, 'low') else b.start_price for b in bis]

    x = np.arange(len(highs))
    try:
        slope_h = np.polyfit(x, highs, 1)[0]
        slope_l = np.polyfit(x, lows, 1)[0]
    except Exception:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if slope_h > 0 and slope_l > 0:
        v1 = "上涨"
    elif slope_h < 0 and slope_l < 0:
        v1 = "下跌"
    else:
        v1 = "震荡"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_bi_zdf(freq: str, bi_list: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """笔涨跌幅信号

    参数模板："{freq}_D{di}B_笔涨跌幅"

    信号逻辑：
    根据最后一笔的涨跌幅判断信号

    信号列表：
    - Signal('15分钟_D1B_笔涨跌幅_大涨_任意_任意')
    - Signal('15分钟_D1B_笔涨跌幅_小跌_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_笔涨跌幅".split("_")
    if len(bi_list) < di:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bi = bi_list[-di]
    start_price = bi.start_price if hasattr(bi, 'start_price') else bi.low
    end_price = bi.end_price if hasattr(bi, 'end_price') else bi.high

    if start_price == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    pct = (end_price - start_price) / start_price * 100
    if pct > 5:
        v1 = "大涨"
    elif pct > 2:
        v1 = "小涨"
    elif pct > -2:
        v1 = "横盘"
    elif pct > -5:
        v1 = "小跌"
    else:
        v1 = "大跌"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_bi_stop(freq: str, bi_list: list, fx_list: list,
                bars_ubi: list, **kwargs) -> OrderedDict:
    """笔停顿信号（分型停顿法）

    参数模板："{freq}_D0BL分型停顿_BE辅助"

    信号逻辑：
    1. 最后一笔方向向下，最新K线收盘价站上底分型最高价 → 向下笔停顿
    2. 最后一笔方向向上，最新K线收盘价跌破顶分型最低价 → 向上笔停顿

    信号列表：
    - Signal('15分钟_D0BL分型停顿_BE辅助_向下_停顿_任意')
    - Signal('15分钟_D0BL分型停顿_BE辅助_向上_停顿_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param fx_list: 分型列表
    :param bars_ubi: 未完成笔的K线
    """
    k1, k2, k3 = f"{freq}_D0BL分型停顿_BE辅助".split("_")
    if len(bi_list) < 2 or len(fx_list) < 2 or len(bars_ubi) < 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_bi = bi_list[-1]
    last_fx = fx_list[-1]
    bar = bars_ubi[-1] if bars_ubi else None

    if bar is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
    bar_close = bar.close if hasattr(bar, 'close') else 0

    if bi_dir == BiDirection.UP or bi_dir == "up":
        v1 = "向上"
        fx_low = last_fx.low if hasattr(last_fx, 'low') else 0
        v2 = "停顿" if bar_close < fx_low else "延伸"
    else:
        v1 = "向下"
        fx_high = last_fx.high if hasattr(last_fx, 'high') else 0
        v2 = "停顿" if bar_close > fx_high else "延伸"

    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def _check_bi_direction(bi) -> str:
    """判断笔方向"""
    if hasattr(bi, 'direction'):
        d = bi.direction
        if d == BiDirection.UP or d == "up":
            return "向上"
        elif d == BiDirection.DOWN or d == "down":
            return "向下"
    # 用价格判断
    sp = bi.start_price if hasattr(bi, 'start_price') else 0
    ep = bi.end_price if hasattr(bi, 'end_price') else 0
    return "向上" if ep > sp else "向下"


def cxt_three_bi(freq: str, bi_list: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """三笔形态信号

    参数模板："{freq}_D{di}B_三笔形态"

    信号逻辑：
    1. 取最近3笔，判断三笔之间的关系
    2. 向上三笔：b1向上，b2回抽，b3再上 → 上涨趋势
    3. 向下三笔：b1向下，b2反弹，b3再下 → 下跌趋势

    信号列表：
    - Signal('15分钟_D1B_三笔形态_上涨趋势_任意_任意')
    - Signal('15分钟_D1B_三笔形态_下跌趋势_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_三笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=3)
    if len(bis) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    b1, b2, b3 = bis[0], bis[1], bis[2]
    b1_high = b1.high if hasattr(b1, 'high') else 0
    b2_low = b2.low if hasattr(b2, 'low') else 0
    b3_high = b3.high if hasattr(b3, 'high') else 0
    b1_low = b1.low if hasattr(b1, 'low') else 0
    b2_high = b2.high if hasattr(b2, 'high') else 0
    b3_low = b3.low if hasattr(b3, 'low') else 0

    if b3_high > b1_high and b2_low > b1_low:
        v1 = "上涨趋势"
    elif b3_low < b1_low and b2_high < b1_high:
        v1 = "下跌趋势"
    elif b3_high > b1_high and b3_low < b1_low:
        v1 = "扩张形态"
    elif b3_high < b1_high and b3_low > b1_low:
        v1 = "收敛形态"
    else:
        v1 = "震荡形态"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_five_bi(freq: str, bi_list: list, di: int = 1,
                **kwargs) -> OrderedDict:
    """五笔形态信号

    参数模板："{freq}_D{di}B_五笔形态"

    信号逻辑：
    取最近5笔，判断五笔之间的关系，识别二类买卖点等形态

    信号列表：
    - Signal('15分钟_D1B_五笔形态_二买_任意_任意')
    - Signal('15分钟_D1B_五笔形态_二卖_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_五笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=5)
    if len(bis) < 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    b1, b2, b3, b4, b5 = bis[0], bis[1], bis[2], bis[3], bis[4]
    highs = [b.high if hasattr(b, 'high') else 0 for b in bis]
    lows = [b.low if hasattr(b, 'low') else 0 for b in bis]

    # 二买：b5向上，b5低点 > b3低点 > b1低点，b3高点 < b1高点
    if highs[4] > highs[2] and lows[4] > lows[2] and lows[2] > lows[0]:
        v1 = "二买"
    # 二卖：b5向下，b5高点 < b3高点 < b1高点，b3低点 > b1低点
    elif highs[4] < highs[2] and highs[2] < highs[0]:
        v1 = "二卖"
    # 类二买
    elif lows[4] > lows[2] and lows[2] >= lows[0] * 0.98:
        v1 = "类二买"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_seven_bi(freq: str, bi_list: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """七笔形态信号

    参数模板："{freq}_D{di}B_七笔形态"

    信号逻辑：
    取最近7笔，判断是否构成中枢及走势形态

    信号列表：
    - Signal('15分钟_D1B_七笔形态_上涨中枢_任意_任意')
    - Signal('15分钟_D1B_七笔形态_下跌中枢_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_七笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=7)
    if len(bis) < 7:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = [b.high if hasattr(b, 'high') else 0 for b in bis]
    lows = [b.low if hasattr(b, 'low') else 0 for b in bis]

    # 中间3笔构成中枢
    zs_high = min(highs[2:5])
    zs_low = max(lows[2:5])

    # 判断走势方向
    if highs[-1] > highs[2] and lows[-1] > lows[2]:
        v1 = "上涨中枢"
    elif highs[-1] < highs[2] and lows[-1] < lows[2]:
        v1 = "下跌中枢"
    else:
        v1 = "盘整中枢"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_nine_bi(freq: str, bi_list: list, di: int = 1,
                **kwargs) -> OrderedDict:
    """九笔形态信号

    参数模板："{freq}_D{di}B_九笔形态"

    信号逻辑：
    取最近9笔，判断双中枢走势

    信号列表：
    - Signal('15分钟_D1B_九笔形态_上涨双中枢_任意_任意')
    - Signal('15分钟_D1B_九笔形态_下跌双中枢_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_九笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=9)
    if len(bis) < 9:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = [b.high if hasattr(b, 'high') else 0 for b in bis]
    lows = [b.low if hasattr(b, 'low') else 0 for b in bis]

    # 前中枢：b2-b4
    zs1_high = min(highs[2:5])
    zs1_low = max(lows[2:5])
    # 后中枢：b6-b8
    zs2_high = min(highs[5:8])
    zs2_low = max(lows[5:8])

    if zs2_low > zs1_low and zs2_high > zs1_high:
        v1 = "上涨双中枢"
    elif zs2_low < zs1_low and zs2_high < zs1_high:
        v1 = "下跌双中枢"
    else:
        v1 = "盘整双中枢"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_eleven_bi(freq: str, bi_list: list, di: int = 1,
                  **kwargs) -> OrderedDict:
    """十一笔形态信号

    参数模板："{freq}_D{di}B_十一笔形态"

    信号逻辑：
    取最近11笔，判断走势完整性

    信号列表：
    - Signal('15分钟_D1B_十一笔形态_完整上涨_任意_任意')
    - Signal('15分钟_D1B_十一笔形态_完整下跌_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_十一笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=11)
    if len(bis) < 11:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = [b.high if hasattr(b, 'high') else 0 for b in bis]
    lows = [b.low if hasattr(b, 'low') else 0 for b in bis]

    # 三个中枢的走势判断
    if highs[-1] > highs[0] and min(highs[-3:]) > min(highs[3:6]) > min(highs[0:3]):
        v1 = "完整上涨"
    elif highs[-1] < highs[0] and max(highs[-3:]) < max(highs[3:6]) < max(highs[0:3]):
        v1 = "完整下跌"
    else:
        v1 = "复杂形态"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_first_buy(freq: str, bi_list: list, zhongshus: list,
                  di: int = 1, **kwargs) -> OrderedDict:
    """一类买点信号

    参数模板："{freq}_D{di}B_BUY1"

    信号逻辑：
    1. 下跌趋势中，最后一个中枢之后出现底背驰
    2. 最后一笔向下且创新低

    信号列表：
    - Signal('15分钟_D1B_BUY1_一买_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_BUY1".split("_")
    if len(bi_list) < di + 5 or not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bi = bi_list[-di]
    bi_dir = bi.direction if hasattr(bi, 'direction') else None

    # 一买：向下笔创新低
    if bi_dir == BiDirection.DOWN or bi_dir == "down":
        # 检查是否在最后一个中枢下方
        last_zs = zhongshus[-1]
        zs_low = last_zs.low if hasattr(last_zs, 'low') else last_zs.zd if hasattr(last_zs, 'zd') else 0
        bi_low = bi.low if hasattr(bi, 'low') else 0
        if bi_low < zs_low:
            v1 = "一买"
        else:
            v1 = "其他"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_first_sell(freq: str, bi_list: list, zhongshus: list,
                   di: int = 1, **kwargs) -> OrderedDict:
    """一类卖点信号

    参数模板："{freq}_D{di}B_SELL1"

    信号逻辑：
    1. 上涨趋势中，最后一个中枢之后出现顶背驰
    2. 最后一笔向上且创新高

    信号列表：
    - Signal('15分钟_D1B_SELL1_一卖_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_SELL1".split("_")
    if len(bi_list) < di + 5 or not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    bi = bi_list[-di]
    bi_dir = bi.direction if hasattr(bi, 'direction') else None

    if bi_dir == BiDirection.UP or bi_dir == "up":
        last_zs = zhongshus[-1]
        zs_high = last_zs.high if hasattr(last_zs, 'high') else last_zs.zg if hasattr(last_zs, 'zg') else 0
        bi_high = bi.high if hasattr(bi, 'high') else 0
        if bi_high > zs_high:
            v1 = "一卖"
        else:
            v1 = "其他"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_second_bs(freq: str, bi_list: list, zhongshus: list,
                  di: int = 1, **kwargs) -> OrderedDict:
    """二类买卖点信号

    参数模板："{freq}_D{di}B_BS2"

    信号逻辑：
    1. 二买：一买后回抽不破前低
    2. 二卖：一卖后反弹不破前高

    信号列表：
    - Signal('15分钟_D1B_BS2_二买_任意_任意')
    - Signal('15分钟_D1B_BS2_二卖_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_BS2".split("_")
    bis = get_sub_elements(bi_list, di=di, n=5)
    if len(bis) < 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    b1, b2, b3, b4, b5 = bis
    b3_low = b3.low if hasattr(b3, 'low') else 0
    b1_low = b1.low if hasattr(b1, 'low') else 0
    b5_low = b5.low if hasattr(b5, 'low') else 0
    b3_high = b3.high if hasattr(b3, 'high') else 0
    b1_high = b1.high if hasattr(b1, 'high') else 0
    b5_high = b5.high if hasattr(b5, 'high') else 0

    # 二买：b5低点 > b3低点（不破前低）
    if b5_low > b3_low and b5_high > b3_high:
        v1 = "二买"
    # 二卖：b5高点 < b3高点（不破前高）
    elif b5_high < b3_high and b5_low < b3_low:
        v1 = "二卖"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_third_buy(freq: str, bi_list: list, zhongshus: list,
                  di: int = 1, **kwargs) -> OrderedDict:
    """三类买点信号

    参数模板："{freq}_D{di}B_BUY3"

    信号逻辑：
    1. 中枢突破后回试不破中枢上沿
    2. 最后一笔向下回试，低点在中枢上沿之上

    信号列表：
    - Signal('15分钟_D1B_BUY3_三买_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_BUY3".split("_")
    if len(bi_list) < di + 3 or not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_zs = zhongshus[-1]
    zs_high = last_zs.high if hasattr(last_zs, 'high') else last_zs.zg if hasattr(last_zs, 'zg') else 0

    # 最后一笔向下回试
    bi = bi_list[-di]
    bi_dir = bi.direction if hasattr(bi, 'direction') else None
    bi_low = bi.low if hasattr(bi, 'low') else 0

    if (bi_dir == BiDirection.DOWN or bi_dir == "down") and bi_low > zs_high:
        v1 = "三买"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_third_bs(freq: str, bi_list: list, zhongshus: list,
                 di: int = 1, **kwargs) -> OrderedDict:
    """三类买卖点信号

    参数模板："{freq}_D{di}B_BS3"

    信号逻辑：
    1. 三买：回试不破中枢上沿
    2. 三卖：反弹不破中枢下沿

    信号列表：
    - Signal('15分钟_D1B_BS3_三买_任意_任意')
    - Signal('15分钟_D1B_BS3_三卖_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_BS3".split("_")
    if len(bi_list) < di + 1 or not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_zs = zhongshus[-1]
    zs_high = last_zs.high if hasattr(last_zs, 'high') else 0
    zs_low = last_zs.low if hasattr(last_zs, 'low') else 0

    bi = bi_list[-di]
    bi_dir = bi.direction if hasattr(bi, 'direction') else None
    bi_low = bi.low if hasattr(bi, 'low') else 0
    bi_high = bi.high if hasattr(bi, 'high') else 0

    if (bi_dir == BiDirection.DOWN or bi_dir == "down") and bi_low > zs_high:
        v1 = "三买"
    elif (bi_dir == BiDirection.UP or bi_dir == "up") and bi_high < zs_low:
        v1 = "三卖"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_zs_breakout(freq: str, zhongshus: list, current_price: float,
                    **kwargs) -> OrderedDict:
    """中枢突破信号

    参数模板："{freq}_中枢突破_ZS_BRK"

    信号逻辑：
    1. 当前价格突破最后一个中枢的上沿 → 向上突破
    2. 当前价格跌破最后一个中枢的下沿 → 向下突破
    3. 否则在中枢内

    信号列表：
    - Signal('15分钟_中枢突破_ZS_BRK_向上突破_任意_任意')
    - Signal('15分钟_中枢突破_ZS_BRK_向下突破_任意_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    :param current_price: 当前价格
    """
    k1, k2, k3 = f"{freq}_中枢突破_ZS_BRK".split("_")
    if not zhongshus or current_price <= 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_zs = zhongshus[-1]
    zs_high = last_zs.high if hasattr(last_zs, 'high') else 0
    zs_low = last_zs.low if hasattr(last_zs, 'low') else 0

    if current_price > zs_high:
        v1 = "向上突破"
    elif current_price < zs_low:
        v1 = "向下突破"
    else:
        v1 = "中枢内"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_zs_status(freq: str, zhongshus: list, bi_list: list,
                  **kwargs) -> OrderedDict:
    """中枢状态信号

    参数模板："{freq}_中枢状态_ZS_STA"

    信号逻辑：
    1. 判断中枢数量和走势类型
    2. 单中枢=盘整，2+中枢=趋势

    信号列表：
    - Signal('15分钟_中枢状态_ZS_STA_盘整_1中枢_任意')
    - Signal('15分钟_中枢状态_ZS_STA_上涨_2中枢_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    :param bi_list: 笔列表
    """
    k1, k2, k3 = f"{freq}_中枢状态_ZS_STA".split("_")
    zs_count = len(zhongshus) if zhongshus else 0

    if zs_count == 0:
        v1 = "无中枢"
        v2 = "0中枢"
    elif zs_count == 1:
        v1 = "盘整"
        v2 = "1中枢"
    else:
        # 判断趋势方向
        zs1 = zhongshus[0]
        zs2 = zhongshus[-1]
        zs1_low = zs1.low if hasattr(zs1, 'low') else 0
        zs2_low = zs2.low if hasattr(zs2, 'low') else 0
        zs1_high = zs1.high if hasattr(zs1, 'high') else 0
        zs2_high = zs2.high if hasattr(zs2, 'high') else 0

        if zs2_low > zs1_low:
            v1 = "上涨"
        elif zs2_high < zs1_high:
            v1 = "下跌"
        else:
            v1 = "盘整"
        v2 = f"{zs_count}中枢"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_zs_overlap(freq: str, zhongshus: list, di: int = 1,
                   **kwargs) -> OrderedDict:
    """中枢重叠信号

    参数模板："{freq}_D{di}ZS_中枢重叠"

    信号逻辑：
    判断最近两个中枢是否有重叠区间

    信号列表：
    - Signal('15分钟_D1ZS_中枢重叠_有重叠_任意_任意')
    - Signal('15分钟_D1ZS_中枢重叠_无重叠_任意_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    :param di: 倒数第di个中枢
    """
    k1, k2, k3 = f"{freq}_D{di}ZS_中枢重叠".split("_")
    if not zhongshus or len(zhongshus) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    zs1 = zhongshus[-di - 1] if len(zhongshus) > di else zhongshus[0]
    zs2 = zhongshus[-di]

    zs1_high = zs1.high if hasattr(zs1, 'high') else 0
    zs1_low = zs1.low if hasattr(zs1, 'low') else 0
    zs2_high = zs2.high if hasattr(zs2, 'high') else 0
    zs2_low = zs2.low if hasattr(zs2, 'low') else 0

    overlap_high = min(zs1_high, zs2_high)
    overlap_low = max(zs1_low, zs2_low)

    v1 = "有重叠" if overlap_high > overlap_low else "无重叠"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_zs_gongzhen(freq: str, zhongshus: list, n: int = 3,
                    **kwargs) -> OrderedDict:
    """中枢共振信号

    参数模板："{freq}_N{n}ZS_中枢共振"

    信号逻辑：
    多个中枢区间相近时产生共振

    信号列表：
    - Signal('15分钟_N3ZS_中枢共振_共振_任意_任意')
    - Signal('15分钟_N3ZS_中枢共振_无共振_任意_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    :param n: 考察中枢数量
    """
    k1, k2, k3 = f"{freq}_N{n}ZS_中枢共振".split("_")
    if not zhongshus or len(zhongshus) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent_zs = zhongshus[-n:]
    centers = []
    for zs in recent_zs:
        h = zs.high if hasattr(zs, 'high') else 0
        l = zs.low if hasattr(zs, 'low') else 0
        centers.append((h + l) / 2)

    # 共振：中枢中心价格变异系数 < 0.02
    center_arr = np.array(centers)
    cv = np.std(center_arr) / np.mean(center_arr) if np.mean(center_arr) > 0 else 1
    v1 = "共振" if cv < 0.02 else "无共振"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_double_zs(freq: str, zhongshus: list, **kwargs) -> OrderedDict:
    """双中枢信号

    参数模板："{freq}_双中枢_DZS"

    信号逻辑：
    判断最近两个中枢的排列关系（上涨/下跌/盘整）

    信号列表：
    - Signal('15分钟_双中枢_DZS_上涨排列_任意_任意')
    - Signal('15分钟_双中枢_DZS_下跌排列_任意_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    """
    k1, k2, k3 = f"{freq}_双中枢_DZS".split("_")
    if not zhongshus or len(zhongshus) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    zs1, zs2 = zhongshus[-2], zhongshus[-1]
    zs1_low = zs1.low if hasattr(zs1, 'low') else 0
    zs2_low = zs2.low if hasattr(zs2, 'low') else 0
    zs1_high = zs1.high if hasattr(zs1, 'high') else 0
    zs2_high = zs2.high if hasattr(zs2, 'high') else 0

    if zs2_low > zs1_high:
        v1 = "上涨排列"
    elif zs2_high < zs1_low:
        v1 = "下跌排列"
    elif zs2_low > zs1_low:
        v1 = "上涨交叉"
    elif zs2_high < zs1_high:
        v1 = "下跌交叉"
    else:
        v1 = "重叠盘整"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_range_oscillation(freq: str, bi_list: list, zhongshus: list,
                          di: int = 1, **kwargs) -> OrderedDict:
    """区间震荡信号

    参数模板："{freq}_D{di}B_区间震荡"

    信号逻辑：
    判断最近走势是否为区间震荡

    信号列表：
    - Signal('15分钟_D1B_区间震荡_窄幅震荡_任意_任意')
    - Signal('15分钟_D1B_区间震荡_宽幅震荡_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_区间震荡".split("_")
    if not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_zs = zhongshus[-1]
    zs_range = (last_zs.high - last_zs.low) if hasattr(last_zs, 'high') and hasattr(last_zs, 'low') else 0
    zs_center = (last_zs.high + last_zs.low) / 2 if zs_range > 0 else 1

    amplitude = zs_range / zs_center if zs_center > 0 else 0
    if amplitude < 0.03:
        v1 = "窄幅震荡"
    elif amplitude < 0.08:
        v1 = "宽幅震荡"
    else:
        v1 = "剧烈震荡"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_decision(freq: str, bi_list: list, zhongshus: list,
                 backchi_analyses: list = None, **kwargs) -> OrderedDict:
    """综合决策信号

    参数模板："{freq}_综合决策_DEC"

    信号逻辑：
    综合笔方向、中枢状态、背驰分析给出多空决策

    信号列表：
    - Signal('15分钟_综合决策_DEC_看多_任意_任意')
    - Signal('15分钟_综合决策_DEC_看空_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param backchi_analyses: 背驰分析列表
    """
    k1, k2, k3 = f"{freq}_综合决策_DEC".split("_")
    if len(bi_list) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    score = 0
    # 1. 笔方向
    last_bi = bi_list[-1]
    bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
    if bi_dir == BiDirection.UP or bi_dir == "up":
        score += 1
    elif bi_dir == BiDirection.DOWN or bi_dir == "down":
        score -= 1

    # 2. 中枢趋势
    if zhongshus and len(zhongshus) >= 2:
        zs1 = zhongshus[-2]
        zs2 = zhongshus[-1]
        zs1_low = zs1.low if hasattr(zs1, 'low') else 0
        zs2_low = zs2.low if hasattr(zs2, 'low') else 0
        if zs2_low > zs1_low:
            score += 1
        else:
            score -= 1

    # 3. 背驰
    if backchi_analyses and len(backchi_analyses) > 0:
        last_bc = backchi_analyses[-1]
        bc_type = str(last_bc.backchi_type) if hasattr(last_bc, 'backchi_type') else ""
        if "底" in bc_type:
            score += 2
        elif "顶" in bc_type:
            score -= 2

    if score > 1:
        v1 = "看多"
    elif score < -1:
        v1 = "看空"
    else:
        v1 = "中性"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_bs_signal(freq: str, bi_list: list, zhongshus: list,
                  buy_sell_points: list = None, **kwargs) -> OrderedDict:
    """买卖点综合信号

    参数模板："{freq}_买卖点_BS"

    信号逻辑：
    综合买卖点信号

    信号列表：
    - Signal('15分钟_买卖点_BS_一买_任意_任意')
    - Signal('15分钟_买卖点_BS_三卖_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param buy_sell_points: 买卖点列表
    """
    k1, k2, k3 = f"{freq}_买卖点_BS".split("_")
    if not buy_sell_points:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="无信号")

    last_point = buy_sell_points[-1]
    pt_type = last_point.point_type if hasattr(last_point, 'point_type') else None

    type_map = {
        BuySellPointType.BUY_1: "一买", BuySellPointType.BUY_2: "二买", BuySellPointType.BUY_3: "三买",
        BuySellPointType.SELL_1: "一卖", BuySellPointType.SELL_2: "二卖", BuySellPointType.SELL_3: "三卖",
    }
    v1 = type_map.get(pt_type, "其他")
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_ubi_end(freq: str, bi_list: list, bars_ubi: list,
                **kwargs) -> OrderedDict:
    """未完成笔结束信号

    参数模板："{freq}_D0UBI_UBI结束"

    信号逻辑：
    判断未完成笔是否即将结束

    信号列表：
    - Signal('15分钟_D0UBI_UBI结束_即将结束_任意_任意')
    - Signal('15分钟_D0UBI_UBI结束_延续中_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param bars_ubi: 未完成笔的K线
    """
    k1, k2, k3 = f"{freq}_D0UBI_UBI结束".split("_")
    if len(bi_list) < 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_bi = bi_list[-1]
    ubi_len = len(bars_ubi)

    if ubi_len < 3:
        v1 = "刚形成"
    elif ubi_len < 5:
        v1 = "即将结束"
    else:
        v1 = "延续中"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_seg_status(freq: str, seg_list: list, **kwargs) -> OrderedDict:
    """线段状态信号

    参数模板："{freq}_D0SEG_线段状态"

    信号逻辑：
    判断当前线段的状态

    信号列表：
    - Signal('15分钟_D0SEG_线段状态_向上_延伸_任意')
    - Signal('15分钟_D0SEG_线段状态_向下_转折_任意')

    :param freq: 周期名称
    :param seg_list: 线段列表
    """
    k1, k2, k3 = f"{freq}_D0SEG_线段状态".split("_")
    if len(seg_list) < 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_seg = seg_list[-1]
    seg_dir = last_seg.direction if hasattr(last_seg, 'direction') else None
    v1 = "向上" if (seg_dir == SegDirection.UP or seg_dir == "up") else "向下"

    # 简化判断
    seg_bis = last_seg.bis if hasattr(last_seg, 'bis') else []
    v2 = "延伸" if len(seg_bis) >= 5 else "转折"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_seg_direction(freq: str, seg_list: list, di: int = 1,
                      n: int = 3, **kwargs) -> OrderedDict:
    """线段方向信号

    参数模板："{freq}_D{di}SN{n}_线段方向"

    信号逻辑：
    取最近n条线段，判断线段方向趋势

    信号列表：
    - Signal('15分钟_D1SN3_线段方向_上涨_任意_任意')
    - Signal('15分钟_D1SN3_线段方向_下跌_任意_任意')

    :param freq: 周期名称
    :param seg_list: 线段列表
    :param di: 倒数第di条线段
    :param n: 取线段数量
    """
    k1, k2, k3 = f"{freq}_D{di}SN{n}_线段方向".split("_")
    segs = get_sub_elements(seg_list, di=di, n=n)
    if len(segs) < n:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = [s.high if hasattr(s, 'high') else s.end_price for s in segs]
    lows = [s.low if hasattr(s, 'low') else s.start_price for s in segs]

    if all(highs[i] < highs[i + 1] for i in range(len(highs) - 1)):
        v1 = "上涨"
    elif all(highs[i] > highs[i + 1] for i in range(len(highs) - 1)):
        v1 = "下跌"
    else:
        v1 = "震荡"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_trend_type_signal(freq: str, trend_type: str = None,
                          trend_strength: float = 0.0,
                          **kwargs) -> OrderedDict:
    """走势类型信号

    参数模板："{freq}_走势类型_TT"

    信号逻辑：
    直接基于走势类型划分结果生成信号

    信号列表：
    - Signal('15分钟_走势类型_TT_上涨_强_任意')
    - Signal('15分钟_走势类型_TT_盘整_中_任意')

    :param freq: 周期名称
    :param trend_type: 走势类型 (up_trend/down_trend/consolidation)
    :param trend_strength: 走势强度 0-1
    """
    k1, k2, k3 = f"{freq}_走势类型_TT".split("_")

    type_map = {"up_trend": "上涨", "down_trend": "下跌", "consolidation": "盘整", "unknown": "未判定"}
    v1 = type_map.get(trend_type, "其他") if trend_type else "其他"

    if trend_strength > 0.7:
        v2 = "强"
    elif trend_strength > 0.4:
        v2 = "中"
    else:
        v2 = "弱"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_backchi_signal(freq: str, backchi_analyses: list = None,
                       **kwargs) -> OrderedDict:
    """背驰信号

    参数模板："{freq}_背驰_BC"

    信号逻辑：
    基于背驰分析结果生成信号

    信号列表：
    - Signal('15分钟_背驰_BC_顶背驰_任意_任意')
    - Signal('15分钟_背驰_BC_底背驰_任意_任意')

    :param freq: 周期名称
    :param backchi_analyses: 背驰分析列表
    """
    k1, k2, k3 = f"{freq}_背驰_BC".split("_")
    if not backchi_analyses or len(backchi_analyses) == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="无背驰")

    last_bc = backchi_analyses[-1]
    bc_type = last_bc.backchi_type if hasattr(last_bc, 'backchi_type') else None

    type_map = {
        DivergenceType.TOP_DIVERGENCE: "顶背驰",
        DivergenceType.BOTTOM_DIVERGENCE: "底背驰",
        DivergenceType.NONE: "无背驰",
    }
    if bc_type in type_map:
        v1 = type_map[bc_type]
    elif isinstance(bc_type, str):
        v1 = bc_type
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_thirteen_bi(freq: str, bi_list: list, di: int = 1,
                    **kwargs) -> OrderedDict:
    """十三笔形态信号

    参数模板："{freq}_D{di}B_十三笔形态"

    信号逻辑：
    取最近13笔，判断走势完整性

    信号列表：
    - Signal('15分钟_D1B_十三笔形态_完整上涨_任意_任意')
    - Signal('15分钟_D1B_十三笔形态_完整下跌_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param di: 倒数第di笔开始
    """
    k1, k2, k3 = f"{freq}_D{di}B_十三笔形态".split("_")
    bis = get_sub_elements(bi_list, di=di, n=13)
    if len(bis) < 13:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    highs = [b.high if hasattr(b, 'high') else 0 for b in bis]
    lows = [b.low if hasattr(b, 'low') else 0 for b in bis]

    # 三个中枢的走势判断
    zs1_high = min(highs[2:5])
    zs2_high = min(highs[5:8])
    zs3_high = min(highs[8:11])
    zs1_low = max(lows[2:5])
    zs2_low = max(lows[5:8])
    zs3_low = max(lows[8:11])

    if zs1_high < zs2_high < zs3_high and zs1_low < zs2_low < zs3_low:
        v1 = "完整上涨"
    elif zs1_high > zs2_high > zs3_high and zs1_low > zs2_low > zs3_low:
        v1 = "完整下跌"
    else:
        v1 = "复杂形态"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_zs_level(freq: str, zhongshus: list, bi_list: list,
                 **kwargs) -> OrderedDict:
    """中枢级别信号

    参数模板："{freq}_中枢级别_ZS_LV"

    信号逻辑：
    判断中枢的级别大小（笔数/跨度）

    信号列表：
    - Signal('15分钟_中枢级别_ZS_LV_大级别_任意_任意')
    - Signal('15分钟_中枢级别_ZS_LV_小级别_任意_任意')

    :param freq: 周期名称
    :param zhongshus: 中枢列表
    :param bi_list: 笔列表
    """
    k1, k2, k3 = f"{freq}_中枢级别_ZS_LV".split("_")
    if not zhongshus:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    last_zs = zhongshus[-1]
    zs_high = last_zs.high if hasattr(last_zs, 'high') else 0
    zs_low = last_zs.low if hasattr(last_zs, 'low') else 0
    zs_range = zs_high - zs_low

    # 中枢跨度
    bi_count = 0
    if hasattr(last_zs, 'bis'):
        bi_count = len(last_zs.bis)
    elif hasattr(last_zs, 'start_bi') and hasattr(last_zs, 'end_bi'):
        bi_count = getattr(last_zs, 'bi_count', 3)
    else:
        bi_count = 3

    if bi_list and len(bi_list) > 0:
        total_range = max(b.high if hasattr(b, 'high') else 0 for b in bi_list[-20:]) - \
                      min(b.low if hasattr(b, 'low') else 0 for b in bi_list[-20:])
        if total_range > 0:
            relative_range = zs_range / total_range
            if relative_range > 0.5 or bi_count >= 7:
                v1 = "大级别"
            elif relative_range > 0.2 or bi_count >= 5:
                v1 = "中级别"
            else:
                v1 = "小级别"
        else:
            v1 = "其他"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_bi_macd_diverge(freq: str, bi_list: list, bars_raw: list = None,
                        di: int = 1, **kwargs) -> OrderedDict:
    """笔MACD背驰信号

    参数模板："{freq}_D{di}B_MACD背驰"

    信号逻辑：
    比较相邻两笔的MACD面积判断背驰

    信号列表：
    - Signal('15分钟_D1B_MACD背驰_顶背驰_任意_任意')
    - Signal('15分钟_D1B_MACD背驰_底背驰_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param bars_raw: K线列表
    :param di: 倒数第di笔
    """
    k1, k2, k3 = f"{freq}_D{di}B_MACD背驰".split("_")
    if len(bi_list) < di + 2 or bars_raw is None:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    close = np.array([b.close for b in bars_raw if hasattr(b, 'close')])
    if len(close) < 35:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    from .tas import _calc_macd
    dif, dea, macd = _calc_macd(close)

    bi1 = bi_list[-(di + 1)]
    bi2 = bi_list[-di]

    bi1_dir = bi1.direction if hasattr(bi1, 'direction') else None
    bi2_dir = bi2.direction if hasattr(bi2, 'direction') else None

    if bi1_dir == bi2_dir:
        v1 = "其他"
    else:
        macd_abs = np.abs(macd)
        recent_area = np.sum(macd_abs[-10:]) if len(macd_abs) >= 10 else 0
        prev_area = np.sum(macd_abs[-20:-10]) if len(macd_abs) >= 20 else 0

        if prev_area == 0:
            v1 = "其他"
        elif recent_area < prev_area * 0.7:
            if bi2_dir == BiDirection.UP or bi2_dir == "up":
                v1 = "顶背驰"
            else:
                v1 = "底背驰"
        else:
            v1 = "无背驰"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def cxt_seg_zs(freq: str, seg_list: list, zhongshus: list = None,
               **kwargs) -> OrderedDict:
    """线段中枢信号

    参数模板："{freq}_D0SEG_线段中枢"

    信号逻辑：
    判断线段是否形成中枢

    信号列表：
    - Signal('15分钟_D0SEG_线段中枢_有中枢_任意_任意')
    - Signal('15分钟_D0SEG_线段中枢_无中枢_任意_任意')

    :param freq: 周期名称
    :param seg_list: 线段列表
    :param zhongshus: 中枢列表
    """
    k1, k2, k3 = f"{freq}_D0SEG_线段中枢".split("_")
    if len(seg_list) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    recent_segs = seg_list[-3:]
    highs = [s.high if hasattr(s, 'high') else 0 for s in recent_segs]
    lows = [s.low if hasattr(s, 'low') else 0 for s in recent_segs]

    overlap_high = min(highs)
    overlap_low = max(lows)

    if overlap_high > overlap_low:
        v1 = "有中枢"
        v2 = f"宽度{overlap_high - overlap_low:.2f}"
    else:
        v1 = "无中枢"
        v2 = "任意"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1, v2=v2)


def cxt_multi_level_bs(freq: str, bi_list: list, zhongshus: list,
                       higher_bi_list: list = None,
                       higher_zhongshus: list = None,
                       **kwargs) -> OrderedDict:
    """多级别买卖点信号

    参数模板："{freq}_多级别买卖_MLBS"

    信号逻辑：
    综合当前级别和高级别的买卖点信号

    信号列表：
    - Signal('15分钟_多级别买卖_MLBS_共振买点_任意_任意')
    - Signal('15分钟_多级别买卖_MLBS_共振卖点_任意_任意')

    :param freq: 周期名称
    :param bi_list: 笔列表
    :param zhongshus: 中枢列表
    :param higher_bi_list: 高级别笔列表
    :param higher_zhongshus: 高级别中枢列表
    """
    k1, k2, k3 = f"{freq}_多级别买卖_MLBS".split("_")

    current_score = 0
    if len(bi_list) >= 3 and zhongshus:
        last_bi = bi_list[-1]
        bi_dir = last_bi.direction if hasattr(last_bi, 'direction') else None
        if bi_dir == BiDirection.UP or bi_dir == "up":
            current_score = 1
        elif bi_dir == BiDirection.DOWN or bi_dir == "down":
            current_score = -1

    higher_score = 0
    if higher_bi_list and len(higher_bi_list) >= 3 and higher_zhongshus:
        h_last_bi = higher_bi_list[-1]
        h_bi_dir = h_last_bi.direction if hasattr(h_last_bi, 'direction') else None
        if h_bi_dir == BiDirection.UP or h_bi_dir == "up":
            higher_score = 1
        elif h_bi_dir == BiDirection.DOWN or h_bi_dir == "down":
            higher_score = -1

    total_score = current_score + higher_score
    if total_score >= 2:
        v1 = "共振买点"
    elif total_score == 1:
        v1 = "偏多"
    elif total_score == -1:
        v1 = "偏空"
    elif total_score <= -2:
        v1 = "共振卖点"
    else:
        v1 = "中性"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
