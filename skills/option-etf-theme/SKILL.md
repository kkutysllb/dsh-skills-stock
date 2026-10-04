---
name: option-etf-theme
description:  期权 ETF 专题分析场景（编排手册）。用户问「期权 ETF 分析 / 7 大期权 ETF / ETF 份额与期权波动率 / 50ETF 300ETF 500ETF 创业板 科创50 中证1000 深100」 等期权 ETF 类问题时触发。并行编排 etf-analysis（行情/份额/规模主面板）+ option-futures-linkage（期权五维联动，覆盖 4 条期指线）+ market-linkage-engine（8 维联动背景）+ html-report 看板交付与报告库归档。 产出：单文件 HTML 期权 ETF 专题看板（7 标的资金/情绪方向矩阵）。
version: 2.2.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 期权 ETF 专题分析场景（编排手册）

本技能是**场景编排层**：并行采集三大引擎数据，汇总 7 大期权 ETF 标的的
资金/情绪方向矩阵并交付 HTML 看板。被分派本场景的代理（主代理或子代理）
按三阶段执行；**产物分区纪律**见顶部「dsh 适配说明」——引擎输出一律落
`data/`、报告落 `reports/`，从工作区根执行。

## 触发条件

- 「期权 ETF 分析」「7 大期权 ETF」「ETF 份额变化」「期权标的 ETF」等；
- 用户点名具体标的（50ETF/300ETF/500ETF/创业板ETF/科创50/中证1000/深100）；
- 大盘资金面问题不触发本场景（走市场联动）。

## 7 大期权 ETF 标的（固定面板）

| ETF | 代码 | 期权联动覆盖 |
|---|---|---|
| 上证50ETF | 510050.SH | ✅ option-futures IH 线 |
| 沪深300ETF | 510300.SH | ✅ option-futures IF 线 |
| 中证500ETF | 510500.SH | ✅ option-futures IC 线 |
| 中证1000ETF | 512100.SH | ✅ IM/MO 线（CFFEX 股指期权代理） |
| 创业板ETF | 159915.SZ | ➖ 无期权联动维度（仅行情/份额） |
| 科创50ETF | 588000.SH | ➖ 无期权联动维度 |
| 深100ETF | 159901.SZ | ➖ 无期权联动维度 |

期权五维联动（PCR/IV 等）只有 4 条期指线；后三只必须诚实标注
「无期权联动维度」，禁止硬套。

## 粒度选择

| 用户问法 | 粒度 | 主轴 |
|---|---|---|
| 今天 / 最新 / 盘后 | 日度 | etf compare 快照 + option-futures 日度 + linkage daily |
| 本周 / 周度复盘 | 周度 | option-futures 周度引擎 + etf daily/shares 周窗口序列 + linkage weekly |

拿不准时选日度，并在报告注明数据日期。

## 阶段一：并行数据采集（必做，用 subagent 三路并行）

先在工作区根 `mkdir -p data reports`；三路委派 prompt 都必须写明：先
`skill` 加载对应技能、记下基目录、执行命令与输出路径（`data/` 下）、
输出格式；返回数值原样转述，不得改写。

| 路 | 加载技能 | 命令（从工作区根执行，基目录按加载结果拼接） |
|---|---|---|
| A 主面板 | etf-analysis | `python3 "<etf-analysis 基目录>/scripts/cli.py" tushare compare --params ts_codes=510050.SH,510300.SH,510500.SH,159915.SZ,588000.SH,512100.SH,159901.SZ > data/etf-compare.json`（输出干净 JSON：价格/涨跌幅/20日60日收益/最新份额(亿份)/成交额/规模） |
| A 补充 | etf-analysis | 趋势需要时：`…tushare daily --params ts_code=510300.SH limit=30 > data/etf-daily-300.json`；份额需要时：`…tushare shares --params ts_code=510300.SH limit=30 > data/etf-shares-300.json`（逐标的采集，4 条联动线优先） |
| B 期权维度 | option-futures-linkage | `python3 "<option-futures-linkage 基目录>/scripts/analysis-engine/analyze_option_futures.py" --json > data/of.json`（输出干净可直接重定向；周度换 `analyze_weekly_option_futures.py`） |
| C 联动背景 | market-linkage-engine | `PYTHONPATH="<market-linkage-engine 基目录>" python3 -m market_linkage_engine daily -f json -o data/linkage.json`（重点看期权波动率/宽基 ETF 份额两维；周度换 weekly） |

- etf-analysis 失败时 stdout 也会是 `{"error": ...}` JSON 且退出码非 0——
  **先看退出码再解析**；
- 问财 `selector` 引擎（`…cli.py selector --query "..."`，需 IWENCAI_API_KEY）
  是自然语言模糊筛选，只用于用户点名的**池外标的**或主题筛选，不用于
  固定 7 标的主面板；缺 key 时跳过并注明。

依赖：A/B/C 均需 TUSHARE_TOKEN（壳已注入；缺 token 明确报错——按
「无数据」口径处理，禁止编造数值）。

## 阶段二：汇总方向矩阵（本场景核心）

1. 逐标的合成一行（7 行矩阵）：价格信号（compare 的 pct_chg/return_20d/
   60d）+ 份额申赎（shares 环比或 compare 的 latest_share_yi 对比期初）
   + 期权信号（of.json 对应品种 linkage 方向/评分；无覆盖标 ➖）
   → **综合方向**（偏多/略偏多/中性/略偏空/偏空）；
2. 共振/背离逐标的标注：份额放量申购 + 价格滞涨 = 背离信号，必须显式
   标注并给两种解读；期权与份额方向矛盾同样标注；
3. C 路联动背景做校验：矩阵结论与 8 维联动综合评分方向严重矛盾时，
   回查数据日期是否错位（T+1 口径），不要硬凑一致。

## 阶段三：报告交付（必做）

1. 按 `html-report` 技能的报告 JSON 契约（其 `references/report-schema.md`）
   构造期权 ETF 专题报告，写 `reports/report.json`：
   - 评分卡：7 标的综合方向矩阵表（价格/份额/期权三列信号 + 综合方向）、
     联动背景综合评分、一句话结论；
   - 图表：重点标的份额时间序列（line）、7 标的近 20 日收益对比（bar）、
     4 条联动线评分（bar）；
   - 分节正文：每标的小节 = 关键指标明细表 + 2-3 条解读（带数据依据，
     背离显式标注）；池外标的单独一节并标注「无期权联动维度」；
   - 风险提示与参考来源（Tushare 接口名 + 数据日期）；
2. 渲染（从工作区根执行）：

   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/option-etf.html
   ```

3. 用 report_archive 工具（契约见 html-report 技能）归档报告库：
4. 向用户给出文件绝对路径交付 `reports/option-etf.html`，消息区给出方向矩阵摘要
   （偏多/偏空标的计数 + 关键背离信号）。

## 输出纪律（强约束）

- 三路引擎数值与表格**原样转述**，禁止改写数值或丢弃矩阵行；
- 份额与价格的同向/背离逐标的标注；金额/份额口径按引擎输出（亿元/亿份，
  不要再次换算）；
- 非期权联动标的（159915/588000/159901）不得硬套期权维度，标注
  「无期权联动维度」；IM/MO 代理口径注明；
- 数据交易日对齐（披露 T+1），错位时注明；缺失维度诚实标注「无数据」
  及原因，禁止以「中性」掩盖；
- 结论必须带数据日期与联动背景评分；全文为研究参考口径，不构成投资建议。

