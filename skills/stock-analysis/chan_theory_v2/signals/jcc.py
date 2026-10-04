#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K线组合形态信号 (jcc = Jia Cha Xing, 即价差形)

参考 czsc.signals.jcc 的设计，实现经典K线组合形态识别。

信号列表：
1.  jcc_san_xing_xian    - 三星线形态
2.  jcc_ten_mo           - 十字星形态
3.  jcc_wu_yun_gai_ding  - 乌云盖顶形态
4.  jcc_ci_tou           - 刺透形态
5.  jcc_san_fa           - 三法形态
6.  jcc_xing_xian        - 星线形态
7.  jcc_fen_shou_xian    - 分手线形态
8.  jcc_zhu_huo_xian     - 抓获线形态
9.  jcc_yun_xian         - 孕线形态
10. jcc_ping_tou         - 平头形态
11. jcc_two_crow         - 两只乌鸦形态
12. jcc_three_crow       - 三只乌鸦形态
13. jcc_szx              - 十字星形态
14. jcc_san_szx          - 三星十字形态
15. jcc_fan_ji_xian      - 反击线形态
16. jcc_shan_chun        - 山川形态
17. jcc_gap_yin_yang     - 跳空并列阴阳形态
18. jcc_ta_xing          - 塔形形态
19. jcc_zhuo_yao_dai_xian- 捉腰带线形态
20. jcc_hammer           - 锤子线/上吊线形态
21. jcc_engulfing        - 吞没形态
22. jcc_harami_cross     - 十字孕线形态
23. jcc_three_white      - 三白兵形态
24. jcc_three_black      - 三黑鸦形态
25. jcc_kicking          - 跳空缺口形态
"""

import numpy as np
from typing import List
from collections import OrderedDict

from .cxt import create_single_signal, get_sub_elements
from chan_theory_v2.models.enums import BiDirection


def _get_bar_attrs(bars: list):
    """获取K线属性字典列表"""
    result = []
    for b in bars:
        if not hasattr(b, 'close'):
            continue
        o = b.open if hasattr(b, 'open') else b.close
        h = b.high if hasattr(b, 'high') else b.close
        l = b.low if hasattr(b, 'low') else b.close
        c = b.close
        v = b.volume if hasattr(b, 'volume') else 0
        solid = abs(c - o)
        upper = h - max(c, o)
        lower = min(c, o) - l
        result.append({
            'open': o, 'high': h, 'low': l, 'close': c, 'volume': v,
            'solid': solid, 'upper': upper, 'lower': lower,
            'is_yang': c > o, 'is_yin': c < o,
        })
    return result


def _check_szx(bar: dict, th: float = 0.001) -> bool:
    """检查是否为十字星"""
    total = bar['high'] - bar['low']
    if total == 0:
        return True
    return bar['solid'] / total < th


def jcc_san_xing_xian(freq: str, bars_raw: list, di: int = 1,
                       **kwargs) -> OrderedDict:
    """三星线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_三星线".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    all_szx = all(_check_szx(b) for b in attrs)
    if all_szx:
        v1 = "三星看多" if attrs[-1]['close'] > attrs[0]['close'] else "三星看空"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_ten_mo(freq: str, bars_raw: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """十字星形态（蜻蜓十字/墓碑十字/长腿十字）"""
    k1, k2, k3 = f"{freq}_D{di}K_十字星".split("_")
    if len(bars_raw) < di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-di:] if di == 1 else bars_raw[-di:-di + 1]
    attrs = _get_bar_attrs(recent[-1:])
    if not attrs:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    bar = attrs[0]
    if not _check_szx(bar):
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    if bar['lower'] > bar['upper'] * 2:
        v1 = "蜻蜓十字"
    elif bar['upper'] > bar['lower'] * 2:
        v1 = "墓碑十字"
    else:
        v1 = "长腿十字"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_wu_yun_gai_ding(freq: str, bars_raw: list, di: int = 1,
                         **kwargs) -> OrderedDict:
    """乌云盖顶形态"""
    k1, k2, k3 = f"{freq}_D{di}K_乌云盖顶".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs[0], attrs[1]
    prev_mid = (prev['open'] + prev['close']) / 2
    if (prev['is_yang'] and curr['is_yin']
            and curr['open'] > prev['high']
            and curr['close'] < prev_mid):
        v1 = "乌云盖顶"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_ci_tou(freq: str, bars_raw: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """刺透形态（乌云盖顶的反面）"""
    k1, k2, k3 = f"{freq}_D{di}K_刺透".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs[0], attrs[1]
    prev_mid = (prev['open'] + prev['close']) / 2
    if (prev['is_yin'] and curr['is_yang']
            and curr['open'] < prev['low']
            and curr['close'] > prev_mid):
        v1 = "刺透"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_san_fa(freq: str, bars_raw: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """三法形态（上升三法/下降三法）"""
    k1, k2, k3 = f"{freq}_D{di}K_三法A".split("_")
    for n in (5, 6, 7, 8):
        if len(bars_raw) < di + n:
            continue
        recent = bars_raw[-(di + n - 1):] if di == 1 else bars_raw[-(di + n):-di + 1]
        attrs = _get_bar_attrs(recent[-n:])
        if len(attrs) != n:
            continue
        first = attrs[0]
        last = attrs[-1]
        if (first['is_yang'] and last['is_yang']
                and last['close'] > first['high']
                and all(attrs[i]['close'] < attrs[i]['open'] for i in range(1, n - 1))
                and all(attrs[i]['high'] < first['high'] for i in range(1, n - 1))
                and all(attrs[i]['low'] > first['open'] for i in range(1, n - 1))):
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="上升三法", v2=f"{n}K")
        if (first['is_yin'] and last['is_yin']
                and last['close'] < first['low']
                and all(attrs[i]['close'] > attrs[i]['open'] for i in range(1, n - 1))
                and all(attrs[i]['low'] > first['low'] for i in range(1, n - 1))
                and all(attrs[i]['high'] < first['open'] for i in range(1, n - 1))):
            return create_single_signal(k1=k1, k2=k2, k3=k3, v1="下降三法", v2=f"{n}K")
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")


def jcc_xing_xian(freq: str, bars_raw: list, di: int = 1,
                  **kwargs) -> OrderedDict:
    """星线形态（晨星/暮星）"""
    k1, k2, k3 = f"{freq}_D{di}K_星线".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    b1, b2, b3 = attrs
    if (b1['is_yin'] and b1['solid'] > b2['solid'] * 2
            and b3['is_yang'] and b3['solid'] > b2['solid'] * 2
            and b2['close'] < b1['close']):
        v1 = "晨星"
    elif (b1['is_yang'] and b1['solid'] > b2['solid'] * 2
          and b3['is_yin'] and b3['solid'] > b2['solid'] * 2
          and b2['close'] > b1['close']):
        v1 = "暮星"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_fen_shou_xian(freq: str, bars_raw: list, di: int = 1,
                       **kwargs) -> OrderedDict:
    """分手线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_分手线".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    same_open = abs(prev['open'] - curr['open']) / max(prev['open'], 1) < 0.002
    if same_open and prev['is_yang'] and curr['is_yin']:
        v1 = "看空分手"
    elif same_open and prev['is_yin'] and curr['is_yang']:
        v1 = "看多分手"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_zhu_huo_xian(freq: str, bars_raw: list, di: int = 1,
                      **kwargs) -> OrderedDict:
    """抓获线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_抓获线".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    if (prev['is_yin'] and curr['is_yang']
            and curr['open'] <= prev['close']
            and curr['close'] >= prev['open']):
        v1 = "看多抓获"
    elif (prev['is_yang'] and curr['is_yin']
          and curr['open'] >= prev['close']
          and curr['close'] <= prev['open']):
        v1 = "看空抓获"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_yun_xian(freq: str, bars_raw: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """孕线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_孕线".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    prev_high = max(prev['open'], prev['close'])
    prev_low = min(prev['open'], prev['close'])
    curr_high = max(curr['open'], curr['close'])
    curr_low = min(curr['open'], curr['close'])
    if prev_high > curr_high and prev_low < curr_low:
        if prev['is_yang'] and curr['is_yin']:
            v1 = "看空孕线"
        elif prev['is_yin'] and curr['is_yang']:
            v1 = "看多孕线"
        else:
            v1 = "十字孕线"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_ping_tou(freq: str, bars_raw: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """平头形态"""
    k1, k2, k3 = f"{freq}_D{di}K_平头".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    th = max(prev['high'], 1) * 0.002
    if abs(prev['high'] - curr['high']) < th:
        v1 = "平头顶"
    elif abs(prev['low'] - curr['low']) < th:
        v1 = "平头底"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_two_crow(freq: str, bars_raw: list, di: int = 1,
                 **kwargs) -> OrderedDict:
    """两只乌鸦形态"""
    k1, k2, k3 = f"{freq}_D{di}K_两只乌鸦".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    b1, b2, b3 = attrs
    if (b1['is_yang'] and b2['is_yin'] and b3['is_yin']
            and b2['open'] > b1['close']
            and b3['open'] > b2['open']
            and b3['close'] < b2['close']):
        v1 = "两只乌鸦"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_three_crow(freq: str, bars_raw: list, di: int = 1,
                   **kwargs) -> OrderedDict:
    """三只乌鸦形态"""
    k1, k2, k3 = f"{freq}_D{di}K_三只乌鸦".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    if all(b['is_yin'] for b in attrs):
        v1 = "三只乌鸦"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_szx(freq: str, bars_raw: list, di: int = 1,
            th: float = 0.001, **kwargs) -> OrderedDict:
    """十字星形态"""
    k1, k2, k3 = f"{freq}_D{di}K_十字星".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    if _check_szx(curr, th):
        if prev['is_yang']:
            v1 = "阳后十字"
        elif prev['is_yin']:
            v1 = "阴后十字"
        else:
            v1 = "十字"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_san_szx(freq: str, bars_raw: list, di: int = 1,
                **kwargs) -> OrderedDict:
    """三星十字形态"""
    k1, k2, k3 = f"{freq}_D{di}K_三星十字".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    if all(_check_szx(b) for b in attrs):
        v1 = "三星十字"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_fan_ji_xian(freq: str, bars_raw: list, di: int = 1,
                    **kwargs) -> OrderedDict:
    """反击线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_反击线".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    same_close = abs(prev['close'] - curr['close']) / max(prev['close'], 1) < 0.002
    if same_close and prev['is_yang'] and curr['is_yin']:
        v1 = "看空反击"
    elif same_close and prev['is_yin'] and curr['is_yang']:
        v1 = "看多反击"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_shan_chun(freq: str, bi_list: list, di: int = 1,
                  **kwargs) -> OrderedDict:
    """山川形态（三山/三川）"""
    k1, k2, k3 = f"{freq}_D{di}B_山川形态".split("_")
    if len(bi_list) < di + 6:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    bis = bi_list[-(di + 5):] if di == 1 else bi_list[-(di + 5):-di + 1]
    if len(bis) < 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    b5, b4, b3, b2, b1 = bis[-5], bis[-4], bis[-3], bis[-2], bis[-1]
    b1_dir = b1.direction if hasattr(b1, 'direction') else None
    highs = [b.high if hasattr(b, 'high') else 0 for b in [b5, b3, b1]]
    lows = [b.low if hasattr(b, 'low') else 0 for b in [b5, b3, b1]]
    if (b1_dir == BiDirection.UP or b1_dir == "up") and np.var(highs) < 0.2:
        v1 = "三山"
    elif (b1_dir == BiDirection.DOWN or b1_dir == "down") and np.var(lows) < 0.2:
        v1 = "三川"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_gap_yin_yang(freq: str, bars_raw: list, di: int = 1,
                     **kwargs) -> OrderedDict:
    """跳空并列阴阳形态"""
    k1, k2, k3 = f"{freq}_D{di}K_并列阴阳".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    b3, b2, b1 = attrs
    if min(b1['low'], b2['low']) > b3['high']:
        if b2['is_yang'] and b1['is_yin'] and np.var([b1['solid'], b2['solid']]) < 0.2:
            v1 = "向上跳空"
        else:
            v1 = "其他"
    elif max(b1['high'], b2['high']) < b3['low']:
        if b2['is_yin'] and b1['is_yang'] and np.var([b1['solid'], b2['solid']]) < 0.2:
            v1 = "向下跳空"
        else:
            v1 = "其他"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_ta_xing(freq: str, bars_raw: list, di: int = 1,
                **kwargs) -> OrderedDict:
    """塔形形态"""
    k1, k2, k3 = f"{freq}_D{di}K_塔形".split("_")
    for n in (5, 6, 7, 8, 9):
        if len(bars_raw) < di + n:
            continue
        recent = bars_raw[-(di + n - 1):] if di == 1 else bars_raw[-(di + n):-di + 1]
        attrs = _get_bar_attrs(recent[-n:])
        if len(attrs) != n:
            continue
        first = attrs[0]
        last = attrs[-1]
        sorted_solid = sorted([b['solid'] for b in attrs])
        if min(first['solid'], last['solid']) >= sorted_solid[-2]:
            if first['is_yang'] and last['is_yin']:
                mid_highs = [b['high'] for b in attrs[1:-1]]
                if np.var(mid_highs) < 0.5:
                    return create_single_signal(k1=k1, k2=k2, k3=k3, v1="顶部", v2=f"{n}K")
            elif first['is_yin'] and last['is_yang']:
                mid_lows = [b['low'] for b in attrs[1:-1]]
                if np.var(mid_lows) < 0.5:
                    return create_single_signal(k1=k1, k2=k2, k3=k3, v1="底部", v2=f"{n}K")
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")


def jcc_zhuo_yao_dai_xian(freq: str, bars_raw: list, di: int = 1,
                           **kwargs) -> OrderedDict:
    """捉腰带线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_捉腰带线".split("_")
    if len(bars_raw) < di + 1:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-di:] if di == 1 else bars_raw[-di:-di + 1]
    attrs = _get_bar_attrs(recent[-1:])
    if not attrs:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    bar = attrs[0]
    total = bar['high'] - bar['low']
    if total == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    if abs(bar['open'] - bar['low']) / total < 0.05 and bar['is_yang'] and bar['solid'] / total > 0.6:
        v1 = "看多捉腰带"
    elif abs(bar['open'] - bar['high']) / total < 0.05 and bar['is_yin'] and bar['solid'] / total > 0.6:
        v1 = "看空捉腰带"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_hammer(freq: str, bars_raw: list, di: int = 1,
               **kwargs) -> OrderedDict:
    """锤子线/上吊线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_锤子线".split("_")
    if len(bars_raw) < di + 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 4):] if di == 1 else bars_raw[-(di + 4):-di + 1]
    attrs = _get_bar_attrs(recent[-5:])
    if len(attrs) < 5:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    bar = attrs[-1]
    total = bar['high'] - bar['low']
    if total == 0:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    if bar['lower'] > bar['solid'] * 2 and bar['upper'] < bar['solid'] * 0.5:
        prev_trend = attrs[0]['close'] > attrs[-2]['close']
        v1 = "上吊线" if prev_trend else "锤子线"
    elif bar['upper'] > bar['solid'] * 2 and bar['lower'] < bar['solid'] * 0.5:
        prev_trend = attrs[0]['close'] > attrs[-2]['close']
        v1 = "射击之星" if prev_trend else "倒锤子"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_engulfing(freq: str, bars_raw: list, di: int = 1,
                  **kwargs) -> OrderedDict:
    """吞没形态"""
    k1, k2, k3 = f"{freq}_D{di}K_吞没".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    prev_body = max(prev['open'], prev['close']) - min(prev['open'], prev['close'])
    curr_body = max(curr['open'], curr['close']) - min(curr['open'], curr['close'])

    if (prev['is_yin'] and curr['is_yang']
            and curr['open'] <= prev['close']
            and curr['close'] >= prev['open']
            and curr_body > prev_body):
        v1 = "看涨吞没"
    elif (prev['is_yang'] and curr['is_yin']
          and curr['open'] >= prev['close']
          and curr['close'] <= prev['open']
          and curr_body > prev_body):
        v1 = "看跌吞没"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_harami_cross(freq: str, bars_raw: list, di: int = 1,
                     **kwargs) -> OrderedDict:
    """十字孕线形态"""
    k1, k2, k3 = f"{freq}_D{di}K_十字孕线".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs
    prev_high = max(prev['open'], prev['close'])
    prev_low = min(prev['open'], prev['close'])
    curr_high = max(curr['open'], curr['close'])
    curr_low = min(curr['open'], curr['close'])

    is_szx = _check_szx(curr)
    if is_szx and prev_high > curr_high and prev_low < curr_low:
        if prev['is_yang']:
            v1 = "看空十字孕线"
        elif prev['is_yin']:
            v1 = "看多十字孕线"
        else:
            v1 = "十字孕线"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_three_white(freq: str, bars_raw: list, di: int = 1,
                    **kwargs) -> OrderedDict:
    """三白兵形态"""
    k1, k2, k3 = f"{freq}_D{di}K_三白兵".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if (all(b['is_yang'] for b in attrs)
            and attrs[2]['close'] > attrs[1]['close'] > attrs[0]['close']
            and attrs[2]['open'] > attrs[1]['open'] > attrs[0]['open']):
        has_upper = any(b['upper'] > b['solid'] * 0.3 for b in attrs)
        if has_upper:
            v1 = "受阻三白兵"
        else:
            v1 = "三白兵"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_three_black(freq: str, bars_raw: list, di: int = 1,
                    **kwargs) -> OrderedDict:
    """三黑鸦形态"""
    k1, k2, k3 = f"{freq}_D{di}K_三黑鸦".split("_")
    if len(bars_raw) < di + 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 2):] if di == 1 else bars_raw[-(di + 2):-di + 1]
    attrs = _get_bar_attrs(recent[-3:])
    if len(attrs) < 3:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")

    if (all(b['is_yin'] for b in attrs)
            and attrs[2]['close'] < attrs[1]['close'] < attrs[0]['close']
            and attrs[2]['open'] < attrs[1]['open'] < attrs[0]['open']):
        has_lower = any(b['lower'] > b['solid'] * 0.3 for b in attrs)
        if has_lower:
            v1 = "受撑三黑鸦"
        else:
            v1 = "三黑鸦"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)


def jcc_kicking(freq: str, bars_raw: list, di: int = 1,
                **kwargs) -> OrderedDict:
    """跳空缺口形态"""
    k1, k2, k3 = f"{freq}_D{di}K_跳空缺口".split("_")
    if len(bars_raw) < di + 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    recent = bars_raw[-(di + 1):] if di == 1 else bars_raw[-(di + 1):-di + 1]
    attrs = _get_bar_attrs(recent[-2:])
    if len(attrs) < 2:
        return create_single_signal(k1=k1, k2=k2, k3=k3, v1="其他")
    prev, curr = attrs

    if curr['low'] > prev['high']:
        v1 = "看多跳空"
    elif curr['high'] < prev['low']:
        v1 = "看空跳空"
    else:
        v1 = "其他"
    return create_single_signal(k1=k1, k2=k2, k3=k3, v1=v1)
