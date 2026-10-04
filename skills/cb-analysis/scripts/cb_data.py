#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可转债 Tushare 数据访问层 CLI — cb-data

封装 Tushare Pro 可转债相关接口，提供统一的数据查询入口，作为问财（实时）
日度引擎的结构化深度补充源。覆盖 8 个可用接口：

  cb_basic         基础信息（全量，1159+ 只历史及存续）
  cb_daily         日线行情（OHLCV）
  cb_issue         发行数据（公告/规模/网上中签/原股东配售）
  cb_call          赎回信息（强赎/到期赎回，call_type + is_call 状态）
  cb_share         转股结果（转股进度/累计转股率/剩余规模）
  cb_rate          票面利率（分年限利率表，需 fields 显式取全字段）
  cb_rating        债券评级历史
  top10_cb_holders 十大持有人

聚合命令：
  profile   个券全维度档案（一次聚合 basic+issue+share+rate+rating+holders+call）
  terms     条款时间线（强赎公告历史 + 评级变迁 + 当前转股价）
  ytm       到期收益率测算（cb_rate 现金流贴现）

未接入的接口（需单独权限，沙箱不可用）：
  cb_factor_pro  cb_price_chg  yc_cb

数据源：Tushare Pro（kk_common 网关）
依赖：TUSHARE_TOKEN 环境变量

用法：
  python3 cb_data.py basic --code 128044.SZ
  python3 cb_data.py daily --code 128044.SZ --start 20260801 --end 20260811
  python3 cb_data.py profile --code 128044.SZ
  python3 cb_data.py ytm --code 128044.SZ
  python3 cb_data.py terms --code 128044.SZ
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ─── 路径与网关初始化 ──────────────────────────────────────────────
# 目录结构：public/cb-analysis/scripts/cb_data.py → 向上 3 级到 public/，
# 再进同级 common/src（与 market-linkage-engine 相同的注入策略）。
_script_dir = os.path.dirname(os.path.abspath(__file__))
_KK_COMMON_SRC = os.path.normpath(
    os.path.join(_script_dir, "..", "..", "common", "src")
)
if os.path.isdir(_KK_COMMON_SRC) and _KK_COMMON_SRC not in sys.path:
    sys.path.insert(0, _KK_COMMON_SRC)

TOKEN = os.environ.get("TUSHARE_TOKEN", "")
if not TOKEN:
    print(json.dumps({"error": "TUSHARE_TOKEN 环境变量未设置"}, ensure_ascii=False))
    sys.exit(1)

try:
    from kk_common import get_finance_data_gateway
    _pro = get_finance_data_gateway()
except Exception as e:
    print(json.dumps({"error": f"kk_common 网关不可用: {e}"}, ensure_ascii=False))
    sys.exit(1)


# ======================================================================
#  通用工具
# ======================================================================

def _fmt_date(d) -> str:
    """YYYYMMDD → YYYY-MM-DD；None/空 → '-'。"""
    if d is None:
        return "-"
    s = str(d)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _valid(v) -> bool:
    """NaN/None 清洗。"""
    if v is None:
        return False
    try:
        return not (float(v) != float(v))
    except (TypeError, ValueError):
        return True


def _num(v, nd=2):
    return "-" if not _valid(v) else round(float(v), nd)


def _num_str(v, nd=2) -> str:
    return "-" if not _valid(v) else f"{float(v):,.{nd}f}"


def _yi(v):
    """元 → 亿元。"""
    return None if not _valid(v) else round(float(v) / 1e8, 4)


def _req(api: str, **kwargs) -> Any:
    """统一网关请求，异常包装为 {"error": ...} dict。"""
    try:
        df = _pro.request(api, **kwargs)
        if df is None:
            return None
        return df
    except Exception as e:
        return {"error": f"{api}: {e}"}


