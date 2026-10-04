#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论K线数据模型
参考Vespa314/chan.py的KLine设计，实现标准的K线数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Iterator
from decimal import Decimal
import pandas as pd
import numpy as np
from .enums import TimeLevel


@dataclass
class KLine:
    """
    单根K线数据模型
    参考Vespa314/chan.py的设计，包含完整的OHLCV数据和扩展信息
    """
    # 基础OHLCV数据
    timestamp: datetime              # 时间戳
    open: float                      # 开盘价
    high: float                      # 最高价
    low: float                       # 最低价  
    close: float                     # 收盘价
    volume: int                      # 成交量
    
    # 扩展数据
    amount: Optional[float] = None   # 成交额
    turnover: Optional[float] = None # 换手率
    
    # 级别信息
    level: Optional[TimeLevel] = None # 时间级别
    
    # 处理标记
    is_processed: bool = False       # 是否经过包含关系处理
    original_count: int = 1          # 原始K线数量（合并后>1）
    
    # 技术指标(可选)
    indicators: Dict[str, float] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后验证"""
        self._validate()
    
    def _validate(self) -> None:
        """数据有效性验证"""
        if self.high < max(self.open, self.close):
            raise ValueError(f"最高价 {self.high} 不能小于开盘价或收盘价")
        if self.low > min(self.open, self.close):
            raise ValueError(f"最低价 {self.low} 不能大于开盘价或收盘价")
        if self.volume < 0:
            raise ValueError(f"成交量 {self.volume} 不能为负数")
    
    @property
    def is_up(self) -> bool:
        """是否为阳线"""
        return self.close > self.open
    
    @property  
    def is_down(self) -> bool:
        """是否为阴线"""
        return self.close < self.open
    
    @property
    def is_doji(self) -> bool:
        """是否为十字星（开盘价等于收盘价）"""
        return abs(self.close - self.open) < 1e-6
    
    @property
    def body_size(self) -> float:
        """实体大小"""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        """上影线长度"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        """下影线长度"""  
        return min(self.open, self.close) - self.low
    
    @property
    def range_size(self) -> float:
        """全幅（最高价-最低价）"""
        return self.high - self.low
    
    @property
    def mid_price(self) -> float:
        """中间价（最高价+最低价）/2"""
        return (self.high + self.low) / 2
    
    @property
    def typical_price(self) -> float:
        """典型价（最高价+最低价+收盘价）/3"""
        return (self.high + self.low + self.close) / 3
    
    def contains(self, other: 'KLine') -> bool:
        """
        判断当前K线是否包含另一根K线
        包含关系：当前K线的高点>=other的高点 且 当前K线的低点<=other的低点
        """
        return self.high >= other.high and self.low <= other.low
    
    def is_contained_by(self, other: 'KLine') -> bool:
        """判断当前K线是否被另一根K线包含"""
        return other.contains(self)
    
    def has_include_relation(self, other: 'KLine') -> bool:
        """判断两根K线是否存在包含关系"""
        return self.contains(other) or other.contains(self)
    
    def merge_with(self, other: 'KLine', trend_up: bool = True) -> 'KLine':
        """
        与另一根K线合并（处理包含关系）
        
        Args:
            other: 另一根K线
            trend_up: 当前趋势是否向上
            
        Returns:
            合并后的新K线
        """
        if trend_up:
            # 上升趋势：高点取高，低点取高
            new_high = max(self.high, other.high)
            new_low = max(self.low, other.low)
        else:
            # 下降趋势：高点取低，低点取低  
            new_high = min(self.high, other.high)
            new_low = min(self.low, other.low)
        
        # 合并后的K线属性
        merged_kline = KLine(
            timestamp=max(self.timestamp, other.timestamp),  # 取较新的时间
            open=self.open,                                  # 开盘价保持第一根
            high=new_high,
            low=new_low,
            close=other.close,                               # 收盘价取最后一根
            volume=self.volume + other.volume,               # 成交量累加
            amount=(self.amount or 0) + (other.amount or 0), # 成交额累加
            level=self.level,
            is_processed=True,
            original_count=self.original_count + other.original_count
        )
        
        return merged_kline
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high, 
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'turnover': self.turnover,
            'level': self.level.value if self.level else None,
            'is_processed': self.is_processed,
            'original_count': self.original_count,
            'indicators': self.indicators
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KLine':
        """从字典创建K线"""
        kline_data = data.copy()
        if 'timestamp' in kline_data and isinstance(kline_data['timestamp'], str):
            kline_data['timestamp'] = datetime.fromisoformat(kline_data['timestamp'])
        if 'level' in kline_data and kline_data['level']:
            kline_data['level'] = TimeLevel(kline_data['level'])
        return cls(**kline_data)
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"KLine({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f}, "
                f"V:{self.volume})")
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if not isinstance(other, KLine):
            return False
        return (self.timestamp == other.timestamp and 
                abs(self.open - other.open) < 1e-6 and
                abs(self.high - other.high) < 1e-6 and
                abs(self.low - other.low) < 1e-6 and
                abs(self.close - other.close) < 1e-6)


class KLineList:
    """
    K线列表容器
    参考Vespa314/chan.py的KLineList设计，提供高效的K线数据管理
    """
    
    def __init__(self, klines: Optional[List[KLine]] = None, level: Optional[TimeLevel] = None):
        """
        初始化K线列表
        
        Args:
            klines: K线列表
            level: 时间级别
        """
        self._klines: List[KLine] = klines or []
        self._level = level
        self._is_processed = False
        
        # 设置K线级别
        if self._level:
            for kline in self._klines:
                if kline.level is None:
                    kline.level = self._level
    
    @property
    def klines(self) -> List[KLine]:
        """获取K线列表"""
        return self._klines
    
    @property
    def level(self) -> Optional[TimeLevel]:
        """获取时间级别"""
        return self._level
    
    @property
    def is_processed(self) -> bool:
        """是否已处理包含关系"""
        return self._is_processed
    
    def __len__(self) -> int:
        """K线数量"""
        return len(self._klines)
    
    def __getitem__(self, index: Union[int, slice]) -> Union[KLine, List[KLine]]:
        """索引访问"""
        return self._klines[index]
    
    def __iter__(self) -> Iterator[KLine]:
        """迭代器"""
        return iter(self._klines)
    
    def append(self, kline: KLine) -> None:
        """添加K线"""
        if self._level and kline.level is None:
            kline.level = self._level
        self._klines.append(kline)
        self._is_processed = False  # 标记需要重新处理
    
    def extend(self, klines: List[KLine]) -> None:
        """批量添加K线"""
        for kline in klines:
            if self._level and kline.level is None:
                kline.level = self._level
        self._klines.extend(klines)
        self._is_processed = False
    
    def clear(self) -> None:
        """清空K线"""
        self._klines.clear()
        self._is_processed = False
    
    def is_empty(self) -> bool:
        """是否为空"""
        return len(self._klines) == 0
    
    def get_price_range(self) -> Optional[tuple]:
        """获取价格范围(最低价, 最高价)"""
        if self.is_empty():
            return None
        
        min_low = min(kline.low for kline in self._klines)
        max_high = max(kline.high for kline in self._klines)
        return (min_low, max_high)
    
    def get_time_range(self) -> Optional[tuple]:
        """获取时间范围(开始时间, 结束时间)"""
        if self.is_empty():
            return None
        
        start_time = min(kline.timestamp for kline in self._klines)
        end_time = max(kline.timestamp for kline in self._klines)
        return (start_time, end_time)
    
    def get_volume_sum(self) -> int:
        """获取总成交量"""
        return sum(kline.volume for kline in self._klines)
    
    def get_amount_sum(self) -> float:
        """获取总成交额"""
        return sum(kline.amount or 0 for kline in self._klines)
    
    def to_dataframe(self) -> pd.DataFrame:
        """转换为pandas DataFrame"""
        if self.is_empty():
            return pd.DataFrame()
        
        data = []
        for kline in self._klines:
            row = {
                'timestamp': kline.timestamp,
                'open': kline.open,
                'high': kline.high,
                'low': kline.low,
                'close': kline.close,
                'volume': kline.volume,
                'amount': kline.amount,
                'turnover': kline.turnover
            }
            # 添加技术指标
            row.update(kline.indicators)
            data.append(row)
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, level: Optional[TimeLevel] = None) -> 'KLineList':
        """从pandas DataFrame创建K线列表"""
        klines = []
        
        for timestamp, row in df.iterrows():
            # 提取技术指标
            indicators = {}
            basic_cols = {'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover'}
            for col in df.columns:
                if col not in basic_cols:
                    indicators[col] = row.get(col)
            
            kline = KLine(
                timestamp=timestamp if isinstance(timestamp, datetime) else pd.to_datetime(timestamp),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row.get('volume', 0)),
                amount=float(row.get('amount')) if pd.notna(row.get('amount')) else None,
                turnover=float(row.get('turnover')) if pd.notna(row.get('turnover')) else None,
                level=level,
                indicators=indicators
            )
            klines.append(kline)
        
        return cls(klines, level)
    
    @classmethod
    def from_dict_data(cls, data: List[Dict[str, Any]], level: TimeLevel) -> 'KLineList':
        """
        从字典数据创建K线列表
        适配项目中的5分钟、30分钟、日线数据格式
        """
        klines = []
        
        for item in data:
            # 处理时间字段
            timestamp = item.get('trade_date') or item.get('datetime') or item.get('timestamp') or item.get('trade_time')
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            elif not isinstance(timestamp, datetime):
                continue  # 跳过无效时间数据
            
            # 处理价格字段  
            try:
                open_price = float(item.get('open', 0))
                high_price = float(item.get('high', 0))
                low_price = float(item.get('low', 0)) 
                close_price = float(item.get('close', 0))
                volume = int(item.get('vol', item.get('volume', 0)))
                
                # 处理成交额（可能有不同字段名）
                amount = item.get('amount') or item.get('turnover_value')
                amount = float(amount) if amount is not None else None
                
                # 创建K线
                kline = KLine(
                    timestamp=timestamp,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    amount=amount,
                    level=level
                )
                
                klines.append(kline)
                
            except (ValueError, TypeError) as e:
                # 跳过无效数据行
                continue
        
        return cls(klines, level)
    
    def validate_data(self) -> List[str]:
        """数据验证，返回错误信息列表"""
        errors = []
        
        if self.is_empty():
            errors.append("K线数据为空")
            return errors
        
        # 检查时间顺序
        timestamps = [kline.timestamp for kline in self._klines]
        if timestamps != sorted(timestamps):
            errors.append("K线时间顺序不正确")
        
        # 检查重复时间
        if len(set(timestamps)) != len(timestamps):
            errors.append("存在重复的时间戳")
        
        # 检查价格数据
        for i, kline in enumerate(self._klines):
            try:
                kline._validate()
            except ValueError as e:
                errors.append(f"第{i+1}根K线数据无效: {e}")
        
        return errors
    
    def __str__(self) -> str:
        """字符串表示"""
        level_str = f"({self._level.value})" if self._level else ""
        return f"KLineList{level_str}[{len(self._klines)} klines]"