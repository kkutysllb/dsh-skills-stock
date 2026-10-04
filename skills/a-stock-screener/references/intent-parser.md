# Intent Parser —— 自然语言 → 选股策略参数

> 本文是 `scripts/intent_parser.py` 的设计契约。意图解析器把用户随口的一句话
> （"我想找低估值高分红的银行股，市值 500 亿以上，PE 小于 8"）映射成结构化的
> `ScreeningIntent` 对象，供工作流引擎消费。

---

## 1. 设计目标

| 目标 | 说明 |
| --- | --- |
| **零训练成本** | 基于关键词词典 + 正则表达式 + 启发式规则，**不依赖任何 LLM**，离线可运行 |
| **可解释** | 每条解析结论都带 `matched_keywords` / `matched_rules`，方便人工校验 |
| **可扩展** | 策略词典和修饰词词典以 YAML/JSON 形式外部化，新增策略无需改代码 |
| **可回退** | 解析失败时给出一个保守的"默认意图"（多因子横截面），而不是抛错 |

---

## 2. 核心数据模型：`ScreeningIntent`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class ScreeningIntent:
    # --- 策略选择 ---
    strategy: str                       # 主策略 id，如 "value"/"dividend"/"momentum"/"multi_factor"
    strategy_label: str                 # 中文标签，如 "价值投资"
    confidence: float                   # 解析置信度 0~1
    matched_keywords: List[str]         # 命中的关键词（可解释用）

    # --- 过滤条件（可选）---
    market_cap_min: Optional[float]     # 市值下限（亿元）
    market_cap_max: Optional[float]     # 市值上限（亿元）
    pe_max: Optional[float]             # PE TTM 上限
    pe_min: Optional[float]             # PE TTM 下限（用来排除负值/微利）
    pb_max: Optional[float]             # PB 上限
    roe_min: Optional[float]            # ROE 下限（%）
    dividend_yield_min: Optional[float] # 股息率下限（%）
    revenue_growth_min: Optional[float] # 营收增速下限（%）
    profit_growth_min: Optional[float]  # 净利润增速下限（%）

    # --- 行业/风格偏好 ---
    industries: List[str] = field(default_factory=list)  # 申万一级行业名
    styles: List[str] = field(default_factory=list)      # 大盘/中盘/小盘/成长/价值
    exclude_st: bool = True                              # 默认剔除 ST
    exclude_suspend: bool = True                         # 默认剔除停牌

    # --- 输出偏好 ---
    top_n: int = 20                       # 输出股票数
    sort_by: str = "score"                # 排序字段
    need_explanation: bool = True        # 是否在报告中给出"为什么选它"

    # --- 元信息 ---
    raw_text: str = ""                    # 原始输入
    parse_warnings: List[str] = field(default_factory=list)  # 解析过程的告警
