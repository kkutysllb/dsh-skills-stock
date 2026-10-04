#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论分析模块 V2.0
基于Vespa314/chan.py设计思路重构的专业缠论分析系统

特性:
- 严格的缠论理论实现
- 模块化设计，易于扩展
- 高性能计算引擎
- 完整的多级别联立分析
- 丰富的买卖点识别算法
- 灵活的数据源支持

作者: KK量化团队
版本: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "KK量化团队"

from .config.chan_config import ChanConfig
from .models.enums import TimeLevel, FenXingType, BiDirection, SegDirection
from .core.kline_processor import KlineProcessor
from . import signals  # 信号函数库

__all__ = [
    'ChanConfig',
    'TimeLevel', 'FenXingType', 'BiDirection', 'SegDirection',
    'KlineProcessor',
    'signals',
]