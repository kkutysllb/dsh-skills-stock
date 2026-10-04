"""
六因子选股引擎 — 价值 / 动量 / 质量 / 低波动 / 规模 / 成长

对齐 references/factor-methodology.md 的因子定义与子指标权重：
每个因子由若干子指标按权重加权合成百分位得分（0-100），
多因子综合得分 = Σ 因子权重 × 因子得分（默认等权 1/6，可自定义）。

输入约定（均以 index=日期、columns=股票代码 的 DataFrame 面板提供）：
  - 正向子指标面板直接用原始值（如 roe、mom_12_1）；
  - 负向子指标面板用取反后的值（如 -volatility、-beta、-leverage、-size），
    统一"值越高得分越高"，避免方向混乱。
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 子指标权重表（references/factor-methodology.md）
# ---------------------------------------------------------------------------

SUB_WEIGHTS: Dict[str, Dict[str, float]] = {
    "value": {"ep": 0.30, "bp": 0.20, "fcf_yield": 0.30, "ev_ebitda_inv": 0.20},
    "momentum": {"mom_12_1": 0.50, "rev_eps": 0.30, "turnover_neg": 0.20},
    "quality": {"roe": 0.30, "stability": 0.20, "leverage_neg": 0.25, "accrual": 0.25},
    "low_vol": {"volatility_neg": 0.40, "beta_neg": 0.30, "downside_neg": 0.30},
    "size": {"size_neg": 1.00},
    "growth": {"revenue_cagr": 0.30, "profit_cagr": 0.30, "margin_expansion": 0.20, "fwd_rev_growth": 0.20},
}

FACTORS = list(SUB_WEIGHTS.keys())

FACTOR_CN = {
    "value": "价值",
    "momentum": "动量",
    "quality": "质量",
    "low_vol": "低波动",
    "size": "规模",
    "growth": "成长",
}


# ---------------------------------------------------------------------------
# 预处理
# ---------------------------------------------------------------------------

def winsorize(df: pd.DataFrame, lower: float = 0.025, upper: float = 0.975) -> pd.DataFrame:
    """截面缩尾去极值（按每行 2.5/97.5 百分位）。"""
    out = df.copy()
    q_lo = out.quantile(lower, axis=1)
    q_hi = out.quantile(upper, axis=1)
    out = out.clip(lower=q_lo, upper=q_hi, axis=0)
    return out


def industry_neutralize(df: pd.DataFrame, industry_map: Dict[str, str]) -> pd.DataFrame:
    """行业中性化：按行业分组做截面 Z-score（行业均值/标准差），返回中性化面板。

    Parameters
    ----------
    df : 原始面板（index=日期, columns=代码）
    industry_map : {股票代码: 行业名}
    """
    if not industry_map:
        return df
    out = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)
    for dt in df.index:
        row = df.loc[dt]
        norm = pd.Series(np.nan, index=row.index, dtype=float)
        for industry in set(industry_map.values()):
            codes = [c for c in row.index if industry_map.get(c) == industry]
            if not codes:
                continue
            vals = row[codes].astype(float)
            mu, sd = vals.mean(), vals.std()
            if sd and not np.isnan(sd) and sd > 0:
                norm[codes] = (vals - mu) / sd
        out.loc[dt] = norm
    return out


def percentile_score(df: pd.DataFrame) -> pd.DataFrame:
    """截面百分位排名 → 0-100 分（值越大得分越高，跨行独立）。"""
    out = df.copy()
    for dt in df.index:
        row = df.loc[dt].dropna()
        if len(row) == 0:
            continue
        ranked = row.rank(method="average")
        out.loc[dt, row.index] = ranked / len(row) * 100.0
    return out


# ---------------------------------------------------------------------------
# 单因子得分
# ---------------------------------------------------------------------------

def factor_score(sub_panels: Dict[str, pd.DataFrame],
                 weights: Optional[Dict[str, float]] = None,
                 winsor: bool = True,
                 industry_map: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """合成单个因子得分。

    Parameters
    ----------
    sub_panels : {子指标名: 面板}（值越高越好，负向指标需预先取反）
    weights : {子指标名: 权重}，缺省使用 SUB_WEIGHTS 中对应因子权重
    """
    w = weights or {}
    total_w = sum(w.values())
    if total_w <= 0:
        raise ValueError("子指标权重和必须大于 0")
    weighted = []
    for name, panel in sub_panels.items():
        w_i = w.get(name)
        if not w_i:
            continue
        p = panel.copy()
        if winsor:
            p = winsorize(p)
        if industry_map:
            p = industry_neutralize(p, industry_map)
        weighted.append(percentile_score(p) * w_i)
    if not weighted:
        return pd.DataFrame()
    out = sum(weighted) / total_w
    return out.fillna(50.0)  # 缺失用中性分 50


def compute_six_factors(panels: Dict[str, pd.DataFrame],
                        industry_map: Optional[Dict[str, str]] = None) -> Dict[str, pd.DataFrame]:
    """从子指标面板集合计算六大因子得分。

    Parameters
    ----------
    panels : {子指标名: 面板}
        需包含 SUB_WEIGHTS 引用的全部子指标；缺失的子指标按权重 0 处理（其余重归一）。
    """
    scores: Dict[str, pd.DataFrame] = {}
    for factor, weights in SUB_WEIGHTS.items():
        available = {k: panels[k] for k in weights if k in panels}
        if not available:
            continue
        effective = {k: v for k, v in weights.items() if k in available}
        scores[factor] = factor_score(available, effective, industry_map=industry_map)
    return scores


# ---------------------------------------------------------------------------
# 多因子综合
# ---------------------------------------------------------------------------

def multifactor_score(factor_scores: Dict[str, pd.DataFrame],
                      weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """多因子综合得分 = Σ 因子权重 × 因子得分（默认等权 1/6）。

    Parameters
    ----------
    factor_scores : {因子名: 得分面板(0-100)}
    weights : {因子名: 权重}，缺省等权
    """
    if not factor_scores:
        return pd.DataFrame()
    if weights is None:
        w = {f: 1.0 / len(factor_scores) for f in factor_scores}
    else:
        w = {f: weights.get(f, 0.0) for f in factor_scores}
    total = sum(w.values())
    if total <= 0:
        raise ValueError("因子权重和必须大于 0")
    out = None
    for f, panel in factor_scores.items():
        term = panel.fillna(50.0) * (w.get(f, 0.0) / total)
        out = term if out is None else out.add(term, fill_value=0)
    return out if out is not None else pd.DataFrame()


def top_n(score_df: pd.DataFrame, n: int = 20, date: Optional[str] = None) -> pd.DataFrame:
    """取综合得分最高的 N 只（默认最新日期；传 date 指定 YYYY-MM-DD）。

    Returns
    -------
    DataFrame(index=日期, columns=['code','score'])，仅保留有数据的日子。
    """
    if score_df is None or score_df.empty:
        return pd.DataFrame(columns=["date", "code", "score"])
    if date is not None:
        if date not in score_df.index:
            return pd.DataFrame(columns=["date", "code", "score"])
        rows = [{"date": pd.Timestamp(date), "code": c, "score": v}
                for c, v in score_df.loc[date].dropna().nlargest(n).items()]
        return pd.DataFrame(rows)
    out = []
    for dt in score_df.index:
        top = score_df.loc[dt].dropna().nlargest(n)
        for code, v in top.items():
            out.append({"date": dt, "code": code, "score": round(v, 2)})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 构造 mock 面板：6 只股票 × 5 个交易日，各子指标
    np.random.seed(7)
    dates = pd.bdate_range("2024-01-01", periods=5)
    codes = [f"STOCK{i:02d}" for i in range(1, 7)]

    def mock_panel(base, spread):
        return pd.DataFrame(
            {c: base + spread * i for i, c in enumerate(codes)},
            index=dates,
        )

    panels = {
        "ep": mock_panel(2.0, 0.5),            # 价值：ep 越高越好
        "bp": mock_panel(1.0, 0.2),
        "fcf_yield": mock_panel(0.05, 0.01),
        "ev_ebitda_inv": mock_panel(0.1, 0.02),
        "mom_12_1": mock_panel(0.05, 0.02),    # 动量
        "rev_eps": mock_panel(0.02, 0.01),
        "turnover_neg": mock_panel(-0.1, 0.02),  # 负换手（低换手高分）
        "roe": mock_panel(10.0, 2.0),          # 质量
        "stability": mock_panel(0.8, 0.03),
        "leverage_neg": mock_panel(-0.3, 0.02),
        "accrual": mock_panel(1.0, 0.05),
        "volatility_neg": mock_panel(-0.25, 0.02),  # 低波动（负波动）
        "beta_neg": mock_panel(-1.1, 0.05),
        "downside_neg": mock_panel(-0.15, 0.01),
        "size_neg": mock_panel(-100.0, 10.0),   # 规模（负市值，越小越高分）
        "revenue_cagr": mock_panel(0.15, 0.03),  # 成长
        "profit_cagr": mock_panel(0.12, 0.03),
        "margin_expansion": mock_panel(0.01, 0.005),
        "fwd_rev_growth": mock_panel(0.15, 0.02),
    }

    six = compute_six_factors(panels)
    print("六因子得分（最新日）：")
    for f, panel in six.items():
        print(f"  {FACTOR_CN[f]:4s} {panel.iloc[-1].round(1).to_dict()}")
    composite = multifactor_score(six)
    print("综合得分（最新日）：", composite.iloc[-1].round(1).to_dict())
    print("Top3：")
    print(top_n(composite, 3).tail(3).to_string(index=False))
