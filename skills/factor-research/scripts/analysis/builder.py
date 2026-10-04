"""
因子面板构造器 — 原始行情/财务 → 因子矩阵与前瞻收益矩阵

设计原则（防前视偏差）：
  - 收益矩阵：t 日的因子值对应持有 t+1 ~ t+N 的收益，
    即收益 = close[t+N] / close[t] - 1（shift 对齐），禁止使用 t 日收益；
  - 动量等用历史数据计算（skip 最近 1 月），避免混入短期反转；
  - 所有函数输入为 pandas 面板（index=日期, columns=股票代码），纯计算、无网络。

用法示例：
    ret = forward_returns(close, period=20)       # 收益矩阵（对齐因子日）
    mom = momentum_panel(close, skip=1, window=12)  # 12-1 月动量
    vol_neg = -volatility_panel(close, window=252)  # 低波动子指标（取反）
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def forward_returns(close: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """前瞻 N 日收益：t 日收益 = close[t+N]/close[t] - 1。

    结果 index 与 close 对齐，最后 period 行收益为 NaN（数据不足）。
    """
    out = close.shift(-period) / close - 1.0
    return out


def daily_returns(close: pd.DataFrame) -> pd.DataFrame:
    """日收益率（pct_change）。"""
    return close.pct_change()


def momentum_panel(close: pd.DataFrame, skip: int = 1, window: int = 12) -> pd.DataFrame:
    """价格动量（跳过最近 skip 期，回看 window 期）：close[t-skip] / close[t-skip-window] - 1。"""
    return close.shift(skip) / close.shift(skip + window) - 1.0


def volatility_panel(close: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """年化已实现波动率（日收益 std × sqrt(252)）。"""
    ret = daily_returns(close)
    vol = ret.rolling(window, min_periods=20).std() * np.sqrt(252)
    return vol


def beta_panel(close: pd.DataFrame, benchmark: pd.Series, window: int = 504) -> pd.DataFrame:
    """CAPM Beta：个股日收益相对基准的滚动协方差/方差。

    Parameters
    ----------
    benchmark : 基准指数收盘价 Series（index=日期）
    """
    bench_ret = benchmark.pct_change()
    stock_ret = daily_returns(close)
    aligned = pd.concat([bench_ret.rename("bench")], axis=1).join(stock_ret, how="inner")
    bench_col = aligned["bench"]
    out = pd.DataFrame(index=aligned.index, columns=close.columns, dtype=float)
    for col in close.columns:
        cov = aligned[col].rolling(window, min_periods=60).cov(bench_col)
        var = bench_col.rolling(window, min_periods=60).var()
        out[col] = cov / var
    return out


def downside_deviation(close: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """下行偏差（仅负收益的半标准差）。"""
    ret = daily_returns(close)
    neg = ret.where(ret < 0, 0.0)
    dd = (neg.pow(2).rolling(window, min_periods=20).mean()).pow(0.5) * np.sqrt(252)
    return dd


def turnover_neg(close: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """负换手率代理：以收益率绝对值的滚动均值近似活跃度，取负（低活跃高分）。"""
    ret = daily_returns(close)
    act = ret.abs().rolling(window, min_periods=20).mean()
    return -act


def build_core_factors(close: pd.DataFrame, benchmark: Optional[pd.Series] = None,
                       period: int = 20) -> dict:
    """一键构造常用因子面板（供 IC/IR 分析直接使用）。

    Returns
    -------
    {子指标名: 面板}，可直接喂给 multifactor.compute_six_factors；
    另附 forward_returns（收益矩阵）。
    """
    mom = momentum_panel(close, skip=1, window=12)
    vol = volatility_panel(close)
    dd = downside_deviation(close)
    size_neg = -pd.DataFrame(np.log(close.abs() + 1e-9), index=close.index, columns=close.columns)

    panels = {
        # 动量
        "mom_12_1": mom,
        "turnover_neg": turnover_neg(close),
        # 低波动（负向取反）
        "volatility_neg": -vol,
        "downside_neg": -dd,
        # 规模（负市值，越小越高分）
        "size_neg": size_neg,
    }
    if benchmark is not None:
        panels["beta_neg"] = -beta_panel(close, benchmark)
    panels["_returns"] = forward_returns(close, period)
    return panels


if __name__ == "__main__":
    np.random.seed(3)
    dates = pd.bdate_range("2023-01-01", periods=400)
    codes = [f"EQ{i:02d}" for i in range(1, 5)]
    # 模拟随机游走价格
    rets = np.random.normal(0.0005, 0.02, (len(dates), len(codes)))
    prices = 100 * np.exp(np.cumsum(rets, axis=0))
    close = pd.DataFrame(prices, index=dates, columns=codes)
    bench = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.01, len(dates)))),
                      index=dates, name="hs300")

    panels = build_core_factors(close, bench, period=20)
    ret = panels.pop("_returns")
    print("构造面板:", list(panels.keys()))
    print("动量(最新日):", panels["mom_12_1"].iloc[-1].round(4).to_dict())
    print("波动率取反(最新日):", panels["volatility_neg"].iloc[-1].round(4).to_dict())
    print("Beta取反(最新日):", panels["beta_neg"].iloc[-1].round(4).to_dict())
    print("前瞻20日收益: NaN 行数 =", ret.isna().sum().sum(), "/", ret.size)
