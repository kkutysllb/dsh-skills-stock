#!/usr/bin/env python3
"""financial-statement 技能数据脚本：一键获取三大报表关键指标 + 盈利质量 + 杜邦拆解。

用法:
    python3 financial_cli.py 600519.SH
    python3 financial_cli.py 600519.SH --periods 4

数据源: Tushare Pro（通过 kk_common 金融数据网关，禁止直接 import tushare）。
输出: 结构化文本（利润表/资产负债表/现金流量表/盈利质量/红旗检测/杜邦拆解），
      数据缺失时如实标注，绝不编造。
"""
import argparse
import subprocess
import sys
import traceback

import os as _os

COMMON_CANDIDATE_PATHS = [
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "common"),
    "/mnt/skills/public/common",
]

def _ensure_kk_common() -> None:
    """确保 kk_common 可导入：未安装时自动 pip install -e（仅一次）。"""
    try:
        import kk_common  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    for path in COMMON_CANDIDATE_PATHS:
        import os
        if os.path.isdir(path):
            print(f"[install] pip install -e {path}", file=sys.stderr)
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-e", path],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0:
                try:
                    import kk_common  # noqa: F401
                    return
                except ModuleNotFoundError:
                    continue
            print(r.stderr[-500:], file=sys.stderr)
    print("错误: 无法导入 kk_common（common 技能未安装）。", file=sys.stderr)
    sys.exit(1)

def _pick(df, *names, default=None):
    """按候选列名取 DataFrame 列（Tushare 字段名兼容）。"""
    if df is None or df.empty:
        return default
    for n in names:
        if n in df.columns:
            return df.iloc[0][n]
    return default

def _num(v, nd=2):
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if fv != fv:  # NaN
        return None
    return round(fv, nd)

def _pct(v):
    nv = _num(v)
    return f"{nv:.2f}%" if nv is not None else "缺失"

def _fmt_wan(v):
    """万元 → 亿元。Tushare 财务字段单位为元，转亿元便于阅读。"""
    nv = _num(v, 2)
    return f"{nv/1e8:.2f}亿" if nv is not None else "缺失"

