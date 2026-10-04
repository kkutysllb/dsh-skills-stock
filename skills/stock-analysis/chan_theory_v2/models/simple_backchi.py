#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的MACD背驰分析算法
基于MACD红绿柱面积对比的实用背驰判断方法
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple
import numpy as np

from .dynamics import MacdCalculator, MacdData, BackChi


@dataclass
class MacdZone:
    """MACD红绿柱区域"""
    start_index: int
    end_index: int
    zone_type: str  # 'red' 或 'green'
    area: float  # 面积（绝对值）
    peak_price: float  # 该区域对应的股价极值（高点或低点）
    peak_index: int  # 极值对应的K线索引


class SimpleBackchiAnalyzer:
    """简化的背驰分析器"""
    
    # 统一的默认配置 - 确保与DynamicsAnalyzer一致
    DEFAULT_CONFIG = {
        'min_area_ratio': 1.1,           # 绿柱面积比阈值
        'max_area_shrink_ratio': 0.9,    # 红柱面积缩小比例
        'confirm_days': 3,               # 金叉确认天数
        'death_cross_confirm_days': 2,   # 死叉确认天数
    }
    
    def __init__(self, config=None):
        self.macd_calculator = MacdCalculator()
        # 使用统一的默认配置
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
    
    @classmethod
    def get_default_config(cls):
        """获取默认配置，供其他类使用以确保一致性"""
        return cls.DEFAULT_CONFIG.copy()
    
    @classmethod
    def validate_config_consistency(cls, other_config: dict, source_name: str = "Unknown") -> bool:
        """验证配置参数的一致性"""
        default_config = cls.get_default_config()
        inconsistent_params = []
        
        for key in default_config:
            if key in other_config and other_config[key] != default_config[key]:
                inconsistent_params.append(f"{key}: {other_config[key]} (expected {default_config[key]})")
        
        if inconsistent_params:
            print(f"⚠️  配置不一致警告 - {source_name}:")
            for param in inconsistent_params:
                print(f"   • {param}")
            return False
        
        return True
    
    def analyze_backchi(self, klines, macd_data: List[MacdData]) -> Tuple[Optional[str], float, str]:
        """
        分析背驰情况
        
        Args:
            klines: K线数据
            macd_data: MACD数据
            
        Returns:
            (背驰类型, 可靠度, 详细描述)
        """
        if len(macd_data) < 20:  # 至少需要20个周期
            return None, 0.0, "数据不足"
        
        # 1. 识别MACD红绿柱区域
        zones = self._identify_macd_zones(macd_data, klines)
        if len(zones) < 2:
            return None, 0.0, "MACD区域不足"
        
        # 2. 检查底背驰（绿柱面积背驰）
        bottom_backchi = self._check_bottom_backchi(zones, macd_data)
        if bottom_backchi:
            return "bottom", bottom_backchi[1], bottom_backchi[2]
        
        # 3. 检查顶背驰（红柱面积背驰）
        top_backchi = self._check_top_backchi(zones, macd_data)
        if top_backchi:
            return "top", top_backchi[1], top_backchi[2]
        
        return None, 0.0, "未发现背驰"
    
    def _identify_macd_zones(self, macd_data: List[MacdData], klines) -> List[MacdZone]:
        """识别MACD红绿柱区域"""
        zones = []
        current_zone_start = None
        current_zone_type = None
        
        for i, macd in enumerate(macd_data):
            # 判断当前是红柱还是绿柱
            if macd.macd > 0:
                zone_type = 'red'
            elif macd.macd < 0:
                zone_type = 'green'
            else:
                continue  # 跳过零值
            
            if current_zone_type != zone_type:
                # 新区域开始，结束上一个区域
                if current_zone_start is not None:
                    zone = self._create_zone(
                        current_zone_start, i-1, current_zone_type, 
                        macd_data[current_zone_start:i], klines[current_zone_start:i]
                    )
                    if zone:
                        zones.append(zone)
                
                current_zone_start = i
                current_zone_type = zone_type
        
        # 处理最后一个区域
        if current_zone_start is not None and current_zone_start < len(macd_data) - 1:
            zone = self._create_zone(
                current_zone_start, len(macd_data)-1, current_zone_type,
                macd_data[current_zone_start:], klines[current_zone_start:]
            )
            if zone:
                zones.append(zone)
        
        return zones
    
    def _create_zone(self, start_idx: int, end_idx: int, zone_type: str, 
                    zone_macd: List[MacdData], zone_klines) -> Optional[MacdZone]:
        """创建MACD区域"""
        if len(zone_macd) < 2:
            return None
        
        # 计算面积（使用绝对值）
        area = sum(abs(macd.macd) for macd in zone_macd)
        
        # 找到该区域对应的价格极值
        if zone_type == 'green':
            # 绿柱区域找最低价
            prices = [kline.low for kline in zone_klines]
            peak_price = min(prices)
            peak_index = start_idx + prices.index(peak_price)
        else:
            # 红柱区域找最高价
            prices = [kline.high for kline in zone_klines]
            peak_price = max(prices)
            peak_index = start_idx + prices.index(peak_price)
        
        return MacdZone(
            start_index=start_idx,
            end_index=end_idx,
            zone_type=zone_type,
            area=area,
            peak_price=peak_price,
            peak_index=peak_index
        )
    
    def _check_bottom_backchi(self, zones: List[MacdZone], macd_data: List[MacdData]) -> Optional[Tuple[str, float, str]]:
        """
        检查底背驰
        条件：
        1. 后一个绿柱面积 > 前一个绿柱面积
        2. 后一个绿柱区域最低价 < 前一个绿柱区域最低价  
        3. MACD形成金叉
        """
        green_zones = [zone for zone in zones if zone.zone_type == 'green']
        
        if len(green_zones) < 2:
            return None
        
        # 取最近的两个绿柱区域
        prev_green = green_zones[-2]
        curr_green = green_zones[-1]
        
        # 条件1：面积背驰（后面更大）
        area_ratio = curr_green.area / prev_green.area if prev_green.area > 0 else 0
        if area_ratio <= self.config['min_area_ratio']:
            return None
        
        # 条件2：价格新低
        if curr_green.peak_price >= prev_green.peak_price:
            return None
        
        # 条件3：检查是否有金叉
        golden_cross = self._check_golden_cross(macd_data, curr_green.end_index)
        if not golden_cross:
            return None
        
        # 计算可靠度
        price_diff_pct = abs(curr_green.peak_price - prev_green.peak_price) / prev_green.peak_price * 100
        reliability = min(0.9, (area_ratio - 1.0) * 0.5 + price_diff_pct * 0.01)
        
        description = f"底背驰: 面积比{area_ratio:.2f}, 价差{price_diff_pct:.1f}%, 有金叉"
        
        return ("bottom", reliability, description)
    
    def _check_top_backchi(self, zones: List[MacdZone], macd_data: List[MacdData]) -> Optional[Tuple[str, float, str]]:
        """
        检查顶背驰
        条件：
        1. 后一个红柱面积 < 前一个红柱面积
        2. 后一个红柱区域最高价 > 前一个红柱区域最高价
        3. MACD形成死叉
        """
        red_zones = [zone for zone in zones if zone.zone_type == 'red']
        
        if len(red_zones) < 2:
            return None
        
        # 取最近的两个红柱区域
        prev_red = red_zones[-2]
        curr_red = red_zones[-1]
        
        # 条件1：面积背驰（后面更小）
        area_ratio = curr_red.area / prev_red.area if prev_red.area > 0 else 1
        if area_ratio >= self.config['max_area_shrink_ratio']:
            return None
        
        # 条件2：价格新高
        if curr_red.peak_price <= prev_red.peak_price:
            return None
        
        # 条件3：检查是否有死叉
        death_cross = self._check_death_cross(macd_data, curr_red.end_index)
        if not death_cross:
            return None
        
        # 计算可靠度
        price_diff_pct = abs(curr_red.peak_price - prev_red.peak_price) / prev_red.peak_price * 100
        reliability = min(0.9, (1.0 - area_ratio) * 0.5 + price_diff_pct * 0.01)
        
        description = f"顶背驰: 面积比{area_ratio:.2f}, 价差{price_diff_pct:.1f}%, 有死叉"
        
        return ("top", reliability, description)
    
    def _check_golden_cross(self, macd_data: List[MacdData], start_index: int) -> bool:
        """检查金叉（从指定位置开始往后检查几个周期）"""
        check_range = min(5, len(macd_data) - start_index)
        if check_range < 2:
            return False
        
        for i in range(start_index, start_index + check_range - 1):
            prev_macd = macd_data[i]
            curr_macd = macd_data[i + 1]
            
            # DIF上穿DEA且MACD转正
            if (prev_macd.dif <= prev_macd.dea and 
                curr_macd.dif > curr_macd.dea and
                curr_macd.macd >= 0):
                return True
        
        return False
    
    def _check_death_cross(self, macd_data: List[MacdData], start_index: int) -> bool:
        """检查死叉（从指定位置开始往后检查几个周期）"""
        check_range = min(5, len(macd_data) - start_index)
        if check_range < 2:
            return False
        
        for i in range(start_index, start_index + check_range - 1):
            prev_macd = macd_data[i]
            curr_macd = macd_data[i + 1]
            
            # DIF下穿DEA且MACD转负
            if (prev_macd.dif >= prev_macd.dea and 
                curr_macd.dif < curr_macd.dea and
                curr_macd.macd <= 0):
                return True
        
        return False