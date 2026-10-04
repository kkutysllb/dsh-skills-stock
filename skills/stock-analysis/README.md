# stock-analysis

A股个股十四维一体深度分析引擎 — 跨平台技能包

## 简介

本技能包提供完整的A股个股分析能力，整合七大核心维度 + 7大高级分析模块 + 10大智能选股策略，可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 七大分析维度

| 维度 | 能力 | 数据源 |
|------|------|--------|
| 技术面 | 多周期K线 + MACD/RSI/KDJ/布林带/ATR/OBV | Tushare Pro |
| 财务面 | 营收/利润/ROE/ROA/现金流质量 | Tushare Pro |
| 筹码面 | 筹码分布 + 套牢盘/获利盘 + 股东结构 | Tushare Pro + 问财 |
| 估值面 | PE/PB历史分位 + PE-Band + 估值陷阱检测 + 多模型估值 | Tushare Pro |
| 消息/机构/资讯 | 新闻 + 机构调研 + 券商预测 + 实时资讯 | Tushare Pro + 问财 |
| 实时行情 | 价格/涨跌/成交量/资金流向/技术指标快照 | 问财 API |
| 经营数据 | 主营/客户/供应商/参控股/重大合同 | 问财 API |

### 7大高级分析模块

| 模块 | 能力 | 数据源 |
|------|------|--------|
| 缠论分析 | 分型/笔/线段/中枢/MACD背驰/三类买卖点/多级别联立 | Tushare Pro |
| 艾略特波浪 | 5浪推动+3浪调整+斐波那契校验+Zigzag检测 | Tushare Pro |
| 谐波形态 | Gartley/Bat/Butterfly/Crab XABCD五点形态+PRZ | Tushare Pro |
| 社交媒体情绪 | 多平台舆情采集+情绪评分+恐惧贪婪指数+反转检测+价格-情绪背离 | 问财 API |
| 财报深度解读 | 三表勾稽+盈利质量评分+12项造假红旗+杜邦分析+现金流矩阵 | Tushare Pro |
| 多估值模型 | DCF+DDM+SOTP+PE-Band+PB-ROE+EV/EBITDA+估值陷阱+交叉验证+目标价 | Tushare Pro |
| 股本股东+事件统计 | 股本结构+股东户数趋势+前十大股东+增减持+实控人+质押风险+6类事件统计+综合评分 | Tushare Pro + 问财 API |

### 10大智能选股策略

价值投资 / 高股息 / 成长股 / 动量突破 / 技术突破 / 超跌反弹 / 涨停龙头 / 资金追踪 / 缠论背驰选股 / 多因子横截面

## 快速开始

### 1. 安装

```bash
# 方式一：自动安装
chmod +x install.sh && ./install.sh

# 方式二：手动安装
pip3 install -r scripts/requirements.txt
```

### 2. 配置环境变量

```bash
export TUSHARE_TOKEN="your_tushare_token"
export IWENCAI_API_KEY="your_iwencai_key"
```

### 3. 使用

```bash
# 个股技术分析
python3 scripts/analysis-engine/analyze_technical.py --stock 600519.SH --json

# 个股全面估值分析
python3 scripts/analysis-engine/analyze_stock_valuation.py --stock 600519.SH --json

# 缠论分析（多级别联立）
python3 scripts/analysis-engine/analyze_stock_chan.py --stock 600519.SH --multi-level --json

# 艾略特波浪分析
python3 scripts/analysis-engine/analyze_elliott_wave.py --stock 600519.SH --json

# 谐波形态分析
python3 scripts/analysis-engine/analyze_harmonic_pattern.py --stock 600519.SH --json

# 社交媒体情绪分析
python3 scripts/analysis-engine/analyze_social_media.py --stock 600519.SH --json

# 财报深度解读
python3 scripts/analysis-engine/analyze_financial_deep.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_financial_deep.py --stock 600519.SH --years 5 --json

# 多估值模型分析（DCF+DDM+PE-Band+PB-ROE+EV/EBITDA+交叉验证）
python3 scripts/analysis-engine/analyze_valuation_models.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_valuation_models.py --stock 600519.SH --years 5 --json

# 股本股东信息+事件统计
python3 scripts/analysis-engine/analyze_stock_shareholder.py --stock 600519.SH --json

# 实时行情查询
python3 scripts/market-query-cli.py --query "贵州茅台实时行情"

# 经营数据穿透
python3 scripts/business-query-cli.py --query "贵州茅台主营业务构成"

# 价值投资选股
python3 scripts/selection-strategies/run_value_investment.py --json

# 缠论背驰选股
python3 scripts/selection-strategies/run_chan_stock_selector.py --pool hs300 --signal buy --json
```