def main() -> None:
    ap = argparse.ArgumentParser(description="三大报表关键指标一键获取")
    ap.add_argument("ts_code", help="股票代码，如 600519.SH")
    ap.add_argument("--periods", type=int, default=4, help="获取最近 N 个报告期（默认 4）")
    args = ap.parse_args()

    _ensure_kk_common()
    from kk_common import get_finance_data_gateway
    gw = get_finance_data_gateway()

    ts_code = args.ts_code.upper()
    print(f"# 财报三表分析: {ts_code}（最近 {args.periods} 期）\n")

    try:
        income = gw.income(ts_code=ts_code, start_date="20180101")
    except Exception as exc:
        print(f"错误: income 接口失败: {exc}")
        income = None
    try:
        bs = gw.balancesheet(ts_code=ts_code, start_date="20180101")
    except Exception as exc:
        print(f"错误: balancesheet 接口失败: {exc}")
        bs = None
    try:
        cf = gw.cashflow(ts_code=ts_code, start_date="20180101")
    except Exception as exc:
        print(f"错误: cashflow 接口失败: {exc}")
        cf = None
    try:
        fina = gw.fina_indicator(ts_code=ts_code, start_date="20180101")
    except Exception as exc:
        print(f"错误: fina_indicator 接口失败: {exc}")
        fina = None

    if income is None or income.empty:
        print("未获取到任何财务数据（TUSHARE_TOKEN 未注入或接口无权限）。")
        sys.exit(1)

    income = income.sort_values("end_date", ascending=False).drop_duplicates(subset=["end_date"]).head(args.periods)
    bs = bs.sort_values("end_date", ascending=False).drop_duplicates(subset=["end_date"]).head(args.periods) if bs is not None and not bs.empty else None
    cf = cf.sort_values("end_date", ascending=False).drop_duplicates(subset=["end_date"]).head(args.periods) if cf is not None and not cf.empty else None
    fina = fina.sort_values("end_date", ascending=False).drop_duplicates(subset=["end_date"]).head(args.periods) if fina is not None and not fina.empty else None

    print("## 一、利润表关键指标")
    print(f"{'报告期':<12}{'营业总收入':>12}{'归母净利润':>12}{'毛利率':>10}{'净利率':>10}")
    for i in range(len(income)):
        row = income.iloc[i]
        period = str(row.get("end_date", ""))[:10]
        rev = _fmt_wan(_pick(income.iloc[[i]], "total_revenue", "revenue"))
        ni = _fmt_wan(_pick(income.iloc[[i]], "n_income_attr_p", "n_income"))
        gm = _pct(_pick(fina.iloc[[i]], "grossprofit_margin") if fina is not None else None)
        nm = _pct(_pick(fina.iloc[[i]], "netprofit_margin") if fina is not None else None)
        print(f"{period:<12}{rev:>12}{ni:>12}{gm:>10}{nm:>10}")

    print("\n## 二、资产负债表重点")
    print(f"{'报告期':<12}{'总资产':>12}{'总负债':>12}{'货币资金':>12}{'存货':>12}")
    if bs is not None:
        for i in range(len(bs)):
            row = bs.iloc[i]
            period = str(row.get("end_date", ""))[:10]
            print(f"{period:<12}"
                  f"{_fmt_wan(_pick(bs.iloc[[i]], 'total_assets')):>12}"
                  f"{_fmt_wan(_pick(bs.iloc[[i]], 'total_liab')):>12}"
                  f"{_fmt_wan(_pick(bs.iloc[[i]], 'money_cap')):>12}"
                  f"{_fmt_wan(_pick(bs.iloc[[i]], 'inventories')):>12}")
    else:
        print("（数据缺失）")

    print("\n## 三、现金流量表重点")
    print(f"{'报告期':<12}{'经营现金流':>12}{'投资现金流':>12}{'筹资现金流':>12}")
    if cf is not None:
        for i in range(len(cf)):
            row = cf.iloc[i]
            period = str(row.get("end_date", ""))[:10]
            print(f"{period:<12}"
                  f"{_fmt_wan(_pick(cf.iloc[[i]], 'n_cashflow_act')):>12}"
                  f"{_fmt_wan(_pick(cf.iloc[[i]], 'n_cashflow_inv_act', 'c_invest')):>12}"
                  f"{_fmt_wan(_pick(cf.iloc[[i]], 'n_cash_flows_fnc_act', 'c_finance')):>12}")
    else:
        print("（数据缺失）")

    # 最新一期盈利质量
    print("\n## 四、盈利质量（最新一期）")
    if cf is not None and not cf.empty and income is not None and not income.empty:
        cfo = _num(_pick(cf, "n_cashflow_act"))
        ni = _num(_pick(income, "n_income_attr_p", "n_income"))
        if cfo is not None and ni not in (None, 0):
            ratio = cfo / ni
            flag = "健康" if ratio >= 0.8 else ("一般" if ratio >= 0.5 else "⚠️ 现金含量偏低")
            print(f"CFO/归母净利润 = {ratio:.2f}（{flag}，<0.8 需警惕利润无现金支撑）")
        else:
            print("CFO 或净利润缺失，无法计算比率")
    else:
        print("（现金流量表数据缺失）")

    print("\n## 五、杜邦拆解（ROE = 净利率 × 总资产周转 × 权益乘数）")
    if fina is not None and not fina.empty:
        row = fina.iloc[0]
        roe = _num(_pick(fina, "roe"))
        nm = _num(_pick(fina, "netprofit_margin"))
        # roe 拆解: roe = netprofit_margin * asset_turnover * equity_multiplier
        print(f"ROE = {roe}%（最新期）" if roe is not None else "ROE 缺失")
        if nm is not None:
            print(f"  净利率 = {nm}%")
        print(f"  总资产周转率 = {_num(_pick(fina, 'assets_turn'))}（次）" if _pick(fina, "assets_turn") is not None else "  总资产周转率 缺失")
        print(f"  资产负债率 = {_pct(_pick(fina, 'debt_to_assets'))}")
    else:
        print("（fina_indicator 数据缺失）")

    print("\n## 六、财务红旗检测（12 项中的关键 4 项）")
    if bs is not None and not bs.empty and income is not None and not income.empty:
        money = _num(_pick(bs, "money_cap")) or 0
        short_loan = _num(_pick(bs, "short_loan")) or 0
        long_loan = _num(_pick(bs, "long_loan")) or 0
        interest_debt = short_loan + long_loan
        if money > 0 and interest_debt > 0 and money > interest_debt * 3:
            print("  红旗#1 存贷双高: ⚠️ 货币资金显著高于有息负债（资金疑似受限/体外循环）")
        else:
            print("  红旗#1 存贷双高: 未触发")
        # 应收账款暴增（用 fina_indicator）
        if fina is not None and not fina.empty and len(fina) >= 2:
            latest = _num(_pick(fina, "accounts_receiv")) if "accounts_receiv" in fina.columns else None
            prev = _num(_pick(fina.iloc[[1]], "accounts_receiv")) if len(fina) > 1 and "accounts_receiv" in fina.columns else None
            if latest is not None and prev not in (None, 0) and latest > prev * 1.5:
                print("  红旗#2 应收暴增: ⚠️ 应收账款同比增幅超 50%")
            else:
                print("  红旗#2 应收暴增: 未触发")
        else:
            print("  红旗#2 应收暴增: 数据不足")
        # CFO/净利润背离（已在上方计算，这里给结论）
        cfo = _num(_pick(cf, "n_cashflow_act")) if cf is not None else None
        ni = _num(_pick(income, "n_income_attr_p", "n_income"))
        if cfo is not None and ni not in (None, 0) and cfo / ni < 0.5:
            print("  红旗#3 现金流背离: ⚠️ CFO/净利润 < 0.5")
        else:
            print("  红旗#3 现金流背离: 未触发")
        # 毛利率异常（同行业比较留白，仅提示）
        print("  红旗#4 毛利率异常: 需结合同行业对比（本脚本不跨公司拉取）")
    else:
        print("（资产负债表数据缺失，跳过红旗检测）")

    print("\n> 数据来源: Tushare Pro（income/balancesheet/cashflow/fina_indicator）")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("脚本异常:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
