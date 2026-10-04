#!/usr/bin/env python3
"""
factor-research CLI — 量化因子研究统一入口

支持三种模式:
  analyze  — IC/IR 分析 + 分层回测
  filter   — 基本面因子筛选（PE/PB/ROE）
  help     — 显示帮助

用法:
  python cli.py analyze --factor-csv <path> --return-csv <path> --output-dir <path> [--n-groups 5]
  python cli.py filter  --codes 000001.SZ,600036.SH --pe-max 20 --pb-max 3 --roe-min 8
  python cli.py help
"""
import argparse
import json
import os
import sys

import pandas as pd

# 添加 analysis 目录到 path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.join(SCRIPT_DIR, "analysis")
sys.path.insert(0, ANALYSIS_DIR)


def cmd_analyze(args):
    """IC/IR 分析 + 分层回测"""
    import pandas as pd
    from factor_engine import load_csv, compute_ic_series, ic_summary, quantile_backtest, save_results

    if not os.path.isfile(args.factor_csv):
        print(json.dumps({"error": f"因子文件不存在: {args.factor_csv}"}))
        sys.exit(1)
    if not os.path.isfile(args.return_csv):
        print(json.dumps({"error": f"收益文件不存在: {args.return_csv}"}))
        sys.exit(1)

    factor_df = load_csv(args.factor_csv)
    return_df = load_csv(args.return_csv)

    ic_df = compute_ic_series(factor_df, return_df)
    ic_sum = ic_summary(ic_df)
    bt_result = quantile_backtest(factor_df, return_df, n_groups=args.n_groups)

    if args.output_dir:
        save_info = save_results(args.output_dir, ic_df, ic_sum, bt_result)
        output = {"ic_summary": ic_sum, "backtest": bt_result, "saved": save_info}
    else:
        output = {"ic_summary": ic_sum, "backtest": bt_result}

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


