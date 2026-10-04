#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
谐波形态（Harmonic Patterns）分析脚本

基于 Fibonacci 几何学派，识别 Gartley/Bat/Butterfly/Crab 等 XABCD 五点形态，
在 PRZ（潜在反转区）生成交易信号。

数据来源于 Tushare Pro API（T+1延迟）。

核心功能：
  - XABCD 五点形态识别
  - 4种经典谐波形态：Gartley、Bat、Butterfly、Crab
  - PRZ（潜在反转区）计算
  - 看涨/看跌形态方向判断

用法:
    python scripts/analysis-engine/analyze_harmonic_pattern.py --stock 600519.SH --json
    python scripts/analysis-engine/analyze_harmonic_pattern.py --stock 宁德时代 --swing-window 12 --json
"""

import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PROJECT_ROOT = os.path.dirname(_SKILL_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ======================================================================
#  谐波形态定义
# ======================================================================

PATTERNS = {
    "Gartley": {
        "b_retrace": (0.55, 0.68),
        "d_retrace": (0.72, 0.84),
        "bc_ratio": (0.382, 0.886),
        "cd_ratio": (1.27, 1.618),
        "description": "Gartley形态：AB回撤XA的0.618，D点在XA的0.786处",
    },
    "Bat": {
        "b_retrace": (0.33, 0.55),
        "d_retrace": (0.82, 0.94),
        "bc_ratio": (0.382, 0.886),
        "cd_ratio": (1.618, 2.618),
        "description": "Bat形态：AB回撤XA的0.382-0.5，D点在XA的0.886处",
    },
    "Butterfly": {
        "b_retrace": (0.72, 0.84),
        "d_retrace": (1.20, 1.38),
        "bc_ratio": (0.382, 0.886),
        "cd_ratio": (1.618, 2.618),
        "description": "Butterfly形态：AB回撤XA的0.786，D点超出X点（1.27 XA）",
    },
    "Crab": {
        "b_retrace": (0.33, 0.68),
        "d_retrace": (1.52, 1.72),
        "bc_ratio": (0.382, 0.886),
        "cd_ratio": (2.24, 3.618),
        "description": "Crab形态：D点最远延伸至XA的1.618处",
    },
}


# ======================================================================
#  谐波形态信号引擎
# ======================================================================

class HarmonicPatternEngine:
    """谐波形态信号引擎。

    检测 Gartley/Bat/Butterfly/Crab 等 XABCD 五点结构，
    在 PRZ（潜在反转区）生成交易信号。
    """

    def __init__(self, swing_window=10, tolerance=0.1):
        self.swing_window = swing_window
        self.tolerance = tolerance

    def _find_swings(self, high: pd.Series, low: pd.Series) -> List[Tuple]:
        """检测摆动高低点并合并为交替序列。"""
        full_window = self.swing_window * 2 + 1
        rolling_max = high.rolling(full_window, center=True).max()
        rolling_min = low.rolling(full_window, center=True).min()

        swing_high = high.where(high == rolling_max).dropna()
        swing_low = low.where(low == rolling_min).dropna()

        points = []
        for ts, price in swing_high.items():
            points.append((ts, float(price), "H"))
        for ts, price in swing_low.items():
            points.append((ts, float(price), "L"))
        points.sort(key=lambda x: x[0])

        # 去除连续同类型点
        merged = []
        for pt in points:
            if not merged or merged[-1][2] != pt[2]:
                merged.append(pt)
            else:
                if pt[2] == "H" and pt[1] > merged[-1][1]:
                    merged[-1] = pt
                elif pt[2] == "L" and pt[1] < merged[-1][1]:
                    merged[-1] = pt
        return merged

    def _in_range(self, value, lo, hi) -> bool:
        tol = self.tolerance
        return (lo - tol) <= value <= (hi + tol)

    def _detect_patterns(self, swings) -> List[Dict]:
        """在摆动序列中检测 XABCD 五点形态。"""
        results = []
        # 需要5个点：X, A, B, C, D
        for i in range(len(swings) - 4):
            x_ts, x_price, x_type = swings[i]
            a_ts, a_price, a_type = swings[i + 1]
            b_ts, b_price, b_type = swings[i + 2]
            c_ts, c_price, c_type = swings[i + 3]
            d_ts, d_price, d_type = swings[i + 4]

            # X和A必须不同类型，B和A同类型，C和B不同类型...
            if x_type == a_type or b_type != a_type or c_type != b_type or d_type != c_type:
                continue

            xa = abs(a_price - x_price)
            if xa == 0:
                continue

            ab = abs(b_price - a_price)
            bc = abs(c_price - b_price)
            cd = abs(d_price - c_price)
            ad = abs(d_price - a_price)

            b_retrace = ab / xa
            d_retrace = ad / xa
            bc_ratio = bc / ab if ab > 0 else 0
            cd_ratio = cd / bc if bc > 0 else 0

            # 判断方向
            is_bullish = (x_type == "H" and d_price < a_price)  # 看涨：D在底部

            for pattern_name, params in PATTERNS.items():
                if (self._in_range(b_retrace, *params["b_retrace"]) and
                    self._in_range(d_retrace, *params["d_retrace"]) and
                    self._in_range(bc_ratio, *params["bc_ratio"]) and
                    self._in_range(cd_ratio, *params["cd_ratio"])):

                    signal = 1 if is_bullish else -1
                    results.append({
                        "date": str(d_ts),
                        "pattern": pattern_name,
                        "direction": "看涨" if is_bullish else "看跌",
                        "signal": signal,
                        "signal_name": "做多" if signal == 1 else "做空",
                        "points": {
                            "X": {"date": str(x_ts), "price": round(x_price, 2)},
                            "A": {"date": str(a_ts), "price": round(a_price, 2)},
                            "B": {"date": str(b_ts), "price": round(b_price, 2)},
                            "C": {"date": str(c_ts), "price": round(c_price, 2)},
                            "D": {"date": str(d_ts), "price": round(d_price, 2)},
                        },
                        "ratios": {
                            "b_retrace": round(b_retrace, 3),
                            "d_retrace": round(d_retrace, 3),
                            "bc_ratio": round(bc_ratio, 3),
                            "cd_ratio": round(cd_ratio, 3),
                        },
                        "description": params["description"]
                    })
        return results

    def analyze(self, df: pd.DataFrame) -> Dict:
        """分析 DataFrame 中的谐波形态。

        Args:
            df: OHLCV DataFrame。

        Returns:
            分析结果字典。
        """
        swings = self._find_swings(df["high"], df["low"])
        patterns = self._detect_patterns(swings)

        # 按形态类型统计
        pattern_stats = {}
        for p in patterns:
            name = p["pattern"]
            if name not in pattern_stats:
                pattern_stats[name] = {"total": 0, "bullish": 0, "bearish": 0}
            pattern_stats[name]["total"] += 1
            if p["signal"] == 1:
                pattern_stats[name]["bullish"] += 1
            else:
                pattern_stats[name]["bearish"] += 1

        latest = patterns[-1] if patterns else None

        return {
            "total_bars": len(df),
            "swing_points": len(swings),
            "total_patterns": len(patterns),
            "pattern_stats": pattern_stats,
            "latest_pattern": latest,
            "patterns": patterns[-20:],  # 最近20个
            "parameters": {
                "swing_window": self.swing_window,
                "tolerance": self.tolerance
            }
        }


# ======================================================================
#  数据获取（复用）
# ======================================================================

def _fetch_stock_data(stock_code: str, period: str = "daily", limit: int = 300) -> pd.DataFrame:
    """从 Tushare 获取股票 K 线数据。"""
    try:
        from kk_common import get_finance_data_gateway
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN 环境变量未设置")
        pro = get_finance_data_gateway()

        if '.' not in stock_code:
            stock_code = _resolve_stock_code(stock_code, pro)

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
    except Exception as e:
        print(f"数据获取错误: {e}", file=sys.stderr)
        return pd.DataFrame()


def _resolve_stock_code(name_or_code: str, pro) -> str:
    if '.' in name_or_code:
        return name_or_code
    if name_or_code.isdigit() and len(name_or_code) == 6:
        suffix = ".SZ" if name_or_code.startswith(("0", "3")) else ".SH"
        return name_or_code + suffix
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
    parser = argparse.ArgumentParser(description="谐波形态分析")
    parser.add_argument("--stock", required=True, help="股票代码或名称")
    parser.add_argument("--swing-window", type=int, default=10, help="摆动点检测窗口（默认10）")
    parser.add_argument("--tolerance", type=float, default=0.1, help="Fibonacci比率容差（默认0.1）")
    parser.add_argument("--limit", type=int, default=300, help="获取K线数量（默认300）")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    df = _fetch_stock_data(args.stock, "daily", args.limit)
    if df.empty:
        result = {"error": f"无法获取 {args.stock} 的K线数据", "stock": args.stock}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    engine = HarmonicPatternEngine(
        swing_window=args.swing_window,
        tolerance=args.tolerance
    )
    result = engine.analyze(df)
    result["stock"] = args.stock
    result["data_source"] = "Tushare Pro API（T+1延迟）"
    result["analysis_type"] = "harmonic_pattern"

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        _print_report(result)


def _print_report(result: dict):
    print("=" * 60)
    print(f"  谐波形态分析 - {result.get('stock', 'N/A')}")
    print(f"  数据量: {result.get('total_bars', 0)} 根K线")
    print("=" * 60)
    print()
    print(f"  摆动点数量: {result.get('swing_points', 0)}")
    print(f"  识别形态总数: {result.get('total_patterns', 0)}")
    print()

    stats = result.get("pattern_stats", {})
    if stats:
        print("  形态统计:")
        for name, s in stats.items():
            print(f"    {name}: {s['total']}次 (看涨{s['bullish']} / 看跌{s['bearish']})")
    print()

    latest = result.get("latest_pattern")
    if latest:
        print(f"  最新形态: {latest['pattern']} ({latest['direction']})")
        print(f"  信号方向: {latest['signal_name']}")
        print(f"  信号日期: {latest['date']}")
        print(f"  D点价格: {latest['points']['D']['price']}")
    else:
        print("  最新形态: 无识别到的形态")

    print()
    print(f"  数据来源: {result.get('data_source', '')}")


if __name__ == "__main__":
    main()
