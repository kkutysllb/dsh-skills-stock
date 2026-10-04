#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论分型数据模型
参考Vespa314/chan.py的分型设计，实现标准的分型识别和管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Iterator
from .enums import FenXingType, TimeLevel
from .kline import KLine


@dataclass
class FenXing:
    """
    分型数据模型
    代表缠论中的顶分型或底分型
    """
    # 基础信息
    kline: KLine                     # 分型所在的K线
    fenxing_type: FenXingType       # 分型类型（顶/底）
    index: int                       # 在K线序列中的索引位置
    
    # 分型特征
    strength: float = 0.0            # 分型强度（0-1）
    confidence: float = 0.0          # 分型置信度（0-1）
    
    # 确认信息
    is_confirmed: bool = False       # 是否已确认
    confirm_kline_count: int = 0     # 确认用的K线数量
    
    # 分型环境
    left_klines: List[KLine] = field(default_factory=list)   # 左侧K线
    right_klines: List[KLine] = field(default_factory=list)  # 右侧K线
    
    # 扩展信息
    volume_ratio: float = 1.0        # 成交量比例
    gap_from_prev: float = 0.0       # 与前一个分型的价格间距
    
    def __post_init__(self):
        """初始化后处理"""
        self._validate()
    
    def _validate(self) -> None:
        """数据有效性验证"""
        if not isinstance(self.kline, KLine):
            raise ValueError("分型必须关联一个有效的K线")
        if self.index < 0:
            raise ValueError("分型索引不能为负数")
        if not (0 <= self.strength <= 1):
            raise ValueError("分型强度必须在[0,1]范围内")
        if not (0 <= self.confidence <= 1):
            raise ValueError("分型置信度必须在[0,1]范围内")
    
    @property
    def timestamp(self) -> datetime:
        """分型时间"""
        return self.kline.timestamp
    
    @property
    def price(self) -> float:
        """分型价格"""
        return self.kline.high if self.fenxing_type == FenXingType.TOP else self.kline.low
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """分型级别"""
        return self.kline.level
    
    @property
    def is_top(self) -> bool:
        """是否为顶分型"""
        return self.fenxing_type == FenXingType.TOP
    
    @property
    def is_bottom(self) -> bool:
        """是否为底分型"""
        return self.fenxing_type == FenXingType.BOTTOM
    
    @property
    def window_size(self) -> int:
        """分型识别窗口大小"""
        return len(self.left_klines) + 1 + len(self.right_klines)
    
    def get_opposite_type(self) -> FenXingType:
        """获取相反的分型类型"""
        return self.fenxing_type.opposite()
    
    def calculate_strength(self) -> float:
        """
        计算分型强度
        基于分型与周围K线的价格关系
        """
        if not self.left_klines or not self.right_klines:
            return 0.0
        
        if self.is_top:
            # 顶分型：计算相对于左右K线最高价的优势
            left_max = max(k.high for k in self.left_klines)
            right_max = max(k.high for k in self.right_klines)
            surrounding_max = max(left_max, right_max)
            
            if surrounding_max > 0:
                self.strength = max(0, (self.price - surrounding_max) / surrounding_max)
            else:
                self.strength = 0.0
        else:
            # 底分型：计算相对于左右K线最低价的优势
            left_min = min(k.low for k in self.left_klines)
            right_min = min(k.low for k in self.right_klines)
            surrounding_min = min(left_min, right_min)
            
            if surrounding_min > 0 and self.price > 0:
                self.strength = max(0, (surrounding_min - self.price) / surrounding_min)
            else:
                self.strength = 0.0
        
        return self.strength
    
    def calculate_volume_ratio(self) -> float:
        """
        计算分型处的成交量比例
        与周围K线成交量的对比
        """
        if not self.left_klines or not self.right_klines:
            return 1.0
        
        # 计算周围K线的平均成交量
        surrounding_volumes = [k.volume for k in self.left_klines + self.right_klines]
        avg_volume = sum(surrounding_volumes) / len(surrounding_volumes) if surrounding_volumes else 1
        
        if avg_volume > 0:
            self.volume_ratio = self.kline.volume / avg_volume
        else:
            self.volume_ratio = 1.0
        
        return self.volume_ratio
    
    def update_confirmation(self, confirm_klines: int) -> None:
        """
        更新分型确认状态
        
        Args:
            confirm_klines: 确认K线数量
        """
        self.confirm_kline_count = confirm_klines
        # 通常需要至少1根K线确认，可以根据需要调整
        self.is_confirmed = confirm_klines >= 1
        
        # 根据确认K线数量调整置信度
        if confirm_klines <= 0:
            self.confidence = 0.0
        elif confirm_klines == 1:
            self.confidence = 0.6
        elif confirm_klines == 2:
            self.confidence = 0.8
        else:
            self.confidence = 1.0
    
    def is_valid_fenxing(self, min_strength: float = 0.001, strict_mode: bool = None) -> bool:
        """
        判断是否为有效分型
        
        Args:
            min_strength: 最小强度要求
            strict_mode: 是否使用严格模式，None时使用默认设置
            
        Returns:
            是否有效
        """
        # 基础检查
        if self.strength < min_strength:
            return False
        
        # 检查左右K线是否足够
        if len(self.left_klines) == 0 or len(self.right_klines) == 0:
            return False
        
        # 如果未指定严格模式，尝试从分型上下文判断
        if strict_mode is None:
            # 这里简化处理，通常分型都应该是有效的
            return True
        
        # 分型检查：根据模式决定严格程度
        if strict_mode:
            # 严格模式：分型价格必须严格高于/低于左右所有K线
            if self.is_top:
                for k in self.left_klines + self.right_klines:
                    if k.high >= self.price:
                        return False
            else:
                for k in self.left_klines + self.right_klines:
                    if k.low <= self.price:
                        return False
        else:
            # 宽松模式：允许相等，但不能被超越
            if self.is_top:
                for k in self.left_klines + self.right_klines:
                    if k.high > self.price:
                        return False
            else:
                for k in self.left_klines + self.right_klines:
                    if k.low < self.price:
                        return False
        
        return True
    
    def distance_to(self, other: 'FenXing') -> float:
        """
        计算与另一个分型的价格距离（绝对值）
        
        Args:
            other: 另一个分型
            
        Returns:
            价格距离
        """
        return abs(self.price - other.price)
    
    def price_ratio_to(self, other: 'FenXing') -> float:
        """
        计算与另一个分型的价格比例
        
        Args:
            other: 另一个分型
            
        Returns:
            价格比例 (self.price / other.price)
        """
        if other.price == 0:
            return float('inf') if self.price > 0 else 1.0
        return self.price / other.price
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'fenxing_type': self.fenxing_type.value,
            'index': self.index,
            'strength': self.strength,
            'confidence': self.confidence,
            'is_confirmed': self.is_confirmed,
            'confirm_kline_count': self.confirm_kline_count,
            'volume_ratio': self.volume_ratio,
            'gap_from_prev': self.gap_from_prev,
            'level': self.level.value if self.level else None,
            'window_size': self.window_size
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.fenxing_type}@{self.price:.2f}"
                f"({self.timestamp.strftime('%m-%d %H:%M')}, "
                f"强度:{self.strength:.3f}, 确认:{self.is_confirmed})")
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if not isinstance(other, FenXing):
            return False
        return (self.timestamp == other.timestamp and
                self.fenxing_type == other.fenxing_type and
                abs(self.price - other.price) < 1e-6)
    
    def __lt__(self, other) -> bool:
        """小于比较（按时间排序）"""
        if not isinstance(other, FenXing):
            return NotImplemented
        return self.timestamp < other.timestamp


