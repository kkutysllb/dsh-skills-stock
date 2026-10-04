#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论增强分析模块 - 借鉴 czsc 库的成熟设计

核心借鉴点：
1. 信号-事件-交易体系：Signal + Event + Position
2. 多级别联立决策：CzscTrader 的多策略集成
3. 丰富的信号库：形态(cxt)、技术指标(tas)、位置(pos)等
4. 可视化集成：to_echarts 方法直接生成图表
5. 实时更新机制：CZSC.update() 支持流式数据

实现功能：
- 信号生成器：标准化信号格式
- 事件检测器：多信号组合触发事件
- 交易决策器：基于事件的买卖决策
- 多级别一致性分析：加权投票机制
"""

from typing import Dict, List, Optional, Callable, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict
import numpy as np

from chan_theory_v2.models.enums import TimeLevel, BiDirection, SegDirection
from chan_theory_v2.models.kline import KLine, KLineList
from chan_theory_v2.models.bi import Bi, BiList
from chan_theory_v2.models.seg import Seg, SegList
from chan_theory_v2.models.zhongshu import ZhongShu, ZhongShuList
from chan_theory_v2.models.dynamics import BuySellPoint, BuySellPointType, BackChi


class SignalType(Enum):
    """信号类型枚举"""
    # 形态信号
    FX_POWER = "fx_power"           # 分型强弱
    BI_STATUS = "bi_status"         # 笔状态
    BI_END = "bi_end"               # 笔结束信号
    ZS_FORMATION = "zs_formation"   # 中枢形成
    
    # 技术指标信号
    MACD_CROSS = "macd_cross"       # MACD金叉/死叉
    MACD_DIVERGENCE = "macd_divergence"  # MACD背离
    MA_TREND = "ma_trend"           # MA趋势
    
    # 买卖点信号
    FIRST_BUY = "first_buy"         # 一类买
    SECOND_BUY = "second_buy"       # 二类买
    THIRD_BUY = "third_buy"         # 三类买
    FIRST_SELL = "first_sell"       # 一类卖
    SECOND_SELL = "second_sell"     # 二类卖
    THIRD_SELL = "third_sell"       # 三类卖
    
    # 综合信号
    TREND_DIRECTION = "trend_direction"  # 趋势方向
    RISK_LEVEL = "risk_level"       # 风险等级


class SignalValue(Enum):
    """信号值枚举"""
    # 方向
    UP = "up"
    DOWN = "down"
    CONSOLIDATION = "consolidation"
    
    # 强弱
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    
    # 状态
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    RELAY = "relay"  # 中继
    REVERSAL = "reversal"  # 转折
    
    # MACD
    GOLDEN_CROSS = "golden_cross"
    DEATH_CROSS = "death_cross"
    TOP_DIVERGENCE = "top_divergence"
    BOTTOM_DIVERGENCE = "bottom_divergence"
    
    # 其他
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass
class ChanSignal:
    """
    缠论信号对象 - 借鉴 czsc.Signal 的设计
    
    信号格式：k1_k2_k3_v1_v2_v3
    例如：15分钟_D1F_分型强弱_强顶_有中枢_任意
    """
    # 信号标识
    k1: str  # 时间周期/级别
    k2: str  # 信号类型
    k3: str  # 信号子类型
    
    # 信号值
    v1: str = "其他"
    v2: str = "任意"
    v3: str = "任意"
    
    # 元数据
    timestamp: datetime = field(default_factory=datetime.now)
    score: float = 0.0  # 信号得分 0-1
    
    def __str__(self) -> str:
        return f"Signal('{self.k1}_{self.k2}_{self.k3}_{self.v1}_{self.v2}_{self.v3}')"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    @property
    def key(self) -> str:
        """信号唯一标识"""
        return f"{self.k1}_{self.k2}_{self.k3}"
    
    @property
    def value(self) -> str:
        """信号值组合"""
        return f"{self.v1}_{self.v2}_{self.v3}"
    
    def is_match(self, pattern: Dict[str, str]) -> bool:
        """检查信号是否匹配模式"""
        for key, value in pattern.items():
            if hasattr(self, key) and getattr(self, key) != value:
                return False
        return True


@dataclass
class ChanEvent:
    """
    缠论事件对象 - 多信号组合触发的事件
    
    借鉴 czsc.Event 的设计，支持多信号组合逻辑：
    - signals_all: 所有信号必须同时满足
    - signals_any: 任一信号满足即可
    - signals_not: 排除信号
    """
    name: str  # 事件名称
    description: str  # 事件描述
    
    # 触发条件
    signals_all: List[Dict[str, str]] = field(default_factory=list)  # 必须全部满足
    signals_any: List[Dict[str, str]] = field(default_factory=list)  # 任一满足
    signals_not: List[Dict[str, str]] = field(default_factory=list)  # 必须不满足
    
    # 事件属性
    priority: int = 0  # 优先级，越高越优先
    max_trigger_count: int = -1  # 最大触发次数，-1表示无限制
    
    # 运行时状态
    trigger_count: int = 0
    last_trigger_time: Optional[datetime] = None
    
    def check(self, signals: Dict[str, ChanSignal]) -> bool:
        """检查事件是否触发"""
        # 检查 signals_all - 所有必须满足
        for pattern in self.signals_all:
            matched = any(s.is_match(pattern) for s in signals.values())
            if not matched:
                return False
        
        # 检查 signals_any - 任一满足即可
        if self.signals_any:
            any_matched = any(
                any(s.is_match(pattern) for s in signals.values())
                for pattern in self.signals_any
            )
            if not any_matched:
                return False
        
        # 检查 signals_not - 必须不满足
        for pattern in self.signals_not:
            matched = any(s.is_match(pattern) for s in signals.values())
            if matched:
                return False
        
        # 检查触发次数限制
        if self.max_trigger_count > 0 and self.trigger_count >= self.max_trigger_count:
            return False
        
        return True
    
    def trigger(self) -> None:
        """记录事件触发"""
        self.trigger_count += 1
        self.last_trigger_time = datetime.now()


@dataclass
class TradingDecision:
    """交易决策对象"""
    action: str  # "buy", "sell", "hold"
    confidence: float  # 置信度 0-1
    reason: str  # 决策理由
    
    # 交易参数
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: float = 1.0  # 仓位比例 0-1
    
    # 信号来源
    signals: List[ChanSignal] = field(default_factory=list)
    events: List[str] = field(default_factory=list)


class SignalGenerator:
    """
    信号生成器 - 借鉴 czsc 的信号体系
    
    生成标准化的 ChanSignal 对象
    """
    
    def __init__(self):
        self.signal_cache: Dict[str, ChanSignal] = {}
    
    def generate_fx_signal(self, time_level: TimeLevel, 
                          fx_power: str, has_zs: bool) -> ChanSignal:
        """生成分型强弱信号"""
        return ChanSignal(
            k1=time_level.value,
            k2="分型强弱",
            k3="D1F",
            v1=fx_power,
            v2="有中枢" if has_zs else "无中枢",
            score=1.0 if fx_power == "强" else 0.7 if fx_power == "中" else 0.4
        )
    
    def generate_bi_signal(self, time_level: TimeLevel,
                          direction: str, status: str) -> ChanSignal:
        """生成笔状态信号"""
        return ChanSignal(
            k1=time_level.value,
            k2="笔状态",
            k3="D0BL",
            v1=direction,
            v2=status,
            score=0.8 if status == "转折" else 0.5
        )
    
    def generate_macd_signal(self, time_level: TimeLevel,
                            cross_type: str, divergence: str) -> ChanSignal:
        """生成MACD信号"""
        return ChanSignal(
            k1=time_level.value,
            k2="MACD",
            k3="信号",
            v1=cross_type,
            v2=divergence,
            score=0.9 if divergence != "无背离" else 0.6
        )
    
    def generate_buy_sell_signal(self, time_level: TimeLevel,
                                 point_type: BuySellPointType,
                                 reliability: float) -> ChanSignal:
        """生成买卖点信号"""
        type_map = {
            BuySellPointType.BUY_1: ("一类买", "BUY1"),
            BuySellPointType.BUY_2: ("二类买", "BUY2"),
            BuySellPointType.BUY_3: ("三类买", "BUY3"),
            BuySellPointType.SELL_1: ("一类卖", "SELL1"),
            BuySellPointType.SELL_2: ("二类卖", "SELL2"),
            BuySellPointType.SELL_3: ("三类卖", "SELL3"),
        }
        v1, k3 = type_map.get(point_type, ("其他", "UNKNOWN"))
        
        return ChanSignal(
            k1=time_level.value,
            k2="买卖点",
            k3=k3,
            v1=v1,
            v2=f"可靠度{int(reliability*100)}%",
            score=reliability
        )
    
    def generate_trend_signal(self, time_level: TimeLevel,
                             direction: str, strength: float) -> ChanSignal:
        """生成趋势信号"""
        strength_str = "强" if strength > 0.7 else "中" if strength > 0.4 else "弱"
        return ChanSignal(
            k1=time_level.value,
            k2="趋势方向",
            k3="综合",
            v1=direction,
            v2=strength_str,
            score=strength
        )
    
    def generate_risk_signal(self, time_level: TimeLevel,
                            risk_level: float) -> ChanSignal:
        """生成风险信号"""
        risk_str = "高" if risk_level > 0.7 else "中" if risk_level > 0.4 else "低"
        return ChanSignal(
            k1=time_level.value,
            k2="风险等级",
            k3="评估",
            v1=risk_str,
            v2=f"{int(risk_level*100)}%",
            score=1 - risk_level  # 风险越低得分越高
        )

    # ─── 新增关键信号函数（参考 czsc 的 cxt/tas 信号） ───

    def generate_bi_end_signal(self, time_level: TimeLevel,
                               bi_direction: str, is_ending: bool,
                               macd_confirms: bool) -> ChanSignal:
        """笔结束信号（参考 czsc 的 cxt 信号）

        当分型确认 + MACD配合时，判断笔可能结束
        Args:
            bi_direction: "向上" 或 "向下"
            is_ending: 笔是否即将结束
            macd_confirms: MACD是否确认（金叉/死叉）
        """
        v1 = "结束" if is_ending else "延续"
        v2 = "MACD确认" if macd_confirms else "MACD未确认"
        score = 0.9 if (is_ending and macd_confirms) else 0.6 if is_ending else 0.3

        return ChanSignal(
            k1=time_level.value,
            k2="笔结束",
            k3="BI_END",
            v1=v1,
            v2=v2,
            v3=bi_direction,
            score=score
        )

    def generate_zs_breakout_signal(self, time_level: TimeLevel,
                                     breakout_type: str, price: float,
                                     zs_high: float, zs_low: float) -> ChanSignal:
        """中枢突破信号（参考 czsc 的 cxt 信号）

        当价格突破中枢边界时触发
        Args:
            breakout_type: "向上突破" 或 "向下突破" 或 "未突破"
            price: 当前价格
            zs_high: 中枢上沿
            zs_low: 中枢下沿
        """
        if breakout_type == "向上突破":
            v1 = "向上突破"
            v2 = f"突破{zs_high:.2f}"
            score = 0.8
        elif breakout_type == "向下突破":
            v1 = "向下突破"
            v2 = f"跌破{zs_low:.2f}"
            score = 0.8
        else:
            v1 = "在中枢内"
            v2 = f"区间{zs_low:.2f}-{zs_high:.2f}"
            score = 0.3

        return ChanSignal(
            k1=time_level.value,
            k2="中枢突破",
            k3="ZS_BRK",
            v1=v1,
            v2=v2,
            score=score
        )

    def generate_macd_divergence_signal(self, time_level: TimeLevel,
                                         divergence_type: str,
                                         price_new_high: bool,
                                         macd_new_high: bool) -> ChanSignal:
        """MACD背离信号（参考 czsc 的 tas 信号）

        价格创新高但MACD不创新高 → 顶背离
        价格创新低但MACD不创新低 → 底背离
        Args:
            divergence_type: "顶背离" 或 "底背离" 或 "无背离"
            price_new_high: 价格是否创新高/低
            macd_new_high: MACD是否创新高/低
        """
        if divergence_type == "顶背离":
            v1 = "顶背离"
            v2 = "价格新高MACD未新高"
            score = 0.85
        elif divergence_type == "底背离":
            v1 = "底背离"
            v2 = "价格新低MACD未新低"
            score = 0.85
        else:
            v1 = "无背离"
            v2 = "量价配合正常"
            score = 0.3

        return ChanSignal(
            k1=time_level.value,
            k2="MACD背离",
            k3="MACD_DIV",
            v1=v1,
            v2=v2,
            score=score
        )

    def generate_volume_break_signal(self, time_level: TimeLevel,
                                      volume_ratio: float,
                                      price_direction: str) -> ChanSignal:
        """量能突破信号（参考 czsc 的 vol 信号）

        放量突破中枢时触发
        Args:
            volume_ratio: 量比（当前成交量/均量）
            price_direction: "向上" 或 "向下"
        """
        if volume_ratio > 3.0:
            v1 = "巨量"
            score = 0.9
        elif volume_ratio > 2.0:
            v1 = "大量"
            score = 0.7
        elif volume_ratio > 1.5:
            v1 = "放量"
            score = 0.5
        else:
            v1 = "缩量"
            score = 0.2

        return ChanSignal(
            k1=time_level.value,
            k2="量能信号",
            k3="VOL_BRK",
            v1=v1,
            v2=f"量比{volume_ratio:.1f}",
            v3=price_direction,
            score=score
        )


class EventDetector:
    """事件检测器 - 基于信号组合检测交易事件"""
    
    def __init__(self):
        self.events: List[ChanEvent] = []
        self._init_default_events()
    
    def _init_default_events(self) -> None:
        """初始化默认事件"""
        # 一类买事件
        self.events.append(ChanEvent(
            name="一类买机会",
            description="底背驰+一类买点",
            signals_all=[
                {"k2": "买卖点", "k3": "BUY1"},
            ],
            priority=3
        ))
        
        # 二类买事件
        self.events.append(ChanEvent(
            name="二类买机会",
            description="一类买后回抽确认",
            signals_all=[
                {"k2": "买卖点", "k3": "BUY2"},
            ],
            priority=2
        ))
        
        # 三类买事件
        self.events.append(ChanEvent(
            name="三类买机会",
            description="中枢突破后回试",
            signals_all=[
                {"k2": "买卖点", "k3": "BUY3"},
            ],
            priority=1
        ))
        
        # 趋势反转事件
        self.events.append(ChanEvent(
            name="趋势反转",
            description="多信号确认趋势反转",
            signals_all=[
                {"k2": "MACD", "v2": "底背离"},
            ],
            signals_any=[
                {"k2": "买卖点", "v1": "一类买"},
                {"k2": "笔状态", "v2": "转折"},
            ],
            priority=3
        ))
        
        # 高风险事件
        self.events.append(ChanEvent(
            name="高风险警告",
            description="顶背驰+一类卖点",
            signals_all=[
                {"k2": "风险等级", "v1": "高"},
            ],
            signals_any=[
                {"k2": "买卖点", "v1": "一类卖"},
                {"k2": "MACD", "v2": "顶背离"},
            ],
            priority=3
        ))
    
    def add_event(self, event: ChanEvent) -> None:
        """添加自定义事件"""
        self.events.append(event)
    
    def detect(self, signals: Dict[str, ChanSignal]) -> List[ChanEvent]:
        """检测触发的事件"""
        triggered = []
        for event in sorted(self.events, key=lambda e: -e.priority):
            if event.check(signals):
                event.trigger()
                triggered.append(event)
        return triggered


class TradingDecisionMaker:
    """交易决策器 - 基于事件生成交易决策"""
    
    def __init__(self):
        self.detector = EventDetector()
    
    def make_decision(self, signals: Dict[str, ChanSignal],
                     current_price: float,
                     zhongshus: ZhongShuList = None) -> TradingDecision:
        """生成交易决策"""
        # 检测事件
        events = self.detector.detect(signals)
        
        if not events:
            return TradingDecision(
                action="hold",
                confidence=0.5,
                reason="无明确信号"
            )
        
        # 根据最高优先级事件生成决策
        top_event = events[0]
        
        if "买" in top_event.name:
            return self._make_buy_decision(events, signals, current_price, zhongshus)
        elif "卖" in top_event.name or "风险" in top_event.name:
            return self._make_sell_decision(events, signals, current_price, zhongshus)
        else:
            return TradingDecision(
                action="hold",
                confidence=0.5,
                reason=f"事件：{top_event.name}"
            )
    
    def _make_buy_decision(self, events: List[ChanEvent],
                          signals: Dict[str, ChanSignal],
                          current_price: float,
                          zhongshus: ZhongShuList = None) -> TradingDecision:
        """生成买入决策"""
        # 计算置信度
        buy_signals = [s for s in signals.values() if s.k2 == "买卖点" and "买" in s.v1]
        avg_confidence = sum(s.score for s in buy_signals) / len(buy_signals) if buy_signals else 0.5
        
        # 确定仓位
        position_size = min(avg_confidence * 1.2, 1.0)
        
        # 设置止损止盈
        stop_loss = current_price * 0.95
        take_profit = current_price * 1.1
        
        if zhongshus and len(zhongshus) > 0:
            latest_zs = zhongshus[-1]
            stop_loss = min(stop_loss, latest_zs.low * 0.98)
        
        return TradingDecision(
            action="buy",
            confidence=avg_confidence,
            reason=f"触发事件：{', '.join(e.name for e in events)}",
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            signals=list(signals.values()),
            events=[e.name for e in events]
        )
    
    def _make_sell_decision(self, events: List[ChanEvent],
                           signals: Dict[str, ChanSignal],
                           current_price: float,
                           zhongshus: ZhongShuList = None) -> TradingDecision:
        """生成卖出决策"""
        sell_signals = [s for s in signals.values() if s.k2 == "买卖点" and "卖" in s.v1]
        avg_confidence = sum(s.score for s in sell_signals) / len(sell_signals) if sell_signals else 0.5
        
        return TradingDecision(
            action="sell",
            confidence=avg_confidence,
            reason=f"触发事件：{', '.join(e.name for e in events)}",
            entry_price=current_price,
            signals=list(signals.values()),
            events=[e.name for e in events]
        )


class EnhancedChanAnalyzer:
    """
    增强型缠论分析器 - 整合信号、事件、决策
    
    借鉴 czsc 的设计，提供：
    1. 标准化信号生成（含100+信号函数库）
    2. 事件检测
    3. 交易决策
    4. 多级别一致性分析
    """
    
    def __init__(self):
        self.signal_generator = SignalGenerator()
        self.event_detector = EventDetector()
        self.decision_maker = TradingDecisionMaker()
        
        # 导入完整信号函数库（157个信号函数）
        from chan_theory_v2.signals import cxt, tas, bar, vol, jcc, pos, sta
        self._cxt = cxt
        self._tas = tas
        self._bar = bar
        self._vol = vol
        self._jcc = jcc
        self._pos = pos
        self._sta = sta
    
    def generate_all_signals(self, time_level: TimeLevel,
                            result: Any) -> Dict[str, ChanSignal]:
        """生成所有信号（兼容旧接口）"""
        signals = {}

        # 趋势信号
        if hasattr(result, 'trend_direction') and result.trend_direction:
            signals['trend'] = self.signal_generator.generate_trend_signal(
                time_level, result.trend_direction, result.trend_strength
            )

        # 风险信号
        if hasattr(result, 'risk_level'):
            signals['risk'] = self.signal_generator.generate_risk_signal(
                time_level, result.risk_level
            )

        # 买卖点信号
        if hasattr(result, 'buy_sell_points'):
            for i, point in enumerate(result.buy_sell_points[:3]):  # 只取前3个
                signals[f'bsp_{i}'] = self.signal_generator.generate_buy_sell_signal(
                    time_level, point.point_type, point.reliability
                )

        # ─── 笔结束信号 ───
        if hasattr(result, 'bis') and len(result.bis) > 0:
            last_bi = result.bis[-1]
            bi_dir = "向上" if hasattr(last_bi, 'is_up') and last_bi.is_up else "向下"
            has_fenxing = len(result.fenxings) > 0
            macd_confirms = len(result.backchi_analyses) > 0
            is_ending = has_fenxing
            signals['bi_end'] = self.signal_generator.generate_bi_end_signal(
                time_level, bi_dir, is_ending, macd_confirms
            )

        # ─── 中枢突破信号 ───
        if hasattr(result, 'zhongshus') and len(result.zhongshus) > 0:
            last_zs = result.zhongshus[-1]
            zs_high = last_zs.high if hasattr(last_zs, 'high') else 0
            zs_low = last_zs.low if hasattr(last_zs, 'low') else 0
            current_price = result.processed_klines[-1].close if hasattr(result, 'processed_klines') and len(result.processed_klines) > 0 else 0
            if current_price > 0 and zs_high > 0:
                if current_price > zs_high:
                    breakout = "向上突破"
                elif current_price < zs_low:
                    breakout = "向下突破"
                else:
                    breakout = "未突破"
                signals['zs_breakout'] = self.signal_generator.generate_zs_breakout_signal(
                    time_level, breakout, current_price, zs_high, zs_low
                )

        # ─── MACD背离信号 ───
        if hasattr(result, 'backchi_analyses') and len(result.backchi_analyses) > 0:
            latest_backchi = result.backchi_analyses[-1]
            div_type = str(latest_backchi.backchi_type) if hasattr(latest_backchi, 'backchi_type') else "无背离"
            if "顶" in div_type:
                signals['macd_div'] = self.signal_generator.generate_macd_divergence_signal(
                    time_level, "顶背离", True, False
                )
            elif "底" in div_type:
                signals['macd_div'] = self.signal_generator.generate_macd_divergence_signal(
                    time_level, "底背离", True, False
                )

        # ─── 量能突破信号 ───
        if hasattr(result, 'processed_klines') and len(result.processed_klines) >= 20:
            pklines = result.processed_klines
            recent_vol = pklines[-1].volume if hasattr(pklines[-1], 'volume') else 0
            avg_vol = sum(k.volume for k in pklines[-20:]) / 20 if len(pklines) >= 20 else 1
            if avg_vol > 0 and recent_vol > 0:
                vol_ratio = recent_vol / avg_vol
                price_dir = "向上" if result.trend_direction == "up" else "向下" if result.trend_direction == "down" else "横盘"
                signals['vol_break'] = self.signal_generator.generate_volume_break_signal(
                    time_level, vol_ratio, price_dir
                )

        return signals

    def generate_signal_library(self, time_level: TimeLevel,
                               result: Any) -> Dict[str, OrderedDict]:
        """使用完整信号函数库生成信号（100+信号）
        
        返回 OrderedDict 格式的信号字典，兼容 czsc 信号格式。
        按需调用，不会自动执行所有信号函数。
        """
        freq = time_level.value
        all_signals = {}

        # ─── cxt 缠论形态信号 ───
        bi_list = list(result.bis) if hasattr(result, 'bis') else []
        fx_list = list(result.fenxings) if hasattr(result, 'fenxings') else []
        zs_list = list(result.zhongshus) if hasattr(result, 'zhongshus') else []
        bars_ubi = []  # 未完成笔K线

        try:
            all_signals['bi_base'] = self._cxt.cxt_bi_base(freq, bi_list, bars_ubi)
        except Exception:
            pass
        try:
            all_signals['fx_power'] = self._cxt.cxt_fx_power(freq, fx_list, zhongshus=zs_list)
        except Exception:
            pass
        try:
            all_signals['bi_end'] = self._cxt.cxt_bi_end(freq, bi_list, fx_list, bars_ubi)
        except Exception:
            pass
        try:
            all_signals['bi_status'] = self._cxt.cxt_bi_status(freq, bi_list, bars_ubi)
        except Exception:
            pass
        try:
            all_signals['bi_trend'] = self._cxt.cxt_bi_trend(freq, bi_list)
        except Exception:
            pass
        try:
            all_signals['zs_breakout'] = self._cxt.cxt_zs_breakout(freq, zs_list,
                result.processed_klines[-1].close if hasattr(result, 'processed_klines') and len(result.processed_klines) > 0 else 0)
        except Exception:
            pass
        try:
            all_signals['zs_status'] = self._cxt.cxt_zs_status(freq, zs_list, bi_list)
        except Exception:
            pass
        try:
            all_signals['double_zs'] = self._cxt.cxt_double_zs(freq, zs_list)
        except Exception:
            pass
        try:
            all_signals['backchi'] = self._cxt.cxt_backchi_signal(freq,
                list(result.backchi_analyses) if hasattr(result, 'backchi_analyses') else [])
        except Exception:
            pass
        try:
            all_signals['decision'] = self._cxt.cxt_decision(freq, bi_list, zs_list,
                list(result.backchi_analyses) if hasattr(result, 'backchi_analyses') else None)
        except Exception:
            pass
        try:
            all_signals['bs_signal'] = self._cxt.cxt_bs_signal(freq, bi_list, zs_list,
                list(result.buy_sell_points) if hasattr(result, 'buy_sell_points') else None)
        except Exception:
            pass

        # 走势类型信号
        if hasattr(result, 'trend_type') and result.trend_type:
            try:
                all_signals['trend_type'] = self._cxt.cxt_trend_type_signal(
                    freq, str(result.trend_type.value) if hasattr(result.trend_type, 'value') else str(result.trend_type),
                    result.trend_analysis.trend_strength if hasattr(result, 'trend_analysis') and result.trend_analysis else 0)
            except Exception:
                pass

        # 多笔形态信号
        if len(bi_list) >= 5:
            try:
                all_signals['three_bi'] = self._cxt.cxt_three_bi(freq, bi_list)
            except Exception:
                pass
        if len(bi_list) >= 5:
            try:
                all_signals['five_bi'] = self._cxt.cxt_five_bi(freq, bi_list)
            except Exception:
                pass
        if len(bi_list) >= 7:
            try:
                all_signals['seven_bi'] = self._cxt.cxt_seven_bi(freq, bi_list)
            except Exception:
                pass

        # 买卖点信号
        if len(bi_list) >= 5 and zs_list:
            try:
                all_signals['first_buy'] = self._cxt.cxt_first_buy(freq, bi_list, zs_list)
            except Exception:
                pass
            try:
                all_signals['first_sell'] = self._cxt.cxt_first_sell(freq, bi_list, zs_list)
            except Exception:
                pass
            try:
                all_signals['second_bs'] = self._cxt.cxt_second_bs(freq, bi_list, zs_list)
            except Exception:
                pass
            try:
                all_signals['third_bs'] = self._cxt.cxt_third_bs(freq, bi_list, zs_list)
            except Exception:
                pass

        # ─── tas 技术指标信号 ───
        bars_raw = list(result.processed_klines) if hasattr(result, 'processed_klines') and len(result.processed_klines) > 0 else []
        if len(bars_raw) >= 50:
            try:
                all_signals['macd_cross'] = self._tas.tas_macd_cross(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['dif_zero'] = self._tas.tas_dif_zero(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['double_ma'] = self._tas.tas_double_ma(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['ma_system'] = self._tas.tas_ma_system(freq, bars_raw)
            except Exception:
                pass
        if len(bars_raw) >= 30:
            try:
                all_signals['boll_status'] = self._tas.tas_boll_status(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['kdj_cross'] = self._tas.tas_kdj_cross(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['rsi_status'] = self._tas.tas_rsi_status(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['atr'] = self._tas.tas_atr(freq, bars_raw)
            except Exception:
                pass

        # ─── bar K线基础信号 ───
        if len(bars_raw) >= 10:
            try:
                all_signals['bar_triple'] = self._bar.bar_triple_accelerate(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['bar_zdf'] = self._bar.bar_zdf(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['bar_big_solid'] = self._bar.bar_big_solid(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['bar_channel'] = self._bar.bar_channel(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['bar_momentum'] = self._bar.bar_section_momentum(freq, bars_raw)
            except Exception:
                pass

        # ─── vol 成交量信号 ───
        if len(bars_raw) >= 20:
            try:
                all_signals['vol_ratio'] = self._vol.vol_ratio_signal(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['vol_single_ma'] = self._vol.vol_single_ma(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['vol_window'] = self._vol.vol_window(freq, bars_raw)
            except Exception:
                pass

        # ─── jcc K线组合形态信号 ───
        if len(bars_raw) >= 5:
            try:
                all_signals['jcc_xing_xian'] = self._jcc.jcc_xing_xian(freq, bars_raw)
            except Exception:
                pass
            try:
                all_signals['jcc_hammer'] = self._jcc.jcc_hammer(freq, bars_raw)
            except Exception:
                pass
        if len(bars_raw) >= 8:
            try:
                all_signals['jcc_ta_xing'] = self._jcc.jcc_ta_xing(freq, bars_raw)
            except Exception:
                pass

        return all_signals
    
    def check_events(self, signals: Dict[str, ChanSignal]) -> List[ChanEvent]:
        """检查触发的事件"""
        return self.event_detector.detect(signals)
    
    def get_trading_decision(self, signals: Dict[str, ChanSignal],
                            current_price: float = None,
                            zhongshus: ZhongShuList = None) -> TradingDecision:
        """获取交易决策"""
        return self.decision_maker.make_decision(
            signals, current_price or 0.0, zhongshus
        )


def create_signals_summary(signals: Dict[str, ChanSignal]) -> str:
    """创建信号摘要"""
    lines = ["📊 信号汇总:"]
    
    # 按类型分组
    by_type = {}
    for sig in signals.values():
        if sig.k2 not in by_type:
            by_type[sig.k2] = []
        by_type[sig.k2].append(sig)
    
    for sig_type, sigs in by_type.items():
        lines.append(f"\n  【{sig_type}】")
        for sig in sigs:
            lines.append(f"    • {sig.v1} | {sig.v2} (得分: {sig.score:.2f})")
    
    return "\n".join(lines)


# 便捷函数
def quick_signals(result: Any, time_level: TimeLevel) -> Dict[str, ChanSignal]:
    """快速生成信号"""
    analyzer = EnhancedChanAnalyzer()
    return analyzer.generate_all_signals(time_level, result)
