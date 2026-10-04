#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论线段数据模型
参考Vespa314/chan.py的线段设计，实现标准的线段识别和管理
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Iterator
from .enums import SegDirection, BiDirection, TimeLevel
from .kline import KLine
from .fenxing import FenXing
from .bi import Bi


@dataclass
class Seg:
    """
    线段数据模型
    代表缠论中由多个笔构成的线段
    """
    # 基础信息
    bis: List[Bi]                    # 构成线段的笔列表
    direction: SegDirection          # 线段方向
    
    # 线段端点
    start_fenxing: Optional[FenXing] = None  # 起始分型
    end_fenxing: Optional[FenXing] = None    # 结束分型
    
    # 线段特征
    strength: float = 0.0            # 线段强度
    integrity: float = 0.0           # 线段完整性
    
    # 确认信息
    is_confirmed: bool = False       # 是否已确认
    break_confirmed: bool = False    # 是否确认被突破
    
    # 特征序列
    feature_sequence: List[Bi] = field(default_factory=list)  # 特征序列
    
    def __post_init__(self):
        """初始化后处理"""
        self._validate()
        self._extract_endpoints()
        self._calculate_metrics()
    
    def _validate(self) -> None:
        """数据有效性验证"""
        if not self.bis:
            raise ValueError("线段必须包含至少一个笔")
        
        if len(self.bis) < 3:
            raise ValueError("标准线段至少需要3个笔")
        
        # 验证笔的连续性
        for i in range(len(self.bis) - 1):
            if self.bis[i].end_fenxing != self.bis[i + 1].start_fenxing:
                raise ValueError(f"笔{i}和笔{i+1}不连续")
        
        # 验证整体方向
        expected_direction = SegDirection.from_bi_direction(self.bis[0].direction)
        if self.direction != expected_direction:
            raise ValueError(f"线段方向与起始笔方向不匹配")
    
    def _extract_endpoints(self) -> None:
        """提取线段端点"""
        if not self.bis:
            return
        
        self.start_fenxing = self.bis[0].start_fenxing
        self.end_fenxing = self.bis[-1].end_fenxing
    
    def _calculate_metrics(self) -> None:
        """计算线段各项指标"""
        self.strength = self._calculate_strength()
        self.integrity = self._calculate_integrity()
        self._extract_feature_sequence()
    
    def _calculate_strength(self) -> float:
        """
        计算线段强度
        基于价格变化、成交量和笔的质量
        """
        if not self.bis:
            return 0.0
        
        # 价格强度
        price_strength = self.amplitude_ratio
        
        # 笔质量强度
        avg_bi_strength = sum(bi.strength for bi in self.bis) / len(self.bis)
        
        # 方向一致性强度
        main_direction_bis = [bi for bi in self.bis if 
                             (self.is_up and bi.is_up) or (self.is_down and bi.is_down)]
        direction_consistency = len(main_direction_bis) / len(self.bis)
        
        # 综合强度
        return (price_strength * 0.5 + 
                avg_bi_strength * 0.3 + 
                direction_consistency * 0.2)
    
    def _calculate_integrity(self) -> float:
        """
        计算线段完整性
        衡量线段结构的完整程度
        """
        if len(self.bis) < 3:
            return 0.0
        
        # 检查是否有完整的上涨-下跌-上涨 或 下跌-上涨-下跌 结构
        pattern_score = 0.0
        
        if self.is_up:
            # 向上线段：应该是 上-下-上-下... 的模式
            expected_pattern = [BiDirection.UP, BiDirection.DOWN]
        else:
            # 向下线段：应该是 下-上-下-上... 的模式
            expected_pattern = [BiDirection.DOWN, BiDirection.UP]
        
        matched_patterns = 0
        for i, bi in enumerate(self.bis):
            expected_direction = expected_pattern[i % 2]
            if bi.direction == expected_direction:
                matched_patterns += 1
        
        pattern_score = matched_patterns / len(self.bis)
        
        # 检查特征序列的质量
        feature_quality = len(self.feature_sequence) / len(self.bis) if self.bis else 0
        
        return (pattern_score * 0.7 + feature_quality * 0.3)
    
    def _extract_feature_sequence(self) -> None:
        """
        提取特征序列
        线段中与线段方向相同的笔构成特征序列
        """
        self.feature_sequence = []
        
        for bi in self.bis:
            if ((self.is_up and bi.is_up) or 
                (self.is_down and bi.is_down)):
                self.feature_sequence.append(bi)
    
    @property
    def start_price(self) -> float:
        """起始价格"""
        return self.start_fenxing.price if self.start_fenxing else 0.0
    
    @property
    def end_price(self) -> float:
        """结束价格"""
        return self.end_fenxing.price if self.end_fenxing else 0.0
    
    @property
    def start_time(self) -> datetime:
        """开始时间"""
        return self.start_fenxing.timestamp if self.start_fenxing else datetime.min
    
    @property
    def end_time(self) -> datetime:
        """结束时间"""
        return self.end_fenxing.timestamp if self.end_fenxing else datetime.min
    
    @property
    def duration(self) -> int:
        """持续时间（K线数量）"""
        return sum(bi.duration for bi in self.bis)
    
    @property
    def amplitude(self) -> float:
        """线段幅度（绝对值）"""
        return abs(self.end_price - self.start_price)
    
    @property
    def amplitude_ratio(self) -> float:
        """线段幅度比例"""
        return self.amplitude / self.start_price if self.start_price > 0 else 0.0
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """线段级别"""
        return self.bis[0].level if self.bis else None
    
    @property
    def is_up(self) -> bool:
        """是否为向上线段"""
        return self.direction == SegDirection.UP
    
    @property  
    def is_down(self) -> bool:
        """是否为向下线段"""
        return self.direction == SegDirection.DOWN
    
    @property
    def high_price(self) -> float:
        """线段最高价"""
        if not self.bis:
            return max(self.start_price, self.end_price)
        return max(bi.high_price for bi in self.bis)
    
    @property
    def low_price(self) -> float:
        """线段最低价"""
        if not self.bis:
            return min(self.start_price, self.end_price)
        return min(bi.low_price for bi in self.bis)
    
    @property
    def total_volume(self) -> int:
        """线段总成交量"""
        return sum(bi.total_volume for bi in self.bis)
    
    @property
    def bi_count(self) -> int:
        """线段包含的笔数量"""
        return len(self.bis)
    
    @property
    def feature_bi_count(self) -> int:
        """特征序列笔数量"""
        return len(self.feature_sequence)
    
    def get_main_trend_bis(self) -> List[Bi]:
        """获取主趋势方向的笔"""
        return self.feature_sequence
    
    def get_counter_trend_bis(self) -> List[Bi]:
        """获取反趋势方向的笔"""
        counter_bis = []
        for bi in self.bis:
            if ((self.is_up and bi.is_down) or 
                (self.is_down and bi.is_up)):
                counter_bis.append(bi)
        return counter_bis
    
    def is_valid_seg(self, min_bi_count: int = 3, min_amplitude: float = 0.01) -> bool:
        """
        判断是否为有效线段
        
        Args:
            min_bi_count: 最少笔数
            min_amplitude: 最小幅度
            
        Returns:
            是否有效
        """
        # 检查笔数
        if len(self.bis) < min_bi_count:
            return False
        
        # 检查幅度
        if self.amplitude_ratio < min_amplitude:
            return False
        
        # 检查完整性
        if self.integrity < 0.5:
            return False
        
        # 检查特征序列
        if len(self.feature_sequence) < 2:
            return False
        
        return True
    
    def is_broken_by_seg(self, other: 'Seg', threshold: float = 0.01) -> bool:
        """
        判断是否被另一个线段破坏
        
        Args:
            other: 另一个线段
            threshold: 破坏阈值
            
        Returns:
            是否被破坏
        """
        if self.direction == other.direction:
            return False  # 同方向不构成破坏
        
        if self.is_up and other.is_down:
            # 向上线段被向下线段破坏
            break_price = self.start_price * (1 - threshold)
            return other.end_price < break_price
        elif self.is_down and other.is_up:
            # 向下线段被向上线段破坏
            break_price = self.start_price * (1 + threshold)
            return other.end_price > break_price
        
        return False
    
    def overlaps_with(self, other: 'Seg') -> float:
        """
        计算与另一个线段的重叠度
        
        Args:
            other: 另一个线段
            
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
            return 0.0
        
        overlap_range = overlap_high - overlap_low
        self_range = self_high - self_low
        other_range = other_high - other_low
        
        if self_range == 0 or other_range == 0:
            return 0.0
        
        min_range = min(self_range, other_range)
        return overlap_range / min_range
    
    def can_form_zhongshu_with(self, other1: 'Seg', other2: 'Seg') -> bool:
        """
        判断能否与另外两个线段构成中枢
        
        Args:
            other1: 第二个线段
            other2: 第三个线段
            
        Returns:
            是否可以构成中枢
        """
        # 检查方向：应该是 上-下-上 或 下-上-下
        if not ((self.is_up and other1.is_down and other2.is_up) or
                (self.is_down and other1.is_up and other2.is_down)):
            return False
        
        # 检查重叠
        overlap1 = self.overlaps_with(other2)  # 第一和第三线段的重叠
        return overlap1 > 0.001  # 降低到0.1%的重叠，适应实际市场情况
    
    def get_retracement_levels(self) -> Dict[str, float]:
        """
        获取回撤水平
        基于斐波那契回撤
        """
        if self.amplitude == 0:
            return {}
        
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        levels = {}
        
        for level in fib_levels:
            if self.is_up:
                retracement_price = self.end_price - (self.amplitude * level)
            else:
                retracement_price = self.end_price + (self.amplitude * level)
            
            levels[f"{level:.1%}"] = retracement_price
        
        return levels
    
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
            'integrity': self.integrity,
            'is_confirmed': self.is_confirmed,
            'break_confirmed': self.break_confirmed,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'total_volume': self.total_volume,
            'bi_count': self.bi_count,
            'feature_bi_count': self.feature_bi_count,
            'level': self.level.value if self.level else None,
            'retracement_levels': self.get_retracement_levels()
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"{self.direction.value}线段: {self.start_price:.2f}->{self.end_price:.2f} "
                f"({self.amplitude_ratio:.2%}, {self.bi_count}笔, 强度:{self.strength:.3f})")
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if not isinstance(other, Seg):
            return False
        return (self.start_fenxing == other.start_fenxing and
                self.end_fenxing == other.end_fenxing)
    
    def __lt__(self, other) -> bool:
        """小于比较（按开始时间排序）"""
        if not isinstance(other, Seg):
            return NotImplemented
        return self.start_time < other.start_time


@dataclass
class SegConfig:
    """
    线段构建配置类
    基于缠论第67课标准，使用特征序列分型判断
    优化参数以提高线段识别敏感性
    """
    # 构建模式
    build_mode: str = "chan"        # "chan"(原文), "def"(定义), "dyh"(都业华)
    
    # 基本参数 - 降低要求提高敏感性
    min_bi_count: int = 3           # 最少笔数（保持标准）
    min_amplitude_ratio: float = 0.005  # 最小幅度比例（提高要求过滤噪音）
    
    # 特征序列参数 - 这是核心
    eigen_fx_check: bool = True     # 是否检查特征序列分型
    min_eigen_count: int = 1        # 最少特征序列笔数（降低要求）
    
    # 线段质量控制
    min_integrity: float = 0.3      # 最小完整性要求（降低）
    enable_loose_termination: bool = True  # 启用宽松终止条件
    
    # 已废弃的参数（保留兼容性）
    require_overlap: bool = False   # 不再使用前三笔重叠检查
    break_confirm_mode: str = "loose"  # 使用宽松模式
    require_new_seg: bool = False   # 不要求新线段确认


class SegBuilder:
    """
    线段构建器
    负责从笔序列构建线段序列，实现缠论中线段的核心算法
    """
    
    def __init__(self, config: Optional[SegConfig] = None):
        """
        初始化线段构建器
        
        Args:
            config: 线段构建配置
        """
        self.config = config or SegConfig()
        self._current_segs: List[Seg] = []
        self._temp_bis: List[Bi] = []
        
    def build_from_bis(self, bis: List[Bi]) -> List[Seg]:
        """
        从笔序列构建线段序列
        
        Args:
            bis: 笔列表（按时间排序）
            
        Returns:
            构建的线段列表
        """
        if len(bis) < self.config.min_bi_count:
            return []
        
        # 清空之前的状态
        self._current_segs.clear()
        self._temp_bis.clear()
        
        # 逐个处理笔，构建线段
        for bi in bis:
            self._process_bi(bi)
        
        # 处理最后剩余的笔
        if len(self._temp_bis) >= self.config.min_bi_count:
            self._try_create_final_seg()
        
        return self._current_segs.copy()
    
    def _process_bi(self, bi: Bi) -> None:
        """
        处理单个笔，尝试构建或更新线段
        基于缠论特征序列方法
        
        Args:
            bi: 待处理的笔
        """
        self._temp_bis.append(bi)
        
        # 当有足够笔时，检查是否应该结束线段
        if len(self._temp_bis) >= self.config.min_bi_count:
            if self._check_seg_termination_by_eigen_sequence():
                self._create_seg()
    
    def _can_create_seg(self) -> bool:
        """
        检查当前临时笔列表是否可以构建线段
        基于缠论第67课标准：使用特征序列分型判断线段结束
        
        Returns:
            是否可以构建线段
        """
        if len(self._temp_bis) < self.config.min_bi_count:
            return False
        
        # 使用特征序列分型判断是否应该结束线段
        return self._check_seg_termination_by_eigen_sequence()
    
    def _check_seg_termination_by_eigen_sequence(self) -> bool:
        """
        基于特征序列分型判断线段是否应该结束
        这是缠论第67课的核心方法，增加宽松终止条件
        
        Returns:
            是否应该结束线段
        """
        if len(self._temp_bis) < 3:
            return False
        
        # 基础检查：特征序列分型
        eigen_sequence = self._extract_eigen_sequence_corrected(self._temp_bis)
        
        # 降低特征序列要求
        min_eigen_required = max(1, self.config.min_eigen_count)
        if len(eigen_sequence) < min_eigen_required:
            return False
        
        # 如果启用宽松终止条件，增加额外判断
        if self.config.enable_loose_termination and len(self._temp_bis) >= 5:
            # 检查线段长度是否过长（超过9笔考虑终止）
            if len(self._temp_bis) >= 9:
                return True
                
            # 检查最近的笔是否显示反转迹象
            if self._check_reversal_signals():
                return True
        
        # 标准特征序列分型检查
        if len(eigen_sequence) >= 3:
            standard_eigen_seq = self._process_eigen_sequence_inclusion(eigen_sequence)
            
            if len(standard_eigen_seq) >= 3:
                return self._check_eigen_sequence_fenxing(standard_eigen_seq)
        
        return False
    
    def _check_reversal_signals(self) -> bool:
        """
        检查最近的笔是否显示反转迹象
        用于宽松模式下的线段终止判断
        
        Returns:
            是否有反转信号
        """
        if len(self._temp_bis) < 4:
            return False
        
        # 获取最后几笔
        recent_bis = self._temp_bis[-4:]
        
        # 检查笔的强度递减（可能的背驰信号）
        strengths = [bi.strength for bi in recent_bis]
        if len(strengths) >= 3:
            # 检查是否存在强度递减趋势
            decreasing_trend = all(strengths[i] >= strengths[i+1] for i in range(len(strengths)-1))
            if decreasing_trend and strengths[-1] < strengths[0] * 0.7:
                return True
        
        # 检查价格动能衰减
        recent_amplitudes = [bi.amplitude_ratio for bi in recent_bis]
        if len(recent_amplitudes) >= 3:
            # 检查振幅递减
            amplitude_decreasing = all(recent_amplitudes[i] >= recent_amplitudes[i+1] for i in range(len(recent_amplitudes)-1))
            if amplitude_decreasing and recent_amplitudes[-1] < recent_amplitudes[0] * 0.5:
                return True
        
        return False
    
    def _check_first_three_overlap(self) -> bool:
        """
        检查前三笔是否有重叠部分
        这是缠论线段成立的核心条件
        
        Returns:
            是否有重叠
        """
        if len(self._temp_bis) < 3:
            return False
        
        bi1, bi2, bi3 = self._temp_bis[:3]
        
        # 获取每笔的价格区间
        bi1_low = min(bi1.start_price, bi1.end_price)
        bi1_high = max(bi1.start_price, bi1.end_price)
        
        bi2_low = min(bi2.start_price, bi2.end_price)
        bi2_high = max(bi2.start_price, bi2.end_price)
        
        bi3_low = min(bi3.start_price, bi3.end_price)
        bi3_high = max(bi3.start_price, bi3.end_price)
        
        # 计算三笔的重叠区间
        overlap_low = max(bi1_low, bi2_low, bi3_low)
        overlap_high = min(bi1_high, bi2_high, bi3_high)
        
        # 有重叠则重叠区间的高点大于低点
        return overlap_high > overlap_low
    
    
    def _extract_eigen_sequence(self, bis: List[Bi]) -> List[Bi]:
        """
        提取特征序列
        向上线段的特征序列是所有向下笔，向下线段的特征序列是所有向上笔
        
        Args:
            bis: 笔列表
            
        Returns:
            特征序列笔列表
        """
        if len(bis) < 3:
            return []
        
        # 确定线段方向（由前三笔决定）
        seg_direction = self._determine_seg_direction(bis[:3])
        
        eigen_seq = []
        for bi in bis:
            # 提取与线段方向相反的笔作为特征序列
            if ((seg_direction == SegDirection.UP and bi.is_down) or
                (seg_direction == SegDirection.DOWN and bi.is_up)):
                eigen_seq.append(bi)
        
        return eigen_seq
    
    def _determine_seg_direction(self, first_three_bis: List[Bi]) -> SegDirection:
        """
        根据前三笔确定线段方向
        基于缠论标准：线段方向由第一笔的方向决定
        
        Args:
            first_three_bis: 前三笔
            
        Returns:
            线段方向
        """
        if len(first_three_bis) < 1:
            return SegDirection.UP
        
        # 线段方向由第一笔的方向决定
        # 向上笔开始的线段是向上线段，向下笔开始的线段是向下线段
        first_bi = first_three_bis[0]
        
        if first_bi.is_up:
            return SegDirection.UP
        else:
            return SegDirection.DOWN
    
    def _check_eigen_break(self, eigen_seq: List[Bi]) -> bool:
        """
        检查特征序列是否被破坏
        根据特征序列的分型来判断
        
        Args:
            eigen_seq: 特征序列
            
        Returns:
            是否被破坏
        """
        if len(eigen_seq) < 3:
            return False
        
        # 检查最后三个特征序列元素是否形成破坏条件
        last_three = eigen_seq[-3:]
        
        # 简化的破坏判断：检查是否形成新的极值
        if self.config.build_mode == "chan":
            return self._check_chan_break(last_three)
        elif self.config.build_mode == "def":
            return self._check_def_break(last_three)
        else:
            return self._check_dyh_break(last_three)
    
    def _extract_eigen_sequence_corrected(self, bis: List[Bi]) -> List[Bi]:
        """
        正确提取特征序列
        根据缠论第67课：向上线段的特征序列是向下的笔，向下线段的特征序列是向上的笔
        
        Args:
            bis: 笔列表
            
        Returns:
            特征序列笔列表
        """
        if len(bis) < 3:
            return []
        
        # 确定线段方向（由第一笔的方向决定线段的起始方向）
        seg_direction = self._determine_seg_direction(bis[:3])
        
        eigen_seq = []
        for bi in bis:
            # 提取与线段方向相反的笔作为特征序列
            if ((seg_direction == SegDirection.UP and bi.is_down) or
                (seg_direction == SegDirection.DOWN and bi.is_up)):
                eigen_seq.append(bi)
        
        return eigen_seq
    
    def _process_eigen_sequence_inclusion(self, eigen_seq: List[Bi]) -> List[Bi]:
        """
        对特征序列进行非包含处理
        根据缠论理论，需要对特征序列进行非包含处理形成标准特征序列
        
        Args:
            eigen_seq: 原始特征序列
            
        Returns:
            处理后的标准特征序列
        """
        if len(eigen_seq) < 2:
            return eigen_seq
        
        processed_seq = [eigen_seq[0]]
        
        for i in range(1, len(eigen_seq)):
            current_bi = eigen_seq[i]
            last_bi = processed_seq[-1]
            
            # 检查包含关系
            current_high = max(current_bi.start_price, current_bi.end_price)
            current_low = min(current_bi.start_price, current_bi.end_price)
            last_high = max(last_bi.start_price, last_bi.end_price)
            last_low = min(last_bi.start_price, last_bi.end_price)
            
            # 如果当前笔被上一笔包含
            if current_high <= last_high and current_low >= last_low:
                # 被包含，不加入序列
                continue
            # 如果当前笔包含上一笔
            elif current_high >= last_high and current_low <= last_low:
                # 替换上一笔
                processed_seq[-1] = current_bi
            else:
                # 无包含关系，直接加入
                processed_seq.append(current_bi)
        
        return processed_seq
    
    def _check_eigen_sequence_fenxing(self, eigen_seq: List[Bi]) -> bool:
        """
        检查特征序列是否出现分型
        根据缠论第67课：特征序列出现顶分型或底分型时，线段结束
        
        Args:
            eigen_seq: 标准特征序列
            
        Returns:
            是否出现分型
        """
        if len(eigen_seq) < 3:
            return False
        
        # 检查最后三个元素是否构成分型
        last_three = eigen_seq[-3:]
        
        # 获取三个笔的价格极值
        prices = []
        for bi in last_three:
            if bi.is_up:
                prices.append(bi.end_price)  # 向上笔的终点价格
            else:
                prices.append(bi.end_price)  # 向下笔的终点价格
        
        # 检查是否构成顶分型（中间高于两边）
        if prices[1] > prices[0] and prices[1] > prices[2]:
            return True
        
        # 检查是否构成底分型（中间低于两边）
        if prices[1] < prices[0] and prices[1] < prices[2]:
            return True
        
        return False
    
    def _check_chan_break(self, last_three: List[Bi]) -> bool:
        """
        缠论原文的破坏判断
        """
        bi1, bi2, bi3 = last_three
        
        # 检查是否形成了新的分型结构
        if bi1.is_down and bi2.is_down and bi3.is_down:
            # 向下特征序列：检查是否创新低
            return bi3.end_price < min(bi1.end_price, bi2.end_price)
        elif bi1.is_up and bi2.is_up and bi3.is_up:
            # 向上特征序列：检查是否创新高
            return bi3.end_price > max(bi1.end_price, bi2.end_price)
        
        return False
    
    def _check_def_break(self, last_three: List[Bi]) -> bool:
        """
        定义模式的破坏判断（更严格）
        """
        # 这里可以实现更严格的破坏条件
        return self._check_chan_break(last_three)
    
    def _check_dyh_break(self, last_three: List[Bi]) -> bool:
        """
        都业华1+1突破的破坏判断
        """
        # 这里可以实现都业华的1+1突破逻辑
        return self._check_chan_break(last_three)
    
    def _create_seg(self) -> None:
        """
        创建新线段
        """
        if len(self._temp_bis) < self.config.min_bi_count:
            return
        
        # 确定线段方向
        direction = self._determine_seg_direction(self._temp_bis[:3])
        
        # 创建线段（不包含导致破坏的最后一笔）
        seg_bis = self._temp_bis[:-1] if len(self._temp_bis) > 3 else self._temp_bis
        
        if len(seg_bis) >= self.config.min_bi_count:
            seg = Seg(bis=seg_bis, direction=direction)
            
            if self._is_valid_seg(seg):
                self._current_segs.append(seg)
        
        # 重新开始，保留最后一笔作为新线段的起点
        if len(self._temp_bis) > 1:
            self._temp_bis = self._temp_bis[-1:]
        else:
            self._temp_bis = []
    
    def _try_create_final_seg(self) -> None:
        """
        尝试创建最后的线段（处理剩余笔）
        """
        if len(self._temp_bis) >= self.config.min_bi_count:
            direction = self._determine_seg_direction(self._temp_bis[:3])
            seg = Seg(bis=self._temp_bis.copy(), direction=direction)
            
            if self._is_valid_seg(seg):
                self._current_segs.append(seg)
    
    def _is_valid_seg(self, seg: Seg) -> bool:
        """
        检查线段是否有效
        
        Args:
            seg: 线段对象
            
        Returns:
            是否有效
        """
        return seg.is_valid_seg(
            min_bi_count=self.config.min_bi_count,
            min_amplitude=self.config.min_amplitude_ratio
        )


class SegList:
    """
    线段列表容器
    管理一系列线段，提供查询、过滤、统计等功能
    """
    
    def __init__(self, segs: Optional[List[Seg]] = None, level: Optional[TimeLevel] = None):
        """
        初始化线段列表
        
        Args:
            segs: 线段列表
            level: 时间级别
        """
        self._segs: List[Seg] = segs or []
        self._level = level
        
        # 按时间排序
        self._segs.sort(key=lambda s: s.start_time)
    
    def __len__(self) -> int:
        """线段数量"""
        return len(self._segs)
    
    def __getitem__(self, index: int) -> Seg:
        """索引访问"""
        return self._segs[index]
    
    def __iter__(self) -> Iterator[Seg]:
        """迭代器"""
        return iter(self._segs)
    
    @property
    def segs(self) -> List[Seg]:
        """获取线段列表"""
        return self._segs
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """获取时间级别"""
        return self._level
    
    def append(self, seg: Seg) -> None:
        """添加线段并保持时间顺序"""
        self._segs.append(seg)
        self._segs.sort(key=lambda s: s.start_time)
    
    def extend(self, segs: List[Seg]) -> None:
        """批量添加线段"""
        self._segs.extend(segs)
        self._segs.sort(key=lambda s: s.start_time)
    
    @classmethod
    def from_bis(cls, bis: List[Bi], config: Optional[SegConfig] = None, 
                 level: Optional[TimeLevel] = None) -> 'SegList':
        """
        从笔列表构建线段列表
        
        Args:
            bis: 笔列表
            config: 线段构建配置
            level: 时间级别
            
        Returns:
            构建的线段列表
        """
        builder = SegBuilder(config)
        segs = builder.build_from_bis(bis)
        return cls(segs, level)
    
    def clear(self) -> None:
        """清空线段列表"""
        self._segs.clear()
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._segs) == 0
    
    def get_up_segs(self) -> List[Seg]:
        """获取所有向上线段"""
        return [seg for seg in self._segs if seg.is_up]
    
    def get_down_segs(self) -> List[Seg]:
        """获取所有向下线段"""
        return [seg for seg in self._segs if seg.is_down]
    
    def get_by_direction(self, direction: SegDirection) -> List[Seg]:
        """按方向获取线段"""
        return [seg for seg in self._segs if seg.direction == direction]
    
    def filter_by_strength(self, min_strength: float) -> List[Seg]:
        """按强度过滤线段"""
        return [seg for seg in self._segs if seg.strength >= min_strength]
    
    def filter_by_amplitude(self, min_amplitude: float) -> List[Seg]:
        """按幅度过滤线段"""
        return [seg for seg in self._segs if seg.amplitude_ratio >= min_amplitude]
    
    def get_valid_segs(self, **kwargs) -> List[Seg]:
        """获取所有有效线段"""
        return [seg for seg in self._segs if seg.is_valid_seg(**kwargs)]
    
    def find_potential_zhongshus(self) -> List[Dict[str, Any]]:
        """
        查找潜在的中枢
        返回可能构成中枢的线段三元组及其详情
        """
        potential_zhongshus = []
        
        if len(self._segs) < 3:
            return potential_zhongshus
        
        for i in range(len(self._segs) - 2):
            seg1 = self._segs[i]
            seg2 = self._segs[i + 1]
            seg3 = self._segs[i + 2]
            
            if seg1.can_form_zhongshu_with(seg2, seg3):
                # 计算中枢区间
                overlap_high = min(max(seg1.start_price, seg1.end_price),
                                 max(seg3.start_price, seg3.end_price))
                overlap_low = max(min(seg1.start_price, seg1.end_price),
                                min(seg3.start_price, seg3.end_price))
                
                zhongshu_info = {
                    'index': i,
                    'segs': (seg1, seg2, seg3),
                    'high': overlap_high,
                    'low': overlap_low,
                    'amplitude': overlap_high - overlap_low,
                    'duration': seg3.end_time - seg1.start_time,
                    'direction': 'up' if seg1.is_up else 'down'
                }
                potential_zhongshus.append(zhongshu_info)
        
        return potential_zhongshus
    
    def detect_divergence_patterns(self) -> List[Dict[str, Any]]:
        """
        检测背驰模式
        识别可能的顶背驰和底背驰
        """
        divergences = []
        
        if len(self._segs) < 3:
            return divergences
        
        for i in range(2, len(self._segs)):
            current_seg = self._segs[i]
            prev_seg = self._segs[i - 2]  # 隔一个线段比较
            
            # 检查同方向线段的背驰
            if current_seg.direction == prev_seg.direction:
                divergence = self._check_divergence(prev_seg, current_seg)
                if divergence:
                    divergences.append({
                        'index': i,
                        'type': divergence['type'],
                        'prev_seg': prev_seg,
                        'current_seg': current_seg,
                        'strength_ratio': divergence['strength_ratio'],
                        'price_ratio': divergence['price_ratio'],
                        'confidence': divergence['confidence']
                    })
        
        return divergences
    
    def _check_divergence(self, prev_seg: Seg, current_seg: Seg) -> Optional[Dict[str, Any]]:
        """
        检查两个同方向线段是否存在背驰
        
        Args:
            prev_seg: 前一个线段
            current_seg: 当前线段
            
        Returns:
            背驰信息，如果不存在则返回None
        """
        if prev_seg.direction != current_seg.direction:
            return None
        
        # 计算价格和强度的比较
        if prev_seg.is_up and current_seg.is_up:
            # 向上线段：价格新高但强度减弱
            price_creates_high = current_seg.end_price > prev_seg.end_price
            strength_weakens = current_seg.strength < prev_seg.strength * 0.8
            
            if price_creates_high and strength_weakens:
                return {
                    'type': 'top_divergence',
                    'strength_ratio': current_seg.strength / prev_seg.strength,
                    'price_ratio': current_seg.end_price / prev_seg.end_price,
                    'confidence': 0.7 + (1 - current_seg.strength / prev_seg.strength) * 0.3
                }
        
        elif prev_seg.is_down and current_seg.is_down:
            # 向下线段：价格新低但强度减弱
            price_creates_low = current_seg.end_price < prev_seg.end_price
            strength_weakens = current_seg.strength < prev_seg.strength * 0.8
            
            if price_creates_low and strength_weakens:
                return {
                    'type': 'bottom_divergence',
                    'strength_ratio': current_seg.strength / prev_seg.strength,
                    'price_ratio': current_seg.end_price / prev_seg.end_price,
                    'confidence': 0.7 + (1 - current_seg.strength / prev_seg.strength) * 0.3
                }
        
        return None
    
    def find_trend_segments(self, min_segs: int = 3) -> List[Dict[str, Any]]:
        """
        识别趋势线段组合
        连续同方向的线段组成趋势
        
        Args:
            min_segs: 最少线段数量
            
        Returns:
            趋势信息列表
        """
        trends = []
        
        if len(self._segs) < min_segs:
            return trends
        
        current_trend = []
        current_direction = None
        
        for i, seg in enumerate(self._segs):
            if current_direction is None:
                current_direction = seg.direction
                current_trend = [seg]
            elif seg.direction == current_direction:
                current_trend.append(seg)
            else:
                # 方向改变，结束当前趋势
                if len(current_trend) >= min_segs:
                    trends.append(self._create_trend_info(current_trend, i - len(current_trend)))
                
                # 开始新趋势
                current_direction = seg.direction
                current_trend = [seg]
        
        # 处理最后的趋势
        if len(current_trend) >= min_segs:
            trends.append(self._create_trend_info(current_trend, len(self._segs) - len(current_trend)))
        
        return trends
    
    def _create_trend_info(self, segs: List[Seg], start_index: int) -> Dict[str, Any]:
        """
        创建趋势信息
        
        Args:
            segs: 线段列表
            start_index: 起始索引
            
        Returns:
            趋势信息
        """
        total_amplitude = sum(seg.amplitude for seg in segs)
        avg_strength = sum(seg.strength for seg in segs) / len(segs)
        
        return {
            'start_index': start_index,
            'end_index': start_index + len(segs) - 1,
            'direction': segs[0].direction,
            'seg_count': len(segs),
            'total_amplitude': total_amplitude,
            'avg_strength': avg_strength,
            'start_time': segs[0].start_time,
            'end_time': segs[-1].end_time,
            'start_price': segs[0].start_price,
            'end_price': segs[-1].end_price
        }
    
    def validate_seg_sequence(self) -> List[str]:
        """
        验证线段序列的合理性
        
        Returns:
            错误信息列表
        """
        errors = []
        
        if len(self._segs) <= 1:
            return errors
        
        for i in range(len(self._segs) - 1):
            current_seg = self._segs[i]
            next_seg = self._segs[i + 1]
            
            # 检查时间顺序
            if current_seg.end_time > next_seg.start_time:
                errors.append(f"线段{i+1}和线段{i+2}时间重叠")
            
            # 检查连接性
            if current_seg.end_fenxing != next_seg.start_fenxing:
                errors.append(f"线段{i+1}和线段{i+2}未正确连接")
            
            # 检查方向交替（这是理想情况，实际可能有连续同方向）
            if current_seg.direction == next_seg.direction:
                # 这不是错误，只是记录连续同方向的情况
                pass
        
        return errors
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取线段统计信息"""
        if self.is_empty():
            return {
                'total_count': 0,
                'up_count': 0,
                'down_count': 0,
                'avg_amplitude': 0.0,
                'avg_strength': 0.0,
                'avg_bi_count': 0.0
            }
        
        up_segs = self.get_up_segs()
        down_segs = self.get_down_segs()
        
        return {
            'total_count': len(self._segs),
            'up_count': len(up_segs),
            'down_count': len(down_segs),
            'valid_count': len(self.get_valid_segs()),
            'avg_amplitude': sum(seg.amplitude_ratio for seg in self._segs) / len(self._segs),
            'avg_strength': sum(seg.strength for seg in self._segs) / len(self._segs),
            'avg_integrity': sum(seg.integrity for seg in self._segs) / len(self._segs),
            'avg_bi_count': sum(seg.bi_count for seg in self._segs) / len(self._segs),
            'potential_zhongshus': len(self.find_potential_zhongshus()),
            'price_range': (
                min(min(seg.start_price, seg.end_price) for seg in self._segs),
                max(max(seg.start_price, seg.end_price) for seg in self._segs)
            ),
            'time_range': (
                min(seg.start_time for seg in self._segs),
                max(seg.end_time for seg in self._segs)
            ) if self._segs else (None, None)
        }
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [seg.to_dict() for seg in self._segs]
    
    def __str__(self) -> str:
        """字符串表示"""
        level_str = f"({self._level.value})" if self._level else ""
        stats = self.get_statistics()
        return (f"SegList{level_str}[{stats['total_count']} segs: "
                f"{stats['up_count']} up, {stats['down_count']} down, "
                f"avg_amp:{stats['avg_amplitude']:.2%}]")