class FenXingList:
    """
    分型列表容器
    管理一系列分型，提供查询、过滤、统计等功能
    """
    
    def __init__(self, fenxings: Optional[List[FenXing]] = None, level: Optional[TimeLevel] = None):
        """
        初始化分型列表
        
        Args:
            fenxings: 分型列表
            level: 时间级别
        """
        self._fenxings: List[FenXing] = fenxings or []
        self._level = level
        
        # 按时间排序
        self._fenxings.sort(key=lambda f: f.timestamp)
    
    def __len__(self) -> int:
        """分型数量"""
        return len(self._fenxings)
    
    def __getitem__(self, index: int) -> FenXing:
        """索引访问"""
        return self._fenxings[index]
    
    def __iter__(self) -> Iterator[FenXing]:
        """迭代器"""
        return iter(self._fenxings)
    
    @property
    def fenxings(self) -> List[FenXing]:
        """获取分型列表"""
        return self._fenxings
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """获取时间级别"""
        return self._level
    
    def append(self, fenxing: FenXing) -> None:
        """添加分型并保持时间顺序"""
        self._fenxings.append(fenxing)
        self._fenxings.sort(key=lambda f: f.timestamp)
    
    def extend(self, fenxings: List[FenXing]) -> None:
        """批量添加分型"""
        self._fenxings.extend(fenxings)
        self._fenxings.sort(key=lambda f: f.timestamp)
    
    def clear(self) -> None:
        """清空分型列表"""
        self._fenxings.clear()
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._fenxings) == 0
    
    def get_tops(self) -> List[FenXing]:
        """获取所有顶分型"""
        return [f for f in self._fenxings if f.is_top]
    
    def get_bottoms(self) -> List[FenXing]:
        """获取所有底分型"""
        return [f for f in self._fenxings if f.is_bottom]
    
    def get_confirmed(self) -> List[FenXing]:
        """获取所有已确认的分型"""
        return [f for f in self._fenxings if f.is_confirmed]
    
    def get_by_type(self, fenxing_type: FenXingType) -> List[FenXing]:
        """按类型获取分型"""
        return [f for f in self._fenxings if f.fenxing_type == fenxing_type]
    
    def filter_by_strength(self, min_strength: float) -> List[FenXing]:
        """按强度过滤分型"""
        return [f for f in self._fenxings if f.strength >= min_strength]
    
    def filter_by_time_range(self, start_time: datetime, end_time: datetime) -> List[FenXing]:
        """按时间范围过滤分型"""
        return [f for f in self._fenxings if start_time <= f.timestamp <= end_time]
    
    def get_latest(self, count: int = 1) -> List[FenXing]:
        """获取最新的N个分型"""
        return self._fenxings[-count:] if len(self._fenxings) >= count else self._fenxings
    
    def get_earliest(self, count: int = 1) -> List[FenXing]:
        """获取最早的N个分型"""
        return self._fenxings[:count] if len(self._fenxings) >= count else self._fenxings
    
    def optimize_consecutive_same_type(self) -> 'FenXingList':
        """
        优化连续同类型分型
        连续的顶分型只保留最高的，连续的底分型只保留最低的
        """
        if len(self._fenxings) <= 1:
            return FenXingList(self._fenxings.copy(), self._level)
        
        optimized = []
        i = 0
        
        while i < len(self._fenxings):
            current_fenxing = self._fenxings[i]
            same_type_group = [current_fenxing]
            
            # 收集连续的同类型分型
            j = i + 1
            while j < len(self._fenxings) and self._fenxings[j].fenxing_type == current_fenxing.fenxing_type:
                same_type_group.append(self._fenxings[j])
                j += 1
            
            # 从同类型组中选择最极端的分型
            if current_fenxing.is_top:
                # 顶分型：选择价格最高的
                best_fenxing = max(same_type_group, key=lambda f: f.price)
            else:
                # 底分型：选择价格最低的
                best_fenxing = min(same_type_group, key=lambda f: f.price)
            
            optimized.append(best_fenxing)
            i = j
        
        return FenXingList(optimized, self._level)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取分型统计信息"""
        if self.is_empty():
            return {
                'total_count': 0,
                'top_count': 0,
                'bottom_count': 0,
                'confirmed_count': 0,
                'avg_strength': 0.0,
                'avg_confidence': 0.0
            }
        
        tops = self.get_tops()
        bottoms = self.get_bottoms()
        confirmed = self.get_confirmed()
        
        return {
            'total_count': len(self._fenxings),
            'top_count': len(tops),
            'bottom_count': len(bottoms),
            'confirmed_count': len(confirmed),
            'confirmation_rate': len(confirmed) / len(self._fenxings),
            'avg_strength': sum(f.strength for f in self._fenxings) / len(self._fenxings),
            'avg_confidence': sum(f.confidence for f in self._fenxings) / len(self._fenxings),
            'price_range': (
                min(f.price for f in self._fenxings),
                max(f.price for f in self._fenxings)
            ) if self._fenxings else (0, 0),
            'time_range': (
                min(f.timestamp for f in self._fenxings),
                max(f.timestamp for f in self._fenxings)
            ) if self._fenxings else (None, None)
        }
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [f.to_dict() for f in self._fenxings]
    
    def __str__(self) -> str:
        """字符串表示"""
        level_str = f"({self._level.value})" if self._level else ""
        stats = self.get_statistics()
        return (f"FenXingList{level_str}[{stats['total_count']} fenxings: "
                f"{stats['top_count']} tops, {stats['bottom_count']} bottoms, "
                f"{stats['confirmed_count']} confirmed]")