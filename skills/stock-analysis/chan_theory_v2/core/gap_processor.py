#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论跳空缺口处理器
实现缺论中跳空缺口的识别和处理标准，包括缺口成笔的判断逻辑
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.kline import KLine, KLineList
from models.fenxing import FenXing
from models.enums import TimeLevel, BiDirection

logger = logging.getLogger(__name__)


class GapType(Enum):
    """缺口类型"""
    UP_GAP = "up_gap"          # 向上跳空
    DOWN_GAP = "down_gap"      # 向下跳空
    NO_GAP = "no_gap"          # 无缺口


class GapDirection(Enum):
    """缺口方向相对于趋势"""
    SAME_DIRECTION = "same"     # 顺势缺口
    OPPOSITE_DIRECTION = "opposite"  # 逆势缺口


@dataclass
class Gap:
    """缺口数据结构"""
    gap_type: GapType
    gap_direction: GapDirection
    gap_size_points: float      # 缺口大小（点数）
    gap_size_percent: float     # 缺口大小（百分比）
    start_kline_index: int      # 缺口前K线索引
    end_kline_index: int        # 缺口后K线索引
    start_kline: KLine          # 缺口前K线
    end_kline: KLine            # 缺口后K线
    can_form_bi: bool = False   # 是否可成笔
    filled_after_bars: Optional[int] = None  # 几根K线后回补（None表示未回补）