## 目录结构

```
stock-analysis/
├── SKILL.md                          # 跨平台技能定义（主入口）
├── README.md                         # 本文件
├── LICENSE                           # MIT 许可证
├── install.sh                        # 自动安装脚本
├── scripts/
│   ├── analysis-engine/              # 16个分析脚本
│   │   ├── analyze_technical.py          # 技术分析
│   │   ├── analyze_financial_report.py   # 财务分析
│   │   ├── analyze_stock_chips.py        # 筹码分析
│   │   ├── analyze_stock_valuation.py    # 估值分析
│   │   ├── analyze_stock_company_info.py # 公司信息
│   │   ├── analyze_stock_news.py         # 新闻分析
│   │   ├── analyze_stock_institute_research.py  # 机构调研
│   │   ├── analyze_stock_earnings_forecast.py    # 盈利预测
│   │   ├── analyze_stock_margin.py        # 融资融券
│   │   ├── analyze_stock_chan.py          # 缠论分析（内嵌引擎）
│   │   ├── analyze_elliott_wave.py        # 艾略特波浪分析
│   │   ├── analyze_harmonic_pattern.py    # 谐波形态分析
│   │   ├── analyze_social_media.py         # 社交媒体情绪分析
│   │   ├── analyze_financial_deep.py       # 财报深度解读
│   │   ├── analyze_valuation_models.py     # 多估值模型分析（DCF+DDM+PE-Band+PB-ROE+EV/EBITDA）
│   │   ├── analyze_stock_shareholder.py     # 股本股东信息+事件统计
│   ├── selection-strategies/         # 10个智能选股策略
│   │   ├── run_value_investment.py
│   │   ├── run_high_dividend.py
│   │   ├── run_growth_stock.py
│   │   ├── run_momentum_breakthrough.py
│   │   ├── run_technical_breakthrough.py
│   │   ├── run_oversold_rebound.py
│   │   ├── run_limit_up_leader.py
│   │   ├── run_fund_flow_tracking.py
│   │   ├── run_chan_stock_selector.py      # 缠论背驰选股（内嵌引擎）
│   │   └── run_multi_factor.py             # 多因子横截面选股
│   ├── chan_theory_v2/              # 缠论引擎（内嵌）
│   ├── market-query-cli.py           # 实时行情查询CLI
│   ├── business-query-cli.py         # 经营数据查询CLI
│   ├── management-query-cli.py       # 股东管理查询CLI
│   ├── requirements.txt              # Python 依赖
│   └── package.sh                    # 打包脚本
├── references/                       # 参考文档
│   ├── business-query.md
│   ├── management-query.md
│   ├── chart-specs.md
│   ├── news-search.md
│   └── valuation-methodology.md
└── adapters/                         # 平台适配指南
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 平台集成

### OpenClaw

将整个目录放入 skills 目录，OpenClaw 会自动读取 SKILL.md 中的 frontmatter 配置。

### Claude Code

将 SKILL.md 内容添加到 `.claude/skills/` 目录即可，Claude 会识别 Markdown 指令格式。

### Qoder / DeerFlow

将整个技能包目录放到项目 `skills/` 路径下。

### 通用集成

参考 `adapters/generic.md` 中的 REST API / Shell / LangChain @tool 集成方式。

## 多因子横截面选股

```bash
# 多因子选股（默认 Top10 等权组合）
python3 scripts/selection-strategies/run_multi_factor.py --json

# 自定义 TopN 和动量窗口
python3 scripts/selection-strategies/run_multi_factor.py --top-n 20 --momentum-window 10 --json
```

## 打包发布

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出文件：
- `dist/stock-analysis.skill` — OpenClaw 格式（ZIP）
- `dist/stock-analysis-v3.5.0.tar.gz` — 通用格式

## 环境要求

- Python 3.8+
- Tushare Pro API 密钥
- 同花顺问财 API 密钥

## 许可证

MIT License
