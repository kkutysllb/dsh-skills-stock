#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论中枢数据模型
参考Vespa314/chan.py的中枢设计，实现标准的中枢识别和管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Iterator, Tuple
from .enums import ZhongShuType, SegDirection, TimeLevel
from .kline import KLine
from .seg import Seg


@dataclass
class ZhongShu:
    """
    中枢数据模型
    代表缠论中的价格中枢区间
    """
    # 基础构成
    forming_segs: List[Seg]          # 构成中枢的线段
    
    # 中枢区间
    high: float                      # 中枢上沿
    low: float                       # 中枢下沿
    center: float                    # 中枢中心
    
    # 时间信息
    start_time: datetime             # 开始时间
    end_time: datetime               # 结束时间
    
    # 中枢特征
    zhongshu_type: ZhongShuType = ZhongShuType.NORMAL  # 中枢类型
    level: Optional[TimeLevel] = None                   # 中枢级别
    
    # 扩展信息
    extend_count: int = 0            # 扩展次数
    up_break_attempts: int = 0       # 上破尝试次数
    down_break_attempts: int = 0     # 下破尝试次数
    
    # 中枢强度
    strength: float = 0.0            # 中枢强度
    stability: float = 0.0           # 中枢稳定性
    
    # 进入和离开
    enter_segs: List[Seg] = field(default_factory=list)    # 进入中枢的线段
    exit_segs: List[Seg] = field(default_factory=list)     # 离开中枢的线段
    
    # 状态标记
    is_finished: bool = True                                # 中枢是否完成（默认为True）
    
    def __post_init__(self):
        """初始化后处理"""
        self._validate()
        self._calculate_metrics()
    
    def _validate(self) -> None:
        """数据有效性验证"""
        if len(self.forming_segs) < 3:
            raise ValueError("中枢至少需要3个线段构成")
        
        if self.high <= self.low:
            raise ValueError("中枢上沿必须高于下沿")
        
        if not (self.low <= self.center <= self.high):
            raise ValueError("中枢中心必须在上下沿之间")
        
        # 验证线段序列的合理性
        directions = [seg.direction for seg in self.forming_segs]
        if len(set(directions)) < 2:
            raise ValueError("构成中枢的线段必须包含不同方向")
    
    def _calculate_metrics(self) -> None:
        """计算中枢各项指标"""
        self.strength = self._calculate_strength()
        self.stability = self._calculate_stability()
        self._classify_type()
    
    def _calculate_strength(self) -> float:
        """
        计算中枢强度
        基于构成线段的质量和中枢的持续时间
        """
        if not self.forming_segs:
            return 0.0
        
        # 线段质量强度
        avg_seg_strength = sum(seg.strength for seg in self.forming_segs) / len(self.forming_segs)
        
        # 持续时间强度
        duration_strength = min(1.0, self.duration_bars / 20)  # 20个K线为满分
        
        # 价格区间强度
        range_strength = min(1.0, self.range_ratio * 10)  # 10%区间为满分
        
        # 参与线段数量强度
        seg_count_strength = min(1.0, len(self.forming_segs) / 5)  # 5个线段为满分
        
        return (avg_seg_strength * 0.4 + 
                duration_strength * 0.3 + 
                range_strength * 0.2 + 
                seg_count_strength * 0.1)
    
    def _calculate_stability(self) -> float:
        """
        计算中枢稳定性
        基于价格在中枢区间内的分布和停留时间
        """
        if not self.forming_segs:
            return 0.0
        
        # 计算价格在中枢区间内的时间比例
        total_duration = self.duration_bars
        in_range_duration = 0
        
        for seg in self.forming_segs:
            # 简化计算：假设线段在中枢范围内的比例
            seg_low = min(seg.start_price, seg.end_price)
            seg_high = max(seg.start_price, seg.end_price)
            
            # 计算线段与中枢的重叠比例
            overlap_low = max(seg_low, self.low)
            overlap_high = min(seg_high, self.high)
            
            if overlap_high > overlap_low:
                seg_range = seg_high - seg_low
                overlap_range = overlap_high - overlap_low
                if seg_range > 0:
                    overlap_ratio = overlap_range / seg_range
                    in_range_duration += seg.duration * overlap_ratio
        
        time_stability = in_range_duration / total_duration if total_duration > 0 else 0
        
        # 扩展次数稳定性（扩展次数越多越稳定）
        extend_stability = min(1.0, self.extend_count / 3)  # 3次扩展为满分
        
        return time_stability * 0.7 + extend_stability * 0.3
    
    def _classify_type(self) -> None:
        """
        分类中枢类型
        """
        # 根据扩展次数和构成线段数量分类
        if self.extend_count >= 3:
            self.zhongshu_type = ZhongShuType.EXTENDED
        elif len(self.forming_segs) >= 5:
            self.zhongshu_type = ZhongShuType.COMPLEX
        else:
            self.zhongshu_type = ZhongShuType.NORMAL
        
        # 根据市场行为进一步分类
        if (self.up_break_attempts + self.down_break_attempts) >= 3:
            if self.range_ratio < 0.05:  # 5%以内的窄幅震荡
                self.zhongshu_type = ZhongShuType.CONSOLIDATION
            else:
                self.zhongshu_type = ZhongShuType.TREND
    
    @property
    def range_size(self) -> float:
        """中枢区间大小"""
        return self.high - self.low
    
    @property
    def range_ratio(self) -> float:
        """中枢区间比例"""
        return self.range_size / self.center if self.center > 0 else 0.0
    
    @property
    def duration(self) -> datetime:
        """中枢持续时间"""
        return self.end_time - self.start_time
    
    @property
    def duration_bars(self) -> int:
        """中枢持续K线数"""
        return sum(seg.duration for seg in self.forming_segs)
    
    @property
    def seg_count(self) -> int:
        """构成线段数量"""
        return len(self.forming_segs)
    
    @property
    def is_active(self) -> bool:
        """中枢是否仍然活跃"""
        # 简单判断：如果最后一个线段的结束时间是最近的，则认为活跃
        if not self.forming_segs:
            return False
        latest_seg_time = max(seg.end_time for seg in self.forming_segs)
        return latest_seg_time == self.end_time
    
    @property
    def upper_boundary(self) -> float:
        """中枢上边界（上沿）"""
        return self.high
    
    @property
    def lower_boundary(self) -> float:
        """中枢下边界（下沿）"""
        return self.low
    
    def contains_price(self, price: float) -> bool:
        """
        判断价格是否在中枢区间内
        
        Args:
            price: 价格
            
        Returns:
            是否在中枢内
        """
        return self.low <= price <= self.high
    
    def distance_from_center(self, price: float) -> float:
        """
        计算价格距离中枢中心的距离
        
        Args:
            price: 价格
            
        Returns:
            距离（可为负数）
        """
        return price - self.center
    
    def get_position_ratio(self, price: float) -> float:
        """
        获取价格在中枢中的位置比例
        
        Args:
            price: 价格
            
        Returns:
            位置比例（0-1，0为下沿，1为上沿）
        """
        if self.range_size == 0:
            return 0.5
        
        ratio = (price - self.low) / self.range_size
        return max(0.0, min(1.0, ratio))
    
    def is_broken_upward(self, price: float, threshold: float = 0.01) -> bool:
        """
        判断是否向上突破中枢
        
        Args:
            price: 价格
            threshold: 突破阈值
            
        Returns:
            是否向上突破
        """
        break_price = self.high * (1 + threshold)
        return price > break_price
    
    def is_broken_downward(self, price: float, threshold: float = 0.01) -> bool:
        """
        判断是否向下突破中枢
        
        Args:
            price: 价格
            threshold: 突破阈值
            
        Returns:
            是否向下突破
        """
        break_price = self.low * (1 - threshold)
        return price < break_price
    
    def can_extend_with(self, seg: Seg, max_extend: int = 9) -> bool:
        """
        判断是否可以用新线段扩展中枢
        
        Args:
            seg: 新线段
            max_extend: 最大扩展次数
            
        Returns:
            是否可以扩展
        """
        if self.extend_count >= max_extend:
            return False
        
        # 检查线段是否在中枢区间内有足够的重叠
        seg_low = min(seg.start_price, seg.end_price)
        seg_high = max(seg.start_price, seg.end_price)
        
        overlap_low = max(seg_low, self.low)
        overlap_high = min(seg_high, self.high)
        
        if overlap_high <= overlap_low:
            return False  # 无重叠
        
        # 重叠度检查
        overlap_range = overlap_high - overlap_low
        seg_range = seg_high - seg_low
        
        if seg_range > 0:
            overlap_ratio = overlap_range / seg_range
            return overlap_ratio >= 0.5  # 至少50%重叠
        
        return False
    
    def extend_with_seg(self, seg: Seg) -> None:
        """
        用新线段扩展中枢
        
        Args:
            seg: 扩展线段
        """
        if not self.can_extend_with(seg):
            raise ValueError("线段无法扩展当前中枢")
        
        self.forming_segs.append(seg)
        self.extend_count += 1
        self.end_time = max(self.end_time, seg.end_time)
        
        # 重新计算中枢区间（可能需要调整）
        self._recalculate_boundaries()
        self._calculate_metrics()
    
    def _recalculate_boundaries(self) -> None:
        """
        重新计算中枢边界
        当中枢扩展时可能需要调整上下沿
        """
        if len(self.forming_segs) < 3:
            return
        
        # 重新计算所有线段的重叠区间
        # 这里采用简化算法，实际实现可能更复杂
        all_lows = []
        all_highs = []
        
        for seg in self.forming_segs:
            seg_low = min(seg.start_price, seg.end_price)
            seg_high = max(seg.start_price, seg.end_price)
            all_lows.append(seg_low)
            all_highs.append(seg_high)
        
        # 中枢区间应该是所有线段都有重叠的部分
        self.low = max(all_lows)
        self.high = min(all_highs)
        
        if self.high <= self.low:
            # 如果没有完全重叠，使用平均值方法
            self.low = sum(all_lows) / len(all_lows)
            self.high = sum(all_highs) / len(all_highs)
        
        self.center = (self.high + self.low) / 2
    
    def get_support_resistance_levels(self) -> Dict[str, float]:
        """
        获取支撑阻力位
        
        Returns:
            支撑阻力位字典
        """
        return {
            'strong_resistance': self.high,
            'weak_resistance': self.center + (self.range_size * 0.25),
            'center': self.center,
            'weak_support': self.center - (self.range_size * 0.25),
            'strong_support': self.low
        }
    
    def get_trading_signals(self, current_price: float) -> List[Dict[str, Any]]:
        """
        根据当前价格获取交易信号
        
        Args:
            current_price: 当前价格
            
        Returns:
            交易信号列表
        """
        signals = []
        position = self.get_position_ratio(current_price)
        
        # 根据价格在中枢中的位置生成信号
        if position <= 0.2:  # 接近下沿
            signals.append({
                'type': 'buy',
                'strength': 0.8,
                'reason': '价格接近中枢下沿，考虑买入',
                'target': self.center,
                'stop_loss': self.low * 0.98
            })
        elif position >= 0.8:  # 接近上沿
            signals.append({
                'type': 'sell',
                'strength': 0.8,
                'reason': '价格接近中枢上沿，考虑卖出',
                'target': self.center,
                'stop_loss': self.high * 1.02
            })
        elif 0.4 <= position <= 0.6:  # 中心区域
            signals.append({
                'type': 'hold',
                'strength': 0.6,
                'reason': '价格在中枢中心区域，建议观望',
                'target': None,
                'stop_loss': None
            })
        
        return signals
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'high': self.high,
            'low': self.low,
            'center': self.center,
            'range_size': self.range_size,
            'range_ratio': self.range_ratio,
            'duration_bars': self.duration_bars,
            'seg_count': self.seg_count,
            'extend_count': self.extend_count,
            'up_break_attempts': self.up_break_attempts,
            'down_break_attempts': self.down_break_attempts,
            'strength': self.strength,
            'stability': self.stability,
            'zhongshu_type': self.zhongshu_type.value,
            'level': self.level.value if self.level else None,
            'is_active': self.is_active,
            'support_resistance': self.get_support_resistance_levels()
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.zhongshu_type}中枢[{self.low:.2f}-{self.high:.2f}] "
                f"(中心:{self.center:.2f}, {self.seg_count}段, "
                f"强度:{self.strength:.3f}, 扩展:{self.extend_count}次)")
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if not isinstance(other, ZhongShu):
            return False
        return (abs(self.high - other.high) < 1e-6 and
                abs(self.low - other.low) < 1e-6 and
                self.start_time == other.start_time)
    
    def __lt__(self, other) -> bool:
        """小于比较（按开始时间排序）"""
        if not isinstance(other, ZhongShu):
            return NotImplemented
        return self.start_time < other.start_time