class GapProcessor:
    """跳空缺口处理器"""
    
    def __init__(self, time_level: TimeLevel = TimeLevel.MIN_30):
        """
        初始化缺口处理器
        
        Args:
            time_level: 时间级别
        """
        self.time_level = time_level
        
        # 根据缠论标准设置缺口成笔阈值
        self.gap_thresholds = self._get_gap_thresholds()
        
    def _get_gap_thresholds(self) -> Dict[str, float]:
        """
        获取缺口成笔的阈值标准
        
        Returns:
            缺口阈值配置
        """
        # 根据缠论标准设置不同级别的缺口成笔阈值
        if self.time_level == TimeLevel.MIN_30:
            return {
                'index_points': 20.0,     # 大盘指数30分钟级别：20点
                'stock_percent': 5.0,     # 个股30分钟级别：5%
                'min_hold_bars': 3        # 至少持续3根K线不回补
            }
        elif self.time_level == TimeLevel.MIN_5:
            return {
                'index_points': 10.0,     # 大盘指数5分钟级别：10点
                'stock_percent': 2.5,     # 个股5分钟级别：2.5%
                'min_hold_bars': 3        # 至少持续3根K线不回补
            }
        else:
            # 日线级别相对要求更高
            return {
                'index_points': 50.0,     # 大盘指数日线级别：50点
                'stock_percent': 8.0,     # 个股日线级别：8%
                'min_hold_bars': 2        # 至少持续2根K线不回补
            }
    
    def identify_gaps(self, klines: KLineList, is_index: bool = False) -> List[Gap]:
        """
        识别K线序列中的所有缺口
        
        Args:
            klines: K线序列
            is_index: 是否为指数（影响成笔阈值判断）
            
        Returns:
            缺口列表
        """
        if len(klines) < 2:
            return []
        
        gaps = []
        
        for i in range(1, len(klines)):
            prev_kline = klines[i-1]
            curr_kline = klines[i]
            
            gap = self._analyze_gap(prev_kline, curr_kline, i-1, i)
            if gap.gap_type != GapType.NO_GAP:
                # 判断是否满足成笔条件
                gap.can_form_bi = self._can_gap_form_bi(gap, klines, is_index)
                
                # 检查缺口是否被回补
                gap.filled_after_bars = self._check_gap_filled(gap, klines, i)
                
                gaps.append(gap)
        
        return gaps
    
    def _analyze_gap(self, prev_kline: KLine, curr_kline: KLine, 
                    prev_index: int, curr_index: int) -> Gap:
        """
        分析两根K线间的缺口
        
        Args:
            prev_kline: 前一根K线
            curr_kline: 当前K线
            prev_index: 前一根K线索引
            curr_index: 当前K线索引
            
        Returns:
            缺口信息
        """
        gap_type = GapType.NO_GAP
        gap_size_points = 0.0
        gap_size_percent = 0.0
        
        # 检查向上跳空：当前K线最低价 > 前一根K线最高价
        if curr_kline.low > prev_kline.high:
            gap_type = GapType.UP_GAP
            gap_size_points = curr_kline.low - prev_kline.high
            gap_size_percent = gap_size_points / prev_kline.high * 100
        
        # 检查向下跳空：当前K线最高价 < 前一根K线最低价
        elif curr_kline.high < prev_kline.low:
            gap_type = GapType.DOWN_GAP
            gap_size_points = prev_kline.low - curr_kline.high
            gap_size_percent = gap_size_points / prev_kline.low * 100
        
        return Gap(
            gap_type=gap_type,
            gap_direction=GapDirection.SAME_DIRECTION,  # 暂时设为顺势，需要结合趋势判断
            gap_size_points=gap_size_points,
            gap_size_percent=gap_size_percent,
            start_kline_index=prev_index,
            end_kline_index=curr_index,
            start_kline=prev_kline,
            end_kline=curr_kline
        )
    
    def _can_gap_form_bi(self, gap: Gap, klines: KLineList, is_index: bool) -> bool:
        """
        判断缺口是否可以成笔
        
        Args:
            gap: 缺口信息
            klines: K线序列
            is_index: 是否为指数
            
        Returns:
            是否可成笔
        """
        thresholds = self.gap_thresholds
        
        # 根据是否为指数选择不同的阈值标准
        if is_index:
            # 指数用点数标准
            size_threshold = thresholds['index_points']
            meets_size = gap.gap_size_points >= size_threshold
        else:
            # 个股用百分比标准
            size_threshold = thresholds['stock_percent']
            meets_size = gap.gap_size_percent >= size_threshold
        
        # 检查是否为反向缺口（逆势缺口更容易成笔）
        # 这里需要结合前期趋势判断，暂时简化处理
        is_significant = meets_size
        
        # 检查持续性：缺口后是否持续一定K线数不回补
        min_hold_bars = thresholds['min_hold_bars']
        can_hold = self._check_gap_persistence(gap, klines, min_hold_bars)
        
        result = is_significant and can_hold
        
        if result:
            logger.info(f"检测到可成笔缺口: {gap.gap_type.value}, "
                       f"大小: {gap.gap_size_percent:.2f}% ({gap.gap_size_points:.2f}点), "
                       f"阈值: {'点数' if is_index else '百分比'} >= {size_threshold}")
        
        return result
    
    def _check_gap_persistence(self, gap: Gap, klines: KLineList, min_bars: int) -> bool:
        """
        检查缺口的持续性（是否在指定K线数内未被回补）
        
        Args:
            gap: 缺口信息
            klines: K线序列
            min_bars: 最小持续K线数
            
        Returns:
            是否满足持续性要求
        """
        start_idx = gap.end_kline_index
        end_idx = min(start_idx + min_bars, len(klines))
        
        # 检查后续K线是否回补缺口
        for i in range(start_idx, end_idx):
            kline = klines[i]
            
            if gap.gap_type == GapType.UP_GAP:
                # 向上缺口：如果低点跌破缺口前的高点，则缺口被回补
                if kline.low <= gap.start_kline.high:
                    return False
            elif gap.gap_type == GapType.DOWN_GAP:
                # 向下缺口：如果高点突破缺口前的低点，则缺口被回补
                if kline.high >= gap.start_kline.low:
                    return False
        
        return True
    
    def _check_gap_filled(self, gap: Gap, klines: KLineList, start_idx: int) -> Optional[int]:
        """
        检查缺口是否被回补，并返回回补时的K线数
        
        Args:
            gap: 缺口信息
            klines: K线序列
            start_idx: 检查起始索引
            
        Returns:
            回补时的K线数，None表示未回补
        """
        for i in range(start_idx, len(klines)):
            kline = klines[i]
            
            if gap.gap_type == GapType.UP_GAP:
                if kline.low <= gap.start_kline.high:
                    return i - start_idx + 1
            elif gap.gap_type == GapType.DOWN_GAP:
                if kline.high >= gap.start_kline.low:
                    return i - start_idx + 1
        
        return None
    
    def create_gap_bi_fenxings(self, gaps: List[Gap], klines: KLineList) -> List[FenXing]:
        """
        基于可成笔的缺口创建分型
        
        Args:
            gaps: 缺口列表
            klines: K线序列
            
        Returns:
            缺口成笔产生的分型列表
        """
        gap_fenxings = []
        
        for gap in gaps:
            if not gap.can_form_bi:
                continue
            
            # 根据缺口类型创建对应的分型
            if gap.gap_type == GapType.UP_GAP:
                # 向上跳空在缺口前创建底分型
                fenxing = self._create_fenxing_from_gap(gap, is_bottom=True, klines=klines)
            elif gap.gap_type == GapType.DOWN_GAP:
                # 向下跳空在缺口前创建顶分型
                fenxing = self._create_fenxing_from_gap(gap, is_bottom=False, klines=klines)
            else:
                continue
            
            if fenxing:
                gap_fenxings.append(fenxing)
        
        return gap_fenxings
    
    def _create_fenxing_from_gap(self, gap: Gap, is_bottom: bool, klines: KLineList) -> Optional[FenXing]:
        """
        从缺口创建分型
        
        Args:
            gap: 缺口信息
            is_bottom: 是否为底分型
            klines: K线序列
            
        Returns:
            创建的分型
        """
        try:
            from models.fenxing import FenXing
            from models.enums import FenXingType
            
            # 使用缺口前的K线作为分型的核心K线
            core_kline = gap.start_kline
            
            fenxing = FenXing(
                kline=core_kline,
                fenxing_type=FenXingType.BOTTOM if is_bottom else FenXingType.TOP,
                index=gap.start_kline_index,
                strength=0.8,  # 缺口成笔的分型强度较高
                confidence=0.9,  # 缺口成笔的置信度较高
                is_confirmed=True,  # 缺口形成即确认
                confirm_kline_count=1  # 缺口形成即确认
            )
            
            return fenxing
        except Exception as e:
            logger.error(f"从缺口创建分型失败: {e}")
            return None
    
    def get_gap_statistics(self, gaps: List[Gap]) -> Dict[str, Any]:
        """
        获取缺口统计信息
        
        Args:
            gaps: 缺口列表
            
        Returns:
            统计信息
        """
        if not gaps:
            return {}
        
        up_gaps = [g for g in gaps if g.gap_type == GapType.UP_GAP]
        down_gaps = [g for g in gaps if g.gap_type == GapType.DOWN_GAP]
        can_form_bi_gaps = [g for g in gaps if g.can_form_bi]
        
        return {
            'total_gaps': len(gaps),
            'up_gaps': len(up_gaps),
            'down_gaps': len(down_gaps),
            'can_form_bi_gaps': len(can_form_bi_gaps),
            'avg_gap_size_percent': sum(g.gap_size_percent for g in gaps) / len(gaps),
            'max_gap_size_percent': max(g.gap_size_percent for g in gaps),
            'bi_formation_rate': len(can_form_bi_gaps) / len(gaps) if gaps else 0
        }


# 便捷函数
def analyze_gaps_in_klines(klines: KLineList, time_level: TimeLevel = TimeLevel.MIN_30, 
                          is_index: bool = False) -> Tuple[List[Gap], Dict[str, Any]]:
    """
    分析K线序列中的缺口
    
    Args:
        klines: K线序列
        time_level: 时间级别
        is_index: 是否为指数
        
    Returns:
        (缺口列表, 统计信息)
    """
    processor = GapProcessor(time_level)
    gaps = processor.identify_gaps(klines, is_index)
    stats = processor.get_gap_statistics(gaps)
    
    return gaps, stats


if __name__ == "__main__":
    # 简单测试
    logging.basicConfig(level=logging.INFO)
    print("缠论跳空缺口处理器测试模块")