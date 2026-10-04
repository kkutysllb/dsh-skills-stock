#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论枚举定义
参考Vespa314/chan.py的枚举设计，定义缠论分析中的核心枚举类型
"""

from enum import Enum, IntEnum
from typing import Dict, List


class TimeLevel(Enum):
    """
    时间级别枚举
    支持从分钟级到年级的多种时间周期
    """
    # 分钟级别
    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"
    MIN_90 = "90min"
    MIN_120 = "120min"

    # 日级别及以上
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    @classmethod
    def get_minute_levels(cls) -> List['TimeLevel']:
        """获取所有分钟级别"""
        return [cls.MIN_1, cls.MIN_5, cls.MIN_15, cls.MIN_30, cls.MIN_60, cls.MIN_90, cls.MIN_120]

    @classmethod
    def get_day_levels(cls) -> List['TimeLevel']:
        """获取日级别及以上"""
        return [cls.DAILY, cls.WEEKLY, cls.MONTHLY, cls.QUARTERLY, cls.YEARLY]

    @classmethod
    def get_supported_levels(cls) -> List['TimeLevel']:
        """获取当前项目支持的级别"""
        return [cls.MIN_5, cls.MIN_15, cls.MIN_30, cls.MIN_60, cls.MIN_90, cls.MIN_120,
                cls.DAILY, cls.WEEKLY, cls.MONTHLY]

    def get_level_weight(self) -> int:
        """获取级别权重，用于级别比较"""
        weights = {
            self.MIN_1: 1,
            self.MIN_5: 5,
            self.MIN_15: 15,
            self.MIN_30: 30,
            self.MIN_60: 60,
            self.MIN_90: 90,
            self.MIN_120: 120,
            self.DAILY: 1440,      # 24*60
            self.WEEKLY: 10080,    # 7*24*60
            self.MONTHLY: 43200,   # 30*24*60
            self.QUARTERLY: 129600, # 90*24*60
            self.YEARLY: 525600    # 365*24*60
        }
        return weights.get(self, 0)
    
    def is_higher_than(self, other: 'TimeLevel') -> bool:
        """判断是否比另一个级别更高"""
        return self.get_level_weight() > other.get_level_weight()
    
    def __str__(self) -> str:
        return self.value


class FenXingType(Enum):
    """
    分型类型枚举
    缠论中的顶分型和底分型
    """
    TOP = "top"        # 顶分型
    BOTTOM = "bottom"  # 底分型
    
    def is_top(self) -> bool:
        """是否为顶分型"""
        return self == self.TOP
    
    def is_bottom(self) -> bool:
        """是否为底分型"""
        return self == self.BOTTOM
    
    def opposite(self) -> 'FenXingType':
        """获取相反类型"""
        return self.BOTTOM if self == self.TOP else self.TOP
    
    def __str__(self) -> str:
        return "顶分型" if self == self.TOP else "底分型"


class BiDirection(Enum):
    """
    笔方向枚举
    """
    UP = "up"      # 向上笔
    DOWN = "down"  # 向下笔
    
    def is_up(self) -> bool:
        """是否为向上笔"""  
        return self == self.UP
    
    def is_down(self) -> bool:
        """是否为向下笔"""
        return self == self.DOWN
    
    def opposite(self) -> 'BiDirection':
        """获取相反方向"""
        return self.DOWN if self == self.UP else self.UP
    
    @classmethod
    def from_fenxing_types(cls, start_type: FenXingType, end_type: FenXingType) -> 'BiDirection':
        """根据起始和结束分型类型确定笔方向"""
        if start_type == FenXingType.BOTTOM and end_type == FenXingType.TOP:
            return cls.UP
        elif start_type == FenXingType.TOP and end_type == FenXingType.BOTTOM:
            return cls.DOWN
        else:
            raise ValueError(f"无法从分型类型确定笔方向: {start_type} -> {end_type}")
    
    def __str__(self) -> str:
        return "向上笔" if self == self.UP else "向下笔"


class SegDirection(Enum):
    """
    线段方向枚举
    """
    UP = "up"      # 向上线段
    DOWN = "down"  # 向下线段
    
    def is_up(self) -> bool:
        """是否为向上线段"""
        return self == self.UP
    
    def is_down(self) -> bool:
        """是否为向下线段"""
        return self == self.DOWN
    
    def opposite(self) -> 'SegDirection':
        """获取相反方向"""
        return self.DOWN if self == self.UP else self.UP
    
    @classmethod
    def from_bi_direction(cls, bi_direction: BiDirection) -> 'SegDirection':
        """从笔方向转换为线段方向"""
        return cls.UP if bi_direction == BiDirection.UP else cls.DOWN
    
    def __str__(self) -> str:
        return "向上线段" if self == self.UP else "向下线段"


class ZhongShuType(Enum):
    """
    中枢类型枚举  
    """
    # 基础类型
    NORMAL = "normal"          # 普通中枢
    EXTENDED = "extended"      # 扩展中枢
    COMPLEX = "complex"        # 复杂中枢
    
    # 特殊类型
    TREND = "trend"            # 趋势中枢
    CONSOLIDATION = "consolidation"  # 盘整中枢
    
    def __str__(self) -> str:
        type_names = {
            self.NORMAL: "普通中枢",
            self.EXTENDED: "扩展中枢", 
            self.COMPLEX: "复杂中枢",
            self.TREND: "趋势中枢",
            self.CONSOLIDATION: "盘整中枢"
        }
        return type_names.get(self, self.value)


class AnalysisResult(IntEnum):
    """
    分析结果状态枚举
    """
    SUCCESS = 0          # 成功
    NO_DATA = 1          # 无数据
    INSUFFICIENT_DATA = 2 # 数据不足
    INVALID_DATA = 3     # 数据无效
    CALCULATION_ERROR = 4 # 计算错误
    UNKNOWN_ERROR = 5    # 未知错误
    
    def is_success(self) -> bool:
        """是否成功"""
        return self == self.SUCCESS
    
    def is_error(self) -> bool:
        """是否错误"""
        return self != self.SUCCESS


class BuySellPointType(Enum):
    """
    买卖点类型枚举
    """
    # 买点
    BUY_1 = "1buy"    # 一类买点
    BUY_2 = "2buy"    # 二类买点  
    BUY_3 = "3buy"    # 三类买点
    
    # 卖点
    SELL_1 = "1sell"  # 一类卖点
    SELL_2 = "2sell"  # 二类卖点
    SELL_3 = "3sell"  # 三类卖点
    
    def is_buy(self) -> bool:
        """是否为买点"""
        return self in [self.BUY_1, self.BUY_2, self.BUY_3]
    
    def is_sell(self) -> bool:
        """是否为卖点"""
        return self in [self.SELL_1, self.SELL_2, self.SELL_3]
    
    def get_level(self) -> int:
        """获取买卖点级别(1-3)"""
        return int(self.value[0])
    
    def __str__(self) -> str:
        type_names = {
            self.BUY_1: "一类买点",
            self.BUY_2: "二类买点", 
            self.BUY_3: "三类买点",
            self.SELL_1: "一类卖点",
            self.SELL_2: "二类卖点",
            self.SELL_3: "三类卖点"
        }
        return type_names.get(self, self.value)


class DivergenceType(Enum):
    """
    背驰类型枚举
    """
    NONE = "none"              # 无背驰
    TOP_DIVERGENCE = "top"     # 顶背驰  
    BOTTOM_DIVERGENCE = "bottom" # 底背驰
    
    def is_divergence(self) -> bool:
        """是否存在背驰"""
        return self != self.NONE
    
    def __str__(self) -> str:
        type_names = {
            self.NONE: "无背驰",
            self.TOP_DIVERGENCE: "顶背驰",
            self.BOTTOM_DIVERGENCE: "底背驰"
        }
        return type_names.get(self, self.value)


# 级别映射关系配置
LEVEL_MAPPING_RATIOS: Dict[TimeLevel, Dict[TimeLevel, int]] = {
    TimeLevel.DAILY: {
        TimeLevel.MIN_30: 16,    # 1日线 ≈ 16个30分钟
        TimeLevel.MIN_5: 96      # 1日线 ≈ 96个5分钟
    },
    TimeLevel.MIN_30: {
        TimeLevel.MIN_5: 6       # 1个30分钟 = 6个5分钟
    }
}


def get_level_ratio(higher_level: TimeLevel, lower_level: TimeLevel) -> int:
    """
    获取两个级别之间的比例关系
    
    Args:
        higher_level: 更高级别
        lower_level: 更低级别
        
    Returns:
        比例倍数，如果无映射关系则返回1
    """
    return LEVEL_MAPPING_RATIOS.get(higher_level, {}).get(lower_level, 1)


def validate_level_sequence(levels: List[TimeLevel]) -> bool:
    """
    验证级别序列是否按从高到低排列
    
    Args:
        levels: 级别列表
        
    Returns:
        是否有效
    """
    if len(levels) <= 1:
        return True
    
    for i in range(len(levels) - 1):
        if not levels[i].is_higher_than(levels[i + 1]):
            return False
    
    return True