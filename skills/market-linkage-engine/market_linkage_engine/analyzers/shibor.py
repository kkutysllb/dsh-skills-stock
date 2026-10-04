"""
7. Shibor 利率走势分析器

数据源：Tushare Pro shibor（银行间同业拆放利率）+ shibor_lpr（LPR 贷款基础利率）

输出维度：
  - 各期限 Shibor 最新值 & 环比变化（ON/1W/1M/3M/6M/1Y）
  - 短端（ON/1W）vs 长端（1Y）期限利差
  - 流动性松紧信号（Shibor 下行=流动性宽松偏多，上行=收紧偏空）
  - LPR 水平（1Y/5Y）作为宏观利率锚
  - 信号评分
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

import pandas as pd

from .base import BaseAnalyzer
from ..utils import pct_str, md_table
from ..config import SHIBOR_TERMS, DATA_SOURCE_TUSHARE


class ShiborAnalyzer(BaseAnalyzer):
    name = "Shibor 利率走势"
    dim_key = "shibor"

    def analyze(
        self, trade_date: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        df = self.fetcher.fetch_shibor(days=days * 2 + 10, end=trade_date)
        if len(df) == 0:
            res["summary"] = "无 Shibor 数据"
            return res

        # 列名：date + 各期限
        term_cols = {t: t for t in SHIBOR_TERMS if t in df.columns}
        # 兼容：若列名是 "1W" / "1M" 等
        if not term_cols:
            # 尝试找数字+字母的列
            for c in df.columns:
                if any(c.upper().endswith(t) for t in SHIBOR_TERMS):
                    term_cols[next(t for t in SHIBOR_TERMS if c.upper().endswith(t))] = c
        if not term_cols:
            res["summary"] = "Shibor 期限列缺失"
            return res

        df = df.sort_values("date").tail(days + 1).reset_index(drop=True)
        latest = df.iloc[-1]
        prev = df.iloc[0]
        detail: Dict[str, Any] = {
            "trade_date": latest["date"].strftime("%Y%m%d") if hasattr(latest["date"], "strftime") else str(latest["date"]),
            "terms": {},
        }

        signals: List[str] = []
        total_chg_bps = 0
        for term, col in term_cols.items():
            val = float(latest[col])
            chg = val - float(prev[col])  # bps（利率已是 %）
            total_chg_bps += chg
            detail["terms"][term] = {"value": val, "change_bps": chg}
            if abs(chg) > 5:  # 单期限变化超 5bps
                if chg < 0:
                    signals.append(f"🟢 {term} Shibor 下行 {abs(chg):.1f}bp，流动性宽松")
                else:
                    signals.append(f"🔴 {term} Shibor 上行 {chg:.1f}bp，流动性收紧")

        # 期限利差
        if "1Y" in detail["terms"] and "ON" in detail["terms"]:
            spread = detail["terms"]["1Y"]["value"] - detail["terms"]["ON"]["value"]
            detail["term_spread_1y_on"] = spread
            if spread < 0.2:
                signals.append("⚠️ 期限利差倒挂/极度平坦，市场预期经济承压")

        # LPR
        try:
            lpr = self.fetcher.fetch_shibor_lpr(days=720, end=trade_date)
            if len(lpr):
                detail["lpr_latest"] = lpr.iloc[-1].to_dict()
        except Exception:
            pass

        avg_chg = total_chg_bps / max(1, len(term_cols))
        if avg_chg < -2:
            score = 65; bias = "bullish"
            signals.append("🟢 Shibor 整体下行，流动性宽松对股市偏多")
        elif avg_chg > 2:
            score = 35; bias = "bearish"
            signals.append("🔴 Shibor 整体上行，流动性收紧对股市偏空")
        else:
            score = 50; bias = "neutral"
            signals.append("⚪ Shibor 整体平稳，流动性中性")

        res["score"] = score
        res["bias"] = bias
        res["summary"] = (
            f"Shibor {days}日平均变化 {avg_chg:+.1f}bp，"
            f"ON {detail['terms'].get('ON',{}).get('value','-')}% / 1Y {detail['terms'].get('1Y',{}).get('value','-')}%，"
            f"流动性 {bias}"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def to_markdown(self, result: Dict[str, Any]) -> str:
        d = result["detail"]
        lines = [f"### 7. {self.name}（{d.get('trade_date','')}）", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        terms = d.get("terms", {})
        rows = []
        for t in SHIBOR_TERMS:
            if t in terms:
                rows.append({
                    "期限": t,
                    "最新(%)": f"{terms[t]['value']:.3f}",
                    "变化(bp)": f"{terms[t]['change_bps']:+.1f}",
                })
        if rows:
            lines.append("\n" + md_table(pd.DataFrame(rows)))
        if d.get("term_spread_1y_on") is not None:
            lines.append(f"\n期限利差(1Y-ON)：**{d['term_spread_1y_on']:.3f}%**")
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
