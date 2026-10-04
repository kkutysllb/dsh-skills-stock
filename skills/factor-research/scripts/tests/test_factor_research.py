"""factor-research 技能包测试 — 覆盖六个模块 + CLI 全子命令。"""

import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

ANALYSIS_DIR = os.path.join(os.path.dirname(__file__), "..", "analysis")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ANALYSIS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from factor_engine import (  # noqa: E402
    compute_ic_series,
    factor_combination,
    ic_summary,
    quantile_backtest,
)
from multifactor import (  # noqa: E402
    compute_six_factors,
    multifactor_score,
    percentile_score,
    top_n,
    winsorize,
)
from factor_timing import (  # noqa: E402
    CYCLE_WEIGHTS,
    crowding_analysis,
    detect_cycle,
    timing_weights,
)
from small_cap_growth import (  # noqa: E402
    market_cap_band,
    pass_growth_gate,
    quality_score,
    screen,
)
from builder import (  # noqa: E402
    build_core_factors,
    forward_returns,
    momentum_panel,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _mk_panel(base, spread, dates, codes):
    return pd.DataFrame({c: base + spread * i for i, c in enumerate(codes)}, index=dates)


@pytest.fixture
def panels():
    np.random.seed(7)
    dates = pd.bdate_range("2024-01-01", periods=30)
    codes = [f"EQ{i:02d}" for i in range(1, 7)]
    return {
        "ep": _mk_panel(2.0, 0.5, dates, codes),
        "bp": _mk_panel(1.0, 0.2, dates, codes),
        "fcf_yield": _mk_panel(0.05, 0.01, dates, codes),
        "ev_ebitda_inv": _mk_panel(0.1, 0.02, dates, codes),
        "mom_12_1": _mk_panel(0.05, 0.02, dates, codes),
        "rev_eps": _mk_panel(0.02, 0.01, dates, codes),
        "turnover_neg": _mk_panel(-0.1, 0.02, dates, codes),
        "roe": _mk_panel(10.0, 2.0, dates, codes),
        "stability": _mk_panel(0.8, 0.03, dates, codes),
        "leverage_neg": _mk_panel(-0.3, 0.02, dates, codes),
        "accrual": _mk_panel(1.0, 0.05, dates, codes),
        "volatility_neg": _mk_panel(-0.25, 0.02, dates, codes),
        "beta_neg": _mk_panel(-1.1, 0.05, dates, codes),
        "downside_neg": _mk_panel(-0.15, 0.01, dates, codes),
        "size_neg": _mk_panel(-100.0, 10.0, dates, codes),
        "revenue_cagr": _mk_panel(0.15, 0.03, dates, codes),
        "profit_cagr": _mk_panel(0.12, 0.03, dates, codes),
        "margin_expansion": _mk_panel(0.01, 0.005, dates, codes),
        "fwd_rev_growth": _mk_panel(0.15, 0.02, dates, codes),
    }


@pytest.fixture
def close():
    np.random.seed(3)
    dates = pd.bdate_range("2023-01-01", periods=400)
    codes = [f"EQ{i:02d}" for i in range(1, 5)]
    rets = np.random.normal(0.0005, 0.02, (len(dates), len(codes)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=codes)


# ---------------------------------------------------------------------------
# factor_engine — IC/IR / 分层回测 / 组合
# ---------------------------------------------------------------------------

def test_compute_ic_series_positive_for_rank_predictive_factor(panels):
    """构造与未来收益正相关的因子 → IC 应为正。"""
    dates = pd.bdate_range("2024-01-01", periods=30)
    codes = [f"EQ{i:02d}" for i in range(1, 7)]
    factor = _mk_panel(1.0, 0.5, dates, codes)          # EQ06 因子值最高
    returns = pd.DataFrame(index=dates, columns=codes)
    for dt in dates:
        returns.loc[dt] = [0.01 + 0.02 * i for i in range(6)]  # 收益与因子正相关
    ic = compute_ic_series(factor, returns)
    assert ic["ic"].dropna().mean() > 0


def test_ic_summary_fields(panels):
    dates = pd.bdate_range("2024-01-01", periods=30)
    codes = [f"EQ{i:02d}" for i in range(1, 7)]
    factor = _mk_panel(1.0, 0.5, dates, codes)
    returns = pd.DataFrame(index=dates, columns=codes)
    for dt in dates:
        returns.loc[dt] = [0.01 + 0.02 * i for i in range(6)]
    summ = ic_summary(compute_ic_series(factor, returns))
    assert {"ic_mean", "ir", "ic_positive_pct", "n_periods", "interpretation"} <= set(summ)


def test_quantile_backtest_monotonic(panels):
    """因子越高收益越高 → 分层回测收益应单调递增。"""
    dates = pd.bdate_range("2024-01-01", periods=30)
    codes = [f"EQ{i:02d}" for i in range(1, 11)]
    factor = _mk_panel(1.0, 1.0, dates, codes)
    returns = pd.DataFrame(index=dates, columns=codes)
    for dt in dates:
        returns.loc[dt] = [0.005 + 0.005 * i for i in range(10)]
    bt = quantile_backtest(factor, returns, n_groups=5)
    stats = bt["group_stats"]
    totals = [s["total_return"] for s in stats]
    assert totals == sorted(totals)


def test_factor_combination_ic_weight_explicit(panels):
    """ic_weight 显式权重应改变组合结果（不等于等权）。"""
    dates = pd.bdate_range("2024-01-01", periods=10)
    codes = [f"EQ{i:02d}" for i in range(1, 5)]
    f1 = _mk_panel(1.0, 1.0, dates, codes)
    f2 = _mk_panel(10.0, -1.0, dates, codes)  # 与 f1 方向相反
    equal = factor_combination([f1, f2], method="equal_weight")
    icw = factor_combination([f1, f2], method="ic_weight", weights=[1.0, 0.0])
    assert not equal.iloc[-1].equals(icw.iloc[-1])
    # 权重 [1,0] → 组合等于 f1 的 Z-score
    assert np.allclose(icw.iloc[-1].values, factor_combination([f1, f2], "equal_weight").iloc[-1].values * 0 + (
        (f1.iloc[-1] - f1.iloc[-1].mean()) / f1.iloc[-1].std()).values)


def test_factor_combination_orthogonal_runs(panels):
    dates = pd.bdate_range("2024-01-01", periods=10)
    codes = [f"EQ{i:02d}" for i in range(1, 5)]
    f1 = _mk_panel(1.0, 1.0, dates, codes)
    f2 = _mk_panel(2.0, 0.5, dates, codes)
    out = factor_combination([f1, f2], method="orthogonal")
    assert len(out) == len(dates)


# ---------------------------------------------------------------------------
# multifactor — 六因子
# ---------------------------------------------------------------------------

def test_six_factors_ordering(panels):
    """所有子指标同向递增 → 六因子得分应单调，EQ06 最高、EQ01 最低。"""
    six = compute_six_factors(panels)
    assert set(six) == {"value", "momentum", "quality", "low_vol", "size", "growth"}
    for f, panel in six.items():
        last = panel.iloc[-1]
        assert last["EQ06"] == 100.0
        assert last["EQ01"] == pytest.approx(100.0 / 6, abs=0.1)


def test_multifactor_score_weights(panels):
    six = compute_six_factors(panels)
    equal = multifactor_score(six)
    w = {"value": 1.0, "momentum": 0.0, "quality": 0.0, "low_vol": 0.0, "size": 0.0, "growth": 0.0}
    value_only = multifactor_score(six, weights=w)
    assert value_only.iloc[-1].equals(six["value"].iloc[-1])


def test_top_n_shape(panels):
    six = compute_six_factors(panels)
    composite = multifactor_score(six)
    top = top_n(composite, n=3)
    assert len(top) == len(composite) * 3
    assert top["score"].max() <= 100


def test_winsorize_clips_extremes():
    df = pd.DataFrame({"a": [1, 2, 3, 100], "b": [1, 2, 3, 4]}, index=pd.bdate_range("2024-01-01", periods=4))
    out = winsorize(df)
    assert out["a"].max() < 100


def test_percentile_score_bounds():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]}, index=pd.bdate_range("2024-01-01", periods=3))
    out = percentile_score(df)
    assert (out >= 0).all().all() and (out <= 100).all().all()


