---
name: industry-analysis
description: A股行业六维一体深度分析引擎——结构层（产业链上中下游拆解）+数据层（行业估值/财务/盈利排名）+框架层（五模块产业链解读）+研究层（券商研报）+资讯层（实时财经资讯）+宏观框架层（全球宏观周期定位），开箱即用的跨平台技能包。
version: 2.0.2
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# A股行业六维一体深度分析引擎

## 执行方式（先读这里）

**禁止自行编写数据分析脚本**：本技能提供现成 CLI，直接调用即可完成行业数据查询：

```bash
cd <本技能包根>/scripts && python3 industry-query-cli.py --query "A股行业估值排名"
# 示例：--query "银行业盈利数据" / "新能源板块行情"
```

输出为问财 API 返回的行业数据条目。**先运行上面这行命令，把返回数据当作事实来源**；六维框架解读（产业链拆解、券商研报、资讯）基于此数据展开即可。禁止自行写 Python/curl 探测 API、禁止花多轮调试参数。若脚本报错，把错误信息原样转述给用户即可，不要尝试自行修复环境。数据缺失时如实说明「未查到」，**禁止编造数据**。

## 技能概述

本技能包提供完整的行业深度分析能力，整合六大核心维度：

1. **结构层** — 产业链上中下游拆解、核心公司识别（问财实时数据）
2. **数据层** — 行业估值排名、财务指标、盈利数据、板块行情（问财 API）
3. **框架层** — 五模块产业链解读框架（顶层评估→驱动→本质→产业链→风险）
4. **研究层** — 券商研报搜索（机构评级、目标价、投资逻辑）
5. **资讯层** — 实时财经资讯（政策/技术/竞争/投融资动态）
6. **宏观框架层** — 全球宏观周期定位与行业映射

## 分析脚本

### 产业链分析脚本（`scripts/analyze_industry.py`）

基于同花顺问财实时获取产业链数据（网关 CLI 主数据源，pywencai 可选），支持：

```bash
# 标准分析
python3 scripts/analyze_industry.py "新能源汽车"

# 深度分析
python3 scripts/analyze_industry.py "人工智能" --depth detailed

# JSON 输出
python3 scripts/analyze_industry.py "半导体" --json

# 保存结果
python3 scripts/analyze_industry.py "光伏" --save

# 列出支持的热门行业
python3 scripts/analyze_industry.py --list
```

覆盖维度：
- 行业概览：概念股数量、市值分布、行业归属
- 产业链结构：上中下游环节拆解、核心公司
- 财务分析：营收、净利润增长、估值水平
- 风险提示：估值、政策、市场风险

### 行业数据查询 CLI（`scripts/industry-query-cli.py`）

通过问财 API 查询行业数据：

```bash
# 行业估值排名
python3 scripts/industry-query-cli.py --query "A股行业估值排名"

# 行业盈利数据
python3 scripts/industry-query-cli.py --query "银行业盈利数据"

# 板块行情
python3 scripts/industry-query-cli.py --query "新能源板块行情"
```

## 六维分析执行流程

### 阶段一：并行数据采集（4路并发）

**维度1: 结构层** — analyze_industry.py
- 产业链上中下游拆解
- 核心公司识别与市值分布
- PE/利润增长等财务指标

**维度2: 数据层** — industry-query-cli.py
- 行业估值排名
- 行业盈利数据
- 板块涨跌幅排名

**维度3: 研究层** — 问财研报搜索 API
- API: `POST https://openapi.iwencai.com/v1/comprehensive/search`
- Headers: `X-Claw-Skill-Id: report-search, X-Claw-Skill-Version: 2.0.0`
- Query: `"{行业名}行业研究报告"`

**维度4: 资讯层** — 问财经资讯搜索 API
- API: `POST https://openapi.iwencai.com/v1/comprehensive/search`
- Headers: `X-Claw-Skill-Id: news-search, X-Claw-Skill-Version: 1.0.0`

### 阶段二：五模块框架分析

使用产业链解读框架整合数据：

