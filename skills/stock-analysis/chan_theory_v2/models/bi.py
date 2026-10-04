#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论笔数据模型
参考Vespa314/chan.py的笔设计，实现标准的笔构建和管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Iterator
from .enums import BiDirection, FenXingType, TimeLevel
from .kline import KLine
from .fenxing import FenXing


@dataclass
class Bi:
    """
    笔数据模型
    代表缠论中连接两个相邻且相反分型的笔
    """
    # 基础信息
    start_fenxing: FenXing           # 起始分型
    end_fenxing: FenXing             # 结束分型
    direction: BiDirection           # 笔方向
    
    # 笔的构成
    klines: List[KLine] = field(default_factory=list)  # 笔包含的K线
    
    # 笔的特征
    strength: float = 0.0            # 笔的强度
    purity: float = 0.0              # 笔的纯度（方向一致性）
    
    # 确认信息
    is_confirmed: bool = False       # 是否已确认
    confirm_bars: int = 0            # 确认用的K线数
    
    # 扩展信息
    volume_profile: Dict[str, float] = field(default_factory=dict)  # 成交量分布
    
    def __post_init__(self):
        """初始化后处理"""
        self._validate()
        self._calculate_metrics()
    
    def _validate(self) -> None:
        """数据有效性验证"""
        if not isinstance(self.start_fenxing, FenXing) or not isinstance(self.end_fenxing, FenXing):
            raise ValueError("笔必须由两个有效分型构成")
        
        if self.start_fenxing.timestamp >= self.end_fenxing.timestamp:
            raise ValueError("笔的结束时间必须晚于开始时间")
        
        # 验证分型类型与笔方向的一致性
        expected_direction = BiDirection.from_fenxing_types(
            self.start_fenxing.fenxing_type, 
            self.end_fenxing.fenxing_type
        )
        if self.direction != expected_direction:
            raise ValueError(f"笔方向与分型类型不匹配: {self.direction} vs {expected_direction}")
    
    def _calculate_metrics(self) -> None:
        """计算笔的各项指标"""
        self.strength = self._calculate_strength()
        self.purity = self._calculate_purity()
    
    def _calculate_strength(self) -> float:
        """
        计算笔的强度
        基于价格变化幅度和成交量
        """
        if self.start_price == 0:
            return 0.0
        
        # 价格强度：基于价格变化幅度
        price_strength = abs(self.end_price - self.start_price) / self.start_price
        
        # 成交量强度：基于平均成交量
        if self.klines:
            avg_volume = sum(k.volume for k in self.klines) / len(self.klines)
            volume_strength = min(1.0, avg_volume / 1000000)  # 归一化处理
        else:
            volume_strength = 0.5
        
        # 综合强度：价格权重0.7，成交量权重0.3
        return price_strength * 0.7 + volume_strength * 0.3
    
    def _calculate_purity(self) -> float:
        """
        计算笔的纯度
        衡量笔方向的一致性
        """
        if not self.klines or len(self.klines) <= 1:
            return 1.0
        
        consistent_moves = 0
        total_moves = len(self.klines) - 1
        
        for i in range(total_moves):
            current_close = self.klines[i].close
            next_close = self.klines[i + 1].close
            
            if self.direction == BiDirection.UP:
                if next_close >= current_close:
                    consistent_moves += 1
            else:  # DOWN
                if next_close <= current_close:
                    consistent_moves += 1
        
        return consistent_moves / total_moves if total_moves > 0 else 1.0
    
    @property
    def start_price(self) -> float:
        """起始价格"""
        return self.start_fenxing.price
    
    @property
    def end_price(self) -> float:
        """结束价格"""
        return self.end_fenxing.price
    
    @property
    def start_time(self) -> datetime:
        """开始时间"""
        return self.start_fenxing.timestamp
    
    @property
    def end_time(self) -> datetime:
        """结束时间"""
        return self.end_fenxing.timestamp
    
    @property
    def duration(self) -> int:
        """持续时间（K线数量）"""
        return len(self.klines)
    
    @property
    def amplitude(self) -> float:
        """笔的幅度（绝对值）"""
        return abs(self.end_price - self.start_price)
    
    @property
    def amplitude_ratio(self) -> float:
        """笔的幅度比例"""
        return self.amplitude / self.start_price if self.start_price > 0 else 0.0
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """笔的级别"""
        return self.start_fenxing.level
    
    @property
    def is_up(self) -> bool:
        """是否为向上笔"""
        return self.direction == BiDirection.UP
    
    @property
    def is_down(self) -> bool:
        """是否为向下笔"""
        return self.direction == BiDirection.DOWN
    
    @property
    def high_price(self) -> float:
        """笔的最高价"""
        if self.klines:
            return max(k.high for k in self.klines)
        return max(self.start_price, self.end_price)
    
    @property
    def low_price(self) -> float:
        """笔的最低价"""
        if self.klines:
            return min(k.low for k in self.klines)
        return min(self.start_price, self.end_price)
    
    @property
    def total_volume(self) -> int:
        """笔的总成交量"""
        return sum(k.volume for k in self.klines)
    
    @property
    def avg_volume(self) -> float:
        """笔的平均成交量"""
        return self.total_volume / len(self.klines) if self.klines else 0.0
    
    def is_valid_bi(self, min_amplitude: float = 0.005, min_duration: int = 3) -> bool:
        """
        判断是否为有效笔
        
        Args:
            min_amplitude: 最小幅度要求
            min_duration: 最小持续时间要求
            
        Returns:
            是否有效
        """
        # 检查幅度
        if self.amplitude_ratio < min_amplitude:
            return False
        
        # 检查持续时间
        if self.duration < min_duration:
            return False
        
        # 检查分型有效性
        if not self.start_fenxing.is_valid_fenxing() or not self.end_fenxing.is_valid_fenxing():
            return False
        
        # 检查纯度
        if self.purity < 0.5:  # 至少50%的方向一致性
            return False
        
        return True
    
    def breaks_by(self, other: 'Bi', threshold: float = 0.01) -> bool:
        """
        判断是否被另一笔破坏
        
        Args:
            other: 另一笔
            threshold: 破坏阈值
            
        Returns:
            是否被破坏
        """
        if self.direction == other.direction:
            return False  # 同方向不构成破坏
        
        if self.is_up and other.is_down:
            # 向上笔被向下笔破坏：其他笔的终点低于当前笔起点
            break_price = self.start_price * (1 - threshold)
            return other.end_price < break_price
        elif self.is_down and other.is_up:
            # 向下笔被向上笔破坏：其他笔的终点高于当前笔起点
            break_price = self.start_price * (1 + threshold)
            return other.end_price > break_price
        
        return False
    
    def overlap_with(self, other: 'Bi') -> float:
        """
        计算与另一笔的重叠度
        
        Args:
            other: 另一笔
            
        Returns:
            重叠度（0-1）
        """
        # 价格重叠
        self_low = min(self.start_price, self.end_price)
        self_high = max(self.start_price, self.end_price)
        other_low = min(other.start_price, other.end_price)
        other_high = max(other.start_price, other.end_price)
        
        overlap_low = max(self_low, other_low)
        overlap_high = min(self_high, other_high)
        
        if overlap_high <= overlap_low:
            return 0.0  # 无重叠
        
        overlap_range = overlap_high - overlap_low
        self_range = self_high - self_low
        other_range = other_high - other_low
        
        if self_range == 0 or other_range == 0:
            return 0.0
        
        # 返回相对于较小区间的重叠比例
        min_range = min(self_range, other_range)
        return overlap_range / min_range
    
    def get_retracement_ratio(self, reference_bi: 'Bi') -> float:
        """
        计算相对于参考笔的回撤比例
        
        Args:
            reference_bi: 参考笔
            
        Returns:
            回撤比例
        """
        ref_amplitude = reference_bi.amplitude
        if ref_amplitude == 0:
            return 0.0
        
        return self.amplitude / ref_amplitude
    
    def is_golden_ratio_retracement(self, reference_bi: 'Bi', tolerance: float = 0.05) -> bool:
        """
        判断是否为黄金分割回撤
        
        Args:
            reference_bi: 参考笔
            tolerance: 容差
            
        Returns:
            是否为黄金分割回撤
        """
        ratio = self.get_retracement_ratio(reference_bi)
        golden_ratios = [0.382, 0.5, 0.618, 0.809]
        
        for golden_ratio in golden_ratios:
            if abs(ratio - golden_ratio) <= tolerance:
                return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'start_price': self.start_price,
            'end_price': self.end_price,
            'direction': self.direction.value,
            'duration': self.duration,
            'amplitude': self.amplitude,
            'amplitude_ratio': self.amplitude_ratio,
            'strength': self.strength,
            'purity': self.purity,
            'is_confirmed': self.is_confirmed,
            'confirm_bars': self.confirm_bars,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'total_volume': self.total_volume,
            'avg_volume': self.avg_volume,
            'level': self.level.value if self.level else None
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.direction.value}笔: {self.start_price:.2f}->{self.end_price:.2f} "
                f"({self.amplitude_ratio:.2%}, {self.duration}K, 强度:{self.strength:.3f})")
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if not isinstance(other, Bi):
            return False
        return (self.start_fenxing == other.start_fenxing and
                self.end_fenxing == other.end_fenxing)
    
    def __lt__(self, other) -> bool:
        """小于比较（按开始时间排序）"""
        if not isinstance(other, Bi):
            return NotImplemented
        return self.start_time < other.start_time


