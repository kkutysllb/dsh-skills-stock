# etf-analysis

ETF 全维度分析 — 跨平台技能包（双引擎）

## 简介

本技能包整合双引擎提供 ETF 全维度分析能力：

- **Tushare 引擎** — 13 种结构化分析维度（行情/净值/份额/规模/五类分类/跟踪指数/行业ETF/横向对比/持仓/经理/分红）
- **问财引擎** — 自然语言智能 ETF 筛选（实时数据）

可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 功能一览

| 功能 | 引擎 | 说明 |
|------|------|------|
| ETF 列表 | tushare | 全市场 ETF 含分类标签 |
| 日行情 | tushare | 收盘价/涨跌幅/成交额 |
| 历史净值 | tushare | 单位净值/累计净值 |
| 份额变化 | tushare | 场内份额及环比变化 |
| 规模分析 | tushare | 日均成交额+估算规模 |
| 五类分类 | tushare | 宽基/行业/跨境/商品/货币 |
| 分类筛选 | tushare | 按类型/规模/涨跌幅 |
| 跟踪指数 | tushare | 指数代码/编制机构/行情 |
| 行业ETF | tushare | 按行业关键词匹配 |
| 横向对比 | tushare | 多ETF价格/收益率/费率 |
| 持仓分析 | tushare | 十大重仓股 |
| 基金经理 | tushare | 在任/历任经理 |
| 分红记录 | tushare | 分红公告/除息/派息 |
| 智能筛选 | selector | 自然语言 ETF 筛选 |

## 快速开始

```bash
# 配置环境变量
export TUSHARE_TOKEN="your-tushare-token"
export IWENCAI_API_KEY="your-iwencai-key"

# ETF 列表（含分类）
python3 scripts/cli.py tushare list --params market=E limit=20

# 日行情
python3 scripts/cli.py tushare daily --params ts_code=510300.SH

# 五类 ETF 分类概览
python3 scripts/cli.py tushare classify --params limit=5

# 宽基 ETF 筛选
python3 scripts/cli.py tushare screen --params etf_type=宽基ETF limit=10

# 横向对比
python3 scripts/cli.py tushare compare --params ts_codes=510300.SH,159919.SZ

# 问财智能筛选
python3 scripts/cli.py selector --query "沪深300ETF有哪些？"
python3 scripts/cli.py selector --query "规模最大的ETF"
```

## 目录结构

```
etf-analysis/
├── SKILL.md              # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── cli.py            # 统一 CLI 入口
│   ├── etf_analyzer.py   # Tushare ETF 分析引擎
│   ├── etf_selector.py   # 问财 ETF 筛选引擎
│   ├── package.sh        # 打包脚本
│   └── requirements.txt  # Python 依赖
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+
- Tushare 引擎: `pip install tushare pandas`
- 问财引擎: 无第三方依赖（纯标准库）

### 环境变量

| 变量 | 说明 | 获取方式 |
|------|------|---------|
| TUSHARE_TOKEN | Tushare Pro Token | https://tushare.pro/register |
| IWENCAI_API_KEY | 问财 API Key | https://www.iwencai.com/skillhub |

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/etf-analysis.skill` + `dist/etf-analysis-1.0.0.tar.gz`

## 许可证

MIT License
