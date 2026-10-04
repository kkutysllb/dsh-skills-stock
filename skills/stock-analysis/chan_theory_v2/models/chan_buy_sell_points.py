#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论多级别买卖点识别器
基于Vespa314/chan.py最佳实践的独立实现
支持5分钟、30分钟、日线的递归关系和区间套策略
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import logging

from .enums import TimeLevel, BiDirection, SegDirection
from .kline import KLine, KLineList
from .bi import Bi, BiList
from .seg import Seg, SegList
from .zhongshu import ZhongShu, ZhongShuList
from .dynamics import BuySellPoint, BuySellPointType, BackChi

logger = logging.getLogger(__name__)


class BSPLevel(Enum):
    """买卖点级别"""
    LEVEL_1 = "1"  # 一类买卖点
    LEVEL_2 = "2"  # 二类买卖点  
    LEVEL_3 = "3"  # 三类买卖点


@dataclass
class MultiLevelContext:
    """多级别分析上下文"""
    time_level: TimeLevel
    klines: KLineList
    bis: BiList
    segs: SegList
    zhongshus: ZhongShuList
    
    # 级别关系
    higher_level: Optional['MultiLevelContext'] = None
    lower_level: Optional['MultiLevelContext'] = None


class ChanBuySellPointAnalyzer:
    """
    缠论买卖点分析器
    基于Vespa314/chan.py的多级别联立思想
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 级别优先级映射 - 使用字符串值确保兼容性
        self.level_priority = {
            TimeLevel.DAILY: 3,
            TimeLevel.MIN_30: 2,
            TimeLevel.MIN_5: 1
        }
        # 添加字符串值映射作为备选
        self.level_priority_str = {
            "daily": 3,
            "30min": 2,
            "5min": 1
        }
    
    def analyze_multi_level_bsp(self, 
                               contexts: Dict[TimeLevel, MultiLevelContext]) -> Dict[TimeLevel, List[BuySellPoint]]:
        """
        多级别买卖点分析
        
        Args:
            contexts: 各级别的分析上下文
            
        Returns:
            各级别的买卖点列表
        """
        if not contexts:
            return {}
            
        self.logger.info(f"🔍 开始多级别买卖点分析，级别数量: {len(contexts)}")
        
        # 按级别从大到小排序
        sorted_levels = sorted(contexts.keys(), 
                             key=lambda x: self.level_priority.get(x, 0), 
                             reverse=True)
        
        # 建立级别关系
        self._build_level_relationships(contexts, sorted_levels)
        
        # 分析各级别买卖点
        all_bsp = {}
        for level in sorted_levels:
            context = contexts[level]
            bsp_list = self._analyze_single_level_bsp(context)
            all_bsp[level] = bsp_list
            level_label = level.value if hasattr(level, 'value') else str(level)
            self.logger.info(f"✅ {level_label}级别: 识别买卖点 {len(bsp_list)} 个")
        
        # 仅在多级别情况下应用多级别确认
        if len(contexts) > 1:
            self._apply_multi_level_confirmation(all_bsp, contexts)
        else:
            self.logger.info("单级别分析，跳过多级别确认")
        
        return all_bsp
    
    def _build_level_relationships(self, 
                                 contexts: Dict[TimeLevel, MultiLevelContext],
                                 sorted_levels: List[TimeLevel]) -> None:
        """建立级别间关系"""
        for i, level in enumerate(sorted_levels):
            context = contexts[level]
            
            # 设置高级别关系
            if i > 0:
                context.higher_level = contexts[sorted_levels[i-1]]
                
            # 设置低级别关系
            if i < len(sorted_levels) - 1:
                context.lower_level = contexts[sorted_levels[i+1]]
    
    def _analyze_single_level_bsp(self, context: MultiLevelContext) -> List[BuySellPoint]:
        """分析单个级别的买卖点"""
        bsp_list = []
        
        # 1. 第一类买卖点：趋势背驰点
        first_class_bsp = self._identify_first_class_bsp(context)
        bsp_list.extend(first_class_bsp)
        
        # 2. 第二类买卖点：回抽确认点
        second_class_bsp = self._identify_second_class_bsp(context, first_class_bsp)
        bsp_list.extend(second_class_bsp)
        
        # 3. 第三类买卖点：类三买
        third_class_bsp = self._identify_third_class_bsp(context)
        bsp_list.extend(third_class_bsp)
        
        # 按时间排序
        bsp_list.sort(key=lambda x: x.timestamp)
        
        return bsp_list
    
    def _identify_first_class_bsp(self, context: MultiLevelContext) -> List[BuySellPoint]:
        """识别第一类买卖点：趋势背驰转折点"""
        bsp_list = []
        
        if len(context.segs) < 3:
            return bsp_list
            
        # 寻找趋势背驰
        for i in range(1, len(context.segs)):
            current_seg = context.segs[i]
            
            # 寻找最近的同向线段进行比较
            prev_seg = None
            for j in range(i-1, -1, -1):
                if context.segs[j].direction == current_seg.direction:
                    prev_seg = context.segs[j]
                    break
            
            # 如果找不到同向线段，跳过
            if prev_seg is None:
                continue
                
            # 检查两个同向线段之间是否存在中枢
            # 找到prev_seg在列表中的位置
            prev_seg_index = None
            for k, seg in enumerate(context.segs):
                if seg is prev_seg:
                    prev_seg_index = k
                    break
            
            if prev_seg_index is None:
                continue
                
            # 检查两个同向线段之间的线段是否构成中枢
            between_segs = context.segs[prev_seg_index+1:i]
            has_zhongshu = any(self._seg_creates_zhongshu(seg, context.zhongshus) 
                             for seg in between_segs) if between_segs else False
            
            if not has_zhongshu:
                continue
                
            # 背驰判断：后段力度小于前段
            if self._is_divergence(prev_seg, current_seg):
                point_type = (BuySellPointType.BUY_1 if current_seg.direction == SegDirection.DOWN 
                            else BuySellPointType.SELL_1)
                
                # 寻找对应K线
                kline_index = self._find_kline_by_time(context.klines, current_seg.end_time)
                
                if kline_index >= 0:
                    bsp = BuySellPoint(
                        point_type=point_type,
                        timestamp=current_seg.end_time,
                        price=current_seg.end_price,
                        kline_index=kline_index,
                        related_seg=current_seg,
                        strength=self._calculate_bsp_strength(current_seg, prev_seg),
                        reliability=0.8,  # 一类买点可靠度高
                        backchi_type=BackChi.BOTTOM_BACKCHI if point_type.is_buy() else BackChi.TOP_BACKCHI
                    )
                    bsp_list.append(bsp)
                    self.logger.debug(f"识别到{point_type}: {current_seg.end_price:.2f}@{current_seg.end_time}")
        
        return bsp_list
    
    def _identify_second_class_bsp(self, 
                                 context: MultiLevelContext, 
                                 first_class_bsp: List[BuySellPoint]) -> List[BuySellPoint]:
        """识别第二类买卖点：回抽确认点"""
        bsp_list = []
        
        for first_bsp in first_class_bsp:
            # 寻找第一类买点之后的回抽
            later_segs = [seg for seg in context.segs 
                         if seg.start_time > first_bsp.timestamp]
            
            if len(later_segs) >= 2:
                # 第一段：离开
                leave_seg = later_segs[0]
                # 第二段：回抽
                pullback_seg = later_segs[1]
                
                # 验证回抽有效性
                if self._is_valid_pullback(first_bsp, pullback_seg):
                    point_type = (BuySellPointType.BUY_2 if first_bsp.point_type.is_buy() 
                                else BuySellPointType.SELL_2)
                    
                    kline_index = self._find_kline_by_time(context.klines, pullback_seg.end_time)
                    
                    if kline_index >= 0:
                        bsp = BuySellPoint(
                            point_type=point_type,
                            timestamp=pullback_seg.end_time,
                            price=pullback_seg.end_price,
                            kline_index=kline_index,
                            related_seg=pullback_seg,
                            strength=pullback_seg.strength,
                            reliability=0.7  # 二类买点可靠度中等
                        )
                        bsp_list.append(bsp)
        
        return bsp_list
    
    def _identify_third_class_bsp(self, context: MultiLevelContext) -> List[BuySellPoint]:
        """识别第三类买卖点：类三买"""
        bsp_list = []
        
        if len(context.zhongshus) == 0:
            return bsp_list
            
        for zhongshu in context.zhongshus:
            # 寻找离开中枢的线段
            leaving_segs = [seg for seg in context.segs 
                          if (seg.start_time >= zhongshu.end_time and
                              ((seg.direction == SegDirection.UP and seg.end_price > zhongshu.high) or
                               (seg.direction == SegDirection.DOWN and seg.end_price < zhongshu.low)))]
            
            for leave_seg in leaving_segs:
                # 寻找回试线段
                test_segs = [seg for seg in context.segs 
                           if seg.start_time > leave_seg.end_time]
                
                if test_segs:
                    test_seg = test_segs[0]
                    
                    # 验证三类买点条件
                    if self._is_valid_third_class(zhongshu, leave_seg, test_seg):
                        point_type = (BuySellPointType.BUY_3 if leave_seg.direction == SegDirection.UP 
                                    else BuySellPointType.SELL_3)
                        
                        kline_index = self._find_kline_by_time(context.klines, test_seg.end_time)
                        
                        if kline_index >= 0:
                            bsp = BuySellPoint(
                                point_type=point_type,
                                timestamp=test_seg.end_time,
                                price=test_seg.end_price,
                                kline_index=kline_index,
                                related_zhongshu=zhongshu,
                                related_seg=test_seg,
                                strength=test_seg.strength,
                                reliability=0.9  # 三类买点可靠度最高
                            )
                            bsp_list.append(bsp)
        
        return bsp_list
    
    def _apply_multi_level_confirmation(self, 
                                      all_bsp: Dict[TimeLevel, List[BuySellPoint]],
                                      contexts: Dict[TimeLevel, MultiLevelContext]) -> None:
        """应用多级别确认机制（区间套策略）"""
        
        # 时间窗口设置
        time_windows = {
            (TimeLevel.DAILY, TimeLevel.MIN_30): 3 * 24 * 3600,    # 3天
            (TimeLevel.MIN_30, TimeLevel.MIN_5): 2 * 3600,         # 2小时
            (TimeLevel.DAILY, TimeLevel.MIN_5): 5 * 24 * 3600      # 5天
        }
        
        for higher_level, higher_bsp_list in all_bsp.items():
            for lower_level, lower_bsp_list in all_bsp.items():
                # 安全获取级别优先级，支持枚举和字符串值
                higher_priority = self.level_priority.get(higher_level) or self.level_priority_str.get(getattr(higher_level, 'value', str(higher_level)), 0)
                lower_priority = self.level_priority.get(lower_level) or self.level_priority_str.get(getattr(lower_level, 'value', str(lower_level)), 0)
                
                if higher_priority <= lower_priority:
                    continue
                    
                time_window = time_windows.get((higher_level, lower_level), 24 * 3600)
                
                # 高级别确认低级别
                for lower_bsp in lower_bsp_list:
                    for higher_bsp in higher_bsp_list:
                        time_diff = abs((lower_bsp.timestamp - higher_bsp.timestamp).total_seconds())
                        same_direction = (lower_bsp.point_type.is_buy() == higher_bsp.point_type.is_buy())
                        
                        if time_diff <= time_window and same_direction:
                            lower_bsp.confirmed_by_higher_level = True
                            lower_bsp.reliability = min(lower_bsp.reliability + 0.2, 1.0)
                            
                # 低级别确认高级别
                for higher_bsp in higher_bsp_list:
                    for lower_bsp in lower_bsp_list:
                        time_diff = abs((higher_bsp.timestamp - lower_bsp.timestamp).total_seconds())
                        same_direction = (higher_bsp.point_type.is_buy() == lower_bsp.point_type.is_buy())
                        
                        if time_diff <= time_window and same_direction:
                            higher_bsp.confirmed_by_lower_level = True
                            higher_bsp.reliability = min(higher_bsp.reliability + 0.1, 1.0)
    
    # 辅助方法
    def _seg_creates_zhongshu(self, seg: Seg, zhongshus: ZhongShuList) -> bool:
        """判断线段是否参与构成中枢"""
        for zs in zhongshus:
            if seg.start_time <= zs.end_time and seg.end_time >= zs.start_time:
                return True
        return False
    
    def _is_divergence(self, prev_seg: Seg, current_seg: Seg) -> bool:
        """判断是否存在背驰"""
        # 背驰判断：后段力度小于前段，使用相对宽松的阈值
        # 0.8表示后段力度至少要比前段小20%才认为是背驰
        return current_seg.strength < prev_seg.strength * 0.8
    
    def _calculate_bsp_strength(self, current_seg: Seg, prev_seg: Seg) -> float:
        """计算买卖点强度"""
        if prev_seg.strength == 0:
            return 0.5
        return min(1.0 - (current_seg.strength / prev_seg.strength), 1.0)
    
    def _is_valid_pullback(self, first_bsp: BuySellPoint, pullback_seg: Seg) -> bool:
        """验证回抽是否有效"""
        if first_bsp.point_type.is_buy():
            # 买点：回抽不破第一类买点
            return pullback_seg.end_price > first_bsp.price * 0.95  # 允许5%误差
        else:
            # 卖点：回抽不破第一类卖点
            return pullback_seg.end_price < first_bsp.price * 1.05  # 允许5%误差
    
    def _is_valid_third_class(self, zhongshu: ZhongShu, leave_seg: Seg, test_seg: Seg) -> bool:
        """验证三类买点条件"""
        if leave_seg.direction == SegDirection.UP:
            # 向上离开后回试不破中枢上沿
            return test_seg.end_price > zhongshu.high * 0.98  # 允许2%误差
        else:
            # 向下离开后回试不破中枢下沿
            return test_seg.end_price < zhongshu.low * 1.02   # 允许2%误差
    
    def _find_kline_by_time(self, klines: KLineList, timestamp: datetime) -> int:
        """根据时间找到对应的K线索引"""
        for i, kline in enumerate(klines):
            if kline.timestamp >= timestamp:
                return i
        return len(klines) - 1