def cmd_filter(args):
    """基本面因子筛选"""
    from fundamental_filter import SignalEngine

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        print(json.dumps({"error": "请提供股票代码 (--codes)"}))
        sys.exit(1)

    engine = SignalEngine(
        pe_max=args.pe_max,
        pb_max=args.pb_max,
        roe_min=args.roe_min,
    )

    # 输出筛选参数
    result = {
        "action": "fundamental_filter",
        "params": {
            "codes": codes,
            "pe_max": args.pe_max,
            "pb_max": args.pb_max,
            "roe_min": args.roe_min,
        },
        "criteria": {
            "value": f"0 < PE <= {args.pe_max} AND PB <= {args.pb_max} AND ROE >= {args.roe_min}%",
            "signal": "满足条件的股票等权做多 (1/N)",
        },
        "note": "SignalEngine 需配合 tushare daily_basic 数据的 DataFrame 使用，"
                "此处仅输出筛选参数。详见 scripts/analysis/fundamental_filter.py",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _load_panels_from_dir(panels_dir):
    """加载 panels-dir 下所有 CSV（文件名=子指标名，index=date, columns=code）。"""
    import glob

    from factor_engine import load_csv

    panels = {}
    for path in sorted(glob.glob(os.path.join(panels_dir, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        panels[name] = load_csv(path)
    return panels


def cmd_multifactor(args):
    """六因子选股：子指标面板目录 → 六因子得分 + 综合得分 + TopN"""
    from multifactor import FACTOR_CN, compute_six_factors, multifactor_score, top_n

    if not os.path.isdir(args.panels_dir):
        print(json.dumps({"error": f"面板目录不存在: {args.panels_dir}"}))
        sys.exit(1)
    panels = _load_panels_from_dir(args.panels_dir)
    if not panels:
        print(json.dumps({"error": "面板目录中没有 CSV 文件"}))
        sys.exit(1)

    six = compute_six_factors(panels)
    if not six:
        print(json.dumps({"error": "子指标面板不足，无法计算任何因子（需要 ep/bp/fcf_yield/mom_12_1/roe 等）"}))
        sys.exit(1)

    weights = None
    if args.weights_json:
        try:
            weights = json.loads(args.weights_json)
        except json.JSONDecodeError:
            print(json.dumps({"error": "--weights-json 不是合法 JSON"}))
            sys.exit(1)

    composite = multifactor_score(six, weights)
    latest = composite.iloc[-1] if len(composite) else None
    # 默认取最新一个交易日的 TopN（选股结果），可用 --date 指定历史日期
    date_arg = args.date or (str(composite.index[-1].date()) if len(composite) else None)
    top = top_n(composite, args.top_n, date_arg)
    top_records = top.to_dict("records")
    for r in top_records:
        r["date"] = str(r["date"])[:10]  # Timestamp → YYYY-MM-DD（JSON 序列化）

    output = {
        "action": "multifactor",
        "factors_computed": {f: FACTOR_CN.get(f, f) for f in six},
        "factor_scores_latest": (
            {f: round(float(panel.iloc[-1].mean()), 2) for f, panel in six.items()} if len(composite) else {}
        ),
        "composite_latest_top": top_records,
    }
    if latest is not None:
        output["composite_latest_mean"] = round(float(latest.mean()), 2)
        output["n_stocks_latest"] = int(latest.notna().sum())
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_timing(args):
    """因子择时：经济周期 → 权重 + 利好/不利因子；可选宏观判定与拥挤度"""
    from factor_timing import detect_cycle, timing_report

    if args.cycle:
        try:
            report = timing_report(args.cycle)
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    else:
        report = detect_cycle(
            gdp_trend=args.gdp_trend,
            inflation=args.inflation,
            interest_trend=args.interest_trend,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_smallcap(args):
    """小盘成长挖掘：特征 CSV（index=code）→ 硬门槛过滤 + 质量评分 + 评级"""
    from small_cap_growth import screen

    if not os.path.isfile(args.input):
        print(json.dumps({"error": f"输入文件不存在: {args.input}"}))
        sys.exit(1)
    df = pd.read_csv(args.input, index_col=0)
    result = screen(df)
    if result.empty:
        print(json.dumps({"action": "smallcap", "passed": 0, "note": "无标的通过市值/成长硬门槛"}))
        return
    cols = [c for c in ["code", "name", "total_mv_yi", "band", "revenue_cagr3_pct", "quality_score", "rating"]
            if c in result.columns]
    top = result.head(args.top_n)
    print(json.dumps({
        "action": "smallcap",
        "passed": int(len(result)),
        "total_candidates": int(len(df)),
        "top": top[cols].to_dict("records"),
    }, ensure_ascii=False, indent=2))


def cmd_build(args):
    """面板构造：close CSV（+benchmark CSV）→ 常用因子面板 CSV 目录（防前视偏差）"""
    from builder import build_core_factors

    if not os.path.isfile(args.close):
        print(json.dumps({"error": f"close 文件不存在: {args.close}"}))
        sys.exit(1)
    from factor_engine import load_csv

    close = load_csv(args.close)
    bench = None
    if args.benchmark:
        if not os.path.isfile(args.benchmark):
            print(json.dumps({"error": f"benchmark 文件不存在: {args.benchmark}"}))
            sys.exit(1)
        bench = load_csv(args.benchmark).iloc[:, 0]

    panels = build_core_factors(close, bench, period=args.period)
    returns = panels.pop("_returns")
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        for name, panel in panels.items():
            panel.to_csv(os.path.join(args.outdir, f"{name}.csv"))
        returns.to_csv(os.path.join(args.outdir, "_returns.csv"))
    print(json.dumps({
        "action": "build",
        "panels": list(panels.keys()),
        "returns": "_returns.csv",
        "lookahead_bias_guard": "收益 = close[t+N]/close[t] - 1（因子 t 日对应 t+N 日持有收益）",
        "outdir": args.outdir or None,
    }, ensure_ascii=False, indent=2))


def cmd_combine(args):
    """多因子组合：多个因子 CSV + 方法 → 组合因子面板"""
    from factor_engine import factor_combination, load_csv

    if len(args.factor_csv) < 2:
        print(json.dumps({"error": "至少需要两个因子 CSV"}))
        sys.exit(1)
    dfs = [load_csv(p) for p in args.factor_csv]
    weights = None
    if args.weights_json:
        try:
            weights = json.loads(args.weights_json)
        except json.JSONDecodeError:
            print(json.dumps({"error": "--weights-json 不是合法 JSON"}))
            sys.exit(1)
    composite = factor_combination(dfs, method=args.method, weights=weights)
    if isinstance(composite, dict) and "error" in composite:
        print(json.dumps(composite))
        sys.exit(1)
    if args.output:
        composite.to_csv(args.output)
    latest = composite.iloc[-1] if len(composite) else None
    print(json.dumps({
        "action": "combine",
        "method": args.method,
        "n_factors": len(dfs),
        "n_dates": int(len(composite)),
        "composite_latest_mean": round(float(latest.mean()), 6) if latest is not None else None,
        "saved": args.output or None,
    }, ensure_ascii=False, indent=2))


def show_help():
    help_text = """
factor-research — 量化因子研究技能包
======================================

模式1: analyze — 因子有效性分析
--------------------------------
  python cli.py analyze \\
    --factor-csv factor.csv \\
    --return-csv return.csv \\
    --output-dir ./output \\
    --n-groups 5

  输入文件格式: CSV (index=date, columns=股票代码)
  输出: IC/IR 统计 + 分层回测结果

模式2: filter — 基本面因子筛选
-------------------------------
  python cli.py filter \\
    --codes 000001.SZ,600036.SH,000858.SZ \\
    --pe-max 20 --pb-max 3 --roe-min 8

  筛选条件: 0 < PE <= pe_max AND PB <= pb_max AND ROE >= roe_min%

模式3: build — 因子面板构造（防前视偏差）
------------------------------------------
  python cli.py build \\
    --close close.csv [--benchmark hs300.csv] [--period 20] [--outdir ./panels]

  产出动量/波动率/下行偏差/换手率/规模/β 子指标面板 + _returns.csv
  （收益 = close[t+N]/close[t]-1，因子 t 日对齐 t+N 持有收益）

模式4: multifactor — 六因子选股
--------------------------------
  python cli.py multifactor \\
    --panels-dir ./panels [--top-n 20] [--weights-json '{"value":0.2,...}']

  panels-dir 内每个 CSV 文件名=子指标名（ep/bp/fcf_yield/ev_ebitda_inv/
  mom_12_1/rev_eps/turnover_neg/roe/stability/leverage_neg/accrual/
  volatility_neg/beta_neg/downside_neg/size_neg/revenue_cagr/profit_cagr/
  margin_expansion/fwd_rev_growth）
  输出: 六因子得分 + 综合得分 TopN

模式5: timing — 因子择时与拥挤度
----------------------------------
  python cli.py timing --cycle recovery_early
  python cli.py timing --gdp-trend 0.8 --inflation 0.2 --interest-trend -0.1

  cycle: recovery_early/expansion_mid/expansion_late/downturn/trough_rebound
  输出: 周期权重 + 利好/不利因子（与 references/factor-methodology.md 一致）

模式6: smallcap — 小盘成长挖掘
--------------------------------
  python cli.py smallcap --input features.csv [--top-n 20]

  features.csv: index=股票代码, 列 total_mv_yi / revenue_cagr3_pct /
  revenue_cagr2_pct（可选）及评分字段（可选）
  输出: 市值/成长硬门槛过滤 + 成长质量评分(0-100) + 星级评级

模式7: combine — 多因子组合
-----------------------------
  python cli.py combine \\
    --factor-csv f1.csv f2.csv f3.csv \\
    --method equal_weight|ic_weight|orthogonal \\
    [--weights-json '[0.2,0.5,0.3]'] [--output composite.csv]

因子方法论参考: references/factor-methodology.md / small-cap-screening-criteria.md
"""
    print(help_text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        show_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="factor-research — 量化因子研究技能包",
    )
    sub = parser.add_subparsers(dest="mode")

    # analyze 模式
    p_analyze = sub.add_parser("analyze", help="IC/IR 分析 + 分层回测")
    p_analyze.add_argument("--factor-csv", required=True, help="因子值 CSV 路径")
    p_analyze.add_argument("--return-csv", required=True, help="收益 CSV 路径")
    p_analyze.add_argument("--output-dir", default=None, help="输出目录")
    p_analyze.add_argument("--n-groups", type=int, default=5, help="分组数 (默认5)")

    # filter 模式
    p_filter = sub.add_parser("filter", help="基本面因子筛选")
    p_filter.add_argument("--codes", required=True, help="股票代码（逗号分隔）")
    p_filter.add_argument("--pe-max", type=float, default=20.0, help="PE 上限")
    p_filter.add_argument("--pb-max", type=float, default=3.0, help="PB 上限")
    p_filter.add_argument("--roe-min", type=float, default=8.0, help="ROE 下限 (%)")

    # build 模式
    p_build = sub.add_parser("build", help="因子面板构造（防前视偏差）")
    p_build.add_argument("--close", required=True, help="收盘价 CSV (index=date, columns=code)")
    p_build.add_argument("--benchmark", default=None, help="基准指数收盘 CSV（可选，用于 β）")
    p_build.add_argument("--period", type=int, default=20, help="前瞻持有期 (默认20)")
    p_build.add_argument("--outdir", default=None, help="面板输出目录")

    # multifactor 模式
    p_mf = sub.add_parser("multifactor", help="六因子选股")
    p_mf.add_argument("--panels-dir", required=True, help="子指标面板 CSV 目录（文件名=子指标名）")
    p_mf.add_argument("--top-n", type=int, default=20, help="TopN (默认20)")
    p_mf.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认最新）")
    p_mf.add_argument("--weights-json", default=None, help="因子权重 JSON（可选）")

    # timing 模式
    p_timing = sub.add_parser("timing", help="因子择时与拥挤度")
    p_timing.add_argument("--cycle", default=None,
                          help="经济周期: recovery_early/expansion_mid/expansion_late/downturn/trough_rebound")
    p_timing.add_argument("--gdp-trend", type=float, default=0.0, help="GDP 环比趋势")
    p_timing.add_argument("--inflation", type=float, default=0.0, help="通胀水平")
    p_timing.add_argument("--interest-trend", type=float, default=0.0, help="利率趋势")

    # smallcap 模式
    p_sc = sub.add_parser("smallcap", help="小盘成长挖掘")
    p_sc.add_argument("--input", required=True, help="特征 CSV (index=code)")
    p_sc.add_argument("--top-n", type=int, default=20, help="TopN (默认20)")

    # combine 模式
    p_cb = sub.add_parser("combine", help="多因子组合")
    p_cb.add_argument("--factor-csv", nargs="+", required=True, help="因子 CSV 列表")
    p_cb.add_argument("--method", default="equal_weight", choices=["equal_weight", "ic_weight", "orthogonal"])
    p_cb.add_argument("--weights-json", default=None, help="IC 权重 JSON（可选）")
    p_cb.add_argument("--output", default=None, help="组合结果 CSV 输出路径")

    args = parser.parse_args()

    if args.mode == "analyze":
        cmd_analyze(args)
    elif args.mode == "filter":
        cmd_filter(args)
    elif args.mode == "build":
        cmd_build(args)
    elif args.mode == "multifactor":
        cmd_multifactor(args)
    elif args.mode == "timing":
        cmd_timing(args)
    elif args.mode == "smallcap":
        cmd_smallcap(args)
    elif args.mode == "combine":
        cmd_combine(args)
    else:
        show_help()


if __name__ == "__main__":
    main()
