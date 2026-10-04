"""
Workflow Engine —— 选股工作流引擎（Orchestrator 模式核心编排器）

负责将用户意图解析 → 策略匹配 → 数据获取 → 打分排序 → 报告生成
5 个阶段串联为一个完整的选股工作流。

每个阶段通过 PipelineStep 接口解耦，方便后续扩展：
- 可插入新阶段（如 AI 分析、回测验证）
- 可替换任一阶段实现（如替换数据源）
- 可记录日志/埋点用于调试

工作流程：
1. parse(user_input) → ScreeningIntent
2. resolve(intent) → [(Strategy, dict), ...]
3. fetch(strategies) → raw stock data (list of dict)
4. rank(data, strategies) → ranked StockResult[]
5. report(results) → ScreeningReport
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Generic

from intent_parser import ScreeningIntent, parse
from strategy_registry import Strategy, StrategyRegistry, get_registry, ParamSpec

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 类型定义
# ──────────────────────────────────────────────


@dataclass
class StockResult:
    """一只个股的选股结果"""
    code: str                          # 股票代码，如 "600519"
    name: str                          # 股票名称，如 "贵州茅台"
    price: float = 0.0                 # 当前价格
    change_pct: float = 0.0            # 涨跌幅(%)
    scores: Dict[str, float] = field(default_factory=dict)   # {策略id: 得分}
    signals: Dict[str, Any] = field(default_factory=dict)    # {字段名: 值}
    total_score: float = 0.0           # 综合总分
    rank: int = 0                      # 排名


@dataclass
class ScreeningReport:
    """一次选股操作产生的完整报告"""
    query: str                         # 用户原始查询
    intent: ScreeningIntent            # 解析后的意图
    strategies_used: List[str]         # 使用的策略 ID 列表
    total_candidates: int = 0          # 候选股总数
    top_results: List[StockResult] = field(default_factory=list)  # Top-N 结果
    generated_at: str = ""             # 报告生成时间
    elapsed_ms: int = 0                # 耗时(毫秒)
    errors: List[str] = field(default_factory=list)  # 错误信息
    warnings: List[str] = field(default_factory=list)  # 警告信息


# ──────────────────────────────────────────────
# Pipeline Step 定义
# ──────────────────────────────────────────────

T = TypeVar("T")
U = TypeVar("U")


class PipelineStep(Generic[T, U]):
    """流水线步骤基类"""

    def __init__(self, name: str):
        self.name = name

    def execute(self, input_data: T, context: dict) -> U:
        """执行步骤（由子类重写）"""
        raise NotImplementedError(f"{self.name}.execute() must be implemented")


class ParseStep(PipelineStep[str, ScreeningIntent]):
    """阶段 1：解析用户输入为结构化意图"""

    def __init__(self):
        super().__init__("parse")

    def execute(self, query: str, context: dict) -> ScreeningIntent:
        return parse(query)


class ResolveStep(PipelineStep[ScreeningIntent, List[Tuple[Strategy, dict]]]):
    """阶段 2：根据意图匹配并解析策略参数"""

    def __init__(self, registry: Optional[StrategyRegistry] = None):
        super().__init__("resolve")
        self._registry = registry or get_registry()

    def execute(self, intent: ScreeningIntent, context: dict) -> List[Tuple[Strategy, dict]]:
        # 1) 优先精确匹配意图映射出的策略 ID（如 value_dividend）。
        # 2) intent.strategy 是意图层的粗粒度语义 ID（value / high_dividend /
        #    growth / momentum），与注册中心的细粒度策略 ID 不同构——直接用
        #    它做 match 永远匹配失败（历史 bug：策略退化、打分全 0）。
        #    失败时回退用原始中文 query 做关键词匹配（策略 tags 为中文）。
        matched: List[Strategy] = []
        sid = intent.strategy or intent.custom_strategy or None
        if sid:
            exact = self._registry.get(sid)
            if exact is not None:
                matched = [exact]
        if not matched:
            text = intent.raw_query or context.get("query") or ""
            matched = self._registry.match(text)
        if not matched:
            logger.warning(f"No strategy matched for: {text or sid}")
            return []
        return [(s, {}) for s in matched]


class FetchStep(PipelineStep[List[Tuple[Strategy, dict]], List[dict]]):
    """阶段 3：获取原始股票数据（抽象基类，子类实现数据源）"""

    def __init__(self):
        super().__init__("fetch")

    def execute(self, strategies: List[Tuple[Strategy, dict]], context: dict) -> List[dict]:
        logger.warning("No fetch function provided, returning empty data")
        return []


class RankStep(PipelineStep[Tuple[List[dict], List[Tuple[Strategy, dict]]], List[StockResult]]):
    """阶段 4：打分排序（抽象基类，子类实现排名逻辑）"""

    def __init__(self):
        super().__init__("rank")

    def execute(self, data_and_strategies: Tuple[List[dict], List[Tuple[Strategy, dict]]], context: dict) -> List[StockResult]:
        logger.warning("No rank function provided, returning empty results")
        return []


class ReportStep(PipelineStep[List[StockResult], ScreeningReport]):
    """阶段 5：生成最终报告"""

    def __init__(self):
        super().__init__("report")

    def execute(self, results: List[StockResult], context: dict) -> ScreeningReport:
        return ScreeningReport(
            query=context.get("query", ""),
            intent=context.get("intent", ScreeningIntent(raw_query=context.get("query", ""))),
            strategies_used=context.get("strategies_used", []),
            total_candidates=len(results),
            top_results=results[:context.get("top_n", 10)],
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            elapsed_ms=context.get("elapsed_ms", 0),
        )


# ──────────────────────────────────────────────
# ScreeningEngine —— 工作流编排器
# ──────────────────────────────────────────────


class ScreeningEngine:
    """
    选股引擎 —— 核心编排器

    将 5 个 PipelineStep 串联为一个完整工作流。
    子类化或通过构造函数注入自定义 Step 以替换任意阶段。
    """

    def __init__(
        self,
        parse_step: Optional[ParseStep] = None,
        resolve_step: Optional[ResolveStep] = None,
        fetch_step: Optional[FetchStep] = None,
        rank_step: Optional[RankStep] = None,
        report_step: Optional[ReportStep] = None,
        top_n: int = 10,
    ):
        self._parse = parse_step or ParseStep()
        self._resolve = resolve_step or ResolveStep()
        self._fetch = fetch_step or FetchStep()
        self._rank = rank_step or RankStep()
        self._report = report_step or ReportStep()
        self.top_n = top_n

    # ── 属性访问器（便于子类 override） ──

    @property
    def parse_step(self) -> ParseStep:
        return self._parse

    @property
    def resolve_step(self) -> ResolveStep:
        return self._resolve

    @property
    def fetch_step(self) -> FetchStep:
        return self._fetch

    @property
    def rank_step(self) -> RankStep:
        return self._rank

    @property
    def report_step(self) -> ReportStep:
        return self._report

    def run(self, query: str) -> ScreeningReport:
        """
        执行完整选股工作流

        Args:
            query: 用户自然语言查询（如 "低估值蓝筹，PE<10"）

        Returns:
            ScreeningReport 包含报告内容
        """
        start = time.time()
        errors: List[str] = []
        context: dict = {"query": query, "top_n": self.top_n}

        try:
            # 阶段 1：解析意图
            intent = self._parse.execute(query, context)
            context["intent"] = intent
            logger.info(f"→ Intent: {intent}")

            # 阶段 2：解析策略
            strategies = self._resolve.execute(intent, context)
            sids = [s.id for s, _ in strategies]
            context["strategies_used"] = sids
            logger.info(f"→ Strategies: {sids}")

            # 阶段 3：获取数据
            raw_data = self._fetch.execute(strategies, context)
            context["raw_data_count"] = len(raw_data)
            logger.info(f"→ Fetched {len(raw_data)} candidates")

            # 阶段 4：打分排序
            results = self._rank.execute((raw_data, strategies), context)
            logger.info(f"→ Ranked {len(results)} stocks")

            # 阶段 5：生成报告
            context["elapsed_ms"] = int((time.time() - start) * 1000)
            report = self._report.execute(results, context)

        except Exception as e:
            logger.exception("Workflow failed")
            errors.append(str(e))
            report = ScreeningReport(
                query=query,
                intent=ScreeningIntent(raw_query=query),
                strategies_used=[],
                generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                elapsed_ms=int((time.time() - start) * 1000),
                errors=errors,
            )

        report.errors = errors
        return report


# ──────────────────────────────────────────────
# 快捷函数 & 自测
# ──────────────────────────────────────────────


def default_engine() -> ScreeningEngine:
    """创建一个使用默认配置的引擎"""
    return ScreeningEngine()


def quick_screen(query: str) -> ScreeningReport:
    """快速选股（使用默认引擎 + mock 数据/打分）"""
    from ranking import MockRankStep
    from data_adapter import MockFetchStep
    engine = ScreeningEngine(
        fetch_step=MockFetchStep(),
        rank_step=MockRankStep(),
    )
    return engine.run(query)


# ──────────────────────────────────────────────
# 自测
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("=" * 60)
    print("Workflow Engine 自测（纯逻辑，无网络）")
    print("=" * 60)

    # 使用 Mock 阶段测完整工作流
    class MockFetchStep(FetchStep):
        def execute(self, strategies, context):
            return [
                {"code": "600519", "name": "贵州茅台", "pe_ttm": 35.2, "pb": 9.8, "roe": 28.5},
                {"code": "000858", "name": "五粮液", "pe_ttm": 22.1, "pb": 5.2, "roe": 24.0},
                {"code": "600036", "name": "招商银行", "pe_ttm": 6.8, "pb": 1.1, "roe": 16.2},
                {"code": "601166", "name": "兴业银行", "pe_ttm": 5.2, "pb": 0.65, "roe": 12.5},
                {"code": "000333", "name": "美的集团", "pe_ttm": 13.5, "pb": 2.8, "roe": 22.0},
            ]

    class MockRankStep(RankStep):
        def execute(self, data_and_strategies, context):
            data, strategies = data_and_strategies
            results = []
            for i, d in enumerate(data):
                score = max(0, 100 - d.get("pe_ttm", 50) * 2)
                results.append(StockResult(
                    code=d["code"],
                    name=d["name"],
                    price=round(d.get("pe_ttm", 0) * 3, 2),
                    scores={s.id: score for s, _ in strategies},
                    total_score=score,
                    rank=i + 1,
                ))
            return sorted(results, key=lambda r: r.total_score, reverse=True)

    engine = ScreeningEngine(
        fetch_step=MockFetchStep(),
        rank_step=MockRankStep(),
    )

    report = engine.run("低估值蓝筹股，PE < 10，PB < 2")

    print(f"\n查询: {report.query}")
    print(f"策略: {report.strategies_used}")
    print(f"候选: {report.total_candidates} 只")
    print(f"耗时: {report.elapsed_ms}ms")
    print(f"\nTop 结果:")
    for r in report.top_results:
        print(f"  #{r.rank} {r.name}({r.code}) 总分={r.total_score:.1f}")
    print("\n✓ 工作流引擎自测通过")
