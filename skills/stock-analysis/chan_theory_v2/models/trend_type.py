#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论走势类型划分模块

基于缠中说禅理论，自动划分走势类型：
- 上涨走势：至少2个依次升高的中枢
- 下跌走势：至少2个依次降低的中枢
- 盘整走势：仅1个中枢或中枢无方向性排列

缠论原文定义：
"走势分为上涨、下跌、盘整三种基本类型。
上涨：最近一个高点比前一高，且最近一个低点比前一低点高。
下跌：最近一个高点比前一高点低，且最近一个低点比前一低点低。
盘整：最近一个高点比前一高点高，且最近一个低点比前一低点低；或者反之。"

实际可操作定义（基于中枢排列）：
- 上涨走势：至少2个中枢，且后一个中枢的区间高于前一个
- 下跌走势：至少2个中枢，且后一个中枢的区间低于前一个
- 盘整走势：中枢无方向性排列或仅有1个中枢
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from .enums import TimeLevel, SegDirection
from .seg import Seg, SegList
from .zhongshu import ZhongShu, ZhongShuList


class TrendType(Enum):
    """走势类型枚举"""
    UP_TREND = "up_trend"           # 上涨走势
    DOWN_TREND = "down_trend"       # 下跌走势
    CONSOLIDATION = "consolidation"  # 盘整走势
    UNKNOWN = "unknown"             # 数据不足，无法判定

    @property
    def is_trend(self) -> bool:
        """是否为趋势（上涨或下跌）"""
        return self in (self.UP_TREND, self.DOWN_TREND)

    @property
    def is_up(self) -> bool:
        """是否为上涨走势"""
        return self == self.UP_TREND

    @property
    def is_down(self) -> bool:
        """是否为下跌走势"""
        return self == self.DOWN_TREND

    def __str__(self) -> str:
        names = {
            self.UP_TREND: "上涨走势",
            self.DOWN_TREND: "下跌走势",
            self.CONSOLIDATION: "盘整走势",
            self.UNKNOWN: "未判定",
        }
        return names.get(self, self.value)


@dataclass
class TrendSegment:
    """走势段：一段具有明确走势类型的行情区间"""
    trend_type: TrendType
    start_index: int           # 起始线段索引
    end_index: int             # 结束线段索引
    start_price: float         # 起始价格
    end_price: float           # 结束价格
    zhongshu_count: int = 0    # 包含的中枢数量
    strength: float = 0.0      # 走势强度 0-1

    @property
    def price_change(self) -> float:
        """价格变化"""
        return self.end_price - self.start_price

    @property
    def price_change_pct(self) -> float:
        """价格变化百分比"""
        if self.start_price == 0:
            return 0.0
        return (self.end_price - self.start_price) / self.start_price * 100


@dataclass
class TrendAnalysisResult:
    """走势类型分析结果"""
    trend_type: TrendType = TrendType.UNKNOWN
    trend_segments: List[TrendSegment] = field(default_factory=list)
    current_trend: Optional[TrendSegment] = None     # 当前走势段
    trend_strength: float = 0.0                       # 整体走势强度
    zhongshu_count: int = 0                           # 中枢总数
    trend_zhongshu_count: int = 0                     # 趋势中的中枢数
    latest_price: float = 0.0                         # 最新K线收盘价
    data_start_price: float = 0.0                     # 数据起始价（第一根K线开盘价）

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            'trend_type': self.trend_type.value,
            'trend_type_cn': str(self.trend_type),
            'trend_strength': round(self.trend_strength, 3),
            'zhongshu_count': self.zhongshu_count,
            'trend_zhongshu_count': self.trend_zhongshu_count,
            'latest_price': round(self.latest_price, 2),
            'data_start_price': round(self.data_start_price, 2),
            'trend_segments': [
                {
                    'type': seg.trend_type.value,
                    'type_cn': str(seg.trend_type),
                    'start_price': round(seg.start_price, 2),
                    'end_price': round(seg.end_price, 2),
                    'change_pct': round(seg.price_change_pct, 2),
                    'zhongshu_count': seg.zhongshu_count,
                    'strength': round(seg.strength, 3),
                }
                for seg in self.trend_segments
            ],
            'current_trend': {
                'type': self.current_trend.trend_type.value,
                'type_cn': str(self.current_trend.trend_type),
                'start_price': round(self.current_trend.start_price, 2),
                'end_price': round(self.current_trend.end_price, 2),
                'latest_price': round(self.latest_price, 2),
                'change_pct': round(self.current_trend.price_change_pct, 2),
                'latest_change_pct': round((self.latest_price - self.current_trend.start_price) / self.current_trend.start_price * 100, 2) if self.current_trend.start_price > 0 else 0.0,
                'zhongshu_count': self.current_trend.zhongshu_count,
                'strength': round(self.current_trend.strength, 3),
            } if self.current_trend else None,
        }


