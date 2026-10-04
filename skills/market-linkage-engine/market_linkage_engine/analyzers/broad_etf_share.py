"""
6. 9 大宽基 ETF 份额变化分析器

数据源：Tushare Pro fund_share（基金每日份额）+ fund_daily（净值/成交）

覆盖 9 大宽基 ETF：
  上证50ETF / 沪深300ETF(沪/深) / 中证500ETF / 中证1000ETF /
  创业板ETF / 科创50ETF / 上证180ETF / 红利ETF

输出维度：
  - 各 ETF 份额变化（周环比/月环比）
  - 份额变化与价格走势背离/同步信号
  - 主力资金借 ETF 布局的方向（份额增=净申购，看好；份额减=净赎回，看空）
  - 信号评分
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

import pandas as pd

from .base import BaseAnalyzer
from ..utils import wan, pct_str, md_table
from ..config import BROAD_ETFS, DATA_SOURCE_TUSHARE


class BroadETFShareAnalyzer(BaseAnalyzer):
    name = "宽基 ETF 份额变化"
    dim_key = "broad_etf_share"

    def analyze(
        self, trade_date: Optional[str] = None, days: int = 20
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        detail: Dict[str, Any] = {"etfs": {}}
        signals: List[str] = []
        increase = decrease = 0

        for code, name in BROAD_ETFS.items():
            info = self._analyze_etf(code, name, trade_date, days)
            detail["etfs"][code] = info
            if info:
                chg = info.get("share_chg_pct", 0)
                if chg > 2:
                    increase += 1
                    signals.append(f"🟢 {name} 份额净申购 {pct_str(chg)}，资金借道 ETF 布局")
                elif chg < -2:
                    decrease += 1
                    signals.append(f"🔴 {name} 份额净赎回 {pct_str(chg)}，资金撤出")

        total = len(BROAD_ETFS)
        if increase > decrease:
            score = 50 + 7 * (increase - decrease); bias = "bullish"
        elif decrease > increase:
            score = 50 - 7 * (decrease - increase); bias = "bearish"
        else:
            score = 50; bias = "neutral"
        score = max(0, min(100, score))
        if not signals:
            signals.append("⚪ 宽基 ETF 份额整体稳定，无明显申赎方向")

        res["score"] = score
        res["bias"] = bias
        res["summary"] = (
            f"9 大宽基 ETF：{increase} 净申购 / {decrease} 净赎回 / {total-increase-decrease} 持平，"
            f"ETF 资金流 {bias}"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def _analyze_etf(self, code: str, name: str,
                     trade_date: Optional[str], days: int) -> Dict[str, Any]:
        df = self.fetcher.fetch_fund_share(code, days=days * 2 + 10, end=trade_date)
        if len(df) == 0:
            return {}
        share_col = next((c for c in ("fd_share", "trade_sh", "share") if c in df.columns), None)
        if share_col is None:
            return {}
        df[share_col] = pd.to_numeric(df[share_col], errors="coerce")
        df = df.sort_values("trade_date").tail(days + 1).reset_index(drop=True)
        if len(df) < 2:
            return {}

        latest = float(df.iloc[-1][share_col])
        n_ago = float(df.iloc[0][share_col])
        chg = latest - n_ago
        chg_pct = (chg / n_ago * 100) if n_ago else 0

        # 价格走势
        price_chg = None
        try:
            fdf = self.fetcher.fetch_fund_daily(code, days=days + 5, end=trade_date)
            if len(fdf) >= 2:
                price_chg = (fdf.iloc[-1]["close"] - fdf.iloc[0]["close"]) / fdf.iloc[0]["close"] * 100
        except Exception:
            pass

        # 背离/同步判断
        divergence = ""
        if price_chg is not None:
            if chg > 0 and price_chg < 0:
                divergence = "份额增+价格跌（底部抄底信号）"
            elif chg < 0 and price_chg > 0:
                divergence = "份额减+价格涨（获利了结信号）"
            elif chg > 0 and price_chg > 0:
                divergence = "份额增+价格涨（趋势顺势）"
            elif chg < 0 and price_chg < 0:
                divergence = "份额减+价格跌（趋势顺势流出）"

        return {
            "etf_code": code,
            "etf_name": name,
            "trade_date": df.iloc[-1]["trade_date"].strftime("%Y%m%d"),
            "latest_share": latest,
            "share_chg": chg,
            "share_chg_pct": chg_pct,
            "price_chg": price_chg,
            "divergence": divergence,
            "signal": "净申购" if chg_pct > 2 else ("净赎回" if chg_pct < -2 else "持平"),
        }

    def to_markdown(self, result: Dict[str, Any]) -> str:
        lines = [f"### 6. {self.name}", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        etfs = result["detail"].get("etfs", {})
        rows = []
        for code, e in etfs.items():
            if not e:
                continue
            rows.append({
                "ETF": e["etf_name"],
                "最新份额": wan(e.get("latest_share", 0)),
                "份额变化": wan(e.get("share_chg", 0)),
                "变化率": pct_str(e.get("share_chg_pct", 0)),
                "价格涨跌": pct_str(e.get("price_chg") or 0),
                "背离/同步": e.get("divergence", ""),
                "信号": e.get("signal", ""),
            })
        if rows:
            lines.append("\n" + md_table(pd.DataFrame(rows)))
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
