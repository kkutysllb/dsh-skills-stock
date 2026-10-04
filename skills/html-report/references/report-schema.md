# 报告 JSON 契约（html-report v2）

渲染器 `scripts/render_report.py` 对字段**宽容**：缺省优雅降级、未知图表
跳过并告警；但产出高质量看板依赖以下结构。

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | ✅ | 报告标题（页面 H1 + 归档标题） |
| generated_at | string | 建议 | ISO-8601 时间戳；归档目录按此分日期 |
| symbol | string | | 标的代码，如 `600519` / `贵州茅台` |
| report_type | string | | `analysis`（默认）/ `annual_report` / `factor_review` / `backtest_summary` … |
| period_start / period_end | string | | 覆盖区间，如 `2025-01-01` |
| risk_level | string | | 低 / 中 / 高（头部徽标） |
| coverage_status | string | | 归档元数据，一般 `complete` |
| summary | string | | 执行摘要，≤200 字；支持 `**粗体**` 与 `` `代码` `` |
| metrics | Metric[] | | 关键指标卡（4-8 个为宜） |
| sections | Section[] | ✅ | 正文分节 |
| risks | string[] | ✅ | 风险提示列表 |
| references | Ref[] | | 参考来源（url 仅 http/https） |
| disclaimer | string | | 免责声明（缺省用内置文案） |

## Metric

```json
{ "label": "营收同比", "value": "15.2%", "tone": "up", "hint": "2025 全年 vs 2024" }
```

- `value` 放短值；说明放 `hint`
- `tone`: `up`（绿）/ `down`（红）/ `warn`（黄）/ `neutral`

## Section

```json
{ "heading": "盈利能力分析", "blocks": [ … ] }
```

### Block 类型

**text** — 段落（`\n` 分段；行内支持 `**粗体**`、`` `代码` ``）

```json
{ "type": "text", "body": "2025 年公司营收 **1,796 亿元**，同比 `+15.2%`。\n第二段……" }
```

**list** — 要点列表

```json
{ "type": "list", "items": ["直营渠道占比提升至 45%", "合同负债同比 +12%"] }
```

**table** — 数据表（columns 与每行等长）

```json
{ "type": "table", "columns": ["指标", "2024", "2025", "同比"], "rows": [["毛利率", "91.9%", "92.1%", "+0.2pct"]] }
```

**callout** — 提示条（`tone`: info 默认 / warn / down）

```json
{ "type": "callout", "tone": "warn", "body": "批价数据为渠道调研口径，与财务确认收入存在时滞。" }
```

**chart** — 内联 SVG 图表（见下）

## Chart（六种）

公共字段：`title`（图题，必填）。

**line / area** — 趋势（多序列；area 带填充）

```json
{ "type": "chart", "title": "营收与净利趋势",
  "chart": { "type": "line", "yLabel": "亿元", "baseline": 0,
             "x": ["2021", "2022", "2023", "2024", "2025"],
             "series": [ { "name": "营收", "values": [1062, 1275, 1506, 1559, 1796] },
                         { "name": "归母净利", "values": [525, 627, 747, 862, 991] } ] } }
```

**bar** — 柱状（多序列自动分组；域跨 0 时画正负柱）

```json
{ "type": "chart", "title": "分产品营收",
  "chart": { "type": "bar", "yLabel": "亿元",
             "x": ["茅台酒", "系列酒", "其他"],
             "series": [ { "name": "2025", "values": [1428, 321, 47] } ] } }
```

**scatter** — 散点（x 为类目或序号）

```json
{ "type": "chart", "title": " ROE-分红率",
  "chart": { "type": "scatter", "x": ["2021", "2022", "2023", "2024", "2025"],
             "series": [ { "name": "ROE%", "values": [29.9, 30.3, 34.2, 36.4, 35.1] } ] } }
```

**pie** — 环形占比（自动标百分比）

```json
{ "type": "chart", "title": "收入结构",
  "chart": { "type": "pie", "data": [ { "name": "茅台酒", "value": 1428 },
                                       { "name": "系列酒", "value": 321 } ] } }
```

**radar** — 多维评估（≥3 维）

```json
{ "type": "chart", "title": "行业五维评估",
  "chart": { "type": "radar", "indicators": ["成长", "盈利", "护城河", "估值", "政策"],
             "series": [ { "name": "白酒", "values": [62, 95, 90, 70, 78] },
                         { "name": "新能源", "values": [85, 55, 60, 88, 90] } ] } }
```

- radar 数值默认按所选序列的 min/max 缩放到外框，量纲不同也可叠加
- line 的 `baseline` 画虚线基准（如 `1.0` 净值、`0` 轴）

## 完整最小例子

```json
{
  "title": "贵州茅台 2025 年报快评",
  "generated_at": "2026-09-18T10:00:00+08:00",
  "symbol": "600519",
  "report_type": "annual_report",
  "period_start": "2025-01-01",
  "period_end": "2025-12-31",
  "risk_level": "中",
  "summary": "2025 年营收 **1,796 亿元**（+15.2%），归母净利 991 亿元（+15.0%）。直营与国际化是主要增量。",
  "metrics": [
    { "label": "营收", "value": "1,796 亿", "tone": "up", "hint": "+15.2%" },
    { "label": "归母净利", "value": "991 亿", "tone": "up", "hint": "+15.0%" },
    { "label": "毛利率", "value": "92.1%", "tone": "neutral" }
  ],
  "sections": [
    { "heading": "增长结构",
      "blocks": [
        { "type": "text", "body": "增量主要来自直营放量与非标提价。" },
        { "type": "chart", "title": "营收趋势",
          "chart": { "type": "line", "yLabel": "亿元", "x": ["2023", "2024", "2025"],
                     "series": [ { "name": "营收", "values": [1506, 1559, 1796] } ] } }
      ] }
  ],
  "risks": ["消费复苏不及预期", "批价波动"],
  "references": [ { "title": "2025 年年度报告", "url": "https://www.sse.com.cn/", "date": "2026-04-02" } ]
}
```
