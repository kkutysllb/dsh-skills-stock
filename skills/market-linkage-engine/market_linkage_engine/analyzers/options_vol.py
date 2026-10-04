"""
5. 7 大期权 ETF 波动率分析器

数据源：Tushare Pro opt_daily（期权日线含隐含波动率）+ index_daily

覆盖 7 大场内期权标的 ETF：
  上证50ETF / 沪深300ETF / 中证500ETF / 中证1000ETF / 创业板ETF / 科创50ETF / 深100ETF

输出维度：
  - 各标的认购/认沽成交量比（PCR）
  - 隐含波动率 IV 水平 + IV 变化
  - 期权市场情绪（PCR + IV 综合判断）
  - 信号评分
"""
from __future__ import annotations

import math
from typing import Dict, Any, Optional, List

import pandas as pd

from .base import BaseAnalyzer
from ..utils import pct_str, md_table
from ..config import OPTION_ETFS, OPTION_ETFS_INDEX, INDEX_NAMES, DATA_SOURCE_TUSHARE


# ETF 期权 name 关键词（opt_basic 的 name 形如 "50ETF购8月3000" / "科创50购3月1700"）
OPTION_NAME_KEYWORDS = {
    "510050.SH": ["50ETF"],
    "510300.SH": ["300ETF"],
    "510500.SH": ["500ETF"],
    "512100.SH": ["中证1000"],
    "588000.SH": ["科创50"],
    "159915.SZ": ["创业板"],
    "159901.SZ": ["深证100"],
}

# 期权品种 → (交易所, 标的价格来源, 中金所 opt_code)
# 中证1000 用中金所股指期权（IM，标的就是 000852 指数，行权价为点位量级）
# 其余 6 只为 ETF 期权（标的为 ETF 价格，行权价为元量级）
OPTION_SOURCE = {
    "510050.SH": ("SSE", "etf", None),
    "510300.SH": ("SSE", "etf", None),
    "510500.SH": ("SSE", "etf", None),
    "512100.SH": ("CFFEX", "index", "OP000852.SH"),
    "588000.SH": ("SSE", "etf", None),
    "159915.SZ": ("SZSE", "etf", None),
    "159901.SZ": ("SZSE", "etf", None),
}


def _implied_vol(spot: float, K: float, T: float, price: float, is_call: bool,
                 lo: float = 1e-4, hi: float = 5.0) -> Optional[float]:
    """二分法反解 BS 隐含波动率（纯标准库，无 scipy 依赖）。"""
    if spot <= 0 or K <= 0 or T <= 0 or price <= 0:
        return None
    intrinsic = max(spot - K, 0) if is_call else max(K - spot, 0)
    if price <= intrinsic + 1e-9:
        return None
    sqrt_t = math.sqrt(T)

    def _ncdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _bs(sig: float) -> float:
        d1 = (math.log(spot / K) + 0.5 * sig * sig * T) / (sig * sqrt_t)
        d2 = d1 - sig * sqrt_t
        if is_call:
            return spot * _ncdf(d1) - K * _ncdf(d2)
        return K * _ncdf(-d2) - spot * _ncdf(-d1)

    try:
        if price < _bs(lo) or price > _bs(hi):
            return None
        for _ in range(60):
            mid = (lo + hi) / 2.0
            if _bs(mid) < price:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0
    except Exception:
        return None