```

---

## 3. 意图分类词典（10 类内置策略）

解析器对每条输入做 **关键词匹配打分**，取分数最高的策略。词典文件
`scripts/data/intent_keywords.yaml`（示例节选）：

```yaml
strategies:
  value:                              # 价值投资
    label: "价值投资"
    weight_keywords:                 # 主关键词（每命中 +3 分）
      - 低估值
      - 估值低
      - 便宜
      - 价值股
      - 破净
      - 安全边际
    weight_aux:                       # 辅助关键词（每命中 +1 分）
      - PE 低
      - PB 低
      - 蓝筹
      - 烟蒂
    defaults:
      pe_max: 15
      pb_max: 1.5
      roe_min: 8
      exclude_st: true

  dividend:                           # 高股息
    label: "高股息"
    weight_keywords:
      - 高股息
      - 分红
      - 派息
      - 吃息
      - 红利
      - 股息率
    weight_aux:
      - 银行
      - 公用事业
      - 稳定
    defaults:
      dividend_yield_min: 4
      roe_min: 8
      pe_max: 20

  growth:                             # 成长
    label: "成长股"
    weight_keywords:
      - 高成长
      - 成长股
      - 业绩高增长
      - 高速增长
      - 黑马
    weight_aux:
      - 营收增长
      - 净利润增长
      - CAGR
    defaults:
      revenue_growth_min: 25
      profit_growth_min: 25
      roe_min: 10

  momentum:                           # 动量
    label: "趋势动量"
    weight_keywords:
      - 动量
      - 趋势
      - 强势
      - 均线多头
      - 创新高
    weight_aux:
      - 突破
      - 上涨趋势
    defaults:
      lookback_days: 60
      min_return: 0.05

  technical_breakout:                 # 技术突破
    label: "技术突破"
    weight_keywords:
      - 突破
      - 涨停
      - 放量突破
      - 平台突破
      - 箱体突破
    weight_aux:
      - 均线
      - 压力位
    defaults:
      volume_ratio: 1.5
      breakout_lookback: 20

  reversal:                           # 超跌反弹
    label: "超跌反弹"
    weight_keywords:
      - 超跌
      - 反弹
      - 跌多了
      - 抄底
      - 跌无可跌
      - 困境反转
    weight_aux:
      - RSI 低
      - 乖离率
    defaults:
      max_drawdown: -0.30
      rsi_max: 30

  limit_up_leader:                    # 涨停龙头
    label: "涨停龙头"
    weight_keywords:
      - 龙头
      - 连板
      - 涨停板
      - 打板
      - 首板
      - 妖股
    weight_aux:
      - 题材
      - 概念
    defaults:
      limit_up_days: 1
      min_volume: 1e8

  institutional:                      # 机构资金追踪
    label: "机构资金追踪"
    weight_keywords:
      - 机构买入
      - 北向资金
      - 主力资金
      - 公募加仓
      - 社保
      - QFII
    weight_aux:
      - 持仓增加
      - 资金流入
    defaults:
      north_bound_days: 5
      institutional_net_buy_min: 1e8

  chanlun:                            # 缠论背驰
    label: "缠论背驰"
    weight_keywords:
      - 缠论
      - 背驰
      - 一买
      - 二买
      - 三买
      - 中枢
    weight_aux:
      - 走势完美
    defaults:
      min_segment: 2
      divergence_lookback: 30

  multi_factor:                       # 多因子横截面（默认）
    label: "多因子综合"
    weight_keywords:
      - 综合
      - 多因子
      - 量化选股
      - 横截面
    weight_aux: []
    defaults:
      top_n: 30
      # 默认权重：质量 30% / 价值 25% / 成长 20% / 动量 15% / 反转 10%
