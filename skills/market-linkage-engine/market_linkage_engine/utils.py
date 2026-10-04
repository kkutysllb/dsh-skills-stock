"""
市场联动分析引擎 — 通用工具函数

提供所有分析器共用的格式化、信号判定、评分工具。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Iterable

import pandas as pd


def yi(value: float) -> str:
    """元 → 亿元（保留 1 位小数）。

    Use this when the input is in **元** (yuan). For data already in 亿元
    (e.g. Tushare moneyflow_hsgt.north_money), use yi_from_yi() instead.
    """
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) / 1e8:.1f}亿"


def yi_from_yi(value: float) -> str:
    """数值本身已是亿元 → 直接渲染为 'N亿'（保留 1 位小数）。

    Tushare 部分接口（moneyflow_hsgt 的 north_money/south_money/hgt/sgt/
    ggt_ss/ggt_sz）直接返回亿元单位的数值，调用方不需要再除以 1e8。
    """
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1f}亿"


def yi_from_wan(value: float) -> str:
    """万元 → 亿元（保留 1 位小数）。

    Tushare moneyflow / moneyflow_dc / daily_basic.total_mv / circ_mv 等
    接口的金额字段返回的是万元单位，调用方需要 /1e4 转为亿元。
    """
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) / 1e4:.1f}亿"


def wan(value: float) -> str:
    """元 → 万元（保留 0 位小数）。"""
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) / 1e4:.0f}万"


def pct_str(value: float, base: Optional[float] = None, decimals: int = 2) -> str:
    """百分比字符串，自动加正号。"""
    if value is None or pd.isna(value):
        return "-"
    if base is not None and base != 0:
        value = value / base * 100
    sign = "+" if value > 0 else ("" if value < 0 else "")
    return f"{sign}{value:.{decimals}f}%"


def signal_cn(value: float, positive_label: str = "偏多", negative_label: str = "偏空",
              neutral_label: str = "中性") -> str:
    """根据正负值给出中文信号。"""
    if value is None or pd.isna(value):
        return neutral_label
    if value > 0:
        return positive_label
    if value < 0:
        return negative_label
    return neutral_label


def score_bar(score: int, total: int = 100) -> str:
    """绘制评分进度条 🔥。"""
    filled = int(round(score / total * 10))
    return "🔥" * filled + "·" * (10 - filled) + f" {score}/{total}"


def md_table(df: pd.DataFrame, columns: Optional[Iterable] = None,
             formatters: Optional[dict] = None, index: bool = False) -> str:
    """DataFrame → Markdown 表格（支持列选择 + 列格式化）。"""
    if df is None or len(df) == 0:
        return "_无数据_\n"
    if columns is not None:
        df = df[list(columns)]
    df = df.copy()
    if formatters:
        for col, fn in formatters.items():
            if col in df.columns:
                df[col] = df[col].apply(fn)
    return df.to_markdown(index=index)


def latest_trade_date(fetcher) -> Optional[str]:
    """获取最近一个交易日（通过 hsgt/沪深港通数据反推，避免依赖 trade_cal 权限）。"""
    try:
        df = fetcher.fetch_northbound(days=5)
        if len(df) and "trade_date" in df.columns:
            return str(df["trade_date"].max().strftime("%Y%m%d"))
    except Exception:
        pass
    return datetime.now().strftime("%Y%m%d")


def n_trade_dates_ago(fetcher, n: int) -> Optional[str]:
    """获取 n 个交易日前的日期。"""
    try:
        df = fetcher.fetch_northbound(days=n * 2 + 10)
        if len(df) and "trade_date" in df.columns:
            dates = sorted(df["trade_date"].unique())
            if len(dates) >= n:
                return str(dates[-n].strftime("%Y%m%d"))
    except Exception:
        pass
    return None


def safe_div(a: Optional[float], b: Optional[float], default: float = 0.0) -> float:
    """安全除法。"""
    if a is None or b is None or b == 0:
        return default
    return float(a) / float(b)
