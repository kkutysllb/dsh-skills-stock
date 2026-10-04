"""
因子研究引擎 — IC/IR 分析、分层回测、因子组合

功能:
  - 单因子有效性检验（IC/IR 统计）
  - 分层回测（N组等权持有）
  - 多因子组合（等权/IC加权/正交化）
  - 因子衰减分析
"""

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd


def load_csv(path):
    """加载 CSV（index=date, columns=codes）"""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def compute_ic_series(factor_df, return_df):
    """计算每日截面 IC（Spearman rank 相关系数）"""
    ic_list = []
    dates = factor_df.index.intersection(return_df.index)
    for dt in dates:
        f = factor_df.loc[dt].dropna()
        r = return_df.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < 5:
            ic_list.append({"date": str(dt.date()), "ic": None, "n": len(common)})
            continue
        ic_val = f[common].corr(r[common], method="spearman")
        ic_list.append({"date": str(dt.date()), "ic": round(ic_val, 6), "n": len(common)})
    return pd.DataFrame(ic_list)


def ic_summary(ic_df):
    """IC 统计摘要"""
    valid = ic_df["ic"].dropna()
    if len(valid) == 0:
        return {"error": "无有效 IC 数据"}
    ic_mean = valid.mean()
    ic_std = valid.std()
    ir = ic_mean / ic_std if ic_std != 0 else 0
    pct_positive = (valid > 0).sum() / len(valid) * 100
    return {
        "ic_mean": round(ic_mean, 6),
        "ic_std": round(ic_std, 6),
        "ir": round(ir, 4),
        "ic_positive_pct": round(pct_positive, 2),
        "n_periods": len(valid),
        "interpretation": _interpret_ic(ic_mean, ir, pct_positive),
    }


def _interpret_ic(ic_mean, ir, pct_pos):
    """IC 解释"""
    parts = []
    if abs(ic_mean) > 0.10:
        parts.append("IC异常高，请检查前视偏差")
    elif abs(ic_mean) > 0.05:
        parts.append("因子具有较强预测力")
    elif abs(ic_mean) > 0.03:
        parts.append("因子具有基本预测力")
    else:
        parts.append("因子预测力较弱")
    if abs(ir) > 1.0:
        parts.append("IR极强（非常罕见）")
    elif abs(ir) > 0.5:
        parts.append("IR较好，因子稳定有效")
    else:
        parts.append("IR偏低，因子不够稳定")
    if pct_pos > 55:
        parts.append("方向稳定")
    elif pct_pos < 50:
        parts.append("方向不稳定")
    return "; ".join(parts)


def quantile_backtest(factor_df, return_df, n_groups=5):
    """分层回测：按因子值分组等权持有"""
    dates = factor_df.index.intersection(return_df.index)
    if len(dates) == 0:
        return {"error": "因子和收益日期无交集"}

    group_equity = {f"group_{g+1}": [1.0] for g in range(n_groups)}
    group_stats = []

    for dt in dates:
        f = factor_df.loc[dt].dropna()
        r = return_df.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < n_groups:
            for g in range(n_groups):
                group_equity[f"group_{g+1}"].append(group_equity[f"group_{g+1}"][-1])
            continue
        ranked = f[common].rank(method="average")
        total = len(ranked)
        for g in range(n_groups):
            lo = int(total * g / n_groups) + 1
            hi = int(total * (g + 1) / n_groups)
            mask = (ranked >= lo) & (ranked <= hi)
            if mask.sum() > 0:
                group_ret = r[common][mask].mean()
            else:
                group_ret = 0
            prev = group_equity[f"group_{g+1}"][-1]
            group_equity[f"group_{g+1}"].append(prev * (1 + group_ret))

    # 统计
    for g in range(n_groups):
        key = f"group_{g+1}"
        vals = group_equity[key][1:]  # skip initial 1.0
        final = vals[-1] if vals else 1.0
        group_stats.append({
            "group": key,
            "final_nav": round(final, 4),
            "total_return": round((final - 1) * 100, 2),
        })

    # 多空
    if len(group_stats) >= 2:
        ls_spread = round((group_stats[-1]["final_nav"] - group_stats[0]["final_nav"]) * 100, 2)
    else:
        ls_spread = 0

    return {
        "n_groups": n_groups,
        "n_dates": len(dates),
        "group_stats": group_stats,
        "long_short_spread_pct": ls_spread,
        "group_equity_dates": [str(d.date()) for d in dates],
    }


def factor_combination(factor_dfs, method="equal_weight", weights=None):
    """
    多因子组合
    method: equal_weight / ic_weight / orthogonal
    factor_dfs: list of DataFrames (same shape)
    weights: ic_weight 时必传——各因子 IC 加权系数（list 与 factor_dfs 对齐，
             或 dict {因子名: 权重}）；等权/正交化时可选。
    """
    if not factor_dfs:
        return {"error": "无因子数据"}

    # Z-score 标准化
    z_factors = []
    for df in factor_dfs:
        z = df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)
        z_factors.append(z.fillna(0))

    if method == "equal_weight":
        composite = sum(z_factors) / len(z_factors)
    elif method == "ic_weight":
        # 显式 IC 加权：权重缺失时回退等权并给出提示
        if weights is None:
            w = [1.0 / len(z_factors)] * len(z_factors)
        elif isinstance(weights, (list, tuple)):
            w = list(weights)
        else:  # dict：按 index 取值，缺省等权
            w = [weights.get(i, 1.0 / len(z_factors)) for i in range(len(z_factors))]
        if len(w) != len(z_factors):
            return {"error": f"IC 权重数量 {len(w)} 与因子数量 {len(z_factors)} 不一致"}
        total_w = sum(w)
        if total_w <= 0:
            return {"error": "IC 权重和必须大于 0"}
        composite = sum(z_factors[i] * (w[i] / total_w) for i in range(len(z_factors)))
    elif method == "orthogonal":
        # Schmidt 正交化
        ortho = [z_factors[0]]
        for i in range(1, len(z_factors)):
            residual = z_factors[i].copy()
            for prev in ortho:
                dot = (residual * prev).sum(axis=1)
                norm = (prev ** 2).sum(axis=1).replace(0, 1)
                proj = prev.mul(dot / norm, axis=0)
                residual = residual - proj
            ortho.append(residual.fillna(0))
        composite = sum(ortho) / len(ortho)
    else:
        return {"error": f"未知组合方法: {method}"}

    return composite


def save_results(output_dir, ic_df, ic_sum, bt_result):
    """保存分析结果"""
    os.makedirs(output_dir, exist_ok=True)
    ic_df.to_csv(os.path.join(output_dir, "ic_series.csv"), index=False)
    with open(os.path.join(output_dir, "ic_summary.json"), "w") as f:
        json.dump(ic_sum, f, indent=2, ensure_ascii=False)
    with open(os.path.join(output_dir, "backtest_result.json"), "w") as f:
        json.dump(bt_result, f, indent=2, ensure_ascii=False)
    return {
        "output_dir": output_dir,
        "files": ["ic_series.csv", "ic_summary.json", "backtest_result.json"],
    }
