"""
市场联动分析引擎 — 分析器基类

所有 8 大维度分析器继承自 BaseAnalyzer，提供统一接口：
  - analyze(trade_date, days): 返回 dict {summary, detail, signals, score}
  - to_markdown(result): 将分析结果转为 Markdown
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from ..data.fetcher import LinkageFetcher


class BaseAnalyzer:
    """分析器基类。

    子类必须实现：
      - name: 分析器中文名
      - dim_key: 维度英文键（用于引擎聚合）
      - analyze(): 核心分析逻辑
      - to_markdown(): 结果渲染（可选，默认空）
    """

    name: str = "Base"
    dim_key: str = "base"

    def __init__(self, fetcher: Optional[LinkageFetcher] = None):
        self.fetcher = fetcher

    def analyze(self, *args, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def to_markdown(self, result: Dict[str, Any]) -> str:
        return f"### {self.name}\n\n_详见结构化输出_\n"

    @staticmethod
    def _result_template() -> Dict[str, Any]:
        return {
            "summary": "",          # 一句话结论
            "detail": {},           # 详细数据
            "signals": [],          # 信号列表（字符串）
            "score": 50,            # 综合评分 0-100（>60 偏多, <40 偏空）
            "bias": "neutral",      # overall 偏向：bullish / bearish / neutral
            "data_source": "",
        }