def _df_to_records(df) -> List[Dict]:
    """DataFrame → records，NaN → None，日期字符串化。"""
    if df is None or len(df) == 0:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    recs = df.to_dict("records")
    for r in recs:
        for k, v in list(r.items()):
            if isinstance(v, str) and len(v) == 8 and v.isdigit() and re.match(r"^\d{8}$", v):
                # 可能是日期，保留原值但标记
                pass
    return recs


def _json_out(obj: Any):
    """JSON 序列化输出，递归清洗 NaN/None。"""
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(v) for v in o]
        if isinstance(o, float):
            # NaN/Inf → None
            if o != o or o in (float("inf"), float("-inf")):
                return None
            return o
        # pandas NA / numpy nan
        try:
            if o is None or (hasattr(o, "__class__") and "NA" in o.__class__.__name__):
                return None
        except Exception:
            pass
        if hasattr(o, "item"):
            try:
                return _clean(o.item())
            except Exception:
                pass
        return o

    def _ser(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    cleaned = _clean(obj)
    print(json.dumps(cleaned, ensure_ascii=False, indent=2, default=_ser))


# ======================================================================
#  rate_clause 解析器（YTM / 现金流测算的核心）
# ======================================================================

def parse_rate_clause(clause: Optional[str]) -> List[Dict[str, Any]]:
    """解析 cb_basic.rate_clause 字段。

    格式形如："20180813-20190812,票面利率:0.40%;20190813-20200812,票面利率:0.60%;..."

    返回: [{"start": "2018-08-13", "end": "2019-08-12", "rate": 0.40}, ...]
    """
    if not clause or not isinstance(clause, str):
        return []
    segments = re.findall(
        r"(\d{8})-(\d{8}),票面利率:([\d.]+)%",
        clause,
    )
    return [
        {"start": _fmt_date(s), "end": _fmt_date(e), "rate": float(r)}
        for s, e, r in segments
    ]


# ======================================================================
#  接口封装层
# ======================================================================

def fetch_basic(code: Optional[str] = None) -> Any:
    """cb_basic：可转债基础信息。"""
    kw = {}
    if code:
        kw["ts_code"] = code
    return _req("cb_basic", **kw)


def fetch_daily(code: Optional[str] = None, start: Optional[str] = None,
                end: Optional[str] = None) -> Any:
    """cb_daily：可转债日线行情。"""
    kw = {}
    if code:
        kw["ts_code"] = code
    if start:
        kw["start_date"] = start
    if end:
        kw["end_date"] = end
    return _req("cb_daily", **kw)


def fetch_issue(code: Optional[str] = None) -> Any:
    """cb_issue：可转债发行数据。"""
    kw = {"ts_code": code} if code else {}
    return _req("cb_issue", **kw)


def fetch_call(code: Optional[str] = None, start: Optional[str] = None,
               end: Optional[str] = None) -> Any:
    """cb_call：可转债赎回信息（强赎/到期赎回）。"""
    kw = {}
    if code:
        kw["ts_code"] = code
    if start:
        kw["start_date"] = start
    if end:
        kw["end_date"] = end
    return _req("cb_call", **kw)


def fetch_share(code: Optional[str] = None) -> Any:
    """cb_share：可转债转股结果。"""
    kw = {"ts_code": code} if code else {}
    return _req("cb_share", **kw)


def fetch_rate(code: str) -> Any:
    """cb_rate：可转债票面利率（需 fields 显式取全字段）。"""
    return _req(
        "cb_rate",
        ts_code=code,
        fields="ts_code,rate_freq,rate_start_date,rate_end_date,coupon_rate",
    )


def fetch_rating(code: Optional[str] = None) -> Any:
    """cb_rating：可转债债券评级。"""
    kw = {"ts_code": code} if code else {}
    return _req("cb_rating", **kw)


def fetch_holders(code: str) -> Any:
    """top10_cb_holders：可转债十大持有人。"""
    return _req("top10_cb_holders", ts_code=code)


# ======================================================================
#  聚合命令
# ======================================================================

def cmd_profile(code: str) -> Dict[str, Any]:
    """个券全维度档案：一次聚合 basic+issue+share+rate+rating+holders+call。

    返回结构化字典，包含：
      basic     基础信息（含 rate_clause 解析后的现金流表）
      issue     发行详情（规模/中签/配售）
      convert   转股进度（最新一期）
      rate      票面利率分年限表
      rating    评级历史
      holders   最新一期十大持有人
      call      强赎/到期赎回历史
      ytm       到期收益率（若价格/到期日可用）
    """
    code = code.upper().strip()
    profile: Dict[str, Any] = {"ts_code": code, "fetch_time": datetime.now().isoformat(timespec="seconds")}

    # 1. 基础信息
    basic_df = fetch_basic(code)
    if isinstance(basic_df, dict) and "error" in basic_df:
        profile["error"] = basic_df["error"]
        return profile
    if basic_df is None or basic_df.empty:
        profile["error"] = f"cb_basic 无 {code} 数据"
        return profile
    b = basic_df.iloc[0].to_dict()
    b = {k: (None if not _valid(v) else v) for k, v in b.items()}
    b["rate_clause_parsed"] = parse_rate_clause(b.get("rate_clause"))
    # 金额换算
    b["issue_size_yi"] = _yi(b.get("issue_size"))
    b["remain_size_yi"] = _yi(b.get("remain_size"))
    profile["basic"] = {
        "ts_code": b.get("ts_code"),
        "bond_full_name": b.get("bond_full_name"),
        "bond_short_name": b.get("bond_short_name"),
        "stk_code": b.get("stk_code"),
        "stk_short_name": b.get("stk_short_name"),
        "maturity": _num(b.get("maturity"), 1),
        "par": _num(b.get("par"), 2),
        "issue_price": _num(b.get("issue_price"), 2),
        "issue_size_yi": b.get("issue_size_yi"),
        "remain_size_yi": b.get("remain_size_yi"),
        "coupon_rate": _num(b.get("coupon_rate"), 2),
        "add_rate": _num(b.get("add_rate"), 2),
        "pay_per_year": b.get("pay_per_year"),
        "value_date": _fmt_date(b.get("value_date")),
        "maturity_date": _fmt_date(b.get("maturity_date")),
        "list_date": _fmt_date(b.get("list_date")),
        "delist_date": _fmt_date(b.get("delist_date")),
        "exchange": b.get("exchange"),
        "conv_start_date": _fmt_date(b.get("conv_start_date")),
        "conv_end_date": _fmt_date(b.get("conv_end_date")),
        "first_conv_price": _num(b.get("first_conv_price"), 4),
        "conv_price": _num(b.get("conv_price"), 4),
        "rate_clause": b.get("rate_clause"),
        "rate_clause_parsed": b.get("rate_clause_parsed"),
    }

    # 2. 发行详情
    issue_df = fetch_issue(code)
    if issue_df is not None and hasattr(issue_df, "empty") and not issue_df.empty:
        i = issue_df.iloc[0].to_dict()
        i = {k: (None if not _valid(v) else v) for k, v in i.items()}
        profile["issue"] = {
            "ann_date": _fmt_date(i.get("ann_date")),
            "res_ann_date": _fmt_date(i.get("res_ann_date")),
            "plan_issue_size_yi": _yi(i.get("plan_issue_size")),
            "issue_size_yi": _yi(i.get("issue_size")),
            "issue_price": _num(i.get("issue_price"), 2),
            "issue_type": i.get("issue_type"),
            "onl_code": i.get("onl_code"),
            "onl_name": i.get("onl_name"),
            "onl_date": _fmt_date(i.get("onl_date")),
            "onl_size": _num(i.get("onl_size"), 2),
            "onl_pch_excess": _num(i.get("onl_pch_excess"), 2),  # 网上超额认购倍数
            "shd_ration_code": i.get("shd_ration_code"),
            "shd_ration_name": i.get("shd_ration_name"),
            "shd_ration_date": _fmt_date(i.get("shd_ration_date")),
            "shd_ration_ratio": _num(i.get("shd_ration_ratio"), 4),  # 配售比例
        }
    else:
        profile["issue"] = None

    # 3. 转股进度（最新一期）
    share_df = fetch_share(code)
    if share_df is not None and hasattr(share_df, "empty") and not share_df.empty:
        s = share_df.iloc[0].to_dict()
        s = {k: (None if not _valid(v) else v) for k, v in s.items()}
        profile["convert"] = {
            "publish_date": _fmt_date(s.get("publish_date")),
            "end_date": _fmt_date(s.get("end_date")),
            "convert_price_initial": _num(s.get("convert_price_initial"), 4),
            "convert_price": _num(s.get("convert_price"), 4),
            "acc_convert_vol": _num(s.get("acc_convert_vol"), 2),
            "acc_convert_ratio": _num(s.get("acc_convert_ratio"), 4),
            "remain_size_yi": _yi(s.get("remain_size")),
            "total_shares": _num(s.get("total_shares"), 2),
        }
    else:
        profile["convert"] = None

    # 4. 票面利率分年限表
    rate_df = fetch_rate(code)
    if rate_df is not None and hasattr(rate_df, "empty") and not rate_df.empty:
        profile["rate"] = [
            {
                "start": _fmt_date(r["rate_start_date"]),
                "end": _fmt_date(r["rate_end_date"]),
                "rate": _num(r.get("coupon_rate"), 4),
                "freq": r.get("rate_freq"),
            }
            for _, r in rate_df.iterrows()
        ]
    else:
        profile["rate"] = None

    # 5. 评级历史
    rating_df = fetch_rating(code)
    if rating_df is not None and hasattr(rating_df, "empty") and not rating_df.empty:
        profile["rating"] = [
            {
                "ann_date": _fmt_date(r["ann_date"]),
                "rating_date": _fmt_date(r.get("rating_date")),
                "rating_com": r.get("rating_com_name"),
                "rating_way": r.get("rating_way"),
                "rating": r.get("rating"),
                "outlook": r.get("rating_outlook"),
            }
            for _, r in rating_df.iterrows()
        ]
    else:
        profile["rating"] = None

    # 6. 最新一期十大持有人
    holders_df = fetch_holders(code)
    if holders_df is not None and hasattr(holders_df, "empty") and not holders_df.empty:
        # 取 end_date 最大的那一期
        latest_end = holders_df["end_date"].max()
        h_latest = holders_df[holders_df["end_date"] == latest_end]
        profile["holders"] = {
            "end_date": _fmt_date(latest_end),
            "top10": [
                {
                    "rank": int(r["holder_rank"]),
                    "name": r["holder_name"],
                    "hold_amount": _num(r["hold_amount"], 4),  # 单位：亿元
                    "hold_ratio": _num(r["hold_ratio"], 2),   # %
                }
                for _, r in h_latest.iterrows()
            ],
        }
    else:
        profile["holders"] = None

    # 7. 强赎/到期赎回历史
    call_df = fetch_call(code)
    if call_df is not None and hasattr(call_df, "empty") and not call_df.empty:
        profile["call"] = [
            {
                "call_type": r.get("call_type"),
                "is_call": r.get("is_call"),
                "ann_date": _fmt_date(r["ann_date"]),
                "call_date": _fmt_date(r.get("call_date")),
                "call_price": _num(r.get("call_price"), 4),
                "call_price_tax": _num(r.get("call_price_tax"), 4),
            }
            for _, r in call_df.iterrows()
        ]
    else:
        profile["call"] = None

    # 8. YTM（若无强赎已实施，且到期日可用，则测算）
    basic_info = profile["basic"]
    if (profile.get("call") is None or
        all(c.get("is_call") != "公告实施强赎" for c in profile["call"])):
        # 取最新价格（cb_daily 最近一日）
        daily_df = fetch_daily(code)
        if daily_df is not None and hasattr(daily_df, "empty") and not daily_df.empty:
            latest = daily_df.iloc[0]
            price = float(latest["close"]) if _valid(latest.get("close")) else None
            trade_date = _fmt_date(latest.get("trade_date"))
            if price and price > 0:
                ytm = compute_ytm(profile.get("rate"), basic_info.get("maturity_date"),
                                  price, basic_info.get("par", 100))
                profile["ytm"] = {
                    "trade_date": trade_date,
                    "price": _num(price, 4),
                    "maturity_date": basic_info.get("maturity_date"),
                    "ytm": _num(ytm, 4) if ytm is not None else None,
                } if ytm is not None else None
                if ytm is None:
                    profile["ytm"] = {"trade_date": trade_date, "price": _num(price, 4),
                                      "ytm": None, "note": "到期日或现金流缺失，无法测算"}
            else:
                profile["ytm"] = None
        else:
            profile["ytm"] = None
    else:
        profile["ytm"] = {"note": "已公告实施强赎/到期赎回，YTM 不适用"}

    return profile


def compute_ytm(rate_table: Optional[List[Dict]], maturity_date: Optional[str],
                price: float, par: float = 100.0) -> Optional[float]:
    """基于 cb_rate 现金流表 + 当前价格 + 到期日，二分法反解 YTM。

    简化模型：
      - 每年付息一次（rate_freq=1），利率取当年对应 coupon_rate
      - 到期还本 + 最后一期利息
      - 剩余现金流 = 未来各年利息 + 到期本金
      - YTM = 使 现金流现值 = 价格 的年化折现率

    Args:
        rate_table: [{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "rate": 1.5}, ...]
        maturity_date: 到期日 "YYYY-MM-DD"
        price: 当前转债价格
        par: 面值（默认 100）

    Returns:
        ytm（小数，如 0.025 表示 2.5%），失败返回 None
    """
    if not rate_table or not maturity_date or price <= 0:
        return None
    today = datetime.now()
    try:
        mat = datetime.strptime(maturity_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    if mat <= today:
        return None  # 已到期

    # 构造未来现金流：每个利率区间的利息 + 到期本金
    cashflows: List[tuple] = []  # [(距今年数, 金额), ...]
    for seg in rate_table:
        try:
            seg_end = datetime.strptime(seg["end"], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if seg_end <= today:
            continue
        years = (seg_end - today).days / 365.25
        if years <= 0:
            continue
        coupon = par * seg["rate"] / 100.0
        cashflows.append((years, coupon))

    # 到期本金
    years_mat = (mat - today).days / 365.25
    cashflows.append((years_mat, par))

    if not cashflows:
        return None

    # 二分法：NPV(y) = sum(cf / (1+y)^t) - price = 0
    def npv(y):
        return sum(cf / (1 + y) ** t for t, cf in cashflows) - price

    # 区间扫描
    lo, hi = -0.5, 1.0
    try:
        n_lo = npv(lo)
        n_hi = npv(hi)
    except Exception:
        return None
    if n_lo * n_hi > 0:
        # 扩大区间再试一次
        lo, hi = -0.9, 2.0
        n_lo, n_hi = npv(lo), npv(hi)
        if n_lo * n_hi > 0:
            return None
    for _ in range(100):
        mid = (lo + hi) / 2
        n_mid = npv(mid)
        if abs(n_mid) < 1e-6:
            return mid
        if n_mid * n_lo < 0:
            hi = mid
            n_hi = n_mid
        else:
            lo = mid
            n_lo = n_mid
    return (lo + hi) / 2


def cmd_terms(code: str) -> Dict[str, Any]:
    """条款时间线：强赎公告历史 + 评级变迁 + 当前转股价。

    用于个券条款博弈分析——强赎窗口期、下修可能性、评级风险。
    """
    code = code.upper().strip()
    result: Dict[str, Any] = {"ts_code": code}

    # 强赎/到期历史
    call_df = fetch_call(code)
    if call_df is not None and hasattr(call_df, "empty") and not call_df.empty:
        calls = []
        for _, r in call_df.iterrows():
            calls.append({
                "ann_date": _fmt_date(r["ann_date"]),
                "call_type": r.get("call_type"),
                "is_call": r.get("is_call"),
                "call_date": _fmt_date(r.get("call_date")),
                "call_price": _num(r.get("call_price"), 4),
            })
        result["call_history"] = calls
        # 当前条款状态判断
        implemented = [c for c in calls if c["is_call"] == "公告实施强赎"]
        not_called = [c for c in calls if c["is_call"] == "公告不强赎"]
        if implemented:
            result["current_status"] = "已实施强赎（转股期结束前强制转股/赎回）"
        elif not_called:
            last = not_called[-1]
            result["current_status"] = f"最近公告不强赎（{last['ann_date']}），强赎窗口可能再次触发"
        else:
            result["current_status"] = "无强赎公告历史"
    else:
        result["call_history"] = []
        result["current_status"] = "无强赎公告历史"

    # 评级变迁
    rating_df = fetch_rating(code)
    if rating_df is not None and hasattr(rating_df, "empty") and not rating_df.empty:
        ratings = []
        for _, r in rating_df.iterrows():
            ratings.append({
                "ann_date": _fmt_date(r["ann_date"]),
                "rating": r.get("rating"),
                "outlook": r.get("rating_outlook"),
                "rating_com": r.get("rating_com_name"),
            })
        result["rating_history"] = ratings
        if ratings:
            result["latest_rating"] = ratings[0]
    else:
        result["rating_history"] = []

    # 当前转股价（从 cb_share 最新一期）
    share_df = fetch_share(code)
    if share_df is not None and hasattr(share_df, "empty") and not share_df.empty:
        s = share_df.iloc[0]
        result["convert_price"] = {
            "publish_date": _fmt_date(s.get("publish_date")),
            "current_conv_price": _num(s.get("convert_price"), 4),
            "initial_conv_price": _num(s.get("convert_price_initial"), 4),
            "acc_convert_ratio": _num(s.get("acc_convert_ratio"), 4),
        }
        # 下修判断
        init_p = s.get("convert_price_initial")
        curr_p = s.get("convert_price")
        if _valid(init_p) and _valid(curr_p) and float(init_p) > 0:
            chg = (float(curr_p) - float(init_p)) / float(init_p) * 100
            result["convert_price"]["downrev_pct"] = round(chg, 2)
            if chg < -5:
                result["convert_price"]["note"] = f"已下修 {abs(chg):.1f}%"
            elif chg < 0:
                result["convert_price"]["note"] = "小幅调整（分红/派息）"
            else:
                result["convert_price"]["note"] = "未下修"

    return result


def cmd_ytm(code: str) -> Dict[str, Any]:
    """YTM 测算：cb_rate 现金流贴现。"""
    code = code.upper().strip()
    # 取基础信息
    basic_df = fetch_basic(code)
    if basic_df is None or not hasattr(basic_df, "empty") or basic_df.empty:
        return {"ts_code": code, "error": "cb_basic 无数据"}
    b = basic_df.iloc[0]
    maturity_date = _fmt_date(b.get("maturity_date"))
    par = float(b.get("par") or 100)

    # 票面利率表
    rate_df = fetch_rate(code)
    if rate_df is None or not hasattr(rate_df, "empty") or rate_df.empty:
        return {"ts_code": code, "error": "cb_rate 无数据"}
    rate_table = [
        {"start": _fmt_date(r["rate_start_date"]), "end": _fmt_date(r["rate_end_date"]),
         "rate": float(r["coupon_rate"]), "freq": r.get("rate_freq")}
        for _, r in rate_df.iterrows()
    ]

    # 最新价格
    daily_df = fetch_daily(code)
    if daily_df is None or not hasattr(daily_df, "empty") or daily_df.empty:
        return {"ts_code": code, "error": "cb_daily 无价格数据"}
    latest = daily_df.iloc[0]
    price = float(latest["close"]) if _valid(latest.get("close")) else None
    if not price or price <= 0:
        return {"ts_code": code, "error": "最新价格无效"}
    trade_date = _fmt_date(latest.get("trade_date"))

    ytm = compute_ytm(rate_table, maturity_date, price, par)
    return {
        "ts_code": code,
        "bond_name": b.get("bond_short_name"),
        "trade_date": trade_date,
        "price": _num(price, 4),
        "par": par,
        "maturity_date": maturity_date,
        "coupon_rate_current": _num(b.get("coupon_rate"), 2),
        "rate_table": rate_table,
        "ytm": _num(ytm * 100, 4) if ytm is not None else None,
        "ytm_pct": f"{ytm*100:.2f}%" if ytm is not None else None,
    }


# ======================================================================
#  各接口的直接输出（基础命令）
# ======================================================================

def cmd_basic(code: Optional[str] = None) -> List[Dict]:
    df = fetch_basic(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    recs = df.to_dict("records")
    # 金额换算
    for r in recs:
        r["issue_size_yi"] = _yi(r.get("issue_size"))
        r["remain_size_yi"] = _yi(r.get("remain_size"))
        r["value_date_fmt"] = _fmt_date(r.get("value_date"))
        r["maturity_date_fmt"] = _fmt_date(r.get("maturity_date"))
        r["list_date_fmt"] = _fmt_date(r.get("list_date"))
        r["delist_date_fmt"] = _fmt_date(r.get("delist_date"))
    return recs


def cmd_daily(code: Optional[str], start: Optional[str], end: Optional[str]) -> List[Dict]:
    df = fetch_daily(code, start, end)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    return df.to_dict("records")


def cmd_issue(code: Optional[str]) -> List[Dict]:
    df = fetch_issue(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    recs = df.to_dict("records")
    for r in recs:
        r["plan_issue_size_yi"] = _yi(r.get("plan_issue_size"))
        r["issue_size_yi"] = _yi(r.get("issue_size"))
    return recs


def cmd_call(code: Optional[str], start: Optional[str], end: Optional[str]) -> List[Dict]:
    df = fetch_call(code, start, end)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    return df.to_dict("records")


def cmd_share(code: Optional[str]) -> List[Dict]:
    df = fetch_share(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    recs = df.to_dict("records")
    for r in recs:
        r["remain_size_yi"] = _yi(r.get("remain_size"))
    return recs


def cmd_rate(code: str) -> List[Dict]:
    df = fetch_rate(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    return [
        {
            "ts_code": r["ts_code"],
            "start": _fmt_date(r.get("rate_start_date")),
            "end": _fmt_date(r.get("rate_end_date")),
            "rate": _num(r.get("coupon_rate"), 4),
            "freq": r.get("rate_freq"),
        }
        for _, r in df.iterrows()
    ]


def cmd_rating(code: Optional[str]) -> List[Dict]:
    df = fetch_rating(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    return [
        {
            "ts_code": r["ts_code"],
            "ann_date": _fmt_date(r["ann_date"]),
            "rating_date": _fmt_date(r.get("rating_date")),
            "rating_com": r.get("rating_com_name"),
            "rating_way": r.get("rating_way"),
            "rating": r.get("rating"),
            "outlook": r.get("rating_outlook"),
        }
        for _, r in df.iterrows()
    ]


def cmd_holders(code: str) -> List[Dict]:
    df = fetch_holders(code)
    if isinstance(df, dict) and "error" in df:
        return df
    if df is None or df.empty:
        return []
    import pandas as pd
    df = df.where(pd.notna(df), None)
    return [
        {
            "ts_code": r["ts_code"],
            "end_date": _fmt_date(r["end_date"]),
            "rank": int(r["holder_rank"]),
            "name": r["holder_name"],
            "hold_amount": _num(r["hold_amount"], 4),
            "hold_ratio": _num(r["hold_ratio"], 2),
        }
        for _, r in df.iterrows()
    ]


# ======================================================================
#  CLI 主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="cb_data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
可转债 Tushare 数据访问层 — cb-data

封装 Tushare Pro 可转债 8 个接口 + 3 个聚合命令（profile/terms/ytm）。
数据源：Tushare Pro（kk_common 网关）；依赖 TUSHARE_TOKEN。

接口命令：
  basic      基础信息（全量或单券）
  daily      日线行情（按 ts_code 或日期）
  issue      发行数据（规模/中签/配售）
  call       赎回信息（强赎/到期赎回）
  share      转股结果（转股进度/累计转股率）
  rate       票面利率（分年限表）
  rating     债券评级历史
  holders    十大持有人

聚合命令：
  profile    个券全维度档案（一次聚合所有接口）
  terms      条款时间线（强赎/评级/下修）
  ytm        到期收益率测算

用法示例：
  python3 cb_data.py basic --code 128044.SZ
  python3 cb_data.py daily --code 128044.SZ --start 20260801
  python3 cb_data.py profile --code 128044.SZ
  python3 cb_data.py ytm --code 128044.SZ
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # basic
    p_basic = sub.add_parser("basic", help="基础信息")
    p_basic.add_argument("--code", "-c", help="转债代码（不传=全量）")

    # daily
    p_daily = sub.add_parser("daily", help="日线行情")
    p_daily.add_argument("--code", "-c", help="转债代码（不传=按日期全市场）")
    p_daily.add_argument("--start", "-s", help="起始日 YYYYMMDD")
    p_daily.add_argument("--end", "-e", help="结束日 YYYYMMDD")

    # issue
    p_issue = sub.add_parser("issue", help="发行数据")
    p_issue.add_argument("--code", "-c", help="转债代码（不传=全量）")

    # call
    p_call = sub.add_parser("call", help="赎回信息")
    p_call.add_argument("--code", "-c", help="转债代码")
    p_call.add_argument("--start", "-s", help="起始日")
    p_call.add_argument("--end", "-e", help="结束日")

    # share
    p_share = sub.add_parser("share", help="转股结果")
    p_share.add_argument("--code", "-c", help="转债代码")

    # rate
    p_rate = sub.add_parser("rate", help="票面利率")
    p_rate.add_argument("--code", "-c", required=True, help="转债代码")

    # rating
    p_rating = sub.add_parser("rating", help="债券评级")
    p_rating.add_argument("--code", "-c", help="转债代码")

    # holders
    p_holders = sub.add_parser("holders", help="十大持有人")
    p_holders.add_argument("--code", "-c", required=True, help="转债代码")

    # profile
    p_profile = sub.add_parser("profile", help="个券全维度档案")
    p_profile.add_argument("--code", "-c", required=True, help="转债代码")

    # terms
    p_terms = sub.add_parser("terms", help="条款时间线")
    p_terms.add_argument("--code", "-c", required=True, help="转债代码")

    # ytm
    p_ytm = sub.add_parser("ytm", help="到期收益率测算")
    p_ytm.add_argument("--code", "-c", required=True, help="转债代码")

    args = parser.parse_args()

    if args.cmd == "basic":
        result = cmd_basic(args.code)
    elif args.cmd == "daily":
        result = cmd_daily(args.code, args.start, args.end)
    elif args.cmd == "issue":
        result = cmd_issue(args.code)
    elif args.cmd == "call":
        result = cmd_call(args.code, args.start, args.end)
    elif args.cmd == "share":
        result = cmd_share(args.code)
    elif args.cmd == "rate":
        result = cmd_rate(args.code)
    elif args.cmd == "rating":
        result = cmd_rating(args.code)
    elif args.cmd == "holders":
        result = cmd_holders(args.code)
    elif args.cmd == "profile":
        result = cmd_profile(args.code)
    elif args.cmd == "terms":
        result = cmd_terms(args.code)
    elif args.cmd == "ytm":
        result = cmd_ytm(args.code)
    else:
        parser.print_help()
        return

    _json_out(result)


if __name__ == "__main__":
    main()