# ---------------------------------------------------------------------------
# factor_timing — 择时
# ---------------------------------------------------------------------------

def test_timing_weights_all_cycles_sum_to_one():
    for cycle in CYCLE_WEIGHTS:
        w = timing_weights(cycle)
        assert abs(sum(w.values()) - 1.0) < 1e-3
        assert set(w) == {"value", "momentum", "quality", "low_vol", "size", "growth"}


def test_timing_recovery_favors_small_growth():
    w = timing_weights("recovery_early")
    assert w["size"] > w["low_vol"]
    assert w["growth"] > w["low_vol"]


def test_detect_cycle_mapping():
    assert detect_cycle(0.8, 0.2, -0.1)["cycle"] == "expansion_mid"
    assert detect_cycle(-0.5, -0.2, -0.3)["cycle"] == "downturn"


def test_crowding_analysis_levels():
    np.random.seed(11)
    dates = pd.bdate_range("2024-01-01", periods=120)
    trend = np.concatenate([np.random.normal(0.001, 0.01, 80), np.random.normal(-0.002, 0.01, 40)])
    rets = pd.DataFrame({"momentum": trend, "quality": np.random.normal(0.0008, 0.008, 120)}, index=dates)
    out = crowding_analysis(rets)
    assert "momentum" in out and "quality" in out
    assert out["momentum"]["crowding"] in ("高", "中", "低")


