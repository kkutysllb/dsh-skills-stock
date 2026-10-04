---
name: stock-analysis
description: A股个股十四维一体深度分析引擎——技术面+财务面+财报深度解读+筹码面+估值面+多模型估值+股本股东+事件统计+消息/机构/资讯层+实时行情+经营数据穿透+缠论分析+艾略特波浪+谐波形态+社交媒体情绪分析，附10大智能选股策略。开箱即用的跨平台技能包，支持 OpenClaw/Claude Code/Qoder 等 Agent 架构。
version: 3.5.1
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# A股个股十四维一体深度分析引擎

## 技能概述

本技能包提供完整的A股个股分析能力，整合七大核心维度 + 7大高级分析模块 + 10大智能选股策略：

1. **技术面分析引擎** — 多周期K线+6大技术指标+支撑压力位
2. **财务面分析引擎** — 营收/利润/ROE/现金流全维度
3. **筹码面分析引擎** — 筹码分布+套牢盘/获利盘+股东结构
4. **估值面分析引擎** — PE/PB历史分位+PE-Band+PB-ROE+估值陷阱检测+多估值模型交叉验证
5. **消息/机构/资讯层** — 新闻+机构调研+券商盈利预测+实时资讯
6. **实时行情层** — 问财API实时价格/资金流向/技术指标快照
7. **经营数据穿透层** — 主营业务/客户/供应商/参控股/重大合同
8. **缠论分析引擎** — 形态学+动力学+多级别联立+三类买卖点
9. **艾略特波浪引擎** — 5浪推动+3浪调整+斐波那契校验
10. **谐波形态引擎** — Gartley/Bat/Butterfly/Crab XABCD五点形态
11. **社交媒体情绪引擎** — 多平台舆情采集+情绪评分+恐惧贪婪指数+反转检测
12. **财报深度解读引擎** — 三表勾稽+盈利质量评分+造假红旗检测+杜邦分析+现金流矩阵
13. **多估值模型引擎** — DCF+DDM+SOTP+PE-Band+PB-ROE+EV/EBITDA+估值陷阱+交叉验证+目标价
14. **股本股东+事件统计引擎** — 股本结构+股东户数趋势+前十大股东+增减持+实控人+质押风险+6类事件统计

## 分析脚本列表

### 个股分析脚本（`scripts/analysis-engine/`）

| 脚本文件 | 功能 | 参数 |
|---------|------|------|
| `analyze_technical.py` | 多周期技术分析（日/周/月+5/15/30/60分钟） | `--stock 600519.SH --json` |
| `analyze_financial_report.py` | 财务分析（营收/利润/ROE/现金流） | `--stock 600519.SH --json` |
| `analyze_financial_deep.py` | 财报深度解读（三表勾稽+盈利质量+造假红旗+杜邦分析+现金流矩阵） | `--stock 600519.SH --years 3 --json` |
| `analyze_stock_chips.py` | 筹码分布（套牢盘/获利盘/支撑压力） | `--stock 600519.SH --json` |
| `analyze_stock_valuation.py` | 估值分析（PE/PB/PS/PCF+PE-Band+估值陷阱） | `--stock 600519.SH --json` |
| `analyze_valuation_models.py` | 多估值模型分析（DCF+DDM+PE-Band+PB-ROE+EV/EBITDA+估值陷阱+交叉验证+目标价） | `--stock 600519.SH --years 5 --json` |
| `analyze_stock_company_info.py` | 公司基本信息 | `--stock 600519.SH --json` |
| `analyze_stock_shareholder.py` | 股本股东信息+事件统计（股本结构+股东户数+前十大+增减持+实控人+质押+6类事件+综合评分） | `--stock 600519.SH --json` |
| `analyze_stock_news.py` | 公司新闻与行业动态（问财 news-search API） | `--stock 600519.SH --json` |
| `analyze_stock_institute_research.py` | 机构调研分析 | `--stock 600519.SH --json` |
| `analyze_stock_earnings_forecast.py` | 券商盈利预测 | `--stock 600519.SH --json` |
| `analyze_stock_margin.py` | 融资融券分析 | `--stock 600519.SH --json` |

### 高级分析脚本（`scripts/analysis-engine/`）

