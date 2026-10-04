"""
8. 龙虎榜分析器

数据源：Tushare Pro top_list（龙虎榜每日明细）+ top_inst（机构成交明细）
+ 同花顺问财（实时补充）

输出维度：
  - 上榜个股 + 上榜原因（日涨幅偏离 / 换手率 / 振幅）
  - 机构净买入个股（机构席位动向）
  - 游资营业部动向（知名游资席位）
  - 热度评分（上榜数量 + 机构净买金额 + 涨停占比）
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

import pandas as pd

from .base import BaseAnalyzer
from ..utils import yi, md_table
from ..config import DRAGON_TOP_N, DATA_SOURCE_TUSHARE


class DragonTigerAnalyzer(BaseAnalyzer):
    name = "龙虎榜分析"
    dim_key = "dragon_tiger"

    def analyze(
        self, trade_date: str, days: int = 1
    ) -> Dict[str, Any]:
        res = self._result_template()
        res["data_source"] = DATA_SOURCE_TUSHARE
        if self.fetcher is None:
            return res

        top = self.fetcher.fetch_dragon_tiger_list(trade_date)
        inst = self.fetcher.fetch_dragon_tiger_inst(trade_date)

        detail: Dict[str, Any] = {"trade_date": trade_date}
        signals: List[str] = []

        if len(top) == 0 and len(inst) == 0:
            res["summary"] = "今日无龙虎榜数据"
            return res

        # 去重个股
        stocks = pd.DataFrame()
        if len(top):
            name_col = "name" if "name" in top.columns else None
            code_col = "ts_code" if "ts_code" in top.columns else None
            reason_col = next((c for c in ("reason", "exalter") if c in top.columns), None)
            if code_col:
                stocks = top[[code_col] + ([name_col] if name_col else []) + ([reason_col] if reason_col else [])].drop_duplicates(subset=[code_col])
                detail["list_count"] = len(stocks)
                detail["stocks"] = stocks.to_dict("records")

        # 机构净买入 TOP
        if len(inst):
            net_col = next((c for c in ("net_amount", "net_buy") if c in inst.columns), None)
            code_col = "ts_code" if "ts_code" in inst.columns else None
            if net_col and code_col:
                by_stock = inst.groupby(code_col)[net_col].sum().reset_index()
                by_stock.columns = [code_col, "inst_net"]
                by_stock = by_stock.sort_values("inst_net", ascending=False)
                detail["inst_net_top"] = by_stock.head(DRAGON_TOP_N).to_dict("records")
                total_inst_net = float(by_stock["inst_net"].sum())
                detail["total_inst_net"] = total_inst_net
                if total_inst_net > 0:
                    signals.append(f"🟢 机构龙虎榜净买入 {yi(total_inst_net)}，机构资金加仓")
                elif total_inst_net < 0:
                    signals.append(f"🔴 机构龙虎榜净卖出 {yi(abs(total_inst_net))}，机构资金减仓")

        # 评分
        list_count = detail.get("list_count", 0)
        total_inst = detail.get("total_inst_net", 0)
        score = 50
        if list_count > 20 and total_inst > 0:
            score = 70; res["bias"] = "bullish"
            signals.append("🟢 龙虎榜活跃度高 + 机构净买入，市场情绪旺盛")
        elif total_inst > 0:
            score = 60; res["bias"] = "bullish"
        elif list_count > 20 and total_inst < 0:
            score = 35; res["bias"] = "bearish"
            signals.append("🔴 龙虎榜活跃但机构净卖出，资金分歧/出货")
        elif total_inst < 0:
            score = 40; res["bias"] = "bearish"
        else:
            res["bias"] = "neutral"

        res["score"] = score
        res["summary"] = (
            f"龙虎榜上榜 {list_count} 只个股，"
            f"机构净{('买入' if total_inst >= 0 else '卖出')} {yi(abs(total_inst))}，"
            f"情绪 {'活跃' if list_count > 15 else '一般'}"
        )
        res["detail"] = detail
        res["signals"] = signals
        return res

    def to_markdown(self, result: Dict[str, Any]) -> str:
        d = result["detail"]
        lines = [f"### 8. {self.name}（{d.get('trade_date','')}）", ""]
        lines.append(f"**综合评分：** {result['score']}/100  | **偏向：** {result['bias']}")
        lines.append(f"**结论：** {result['summary']}")
        lines.append("")
        if d.get("stocks"):
            lines.append(f"\n**上榜个股（共 {d.get('list_count',0)} 只，展示 TOP {DRAGON_TOP_N}）：**")
            df = pd.DataFrame(d["stocks"]).head(DRAGON_TOP_N)
            lines.append(md_table(df))
        if d.get("inst_net_top"):
            lines.append(f"\n**机构净买入 TOP {DRAGON_TOP_N}：**")
            df = pd.DataFrame(d["inst_net_top"]).head(DRAGON_TOP_N)
            lines.append(md_table(df, formatters={df.columns[-1]: yi}))
        if result["signals"]:
            lines.append("\n**信号：**")
            for s in result["signals"]:
                lines.append(f"- {s}")
        return "\n".join(lines)