# ---------------------------------------------------------------------------
# small_cap_growth — 小盘成长
# ---------------------------------------------------------------------------

def test_market_cap_band_bounds():
    assert market_cap_band(80) == "小盘"
    assert market_cap_band(15) is None
    assert market_cap_band(300) is None
    assert market_cap_band(30) == "微盘"


def test_growth_gate():
    assert pass_growth_gate(25.0, None)
    assert pass_growth_gate(15.0, 30.0)   # 近2年 > 25% 也通过
    assert not pass_growth_gate(15.0, 20.0)


def test_quality_score_rating():
    good = quality_score({"revenue_growth_pct": 40, "margin_delta": 2.0, "cash_ratio_pct": 110,
                          "debt_ratio": 40, "holder_pct": 45, "moat_score": 9, "rnd_score": 8, "peg": 0.7})
    assert good["total"] >= 80
    assert "★★★★★" in good["rating"]


def test_screen_filters():
    df = pd.DataFrame([
        {"total_mv_yi": 80.0, "revenue_cagr3_pct": 30.0, "revenue_growth_pct": 35.0,
         "margin_delta": 1.5, "cash_ratio_pct": 90.0, "debt_ratio": 45.0, "holder_pct": 30.0,
         "moat_score": 8, "rnd_score": 7, "peg": 0.9},
        {"total_mv_yi": 15.0, "revenue_cagr3_pct": 35.0, "revenue_growth_pct": 40.0,
         "margin_delta": 2.0, "cash_ratio_pct": 110.0, "debt_ratio": 40.0, "holder_pct": 45.0,
         "moat_score": 9, "rnd_score": 8, "peg": 0.7},
        {"total_mv_yi": 300.0, "revenue_cagr3_pct": 25.0, "revenue_growth_pct": 25.0,
         "margin_delta": 0.5, "cash_ratio_pct": 85.0, "debt_ratio": 50.0, "holder_pct": 25.0,
         "moat_score": 6, "rnd_score": 6, "peg": 1.1},
    ], index=["GOOD", "MICRO", "BIG"])
    out = screen(df)
    assert set(out["code"]) == {"GOOD"}  # 微盘/超大盘被硬门槛排除


# ---------------------------------------------------------------------------
# builder — 面板构造（前视偏差防护）
# ---------------------------------------------------------------------------

