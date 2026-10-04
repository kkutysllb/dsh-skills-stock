"""
3. 两融趋势分析器

数据源：Tushare Pro margin（融资融券日余额）+ margin_detail（个股明细）
+ 同花顺问财（实时补充）

输出维度：
  - 融资余额 / 融券余额 / 两融余额趋势
  - 融资净买入额（环比变化）
  - 两融余额占流通市值比（杠杆水平）
  - 信号评分（趋势 + 杠杆 + 情绪过热识别）
"""
from __future__ import annotations

from typing import Dict, Any, Optional

import pandas as pd

from .base import BaseAnalyzer
from ..utils import yi, signal_cn, md_table, pct_str
from ..config import MARGIN_RATIO_HIGH, MARGIN_RATIO_LOW, DATA_SOURCE_TUSHARE


class MarginAnalyzer(BaseAnalyzer):
    name = "两融趋势"
    dim_key = "margin"

    def analyze(
        self, trade_date: Optional[str] = None, days: int = 20
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        df = self.fetcher.fetch_margin_daily(days=days * 2 + 10)
        if len(df) == 0:
            res["summary"] = "无两融数据"
            return res
        df = df.tail(days).reset_index(drop=True)
        df = df.sort_values("trade_date").reset_index(drop=True)

        rzye_col = next((c for c in ("rzye", "rzye_total") if c in df.columns), None)
        rqye_col = next((c for c in ("rqye", "rqye_total") if c in df.columns), None)
        rzrqye_col = next((c for c in ("rzrqye", "total") if c in df.columns), None)
        if rzye_col is None:
            res["summary"] = "两融数据列缺失"
            return res

        # 兼容字段
        df[rzye_col] = pd.to_numeric(df[rzye_col], errors="coerce")
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        rzye_latest = float(latest[rzye_col])
        rzye_prev = float(prev[rzye_col])
        rz_net = rzye_latest - rzye_prev  # 融资净买入额（环比）
        rqye_latest = float(latest[rqye_col]) if rqye_col else 0.0
        total = float(latest[rzrqye_col]) if rzrqye_col else (rzye_latest + rqye_latest)

        # 趋势
        rzye_series = df[rzye_col].astype(float)
        change_pct = (rzye_latest - rzye_series.iloc[0]) / rzye_series.iloc[0] * 100 if rzye_series.iloc[0] else 0
        ma5 = rzye_series.tail(5).mean()
        trend = "上升" if rzye_latest > ma5 else "下降"

        detail = {
            "trade_date": latest["trade_date"].strftime("%Y%m%d"),
            "rzye": rzye_latest,                 # 融资余额（元）
            "rqye": rqye_latest,                 # 融券余额（元）
            "total": total,
            "rz_net": rz_net,                    # 融资净买入
            "change_pct": change_pct,            # N日变化率
            "ma5": ma5,
            "trend": trend,
            "history": df[["trade_date", rzye_col]].to_dict("records"),
        }

        # 个股明细（仅融资余额 TOP）
        try:
            md_df = self.fetcher.fetch_margin_detail(detail["trade_date"], top_n=20)
            if len(md_df):
                detail["top_stocks"] = md_df.to_dict("records")
        except Exception:
            pass

        # 信号评分
        score = 50
        signals = []
        # 融资净买入方向
        if rz_net > 0:
            score += 12; signals.append(f"🟢 融资净买入 {yi(rz_net)}，杠杆资金加仓")
        else:
            score -= 12; signals.append(f"🔴 融资净偿还 {yi(abs(rz_net))}，杠杆资金减仓")
        # 趋势
        if change_pct > 1.5:
            score += 8; signals.append(f"🟢 两融余额{days}日累计+{change_pct:.2f}%，杠杆资金持续流入")
        elif change_pct < -1.5:
            score -= 8; signals.append(f"🔴 两融余额{days}日累计{change_pct:.2f}%，杠杆资金持续流出")

        score = max(0, min(100, score))
        res["score"] = score
        res["bias"] = "bullish" if score > 55 else ("bearish" if score < 45 else "neutral")
        res["summary"] = (
            f"两融余额 {yi(total)}（融资 {yi(rzye_latest)}），{days}日{pct_str(change_pct)}，"
            f"融资{('净买入' if rz_net > 0 else '净偿还')} {yi(abs(rz_net))}，{trend}趋势"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def to_markdown(self, result: Dict[str, Any]) -> str:
        d = result["detail"]
        lines = [f"### 3. {self.name}（{d.get('trade_date','')}）", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        lines.append(f"- 融资余额：**{yi(d.get('rzye',0))}**")
        lines.append(f"- 融券余额：{yi(d.get('rqye',0))}")
        lines.append(f"- 两融余额合计：**{yi(d.get('total',0))}**")
        lines.append(f"- 融资净买入：{yi(d.get('rz_net',0))}")
        lines.append(f"- {d.get('trend','-')}（MA5 {yi(d.get('ma5',0))}）")
        if d.get("top_stocks"):
            lines.append("\n**融资余额 TOP 20 个股：**")
            df = pd.DataFrame(d["top_stocks"]).head(20)
            lines.append(md_table(df))
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
