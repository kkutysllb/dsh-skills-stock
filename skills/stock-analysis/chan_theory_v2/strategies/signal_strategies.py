#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论信号组合策略模板

基于信号函数库的输出，定义信号组合选股策略。
借鉴 chan_enhanced.py 中 ChanEvent 的 signals_all/any/not 机制，
结合 SignalScorer 的评分融合，实现灵活的策略配置。

策略模板包含：
1. 信号条件定义（signals_all/any/not）
2. 最低评分阈值
3. 策略权重和优先级
4. 信号方向约束（看多/看空/双向）

使用方式：
    from chan_theory_v2.strategies.signal_strategies import (
        STRATEGY_TEMPLATES, SignalStrategy, StrategyManager
    )
    manager = StrategyManager()
    results = manager.evaluate(signals, score_result)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StrategyDirection(Enum):
    """策略方向"""
    LONG = "long"       # 做多策略
    SHORT = "short"     # 做空策略
    BOTH = "both"       # 双向策略


class StrategyRiskLevel(Enum):
    """策略风险等级"""
    CONSERVATIVE = "conservative"   # 保守型
    MODERATE = "moderate"           # 稳健型
    AGGRESSIVE = "aggressive"       # 激进型


@dataclass
class SignalCondition:
    """信号条件定义
    
    Attributes:
        signal_name: 信号函数名（如 "cxt_first_buy"）
        value_pattern: 信号值匹配模式（支持通配符 "任意"）
        min_score: 最低评分阈值（可选）
    """
    signal_name: str
    value_pattern: str = "任意"
    min_score: float = 0.0

    def matches(self, signal_name: str, signal_value: str, score: float = 0.0) -> bool:
        """检查信号是否匹配条件"""
        if signal_name != self.signal_name:
            return False
        if self.value_pattern == "任意":
            return True
        if self.value_pattern in signal_value:
            return True
        if score < self.min_score:
            return False
        return False


