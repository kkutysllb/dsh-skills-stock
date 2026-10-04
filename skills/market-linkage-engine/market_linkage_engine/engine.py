"""
市场联动分析引擎 — 核心编排器 (LinkageEngine)

将 8 大维度分析器聚合为统一报告：
  1. 主力资金流向       MainCapitalAnalyzer
  2. 北向资金流向       NorthboundAnalyzer
  3. 两融趋势           MarginAnalyzer
  4. 股指期货基差       FuturesBasisAnalyzer
  5. 7 大期权 ETF 波动率 OptionsVolatilityAnalyzer
  6. 9 大宽基 ETF 份额   BroadETFShareAnalyzer
  7. Shibor 利率走势     ShiborAnalyzer
  8. 龙虎榜分析         DragonTigerAnalyzer

提供：
  - run_daily(trade_date):  日度联动分析（所有维度，报告周期1-5日）
  - run_weekly(end_date):   周度联动分析（拉长窗口至20日，看中期趋势）
  - to_markdown(report):    生成完整 Markdown 报告
  - to_summary(report):     生成一句话市场情绪总结
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .data.fetcher import LinkageFetcher
from .analyzers import (
    MainCapitalAnalyzer,
    NorthboundAnalyzer,
    MarginAnalyzer,
    FuturesBasisAnalyzer,
    OptionsVolatilityAnalyzer,
    BroadETFShareAnalyzer,
    ShiborAnalyzer,
    DragonTigerAnalyzer,
)
from .utils import latest_trade_date, score_bar

logger = logging.getLogger("market_linkage_engine")


class LinkageEngine:
    """市场联动分析引擎主入口。"""

    def __init__(
        self,
        fetcher: Optional[LinkageFetcher] = None,
        use_iwencai: bool = False,
    ):
        self.fetcher = fetcher or LinkageFetcher(use_iwencai=use_iwencai)
        self.analyzers = {
            "main_capital":   MainCapitalAnalyzer(self.fetcher),
            "northbound":     NorthboundAnalyzer(self.fetcher),
            "margin":         MarginAnalyzer(self.fetcher),
            "futures_basis":  FuturesBasisAnalyzer(self.fetcher),
            "options_vol":    OptionsVolatilityAnalyzer(self.fetcher),
            "broad_etf_share": BroadETFShareAnalyzer(self.fetcher),
            "shibor":         ShiborAnalyzer(self.fetcher),
            "dragon_tiger":   DragonTigerAnalyzer(self.fetcher),
        }

    # ==================================================================
    #  日度分析
    # ==================================================================
    def run_daily(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """运行日度联动分析（8 大维度，短周期）。

        Parameters
        ----------
        trade_date : str, optional
            交易日期 YYYYMMDD，默认自动取最近交易日。
        """
        if trade_date is None:
            trade_date = latest_trade_date(self.fetcher)

        logger.info("开始日度联动分析，trade_date=%s", trade_date)
        report: Dict[str, Any] = {
            "report_type": "daily",
            "trade_date": trade_date,
            "generated_at": datetime.now().isoformat(),
            "dimensions": {},
        }

        # 逐维度分析（容错：单维度失败不影响其他）
        dims_config = {
            "main_capital":   {"trade_date": trade_date, "days": 1},
            "northbound":     {"trade_date": trade_date, "days": 5, "top10": True},
            "margin":         {"trade_date": trade_date, "days": 20},
            "futures_basis":  {"trade_date": trade_date, "days": 1},
            "options_vol":    {"trade_date": trade_date, "days": 5},
            "broad_etf_share": {"trade_date": trade_date, "days": 20},
            "shibor":         {"trade_date": trade_date, "days": 30},
            "dragon_tiger":   {"trade_date": trade_date, "days": 1},
        }
        for key, analyzer in self.analyzers.items():
            try:
                report["dimensions"][key] = analyzer.analyze(**dims_config[key])
            except Exception as e:
                logger.error("维度 %s 分析失败: %s", key, e)
                report["dimensions"][key] = {
                    "summary": f"分析失败: {e}",
                    "score": 50, "bias": "neutral",
                    "detail": {}, "signals": [], "data_source": "",
                }

        # 聚合综合判断
        report["overall"] = self._aggregate(report["dimensions"])
        return report

    # ==================================================================
    #  周度分析
    # ==================================================================
    def run_weekly(self, end_date: Optional[str] = None) -> Dict[str, Any]:
        """运行周度联动分析（拉长窗口，看中期趋势）。

        Parameters
        ----------
        end_date : str, optional
            周末日期 YYYYMMDD。
        """
        if end_date is None:
            end_date = latest_trade_date(self.fetcher)

        logger.info("开始周度联动分析，end_date=%s", end_date)
        report: Dict[str, Any] = {
            "report_type": "weekly",
            "trade_date": end_date,
            "generated_at": datetime.now().isoformat(),
            "dimensions": {},
        }

        dims_config = {
            "main_capital":   {"trade_date": end_date, "days": 5},
            "northbound":     {"trade_date": end_date, "days": 20, "top10": False},
            "margin":         {"trade_date": end_date, "days": 30},
            "futures_basis":  {"trade_date": end_date, "days": 5},
            "options_vol":    {"trade_date": end_date, "days": 10},
            "broad_etf_share": {"trade_date": end_date, "days": 20},
            "shibor":         {"trade_date": end_date, "days": 60},
            "dragon_tiger":   {"trade_date": end_date, "days": 5},
        }
        for key, analyzer in self.analyzers.items():
            try:
                report["dimensions"][key] = analyzer.analyze(**dims_config[key])
            except Exception as e:
                logger.error("维度 %s 分析失败: %s", key, e)
                report["dimensions"][key] = {
                    "summary": f"分析失败: {e}",
                    "score": 50, "bias": "neutral",
                    "detail": {}, "signals": [], "data_source": "",
                }

        report["overall"] = self._aggregate(report["dimensions"])
        return report

    # ==================================================================
    #  聚合 & 报告
    # ==================================================================
    @staticmethod
    def _aggregate(dimensions: Dict[str, Any]) -> Dict[str, Any]:
        """聚合 8 维度评分，输出综合判断。"""
        scores = [d["score"] for d in dimensions.values()]
        biases = [d["bias"] for d in dimensions.values()]
        valid_scores = [s for s in scores if s is not None]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 50
        bull = sum(1 for b in biases if b == "bullish")
        bear = sum(1 for b in biases if b == "bearish")

        if bull > bear and avg_score >= 58:
            sentiment = "偏多"
            action = "逢低布局，关注增量资金驱动的板块"
        elif bear > bull and avg_score <= 42:
            sentiment = "偏空"
            action = "控制仓位，防范资金流出与杠杆资金撤离风险"
        else:
            sentiment = "中性震荡"
            action = "结构性机会为主，紧盯北向资金与两融变化"

        return {
            "avg_score": round(avg_score, 1),
            "bull_count": bull,
            "bear_count": bear,
            "neutral_count": 8 - bull - bear,
            "sentiment": sentiment,
            "action": action,
        }

    def to_markdown(self, report: Dict[str, Any]) -> str:
        """生成完整 Markdown 报告。"""
        o = report["overall"]
        rt = "日度" if report["report_type"] == "daily" else "周度"
        lines = [
            f"# A 股市场联动分析报告（{rt}）",
            "",
            f"> 交易日：**{report['trade_date']}**  | 生成时间：{report['generated_at'][:19]}",
            "",
            "## 📊 综合判断",
            "",
            f"{score_bar(int(o['avg_score']))}",
            "",
            f"- **综合情绪：{o['sentiment']}**（{o['bull_count']} 偏多 / {o['neutral_count']} 中性 / {o['bear_count']} 偏空）",
            f"- **操作建议：** {o['action']}",
            "",
            "---",
            "",
            "## 🔍 八大维度分析",
            "",
        ]
        order = [
            ("main_capital",   self.analyzers["main_capital"]),
            ("northbound",     self.analyzers["northbound"]),
            ("margin",         self.analyzers["margin"]),
            ("futures_basis",  self.analyzers["futures_basis"]),
            ("options_vol",    self.analyzers["options_vol"]),
            ("broad_etf_share", self.analyzers["broad_etf_share"]),
            ("shibor",         self.analyzers["shibor"]),
            ("dragon_tiger",   self.analyzers["dragon_tiger"]),
        ]
        for key, analyzer in order:
            dim_result = report["dimensions"].get(key, {})
            try:
                lines.append(analyzer.to_markdown(dim_result))
            except Exception as e:
                lines.append(f"### {analyzer.name}\n\n_渲染失败: {e}_\n")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*数据来源：Tushare Pro API（T+1）" +
                      (" + 同花顺问财（实时）" if self.fetcher.use_iwencai else "") + "*")
        return "\n".join(lines)

    def to_summary(self, report: Dict[str, Any]) -> str:
        """一句话市场情绪总结。"""
        o = report["overall"]
        dims = report["dimensions"]
        key_signals = []
        for key in ("main_capital", "northbound", "margin"):
            d = dims.get(key, {})
            if d.get("summary"):
                key_signals.append(d["summary"])
        body = "；".join(key_signals) if key_signals else "各维度信号中性"
        return (
            f"【{report['trade_date']} 市场联动】综合评分 {o['avg_score']}/100，"
            f"{o['sentiment']}（偏多{o['bull_count']}/偏空{o['bear_count']}）。"
            f"{body}。建议：{o['action']}。"
        )
