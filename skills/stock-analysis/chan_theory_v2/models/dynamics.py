#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论动力学分析模块
实现缠论的动力学原理：背驰分析、MACD辅助判断、一二三类买卖点识别

基于缠中说禅《教你炒股票》系列理论和网络最佳实践
核心功能：
1. MACD背驰分析
2. 一二三类买卖点识别  
3. 多级别动力学关系判定
4. 走势力度计算和比较
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import numpy as np
from abc import ABC, abstractmethod

from .enums import TimeLevel, BiDirection, SegDirection, ZhongShuType
from .kline import KLine, KLineList
from .bi import Bi, BiList
from .seg import Seg, SegList  
from .zhongshu import ZhongShu, ZhongShuList


class BackChi(Enum):
    """背驰类型枚举"""
    NONE = "none"              # 无背驰
    TOP_BACKCHI = "top"        # 顶背驰
    BOTTOM_BACKCHI = "bottom"  # 底背驰
    
    def is_backchi(self) -> bool:
        return self != self.NONE
    
    def __str__(self) -> str:
        names = {
            self.NONE: "无背驰",
            self.TOP_BACKCHI: "顶背驰", 
            self.BOTTOM_BACKCHI: "底背驰"
        }
        return names.get(self, self.value)


class BuySellPointType(Enum):
    """买卖点类型枚举"""
    # 买点
    BUY_1 = "1buy"    # 一类买点：跌势转向上涨或盘整的起点
    BUY_2 = "2buy"    # 二类买点：第一类买点后首次次级别回调低点  
    BUY_3 = "3buy"    # 三类买点：次级别走势向上离开中枢后，回试不穿越中枢高点
    
    # 卖点
    SELL_1 = "1sell"  # 一类卖点：涨势转向下跌或盘整的起点
    SELL_2 = "2sell"  # 二类卖点：第一类卖点后首次次级别回调高点
    SELL_3 = "3sell"  # 三类卖点：次级别走势向下离开中枢后，回试不穿越中枢低点
    
    def is_buy(self) -> bool:
        return self in [self.BUY_1, self.BUY_2, self.BUY_3]
    
    def is_sell(self) -> bool:
        return self in [self.SELL_1, self.SELL_2, self.SELL_3]
    
    def get_level(self) -> int:
        return int(self.value[0])
    
    def __str__(self) -> str:
        names = {
            self.BUY_1: "一类买点", self.BUY_2: "二类买点", self.BUY_3: "三类买点",
            self.SELL_1: "一类卖点", self.SELL_2: "二类卖点", self.SELL_3: "三类卖点"
        }
        return names.get(self, self.value)


@dataclass
class MacdData:
    """MACD指标数据"""
    dif: float          # DIF线 (12日EMA - 26日EMA)
    dea: float          # DEA线 (DIF的9日EMA)  
    macd: float         # MACD柱 (DIF - DEA) * 2
    timestamp: datetime
    
    @property
    def is_above_zero(self) -> bool:
        """MACD是否在0轴上方"""
        return self.dif > 0 and self.dea > 0
    
    @property
    def is_golden_cross(self) -> bool:
        """是否为金叉(DIF上穿DEA)"""
        return self.dif > self.dea and self.macd > 0
    
    @property
    def is_death_cross(self) -> bool:
        """是否为死叉(DIF下穿DEA)"""
        return self.dif < self.dea and self.macd < 0


@dataclass
class BuySellPoint:
    """买卖点数据结构"""
    point_type: BuySellPointType
    timestamp: datetime
    price: float
    kline_index: int
    
    # 相关结构信息
    related_zhongshu: Optional[ZhongShu] = None
    related_seg: Optional[Seg] = None
    related_bi: Optional[Bi] = None
    
    # 动力学信息
    macd_data: Optional[MacdData] = None
    backchi_type: BackChi = BackChi.NONE
    strength: float = 0.0           # 买卖点强度
    reliability: float = 0.0        # 可靠度
    
    # 多级别确认
    confirmed_by_higher_level: bool = False
    confirmed_by_lower_level: bool = False
    
    def __str__(self) -> str:
        return f"{self.point_type} @{self.price:.2f} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"


