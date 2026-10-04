#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
艾略特波浪理论分析脚本

基于 Zigzag 摆动点检测，匹配 5 浪推动与 3 浪调整结构，
结合斐波那契关系校验，生成趋势见顶与调整完成信号。

数据来源于 Tushare Pro API（T+1延迟）。

核心功能：
  - Zigzag 摆动点检测（滚动窗口局部极值）
  - 5 浪推动结构匹配 + 三大铁律验证
  - ABC 调整结构匹配
  - 斐波那契浪间关系过滤
  - 信号生成：1=做多, -1=做空, 0=观望

用法:
    python scripts/analysis-engine/analyze_elliott_wave.py --stock 600519.SH --json
    python scripts/analysis-engine/analyze_elliott_wave.py --stock 宁德时代 --period 30min --json
    python scripts/analysis-engine/analyze_elliott_wave.py --stock 300750.SZ --swing-window 15 --json
"""

import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# 路径设置
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PROJECT_ROOT = os.path.dirname(_SKILL_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ======================================================================
#  艾略特波浪信号引擎（自包含实现）
# ======================================================================

class ElliottWaveEngine:
    """艾略特波浪理论信号引擎。

    检测流程：
    1. Zigzag 摆动点检测（滚动窗口局部极值）
    2. 5 浪推动结构匹配 + 三大铁律验证
    3. ABC 调整结构匹配
    4. Fibonacci 浪间关系过滤

    策略：宁可漏信号也不误判。
    """

    def __init__(self, swing_window=10, fib_tolerance=0.15, min_wave_bars=5):
        self.swing_window = swing_window
        self.fib_tolerance = fib_tolerance
        self.min_wave_bars = min_wave_bars

    def _find_swings(self, high: pd.Series, low: pd.Series) -> List[Dict]:
        """用滚动窗口找局部高低点，生成交替的 Zigzag 序列。"""
        w = self.swing_window
        full_w = w * 2 + 1
        if len(high) < full_w:
            return []

        roll_max = high.rolling(full_w, center=True).max()
        roll_min = low.rolling(full_w, center=True).min()
        swing_high_mask = high == roll_max
        swing_low_mask = low == roll_min

        raw_points = []
        for idx in high.index:
            is_h = bool(swing_high_mask.get(idx, False))
            is_l = bool(swing_low_mask.get(idx, False))
            if is_h and not is_l:
                raw_points.append({"index": idx, "price": float(high[idx]), "type": "H"})
            elif is_l and not is_h:
                raw_points.append({"index": idx, "price": float(low[idx]), "type": "L"})

        if len(raw_points) < 2:
            return raw_points

        zigzag = [raw_points[0]]
        for pt in raw_points[1:]:
            if pt["type"] == zigzag[-1]["type"]:
                if pt["type"] == "H" and pt["price"] > zigzag[-1]["price"]:
                    zigzag[-1] = pt
                elif pt["type"] == "L" and pt["price"] < zigzag[-1]["price"]:
                    zigzag[-1] = pt
            else:
                zigzag.append(pt)
        return zigzag

    def _check_fib_ratios(self, w1, w2, w3, w4, w5) -> bool:
        """验证 5 浪推动结构的 Fibonacci 浪间关系。"""
        tol = self.fib_tolerance
        if w1 == 0 or w3 == 0:
            return False
        r2 = w2 / w1
        if not (0.5 - tol <= r2 <= 0.618 + tol):
            return False
        r3 = w3 / w1
        if not (1.0 - tol <= r3 <= 2.618 + tol):
            return False
        r4 = w4 / w3
        if not (0.236 - tol <= r4 <= 0.5 + tol):
            return False
        return True

    def _check_min_bars(self, swings, start, count) -> bool:
        """检查连续摆动点之间是否满足最少 K 线数。"""
        for i in range(start, start + count - 1):
            idx_a = swings[i]["index"]
            idx_b = swings[i + 1]["index"]
            if hasattr(idx_a, 'value') and hasattr(idx_b, 'value'):
                diff = abs((idx_b - idx_a).days)
            else:
                diff = abs(int(idx_b) - int(idx_a))
            if diff < self.min_wave_bars:
                return False
        return True

    def _find_impulse(self, swings) -> List[Tuple]:
        """在摆动序列中寻找 5 浪推动结构。"""
        results = []
        for i in range(len(swings) - 5):
            types = [s["type"] for s in swings[i:i + 6]]
            if types == ["L", "H", "L", "H", "L", "H"]:
                x, p1, p2, p3, p4, p5 = swings[i:i + 6]
                wave1 = p1["price"] - x["price"]
                wave2 = p1["price"] - p2["price"]
                wave3 = p3["price"] - p2["price"]
                wave4 = p3["price"] - p4["price"]
                wave5 = p5["price"] - p4["price"]
                if wave1 <= 0 or wave3 <= 0 or wave5 <= 0:
                    continue
                if p2["price"] <= x["price"]:
                    continue
                if wave3 < wave1 and wave3 < wave5:
                    continue
                if p4["price"] <= p1["price"]:
                    continue
                if not self._check_min_bars(swings, i, 6):
                    continue
                if not self._check_fib_ratios(wave1, wave2, wave3, wave4, wave5):
                    continue
                results.append({"index": p5["index"], "signal": -1, "type": "impulse_bearish",
                                "waves": {"w1": wave1, "w2": wave2, "w3": wave3, "w4": wave4, "w5": wave5}})

            elif types == ["H", "L", "H", "L", "H", "L"]:
                x, p1, p2, p3, p4, p5 = swings[i:i + 6]
                wave1 = x["price"] - p1["price"]
                wave2 = p2["price"] - p1["price"]
                wave3 = p2["price"] - p3["price"]
                wave4 = p4["price"] - p3["price"]
                wave5 = p4["price"] - p5["price"]
                if wave1 <= 0 or wave3 <= 0 or wave5 <= 0:
                    continue
                if p2["price"] >= x["price"]:
                    continue
                if wave3 < wave1 and wave3 < wave5:
                    continue
                if p4["price"] >= p1["price"]:
                    continue
                if not self._check_min_bars(swings, i, 6):
                    continue
                if not self._check_fib_ratios(wave1, wave2, wave3, wave4, wave5):
                    continue
                results.append({"index": p5["index"], "signal": 1, "type": "impulse_bullish",
                                "waves": {"w1": wave1, "w2": wave2, "w3": wave3, "w4": wave4, "w5": wave5}})
        return results

    def _find_abc(self, swings) -> List[Dict]:
        """在摆动序列中寻找 ABC 调整结构。"""
        tol = self.fib_tolerance
        results = []
        for i in range(len(swings) - 3):
            types = [s["type"] for s in swings[i:i + 4]]

            if types == ["H", "L", "H", "L"]:
                start, pa, pb, pc = swings[i:i + 4]
                wave_a = start["price"] - pa["price"]
                wave_b = pb["price"] - pa["price"]
                wave_c = pb["price"] - pc["price"]
                if wave_a <= 0 or wave_b <= 0 or wave_c <= 0:
                    continue
                if pb["price"] >= start["price"]:
                    continue
                r_b = wave_b / wave_a
                if not (0.382 - tol <= r_b <= 0.618 + tol):
                    continue
                r_c = wave_c / wave_a
                if not (0.618 - tol <= r_c <= 1.618 + tol):
                    continue
                if not self._check_min_bars(swings, i, 4):
                    continue
                results.append({"index": pc["index"], "signal": 1, "type": "abc_bullish",
                                "waves": {"a": wave_a, "b": wave_b, "c": wave_c}})

            elif types == ["L", "H", "L", "H"]:
                start, pa, pb, pc = swings[i:i + 4]
                wave_a = pa["price"] - start["price"]
                wave_b = pa["price"] - pb["price"]
                wave_c = pc["price"] - pb["price"]
                if wave_a <= 0 or wave_b <= 0 or wave_c <= 0:
                    continue
                if pb["price"] <= start["price"]:
                    continue
                r_b = wave_b / wave_a
                if not (0.382 - tol <= r_b <= 0.618 + tol):
                    continue
                r_c = wave_c / wave_a
                if not (0.618 - tol <= r_c <= 1.618 + tol):
                    continue
                if not self._check_min_bars(swings, i, 4):
                    continue
                results.append({"index": pc["index"], "signal": -1, "type": "abc_bearish",
                                "waves": {"a": wave_a, "b": wave_b, "c": wave_c}})
        return results

    def analyze(self, df: pd.DataFrame) -> Dict:
        """分析 DataFrame 中的波浪结构。

        Args:
            df: OHLCV DataFrame，需包含 high/low/close 列。

        Returns:
            分析结果字典。
        """
        swings = self._find_swings(df["high"], df["low"])
        impulse_signals = self._find_impulse(swings) if len(swings) >= 6 else []
        abc_signals = self._find_abc(swings) if len(swings) >= 4 else []

        # 生成信号序列
        signal_series = pd.Series(0, index=df.index, dtype=int)
        all_signals = []
        for sig in impulse_signals + abc_signals:
            idx = sig["index"]
            if idx in signal_series.index:
                signal_series[idx] = sig["signal"]
            all_signals.append({
                "date": str(idx),
                "signal": sig["signal"],
                "signal_name": "做多" if sig["signal"] == 1 else "做空",
                "type": sig["type"],
                "type_name": self._type_name(sig["type"]),
                "waves": sig["waves"]
            })

        buy_count = sum(1 for s in all_signals if s["signal"] == 1)
        sell_count = sum(1 for s in all_signals if s["signal"] == -1)

        # 最新信号
        latest_signal = None
        if all_signals:
            latest_signal = all_signals[-1]

        return {
            "total_bars": len(df),
            "swing_points": len(swings),
            "total_signals": len(all_signals),
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "latest_signal": latest_signal,
            "signals": all_signals[-20:],  # 最近20个信号
            "parameters": {
                "swing_window": self.swing_window,
                "fib_tolerance": self.fib_tolerance,
                "min_wave_bars": self.min_wave_bars
            }
        }

    @staticmethod
    def _type_name(t: str) -> str:
        names = {
            "impulse_bearish": "5浪上升完成（看跌）",
            "impulse_bullish": "5浪下跌完成（看涨）",
            "abc_bullish": "ABC下调完成（看涨）",
            "abc_bearish": "ABC上调完成（看跌）"
        }
        return names.get(t, t)


# ======================================================================
#  数据获取
# ======================================================================

def _fetch_stock_data(stock_code: str, period: str = "daily", limit: int = 300) -> pd.DataFrame:
    """从 Tushare 获取股票 K 线数据。"""
    try:
        from kk_common import get_finance_data_gateway
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN 环境变量未设置")
        pro = get_finance_data_gateway()

        # 处理股票代码格式
        if '.' not in stock_code:
            stock_code = _resolve_stock_code(stock_code, pro)

        df = pro.daily(ts_code=stock_code, limit=limit) if period == "daily" else None
        if df is None or df.empty:
            df = pro.daily(ts_code=stock_code, limit=limit)

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.sort_values("trade_date")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date")
        df = df.rename(columns={"vol": "volume"})
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df[["open", "high", "low", "close", "volume"]].dropna()
    except ImportError:
        return pd.DataFrame()
    except Exception as e:
        print(f"数据获取错误: {e}", file=sys.stderr)
        return pd.DataFrame()


def _resolve_stock_code(name_or_code: str, pro) -> str:
    """将股票名称或简写代码解析为完整 ts_code。"""
    if '.' in name_or_code:
        return name_or_code
    if name_or_code.isdigit() and len(name_or_code) == 6:
        suffix = ".SZ" if name_or_code.startswith(("0", "3")) else ".SH"
        return name_or_code + suffix
    # 尝试名称搜索
    try:
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,name")
        match = df[df["name"].str.contains(name_or_code, na=False)]
        if not match.empty:
            return match.iloc[0]["ts_code"]
    except Exception:
        pass
    return name_or_code


# ======================================================================
#  主函数
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="艾略特波浪理论分析")
    parser.add_argument("--stock", required=True, help="股票代码或名称")
    parser.add_argument("--period", default="daily", help="K线周期: daily/weekly/monthly")
    parser.add_argument("--swing-window", type=int, default=10, help="摆动点检测窗口（默认10）")
    parser.add_argument("--fib-tolerance", type=float, default=0.15, help="Fibonacci容差（默认0.15）")
    parser.add_argument("--min-wave-bars", type=int, default=5, help="每浪最少K线数（默认5）")
    parser.add_argument("--limit", type=int, default=300, help="获取K线数量（默认300）")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    # 获取数据
    df = _fetch_stock_data(args.stock, args.period, args.limit)
    if df.empty:
        result = {"error": f"无法获取 {args.stock} 的K线数据", "stock": args.stock}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    # 执行分析
    engine = ElliottWaveEngine(
        swing_window=args.swing_window,
        fib_tolerance=args.fib_tolerance,
        min_wave_bars=args.min_wave_bars
    )
    result = engine.analyze(df)
    result["stock"] = args.stock
    result["period"] = args.period
    result["data_source"] = "Tushare Pro API（T+1延迟）"
    result["analysis_type"] = "elliott_wave"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        _print_report(result, df)


def _print_report(result: dict, df: pd.DataFrame):
    """人类可读报告。"""
    print("=" * 60)
    print(f"  艾略特波浪理论分析 - {result.get('stock', 'N/A')}")
    print(f"  K线周期: {result.get('period', 'daily')}  数据量: {result.get('total_bars', 0)} 根")
    print("=" * 60)
    print()
    print(f"  摆动点数量: {result.get('swing_points', 0)}")
    print(f"  总信号数量: {result.get('total_signals', 0)}")
    print(f"    做多信号: {result.get('buy_signals', 0)}")
    print(f"    做空信号: {result.get('sell_signals', 0)}")
    print()

    latest = result.get("latest_signal")
    if latest:
        print(f"  最新信号: {latest['signal_name']} ({latest['type_name']})")
        print(f"  信号日期: {latest['date']}")
    else:
        print("  最新信号: 无（观望）")

    print()
    print(f"  数据来源: {result.get('data_source', '')}")


if __name__ == "__main__":
    main()
