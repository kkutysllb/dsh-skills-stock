"""
4. 股指期货基差分析器

数据源：Tushare Pro fut_daily（股指期货日行情）+ index_daily（对应指数）
+ fut_holding（会员持仓）

覆盖品种：IF（沪深300）/ IC（中证500）/ IH（上证50）/ IM（中证1000）

输出维度：
  - 各品种主力合约基差 / 基差率
  - 升贴水信号（升水=多头情绪，贴水=空头情绪）
  - 多空持仓（前20 会员净持仓变化）
  - 信号评分（基差方向 + 期限结构）
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

import pandas as pd

from .base import BaseAnalyzer
from ..utils import yi, signal_cn, md_table, pct_str, safe_div
from ..config import INDEX_FUTURES, INDEX_NAMES, BASIS_STRONG_LONG, BASIS_STRONG_SHORT, DATA_SOURCE_TUSHARE


class FuturesBasisAnalyzer(BaseAnalyzer):
    name = "股指期货基差"
    dim_key = "futures_basis"

    def analyze(
        self, trade_date: Optional[str] = None, days: int = 1
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        detail: Dict[str, Any] = {"contracts": {}}
        signals: List[str] = []
        bull_count = 0
        bear_count = 0

        for variety, idx_code in INDEX_FUTURES.items():
            contract_info = self._analyze_variety(variety, idx_code, trade_date, days)
            detail["contracts"][variety] = contract_info
            if contract_info:
                basis_rate = contract_info.get("basis_rate", 0)
                # 升水（期货 > 现货）为正值 → 偏多；贴水为负值 → 偏空
                if basis_rate > BASIS_STRONG_LONG:
                    bull_count += 1
                    signals.append(
                        f"🟢 {variety}({INDEX_NAMES.get(idx_code, idx_code)}) "
                        f"升水 {pct_str(basis_rate)}，多头情绪"
                    )
                elif basis_rate < BASIS_STRONG_SHORT:
                    bear_count += 1
                    signals.append(
                        f"🔴 {variety}({INDEX_NAMES.get(idx_code, idx_code)}) "
                        f"贴水 {pct_str(basis_rate)}，空头情绪"
                    )

        # 综合评分
        total = len(INDEX_FUTURES)
        if bull_count > bear_count:
            score = 50 + 10 * (bull_count - bear_count)
            bias = "bullish"
        elif bear_count > bull_count:
            score = 50 - 10 * (bear_count - bull_count)
            bias = "bearish"
        else:
            score = 50
            bias = "neutral"
        score = max(0, min(100, score))
        if not signals:
            signals.append("⚪ 各品种基差波动不大，期指情绪中性")

        res["score"] = score
        res["bias"] = bias
        res["summary"] = (
            f"期指基差：{bull_count} 升水 / {bear_count} 贴水 / {total-bull_count-bear_count} 平衡，"
            f"信号 {bias}"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def _analyze_variety(self, variety: str, idx_code: str,
                         trade_date: Optional[str], days: int) -> Dict[str, Any]:
        """分析单个品种（自动取主力合约：当月或下月最新）。"""
        # 用 fut_basic 拿不到主力合约列表时，按规则构造 ts_code。
        # 简化：直接拉该品种最近日期的 fut_daily，取成交量最大的合约为主力
        try:
            # 取最近 5 个交易日的期货数据，过滤品种前缀
            df_fut = self.fetcher.fetch_futures_daily(ts_code="", days=30, end=trade_date)
        except Exception:
            df_fut = pd.DataFrame()

        if len(df_fut) and "ts_code" in df_fut.columns:
            df_v = df_fut[df_fut["ts_code"].str.startswith(variety)]
            if len(df_v):
                # 取最近一日 + 成交量最大合约
                latest_date = df_v["trade_date"].max()
                df_latest = df_v[df_v["trade_date"] == latest_date]
                main = df_latest.sort_values("vol", ascending=False).iloc[0]
                main_code = main["ts_code"]
                fut_close = float(main["close"])
                fut_settle = float(main.get("settle", main["close"]))
            else:
                return {}
        else:
            return {}

        # 对应指数点位
        idx_df = self.fetcher.fetch_index_daily(idx_code, days=5, end=trade_date)
        idx_close = float(idx_df.iloc[-1]["close"]) if len(idx_df) else 0.0

        if idx_close == 0:
            return {}

        # 基差 = 期货 - 现货（贴水为负，升水为正）
        basis = fut_settle - idx_close
        basis_rate = basis / idx_close * 100  # %
        net_long = None
        try:
            hold = self.fetcher.fetch_futures_holding(variety, trade_date=str(latest_date.strftime("%Y%m%d")), days=1)
            if len(hold) and "vol" in hold.columns and "long_" in hold.columns:
                # Tushare fut_holding 提供多空会员持仓
                long_total = hold[hold["side"] == "0"]["vol"].sum() if "side" in hold.columns else 0
                short_total = hold[hold["side"] == "1"]["vol"].sum() if "side" in hold.columns else 0
                net_long = long_total - short_total
        except Exception:
            pass

        return {
            "variety": variety,
            "index_name": INDEX_NAMES.get(idx_code, idx_code),
            "main_contract": main_code,
            "trade_date": latest_date.strftime("%Y%m%d") if hasattr(latest_date, "strftime") else str(latest_date),
            "fut_settle": fut_settle,
            "fut_close": fut_close,
            "index_close": idx_close,
            "basis": basis,
            "basis_rate": basis_rate,
            "net_long_holding": net_long,
            "signal": "升水偏多" if basis_rate > BASIS_STRONG_LONG
                      else ("贴水偏空" if basis_rate < BASIS_STRONG_SHORT else "基差中性"),
        }

    def to_markdown(self, result: Dict[str, Any]) -> str:
        lines = [f"### 4. {self.name}", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        contracts = result["detail"].get("contracts", {})
        if contracts:
            rows = []
            for v, c in contracts.items():
                if not c:
                    continue
                rows.append({
                    "品种": c["variety"],
                    "指数": c["index_name"],
                    "主力合约": c["main_contract"],
                    "期货结算价": f"{c['fut_settle']:.1f}",
                    "现货点位": f"{c['index_close']:.1f}",
                    "基差": f"{c['basis']:+.2f}",
                    "基差率": pct_str(c["basis_rate"]),
                    "信号": c["signal"],
                })
            if rows:
                lines.append("\n" + md_table(pd.DataFrame(rows)))
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