| 脚本文件 | 功能 | 参数 |
|---------|------|------|
| `analyze_stock_chan.py` | 缠论分析（分型/笔/线段/中枢/MACD背驰/三类买卖点） | `--stock 600519.SH --json` |
| `analyze_elliott_wave.py` | 艾略特波浪分析（5浪推动+3浪调整+斐波那契校验） | `--stock 600519.SH --json` |
| `analyze_harmonic_pattern.py` | 谐波形态分析（Gartley/Bat/Butterfly/Crab XABCD） | `--stock 600519.SH --json` |
| `analyze_social_media.py` | 社交媒体情绪分析（多平台舆情+情绪评分+恐惧贪婪指数+反转检测） | `--stock 600519.SH --days 7 --json` |

### 智能选股策略（独立技能 `stock/selection-strategies/`，脚本位于该技能包根目录）

| 脚本文件 | 策略 | 说明 |
|---------|------|------|
| `run_value_investment.py` | 价值投资 | 低PE/PB、高ROE的低估优质股 |
| `run_high_dividend.py` | 高股息 | 股息率高、分红稳定的防御型 |
| `run_growth_stock.py` | 成长股 | 营收/利润高速增长 |
| `run_momentum_breakthrough.py` | 动量突破 | 价格突破关键阻力位 |
| `run_technical_breakthrough.py` | 技术突破 | 均线/形态突破+量能确认 |
| `run_oversold_rebound.py` | 超跌反弹 | RSI/KDJ极度超卖后均值回归 |
| `run_limit_up_leader.py` | 涨停龙头 | 连板强势股的趋势延续 |
| `run_fund_flow_tracking.py` | 资金追踪 | 跟随主力大单净流入方向 |
| `run_chan_stock_selector.py` | 缠论背驰选股 | MACD背驰信号全市场扫描 |
| `run_multi_factor.py` | 多因子横截面 | 7大因子截面Z-score标准化+等权/加权评分+TopN组合 |

### CLI 工具（`scripts/`）

| 文件 | 用途 |
|------|------|
| `market-query-cli.py` | 问财实时行情查询（个股行情/资金/技术指标） |
| `business-query-cli.py` | 经营数据穿透（主营/客户/供应商/合同） |
| `management-query-cli.py` | 股东管理数据（股本/股东/实控人/质押） |

## 脚本调用方式

```bash
# =================== 基础分析 ===================

# 个股全面技术分析
python3 scripts/analysis-engine/analyze_technical.py --stock 600519.SH --json

# 财务分析
python3 scripts/analysis-engine/analyze_financial_report.py --stock 600519.SH --json

# 筹码分析
python3 scripts/analysis-engine/analyze_stock_chips.py --stock 600519.SH --json

# 估值分析（含PE-Band+估值陷阱检测）
python3 scripts/analysis-engine/analyze_stock_valuation.py --stock 600519.SH --json

| `run_fund_flow_tracking.py` | 资金追踪 | 跟随主力大单净流入方向 |
| `run_chan_stock_selector.py` | 缠论背驰选股 | MACD背驰信号全市场扫描 |
| `run_multi_factor.py` | 多因子横截面 | 7大因子截面Z-score标准化+等权/加权评分+TopN组合 |
python3 scripts/analysis-engine/analyze_valuation_models.py --stock 600519.SH --years 5 --json

# 机构调研分析
python3 scripts/analysis-engine/analyze_stock_institute_research.py --stock 600519.SH --json

# 券商盈利预测
python3 scripts/analysis-engine/analyze_stock_earnings_forecast.py --stock 600519.SH --json

# 融资融券分析
python3 scripts/analysis-engine/analyze_stock_margin.py --stock 600519.SH --json

# =================== 高级分析 ===================

# 缠论分析（单级别/多级别联立）
python3 scripts/analysis-engine/analyze_stock_chan.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_stock_chan.py --stock 茅台 --multi-level --json

# 艾略特波浪分析
python3 scripts/analysis-engine/analyze_elliott_wave.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_elliott_wave.py --stock 600519.SH --swing-window 15 --json

# 谐波形态分析
python3 scripts/analysis-engine/analyze_harmonic_pattern.py --stock 600519.SH --json

# 社交媒体情绪分析
python3 scripts/analysis-engine/analyze_social_media.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_social_media.py --stock 600519.SH --days 14 --json

# 财报深度解读
python3 scripts/analysis-engine/analyze_financial_deep.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_financial_deep.py --stock 600519.SH --years 5 --json

# =================== 实时行情/经营数据 ===================

# 实时行情查询
python3 scripts/market-query-cli.py --query "贵州茅台实时行情"

# 经营数据穿透
python3 scripts/business-query-cli.py --query "贵州茅台主营业务构成"

# 股东管理数据
python3 scripts/management-query-cli.py --query "贵州茅台股本结构"

# =================== 智能选股（脚本位于独立技能 stock/selection-strategies/ 根目录） ===================

# 价值投资策略
python3 ../selection-strategies/run_value_investment.py --json

# 高股息策略
python3 ../selection-strategies/run_high_dividend.py --json

# 缠论背驰选股（全市场/指定股票池）
python3 ../selection-strategies/run_chan_stock_selector.py --json
python3 ../selection-strategies/run_chan_stock_selector.py --pool hs300 --signal buy --json

# 多因子横截面选股（7因子Z-score+TopN等权组合）
python3 ../selection-strategies/run_multi_factor.py --json
python3 ../selection-strategies/run_multi_factor.py --top-n 20 --momentum-window 10 --json

# =================== 多估值模型分析 ===================

# 多估值模型分析（DCF+DDM+PE-Band+PB-ROE+EV/EBITDA+交叉验证）
python3 scripts/analysis-engine/analyze_valuation_models.py --stock 600519.SH --json
python3 scripts/analysis-engine/analyze_valuation_models.py --stock 600519.SH --years 5 --json
```