class TrendTypeAnalyzer:
    """走势类型分析器"""

    def analyze(self, segs: SegList, zhongshus: ZhongShuList,
                 latest_price: float = 0.0, data_start_price: float = 0.0) -> TrendAnalysisResult:
        """
        分析走势类型

        Args:
            segs: 线段列表
            zhongshus: 中枢列表

        Returns:
            走势类型分析结果
        """
        result = TrendAnalysisResult()
        result.zhongshu_count = len(zhongshus)
        result.latest_price = latest_price
        result.data_start_price = data_start_price

        # 数据不足，无法判定
        if len(zhongshus) == 0:
            result.trend_type = TrendType.UNKNOWN
            return result

        # 仅1个中枢 → 盘整走势
        if len(zhongshus) == 1:
            result.trend_type = TrendType.CONSOLIDATION
            result.trend_zhongshu_count = 1
            result.trend_strength = self._calculate_consolidation_strength(zhongshus[0], segs)
            result.trend_segments = self._build_trend_segments(segs, zhongshus)
            result.current_trend = result.trend_segments[-1] if result.trend_segments else None
            return result

        # 2个及以上中枢：判断中枢排列方向
        trend_type = self._judge_trend_by_zhongshus(zhongshus)
        result.trend_type = trend_type

        # 计算趋势中的中枢数（方向一致的中枢）
        result.trend_zhongshu_count = self._count_trend_zhongshus(zhongshus, trend_type)

        # 计算走势强度
        result.trend_strength = self._calculate_trend_strength(zhongshus, trend_type)

        # 划分走势段
        result.trend_segments = self._build_trend_segments(segs, zhongshus)
        result.current_trend = result.trend_segments[-1] if result.trend_segments else None

        return result

    def _judge_trend_by_zhongshus(self, zhongshus: ZhongShuList) -> TrendType:
        """
        根据中枢排列判断走势类型

        规则：
        - 上涨走势：中枢依次升高（后一个中枢的下沿 > 前一个中枢的下沿）
        - 下跌走势：中枢依次降低（后一个中枢的上沿 < 前一个中枢的上沿）
        - 盘整走势：中枢无方向性排列
        """
        if len(zhongshus) < 2:
            return TrendType.CONSOLIDATION

        # 比较相邻中枢的高低点
        up_count = 0   # 后中枢高于前中枢的次数
        down_count = 0  # 后中枢低于前中枢的次数

        for i in range(1, len(zhongshus)):
            prev_zs = zhongshus[i - 1]
            curr_zs = zhongshus[i]

            prev_low = prev_zs.low if hasattr(prev_zs, 'low') else getattr(prev_zs, 'zg', 0)
            curr_low = curr_zs.low if hasattr(curr_zs, 'low') else getattr(curr_zs, 'zg', 0)
            prev_high = prev_zs.high if hasattr(prev_zs, 'high') else getattr(prev_zs, 'zd', 0)
            curr_high = curr_zs.high if hasattr(curr_zs, 'high') else getattr(curr_zs, 'zd', 0)

            # 用中枢下沿比较
            if curr_low > prev_low:
                up_count += 1
            elif curr_high < prev_high:
                down_count += 1

        total = up_count + down_count
        if total == 0:
            return TrendType.CONSOLIDATION

        # 简单多数投票
        if up_count > down_count:
            return TrendType.UP_TREND
        elif down_count > up_count:
            return TrendType.DOWN_TREND
        else:
            return TrendType.CONSOLIDATION

    def _count_trend_zhongshus(self, zhongshus: ZhongShuList, trend_type: TrendType) -> int:
        """统计趋势方向一致的中枢数量"""
        if trend_type == TrendType.CONSOLIDATION:
            return len(zhongshus)

        count = 1  # 至少第一个中枢算
        for i in range(1, len(zhongshus)):
            prev_zs = zhongshus[i - 1]
            curr_zs = zhongshus[i]

            prev_low = prev_zs.low if hasattr(prev_zs, 'low') else 0
            curr_low = curr_zs.low if hasattr(curr_zs, 'low') else 0
            prev_high = prev_zs.high if hasattr(prev_zs, 'high') else 0
            curr_high = curr_zs.high if hasattr(curr_zs, 'high') else 0

            if trend_type == TrendType.UP_TREND and curr_low > prev_low:
                count += 1
            elif trend_type == TrendType.DOWN_TREND and curr_high < prev_high:
                count += 1

        return count

    def _calculate_trend_strength(self, zhongshus: ZhongShuList, trend_type: TrendType) -> float:
        """
        计算走势强度

        基于中枢排列一致性：
        - 所有相邻中枢方向一致 → 强度 0.8-1.0
        - 大部分方向一致 → 强度 0.5-0.8
        - 方向不明确 → 强度 0.0-0.5
        """
        if len(zhongshus) < 2:
            return 0.3  # 盘整默认强度

        total_pairs = len(zhongshus) - 1
        consistent = 0

        for i in range(1, len(zhongshus)):
            prev_zs = zhongshus[i - 1]
            curr_zs = zhongshus[i]

            prev_low = prev_zs.low if hasattr(prev_zs, 'low') else 0
            curr_low = curr_zs.low if hasattr(curr_zs, 'low') else 0
            prev_high = prev_zs.high if hasattr(prev_zs, 'high') else 0
            curr_high = curr_zs.high if hasattr(curr_zs, 'high') else 0

            if trend_type == TrendType.UP_TREND and curr_low > prev_low:
                consistent += 1
            elif trend_type == TrendType.DOWN_TREND and curr_high < prev_high:
                consistent += 1
            elif trend_type == TrendType.CONSOLIDATION:
                consistent += 0.5

        base_strength = consistent / total_pairs if total_pairs > 0 else 0.3

        # 中枢数量加成
        bonus = min(len(zhongshus) * 0.05, 0.2)

        return min(base_strength + bonus, 1.0)

    def _calculate_consolidation_strength(self, zs: ZhongShu, segs: SegList) -> float:
        """计算盘整走势强度"""
        # 盘整强度基于中枢的振幅和线段数
        zs_range = zs.high - zs.low if hasattr(zs, 'high') and hasattr(zs, 'low') else 0
        if zs_range == 0 or not hasattr(zs, 'low') or zs.low == 0:
            return 0.3
        amplitude = zs_range / zs.low
        # 振幅越小，盘整越紧凑，强度越高
        return max(0.1, min(1.0 - amplitude, 0.7))

    def _build_trend_segments(self, segs: SegList, zhongshus: ZhongShuList) -> List[TrendSegment]:
        """
        划分走势段

        将线段按中枢划分区间，每个区间判断走势类型
        """
        if not zhongshus or not segs:
            return []

        segments = []

        # 简单实现：按中枢的位置将线段分组
        if len(zhongshus) == 1:
            # 单中枢 → 整体盘整
            zs = zhongshus[0]
            start_idx = 0
            end_idx = len(segs) - 1
            segments.append(TrendSegment(
                trend_type=TrendType.CONSOLIDATION,
                start_index=start_idx,
                end_index=end_idx,
                start_price=segs[0].start_price if hasattr(segs[0], 'start_price') else 0,
                end_price=segs[-1].end_price if hasattr(segs[-1], 'end_price') else 0,
                zhongshu_count=1,
                strength=0.3,
            ))
        else:
            # 多中枢：每2个相邻中枢之间判断走势类型
            for i in range(len(zhongshus) - 1):
                prev_zs = zhongshus[i]
                curr_zs = zhongshus[i + 1]

                prev_low = prev_zs.low if hasattr(prev_zs, 'low') else 0
                curr_low = curr_zs.low if hasattr(curr_zs, 'low') else 0
                prev_high = prev_zs.high if hasattr(prev_zs, 'high') else 0
                curr_high = curr_zs.high if hasattr(curr_zs, 'high') else 0

                if curr_low > prev_low:
                    seg_type = TrendType.UP_TREND
                elif curr_high < prev_high:
                    seg_type = TrendType.DOWN_TREND
                else:
                    seg_type = TrendType.CONSOLIDATION

                # 找对应的线段范围
                start_idx = max(0, i)
                end_idx = min(len(segs) - 1, i + 2)

                start_price = segs[start_idx].start_price if start_idx < len(segs) and hasattr(segs[start_idx], 'start_price') else prev_low
                end_price = segs[end_idx].end_price if end_idx < len(segs) and hasattr(segs[end_idx], 'end_price') else curr_high

                segments.append(TrendSegment(
                    trend_type=seg_type,
                    start_index=start_idx,
                    end_index=end_idx,
                    start_price=start_price,
                    end_price=end_price,
                    zhongshu_count=2,
                    strength=0.5,
                ))

        return segments