@dataclass  
class BackChiAnalysis:
    """背驰分析结果"""
    backchi_type: BackChi
    current_seg: Seg
    previous_seg: Seg
    zhongshu: ZhongShu
    
    # MACD分析数据
    current_macd_area: float        # 当前段MACD面积
    previous_macd_area: float       # 前一段MACD面积
    macd_divergence: float          # MACD背离度
    
    # 力度分析
    current_strength: float         # 当前段力度
    previous_strength: float        # 前一段力度
    strength_ratio: float           # 力度比值
    
    reliability: float = 0.0        # 背驰可靠度
    
    def is_valid_backchi(self) -> bool:
        """是否为有效背驰"""
        return (self.backchi_type.is_backchi() and 
                self.reliability > 0.6 and
                abs(self.strength_ratio - 1.0) > 0.1)
    
    @property
    def is_buy_signal(self) -> bool:
        """是否为买入信号（底背驰）"""
        return self.backchi_type == BackChi.BOTTOM_BACKCHI
    
    @property 
    def is_sell_signal(self) -> bool:
        """是否为卖出信号（顶背驰）"""
        return self.backchi_type == BackChi.TOP_BACKCHI


class MacdCalculator:
    """MACD计算器"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def calculate(self, prices: List[float]) -> List[MacdData]:
        """计算MACD指标"""
        if len(prices) < self.slow_period + self.signal_period:
            return []
        
        # 计算EMA
        fast_ema = self._calculate_ema(prices, self.fast_period)
        slow_ema = self._calculate_ema(prices, self.slow_period)
        
        # 计算DIF
        dif_values = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]
        
        # 计算DEA
        dea_values = self._calculate_ema(dif_values, self.signal_period)
        
        # 计算MACD
        macd_values = [(dif - dea) * 2 for dif, dea in zip(dif_values, dea_values)]
        
        # 构造结果
        result = []
        start_idx = max(self.slow_period, self.signal_period) - 1
        for i in range(start_idx, len(prices)):
            result.append(MacdData(
                dif=dif_values[i],
                dea=dea_values[i], 
                macd=macd_values[i],
                timestamp=datetime.now()  # 实际使用时需要传入对应时间
            ))
        
        return result
    
    def _calculate_ema(self, values: List[float], period: int) -> List[float]:
        """计算指数移动平均"""
        if len(values) < period:
            return []
        
        multiplier = 2.0 / (period + 1)
        ema = [sum(values[:period]) / period]  # 初始值使用简单平均
        
        for i in range(period, len(values)):
            ema.append((values[i] * multiplier) + (ema[-1] * (1 - multiplier)))
        
        # 补充前面的值
        result = [0.0] * (period - 1) + ema
        return result


class DynamicsAnalyzer:
    """动力学分析器 - 基于简化MACD背驰算法的核心类"""
    
    def __init__(self, config=None):
        self.macd_calculator = MacdCalculator()
        # 使用SimpleBackchiAnalyzer的统一配置，确保完全一致
        from .simple_backchi import SimpleBackchiAnalyzer
        self.config = SimpleBackchiAnalyzer.get_default_config()
        # 添加DynamicsAnalyzer特有的配置
        self.config.update({
            'min_reliability': 0.3,          # 最小可靠度 (与选股器的min_backchi_strength一致)
        })
        if config:
            self.config.update(config)
    
    def analyze_simple_backchi(self, klines: KLineList) -> List[BackChiAnalysis]:
        """
        简化背驰分析：基于MACD红绿柱面积对比
        不依赖线段和中枢，直接分析MACD信号
        """
        if len(klines) < 20:
            return []
        
        # 计算MACD数据
        close_prices = [kline.close for kline in klines]
        macd_data = self.macd_calculator.calculate(close_prices)
        
        if len(macd_data) < 20:
            return []
        
        # 使用简化背驰分析器，传递正确的配置
        from .simple_backchi import SimpleBackchiAnalyzer
        analyzer = SimpleBackchiAnalyzer(self.config)
        backchi_type, reliability, description = analyzer.analyze_backchi(klines, macd_data)
        
        backchi_results = []
        
        if backchi_type and reliability >= self.config['min_reliability']:
            # 创建简化的背驰分析结果
            latest_kline = klines[-1]
            
            backchi = BackChiAnalysis(
                backchi_type=BackChi.BOTTOM_BACKCHI if backchi_type == "bottom" else BackChi.TOP_BACKCHI,
                current_seg=None,      # 简化算法不使用线段
                previous_seg=None,     # 简化算法不使用线段
                zhongshu=None,         # 简化算法不使用中枢
                current_macd_area=0.0, # 实际值由analyzer计算
                previous_macd_area=0.0,# 实际值由analyzer计算
                macd_divergence=0.0,   # 简化版本不计算
                current_strength=reliability,
                previous_strength=0.0,
                strength_ratio=reliability,
                reliability=reliability
            )
            backchi_results.append(backchi)
        
        return backchi_results
    
    def get_latest_signals(self, klines: KLineList, timeframe: str = "30min") -> List[Dict[str, Any]]:
        """获取最新的买卖信号"""
        backchi_results = self.analyze_simple_backchi(klines)
        
        signals = []
        for backchi in backchi_results:
            if backchi.backchi_type != BackChi.NONE:
                signal = {
                    "type": "买入" if backchi.backchi_type == BackChi.BOTTOM_BACKCHI else "卖出",
                    "timeframe": timeframe,
                    "reliability": backchi.reliability,
                    "strength": backchi.current_strength,
                    "description": f"{'底背驰' if backchi.backchi_type == BackChi.BOTTOM_BACKCHI else '顶背驰'}信号"
                }
                signals.append(signal)
        
        return signals
    
    
    def identify_buy_sell_points(self, klines: KLineList) -> List[BuySellPoint]:
        """识别简化买卖点（用于选股等简化场景）"""
        buy_sell_points = []
        
        # 直接使用简化背驰分析生成买卖点
        backchi_results = self.analyze_simple_backchi(klines)
        
        for backchi in backchi_results:
            if backchi.backchi_type != BackChi.NONE:
                latest_kline = klines[-1]
                
                point_type = (BuySellPointType.BUY_1 if backchi.backchi_type == BackChi.BOTTOM_BACKCHI 
                            else BuySellPointType.SELL_1)
                
                point = BuySellPoint(
                    point_type=point_type,
                    timestamp=latest_kline.timestamp,
                    price=latest_kline.close,
                    kline_index=len(klines) - 1,
                    related_zhongshu=None,     # 简化算法不依赖中枢
                    related_seg=None,          # 简化算法不依赖线段
                    backchi_type=backchi.backchi_type,
                    strength=backchi.current_strength,
                    reliability=backchi.reliability
                )
                buy_sell_points.append(point)
        
        return buy_sell_points
    
    def identify_chan_buy_sell_points(self, 
                                    klines: KLineList,
                                    segs: SegList, 
                                    zhongshus: ZhongShuList,
                                    bis: BiList = None) -> List[BuySellPoint]:
        """
        识别经典缠论买卖点
        基于缠中说禅理论的完整一二三类买卖点识别
        
        Args:
            klines: K线数据
            segs: 线段数据  
            zhongshus: 中枢数据
            bis: 笔数据（可选）
            
        Returns:
            经典缠论买卖点列表
        """
        buy_sell_points = []
        
        if len(segs) < 3 or len(zhongshus) == 0:
            # 没有足够的线段或中枢时，降级使用简化背驰分析
            backchi_results = self.analyze_simple_backchi(klines)
            
            for backchi in backchi_results:
                if backchi.backchi_type != BackChi.NONE:
                    latest_kline = klines[-1]
                    
                    point_type = (BuySellPointType.BUY_1 if backchi.backchi_type == BackChi.BOTTOM_BACKCHI 
                                else BuySellPointType.SELL_1)
                    
                    point = BuySellPoint(
                        point_type=point_type,
                        timestamp=latest_kline.timestamp,
                        price=latest_kline.close,
                        kline_index=len(klines) - 1,
                        related_zhongshu=None,
                        related_seg=None,
                        backchi_type=backchi.backchi_type,
                        strength=backchi.current_strength if hasattr(backchi, 'current_strength') else 0.5,
                        reliability=backchi.reliability if hasattr(backchi, 'reliability') else 0.6
                    )
                    buy_sell_points.append(point)
            
            return buy_sell_points
        
        # 1. 识别第一类买卖点（基于背驰+中枢）
        first_class_points = self._identify_first_class_points(klines, segs, zhongshus)
        buy_sell_points.extend(first_class_points)
        
        # 2. 识别第二类买卖点（第一类买点的次级别回抽确认）
        second_class_points = self._identify_second_class_points(klines, segs, zhongshus, first_class_points)
        buy_sell_points.extend(second_class_points)
        
        # 3. 识别第三类买卖点（中枢突破后回试确认）
        third_class_points = self._identify_third_class_points(klines, segs, zhongshus)
        buy_sell_points.extend(third_class_points)
        
        # 按时间排序
        buy_sell_points.sort(key=lambda x: x.timestamp)
        
        return buy_sell_points
    
    def _identify_first_class_points(self, klines: KLineList, segs: SegList, zhongshus: ZhongShuList) -> List[BuySellPoint]:
        """识别第一类买卖点：背驰+趋势转折"""
        points = []
        
        # 必须有足够的线段构成趋势
        if len(segs) < 5:
            return points
            
        # 寻找趋势段 + 中枢 + 背驰的组合
        for i in range(2, len(zhongshus)):
            zhongshu = zhongshus[i]
            
            # 获取中枢前后的线段
            pre_segs = self._get_segs_before_zhongshu(segs, zhongshu)
            post_segs = self._get_segs_after_zhongshu(segs, zhongshu)
            
            if len(pre_segs) < 2 or len(post_segs) < 1:
                continue
                
            # 检查是否形成趋势
            if self._is_trend_sequence(pre_segs):
                # 检查背驰
                last_trend_seg = post_segs[0] if post_segs else None
                if last_trend_seg and self._check_backchi_with_zhongshu(pre_segs[-1], last_trend_seg, zhongshu):
                    # 创建第一类买卖点
                    point_type = (BuySellPointType.BUY_1 if last_trend_seg.direction == SegDirection.DOWN 
                                else BuySellPointType.SELL_1)
                    
                    # 找到对应的K线
                    seg_end_time = last_trend_seg.end_time
                    kline_index = self._find_kline_index_by_time(klines, seg_end_time)
                    
                    if kline_index >= 0:
                        point = BuySellPoint(
                            point_type=point_type,
                            timestamp=seg_end_time,
                            price=last_trend_seg.end_price,
                            kline_index=kline_index,
                            related_zhongshu=zhongshu,
                            related_seg=last_trend_seg,
                            backchi_type=BackChi.BOTTOM_BACKCHI if point_type.is_buy() else BackChi.TOP_BACKCHI,
                            strength=last_trend_seg.strength,
                            reliability=0.8  # 第一类买点可靠度较高
                        )
                        points.append(point)
        
        return points
    
    def _identify_second_class_points(self, klines: KLineList, segs: SegList, 
                                    zhongshus: ZhongShuList, first_points: List[BuySellPoint]) -> List[BuySellPoint]:
        """识别第二类买卖点：第一类买点的次级别回抽确认"""
        points = []
        
        for first_point in first_points:
            if not first_point.related_seg:
                continue
                
            # 寻找第一类买点后的回抽
            later_segs = self._get_segs_after_time(segs, first_point.timestamp)
            
            if len(later_segs) >= 2:
                # 第一段：离开第一类买点
                # 第二段：回抽测试
                test_seg = later_segs[1] if len(later_segs) > 1 else None
                
                if test_seg and self._is_valid_second_class_test(first_point, test_seg):
                    point_type = (BuySellPointType.BUY_2 if first_point.point_type.is_buy() 
                                else BuySellPointType.SELL_2)
                    
                    kline_index = self._find_kline_index_by_time(klines, test_seg.end_time)
                    
                    if kline_index >= 0:
                        point = BuySellPoint(
                            point_type=point_type,
                            timestamp=test_seg.end_time,
                            price=test_seg.end_price,
                            kline_index=kline_index,
                            related_zhongshu=first_point.related_zhongshu,
                            related_seg=test_seg,
                            strength=test_seg.strength,
                            reliability=0.7  # 第二类买点可靠度中等
                        )
                        points.append(point)
        
        return points
    
    def _identify_third_class_points(self, klines: KLineList, segs: SegList, zhongshus: ZhongShuList) -> List[BuySellPoint]:
        """识别第三类买卖点：次级别离开中枢后回试不破"""
        points = []
        
        for zhongshu in zhongshus:
            if not zhongshu.is_finished:
                continue
                
            # 获取离开中枢的线段
            leaving_segs = self._get_segs_leaving_zhongshu(segs, zhongshu)
            
            for leaving_seg in leaving_segs:
                # 寻找回试线段
                later_segs = self._get_segs_after_time(segs, leaving_seg.end_time)
                
                if len(later_segs) >= 1:
                    test_seg = later_segs[0]
                    
                    # 检查是否为有效的第三类买卖点
                    if self._is_valid_third_class_test(zhongshu, leaving_seg, test_seg):
                        point_type = (BuySellPointType.BUY_3 if leaving_seg.direction == SegDirection.UP 
                                    else BuySellPointType.SELL_3)
                        
                        kline_index = self._find_kline_index_by_time(klines, test_seg.end_time)
                        
                        if kline_index >= 0:
                            point = BuySellPoint(
                                point_type=point_type,
                                timestamp=test_seg.end_time,
                                price=test_seg.end_price,
                                kline_index=kline_index,
                                related_zhongshu=zhongshu,
                                related_seg=test_seg,
                                strength=test_seg.strength,
                                reliability=0.9  # 第三类买点可靠度最高
                            )
                            points.append(point)
        
        return points
    
    def _get_segs_before_zhongshu(self, segs: SegList, zhongshu: ZhongShu) -> List[Seg]:
        """获取中枢前的线段"""
        return [seg for seg in segs if seg.end_time <= zhongshu.start_time]
    
    def _get_segs_after_zhongshu(self, segs: SegList, zhongshu: ZhongShu) -> List[Seg]:
        """获取中枢后的线段"""
        return [seg for seg in segs if seg.start_time >= zhongshu.end_time]
    
    def _get_segs_after_time(self, segs: SegList, timestamp) -> List[Seg]:
        """获取指定时间后的线段"""
        return [seg for seg in segs if seg.start_time > timestamp]
    
    def _get_segs_leaving_zhongshu(self, segs: SegList, zhongshu: ZhongShu) -> List[Seg]:
        """获取离开中枢的线段"""
        leaving_segs = []
        for seg in segs:
            if (seg.start_time >= zhongshu.end_time and 
                ((seg.direction == SegDirection.UP and seg.end_price > zhongshu.high) or
                 (seg.direction == SegDirection.DOWN and seg.end_price < zhongshu.low))):
                leaving_segs.append(seg)
        return leaving_segs
    
    def _is_trend_sequence(self, segs: List[Seg]) -> bool:
        """判断线段序列是否构成趋势"""
        if len(segs) < 2:
            return False
        
        # 检查是否有同向的连续线段（趋势特征）
        up_count = sum(1 for seg in segs if seg.direction == SegDirection.UP)
        down_count = sum(1 for seg in segs if seg.direction == SegDirection.DOWN)
        
        # 趋势要求有明显的方向性
        return abs(up_count - down_count) >= 2
    
    def _check_backchi_with_zhongshu(self, prev_seg: Seg, current_seg: Seg, zhongshu: ZhongShu) -> bool:
        """检查基于中枢的背驰"""
        if prev_seg.direction != current_seg.direction:
            return False
            
        # 简化的背驰判断：力度减弱
        return current_seg.strength < prev_seg.strength * 0.8
    
    def _is_valid_second_class_test(self, first_point: BuySellPoint, test_seg: Seg) -> bool:
        """验证第二类买卖点的回抽测试是否有效"""
        if first_point.point_type.is_buy():
            # 买点：回抽不能跌破第一类买点
            return test_seg.end_price > first_point.price
        else:
            # 卖点：回抽不能升破第一类卖点
            return test_seg.end_price < first_point.price
    
    def _is_valid_third_class_test(self, zhongshu: ZhongShu, leaving_seg: Seg, test_seg: Seg) -> bool:
        """验证第三类买卖点的回试是否有效"""
        if leaving_seg.direction == SegDirection.UP:
            # 向上离开后回试不能跌破中枢上沿
            return test_seg.end_price > zhongshu.high
        else:
            # 向下离开后回试不能升破中枢下沿
            return test_seg.end_price < zhongshu.low
    
    def _find_kline_index_by_time(self, klines: KLineList, timestamp) -> int:
        """根据时间戳找到对应的K线索引"""
        for i, kline in enumerate(klines):
            if kline.timestamp >= timestamp:
                return i
        return len(klines) - 1  # 如果没找到，返回最后一个
    


@dataclass
class MultiLevelAnalysis:
    """多级别分析结果"""
    time_level: TimeLevel
    backchi_analyses: List[BackChiAnalysis] 
    buy_sell_points: List[BuySellPoint]
    
    # 级别间关系
    higher_level_confirmation: bool = False
    lower_level_confirmation: bool = False
    level_consistency_score: float = 0.0


class MultiLevelDynamicsAnalyzer:
    """多级别动力学分析器 - 简化版本"""
    
    def __init__(self, config=None):
        self.analyzer = DynamicsAnalyzer(config)
    
    def analyze_multi_level_dynamics(self,
                                   level_data: Dict[TimeLevel, KLineList]
                                   ) -> Dict[TimeLevel, MultiLevelAnalysis]:
        """多级别简化动力学分析"""
        results = {}
        
        # 单独分析各个级别 - 只需要K线数据
        for level, klines in level_data.items():
            backchi_analyses = self.analyzer.analyze_simple_backchi(klines)
            buy_sell_points = self.analyzer.identify_buy_sell_points(klines)
            
            results[level] = MultiLevelAnalysis(
                time_level=level,
                backchi_analyses=backchi_analyses,
                buy_sell_points=buy_sell_points
            )
        
        return results
    
    def get_consensus_signals(self, 
                            results: Dict[TimeLevel, MultiLevelAnalysis]
                            ) -> List[Dict[str, Any]]:
        """获取多级别共振信号"""
        consensus_signals = []
        
        # 寻找多级别共振的买卖点
        for level, analysis in results.items():
            for point in analysis.buy_sell_points:
                # 检查其他级别是否有同向信号
                confirmations = 0
                for other_level, other_analysis in results.items():
                    if other_level == level:
                        continue
                    
                    for other_point in other_analysis.buy_sell_points:
                        if (point.point_type.is_buy() == other_point.point_type.is_buy() and
                            abs((point.timestamp - other_point.timestamp).total_seconds()) < 86400 * 3):  # 3天内
                            confirmations += 1
                            break
                
                if confirmations > 0:  # 至少有一个级别确认
                    signal = {
                        "type": "买入" if point.point_type.is_buy() else "卖出",
                        "primary_timeframe": level.value,
                        "price": point.price,
                        "timestamp": point.timestamp,
                        "reliability": point.reliability,
                        "confirmations": confirmations,
                        "strength": point.strength
                    }
                    consensus_signals.append(signal)
        
        return consensus_signals


# 配置类
@dataclass
class DynamicsConfig:
    """简化动力学分析配置"""
    # MACD参数
    macd_params: Tuple[int, int, int] = (12, 26, 9)
    
    # 简化背驰参数 - 恢复原始阈值设置
    min_area_ratio: float = 1.2           # 绿柱面积比阈值
    max_area_shrink_ratio: float = 0.8    # 红柱面积缩小比例
    confirm_days: int = 3                 # 金叉确认天数
    death_cross_confirm_days: int = 2     # 死叉确认天数
    min_reliability: float = 0.5          # 最小可靠度
    
    # 多级别确认参数
    multi_level_confirmation_window_days: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'macd_params': self.macd_params,
            'min_area_ratio': self.min_area_ratio,
            'max_area_shrink_ratio': self.max_area_shrink_ratio,
            'confirm_days': self.confirm_days,
            'death_cross_confirm_days': self.death_cross_confirm_days,
            'min_reliability': self.min_reliability,
            'multi_level_confirmation_window_days': self.multi_level_confirmation_window_days
        }