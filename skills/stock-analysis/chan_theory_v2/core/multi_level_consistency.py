#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多级别一致性分析模块

借鉴 czsc 库的信号-事件-交易逻辑体系，实现多级别联立决策
"""

from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

from chan_theory_v2.models.enums import TimeLevel
from chan_theory_v2.models.chan_buy_sell_points import BuySellPointType


class TrendDirection(Enum):
    """趋势方向"""
    UP = "up"
    DOWN = "down"
    CONSOLIDATION = "consolidation"
    UNKNOWN = "unknown"


class SignalStrength(Enum):
    """信号强度"""
    STRONG = 3
    MEDIUM = 2
    WEAK = 1
    NONE = 0


@dataclass
class LevelSignal:
    """级别信号"""
    time_level: TimeLevel
    trend_direction: TrendDirection
    trend_strength: float  # 0-1
    has_buy_signal: bool
    has_sell_signal: bool
    buy_point_types: List[BuySellPointType] = field(default_factory=list)
    sell_point_types: List[BuySellPointType] = field(default_factory=list)
    confidence: float = 0.0
    reliability: float = 0.0


@dataclass
class MultiLevelConsensus:
    """多级别共识结果"""
    # 各级别信号
    level_signals: Dict[TimeLevel, LevelSignal] = field(default_factory=dict)
    
    # 综合评估
    overall_direction: TrendDirection = TrendDirection.UNKNOWN
    overall_confidence: float = 0.0
    consistency_score: float = 0.0  # 一致性得分 0-1
    
    # 买卖点统计
    buy_consensus: int = 0  # 看涨级别数量
    sell_consensus: int = 0  # 看跌级别数量
    neutral_count: int = 0  # 中性级别数量
    
    # 共振分析
    resonance_levels: List[TimeLevel] = field(default_factory=list)  # 共振的级别
    resonance_strength: float = 0.0  # 共振强度
    
    # 交易建议
    recommended_action: str = "hold"  # "buy", "sell", "hold"
    position_size: float = 0.0  # 建议仓位 0-1
    urgency: str = "normal"  # "high", "normal", "low"
    
    # 详细分析
    analysis_summary: str = ""
    risk_warnings: List[str] = field(default_factory=list)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "overall_direction": self.overall_direction.value,
            "overall_confidence": self.overall_confidence,
            "consistency_score": self.consistency_score,
            "buy_consensus": self.buy_consensus,
            "sell_consensus": self.sell_consensus,
            "recommended_action": self.recommended_action,
            "position_size": self.position_size,
            "urgency": self.urgency,
            "resonance_levels": [l.value for l in self.resonance_levels],
            "resonance_strength": self.resonance_strength
        }


class MultiLevelConsistencyAnalyzer:
    """
    多级别一致性分析器
    
    借鉴 czsc 的多级别联立决策思想
    """
    
    # 级别权重配置（大级别权重更高）
    LEVEL_WEIGHTS = {
        TimeLevel.MONTHLY: 1.0,
        TimeLevel.WEEKLY: 0.9,
        TimeLevel.DAILY: 0.8,
        TimeLevel.MIN_120: 0.7,
        TimeLevel.MIN_90: 0.65,
        TimeLevel.MIN_60: 0.6,
        TimeLevel.MIN_30: 0.5,
        TimeLevel.MIN_15: 0.4,
        TimeLevel.MIN_5: 0.3,
    }
    
    def __init__(self):
        self.consensus = MultiLevelConsensus()
    
    def analyze(self, level_results: Dict[TimeLevel, Any]) -> MultiLevelConsensus:
        """
        执行多级别一致性分析
        
        Args:
            level_results: 各级别的分析结果
            
        Returns:
            多级别共识结果
        """
        self.consensus = MultiLevelConsensus()
        
        # 1. 提取各级别信号
        self._extract_level_signals(level_results)
        
        # 2. 计算一致性得分
        self._calculate_consistency()
        
        # 3. 检测多级别共振
        self._detect_resonance()
        
        # 4. 生成综合决策
        self._generate_consensus_decision()
        
        # 5. 生成分析摘要
        self._generate_summary()
        
        return self.consensus
    
    def _extract_level_signals(self, level_results: Dict[TimeLevel, Any]) -> None:
        """提取各级别信号"""
        for level, result in level_results.items():
            signal = LevelSignal(
                time_level=level,
                trend_direction=self._parse_trend_direction(result),
                trend_strength=getattr(result, 'trend_strength', 0.0),
                has_buy_signal=False,
                has_sell_signal=False,
                confidence=getattr(result, 'confidence_score', 0.0),
                reliability=getattr(result, 'confidence_score', 0.0)
            )
            
            # 提取买卖点信息
            if hasattr(result, 'buy_sell_points'):
                for point in result.buy_sell_points:
                    if point.point_type.is_buy():
                        signal.has_buy_signal = True
                        signal.buy_point_types.append(point.point_type)
                    else:
                        signal.has_sell_signal = True
                        signal.sell_point_types.append(point.point_type)
            
            self.consensus.level_signals[level] = signal
    
    def _parse_trend_direction(self, result: Any) -> TrendDirection:
        """解析趋势方向"""
        direction = getattr(result, 'trend_direction', 'consolidation')
        direction_map = {
            'up': TrendDirection.UP,
            'down': TrendDirection.DOWN,
            'consolidation': TrendDirection.CONSOLIDATION
        }
        return direction_map.get(direction, TrendDirection.UNKNOWN)
    
    def _calculate_consistency(self) -> None:
        """计算级别间一致性"""
        if len(self.consensus.level_signals) < 2:
            self.consensus.consistency_score = 0.0
            return
        
        signals = list(self.consensus.level_signals.values())
        
        # 统计各方向数量
        up_count = sum(1 for s in signals if s.trend_direction == TrendDirection.UP)
        down_count = sum(1 for s in signals if s.trend_direction == TrendDirection.DOWN)
        neutral_count = len(signals) - up_count - down_count
        
        # 一致性得分 = 最大一致方向的比例
        max_consensus = max(up_count, down_count, neutral_count)
        self.consensus.consistency_score = max_consensus / len(signals)
        
        # 统计买卖点共识
        self.consensus.buy_consensus = sum(1 for s in signals if s.has_buy_signal)
        self.consensus.sell_consensus = sum(1 for s in signals if s.has_sell_signal)
        self.consensus.neutral_count = neutral_count
    
    def _detect_resonance(self) -> None:
        """检测多级别共振"""
        resonance_levels = []
        total_weight = 0.0
        matched_weight = 0.0
        
        # 确定主导方向
        if self.consensus.buy_consensus > self.consensus.sell_consensus:
            dominant_direction = TrendDirection.UP
        elif self.consensus.sell_consensus > self.consensus.buy_consensus:
            dominant_direction = TrendDirection.DOWN
        else:
            dominant_direction = TrendDirection.CONSOLIDATION
        
        # 找出与主导方向一致的级别
        for level, signal in self.consensus.level_signals.items():
            weight = self.LEVEL_WEIGHTS.get(level, 0.5)
            total_weight += weight
            
            if signal.trend_direction == dominant_direction:
                resonance_levels.append(level)
                matched_weight += weight
                
                # 如果有同向买卖点，增强共振
                if (dominant_direction == TrendDirection.UP and signal.has_buy_signal) or \
                   (dominant_direction == TrendDirection.DOWN and signal.has_sell_signal):
                    matched_weight += weight * 0.3
        
        self.consensus.resonance_levels = resonance_levels
        self.consensus.resonance_strength = matched_weight / total_weight if total_weight > 0 else 0.0
    
    def _generate_consensus_decision(self) -> None:
        """生成综合决策"""
        signals = list(self.consensus.level_signals.values())
        
        if not signals:
            self.consensus.recommended_action = "hold"
            return
        
        # 加权计算综合方向
        up_score = 0.0
        down_score = 0.0
        total_weight = 0.0
        
        for level, signal in self.consensus.level_signals.items():
            weight = self.LEVEL_WEIGHTS.get(level, 0.5) * signal.trend_strength
            total_weight += weight
            
            if signal.trend_direction == TrendDirection.UP:
                up_score += weight
            elif signal.trend_direction == TrendDirection.DOWN:
                down_score += weight
        
        # 确定综合方向
        if up_score > down_score * 1.5:
            self.consensus.overall_direction = TrendDirection.UP
        elif down_score > up_score * 1.5:
            self.consensus.overall_direction = TrendDirection.DOWN
        else:
            self.consensus.overall_direction = TrendDirection.CONSOLIDATION
        
        # 计算综合置信度
        self.consensus.overall_confidence = max(up_score, down_score) / total_weight if total_weight > 0 else 0.0
        
        # 生成交易建议
        self._generate_trading_recommendation()
    
    def _generate_trading_recommendation(self) -> None:
        """生成交易建议"""
        # 基于综合方向和共振强度生成建议
        if self.consensus.overall_direction == TrendDirection.UP:
            if self.consensus.resonance_strength > 0.7:
                self.consensus.recommended_action = "buy"
                self.consensus.position_size = min(self.consensus.resonance_strength * 1.2, 1.0)
                self.consensus.urgency = "high" if self.consensus.resonance_strength > 0.85 else "normal"
            elif self.consensus.resonance_strength > 0.5:
                self.consensus.recommended_action = "buy"
                self.consensus.position_size = self.consensus.resonance_strength * 0.6
                self.consensus.urgency = "normal"
            else:
                self.consensus.recommended_action = "hold"
                self.consensus.position_size = 0.0
                self.consensus.urgency = "low"
                
        elif self.consensus.overall_direction == TrendDirection.DOWN:
            if self.consensus.resonance_strength > 0.7:
                self.consensus.recommended_action = "sell"
                self.consensus.position_size = 1.0  # 清仓
                self.consensus.urgency = "high"
            elif self.consensus.resonance_strength > 0.5:
                self.consensus.recommended_action = "sell"
                self.consensus.position_size = 0.5
                self.consensus.urgency = "normal"
            else:
                self.consensus.recommended_action = "hold"
                self.consensus.position_size = 0.0
                self.consensus.urgency = "low"
        else:
            self.consensus.recommended_action = "hold"
            self.consensus.position_size = 0.0
            self.consensus.urgency = "low"
        
        # 添加风险提示
        if self.consensus.consistency_score < 0.5:
            self.consensus.risk_warnings.append("级别间方向不一致，建议观望")
        
        if self.consensus.overall_confidence < 0.5:
            self.consensus.risk_warnings.append("整体置信度较低，谨慎操作")
    
    def _generate_summary(self) -> None:
        """生成分析摘要"""
        lines = []
        
        # 方向分析
        direction_map = {
            TrendDirection.UP: "看涨 📈",
            TrendDirection.DOWN: "看跌 📉",
            TrendDirection.CONSOLIDATION: "震荡 ↔️",
            TrendDirection.UNKNOWN: "未知 ❓"
        }
        lines.append(f"综合方向: {direction_map.get(self.consensus.overall_direction, '未知')}")
        lines.append(f"综合置信度: {self.consensus.overall_confidence:.1%}")
        lines.append(f"一致性得分: {self.consensus.consistency_score:.1%}")
        
        # 共振分析
        if self.consensus.resonance_levels:
            levels_str = ", ".join([l.value for l in self.consensus.resonance_levels])
            lines.append(f"共振级别: {levels_str}")
            lines.append(f"共振强度: {self.consensus.resonance_strength:.1%}")
        
        # 买卖点统计
        lines.append(f"看涨级别数: {self.consensus.buy_consensus}")
        lines.append(f"看跌级别数: {self.consensus.sell_consensus}")
        
        # 风险提示
        if self.consensus.risk_warnings:
            lines.append("\n风险提示:")
            for warning in self.consensus.risk_warnings:
                lines.append(f"  ⚠️ {warning}")
        
        self.consensus.analysis_summary = "\n".join(lines)


# 便捷函数
def calculate_level_consistency(level_results: Dict[TimeLevel, Any],
                                method: str = "weighted_vote") -> MultiLevelConsensus:
    """
    计算多级别一致性
    
    Args:
        level_results: 各级别分析结果
        method: 集成方法 (weighted_vote, mean, max)
        
    Returns:
        多级别共识结果
    """
    analyzer = MultiLevelConsistencyAnalyzer()
    return analyzer.analyze(level_results)


def get_trading_suggestion(consensus: MultiLevelConsensus) -> str:
    """获取交易建议文本"""
    action_map = {
        "buy": "买入",
        "sell": "卖出",
        "hold": "持仓观望"
    }
    
    urgency_map = {
        "high": "紧急",
        "normal": "一般",
        "low": "可等待"
    }
    
    suggestion = f"""
╔══════════════════════════════════════════════════════════╗
║                    📊 多级别综合决策                      ║
╠══════════════════════════════════════════════════════════╣
║  操作建议: {action_map.get(consensus.recommended_action, '观望'):^10}                    ║
║  紧急程度: {urgency_map.get(consensus.urgency, '一般'):^10}                    ║
║  建议仓位: {consensus.position_size:.0%}                                          ║
║  综合置信度: {consensus.overall_confidence:.1%}                                       ║
║  共振强度: {consensus.resonance_strength:.1%}                                        ║
╚══════════════════════════════════════════════════════════╝
"""
    return suggestion
