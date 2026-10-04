#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多因子横截面选股策略运行脚本

策略特点：
  - 基于已安装的多因子选股策略技能实现
  - 内置7大因子：动量(momentum)/反转(reversal)/波动率(volatility)/量比(volume_ratio)/PE/PB/ROE
  - 截面Z-score标准化 + 等权/自定义加权综合评分
  - TopN等权组合构建，适合量化组合策略

数据来源：Tushare Pro API（T+1延迟）

用法：
  python scripts/selection-strategies/run_multi_factor.py [选项]

选项：
  --limit      N     返回股票数量（默认 20）
  --top-n      N     选入TopN（默认 10）
  --momentum-window N  动量回溯窗口（默认 20）
  --vol-window N      波动率回溯窗口（默认 20）
  --weights    W     因子权重JSON（默认等权），如 '{"momentum":0.2,"pe_factor":0.2}'
  --market-cap TYPE   市值范围：large / mid / small / all（默认 all）
  --stock-pool TYPE   股票池：all / main / gem / star（默认 all）
  --date       DATE   指定交易日期 YYYYMMDD（默认最新交易日）
  --output     FILE   结果保存到文件（可选，csv 格式）
"""

import sys
import os
import argparse
import json
import csv
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ── 路径设置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(SKILL_ROOT)
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
# ─────────────────────────────────────────────────────────


# ════════════════════════════════════════════════════════════
#  因子方向定义
# ════════════════════════════════════════════════════════════
# 正方向=越大越好，负方向=越小越好（标准化前取反）
FACTOR_CONFIG = {
    "momentum":      {"direction": 1,  "desc": "N日涨跌幅（动量）"},
    "reversal":      {"direction": -1, "desc": "5日涨跌幅（反转）"},
    "volatility":    {"direction": -1, "desc": "N日收益率标准差（波动率）"},
    "volume_ratio":  {"direction": 1,  "desc": "当日成交量/N日均量（量比）"},
    "pe_factor":     {"direction": 1,  "desc": "1/PE_TTM（低PE因子）"},
    "pb_factor":     {"direction": 1,  "desc": "1/PB（低PB因子）"},
    "roe_factor":    {"direction": 1,  "desc": "ROE_TTM（盈利能力因子）"},
}

DEFAULT_WEIGHTS = {k: round(1.0 / len(FACTOR_CONFIG), 4) for k in FACTOR_CONFIG}


# ════════════════════════════════════════════════════════════
#  数据获取（Tushare Pro API）
# ════════════════════════════════════════════════════════════
class TushareDataFetcher:
    """通过 Tushare Pro API 获取横截面选股数据"""

    def __init__(self):
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            raise RuntimeError("缺少环境变量 TUSHARE_TOKEN")
        from kk_common import get_finance_data_gateway
        self.pro = get_finance_data_gateway()

    def get_trade_date(self, date_str=None):
        """获取最近交易日（T+1 延迟：当日行情次日才入库，取上一交易日）"""
        if date_str:
            return date_str
        cal_df = self.pro.trade_cal(
            exchange="SSE",
            is_open="1",
            end_date=datetime.now().strftime("%Y%m%d"),
            limit=2,
        )
        if cal_df is not None and not cal_df.empty:
            cal_df = cal_df.sort_values("cal_date", ascending=False)
            # limit=2 取最近两个交易日，返回较旧的那个（当日数据 T+1 延迟不可用）
            return cal_df.iloc[1]["cal_date"] if len(cal_df) >= 2 else cal_df.iloc[0]["cal_date"]
        return datetime.now().strftime("%Y%m%d")

    def get_stock_list(self, stock_pool="all", market_cap="all"):
        """获取股票池列表"""
        df = self.pro.stock_basic(
            exchange="", list_status="L", fields="ts_code,symbol,name,area,industry,market,list_date"
        )
        if df is None or df.empty:
            return pd.DataFrame()

        # 排除 ST / *ST
        df = df[~df["name"].str.contains("ST", na=False)]
        # 排除上市不足60个交易日的新股
        min_list_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        df = df[df["list_date"] <= min_list_date]

        # 股票池过滤
        if stock_pool == "main":
            df = df[df["market"].isin(["主板"])]
        elif stock_pool == "gem":
            df = df[df["market"].isin(["创业板"])]
        elif stock_pool == "star":
            df = df[df["market"].isin(["科创板"])]

        return df

    def fetch_daily(self, ts_codes, trade_date, lookback=30):
        """获取日线行情数据"""
        # 获取截面日行情
        daily_df = self.pro.daily(trade_date=trade_date)
        if daily_df is None or daily_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # 过滤目标股票池
        daily_df = daily_df[daily_df["ts_code"].isin(ts_codes)]

        # 获取过去N个交易日行情（用于计算动量/波动率等）
        # 先找到回溯起始日期
        cal_df = self.pro.trade_cal(
            exchange="SSE", is_open="1",
            end_date=trade_date, limit=lookback + 10,
        )
        start_date = None
        if cal_df is not None and not cal_df.empty:
            cal_df = cal_df.sort_values("cal_date", ascending=True)
            start_date = cal_df.iloc[max(0, len(cal_df) - lookback - 1)]["cal_date"]
        else:
            # 防御：交易日历缺失/异常时按自然日向前推算（如 30 交易日 ≈ 45 自然日）
            from datetime import datetime, timedelta
            try:
                td_dt = datetime.strptime(str(trade_date), "%Y%m%d")
                start_date = (td_dt - timedelta(days=int(lookback * 1.5) + 10)).strftime("%Y%m%d")
            except Exception:
                start_date = None
        if start_date is None:
            return daily_df, pd.DataFrame()

        # 分批获取历史行情：按交易日批量拉取（每次 1 个交易日覆盖全部股票，
        # 共 lookback 次调用），而非逐股 5538 次调用（易限流且慢 ~180 倍）。
        hist_frames = []
        if cal_df is not None and not cal_df.empty:
            trade_days = [str(d) for d in cal_df.sort_values("cal_date", ascending=True)["cal_date"]]
            for day in trade_days:
                try:
                    h = self.pro.daily(trade_date=day)
                    if h is not None and not h.empty:
                        hit = h[h["ts_code"].isin(ts_codes)]
                        if not hit.empty:
                            hist_frames.append(hit)
                except Exception:
                    pass

        hist_df = pd.concat(hist_frames, ignore_index=True) if hist_frames else pd.DataFrame()
        return daily_df, hist_df

    def fetch_daily_basic(self, ts_codes, trade_date):
        """获取每日基本面指标（PE/PB/ROE/总市值）"""
        db = self.pro.daily_basic(trade_date=trade_date)
        if db is None or db.empty:
            return pd.DataFrame()
        db = db[db["ts_code"].isin(ts_codes)]
        return db


# ════════════════════════════════════════════════════════════
#  因子计算
# ════════════════════════════════════════════════════════════
def compute_factors(daily_df, hist_df, basic_df, momentum_window=20, vol_window=20):
    """
    为每只股票计算全部因子。

    Parameters
    ----------
    daily_df : 截面日行情（含 pct_chg, vol, close 等）
    hist_df  : 历史行情（用于计算动量/波动率）
    basic_df : daily_basic（含 pe_ttm, pb, total_mv 等）
    """
    if daily_df.empty:
        return pd.DataFrame()

    # ---- 合并截面行情 + 基本面 ----
    if not basic_df.empty:
        merge_cols = ["ts_code"]
        basic_cols = ["ts_code"]
        for c in ["pe_ttm", "pb", "total_mv", "turnover_rate"]:
            if c in basic_df.columns:
                basic_cols.append(c)
        merged = daily_df.merge(basic_df[basic_cols], on="ts_code", how="left")
    else:
        merged = daily_df.copy()
        for c in ["pe_ttm", "pb", "total_mv", "turnover_rate"]:
            merged[c] = np.nan

    # ---- 计算历史因子 ----
    factor_dict = {}

    for _, row in merged.iterrows():
        code = row["ts_code"]
        fvals = {}

        if not hist_df.empty:
            code_hist = hist_df[hist_df["ts_code"] == code].sort_values("trade_date", ascending=True)
        else:
            code_hist = pd.DataFrame()

        if code_hist.empty or len(code_hist) < 3:
            # 数据不足，因子全部 NaN
            for k in FACTOR_CONFIG:
                fvals[k] = np.nan
            fvals["close"] = row.get("close", np.nan)
            fvals["pct_chg"] = row.get("pct_chg", np.nan)
            fvals["vol"] = row.get("vol", np.nan)
            fvals["total_mv"] = row.get("total_mv", np.nan)
            factor_dict[code] = fvals
            continue

        closes = code_hist["close"].values
        vols = code_hist["vol"].values
        n = len(closes)

        # 动量：过去 N 日收益率
        mw = min(momentum_window, n - 1)
        fvals["momentum"] = (closes[-1] / closes[-1 - mw] - 1) if mw > 0 else np.nan

        # 反转：过去 5 日收益率
        rw = min(5, n - 1)
        fvals["reversal"] = (closes[-1] / closes[-1 - rw] - 1) if rw > 0 else np.nan

        # 波动率：过去 N 日收益率标准差
        vw = min(vol_window, n - 1)
        rets = np.diff(closes[-vw - 1:]) / closes[-vw - 1:-1] if vw > 0 else np.array([])
        fvals["volatility"] = np.std(rets) if len(rets) > 1 else np.nan

        # 量比：当日成交量 / N 日均量
        avg_vol = np.mean(vols[-vw:]) if vw > 0 and len(vols) >= vw else np.nan
        fvals["volume_ratio"] = (vols[-1] / avg_vol) if avg_vol and avg_vol > 0 else np.nan

        # PE 因子（1/PE）
        pe = row.get("pe_ttm", np.nan)
        fvals["pe_factor"] = (1.0 / pe) if pd.notna(pe) and pe > 0 else np.nan

        # PB 因子（1/PB）
        pb = row.get("pb", np.nan)
        fvals["pb_factor"] = (1.0 / pb) if pd.notna(pb) and pb > 0 else np.nan

        # ROE 因子（用 turnover_rate 近似或留空，Tushare daily_basic 不含 ROE）
        # 从 pe_ttm 和 pb 推导：ROE = PB/PE ≈ PB / PE_TTM
        if pd.notna(pe) and pd.notna(pb) and pe > 0:
            fvals["roe_factor"] = pb / pe  # 近似 ROE
        else:
            fvals["roe_factor"] = np.nan

        fvals["close"] = closes[-1]
        fvals["pct_chg"] = row.get("pct_chg", np.nan)
        fvals["vol"] = vols[-1]
        fvals["total_mv"] = row.get("total_mv", np.nan)
        factor_dict[code] = fvals

    factor_df = pd.DataFrame.from_dict(factor_dict, orient="index")
    factor_df.index.name = "ts_code"
    factor_df = factor_df.reset_index()
    return factor_df


# ════════════════════════════════════════════════════════════
#  截面标准化 + 综合评分
# ════════════════════════════════════════════════════════════
def cross_sectional_zscore(factor_df, factor_names):
    """
    对每个因子做截面 Z-score 标准化。
    根据因子方向调整符号（负方向因子取反后标准化）。
    """
    result = factor_df.copy()
    for fname in factor_names:
        col = fname + "_z"
        series = result[fname].copy()
        # 方向调整
        direction = FACTOR_CONFIG.get(fname, {}).get("direction", 1)
        if direction == -1:
            series = -series
        # Z-score
        mean = series.mean()
        std = series.std()
        if pd.notna(std) and std > 1e-10:
            result[col] = (series - mean) / std
        else:
            result[col] = 0.0
    return result


def composite_score(zscore_df, factor_names, weights=None):
    """
    计算综合评分 = Σ(weight_i × zscore_i)
    """
    if weights is None:
        weights = {k: 1.0 / len(factor_names) for k in factor_names}

    z_cols = [f + "_z" for f in factor_names]
    score = pd.Series(0.0, index=zscore_df.index)
    for fname, z_col in zip(factor_names, z_cols):
        w = weights.get(fname, 0)
        score += w * zscore_df[z_col].fillna(0)

    zscore_df["composite_score"] = score
    zscore_df = zscore_df.sort_values("composite_score", ascending=False).reset_index(drop=True)
    zscore_df["rank"] = range(1, len(zscore_df) + 1)
    return zscore_df


# ════════════════════════════════════════════════════════════
#  市值过滤
# ════════════════════════════════════════════════════════════
def apply_market_cap_filter(df, market_cap="all"):
    """按市值范围过滤"""
    if market_cap == "all" or df.empty:
        return df
    if "total_mv" not in df.columns:
        return df
    mv = df["total_mv"]
    # total_mv 单位：万元 → 转为亿元
    mv_yi = mv / 10000
    if market_cap == "large":
        return df[mv_yi >= 500]
    elif market_cap == "mid":
        return df[(mv_yi >= 100) & (mv_yi < 500)]
    elif market_cap == "small":
        return df[mv_yi < 100]
    return df


# ════════════════════════════════════════════════════════════
#  输出辅助
# ════════════════════════════════════════════════════════════
def print_header(params: dict):
    print("\n" + "=" * 70)
    print(f"  策略：多因子横截面选股")
    print(f"  运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  截面日期：{params.get('trade_date')}")
    print(f"  股票池：{params.get('stock_pool')}  市值范围：{params.get('market_cap')}")
    print(f"  动量窗口：{params.get('momentum_window')}  波动率窗口：{params.get('vol_window')}")
    print(f"  TopN：{params.get('top_n')}  显示数量：{params.get('limit')}")
    wt = params.get("weights", {})
    if wt:
        print(f"  因子权重：{json.dumps(wt, ensure_ascii=False)}")
    print("=" * 70)


def print_results(scored_df: pd.DataFrame, stock_info: dict, top_n: int):
    """打印选股结果"""
    if scored_df.empty:
        print("\n  暂无符合条件的股票")
        return

    total = len(scored_df)
    selected = scored_df.head(top_n)
    print(f"\n共扫描 {total} 只股票，选入 Top{top_n}：\n")

    # 因子列
    factor_names = [k for k in FACTOR_CONFIG if k in scored_df.columns]

    # 表头
    col_w = [5, 10, 8, 8, 8, 7, 7, 7, 7, 7, 7, 7]
    headers = ["排名", "代码", "名称", "综合分", "动量%", "反转%", "波动率", "量比", "PE因子", "PB因子", "ROE因子", "市值(亿)"]
    print("  " + "  ".join(h.ljust(col_w[i]) for i, h in enumerate(headers)))
    print("  " + "-" * 95)

    def _f(v, fmt=".2f"):
        return format(v, fmt) if isinstance(v, (int, float)) and pd.notna(v) else "--"

    for _, row in selected.iterrows():
        code = row.get("ts_code", "--")
        name = stock_info.get(code, {}).get("name", "--")[:4]
        mv_val = row.get("total_mv", np.nan)
        mv_str = _f(mv_val / 10000, ".1f") if pd.notna(mv_val) else "--"

        r = [
            str(int(row.get("rank", 0))),
            code,
            name,
            _f(row.get("composite_score"), ".3f"),
            _f(row.get("momentum", np.nan) * 100, ".1f") if pd.notna(row.get("momentum")) else "--",
            _f(row.get("reversal", np.nan) * 100, ".1f") if pd.notna(row.get("reversal")) else "--",
            _f(row.get("volatility", np.nan), ".4f"),
            _f(row.get("volume_ratio")),
            _f(row.get("pe_factor")),
            _f(row.get("pb_factor")),
            _f(row.get("roe_factor")),
            mv_str,
        ]
        print("  " + "  ".join(str(v).ljust(col_w[i]) for i, v in enumerate(r)))

    # 因子概览
    print(f"\n── 因子截面统计 ──")
    for fname in factor_names:
        vals = scored_df[fname].dropna()
        if len(vals) > 0:
            print(f"  {fname:14s}:  均值={vals.mean():.4f}  标准差={vals.std():.4f}  "
                  f"最大={vals.max():.4f}  最小={vals.min():.4f}  有效数={len(vals)}")
    print()


def save_to_csv(scored_df: pd.DataFrame, stock_info: dict, filepath: str):
    """保存到 CSV"""
    if scored_df.empty:
        print("  无数据，跳过保存")
        return
    out = scored_df.copy()
    out["name"] = out["ts_code"].map(lambda c: stock_info.get(c, {}).get("name", ""))
    cols_order = ["rank", "ts_code", "name", "composite_score",
                  "momentum", "reversal", "volatility", "volume_ratio",
                  "pe_factor", "pb_factor", "roe_factor",
                  "close", "pct_chg", "total_mv"]
    cols_order = [c for c in cols_order if c in out.columns]
    out[cols_order].to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"  结果已保存至：{filepath}")


# ════════════════════════════════════════════════════════════
#  主流程
# ════════════════════════════════════════════════════════════
async def run_selection(
    trade_date=None,
    stock_pool="all",
    market_cap="all",
    limit=20,
    top_n=10,
    momentum_window=20,
    vol_window=20,
    weights=None,
):
    """
    多因子横截面选股主函数。
    返回 dict，兼容 --json 输出。
    """
    result = {
        "strategy": "multi_factor",
        "strategy_desc": "多因子横截面选股",
        "data_source": "Tushare Pro API（T+1延迟）",
        "trade_date": None,
        "params": {
            "stock_pool": stock_pool,
            "market_cap": market_cap,
            "top_n": top_n,
            "momentum_window": momentum_window,
            "vol_window": vol_window,
            "weights": weights or DEFAULT_WEIGHTS,
        },
    }

    try:
        fetcher = TushareDataFetcher()
        td = fetcher.get_trade_date(trade_date)
        result["trade_date"] = td

        # 1. 获取股票池
        stock_list = fetcher.get_stock_list(stock_pool=stock_pool, market_cap=market_cap)
        if stock_list.empty:
            result["error"] = "股票池为空，请检查过滤条件"
            return result

        ts_codes = set(stock_list["ts_code"].tolist())
        stock_info = {
            r["ts_code"]: {"name": r["name"], "industry": r.get("industry", ""), "market": r.get("market", "")}
            for _, r in stock_list.iterrows()
        }

        # 2. 获取行情 + 基本面
        daily_df, hist_df = fetcher.fetch_daily(ts_codes, td, lookback=max(momentum_window, vol_window) + 10)
        basic_df = fetcher.fetch_daily_basic(ts_codes, td)

        if daily_df.empty:
            result["error"] = f"截面日 {td} 无行情数据"
            return result

        # 3. 计算因子
        factor_df = compute_factors(daily_df, hist_df, basic_df,
                                    momentum_window=momentum_window, vol_window=vol_window)

        # 4. 市值过滤
        factor_df = apply_market_cap_filter(factor_df, market_cap)

        # 5. 截面标准化
        factor_names = list(FACTOR_CONFIG.keys())
        # 只保留有效因子数量 >= 3 的股票（至少3个因子有值）
        valid_count = factor_df[factor_names].notna().sum(axis=1)
        factor_df = factor_df[valid_count >= 3].copy()

        if len(factor_df) < 3:
            result["error"] = "有效股票不足3只，无法进行截面标准化"
            return result

        zscore_df = cross_sectional_zscore(factor_df, factor_names)

        # 6. 综合评分
        w = weights if weights else DEFAULT_WEIGHTS
        scored_df = composite_score(zscore_df, factor_names, weights=w)

        # 7. 构建输出
        top_stocks = scored_df.head(top_n)
        stocks_out = []
        for _, row in top_stocks.iterrows():
            code = row.get("ts_code", "")
            item = {
                "rank": int(row.get("rank", 0)),
                "ts_code": code,
                "name": stock_info.get(code, {}).get("name", ""),
                "industry": stock_info.get(code, {}).get("industry", ""),
                "composite_score": round(float(row.get("composite_score", 0)), 4),
                "weight": round(1.0 / top_n, 4),  # 等权
            }
            for fname in factor_names:
                val = row.get(fname, np.nan)
                item[fname] = round(float(val), 6) if pd.notna(val) else None
            item["close"] = round(float(row.get("close", 0)), 2) if pd.notna(row.get("close")) else None
            item["pct_chg"] = round(float(row.get("pct_chg", 0)), 2) if pd.notna(row.get("pct_chg")) else None
            item["total_mv"] = round(float(row.get("total_mv", 0)), 2) if pd.notna(row.get("total_mv")) else None
            stocks_out.append(item)

        result["total_count"] = len(scored_df)
        result["selected_count"] = len(stocks_out)
        result["stocks"] = stocks_out
        result["factor_stats"] = {}
        for fname in factor_names:
            vals = scored_df[fname].dropna()
            if len(vals) > 0:
                result["factor_stats"][fname] = {
                    "mean": round(float(vals.mean()), 6),
                    "std": round(float(vals.std()), 6),
                    "max": round(float(vals.max()), 6),
                    "min": round(float(vals.min()), 6),
                    "valid_count": int(len(vals)),
                }

    except Exception as e:
        result["error"] = str(e)

    return result


async def main():
    parser = argparse.ArgumentParser(description="多因子横截面选股策略")
    parser.add_argument("--limit",           type=int,   default=20,    help="显示数量")
    parser.add_argument("--top-n",           type=int,   default=10,    help="选入TopN")
    parser.add_argument("--momentum-window", type=int,   default=20,    help="动量回溯窗口")
    parser.add_argument("--vol-window",      type=int,   default=20,    help="波动率回溯窗口")
    parser.add_argument("--weights",         type=str,   default=None,  help="因子权重JSON")
    parser.add_argument("--market-cap",      type=str,   default="all", dest="market_cap",
                        choices=["all", "large", "mid", "small"], help="市值范围")
    parser.add_argument("--stock-pool",      type=str,   default="all", dest="stock_pool",
                        choices=["all", "main", "gem", "star"],   help="股票池")
    parser.add_argument("--pool",            type=str,   default=None,  dest="pool_alias",
                        choices=["all", "hs300", "zz500", "zz1000"], help="股票池(简写)")
    parser.add_argument("--date",            type=str,   default=None,  help="交易日期 YYYYMMDD")
    parser.add_argument("--output",          type=str,   default=None,  help="结果保存路径（csv）")
    parser.add_argument("--json",            action="store_true", default=False, help="输出JSON格式")
    args = parser.parse_args()

    stock_pool = args.pool_alias or args.stock_pool
    weights = json.loads(args.weights) if args.weights else None

    params = {
        "trade_date": args.date or "latest",
        "stock_pool": stock_pool,
        "market_cap": args.market_cap,
        "limit": args.limit,
        "top_n": args.top_n,
        "momentum_window": args.momentum_window,
        "vol_window": args.vol_window,
        "weights": weights or DEFAULT_WEIGHTS,
    }

    if not args.json:
        print_header(params)

    result = await run_selection(
        trade_date=args.date,
        stock_pool=stock_pool,
        market_cap=args.market_cap,
        limit=args.limit,
        top_n=args.top_n,
        momentum_window=args.momentum_window,
        vol_window=args.vol_window,
        weights=weights,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
        return result

    if result.get("error"):
        print(f"\n选股失败：{result['error']}")
        return result

    # 从结果构建 scored_df 用于打印
    stocks = result.get("stocks", [])
    if stocks:
        scored_df = pd.DataFrame(stocks)
        # 重建 stock_info
        stock_info = {s["ts_code"]: {"name": s["name"]} for s in stocks}
        print_results(scored_df, stock_info, args.top_n)
    else:
        print("\n  无选股结果")

    if args.output and stocks:
        scored_df = pd.DataFrame(stocks)
        stock_info = {s["ts_code"]: {"name": s["name"]} for s in stocks}
        save_to_csv(scored_df, stock_info, args.output)

    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