```

> **解析算法**：对每个策略计算 `score = 3 × 主关键词命中数 + 1 × 辅助关键词命中数`，
> 取分数最高的策略；若全部为 0 分或最高分 < 2，**回退到 `multi_factor`** 并把
> `confidence` 设为 `0.3`。

---

## 4. 修饰词提取规则

修饰词提取与意图分类**并行**进行，使用正则 + 单位识别：

| 模式 | 正则 | 提取结果 |
| --- | --- | --- |
| 市值下限 | `市值\s*[>大于超过至少]?\s*(\d+(?:\.\d+)?)\s*亿` | `market_cap_min = X` |
| 市值上限 | `市值\s*[<小于不超过最多]?\s*(\d+(?:\.\d+)?)\s*亿` | `market_cap_max = X` |
| PE 上限 | `PE\s*[<小于不超过]?\s*(\d+(?:\.\d+)?)` | `pe_max = X` |
| PB 上限 | `PB\s*[<小于不超过]?\s*(\d+(?:\.\d+)?)` | `pb_max = X` |
| 股息率下限 | `股息率\s*[>大于超过]?\s*(\d+(?:\.\d+)?)\s*%?` | `dividend_yield_min = X` |
| ROE 下限 | `ROE\s*[>大于超过]?\s*(\d+(?:\.\d+)?)\s*%?` | `roe_min = X` |
| 营收增速下限 | `营收(?:增长)?\s*[>大于超过]?\s*(\d+(?:\.\d+)?)\s*%` | `revenue_growth_min = X` |
| 净利润增速下限 | `(?:净利润|利润)增长\s*[>大于超过]?\s*(\d+(?:\.\d+)?)\s*%` | `profit_growth_min = X` |
| 行业偏好 | 申万一级行业词典（78 个）做子串匹配 | `industries = [...]` |
| 大小盘偏好 | `大盘股|中盘股|小盘股|中小盘` | `styles = ["large"/"mid"/"small"]` |
| Top N | `(?:要|输出|选|给).{0,4}?(\d+)\s*(?:只|个|支|票)` | `top_n = X` |
| 排除 ST | `包括 ST|不要排除 ST` → 默认翻转 | `exclude_st = True/False` |
| 排除停牌 | `包括停牌|允许停牌` | `exclude_suspend = False` |

**单位约定**：
- 市值：默认"亿"（中文语境）；若出现"万亿"自动 ×10000
- 增速：默认"%"
- 比率（PE/PB）：无量纲

---

## 5. 行业词典（节选）

> 完整 78 个申万一级行业见 `scripts/data/industries.yaml`，本节列高频出现的：

银行 / 非银金融 / 证券 / 保险 / 房地产 / 建筑装饰 / 建筑材料 / 钢铁 / 有色金属 /
化工 / 石油石化 / 煤炭 / 电力 / 公用事业 / 环保 / 机械设备 / 电力设备 / 汽车 /
家用电器 / 纺织服饰 / 轻工制造 / 医药生物 / 食品饮料 / 农林牧渔 / 商贸零售 /
社会服务 / 美容护理 / 传媒 / 互联网 / 通信 / 计算机 / 电子 / 半导体 / 国防军工 /
银行/煤炭（多关键词）

解析时同时支持"金融"、"银行股"等**口语化写法**，做归一化（见 `normalizer.py`）。

---

## 6. 解析流程（伪代码）

```python
def parse(text: str) -> ScreeningIntent:
    intent = ScreeningIntent(raw_text=text)
    text_norm = normalize(text)              # 全角转半角、去空格、转小写
    intent.matched_keywords = []

    # 1) 提取所有修饰词
    for rule in MODIFIER_RULES:
        for m in rule.regex.finditer(text_norm):
            setattr(intent, rule.field, m.group(1))

    # 2) 行业关键词
    for industry, aliases in INDUSTRY_DICT.items():
        if any(alias in text_norm for alias in aliases):
            intent.industries.append(industry)

    # 3) 策略打分
    scores = score_strategies(text_norm)
    best, score = max(scores.items(), key=lambda kv: kv[1])
    intent.strategy = best
    intent.strategy_label = STRATEGY_LABELS[best]
    intent.confidence = min(score / 6.0, 1.0)
    intent.matched_keywords = scores[best]["matched"]

    # 4) 套用策略默认参数（被用户显式覆盖的字段保留用户值）
    apply_defaults(intent, STRATEGY_DEFAULTS[intent.strategy])

    # 5) 兜底
    if intent.confidence < 0.3:
        intent.parse_warnings.append("未能匹配任何策略，使用多因子综合（默认）")
        intent.strategy = "multi_factor"
        intent.confidence = 0.3

    return intent
```

---

## 7. 解析示例

| 输入 | 解析结果 |
| --- | --- |
| `"找低估值高分红的银行股"` | strategy=`dividend`（高股息+银行辅助），pe_max=15, dividend_yield_min=4, industries=[银行], confidence=0.67 |
| `"市值 500 亿以上，PE 小于 8"` | strategy=`value`，market_cap_min=500, pe_max=8, confidence=0.5 |
| `"最近涨得好的龙头，连板的"` | strategy=`limit_up_leader`，momentum 辅助, confidence=0.83 |
| `"缠论一买"` | strategy=`chanlun`，confidence=1.0 |
| `"随便来点"` | strategy=`multi_factor`，confidence=0.3, warning="未能匹配任何策略" |

---

## 8. 解析失败与告警

| 场景 | 行为 |
| --- | --- |
| 行业词命中但与策略逻辑冲突（如"高股息 + ST"） | 不阻断，加入 `parse_warnings` |
| 数值格式异常（如"PE 小于 -5"） | 丢弃该字段，记 warning |
| 同时命中多个高分策略（差值 ≤ 1） | 取**先注册者**，并在 warning 中列出候选项让用户二选一 |
| 输入为空字符串 | 返回默认 `multi_factor`，confidence=0.1 |
| 输入超长（>500 字） | 截断并 warning "输入已截断到 500 字" |

---

## 9. 与工作流引擎的契约

`workflow_engine.py` **只接受** `ScreeningIntent` 对象，不接受原始字符串；
所有 CLI、HTTP、agent 入口都必须先调 `intent_parser.parse()`。

```python
# cli.py 入口
from intent_parser import parse
from workflow_engine import run

intent = parse(user_text)
report = run(intent)
print_report(report)
```

这样工作流引擎对用户表达方式完全解耦，未来加 HTTP/UI/agent 入口都不需要改引擎。