## 十四维分析执行流程

### 阶段一：并行数据采集（14路并发）

**维度1: 技术面** — analyze_technical.py
**维度2: 财务面** — analyze_financial_report.py
**维度3: 财报深度解读** — analyze_financial_deep.py（三表勾稽+盈利质量+造假红旗+杜邦分析+现金流矩阵）
**维度4: 筹码面** — analyze_stock_chips.py + management-query-cli.py
**维度5: 估值面** — analyze_stock_valuation.py
**维度6: 多估值模型** — analyze_valuation_models.py（DCF+DDM+PE-Band+PB-ROE+EV/EBITDA+估值陷阱+交叉验证+目标价）
**维度7: 股本股东+事件统计** — analyze_stock_shareholder.py（股本结构+股东户数+前十大+增减持+实控人+质押+6类事件）
**维度8: 消息/机构/资讯** — analyze_stock_news.py（问财 news-search API）+ analyze_stock_institute_research.py + analyze_stock_earnings_forecast.py + news-search API
**维度9: 实时行情** — market-query-cli.py
**维度10: 经营数据** — business-query-cli.py（主营/客户/供应商/合同）
**维度11: 缠论分析** — analyze_stock_chan.py（形态学+动力学+多级别联立+三类买卖点）
**维度12: 艾略特波浪** — analyze_elliott_wave.py（5浪推动+3浪调整+斐波那契校验）
**维度13: 谐波形态** — analyze_harmonic_pattern.py（Gartley/Bat/Butterfly/Crab XABCD）
**维度14: 社交媒体情绪** — analyze_social_media.py（多平台舆情+情绪评分+恐惧贪婪指数+反转检测）

### 阶段二：数据融合与交叉验证

十四维数据融合策略：
1. **财务 x 经营**：利润表质量 x 收入结构 — 判断营收真实性
2. **财报深度 x 估值**：三表勾稽验证 x 估值分位 — 验证盈利支撑估值的合理性
3. **资金 x 合同**：实时资金流向 x 重大合同 — 识别主力布局
4. **估值 x 业务**：PE/PB分位 x 主营变化 — 判断估值匹配度
5. **筹码 x 供应链**：筹码分布 x 客户/供应商集中度 — 评估机构持仓逻辑
6. **资讯 x 行情**：新闻热点 x 资金流向 — 验证市场反应方向
7. **缠论 x 波浪**：缠论买卖点 x 波浪结构位置 — 双理论交叉验证
8. **波浪 x 谐波**：波浪阶段 x 谐波形态PRZ — 精确反转点位
9. **多模型估值 x 财报深度**：DCF/PE-Band等估值结果 x 三表勾稽质量 — 验证估值假设的财务支撑
10. **股东 x 事件**：股东增减持方向 x 监管函/解禁事件 — 内部人行为 vs 外部事件交叉验证
11. **质押 x 估值**：质押风险 x 多模型估值 — 高质押低估值的陷阱识别

