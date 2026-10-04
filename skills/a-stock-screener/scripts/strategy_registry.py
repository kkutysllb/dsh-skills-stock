"""
Strategy Registry —— 策略注册中心

管理所有内置选股策略的定义、注册和匹配。
每个策略包含：
  - id:           唯一标识（如 "value_low_pe"）
  - name:         中文名称
  - category:     策略大类（value / growth / momentum / quality / thematic / technical）
  - description:  简要描述
  - tags:         关键词标签（用于从用户意图匹配）
  - params:       参数模板（该策略支持的筛选参数及默认值）
  - scoring_fn:   打分函数（接受 data[] → 返回得分列表）
  - filter_fn:    过滤函数（接受 data[] → 返回符合条件的数据）

架构采用「注册-查找」模式：调用 register() 注册策略，
通过 match() 方法根据用户意图匹配最佳策略。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

# ──────────────────────────────────────────────
# 类型别名
# ──────────────────────────────────────────────

ScoreFn = Callable[[List[dict]], List[float]]
FilterFn = Callable[[List[dict]], List[dict]]


# ──────────────────────────────────────────────
# 策略参数定义
# ──────────────────────────────────────────────

@dataclass
class ParamSpec:
    """单个筛选参数的规格说明"""
    key: str                          # 参数名（如 "pe_ttm"）
    label: str                        # 中文名（如 "市盈率 TTM"）
    dtype: str = "float"              # 数据类型：float / int / str / bool
    default: Any = None               # 默认值
    min_val: Optional[float] = None   # 范围最小值
    max_val: Optional[float] = None   # 范围最大值
    description: str = ""             # 参数说明
    required: bool = False            # 是否必填


@dataclass
class Strategy:
    """一个完整的选股策略定义"""
    id: str
    name: str
    category: str                     # value / growth / momentum / quality / thematic / technical
    description: str
    tags: List[str] = field(default_factory=list)
    params: List[ParamSpec] = field(default_factory=list)
    scoring_fn: Optional[ScoreFn] = None
    filter_fn: Optional[FilterFn] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "tags": list(self.tags),
            "params": [
                {
                    "key": p.key,
                    "label": p.label,
                    "dtype": p.dtype,
                    "default": p.default,
                    "min_val": p.min_val,
                    "max_val": p.max_val,
                    "description": p.description,
                    "required": p.required,
                }
                for p in self.params
            ],
        }


# ──────────────────────────────────────────────
# 策略注册中心
# ──────────────────────────────────────────────

class StrategyRegistry:
    """策略注册中心，全局单例模式"""

    _instance: Optional["StrategyRegistry"] = None

    def __new__(cls) -> "StrategyRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._strategies: dict[str, Strategy] = {}
            cls._instance._initialized = False
        return cls._instance

    # ── 注册 ──────────────────────────────────

    def register(self, strategy: Strategy) -> None:
        """注册一个策略"""
        if strategy.id in self._strategies:
            raise ValueError(f"Strategy '{strategy.id}' already registered.")
        self._strategies[strategy.id] = strategy

    def register_many(self, strategies: List[Strategy]) -> None:
        """批量注册策略"""
        for s in strategies:
            self.register(s)

    # ── 查找 ──────────────────────────────────

    def get(self, strategy_id: str) -> Optional[Strategy]:
        """根据 id 获取策略"""
        return self._strategies.get(strategy_id)

    def list_all(self) -> List[Strategy]:
        """返回所有注册策略"""
        return list(self._strategies.values())

    def list_by_category(self, category: str) -> List[Strategy]:
        """按大类返回策略列表"""
        return [s for s in self._strategies.values() if s.category == category]

    def match(self, text: str, top_k: int = 3) -> List[Strategy]:
        """
        根据用户输入的自然语言，通过关键词标签匹配最合适的策略。
        返回按匹配度排序的策略列表（最多 top_k 个）。
        """
        scores: list[tuple[Strategy, int]] = []
        for strategy in self._strategies.values():
            score = self._compute_match_score(text, strategy)
            if score > 0:
                scores.append((strategy, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scores[:top_k]]

    @staticmethod
    def _compute_match_score(text: str, strategy: Strategy) -> int:
        """计算文本与策略的匹配得分（简单词频匹配）"""
        text_lower = text.lower()
        score = 0
        for tag in strategy.tags:
            # 直接匹配标签
            count = len(re.findall(re.escape(tag.lower()), text_lower))
            score += count
        # 匹配策略名称中的关键词
        for word in strategy.name:
            if word in text_lower:
                score += 1
        # 匹配描述中的关键词
        for word in strategy.description.split():
            if word.lower() in text_lower:
                score += 0.5
        return score

    # ── 内置策略初始化 ────────────────────────

    def load_builtin_strategies(self) -> None:
        """加载所有内置策略（避免重复加载）"""
        if self._initialized:
            return
        self._initialized = True

        builtins = _BUILTIN_STRATEGIES
        for s_dict in builtins:
            params = [ParamSpec(**p) for p in s_dict.pop("params", [])]
            strategy = Strategy(params=params, **s_dict)
            self._strategies[strategy.id] = strategy

    def count(self) -> int:
        return len(self._strategies)


# ──────────────────────────────────────────────
# 内置策略定义
# ──────────────────────────────────────────────

_BUILTIN_STRATEGIES = [
    # ── 估值类 ──────────────────────────────
    {
        "id": "value_low_pe",
        "name": "低市盈率",
        "category": "value",
        "description": "筛选 PE (TTM) 低于行业均值的低估值股票",
        "tags": ["低估值", "低PE", "市盈率低", "便宜", "价值"],
        "params": [
            {"key": "pe_ttm_max", "label": "PE(TTM) 上限", "dtype": "float", "default": 15.0, "min_val": 0, "max_val": 100, "description": "市盈率 TTM 最大值"},
            {"key": "pe_ttm_min", "label": "PE(TTM) 下限", "dtype": "float", "default": 0, "min_val": 0, "max_val": 100, "description": "市盈率 TTM 最小值"},
        ],
    },
    {
        "id": "value_low_pb",
        "name": "低市净率",
        "category": "value",
        "description": "筛选 PB 低于 1 的破净股票",
        "tags": ["破净", "低PB", "市净率低", "资产折价"],
        "params": [
            {"key": "pb_max", "label": "PB 上限", "dtype": "float", "default": 1.0, "min_val": 0, "max_val": 10, "description": "市净率最大值"},
        ],
    },
    {
        "id": "value_dividend",
        "name": "高股息率",
        "category": "value",
        "description": "筛选股息率高于市场平均的高分红股票",
        "tags": ["高分红", "高股息", "分红", "股息率", "红利"],
        "params": [
            {"key": "dividend_yield_min", "label": "股息率下限(%)", "dtype": "float", "default": 3.0, "min_val": 0, "max_val": 20, "description": "股息率最小值"},
        ],
    },

    # ── 成长类 ──────────────────────────────
    {
        "id": "growth_high_roe",
        "name": "高 ROE",
        "category": "growth",
        "description": "筛选净资产收益率长期高于 15% 的优质成长股",
        "tags": ["高ROE", "净资产收益率", "成长", "优质"],
        "params": [
            {"key": "roe_min", "label": "ROE 下限(%)", "dtype": "float", "default": 15.0, "min_val": 0, "max_val": 60, "description": "净资产收益率最小值"},
        ],
    },
    {
        "id": "growth_revenue",
        "name": "营收增长",
        "category": "growth",
        "description": "筛选营收与利润连续增长的高成长股票",
        "tags": ["高增长", "营收增长", "利润增长", "成长"],
        "params": [
            {"key": "revenue_growth_min", "label": "营收增长率下限(%)", "dtype": "float", "default": 20.0, "min_val": -100, "max_val": 1000, "description": "营业收入同比增长率最小值"},
            {"key": "profit_growth_min", "label": "净利润增长率下限(%)", "dtype": "float", "default": 20.0, "min_val": -100, "max_val": 1000, "description": "净利润同比增长率最小值"},
        ],
    },

    # ── 动量类 ──────────────────────────────
    {
        "id": "momentum_1m",
        "name": "月度动量",
        "category": "momentum",
        "description": "筛选近 1 个月涨幅居前的强势股",
        "tags": ["强势", "动量", "上涨", "突破"],
        "params": [
            {"key": "return_1m_min", "label": "近1月涨幅下限(%)", "dtype": "float", "default": 10.0, "min_val": -100, "max_val": 500, "description": "近1个月涨幅最小值"},
            {"key": "return_1m_max", "label": "近1月涨幅上限(%)", "dtype": "float", "default": 200.0, "min_val": -100, "max_val": 500, "description": "近1个月涨幅最大值"},
        ],
    },
    {
        "id": "momentum_3m",
        "name": "季度动量",
        "category": "momentum",
        "description": "筛选近 3 个月持续上涨的趋势股",
        "tags": ["趋势", "季度动量", "持续上涨"],
        "params": [
            {"key": "return_3m_min", "label": "近3月涨幅下限(%)", "dtype": "float", "default": 15.0, "min_val": -100, "max_val": 500, "description": "近3个月涨幅最小值"},
        ],
    },

    # ── 质量类 ──────────────────────────────
    {
        "id": "quality_margin",
        "name": "高利润率",
        "category": "quality",
        "description": "筛选毛利率和净利率双高的高质量公司",
        "tags": ["高毛利率", "高净利率", "高质量", "盈利能力强"],
        "params": [
            {"key": "gross_margin_min", "label": "毛利率下限(%)", "dtype": "float", "default": 30.0, "min_val": 0, "max_val": 100, "description": "销售毛利率最小值"},
            {"key": "net_margin_min", "label": "净利率下限(%)", "dtype": "float", "default": 10.0, "min_val": 0, "max_val": 100, "description": "销售净利率最小值"},
        ],
    },
    {
        "id": "quality_debt",
        "name": "低负债率",
        "category": "quality",
        "description": "筛选资产负债率较低、财务稳健的公司",
        "tags": ["低负债", "财务稳健", "安全", "负债率低"],
        "params": [
            {"key": "debt_ratio_max", "label": "资产负债率上限(%)", "dtype": "float", "default": 50.0, "min_val": 0, "max_val": 100, "description": "资产负债率最大值"},
        ],
    },

    # ── 题材类 ──────────────────────────────
    {
        "id": "thematic_etf",
        "name": "ETF 持仓",
        "category": "thematic",
        "description": "筛选热门 ETF 重仓持有的成分股",
        "tags": ["ETF", "重仓", "北向资金", "机构持仓"],
        "params": [
            {"key": "etf_name", "label": "ETF 名称", "dtype": "str", "default": "", "description": "指定 ETF，如 '沪深300'、'中证500'"},
        ],
    },

    # ── 技术类 ──────────────────────────────
    {
        "id": "technical_volume",
        "name": "放量突破",
        "category": "technical",
        "description": "筛选成交量放量突破的短线活跃股",
        "tags": ["放量", "突破", "量比", "换手率", "短线"],
        "params": [
            {"key": "volume_ratio_min", "label": "量比下限", "dtype": "float", "default": 1.5, "min_val": 0, "max_val": 20, "description": "量比最小值"},
            {"key": "turnover_rate_min", "label": "换手率下限(%)", "dtype": "float", "default": 3.0, "min_val": 0, "max_val": 100, "description": "换手率最小值"},
            {"key": "turnover_rate_max", "label": "换手率上限(%)", "dtype": "float", "default": 30.0, "min_val": 0, "max_val": 100, "description": "换手率最大值（过滤妖股）"},
        ],
    },
]

# ──────────────────────────────────────────────
# 快捷方法
# ──────────────────────────────────────────────

_registry: Optional[StrategyRegistry] = None


def get_registry() -> StrategyRegistry:
    """获取全局策略注册中心单例"""
    global _registry
    if _registry is None:
        _registry = StrategyRegistry()
        _registry.load_builtin_strategies()
    return _registry


def list_strategies() -> List[Strategy]:
    """列出所有内置策略"""
    return get_registry().list_all()


def match_strategies(text: str, top_k: int = 3) -> List[Strategy]:
    """根据自然语言匹配策略"""
    return get_registry().match(text, top_k=top_k)


# ──────────────────────────────────────────────
# 自测
# ──────────────────────────────────────────────

if __name__ == "__main__":
    registry = get_registry()
    print(f"已加载 {registry.count()} 个内置策略\n")

    print("=" * 60)
    print("所有策略列表：")
    for s in registry.list_all():
        print(f"  [{s.category:>8}] {s.id:<24} {s.name}")

    print("\n" + "=" * 60)
    print("策略匹配测试:")
    test_queries = [
        "我想找低估值高分红的银行股",
        "最近放量突破的短线强势股",
        "高ROE的优质成长股",
        "破净的便宜股票",
    ]
    for q in test_queries:
        matches = registry.match(q, top_k=2)
        names = [s.name for s in matches]
        print(f"  '{q}' → {names}")