1. **行业整体评估与投资价值定调** — 五维度雷达评分
2. **核心驱动与长期确信** — 底层逻辑拆解，结合政策资讯验证
3. **产业本质与商业模式** — 传导路径与边界
4. **产业链全链路拆解与咽喉节点** — 结合 analyze_industry 结果
5. **宏观周期与行业映射** — 结合全球宏观框架
6. **核心风险与长期基本面跟踪** — 实时资讯+宏观风险预警

### 阶段三：图表生成

- **雷达图** — 行业五维评估（天花板/护城河/生命周期/竞争格局/政策顺风）
- **柱状图** — 行业估值排名对比
- **饼图** — 产业链各环节占比
- **桑基图** — 产业链上下游流转

### 阶段四：报告生成（单文件 HTML 直接落盘）

dsh 宿主没有 render_html_report 看板工具，本技能在 dsh 下改为**直接编写并交付单文件 HTML 报告**（写入当前工作目录，双击浏览器可离线打开）。流程：

1. 将行业画像、估值排名、研报观点、实时资讯、产业链解读、宏观周期评估、风险与跟踪指标整理为报告 JSON，顶层字段：`title` / `generated_at` / `summary` / `assessment` / `risk_level` / `data_overview` / `core_analysis` / `risks` / `references` / `charts`。
2. 图表用内嵌 SVG 或 CSS 绘制（可复用 chart-visualization 技能生成 ECharts 图表后以内嵌方式合入），**禁止使用远程图片 URL**。至少 3 个图表。
3. 用文件写入工具把完整报告落盘为 `行业分析报告-<行业名>-<日期>.html`，并向用户给出文件绝对路径；**不要**把整份 HTML 贴进对话，也不要把大 JSON 读入上下文。

报告覆盖：行业画像（五维雷达图 + 最新动态）、行业估值排名（柱状图）、投研观点摘要、行业实时资讯、产业链深度解读（桑基图/饼图）、宏观周期评估、风险与需跟踪指标。报告只给研究结论、情景条件、风险等级和需跟踪指标，**不给出买入/卖出/持有等交易建议**。

## 参考文档

| 文件 | 说明 |
|------|------|
| `references/industry-chain-framework.md` | 产业链解读五模块框架（V3.0） |
| `references/analysis-framework.md` | 详细分析方法论与双轨制产业链分析 |
| `references/output-template.md` | 标准化报告输出模板 |
| `references/data-sources.md` | 可靠数据源参考 |
| `references/global-macro.md` | 全球宏观周期分析框架 |
| `references/chart-specs.md` | 图表可视化规范 |

## 数据模型

`models/industry_models.py` 提供 Pydantic 数据模型：
- `IndustryChainNode` — 产业链节点
- `IndustryChainAnalysis` — 产业链分析结果
- `IndustryOverview` — 行业概览
- `StockInIndustry` — 行业内个股
- `IndustryAnalysisResult` — 完整分析结果

## 环境变量

| 变量 | 必填 | 说明 | 获取方式 |
|------|------|------|---------|
| `IWENCAI_API_KEY` | 是 | 同花顺问财API密钥 | https://www.iwencai.com/skillhub |

## Python 依赖

```
pandas>=2.0.0
pydantic>=2.0.0
# pywencai 可选（增强数据源），非必需：主数据源为问财网关 CLI（纯标准库，无需额外安装）
```

## 数据来源标注

- 产业链数据标注「数据来源于同花顺i问财（问财网关）」
- 行业估值/财务数据标注「数据来源于同花顺问财」
- 研报数据标注来源机构
- 资讯数据标注「数据来源于同花顺问财」

## 注意事项

1. analyze_industry.py 主数据源为问财网关 CLI（industry-query-cli.py，IWENCAI_API_KEY，无需额外安装）；pywencai 仅为可选增强，缺失自动降级，勿因提示去 pip install
2. 行业分析需结合宏观周期阶段，不同周期下同一行业投资逻辑可能截然不同
3. 资讯层建议至少查询行业动态+政策两条，覆盖基本面和技术面
4. 分析结果仅供参考，不构成投资建议

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `IWENCAI_API_KEY` | 同花顺问财 OpenAPI（自然语言数据查询） | 问财开放平台控制台 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   IWENCAI_API_KEY=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