### 阶段三：报告输出

十四维综合评分（0-100），权重分配：
| 维度 | 权重 | 说明 |
|------|------|------|
| 技术面 | 7% | 趋势与买卖点 |
| 财务面 | 8% | 盈利质量与成长性 |
| 财报深度解读 | 8% | 三表勾稽+造假红旗+杜邦分析 |
| 筹码面 | 7% | 主力动向 |
| 估值面 | 7% | 安全边际 |
| 多估值模型 | 8% | DCF+DDM+EV/EBITDA交叉验证 |
| 股本股东+事件 | 7% | 股东面健康度+事件风险 |
| 消息+机构+资讯 | 7% | 情绪、预期与事件驱动 |
| 实时行情 | 5% | 短期动能 |
| 经营面 | 8% | 业务实质与护城河 |
| 缠论分析 | 7% | 形态动力学信号 |
| 艾略特波浪 | 5% | 波浪结构判断 |
| 谐波形态 | 5% | PRZ反转信号 |
| 社交媒体情绪 | 11% | 舆情与情绪驱动 |

### 报告生成（委托 analysis-report）

十四维综合评分完成后，本技能**不自行编写报告或绘图代码**，而是委托 `common/analysis-report` 统一渲染。流程：

1. 将综合评分、各维度分项、关键指标、风险与数据来源整理为 `analysis-report` 的输入 JSON（含 `title` / `generated_at` / `summary` / `assessment` / `risk_level` / `data_overview` / `core_analysis` / `risks` / `references` / `charts`）。
2. 为每个图表读取 `chart-visualization/references/generate_{type}.md`，按官方字段构造 `args`，并对同一份数据分别用 `theme: "dark"`（背景 `#101418`）与 `theme: "default"`（背景 `#ffffff`）生成两个 URL，写入 `charts[].dark` 与 `charts[].light`。至少 3 个图表。
3. 执行渲染器，一次生成三份文件：

   ```bash
   python3 common/analysis-report/scripts/render_report.py \
     --input report.json \
     --output-dir . \
     --basename 2026-07-25_{股票代码}_stock-analysis
   ```

4. 在最终答复中列出 `{basename}.md`、`{basename}-dark.html`、`{basename}-light.html` 三份文件路径。

报告只给研究结论、情景条件、风险等级和需跟踪指标，**不给出买入/卖出/持有等交易建议**。

## 环境变量

| 变量 | 必填 | 说明 | 获取方式 |
|------|------|------|---------|
| `TUSHARE_TOKEN` | 是 | Tushare Pro API密钥 | https://tushare.pro |
| `IWENCAI_API_KEY` | 是 | 同花顺问财API密钥 | https://www.iwencai.com/skillhub |

## Python 依赖

```
tushare>=1.4.0
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
```

## 数据来源标注

- 量化引擎数据标注「数据来源于Tushare Pro API（日频数据通常每日 18:00 后更新，具体以接口返回为准）」
- 实时行情数据标注「数据来源于同花顺问财（实时）」
- 经营数据标注「数据来源于同花顺问财」
- 资讯搜索标注「数据来源于同花顺问财」

## 数据约定

- 深圳股票代码：`XXXXXX.SZ`（如 `000001.SZ`）
- 上海股票代码：`XXXXXX.SH`（如 `600519.SH`）
- 日期格式：`YYYYMMDD`

## 注意事项

1. 分析结果仅供参考，不构成投资建议
2. Tushare 日频数据通常每日 18:00 后更新，不应标注为固定 T+1；实时数据通过问财API补充
3. 经营层子维度可按需查询，常规分析建议至少覆盖主营业务+主要客户
4. analyze_stock_news 通过问财 news-search API 搜索新闻，不再依赖本地数据库

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro 数据接口（行情/财务/宏观主源） | tushare.pro 个人主页 |
| `IWENCAI_API_KEY` | 同花顺问财 OpenAPI（自然语言数据查询） | 问财开放平台控制台 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   TUSHARE_TOKEN=你的密钥
   IWENCAI_API_KEY=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
