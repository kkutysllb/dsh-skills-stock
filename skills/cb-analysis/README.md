# cb-analysis

可转债全链路分析技能包 — 筛选 + 分析 + 看板三引擎一体化。

## 特性

- **三引擎架构**：筛选(selector) + 分析(analyzer) + 看板(dashboard)
- **零依赖**：纯 Python 3 标准库
- **16大看板模块**：强赎/下修/龙虎榜/妖债/套利等
- **六维度评分**：基本指标/正股联动/债底保护/时间价值/资金面/套利信号
- **自然语言筛选**：基于同花顺问财 OpenAPI

## 快速开始

```bash
# 设置 API Key
export IWENCAI_API_KEY="your-key"

# 智能筛选
python3 scripts/cli.py select --query "转股溢价率低于10%的可转债"

# 深度分析
python3 scripts/cli.py analyze --mode single --bonds "精达转债"

# 全景看板
python3 scripts/cli.py dashboard

# 强赎时间表
python3 scripts/cli.py dashboard --module forced-redeem
```

## 目录结构

```
cb-analysis/
├── SKILL.md                    # 技能定义
├── scripts/
│   ├── cli.py                  # 统一 CLI 入口
│   ├── selector.py             # 筛选引擎（346行）
│   ├── analyzer.py             # 分析引擎（603行，含评分）
│   └── dashboard.py            # 看板引擎（1241行，16模块）
└── adapters/                   # 平台适配器
```

## License

MIT