def test_forward_returns_no_lookahead(close):
    ret = forward_returns(close, period=20)
    # 最后 20 行应为 NaN（无未来数据）
    assert ret.iloc[-20:].isna().all().all()
    # 非尾部行有值
    assert ret.iloc[0].notna().all()


def test_momentum_uses_history_only(close):
    mom = momentum_panel(close, skip=1, window=12)
    assert mom.isna().iloc[:13].all().all()  # 前 13 行无足够历史


def test_build_core_factors_keys(close):
    np.random.seed(9)
    bench = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.01, len(close)))),
                      index=close.index)
    panels = build_core_factors(close, bench, period=20)
    assert {"mom_12_1", "turnover_neg", "volatility_neg", "downside_neg", "size_neg", "beta_neg"} <= set(panels)
    ret = panels.pop("_returns")
    assert ret.shape == close.shape


# ---------------------------------------------------------------------------
# CLI 端到端
# ---------------------------------------------------------------------------

def _run_cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = SCRIPTS_DIR + os.pathsep + ANALYSIS_DIR + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "cli.py"), *args],
        capture_output=True, text=True, env=env,
    )
    return proc


def test_cli_timing_cycle(tmp_path):
    proc = _run_cli("timing", "--cycle", "recovery_early")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["cycle"] == "recovery_early"
    assert abs(sum(out["weights"].values()) - 1.0) < 1e-3


def test_cli_timing_macro_detect(tmp_path):
    proc = _run_cli("timing", "--gdp-trend", "0.8", "--inflation", "0.2", "--interest-trend", "-0.1")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["cycle"] == "expansion_mid"


def test_cli_build(tmp_path, close):
    close_csv = tmp_path / "close.csv"
    close.to_csv(close_csv)
    outdir = tmp_path / "panels"
    proc = _run_cli("build", "--close", str(close_csv), "--period", "20", "--outdir", str(outdir))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert "mom_12_1" in out["panels"]
    assert (outdir / "mom_12_1.csv").exists()


def test_cli_multifactor(tmp_path, panels):
    panels_dir = tmp_path / "panels"
    panels_dir.mkdir()
    for name, panel in panels.items():
        panel.to_csv(panels_dir / f"{name}.csv")
    proc = _run_cli("multifactor", "--panels-dir", str(panels_dir), "--top-n", "3")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert set(out["factors_computed"]) == {"value", "momentum", "quality", "low_vol", "size", "growth"}
    assert len(out["composite_latest_top"]) == 3
    assert out["composite_latest_top"][0]["code"] == "EQ06"


def test_cli_smallcap(tmp_path):
    features = tmp_path / "features.csv"
    features.write_text(
        "code,total_mv_yi,revenue_cagr3_pct,revenue_growth_pct,margin_delta,cash_ratio_pct,debt_ratio,holder_pct,moat_score,rnd_score,peg\n"
        "GOOD,80,30,35,1.5,90,45,30,8,7,0.9\n"
        "MICRO,15,35,40,2.0,110,40,45,9,8,0.7\n"
        "BIG,300,25,25,0.5,85,50,25,6,6,1.1\n",
        encoding="utf-8",
    )
    proc = _run_cli("smallcap", "--input", str(features))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["passed"] == 1
    assert out["top"][0]["code"] == "GOOD"


def test_cli_combine(tmp_path):
    dates = pd.bdate_range("2024-01-01", periods=10)
    codes = [f"EQ{i:02d}" for i in range(1, 5)]
    f1 = _mk_panel(1.0, 1.0, dates, codes)
    f2 = _mk_panel(10.0, -1.0, dates, codes)
    p1, p2 = tmp_path / "f1.csv", tmp_path / "f2.csv"
    f1.to_csv(p1)
    f2.to_csv(p2)
    proc = _run_cli("combine", "--factor-csv", str(p1), str(p2),
                    "--method", "ic_weight", "--weights-json", "[1.0, 0.0]")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["method"] == "ic_weight"
    assert out["n_factors"] == 2


def test_cli_help(tmp_path):
    proc = _run_cli("help")
    assert proc.returncode == 0
    assert "multifactor" in proc.stdout
    assert "smallcap" in proc.stdout
