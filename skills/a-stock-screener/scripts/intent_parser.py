"""
Intent Parser —— 自然语言 → ScreeningIntent

将用户的一句中文自然语言（如 "我想找低估值高分红的银行股，PE < 8，PB < 1"）
解析为结构化的 ScreeningIntent 对象，供 workflow_engine 消费。

核心流程：
1. 领域关键词提取（估值/成长/动量/技术/题材）
2. 过滤条件提取（PE / PB / ROE / 市值 / 换手率 等阈值）
3. 策略映射（匹配最合适的选股策略）
4. 构建 ScreeningIntent 数据结构

Usage:
    intent = parse("找低估值高分红的银行股，PE < 8，PB < 1")
    # => ScreeningIntent(strategy="value", filters={...})
"""

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ScreenFilter:
    """单个过滤条件"""
    field: str          # pe_ttm / pb / roe / market_cap / dividend_yield / turnover_rate / ...
    operator: str       # gt / ge / lt / le / eq / between
    value: float
    value_to: Optional[float] = None   # 当 operator == 'between' 时使用
    label: str = ""     # 中文描述，如 "市盈率"

    def __post_init__(self):
        if not self.label:
            self.label = LABEL_MAP.get(self.field, self.field)


@dataclass
class SectorPreference:
    """板块偏好"""
    include: List[str] = field(default_factory=list)   # 包含的行业/概念
    exclude: List[str] = field(default_factory=list)   # 排除的行业/概念


@dataclass
class ScreeningIntent:
    """
    结构化的选股意图，由 IntentParser 解析自然语言后生成，
    作为 workflow_engine 的输入。
    """
    # ---- 策略选择（二选一） ----
    strategy: str = "multi_factor"            # 策略 ID（strategy-catalog.md 中的 ID）
    custom_strategy: Optional[str] = None     # 若非内置策略，自定义描述

    # ---- 过滤条件 ----
    filters: List[ScreenFilter] = field(default_factory=list)
    sector: SectorPreference = field(default_factory=SectorPreference)

    # ---- 排序 ----
    top_k: int = 20
    sort_by: str = "score"                    # score / pe_ttm / roe / market_cap ...
    sort_descending: bool = True

    # ---- 输出 ----
    output_format: str = "console"            # console / md
    verbose: bool = False

    # ---- 原始信息 ----
    raw_query: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> Tuple[bool, List[str]]:
        """基础校验，返回 (是否合法, 错误信息列表)"""
        errors: List[str] = []
        if not self.strategy and not self.custom_strategy:
            errors.append("未指定选股策略")
        if self.top_k < 1:
            errors.append("top_k 必须 >= 1")
        return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# 常量映射表
# ---------------------------------------------------------------------------

LABEL_MAP: Dict[str, str] = {
    "pe_ttm": "市盈率(TTM)",
    "pe_lyr": "市盈率(静态)",
    "pb": "市净率",
    "ps_ttm": "市销率(TTM)",
    "pcf_ttm": "市现率(TTM)",
    "roe": "净资产收益率",
    "roa": "总资产收益率",
    "gross_margin": "毛利率",
    "net_margin": "净利率",
    "market_cap": "总市值",
    "circulating_market_cap": "流通市值",
    "dividend_yield": "股息率",
    "dividend_ratio": "分红率",
    "revenue_growth": "营收增长率",
    "profit_growth": "净利润增长率",
    "turnover_rate": "换手率",
    "volume_ratio": "量比",
    "amplitude": "振幅",
    "change_pct": "涨跌幅",
    "amount": "成交额",
    "debt_ratio": "资产负债率",
    "current_ratio": "流动比率",
    "quick_ratio": "速动比率",
    "score": "综合评分",
}

# 策略 → 关键词映射
STRATEGY_KEYWORDS: Dict[str, List[str]] = {
    "value":           ["低估值", "价值", "破净", "便宜", "市盈率低", "市净率低", "低价"],
    "high_dividend":   ["高股息", "分红", "股息率", "高分红", "红利", "现金分红", "分红率"],
    "growth":          ["成长", "高增长", "增速", "高成长", "营收增长", "利润增长", "高增速"],
    "momentum":        ["动量", "强势", "趋势", "创新高", "突破", "主升浪", "上涨趋势"],
    "breakout":        ["技术突破", "突破", "放量突破", "均线突破", "平台突破", "突破压力"],
    "oversold":        ["超跌反弹", "超跌", "反弹", "底部", "超卖", "跌深", "触底"],
    "limit_up":        ["涨停", "连板", "涨停龙头", "打板", "龙头", "封板"],
    "institutional":   ["机构", "基金", "北向", "外资", "主力", "资金流入", "机构重仓"],
    "chanlun":         ["缠论", "背驰", "缠论背驰", "中枢", "盘整", "趋势背驰"],
    "multi_factor":    ["多因子", "综合", "横截面", "打分", "精选", "优选"],
}