class ZhongShuList:
    """
    中枢列表容器
    管理一系列中枢，提供查询、过滤、统计等功能
    """
    
    def __init__(self, zhongshus: Optional[List[ZhongShu]] = None, level: Optional[TimeLevel] = None):
        """
        初始化中枢列表
        
        Args:
            zhongshus: 中枢列表
            level: 时间级别
        """
        self._zhongshus: List[ZhongShu] = zhongshus or []
        self._level = level
        
        # 按时间排序
        self._zhongshus.sort(key=lambda z: z.start_time)
    
    def __len__(self) -> int:
        """中枢数量"""
        return len(self._zhongshus)
    
    def __getitem__(self, index: int) -> ZhongShu:
        """索引访问"""
        return self._zhongshus[index]
    
    def __iter__(self) -> Iterator[ZhongShu]:
        """迭代器"""
        return iter(self._zhongshus)
    
    @property
    def zhongshus(self) -> List[ZhongShu]:
        """获取中枢列表"""
        return self._zhongshus
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """获取时间级别"""
        return self._level
    
    def append(self, zhongshu: ZhongShu) -> None:
        """添加中枢并保持时间顺序"""
        self._zhongshus.append(zhongshu)
        self._zhongshus.sort(key=lambda z: z.start_time)
    
    def extend(self, zhongshus: List[ZhongShu]) -> None:
        """批量添加中枢"""
        self._zhongshus.extend(zhongshus)
        self._zhongshus.sort(key=lambda z: z.start_time)
    
    @classmethod
    def from_segs(cls, segs: List[Seg], config: Optional['ZhongShuConfig'] = None, 
                  level: Optional[TimeLevel] = None) -> 'ZhongShuList':
        """
        从线段列表构建中枢列表
        
        Args:
            segs: 线段列表
            config: 中枢构建配置
            level: 时间级别
            
        Returns:
            构建的中枢列表
        """
        builder = ZhongShuBuilder(config)
        zhongshus = builder.build_from_segs(segs)
        return cls(zhongshus, level)
    
    def clear(self) -> None:
        """清空中枢列表"""
        self._zhongshus.clear()
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._zhongshus) == 0
    
    def get_active_zhongshus(self) -> List[ZhongShu]:
        """获取活跃中枢"""
        return [zs for zs in self._zhongshus if zs.is_active]
    
    def get_by_type(self, zhongshu_type: ZhongShuType) -> List[ZhongShu]:
        """按类型获取中枢"""
        return [zs for zs in self._zhongshus if zs.zhongshu_type == zhongshu_type]
    
    def filter_by_strength(self, min_strength: float) -> List[ZhongShu]:
        """按强度过滤中枢"""
        return [zs for zs in self._zhongshus if zs.strength >= min_strength]
    
    def filter_by_duration(self, min_duration: int) -> List[ZhongShu]:
        """按持续时间过滤中枢"""
        return [zs for zs in self._zhongshus if zs.duration_bars >= min_duration]
    
    def find_current_zhongshu(self, current_price: float) -> Optional[ZhongShu]:
        """
        查找当前价格所在的中枢
        
        Args:
            current_price: 当前价格
            
        Returns:
            包含当前价格的中枢，如果没有则返回None
        """
        for zs in reversed(self._zhongshus):  # 从最新的开始查找
            if zs.contains_price(current_price) and zs.is_active:
                return zs
        return None
    
    def find_nearest_zhongshu(self, target_price: float) -> Optional[Tuple[ZhongShu, float]]:
        """
        查找距离目标价格最近的中枢
        
        Args:
            target_price: 目标价格
            
        Returns:
            (最近中枢, 距离)，如果没有中枢则返回None
        """
        if self.is_empty():
            return None
        
        nearest_zs = None
        min_distance = float('inf')
        
        for zs in self._zhongshus:
            distance = abs(zs.distance_from_center(target_price))
            if distance < min_distance:
                min_distance = distance
                nearest_zs = zs
        
        return (nearest_zs, min_distance) if nearest_zs else None
    
    def get_support_resistance_levels(self) -> List[float]:
        """
        获取所有中枢的支撑阻力位
        
        Returns:
            支撑阻力位价格列表
        """
        levels = []
        for zs in self._zhongshus:
            sr_levels = zs.get_support_resistance_levels()
            levels.extend(sr_levels.values())
        
        # 去重并排序
        levels = sorted(list(set(levels)))
        return levels
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取中枢统计信息"""
        if self.is_empty():
            return {
                'total_count': 0,
                'active_count': 0,
                'avg_strength': 0.0,
                'avg_duration': 0.0,
                'avg_range_ratio': 0.0
            }
        
        active_zhongshus = self.get_active_zhongshus()
        
        # 按类型统计
        type_counts = {}
        for zs_type in ZhongShuType:
            type_counts[zs_type.value] = len(self.get_by_type(zs_type))
        
        return {
            'total_count': len(self._zhongshus),
            'active_count': len(active_zhongshus),
            'type_distribution': type_counts,
            'avg_strength': sum(zs.strength for zs in self._zhongshus) / len(self._zhongshus),
            'avg_stability': sum(zs.stability for zs in self._zhongshus) / len(self._zhongshus),
            'avg_duration': sum(zs.duration_bars for zs in self._zhongshus) / len(self._zhongshus),
            'avg_range_ratio': sum(zs.range_ratio for zs in self._zhongshus) / len(self._zhongshus),
            'avg_extend_count': sum(zs.extend_count for zs in self._zhongshus) / len(self._zhongshus),
            'price_coverage': (
                min(zs.low for zs in self._zhongshus),
                max(zs.high for zs in self._zhongshus)
            ),
            'time_range': (
                min(zs.start_time for zs in self._zhongshus),
                max(zs.end_time for zs in self._zhongshus)
            ) if self._zhongshus else (None, None)
        }
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [zs.to_dict() for zs in self._zhongshus]
    
    def __str__(self) -> str:
        """字符串表示"""
        level_str = f"({self._level.value})" if self._level else ""
        stats = self.get_statistics()
        return (f"ZhongShuList{level_str}[{stats['total_count']} zhongshus: "
                f"{stats['active_count']} active, "
                f"avg_strength:{stats['avg_strength']:.3f}]")


@dataclass
class ZhongShuConfig:
    """
    中枢构建配置类
    控制中枢识别和构建的各种参数
    基于缠论最佳实践优化参数设置
    """
    # 基本参数
    min_seg_count: int = 3          # 最少线段数（标准为3）
    min_overlap_ratio: float = 0.01  # 最小重叠比例（提高到1%，更合理）
    max_extend_count: int = 9       # 最大扩展次数（缠论九段标准）
    
    # 中枢质量参数
    min_duration: int = 1           # 最小持续K线数
    min_amplitude_ratio: float = 0.005  # 最小幅度比例（提高要求）
    
    # 构建模式
    build_mode: str = "loose"       # "standard", "strict", "loose" - 宽松模式更容易构建中枢
    allow_gap: bool = True          # 允许跳空（股市正常现象）
    require_alternating: bool = False # 不严格要求方向交替（更符合实际）
    
    # 扩展优化参数
    enable_nine_segment_extension: bool = True  # 启用九段延伸机制
    extension_overlap_threshold: float = 0.3   # 延伸重叠阈值
    
    # 强度计算权重
    price_weight: float = 0.4       # 价格强度权重
    duration_weight: float = 0.3    # 持续时间权重
    volume_weight: float = 0.2      # 成交量权重
    seg_quality_weight: float = 0.1 # 线段质量权重


class ZhongShuBuilder:
    """
    中枢构建器
    负责从线段序列识别和构建中枢，实现缠论中枢的核心算法
    """
    
    def __init__(self, config: Optional['ZhongShuConfig'] = None):
        """
        初始化中枢构建器
        
        Args:
            config: 中枢构建配置
        """
        self.config = config or ZhongShuConfig()
        self._current_zhongshus: List[ZhongShu] = []
        self._temp_segs: List[Seg] = []
        
    def build_from_segs(self, segs: List[Seg]) -> List[ZhongShu]:
        """
        从线段序列构建中枢序列
        
        Args:
            segs: 线段列表（按时间排序）
            
        Returns:
            构建的中枢列表
        """
        if len(segs) < self.config.min_seg_count:
            return []
        
        # 清空之前的状态
        self._current_zhongshus.clear()
        self._temp_segs.clear()
        
        # 使用滑动窗口方法逐个检查线段组合
        i = 0
        while i < len(segs) - self.config.min_seg_count + 1:
            # 尝试从当前位置构建中枢
            zhongshu_result = self._try_build_zhongshu_from_index(segs, i)
            
            if zhongshu_result:
                zhongshu, consumed_count = zhongshu_result
                self._current_zhongshus.append(zhongshu)
                i += consumed_count  # 跳过已被使用的线段
            else:
                i += 1  # 移动到下一个起始位置
        
        return self._current_zhongshus.copy()
    
    def _try_build_zhongshu_from_index(self, segs: List[Seg], start_index: int) -> Optional[Tuple[ZhongShu, int]]:
        """
        尝试从指定索引开始构建中枢
        
        Args:
            segs: 线段列表
            start_index: 起始索引
            
        Returns:
            (中枢对象, 消耗的线段数量) 或 None
        """
        if start_index + self.config.min_seg_count > len(segs):
            return None
        
        # 检查最基本的三线段中枢
        base_segs = segs[start_index:start_index + 3]
        
        if not self._can_form_basic_zhongshu(base_segs):
            return None
        
        # 计算基础中枢区间
        zhongshu_range = self._calculate_zhongshu_range(base_segs)
        if not zhongshu_range:
            return None
        
        high, low, center = zhongshu_range
        
        # 尝试扩展中枢
        forming_segs = base_segs.copy()
        extend_index = start_index + 3
        extend_count = 0
        
        while (extend_index < len(segs) and 
               extend_count < self.config.max_extend_count):
            
            candidate_seg = segs[extend_index]
            
            if self._can_extend_zhongshu(forming_segs, candidate_seg, high, low):
                forming_segs.append(candidate_seg)
                extend_count += 1
                extend_index += 1
                
                # 重新计算中枢区间
                new_range = self._calculate_zhongshu_range(forming_segs)
                if new_range:
                    high, low, center = new_range
            else:
                break
        
        # 创建中枢对象
        try:
            zhongshu = ZhongShu(
                forming_segs=forming_segs,
                high=high,
                low=low,
                center=center,
                start_time=forming_segs[0].start_time,
                end_time=forming_segs[-1].end_time,
                extend_count=extend_count
            )
            
            # 验证中枢有效性
            if self._is_valid_zhongshu(zhongshu):
                return zhongshu, len(forming_segs)
            
        except ValueError as e:
            # 中枢创建失败
            pass
        
        return None
    
    def _can_form_basic_zhongshu(self, segs: List[Seg]) -> bool:
        """
        检查三个线段是否可以构成基础中枢
        基于缠论最佳实践：至少三个连续次级别走势类型重叠的部分
        
        Args:
            segs: 三个线段
            
        Returns:
            是否可以构成中枢
        """
        if len(segs) != 3:
            return False
        
        seg1, seg2, seg3 = segs
        
        # 检查方向交替（如果要求的话）
        if self.config.require_alternating:
            if not ((seg1.is_up and seg2.is_down and seg3.is_up) or
                    (seg1.is_down and seg2.is_up and seg3.is_down)):
                return False
        
        # 检查时间连续性
        if seg1.end_time > seg2.start_time or seg2.end_time > seg3.start_time:
            if not self.config.allow_gap:
                return False
        
        # 基于缠论最佳实践：检查三个连续线段是否有重叠部分
        # 使用标准公式：3线段中有高点和低点，2个高点取其低，2个低点取其高
        return self._check_three_segs_overlap(seg1, seg2, seg3)
    
    def _calculate_overlap_ratio(self, seg1: Seg, seg3: Seg) -> float:
        """
        计算第一和第三线段的重叠比例
        修正版本：使用线段的价格波动区间而不是起终点区间
        
        Args:
            seg1: 第一线段
            seg3: 第三线段
            
        Returns:
            重叠比例
        """
        # 获取线段的实际价格波动区间
        seg1_low = seg1.low_price
        seg1_high = seg1.high_price
        seg3_low = seg3.low_price
        seg3_high = seg3.high_price
        
        # 计算重叠区间
        overlap_low = max(seg1_low, seg3_low)
        overlap_high = min(seg1_high, seg3_high)
        
        if overlap_high <= overlap_low:
            return 0.0
        
        # 重叠区间大小
        overlap_range = overlap_high - overlap_low
        
        # 以两个线段波动区间的平均值作为基准
        seg1_range = seg1_high - seg1_low
        seg3_range = seg3_high - seg3_low
        avg_range = (seg1_range + seg3_range) / 2
        
        if avg_range <= 0:
            return 0.0
        
        return overlap_range / avg_range
    
    def _check_three_segs_overlap(self, seg1: Seg, seg2: Seg, seg3: Seg) -> bool:
        """
        检查三个连续线段是否有重叠部分
        基于缠论最佳实践：3线段中有2个高点和2个低点，2个高点取其低，2个低点取其高
        
        Args:
            seg1: 第一线段
            seg2: 第二线段  
            seg3: 第三线段
            
        Returns:
            是否有重叠部分可构成中枢
        """
        # 获取三个线段的高点和低点
        highs = [seg1.high_price, seg2.high_price, seg3.high_price]
        lows = [seg1.low_price, seg2.low_price, seg3.low_price]
        
        # 根据缠论标准公式计算中枢区间
        # 中枢下沿 = max(所有低点) - 取低点中的最高者
        # 中枢上沿 = min(所有高点) - 取高点中的最低者
        zhongshu_low = max(lows)   # 2个低点取其高
        zhongshu_high = min(highs) # 2个高点取其低
        
        # 有效的中枢区间必须上沿高于下沿
        if zhongshu_high > zhongshu_low:
            # 检查重叠区间大小是否满足最小要求
            overlap_range = zhongshu_high - zhongshu_low
            avg_seg_range = sum(highs[i] - lows[i] for i in range(3)) / 3
            
            if avg_seg_range > 0:
                overlap_ratio = overlap_range / avg_seg_range
                return overlap_ratio >= self.config.min_overlap_ratio
            else:
                return overlap_range > 0  # 如果线段范围为0，只要有重叠就可以
        
        return False
    
    def _calculate_zhongshu_range(self, segs: List[Seg]) -> Optional[Tuple[float, float, float]]:
        """
        计算中枢的价格区间
        基于缠论标准公式：A、B、C分别的高、低点是a1\\a2,b1\\b2,c1\\c2，
        则中枢的区间就是[max(a2,b2,c2), min(a1,b1,c1)]
        
        Args:
            segs: 构成中枢的线段列表
            
        Returns:
            (高点, 低点, 中心) 或 None
        """
        if len(segs) < 3:
            return None
        
        # 按照缠论标准公式计算中枢区间
        # 对于每个线段，获取其高点(a1)和低点(a2)
        seg_highs = []  # 存储各线段高点 [a1, b1, c1, ...]
        seg_lows = []   # 存储各线段低点 [a2, b2, c2, ...]
        
        for seg in segs:
            # 线段的高点和低点（不是起终点，而是整个线段的极值）
            seg_highs.append(seg.high_price)
            seg_lows.append(seg.low_price)
        
        # 根据缠论标准公式：
        # 中枢下沿 = max(a2, b2, c2, ...) - 各线段低点的最大值
        # 中枢上沿 = min(a1, b1, c1, ...) - 各线段高点的最小值
        zhongshu_low = max(seg_lows)   # max(a2, b2, c2)
        zhongshu_high = min(seg_highs) # min(a1, b1, c1)
        
        # 验证中枢区间的有效性
        if zhongshu_high <= zhongshu_low:
            # 如果标准公式得出无效区间，说明这些线段无法构成标准中枢
            # 使用备用方案：取前三个线段计算
            if len(segs) >= 3:
                first_three = segs[:3]
                first_three_highs = [seg.high_price for seg in first_three]
                first_three_lows = [seg.low_price for seg in first_three]
                
                zhongshu_low = max(first_three_lows)
                zhongshu_high = min(first_three_highs)
                
                # 如果前三个线段也无法构成有效中枢，返回None
                if zhongshu_high <= zhongshu_low:
                    return None
        
        zhongshu_center = (zhongshu_high + zhongshu_low) / 2
        
        return zhongshu_high, zhongshu_low, zhongshu_center
    
    def _can_extend_zhongshu(self, current_segs: List[Seg], candidate_seg: Seg, 
                           current_high: float, current_low: float) -> bool:
        """
        检查是否可以用新线段扩展中枢
        
        Args:
            current_segs: 当前构成中枢的线段
            candidate_seg: 候选扩展线段
            current_high: 当前中枢上沿
            current_low: 当前中枢下沿
            
        Returns:
            是否可以扩展
        """
        # 检查方向交替（如果要求的话）
        if self.config.require_alternating:
            last_seg = current_segs[-1]
            if candidate_seg.direction == last_seg.direction:
                return False
        
        # 检查时间连续性
        last_seg = current_segs[-1]
        if last_seg.end_time > candidate_seg.start_time:
            if not self.config.allow_gap:
                return False
        
        # 检查新线段是否与中枢区间有足够重叠
        candidate_low = min(candidate_seg.start_price, candidate_seg.end_price)
        candidate_high = max(candidate_seg.start_price, candidate_seg.end_price)
        
        # 计算重叠
        overlap_low = max(candidate_low, current_low)
        overlap_high = min(candidate_high, current_high)
        
        if overlap_high <= overlap_low:
            return False  # 无重叠
        
        # 重叠度检查
        overlap_range = overlap_high - overlap_low
        candidate_range = candidate_high - candidate_low
        
        if candidate_range > 0:
            overlap_ratio = overlap_range / candidate_range
            return overlap_ratio >= self.config.min_overlap_ratio
        
        return False
    
    def _is_valid_zhongshu(self, zhongshu: ZhongShu) -> bool:
        """
        检查中枢是否有效
        
        Args:
            zhongshu: 中枢对象
            
        Returns:
            是否有效
        """
        # 检查基本要求
        if len(zhongshu.forming_segs) < self.config.min_seg_count:
            return False
        
        # 检查持续时间
        if zhongshu.duration_bars < self.config.min_duration:
            return False
        
        # 检查幅度
        if zhongshu.range_ratio < self.config.min_amplitude_ratio:
            return False
        
        # 根据构建模式进行额外检查
        if self.config.build_mode == "strict":
            return self._strict_validation(zhongshu)
        elif self.config.build_mode == "loose":
            return True  # 宽松模式，基本检查通过即可
        else:
            return self._standard_validation(zhongshu)
    
    def _strict_validation(self, zhongshu: ZhongShu) -> bool:
        """
        严格模式验证
        
        Args:
            zhongshu: 中枢对象
            
        Returns:
            是否通过严格验证
        """
        # 检查所有线段的质量
        avg_strength = sum(seg.strength for seg in zhongshu.forming_segs) / len(zhongshu.forming_segs)
        if avg_strength < 0.5:
            return False
        
        # 检查中枢稳定性
        if zhongshu.stability < 0.6:
            return False
        
        return True
    
    def _standard_validation(self, zhongshu: ZhongShu) -> bool:
        """
        標準模式验证
        
        Args:
            zhongshu: 中枢对象
            
        Returns:
            是否通过标准验证
        """
        # 标准验证相对宽松，主要检查结构完整性
        return zhongshu.strength > 0.3