@dataclass
class BiConfig:
    """
    笔构建配置类
    参考Vespa314/chan.py的配置设计
    调整为更宽松的默认参数以适应真实市场数据
    """
    # 分型检查模式
    fx_check_mode: str = "loss"         # "strict", "totally", "loss", "half" - 使用更宽松的模式
    
    # 笔构建参数
    is_strict: bool = False             # 非严格模式，允许更多的笔构建
    allow_equal: bool = True            # 允许相等价格，适应实际市场情况
    min_bi_length: int = 3              # 最小笔长度（K线数）
    min_amplitude_ratio: float = 0.001  # 降低最小幅度比例，适应小幅波动
    
    # 确认参数
    confirm_klines: int = 0             # 减少确认K线数量，加快笔确认
    require_confirmation: bool = False   # 暂时不需要确认，简化算法


class BiBuilder:
    """
    笔构建器
    负责从分型序列构建笔序列，处理缠论中笔的核心算法
    """
    
    def __init__(self, config: Optional[BiConfig] = None):
        """
        初始化笔构建器
        
        Args:
            config: 笔构建配置
        """
        self.config = config or BiConfig()
        self._current_bis: List[Bi] = []
        self._temp_fenxings: List[FenXing] = []
        self._all_klines: List[KLine] = []  # 存储完整的K线序列
        
    def build_from_fenxings(self, fenxings: List[FenXing], klines: Optional[List[KLine]] = None) -> List[Bi]:
        """
        从分型序列构建笔序列
        按照缠论标准定义：相邻的顶分型和底分型之间的连线构成笔
        
        Args:
            fenxings: 分型列表（按时间排序）
            klines: 完整的K线序列（可选）
            
        Returns:
            构建的笔列表
        """
        if len(fenxings) < 2:
            return []
        
        # 存储K线序列
        if klines:
            self._all_klines = sorted(klines, key=lambda k: k.timestamp)
        else:
            self._all_klines = []
            for fx in fenxings:
                if fx.kline not in self._all_klines:
                    self._all_klines.append(fx.kline)
            self._all_klines.sort(key=lambda k: k.timestamp)
        
        # 按缠论标准构建笔：相邻不同类型分型直接连接
        bis = []
        
        # 首先处理连续同类型分型，只保留最极端的
        processed_fenxings = self._optimize_consecutive_fenxings(fenxings)
        
        # 构建笔：相邻的顶分型和底分型连接
        for i in range(len(processed_fenxings) - 1):
            start_fx = processed_fenxings[i]
            end_fx = processed_fenxings[i + 1]
            
            # 确保是不同类型的分型
            if start_fx.fenxing_type != end_fx.fenxing_type:
                try:
                    bi = self._create_bi_from_fenxings(start_fx, end_fx)
                    if bi:
                        bis.append(bi)
                except Exception as e:
                    # 忽略无法创建的笔，继续处理
                    continue
        
        return bis
    
    def _create_bi_from_fenxings(self, start_fx: FenXing, end_fx: FenXing) -> Optional[Bi]:
        """
        从两个分型创建笔
        
        Args:
            start_fx: 起始分型  
            end_fx: 结束分型
            
        Returns:
            创建的笔对象，如果无法创建则返回None
        """
        # 确定笔的方向
        if start_fx.is_bottom and end_fx.is_top:
            direction = BiDirection.UP
        elif start_fx.is_top and end_fx.is_bottom:
            direction = BiDirection.DOWN
        else:
            return None
        
        # 获取笔经过的K线
        start_time = start_fx.timestamp
        end_time = end_fx.timestamp
        
        bi_klines = [k for k in self._all_klines 
                     if start_time <= k.timestamp <= end_time]
        
        if not bi_klines:
            return None
        
        try:
            # 创建笔对象
            bi = Bi(
                start_fenxing=start_fx,
                end_fenxing=end_fx,
                direction=direction,
                klines=bi_klines
            )
            return bi
        except Exception as e:
            return None
    
    def _optimize_consecutive_fenxings(self, fenxings: List[FenXing]) -> List[FenXing]:
        """
        优化连续同类型分型
        缠论标准：连续的同类型分型只保留第一个，舍弃后续的（用X标出）
        
        Args:
            fenxings: 原始分型列表
            
        Returns:
            优化后的分型列表
        """
        if len(fenxings) <= 1:
            return fenxings
        
        optimized = []
        i = 0
        
        while i < len(fenxings):
            current_fenxing = fenxings[i]
            same_type_group = [current_fenxing]
            
            # 收集连续的同类型分型
            j = i + 1
            while j < len(fenxings) and fenxings[j].fenxing_type == current_fenxing.fenxing_type:
                same_type_group.append(fenxings[j])
                j += 1
            
            # 缠论标准：保留第一个分型，舍弃后续的（不论价格高低）
            first_fenxing = same_type_group[0]  # 保留第一个
            optimized.append(first_fenxing)
            
            # 记录被舍弃的分型（用于调试）
            if len(same_type_group) > 1:
                discarded_count = len(same_type_group) - 1
                discarded_type = "顶分型" if first_fenxing.is_top else "底分型"
                # 可以添加日志记录被舍弃的分型
            
            i = j
        
        return optimized
    
    # 旧的复杂方法已被新的简化方法替代
    def _process_fenxing_old(self, fenxing: FenXing) -> None:
        """
        旧的处理方法，已被简化的缠论标准方法替代
        """
        pass
    
    def _can_create_bi(self) -> bool:
        """
        检查当前临时分型列表是否可以构建笔
        
        Returns:
            是否可以构建笔
        """
        if len(self._temp_fenxings) < 2:
            return False
        
        start_fx = self._temp_fenxings[0]   # 使用第一个分型
        end_fx = self._temp_fenxings[-1]    # 使用最后一个分型
        
        # 必须是相反类型的分型
        if start_fx.fenxing_type == end_fx.fenxing_type:
            return False
        
        # 检查是否与已有笔冲突
        if self._current_bis:
            last_bi = self._current_bis[-1]
            
            # 新笔的起始分型必须是上一笔的结束分型
            if start_fx != last_bi.end_fenxing:
                return False
            
            # 新笔的方向必须与上一笔相反
            proposed_direction = BiDirection.from_fenxing_types(start_fx.fenxing_type, end_fx.fenxing_type)
            if proposed_direction == last_bi.direction:
                return False
        
        # 检查分型间的有效性
        return self._validate_fenxing_pair(start_fx, end_fx)
    
    def _validate_fenxing_pair(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """
        验证分型对是否可以构成有效笔
        
        Args:
            start_fx: 起始分型
            end_fx: 结束分型
            
        Returns:
            是否有效
        """
        # 检查时间顺序
        if start_fx.timestamp >= end_fx.timestamp:
            return False
        
        # 检查分型有效性
        if not start_fx.is_valid_fenxing() or not end_fx.is_valid_fenxing():
            return False
        
        # 根据配置的检查模式验证
        return self._check_fenxing_relationship(start_fx, end_fx)
    
    def _check_fenxing_relationship(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """
        根据配置的模式检查分型关系
        
        Args:
            start_fx: 起始分型
            end_fx: 结束分型
            
        Returns:
            是否满足关系要求
        """
        mode = self.config.fx_check_mode
        
        if mode == "strict":
            return self._check_strict_mode(start_fx, end_fx)
        elif mode == "totally":
            return self._check_totally_mode(start_fx, end_fx)
        elif mode == "loss":
            return self._check_loss_mode(start_fx, end_fx)
        elif mode == "half":
            return self._check_half_mode(start_fx, end_fx)
        else:
            # 默认使用严格模式
            return self._check_strict_mode(start_fx, end_fx)
    
    def _check_strict_mode(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """严格模式检查"""
        if start_fx.is_bottom and end_fx.is_top:
            # 向上笔：底分型的最低点必须低于顶分型三元素最低点的最小值
            start_min = min(k.low for k in start_fx.left_klines + [start_fx.kline] + start_fx.right_klines)
            end_min = min(k.low for k in end_fx.left_klines + [end_fx.kline] + end_fx.right_klines)
            return start_min < end_min
        elif start_fx.is_top and end_fx.is_bottom:
            # 向下笔：顶分型的最高点必须高于底分型三元素最高点的最大值
            start_max = max(k.high for k in start_fx.left_klines + [start_fx.kline] + start_fx.right_klines)
            end_max = max(k.high for k in end_fx.left_klines + [end_fx.kline] + end_fx.right_klines)
            return start_max > end_max
        return False
    
    def _check_totally_mode(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """完全模式检查"""
        if start_fx.is_bottom and end_fx.is_top:
            # 底分型的三元素最高点都必须低于顶分型的三元素最低点
            start_max = max(k.high for k in start_fx.left_klines + [start_fx.kline] + start_fx.right_klines)
            end_min = min(k.low for k in end_fx.left_klines + [end_fx.kline] + end_fx.right_klines)
            return start_max < end_min
        elif start_fx.is_top and end_fx.is_bottom:
            # 顶分型的三元素最低点都必须高于底分型的三元素最高点
            start_min = min(k.low for k in start_fx.left_klines + [start_fx.kline] + start_fx.right_klines)
            end_max = max(k.high for k in end_fx.left_klines + [end_fx.kline] + end_fx.right_klines)
            return start_min > end_max
        return False
    
    def _check_loss_mode(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """宽松模式检查"""
        if start_fx.is_bottom and end_fx.is_top:
            # 底分型的最低点只需低于顶分型中间元素的最低点
            return start_fx.price < end_fx.kline.low
        elif start_fx.is_top and end_fx.is_bottom:
            # 顶分型的最高点只需高于底分型中间元素的最高点
            return start_fx.price > end_fx.kline.high
        return False
    
    def _check_half_mode(self, start_fx: FenXing, end_fx: FenXing) -> bool:
        """半严格模式检查"""
        if start_fx.is_bottom and end_fx.is_top:
            # 对于向上笔：底分型最低点需低于顶分型前两个元素的最低点
            if len(end_fx.left_klines) >= 2:
                end_partial_min = min(k.low for k in end_fx.left_klines[:2])
                return start_fx.price < end_partial_min
            else:
                return self._check_strict_mode(start_fx, end_fx)
        elif start_fx.is_top and end_fx.is_bottom:
            # 对于向下笔：顶分型最高点需高于底分型后两个元素的最高点
            if len(end_fx.right_klines) >= 2:
                end_partial_max = max(k.high for k in end_fx.right_klines[:2])
                return start_fx.price > end_partial_max
            else:
                return self._check_strict_mode(start_fx, end_fx)
        return False
    
    def _create_bi(self) -> None:
        """
        创建新笔并添加到笔列表中
        """
        if len(self._temp_fenxings) < 2:
            return
        
        start_fx = self._temp_fenxings[0]  # 使用第一个分型作为起点
        end_fx = self._temp_fenxings[-1]   # 使用最后一个分型作为终点
        
        # 确定笔方向
        direction = BiDirection.from_fenxing_types(start_fx.fenxing_type, end_fx.fenxing_type)
        
        # 获取笔包含的K线（从起始分型到结束分型之间的所有K线）
        klines = self._get_klines_between_fenxings(start_fx, end_fx)
        
        # 创建笔对象
        bi = Bi(
            start_fenxing=start_fx,
            end_fenxing=end_fx,
            direction=direction,
            klines=klines
        )
        
        # 检查笔的有效性
        if self._is_valid_bi(bi):
            self._current_bis.append(bi)
            
            # 重要：清空临时分型列表，让下一个分型重新开始
            # 但保留结束分型作为下一笔的潜在起点
            self._temp_fenxings = [end_fx]
    
    def _get_klines_between_fenxings(self, start_fx: FenXing, end_fx: FenXing) -> List[KLine]:
        """
        获取两个分型之间的K线
        
        Args:
            start_fx: 起始分型
            end_fx: 结束分型
            
        Returns:
            K线列表
        """
        if not self._all_klines:
            # 没有完整K线序列时的简化处理
            return [start_fx.kline, end_fx.kline]
        
        # 找到分型对应的K线索引
        start_index = -1
        end_index = -1
        
        for i, kline in enumerate(self._all_klines):
            if kline.timestamp == start_fx.timestamp:
                start_index = i
            elif kline.timestamp == end_fx.timestamp:
                end_index = i
                break
        
        # 如果找不到对应的K线，使用简化处理
        if start_index == -1 or end_index == -1 or start_index >= end_index:
            return [start_fx.kline, end_fx.kline]
        
        # 返回两个分型之间的所有K线（包含起始和结束分型的K线）
        return self._all_klines[start_index:end_index + 1]
    
    def _is_valid_bi(self, bi: Bi) -> bool:
        """
        检查笔是否有效
        
        Args:
            bi: 笔对象
            
        Returns:
            是否有效
        """
        # 基本检查：价格有效性
        if bi.start_price <= 0 or bi.end_price <= 0:
            return False
        
        # 检查幅度（使用更宽松的标准）
        if bi.amplitude_ratio < self.config.min_amplitude_ratio:
            return False
        
        # 检查K线数量（允许更少的K线）
        if len(bi.klines) < max(2, self.config.min_bi_length):
            return False
        
        # 检查分型有效性（使用宽松模式）
        if not bi.start_fenxing.is_valid_fenxing(min_strength=0.0, strict_mode=False):
            return False
        if not bi.end_fenxing.is_valid_fenxing(min_strength=0.0, strict_mode=False):
            return False
        
        # 如果需要确认，检查确认状态
        if self.config.require_confirmation:
            return (bi.start_fenxing.is_confirmed and 
                    bi.end_fenxing.is_confirmed and
                    bi.start_fenxing.confirm_kline_count >= self.config.confirm_klines and
                    bi.end_fenxing.confirm_kline_count >= self.config.confirm_klines)
        
        return True


class BiList:
    """
    笔列表容器
    管理一系列笔，提供查询、过滤、统计等功能
    """
    
    def __init__(self, bis: Optional[List[Bi]] = None, level: Optional[TimeLevel] = None):
        """
        初始化笔列表
        
        Args:
            bis: 笔列表
            level: 时间级别
        """
        self._bis: List[Bi] = bis or []
        self._level = level
        
        # 按时间排序
        self._bis.sort(key=lambda b: b.start_time)
    
    def __len__(self) -> int:
        """笔数量"""
        return len(self._bis)
    
    def __getitem__(self, index: int) -> Bi:
        """索引访问"""
        return self._bis[index]
    
    def __iter__(self) -> Iterator[Bi]:
        """迭代器"""
        return iter(self._bis)
    
    @property
    def bis(self) -> List[Bi]:
        """获取笔列表"""
        return self._bis
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """获取时间级别"""
        return self._level
    
    def append(self, bi: Bi) -> None:
        """添加笔并保持时间顺序"""
        self._bis.append(bi)
        self._bis.sort(key=lambda b: b.start_time)
    
    def extend(self, bis: List[Bi]) -> None:
        """批量添加笔"""
        self._bis.extend(bis)
        self._bis.sort(key=lambda b: b.start_time)
    
    @classmethod
    def from_fenxings(cls, fenxings: List[FenXing], config: Optional[BiConfig] = None, 
                      level: Optional[TimeLevel] = None, klines: Optional[List[KLine]] = None) -> 'BiList':
        """
        从分型列表构建笔列表
        
        Args:
            fenxings: 分型列表
            config: 笔构建配置
            level: 时间级别
            klines: 完整的K线序列（可选）
            
        Returns:
            构建的笔列表
        """
        builder = BiBuilder(config)
        bis = builder.build_from_fenxings(fenxings, klines)
        return cls(bis, level)
    
    def clear(self) -> None:
        """清空笔列表"""
        self._bis.clear()
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._bis) == 0
    
    def get_up_bis(self) -> List[Bi]:
        """获取所有向上笔"""
        return [bi for bi in self._bis if bi.is_up]
    
    def get_down_bis(self) -> List[Bi]:
        """获取所有向下笔"""
        return [bi for bi in self._bis if bi.is_down]
    
    def get_by_direction(self, direction: BiDirection) -> List[Bi]:
        """按方向获取笔"""
        return [bi for bi in self._bis if bi.direction == direction]
    
    def filter_by_strength(self, min_strength: float) -> List[Bi]:
        """按强度过滤笔"""
        return [bi for bi in self._bis if bi.strength >= min_strength]
    
    def filter_by_amplitude(self, min_amplitude: float) -> List[Bi]:
        """按幅度过滤笔"""
        return [bi for bi in self._bis if bi.amplitude_ratio >= min_amplitude]
    
    def filter_by_duration(self, min_duration: int) -> List[Bi]:
        """按持续时间过滤笔"""
        return [bi for bi in self._bis if bi.duration >= min_duration]
    
    def get_valid_bis(self, **kwargs) -> List[Bi]:
        """获取所有有效笔"""
        return [bi for bi in self._bis if bi.is_valid_bi(**kwargs)]
    
    def get_latest(self, count: int = 1) -> List[Bi]:
        """获取最新的N个笔"""
        return self._bis[-count:] if len(self._bis) >= count else self._bis
    
    def get_earliest(self, count: int = 1) -> List[Bi]:
        """获取最早的N个笔"""
        return self._bis[:count] if len(self._bis) >= count else self._bis
    
    def find_overlapping_bis(self, threshold: float = 0.5) -> List[tuple]:
        """
        查找重叠的笔对
        
        Args:
            threshold: 重叠阈值
            
        Returns:
            重叠笔对列表
        """
        overlapping_pairs = []
        
        for i in range(len(self._bis)):
            for j in range(i + 1, len(self._bis)):
                bi1, bi2 = self._bis[i], self._bis[j]
                overlap = bi1.overlap_with(bi2)
                if overlap >= threshold:
                    overlapping_pairs.append((bi1, bi2, overlap))
        
        return overlapping_pairs
    
    def validate_sequence(self) -> List[str]:
        """
        验证笔序列的合理性
        
        Returns:
            错误信息列表
        """
        errors = []
        
        if len(self._bis) <= 1:
            return errors
        
        for i in range(len(self._bis) - 1):
            current_bi = self._bis[i]
            next_bi = self._bis[i + 1]
            
            # 检查时间顺序（允许在分型连接处的时间相等，这在缠论中是正常的）
            if current_bi.end_time > next_bi.start_time:
                errors.append(f"笔{i+1}和笔{i+2}时间异常重叠")
            
            # 检查连接性
            if current_bi.end_fenxing != next_bi.start_fenxing:
                errors.append(f"笔{i+1}和笔{i+2}未正确连接")
            
            # 检查方向交替
            if current_bi.direction == next_bi.direction:
                errors.append(f"笔{i+1}和笔{i+2}方向相同")
        
        return errors
    
    def validate_chan_theory_rules(self) -> List[str]:
        """
        验证笔序列是否符合缠论规则
        
        Returns:
            违规信息列表
        """
        violations = []
        
        if len(self._bis) < 3:
            return violations
        
        for i in range(len(self._bis) - 2):
            bi1 = self._bis[i]
            bi2 = self._bis[i + 1]
            bi3 = self._bis[i + 2]
            
            # 检查三笔的方向模式（应该是交替的）
            if not (bi1.direction != bi2.direction and bi2.direction != bi3.direction):
                violations.append(f"笔{i+1}-{i+3}方向模式违规")
            
            # 检查同向笔的极值关系（宽松验证，允许不创新高/新低）
            if bi1.direction == bi3.direction:
                if bi1.is_up and bi3.is_up:
                    # 向上笔：检查是否有明显的价格背离（过于严格会误判正常的震荡）
                    price_diff_ratio = abs(bi3.end_price - bi1.end_price) / bi1.end_price
                    if price_diff_ratio > 0.1 and bi3.end_price < bi1.end_price * 0.95:  # 明显下跌超过5%
                        violations.append(f"向上笔{i+3}出现明显背离")
                elif bi1.is_down and bi3.is_down:
                    # 向下笔：检查是否有明显的价格背离
                    price_diff_ratio = abs(bi3.end_price - bi1.end_price) / bi1.end_price  
                    if price_diff_ratio > 0.1 and bi3.end_price > bi1.end_price * 1.05:  # 明显上涨超过5%
                        violations.append(f"向下笔{i+3}出现明显背离")
        
        return violations
    
    def find_trend_continuation_patterns(self) -> List[Dict[str, Any]]:
        """
        识别趋势延续模式
        
        Returns:
            趋势延续模式列表
        """
        patterns = []
        
        if len(self._bis) < 5:
            return patterns
        
        for i in range(len(self._bis) - 4):
            bis_group = self._bis[i:i+5]
            
            # 检查是否形成标准的五笔趋势延续模式
            if self._is_trend_continuation_pattern(bis_group):
                patterns.append({
                    'start_index': i,
                    'end_index': i + 4,
                    'direction': bis_group[0].direction,
                    'strength': self._calculate_pattern_strength(bis_group)
                })
        
        return patterns
    
    def _is_trend_continuation_pattern(self, bis_group: List[Bi]) -> bool:
        """
        检查五笔是否构成趋势延续模式
        
        Args:
            bis_group: 五笔序列
            
        Returns:
            是否为趋势延续模式
        """
        if len(bis_group) != 5:
            return False
        
        # 检查方向交替模式
        for i in range(4):
            if bis_group[i].direction == bis_group[i + 1].direction:
                return False
        
        # 检查同向笔的强度递增
        if bis_group[0].direction == bis_group[2].direction == bis_group[4].direction:
            if bis_group[0].is_up:
                return (bis_group[2].end_price > bis_group[0].end_price and
                        bis_group[4].end_price > bis_group[2].end_price)
            else:
                return (bis_group[2].end_price < bis_group[0].end_price and
                        bis_group[4].end_price < bis_group[2].end_price)
        
        return False
    
    def _calculate_pattern_strength(self, bis_group: List[Bi]) -> float:
        """
        计算模式强度
        
        Args:
            bis_group: 笔序列
            
        Returns:
            模式强度
        """
        total_strength = sum(bi.strength for bi in bis_group)
        avg_strength = total_strength / len(bis_group)
        return avg_strength
    
    def detect_potential_reversal_points(self) -> List[Dict[str, Any]]:
        """
        检测潜在的反转点
        
        Returns:
            反转点信息列表
        """
        reversal_points = []
        
        if len(self._bis) < 3:
            return reversal_points
        
        for i in range(1, len(self._bis) - 1):
            prev_bi = self._bis[i - 1]
            current_bi = self._bis[i]
            next_bi = self._bis[i + 1]
            
            # 检查力度背驰
            if self._has_momentum_divergence(prev_bi, current_bi, next_bi):
                reversal_points.append({
                    'bi_index': i,
                    'price': current_bi.end_price,
                    'timestamp': current_bi.end_time,
                    'type': 'momentum_divergence',
                    'confidence': self._calculate_reversal_confidence(prev_bi, current_bi, next_bi)
                })
        
        return reversal_points
    
    def _has_momentum_divergence(self, prev_bi: Bi, current_bi: Bi, next_bi: Bi) -> bool:
        """
        检查是否存在力度背驰
        
        Args:
            prev_bi: 前一笔
            current_bi: 当前笔
            next_bi: 下一笔
            
        Returns:
            是否存在力度背驰
        """
        # 简化的力度背驰检测
        if prev_bi.direction == next_bi.direction:
            if prev_bi.is_up and next_bi.is_up:
                # 向上笔：价格创新高但力度减弱
                return (next_bi.end_price > prev_bi.end_price and 
                        next_bi.strength < prev_bi.strength * 0.8)
            elif prev_bi.is_down and next_bi.is_down:
                # 向下笔：价格创新低但力度减弱
                return (next_bi.end_price < prev_bi.end_price and 
                        next_bi.strength < prev_bi.strength * 0.8)
        
        return False
    
    def _calculate_reversal_confidence(self, prev_bi: Bi, current_bi: Bi, next_bi: Bi) -> float:
        """
        计算反转信号的置信度
        
        Returns:
            置信度（0-1）
        """
        confidence = 0.5
        
        # 基于力度差异调整置信度
        if prev_bi.direction == next_bi.direction:
            strength_ratio = next_bi.strength / prev_bi.strength if prev_bi.strength > 0 else 0.5
            if strength_ratio < 0.6:
                confidence += 0.3
            elif strength_ratio < 0.8:
                confidence += 0.2
        
        # 基于价格创新程度调整置信度
        if prev_bi.direction == next_bi.direction:
            if prev_bi.is_up and next_bi.is_up:
                price_ratio = (next_bi.end_price - prev_bi.end_price) / prev_bi.end_price
                if price_ratio > 0.05:  # 创新高超过5%
                    confidence += 0.1
            elif prev_bi.is_down and next_bi.is_down:
                price_ratio = (prev_bi.end_price - next_bi.end_price) / prev_bi.end_price
                if price_ratio > 0.05:  # 创新低超过5%
                    confidence += 0.1
        
        return min(1.0, confidence)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取笔统计信息"""
        if self.is_empty():
            return {
                'total_count': 0,
                'up_count': 0,
                'down_count': 0,
                'avg_amplitude': 0.0,
                'avg_strength': 0.0,
                'avg_duration': 0.0
            }
        
        up_bis = self.get_up_bis()
        down_bis = self.get_down_bis()
        
        return {
            'total_count': len(self._bis),
            'up_count': len(up_bis),
            'down_count': len(down_bis),
            'valid_count': len(self.get_valid_bis()),
            'avg_amplitude': sum(bi.amplitude_ratio for bi in self._bis) / len(self._bis),
            'avg_strength': sum(bi.strength for bi in self._bis) / len(self._bis),
            'avg_duration': sum(bi.duration for bi in self._bis) / len(self._bis),
            'avg_purity': sum(bi.purity for bi in self._bis) / len(self._bis),
            'price_range': (
                min(min(bi.start_price, bi.end_price) for bi in self._bis),
                max(max(bi.start_price, bi.end_price) for bi in self._bis)
            ),
            'time_range': (
                min(bi.start_time for bi in self._bis),
                max(bi.end_time for bi in self._bis)
            ) if self._bis else (None, None)
        }
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [bi.to_dict() for bi in self._bis]
    
    def __str__(self) -> str:
        """字符串表示"""
        level_str = f"({self._level.value})" if self._level else ""
        stats = self.get_statistics()
        return (f"BiList{level_str}[{stats['total_count']} bis: "
                f"{stats['up_count']} up, {stats['down_count']} down, "
                f"avg_amp:{stats['avg_amplitude']:.2%}]")