"""
策略模板库 — 经典量化策略 SignalEngine 实现

提供 3 种即用策略:
  - DualMASignal: 双均线交叉
  - RSISignal: RSI 超买超卖
  - MACDSignal: MACD 金叉死叉
"""

import numpy as np
import pandas as pd
from typing import Dict


class DualMASignal:
    """双均线交叉策略"""

    def __init__(self, short_window=5, long_window=20):
        self.short_window = short_window
        self.long_window = long_window

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signals = {}
        for code, df in data_map.items():
            close = df["close"]
            ma_short = close.rolling(self.short_window).mean()
            ma_long = close.rolling(self.long_window).mean()
            sig = pd.Series(0.0, index=df.index)
            sig[ma_short > ma_long] = 1.0
            sig[ma_short < ma_long] = -1.0
            # 前 long_window 天无信号
            sig.iloc[:self.long_window] = 0.0
            signals[code] = sig
        return signals


class RSISignal:
    """RSI 超买超卖策略"""

    def __init__(self, period=14, oversold=30, overbought=70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signals = {}
        for code, df in data_map.items():
            close = df["close"]
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(self.period).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(self.period).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            sig = pd.Series(0.0, index=df.index)
            sig[rsi < self.oversold] = 1.0   # 超卖→买入
            sig[rsi > self.overbought] = -1.0 # 超买→卖出
            sig.iloc[:self.period] = 0.0
            signals[code] = sig
        return signals


class MACDSignal:
    """MACD 金叉死叉策略"""

    def __init__(self, fast=12, slow=26, signal_period=9):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        signals = {}
        for code, df in data_map.items():
            close = df["close"]
            ema_fast = close.ewm(span=self.fast, adjust=False).mean()
            ema_slow = close.ewm(span=self.slow, adjust=False).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=self.signal_period, adjust=False).mean()
            sig = pd.Series(0.0, index=df.index)
            sig[macd > macd_signal] = 1.0   # 金叉→做多
            sig[macd < macd_signal] = -1.0   # 死叉→做空
            sig.iloc[:self.slow] = 0.0
            signals[code] = sig
        return signals


# 策略注册表
STRATEGY_REGISTRY = {
    "dual_ma": DualMASignal,
    "rsi": RSISignal,
    "macd": MACDSignal,
}


def get_strategy(name: str, **kwargs):
    """获取策略实例"""
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未知策略: {name}，可选: {list(STRATEGY_REGISTRY.keys())}")
    return cls(**kwargs)
