"""
Ranking 模块 —— 选股打分排序实现

提供两类 RankStep：
- ``MockRankStep``：纯逻辑打分（无数据源依赖），用于离线自测/冒烟
- ``DataRankStep``：基于 DataAdapter 拉取真实数据的打分排序（问财/Tushare）

被 workflow_engine 的 quick_screen / ScreeningEngine 消费。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from workflow_engine import RankStep, StockResult

logger = logging.getLogger(__name__)


class MockRankStep(RankStep):
    """Mock 打分：低 PE 高分为主（纯逻辑，无网络）。"""

    def execute(self, data_and_strategies: Tuple[List[dict], List[Any]], context: dict) -> List[StockResult]:
        data, strategies = data_and_strategies
        results = []
        for i, d in enumerate(data):
            pe = d.get("pe_ttm") or d.get("pe") or 50
            pb = d.get("pb") or 10
            roe = d.get("roe") or 0
            score = max(0.0, 100 - float(pe) * 2 + float(roe) * 0.5 - float(pb) * 0.3)
            results.append(StockResult(
                code=str(d.get("code") or d.get("ts_code") or ""),
                name=str(d.get("name") or ""),
                price=round(float(d.get("close") or d.get("price") or 0), 2),
                change_pct=round(float(d.get("pct_chg") or 0), 2),
                scores={s.id: round(score, 2) for s, _ in strategies},
                signals={"pe_ttm": pe, "pb": pb, "roe": roe},
                total_score=round(score, 2),
                rank=i + 1,
            ))
        return sorted(results, key=lambda r: r.total_score, reverse=True)


class DataRankStep(RankStep):
    """真实数据打分：优先用策略自带的 scoring_fn，否则回退 Mock 打分逻辑。

    数据由 DataFetchStep 提供（问财查询结果 DataFrame 的 record 列表），
    本步骤只负责打分排序，不触碰数据源。
    """

    def __init__(self, top_n: int = 10):
        super().__init__()
        self.top_n = top_n

    def execute(self, data_and_strategies: Tuple[List[dict], List[Any]], context: dict) -> List[StockResult]:
        data, strategies = data_and_strategies
        if not data:
            return []

        # 尝试用每个策略的 scoring_fn 聚合打分；无策略匹配时用默认打分（低 PE 高分）
        results = []
        for i, d in enumerate(data):
            scores: dict[str, float] = {}
            if strategies:
                for s, params in strategies:
                    try:
                        if s.scoring_fn is not None:
                            vals = s.scoring_fn([d])
                            scores[s.id] = round(float(vals[0]), 2) if vals else 0.0
                        else:
                            pe = float(d.get("pe_ttm") or d.get("pe") or 50)
                            scores[s.id] = round(max(0.0, 100 - pe * 2), 2)
                    except Exception as exc:  # 单个策略打分失败不影响整体
                        logger.warning("strategy %s scoring failed: %s", s.id, exc)
                        scores[s.id] = 0.0
                total = round(sum(scores.values()) / max(len(scores), 1), 2)
            else:
                pe = _to_float(d.get("pe_ttm"), 50.0)
                pb = _to_float(d.get("pb"), 10.0)
                score = round(max(0.0, 100 - pe * 2 - pb * 0.3), 2)
                scores["default"] = score
                total = score
            results.append(StockResult(
                code=str(d.get("ts_code") or d.get("code") or ""),
                name=str(d.get("name") or ""),
                price=round(float(d.get("close") or 0), 2),
                change_pct=round(float(d.get("pct_chg") or 0), 2),
                scores=scores,
                signals={k: d.get(k) for k in ("pe_ttm", "pb", "roe", "total_mv") if k in d},
                total_score=total,
                rank=i + 1,
            ))

        ranked = sorted(results, key=lambda r: r.total_score, reverse=True)
        for idx, r in enumerate(ranked, start=1):
            r.rank = idx
        return ranked[: self.top_n]


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mock = MockRankStep()
    out = mock.execute(
        ([{"code": "600519", "name": "贵州茅台", "pe_ttm": 35.2, "pb": 9.8, "roe": 28.5}], []),
        {},
    )
    print("MockRankStep OK:", [(r.code, r.total_score) for r in out])
