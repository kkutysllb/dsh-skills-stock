# Output Template —— 选股报告输出模板

> 本文定义 a-stock-screener 的选股报告输出格式。报告分为 **控制台短报告**（CLI 默认输出）
> 和 **Markdown 详细报告**（`--format md`）两种形态，支持终端高亮显示。
>
> 报告生成由 `scripts/report_generator.py` 实现。

---

## 1. 报告结构总览

```
╔══════════════════════════════════════════════╗
║         📊 A 股选股报告                        ║
║         ─────────────────────                 ║
║  策略：价值精选 | 日期：2026-06-29 15:30      ║
║  筛选范围：沪深 A 股  →  初筛 4320 只          ║
║  过滤条件：PE < 10 | PB < 1.5 | ROE > 15%     ║
║  最终入选：12 只                               ║
╠══════════════════════════════════════════════╣
║  排名 │ 代码    │ 名称  │ 综合分 │ PE  │ PB   ║
║  ─────┼────────┼───────┼───────┼─────┼──────║
║  🥇 1 │ 000001 │ 平安  │ 92.5   │ 8.2 │ 1.1  ║
║  🥈 2 │ 000002 │ 万科  │ 88.3   │ 7.5 │ 0.9  ║
║  🥉 3 │ 000003 │ 招商  │ 85.1   │ 9.1 │ 1.3  ║
║  ...                                          ║
╠══════════════════════════════════════════════╣
║  策略说明 & 风险提示                          ║
╚══════════════════════════════════════════════╝
```

---

## 2. 控制台短报告（CLI 默认）

### 2.1 终端颜色方案

| 元素 | 颜色 | 用途 |
|------|------|------|
| 标题 / 边框 | `BOLD_CYAN` | 报告头部 |
| 策略名 | `BOLD_YELLOW` | 策略信息行 |
| 🥇 第 1 名 | `BOLD_GREEN` | 综合分最高 |
| 🥈 第 2 名 | `GREEN` | 第二高分 |
| 🥉 第 3 名 | `YELLOW` | 第三高分 |
| 风险提示 | `RED` | 警告信息 |
| 表格列名 | `BOLD` | 表头行 |
| 普通行 | `WHITE` | 数据行 |

### 2.2 输出格式

```
╔═══════════════════════════════════════════════╗
║  📊 A 股选股报告                              ║
║  ─────────────────────                        ║
║  策略：{strategy_name}                        ║
║  日期：{timestamp}                            ║
║  筛选池：{universe} → 初筛 {initial_count} 只  ║
║  过滤条件：{filters}                          ║
║  入选：{final_count} 只                       ║
╠═══════════════════════════════════════════════╣
║  # │ 代码    │ 名称    │ 综合分 │ PE  │ PB  ...║
║  ───┼─────────┼─────────┼───────┼─────┼────── ║
║  1  │ {code} │ {name} │ {score}│ {pe} │ {pb}  ║
║  2  │ ...                                       ║
╠═══════════════════════════════════════════════╣
║  策略说明：{description}                       ║
║  ⚠ 风险提示：{risk_warning}                    ║
╚═══════════════════════════════════════════════╝
```

### 2.3 字段定义

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `strategy_name` | str | 策略中文名 | "价值精选" |
| `timestamp` | str | 报告生成时间 | "2026-06-29 15:30:00" |
| `universe` | str | 筛选范围 | "沪深 A 股" |
| `initial_count` | int | 初筛股票总数 | 4320 |
| `final_count` | int | 最终入选数量 | 12 |
| `filters` | str | 过滤条件描述 | "PE<10, PB<1.5" |
| `description` | str | 策略说明 | "寻找低估值优质公司" |
| `risk_warning` | str | 风险提示 | "低估值不代表短期上涨" |

### 2.4 表格列灵活控制

列通过 `output_columns` 参数控制，默认列包括：

```
DEFAULT_COLUMNS = [
    ("代码",   "code"),
    ("名称",   "name"),
    ("综合分", "score"),
    ("PE",     "pe"),
    ("PB",     "pb"),
    ("ROE(%)", "roe"),
]
```

不同策略可扩展列：

| 策略 | 额外列 |
|------|--------|
| 高股息 | `股息率(%)`, `分红率(%)` |
| 成长 | `营收增速(%)`, `利润增速(%)` |
| 动量 | `5日涨幅(%)`, `20日涨幅(%)` |
| 涨停龙头 | `涨停封单(亿)`, `连板数` |
| 缠论背驰 | `背驰类型`, `底分型强度` |
| 机构资金追踪 | `北向净买(亿)`, `机构评级` |

---

## 3. Markdown 详细报告

使用 `--format md` 或 `--output report.md` 时输出。

### 3.1 模板结构

