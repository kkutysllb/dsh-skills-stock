#!/usr/bin/env python3
"""valuation-model 技能数据脚本：一键计算 PE-Band（5 年 PE_TTM 序列 + 分位数）。

用法:
    python3 pe_band_cli.py 600519.SH
    python3 pe_band_cli.py 600519.SH --years 5

数据源: Tushare Pro（通过 kk_common 金融数据网关，禁止直接 import tushare）。
输出: 当前 PE/市值 + 5 年 PE_TTM 分位表 + 估值结论 + 陷阱提示。
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
    try:
        import kk_common  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    import os
    for path in COMMON_CANDIDATE_PATHS:
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

def _num(v, nd=2):
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if fv != fv:
        return None
    return round(fv, nd)

def main() -> None:
    ap = argparse.ArgumentParser(description="PE-Band 估值分析（5 年 PE_TTM 分位）")
    ap.add_argument("ts_code", help="股票代码，如 600519.SH")
    ap.add_argument("--years", type=int, default=5, help="历史年数（默认 5）")
    args = ap.parse_args()

    _ensure_kk_common()
    from kk_common import get_finance_data_gateway
    gw = get_finance_data_gateway()

    ts_code = args.ts_code.upper()
    print(f"# PE-Band 估值分析: {ts_code}（近 {args.years} 年 PE_TTM）\n")

    # 1. 当前行情 + 每日指标（PE/PB/市值）
    try:
        daily_basic = gw.daily_basic(ts_code=ts_code, start_date="20180101")
    except Exception as exc:
        print(f"错误: daily_basic 接口失败: {exc}")
        sys.exit(1)
    if daily_basic is None or daily_basic.empty:
        print("未获取到数据（TUSHARE_TOKEN 未注入或接口无权限）。")
        sys.exit(1)

    daily_basic = daily_basic.sort_values("trade_date")
    daily_basic = daily_basic.drop_duplicates(subset=["trade_date"], keep="last")
    latest = daily_basic.iloc[-1]
    cur_date = str(latest.get("trade_date", ""))[:10]
    cur_pe = _num(latest.get("pe_ttm"))
    cur_pe_static = _num(latest.get("pe"))
    cur_pb = _num(latest.get("pb"))
    total_mv = _num(latest.get("total_mv"))  # 万元
    close = _num(latest.get("close"))

    print("## 一、当前估值快照")
    print(f"  交易日: {cur_date}")
    print(f"  收盘价: {close if close is not None else '缺失'}")
    print(f"  PE(TTM): {cur_pe if cur_pe is not None else '缺失'}")
    print(f"  PE(静态): {cur_pe_static if cur_pe_static is not None else '缺失'}")
    print(f"  PB: {cur_pb if cur_pb is not None else '缺失'}")
    if total_mv is not None:
        print(f"  总市值: {total_mv/1e4:.2f} 亿元")
    else:
        print("  总市值: 缺失")

    # 2. 5 年 PE_TTM 序列（月末抽样）
    pe_series = daily_basic[["trade_date", "pe_ttm"]].dropna()
    if pe_series.empty:
        print("\n历史 PE_TTM 序列为空（接口无权限或数据缺失）。")
        sys.exit(1)
    # 按年月取每月最后一个交易日
    pe_series = pe_series.copy()
    pe_series["ym"] = pe_series["trade_date"].str[:6]
    monthly = pe_series.groupby("ym").last().reset_index()
    years = args.years
    cutoff = monthly["ym"].max()[:4]
    try:
        cutoff_year = int(cutoff) - years
    except (TypeError, ValueError):
        cutoff_year = 2018
    window = monthly[monthly["ym"] >= f"{cutoff_year}01"]

    print(f"\n## 二、近 {years} 年 PE_TTM 月末序列（{len(window)} 个月）")
    print("  首月:", str(window.iloc[0].get("ym")), "末月:", str(window.iloc[-1].get("ym")))

    # 3. 分位数
    vals = window["pe_ttm"].astype(float).values
    import statistics
    sval = sorted(vals)
    pcts = {
        p: round(sval[max(int(len(vals) * p / 100) - 1, 0)], 2)
        for p in (10, 25, 50, 75, 90)
    }
    mn, mx = round(min(vals), 2), round(max(vals), 2)
    mean = round(statistics.mean(vals), 2)
    median = pcts[50]

    print("\n## 三、PE_TTM 历史分位")
    print(f"  {'分位':<6}{'PE':>8}")
    for p in (10, 25, 50, 75, 90):
        print(f"  {p}%{'':<4}{pcts[p]:>8}")
    print(f"  min{'':<4}{mn:>8}")
    print(f"  max{'':<4}{mx:>8}")
    print(f"  mean{'':<4}{mean:>8}")
    print(f"  样本数: {len(vals)}")

    # 4. 当前 PE 分位判定
    print("\n## 四、估值结论")
    if cur_pe is None:
        print("  当前 PE(TTM) 缺失，无法判定分位。")
    else:
        below = sum(1 for v in vals if v <= cur_pe)
        percentile = round(below / len(vals) * 100, 1)
        if percentile <= 10:
            verdict = "深度低估（≤10 分位）"
        elif percentile <= 25:
            verdict = "低估（≤25 分位）"
        elif percentile <= 50:
            verdict = "偏低（25-50 分位）"
        elif percentile <= 75:
            verdict = "合理偏高（50-75 分位）"
        else:
            verdict = "高估（>75 分位）"
        print(f"  当前 PE(TTM) = {cur_pe}，处于近 {years} 年 {percentile}% 分位 → {verdict}")
        print(f"  （按 SKILL.md 判定标准：≤10% 深度低估 / ≤25% 低估 / 50% 中枢 / >75% 高估）")

    # 5. 陷阱提示（SKILL.md Top10 Trap #1: 周期低位假象）
    print("\n## 五、估值陷阱提示（SKILL.md Top10）")
    print("  Trap#1 周期低位假象: PE 最低点往往出现在盈利峰值，若当前盈利处于下行周期，")
    print("         低 PE 可能是『低 PE 假象』而非真低估——需交叉验证盈利趋势与行业周期。")
    print("  Trap#2 高 PE 成长可证: PEG<1 时高 PE 可被成长支撑，勿机械套用分位结论。")
    print("  Trap#8 股本稀释: 期权/可转债会摊薄 EPS，PE 应基于摊薄后 EPS。")

    print("\n> 数据来源: Tushare Pro daily_basic（pe_ttm）")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("脚本异常:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
