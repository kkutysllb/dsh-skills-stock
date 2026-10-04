#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略适配器子模块
Strategy Adapters Submodule

本模块包含8大量化选股策略适配器，用于从API接口层分离出核心选股逻辑。
该架构调整将策略核心逻辑集中管理，API层只负责接口功能。

8大核心策略：
1. 价值投资策略 (value_investment_adapter.py)
2. 成长股策略 (growth_stock_adapter.py)
3. 动量突破策略 (momentum_breakthrough_adapter.py)
4. 高股息策略 (high_dividend_adapter.py)
5. 技术突破策略 (technical_breakthrough_adapter.py)
6. 超跌反弹策略 (oversold_rebound_adapter_simple.py)
7. 连板龙头策略 (limit_up_leader_adapter_simple.py)
8. 融资追踪策略 (fund_flow_tracking_adapter.py)
"""

# 导入8大核心策略适配器
from .value_investment_adapter import ValueInvestmentAdapter
from .growth_stock_adapter import GrowthStockAdapter
from .momentum_breakthrough_adapter import MomentumBreakthroughAdapter
from .high_dividend_adapter import HighDividendAdapter
from .technical_breakthrough_adapter import TechnicalBreakthroughAdapter
from .oversold_rebound_adapter_simple import OversoldReboundAdapter
from .limit_up_leader_adapter_simple import LimitUpLeaderAdapter
from .fund_flow_tracking_adapter import FundFlowTrackingAdapter

# 8大核心策略适配器注册表
STRATEGY_ADAPTERS = {
    "value_investment_adapter": ValueInvestmentAdapter,           # 价值投资策略
    "growth_stock_adapter": GrowthStockAdapter,                   # 成长股策略
    "momentum_breakthrough_adapter": MomentumBreakthroughAdapter, # 动量突破策略
    "high_dividend_adapter": HighDividendAdapter,                 # 高股息策略
    "technical_breakthrough_adapter": TechnicalBreakthroughAdapter, # 技术突破策略
    "oversold_rebound_adapter": OversoldReboundAdapter,           # 超跌反弹策略
    "limit_up_leader_adapter": LimitUpLeaderAdapter,             # 连板龙头策略
    "fund_flow_tracking_adapter": FundFlowTrackingAdapter,       # 融资追踪策略
}

# 8大策略类型分类
STRATEGY_TYPES = {
    "value": ["value_investment_adapter"],          # 价值投资
    "growth": ["growth_stock_adapter"],            # 成长股
    "momentum": ["momentum_breakthrough_adapter"],  # 动量突破
    "dividend": ["high_dividend_adapter"],         # 高股息
    "technical": ["technical_breakthrough_adapter"], # 技术突破
    "rebound": ["oversold_rebound_adapter"],       # 超跌反弹
    "limit_up": ["limit_up_leader_adapter"],      # 连板龙头
    "fund_flow": ["fund_flow_tracking_adapter"],  # 融资追踪
}

def get_strategy_adapter(name: str):
    """
    获取策略适配器类
    
    Args:
        name: 策略适配器名称
        
    Returns:
        策略适配器类，如果未找到则返回None
    """
    return STRATEGY_ADAPTERS.get(name)

def get_all_strategies():
    """
    获取所有策略适配器
    
    Returns:
        策略适配器字典
    """
    return STRATEGY_ADAPTERS.copy()

def get_strategies_by_type(strategy_type: str):
    """
    根据策略类型获取策略适配器
    
    Args:
        strategy_type: 策略类型
        
    Returns:
        该类型的策略适配器名称列表
    """
    return STRATEGY_TYPES.get(strategy_type, [])

def list_all_strategy_names():
    """
    列出所有策略适配器名称
    
    Returns:
        策略适配器名称列表
    """
    return list(STRATEGY_ADAPTERS.keys())

def list_all_strategy_types():
    """
    列出所有策略类型
    
    Returns:
        策略类型列表
    """
    return list(STRATEGY_TYPES.keys())

# 导出的公共接口
__all__ = [
    # 8大核心策略适配器类
    'ValueInvestmentAdapter',
    'GrowthStockAdapter',
    'MomentumBreakthroughAdapter',
    'HighDividendAdapter',
    'TechnicalBreakthroughAdapter',
    'OversoldReboundAdapter',
    'LimitUpLeaderAdapter',
    'FundFlowTrackingAdapter',
    
    # 注册表和工具函数
    'STRATEGY_ADAPTERS',
    'STRATEGY_TYPES',
    'get_strategy_adapter',
    'get_all_strategies',
    'get_strategies_by_type',
    'list_all_strategy_names',
    'list_all_strategy_types'
]