```markdown
# 📊 A 股选股报告

**策略**：{strategy_name}  
**生成时间**：{timestamp}  
**筛选范围**：{universe}  
**初筛数量**：{initial_count} 只  
**过滤条件**：{filters}  
**最终入选**：{final_count} 只

---

## 📋 选股结果

| 排名 | 代码 | 名称 | 综合分 | PE | PB | ROE(%) | {extra_headers} |
|:----:|:----:|:----:|:------:|:--:|:--:|:------:|:--------------:|
{table_rows}

*排名说明：综合分 = {score_formula}*

---

## 📝 策略说明

**{strategy_name}**  
{description}

### 筛选逻辑

{screening_logic}

### 适用场景

{suitable_scenarios}

---

## ⚠️ 风险提示

{risk_warning}

---

*报告由 **A 股选股助手 (a-stock-screener)** 自动生成，仅供参考，不构成投资建议。*
```

### 3.2 模板变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `{table_rows}` | str | 表格行，每行格式 `\| N \| {code} \| {name} \| {score} \| ...` |
| `{extra_headers}` | str | 策略专属列头 |
| `{score_formula}` | str | 打分公式说明 |
| `{screening_logic}` | str | 筛选逻辑描述 |
| `{suitable_scenarios}` | str | 适用场景描述 |
| `{risk_warning}` | str | 风险提示 |

---

## 4. JSON 结构化输出

使用 `--format json` 时输出。

```json
{
  "meta": {
    "strategy": "value",
    "strategy_name": "价值精选",
    "timestamp": "2026-06-29T15:30:00+08:00",
    "universe": "沪深A股",
    "total_initial": 4320,
    "total_final": 12,
    "filters_applied": [
      {"field": "pe_ttm", "op": "lt", "value": 10},
      {"field": "pb", "op": "lt", "value": 1.5}
    ]
  },
  "stocks": [
    {
      "rank": 1,
      "code": "000001",
      "name": "平安银行",
      "score": 92.5,
      "factors": {
        "pe": 8.2,
        "pb": 1.1,
        "roe": 16.5,
        "dividend_yield": 4.2
      }
    }
  ],
  "description": "寻找低估值优质公司",
  "risk_warning": "低估值不代表短期上涨",
  "strategy_details": {
    "score_formula": "0.4*value_score + 0.3*quality_score + 0.3*stability_score",
    "suitable_scenarios": "...",
    "screening_logic": "..."
  }
}
```

---

## 5. 空结果处理

当无股票满足条件时：

### 控制台输出

```
╔═══════════════════════════════════════════════╗
║  📊 A 股选股报告                              ║
║  ─────────────────────                        ║
║  策略：{strategy_name}                        ║
║  筛选池：{universe} → 初筛 {initial_count} 只  ║
║  过滤条件：{filters}                          ║
║  入选：0 只 ❌                                 ║
╠═══════════════════════════════════════════════╣
║  未找到符合条件的股票。                         ║
║  建议：放宽过滤条件或尝试其他策略。              ║
╚═══════════════════════════════════════════════╝
```

### Markdown 报告

```markdown
# 📊 A 股选股报告

**策略**：{strategy_name}
**生成时间**：{timestamp}
**入选**：0 只

> ❌ 未找到符合条件的股票。
> 
> **建议**：放宽过滤条件或尝试其他策略。
```

---

## 6. 报告生成器接口

```python
class ReportGenerator:
    """选股报告生成器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def generate_console(
        self,
        result: ScreeningResult,
        columns: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        """生成控制台输出文本"""
        ...

    def generate_markdown(
        self,
        result: ScreeningResult,
        output_path: Optional[str] = None,
    ) -> str:
        """生成 Markdown 报告"""
        ...

    def generate_json(
        self,
        result: ScreeningResult,
    ) -> str:
        """生成 JSON 结构化输出"""
        ...

    def save(
        self,
        result: ScreeningResult,
        output_path: str,
        format: str = "md",
    ) -> str:
        """保存报告到文件"""
        ...
```

---

## 7. 报告模板定制

用户可通过 `--template` 参数指定自定义 Jinja2 模板：

```bash
python cli.py "低估值高股息" --template custom_template.md.j2
```

自定义模板变量与 3.2 节保持一致，额外可用：

| 变量 | 类型 | 说明 |
|------|------|------|
| `{raw_data}` | List[dict] | 原始股票数据 |
| `{factors}` | dict | 所有因子的分布统计 |
| `{histogram}` | str | 综合分分布 ASCII 直方图 |

---

## 附录：颜色代码定义

```python
# terminal_colors.py
class Color:
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
    # 标准颜色
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # 高亮（Bold 变体）
    BOLD_GREEN = '\033[1;32m'
    BOLD_YELLOW = '\033[1;33m'
    BOLD_CYAN = '\033[1;36m'
    
    RESET = '\033[0m'
```

---

> **文档历史**
>
> | 版本 | 日期 | 变更 |
> |------|------|------|
> | v1.0 | 2026-06-29 | 初始版本，定义控制台/Markdown/JSON 三种输出 |