class OptionsVolatilityAnalyzer(BaseAnalyzer):
    name = "期权 ETF 波动率"
    dim_key = "options_vol"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._basic_cache: Dict[str, pd.DataFrame] = {}

    def _get_basic(self, exchange: str) -> pd.DataFrame:
        if exchange not in self._basic_cache:
            self._basic_cache[exchange] = self.fetcher.fetch_option_basic(exchange)
        return self._basic_cache[exchange]

    def analyze(
        self, trade_date: Optional[str] = None, days: int = 5
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        detail: Dict[str, Any] = {"etfs": {}}
        signals: List[str] = []
        bull = bear = missing = 0

        for etf_code, etf_name in OPTION_ETFS.items():
            info = self._analyze_etf(etf_code, etf_name, trade_date, days)
            detail["etfs"][etf_code] = info
            if not info or info.get("error"):
                missing += 1
                if info and info.get("error"):
                    signals.append(f"⚠️ {etf_name}：{info['error']}")
                continue
            pcr = info.get("pcr", 1.0)
            if pcr < 0.7:       # 认购活跃，偏多
                bull += 1
                signals.append(f"🟢 {etf_name} PCR={pcr:.2f}，认购活跃偏多")
            elif pcr > 1.3:     # 认沽活跃，偏空/避险
                bear += 1
                signals.append(f"🔴 {etf_name} PCR={pcr:.2f}，认沽活跃避险情绪")

        total = len(OPTION_ETFS)
        if bull > bear:
            score = 50 + 8 * (bull - bear); bias = "bullish"
        elif bear > bull:
            score = 50 - 8 * (bear - bull); bias = "bearish"
        else:
            score = 50; bias = "neutral"
        score = max(0, min(100, score))
        if not signals:
            signals.append("⚪ 期权 PCR 整体中性，无明显避险或追涨情绪")

        res["score"] = score
        res["bias"] = bias
        res["summary"] = (
            f"7 大期权 ETF：{bull} 认购活跃 / {bear} 认沽活跃 / {total-bull-bear-missing} 中性 / "
            f"{missing} 无数据，PCR 整体 {bias}"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def _analyze_etf(self, etf_code: str, etf_name: str,
                     trade_date: Optional[str], days: int) -> Dict[str, Any]:
        """分析单个期权品种：opt_basic 合约信息 + opt_daily 行情 → PCR / ATM IV。

        中证1000 走中金所（CFFEX）股指期权（IM，opt_code=OP000852，标的是 000852 指数）；
        其余 6 只为 ETF 期权（SSE/SZSE，标的是 ETF 价格）。
        """
        exchange, src_type, opt_code = OPTION_SOURCE.get(etf_code, ("SSE", "etf", None))
        basic = self._get_basic(exchange)
        if basic.empty or "call_put" not in basic.columns:
            return {"etf_code": etf_code, "etf_name": etf_name,
                    "error": f"opt_basic({exchange}) 无 call_put 字段（数据权限受限）"}

        # 合约过滤：CFFEX 按 opt_code 精确匹配；ETF 期权按 name 关键词
        if exchange == "CFFEX" and opt_code:
            contracts = basic[basic.get("opt_code") == opt_code] if "opt_code" in basic.columns else basic
        else:
            keywords = OPTION_NAME_KEYWORDS.get(etf_code, [etf_name[:4]])
            mask = pd.Series([False] * len(basic), index=basic.index)
            for kw in keywords:
                mask |= basic["name"].astype(str).str.contains(kw, na=False)
            contracts = basic[mask]
        if contracts.empty:
            return {"etf_code": etf_code, "etf_name": etf_name,
                    "error": f"未匹配到 {etf_name} 期权合约"}

        # 拉行情并按合约代码合并
        try:
            df = self.fetcher.fetch_option_daily(trade_date=trade_date, days=days, exchange=exchange)
        except Exception:
            df = pd.DataFrame()
        if len(df) == 0:
            return {"etf_code": etf_code, "etf_name": etf_name, "error": "opt_daily 无数据"}
        valid_codes = set(contracts["ts_code"])
        merged = df[df["ts_code"].isin(valid_codes)].merge(
            contracts[["ts_code", "call_put", "exercise_price", "maturity_date"]],
            on="ts_code", how="left")
        merged = merged[merged["call_put"].notna()]
        if merged.empty:
            return {"etf_code": etf_code, "etf_name": etf_name, "error": "本品种无成交"}
        for c in ("vol", "oi", "settle"):
            if c in merged.columns:
                merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

        # 最新交易日（trade_date 可能为 datetime / int / str，统一为 YYYYMMDD）
        latest_raw = merged["trade_date"].max()
        latest_date = latest_raw.strftime("%Y%m%d") if hasattr(latest_raw, "strftime") else str(latest_raw)
        today = merged[merged["trade_date"] == latest_raw].copy()
        if today.empty:
            return {"etf_code": etf_code, "etf_name": etf_name, "error": "最新交易日无成交"}

        # 认沽/认购成交与持仓 PCR
        calls = today[today["call_put"].astype(str).str.upper().str.startswith("C")]
        puts = today[~today["call_put"].astype(str).str.upper().str.startswith("C")]
        call_vol = float(calls["vol"].sum())
        put_vol = float(puts["vol"].sum())
        call_oi = float(calls["oi"].sum())
        put_oi = float(puts["oi"].sum())
        pcr = round(put_vol / call_vol, 2) if call_vol > 0 else None
        pcr_oi = round(put_oi / call_oi, 2) if call_oi > 0 else None

        # 隐含波动率：标的价 + 活跃合约 BS 反解 → ATM（剩余期限≤60天、|moneyness-1| 最小）
        # 注意：ETF 期权用 ETF 价格（行权价元量级）；中证1000 股指期权用指数点位（行权价点位量级）
        idx_code = OPTION_ETFS_INDEX.get(etf_code)
        idx_chg = None
        spot = None
        try:
            if src_type == "etf":
                fund_df = self.fetcher.fetch_fund_daily(etf_code, days=3, end=trade_date)
                if len(fund_df):
                    spot = float(fund_df.iloc[-1]["close"])
            elif idx_code:
                idx_df = self.fetcher.fetch_index_daily(idx_code, days=3, end=trade_date)
                if len(idx_df):
                    spot = float(idx_df.iloc[-1]["close"])
        except Exception:
            pass
        if idx_code:
            try:
                idx_df = self.fetcher.fetch_index_daily(idx_code, days=3, end=trade_date)
                if len(idx_df) >= 2:
                    idx_chg = (idx_df.iloc[-1]["close"] - idx_df.iloc[-2]["close"]) / idx_df.iloc[-2]["close"] * 100
            except Exception:
                pass
        iv = atm_iv = None
        ivs: List[Dict[str, Any]] = []
        if spot and spot > 0 and "exercise_price" in merged.columns:
            active = today[(today["vol"] > 0) & (today["settle"] > 0)]
            for _, r in active.iterrows():
                try:
                    T = max((pd.to_datetime(str(r["maturity_date"])).date()
                             - pd.to_datetime(latest_date).date()).days, 1) / 365.0
                    iv_i = _implied_vol(spot, float(r["exercise_price"]), T, float(r["settle"]),
                                        r["call_put"].upper().startswith("C"))
                    if iv_i is not None:
                        ivs.append({"iv": iv_i, "moneyness": float(r["exercise_price"]) / spot, "T": T,
                                    "vol": float(r["vol"])})
                except Exception:
                    continue
            if ivs:
                iv = round(sum(x["iv"] * x["vol"] for x in ivs) / sum(x["vol"] for x in ivs), 4)
                near = [x for x in ivs if x["T"] <= 60 / 365]
                if near:
                    atm = min(near, key=lambda x: abs(x["moneyness"] - 1.0))
                    atm_iv = round(atm["iv"] * 100, 2)

        signal = "认购活跃偏多" if (pcr or 1.0) < 0.7 else ("认沽活跃偏空" if (pcr or 1.0) > 1.3 else "情绪中性")
        return {
            "etf_code": etf_code,
            "etf_name": etf_name,
            "index_name": INDEX_NAMES.get(idx_code, "") if idx_code else "",
            "trade_date": latest_date,
            "index_chg": idx_chg,
            "call_vol": call_vol,
            "put_vol": put_vol,
            "pcr": pcr if pcr is not None else 1.0,
            "pcr_oi": pcr_oi,
            "iv": iv,
            "atm_iv": atm_iv,
            "signal": signal,
        }

    def to_markdown(self, result: Dict[str, Any]) -> str:
        lines = [f"### 5. {self.name}", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        etfs = result["detail"].get("etfs", {})
        rows = []
        for code, e in etfs.items():
            if not e:
                continue
            if e.get("error"):
                rows.append({"标的": e.get("etf_name", code), "对应指数": e.get("index_name", ""),
                             "指数涨跌": "-", "认购量": "-",
                             "认沽量": "-", "PCR(量)": "-", "PCR(持仓)": "-", "ATM IV": "-",
                             "信号": f"⚠️ {e['error']}"})
                continue
            rows.append({
                "标的": e["etf_name"],
                "对应指数": e.get("index_name", ""),
                "指数涨跌": pct_str(e.get("index_chg") or 0),
                "认购量": f"{e.get('call_vol',0):.0f}",
                "认沽量": f"{e.get('put_vol',0):.0f}",
                "PCR(量)": f"{e.get('pcr',1):.2f}",
                "PCR(持仓)": f"{e.get('pcr_oi',1):.2f}" if e.get("pcr_oi") else "-",
                "ATM IV": f"{e.get('atm_iv',0):.2f}%" if e.get("atm_iv") else "-",
                "信号": e.get("signal", ""),
            })
        if rows:
            lines.append("\n" + md_table(pd.DataFrame(rows)))
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