@dataclass
class SignalStrategy:
    """信号组合策略定义
    
    Attributes:
        name: 策略名称
        description: 策略描述
        direction: 策略方向
        risk_level: 风险等级
        signals_all: 必须全部满足的信号条件
        signals_any: 任一满足即可的信号条件
        signals_not: 必须不满足的信号条件
        min_total_score: 最低综合评分阈值（0~100）
        min_category_scores: 各类别最低评分要求
        priority: 优先级（越高越优先）
    """
    name: str
    description: str
    direction: StrategyDirection = StrategyDirection.LONG
    risk_level: StrategyRiskLevel = StrategyRiskLevel.MODERATE
    
    # 信号条件
    signals_all: List[SignalCondition] = field(default_factory=list)
    signals_any: List[SignalCondition] = field(default_factory=list)
    signals_not: List[SignalCondition] = field(default_factory=list)
    
    # 评分阈值
    min_total_score: float = 55.0
    min_category_scores: Dict[str, float] = field(default_factory=dict)
    
    # 优先级
    priority: int = 0

    def evaluate(self, signals: Dict[str, Any],
                 score_result: Optional[Any] = None) -> Dict[str, Any]:
        """
        评估策略是否触发
        
        Args:
            signals: {信号名: OrderedDict} 格式的信号字典
            score_result: SignalScoreResult 评分结果（可选）
            
        Returns:
            评估结果字典
        """
        # 扁平化信号值，构建查找表
        signal_lookup = {}
        signal_scores = {}
        for sig_name, sig_value in signals.items():
            if hasattr(sig_value, 'values'):
                value_str = list(sig_value.values())[0] if sig_value else ""
            else:
                value_str = str(sig_value)
            signal_lookup[sig_name] = value_str
            signal_scores[sig_name] = 0.0  # 默认评分

        # 如果有评分结果，更新信号评分
        if score_result and hasattr(score_result, 'signal_details'):
            for detail in score_result.signal_details:
                signal_scores[detail['name']] = detail.get('score', 0.0)

        # 1. 检查 signals_all - 所有必须满足
        all_matched = True
        all_details = []
        for cond in self.signals_all:
            matched = False
            for sig_name, sig_value in signal_lookup.items():
                if cond.matches(sig_name, sig_value, signal_scores.get(sig_name, 0.0)):
                    matched = True
                    break
            all_details.append({
                "condition": f"{cond.signal_name}:{cond.value_pattern}",
                "matched": matched,
            })
            if not matched:
                all_matched = False
                break

        # 2. 检查 signals_any - 任一满足即可
        any_matched = True
        any_details = []
        if self.signals_any:
            any_matched = False
            for cond in self.signals_any:
                for sig_name, sig_value in signal_lookup.items():
                    if cond.matches(sig_name, sig_value, signal_scores.get(sig_name, 0.0)):
                        any_matched = True
                        any_details.append({
                            "condition": f"{cond.signal_name}:{cond.value_pattern}",
                            "matched": True,
                        })
                        break
                if any_matched:
                    break
            if not any_details:
                any_details = [{"condition": "无匹配", "matched": False}]

        # 3. 检查 signals_not - 必须不满足
        not_violated = True
        not_details = []
        for cond in self.signals_not:
            for sig_name, sig_value in signal_lookup.items():
                if cond.matches(sig_name, sig_value, signal_scores.get(sig_name, 0.0)):
                    not_violated = False
                    not_details.append({
                        "condition": f"{cond.signal_name}:{cond.value_pattern}",
                        "violated": True,
                    })
                    break
        if not not_details:
            not_details = [{"condition": "无违规", "violated": False}]

        # 4. 检查评分阈值
        score_passed = True
        score_detail = {}
        if score_result:
            score_detail["total_score"] = score_result.final_score
            if score_result.final_score < self.min_total_score:
                score_passed = False
            # 检查各类别最低评分
            for cat, min_score in self.min_category_scores.items():
                cat_score = score_result.category_scores.get(cat, 0.0)
                score_detail[f"{cat}_score"] = cat_score
                if cat_score < min_score:
                    score_passed = False

        # 综合判断
        triggered = all_matched and any_matched and not_violated and score_passed

        return {
            "strategy_name": self.name,
            "direction": self.direction.value,
            "risk_level": self.risk_level.value,
            "triggered": triggered,
            "conditions": {
                "all_matched": all_matched,
                "any_matched": any_matched,
                "not_violated": not_violated,
                "score_passed": score_passed,
            },
            "details": {
                "signals_all": all_details,
                "signals_any": any_details,
                "signals_not": not_details,
                "score": score_detail,
            },
            "min_total_score": self.min_total_score,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  预定义策略模板
# ═══════════════════════════════════════════════════════════════════════════

STRATEGY_TEMPLATES: Dict[str, SignalStrategy] = {
    # ── 底背驰反转策略 ──
    "底背驰反转": SignalStrategy(
        name="底背驰反转",
        description="底背驰+MACD金叉+放量确认，趋势反转做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.MODERATE,
        signals_all=[
            SignalCondition("cxt_backchi_signal", "底背驰"),
        ],
        signals_any=[
            SignalCondition("tas_macd_cross", "金叉"),
            SignalCondition("tas_kdj_cross", "金叉"),
            SignalCondition("tas_double_ma", "金叉"),
        ],
        signals_not=[
            SignalCondition("cxt_backchi_signal", "顶背驰"),
            SignalCondition("tas_rsi_status", "超买"),
        ],
        min_total_score=58.0,
        min_category_scores={"cxt": 10.0},
        priority=3,
    ),

    # ── 一类买点策略 ──
    "一类买点": SignalStrategy(
        name="一类买点",
        description="缠论一类买点+MACD底背离，高胜率做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.MODERATE,
        signals_all=[
            SignalCondition("cxt_first_buy", "一类买"),
        ],
        signals_any=[
            SignalCondition("tas_macd_bc", "底背驰"),
            SignalCondition("cxt_bi_macd_diverge", "底背离"),
        ],
        signals_not=[
            SignalCondition("cxt_backchi_signal", "顶背驰"),
        ],
        min_total_score=60.0,
        min_category_scores={"cxt": 20.0},
        priority=4,
    ),

    # ── 中枢突破追涨策略 ──
    "中枢突破追涨": SignalStrategy(
        name="中枢突破追涨",
        description="中枢向上突破+均线多头排列+放量，趋势追踪做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.AGGRESSIVE,
        signals_all=[
            SignalCondition("cxt_zs_breakout", "向上突破"),
        ],
        signals_any=[
            SignalCondition("tas_ma_system", "多头排列"),
            SignalCondition("tas_double_ma", "金叉"),
        ],
        signals_not=[
            SignalCondition("cxt_backchi_signal", "顶背驰"),
            SignalCondition("tas_rsi_status", "超买"),
        ],
        min_total_score=60.0,
        min_category_scores={"cxt": 15.0},
        priority=2,
    ),

    # ── 超卖反弹策略 ──
    "超卖反弹": SignalStrategy(
        name="超卖反弹",
        description="RSI超卖+KDJ金叉+底部K线组合，短线反弹做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.CONSERVATIVE,
        signals_all=[
            SignalCondition("tas_rsi_status", "超卖"),
        ],
        signals_any=[
            SignalCondition("tas_kdj_cross", "金叉"),
            SignalCondition("jcc_hammer", "锤子线"),
            SignalCondition("jcc_engulfing", "看多吞没"),
            SignalCondition("jcc_xing_xian", "晨星"),
        ],
        signals_not=[
            SignalCondition("tas_ma_system", "空头排列"),
        ],
        min_total_score=52.0,
        priority=1,
    ),

    # ── 均线多头回踩策略 ──
    "均线多头回踩": SignalStrategy(
        name="均线多头回踩",
        description="均线多头排列+回踩支撑+缩量，趋势延续做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.MODERATE,
        signals_all=[
            SignalCondition("tas_ma_system", "多头排列"),
            SignalCondition("pos_above_ma", "均线上方"),
        ],
        signals_any=[
            SignalCondition("tas_boll_status", "中轨上方"),
            SignalCondition("pos_support_resistance", "支撑位附近"),
            SignalCondition("vol_shrink", "缩量"),
        ],
        signals_not=[
            SignalCondition("bar_zdf", "大跌"),
            SignalCondition("bar_zdf", "跌停"),
        ],
        min_total_score=58.0,
        min_category_scores={"tas": 10.0},
        priority=2,
    ),

    # ── 三类买点中枢回试策略 ──
    "三类买点回试": SignalStrategy(
        name="三类买点回试",
        description="三类买点+中枢回试确认+量能配合，稳健做多",
        direction=StrategyDirection.LONG,
        risk_level=StrategyRiskLevel.CONSERVATIVE,
        signals_all=[
            SignalCondition("cxt_third_buy", "三类买"),
        ],
        signals_any=[
            SignalCondition("vol_break", "放量突破"),
            SignalCondition("tas_volume_price", "价涨量增"),
        ],
        signals_not=[
            SignalCondition("cxt_backchi_signal", "顶背驰"),
        ],
        min_total_score=55.0,
        min_category_scores={"cxt": 15.0},
        priority=3,
    ),

    # ── 顶背驰逃顶策略 ──
    "顶背驰逃顶": SignalStrategy(
        name="顶背驰逃顶",
        description="顶背驰+MACD死叉+高位K线组合，风险规避",
        direction=StrategyDirection.SHORT,
        risk_level=StrategyRiskLevel.MODERATE,
        signals_all=[
            SignalCondition("cxt_backchi_signal", "顶背驰"),
        ],
        signals_any=[
            SignalCondition("tas_macd_cross", "死叉"),
            SignalCondition("tas_kdj_cross", "死叉"),
            SignalCondition("jcc_wu_yun_gai_ding", "乌云盖顶"),
            SignalCondition("jcc_three_crow", "三只乌鸦"),
        ],
        signals_not=[
            SignalCondition("tas_ma_system", "多头排列"),
        ],
        min_total_score=40.0,
        min_category_scores={"cxt": -10.0},
        priority=4,
    ),

    # ── 缩量阴跌风险策略 ──
    "缩量阴跌风险": SignalStrategy(
        name="缩量阴跌风险",
        description="空头排列+缩量+位置偏下，持续下跌风险",
        direction=StrategyDirection.SHORT,
        risk_level=StrategyRiskLevel.CONSERVATIVE,
        signals_all=[
            SignalCondition("tas_ma_system", "空头排列"),
        ],
        signals_any=[
            SignalCondition("vol_shrink", "缩量"),
            SignalCondition("tas_rsi_status", "偏弱"),
        ],
        signals_not=[
            SignalCondition("cxt_backchi_signal", "底背驰"),
        ],
        min_total_score=42.0,
        min_category_scores={"tas": -10.0},
        priority=1,
    ),
}


class StrategyManager:
    """策略管理器 - 管理和执行多个策略"""

    def __init__(self, strategies: Optional[Dict[str, SignalStrategy]] = None):
        self.strategies = strategies or STRATEGY_TEMPLATES.copy()

    def evaluate_all(self, signals: Dict[str, Any],
                     score_result: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        评估所有策略

        Args:
            signals: 信号字典
            score_result: SignalScoreResult 评分结果

        Returns:
            按优先级排序的策略评估结果列表
        """
        results = []
        for name, strategy in self.strategies.items():
            try:
                result = strategy.evaluate(signals, score_result)
                results.append(result)
            except Exception as e:
                logger.debug(f"策略 {name} 评估失败: {e}")

        # 按优先级排序
        results.sort(key=lambda x: self.strategies[x["strategy_name"]].priority
                     if x["strategy_name"] in self.strategies else 0, reverse=True)

        return results

    def get_triggered_strategies(self, signals: Dict[str, Any],
                                  score_result: Optional[Any] = None) -> List[Dict[str, Any]]:
        """获取所有被触发的策略"""
        all_results = self.evaluate_all(signals, score_result)
        return [r for r in all_results if r["triggered"]]

    def get_best_strategy(self, signals: Dict[str, Any],
                           score_result: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """获取最优触发的策略（优先级最高）"""
        triggered = self.get_triggered_strategies(signals, score_result)
        return triggered[0] if triggered else None

    def add_strategy(self, strategy: SignalStrategy) -> None:
        """添加自定义策略"""
        self.strategies[strategy.name] = strategy

    def remove_strategy(self, name: str) -> None:
        """移除策略"""
        self.strategies.pop(name, None)

    def list_strategies(self) -> List[Dict[str, str]]:
        """列出所有策略"""
        return [
            {
                "name": s.name,
                "description": s.description,
                "direction": s.direction.value,
                "risk_level": s.risk_level.value,
                "priority": s.priority,
            }
            for s in self.strategies.values()
        ]