# 过滤字段 → 正则模式
FILTER_PATTERNS: Dict[str, List[str]] = {
    "pe_ttm": [r"PE[（(]?TTM[）)]?\s*([<≤>≥=])\s*([\d.]+)"],
    "pb":     [r"PB\s*([<≤>≥=])\s*([\d.]+)"],
    "roe":    [r"ROE\s*([<≤>≥=])\s*([\d.]+)", r"净资产收益率\s*([<≤>≥=])\s*([\d.]+)"],
}

# 常见操作符映射
OP_MAP: Dict[str, str] = {
    "<": "lt", "<=": "le", "≤": "le",
    ">": "gt", ">=": "ge", "≥": "ge",
    "=": "eq",
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class IntentParser:
    """自然语言意图解析器"""

    def __init__(self):
        self._compiled: Dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译正则"""
        for field, patterns in FILTER_PATTERNS.items():
            self._compiled[field] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def _extract_industry(self, text: str) -> List[str]:
        """提取行业/概念关键词"""
        known_industries = [
            "银行", "保险", "证券", "地产", "医药", "生物", "医疗",
            "消费", "白酒", "食品", "家电", "汽车", "新能源", "光伏",
            "风电", "锂电", "储能", "半导体", "芯片", "电子", "通信",
            "计算机", "AI", "人工智能", "机器人", "军工", "有色",
            "化工", "钢铁", "煤炭", "建材", "建筑", "交运", "公用",
            "环保", "农业", "养殖", "煤炭", "石油", "电力", "港口",
            "机场", "高速", "旅游", "酒店", "传媒", "教育",
        ]
        found: List[str] = []
        for industry in known_industries:
            if industry in text:
                found.append(industry)
        return found

    def _extract_filters(self, text: str) -> List[ScreenFilter]:
        """提取数值过滤条件"""
        filters: List[ScreenFilter] = []
        for field, patterns in self._compiled.items():
            for pattern in patterns:
                m = pattern.search(text)
                if m:
                    op_str = m.group(1)
                    val = float(m.group(2))
                    op = OP_MAP.get(op_str, "eq")
                    filters.append(ScreenFilter(
                        field=field, operator=op, value=val,
                    ))
        return filters

    def _map_strategy(self, text: str) -> str:
        """根据关键词匹配最佳策略"""
        scores: List[Tuple[int, str]] = []
        for strategy, keywords in STRATEGY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores.append((score, strategy))
        if not scores:
            return "multi_factor"
        scores.sort(key=lambda x: (-x[0], x[1]))
        return scores[0][1]

    def parse(self, query: str) -> ScreeningIntent:
        """将自然语言查询解析为 ScreeningIntent"""
        text = query.strip()
        if not text:
            return ScreeningIntent(raw_query=query)

        strategy = self._map_strategy(text)
        filters = self._extract_filters(text)
        industries = self._extract_industry(text)

        sector = SectorPreference(include=industries)

        return ScreeningIntent(
            strategy=strategy,
            filters=filters,
            sector=sector,
            raw_query=query,
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

_DEFAULT_PARSER = IntentParser()


def parse(query: str) -> ScreeningIntent:
    """快捷解析函数"""
    return _DEFAULT_PARSER.parse(query)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        "我想找低估值高分红的银行股，PE < 8，PB < 1",
        "最近超跌的新能源龙头，ROE > 15，市值 500 亿以上",
        "找连续涨停的半导体龙头",
        "北向资金重仓的白马股，PE > 10 且 PE < 30",
        "高成长的医疗股，营收增速 20% 以上",
    ]

    for tc in test_cases:
        intent = parse(tc)
        print(f"Q: {tc}")
        print(f"  Strategy : {intent.strategy}")
        print(f"  Filters  : {[f'{f.label} {f.operator} {f.value}' for f in intent.filters]}")
        print(f"  Sectors  : {intent.sector.include}")
        print()
