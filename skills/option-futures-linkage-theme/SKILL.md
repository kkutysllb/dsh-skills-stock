---
name: option-futures-linkage-theme
description:  期指期权联动分析场景（编排手册）。用户问「期指期权联动 / 期权 PCR 与期指 方向 / 期权持仓变化与期货持仓印证」等期权×期货交叉验证类问题时触发。 编排 option-futures-linkage 联动引擎（期权五维 × 期指维度，信号评分 -6..+6）+ futures-analysis / options-volatility 两翼交叉 + html-report 看板交付与报告库归档。产出：单文件 HTML 联动看板。
version: 2.2.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 期指期权联动分析场景（编排手册）

本技能是**场景编排层**：以 option-futures-linkage 引擎为主轴（期权五维 ×
期指维度的联动信号矩阵），完成「期权指标 × 期指持仓/基差」交叉验证并交付
HTML 看板。被分派本场景的代理（主代理或子代理）按三阶段执行。

## 触发条件

- 「期指期权联动」「期权印证期指」「PCR 与期货多空」「期权持仓与期货席位」
  等跨品种交叉类问题；
- 期指专题或期权 ETF 分析中用户追问「两边信号是否印证」时。

## 品种映射（引擎固定口径）

| 期指 | 期权标的 |
|---|---|
| IF（沪深300） | 300ETF 期权（510300.SH） |
| IH（上证50） | 50ETF 期权（510050.SH） |
| IC（中证500） | 500ETF 期权（510500.SH） |
| IM（中证1000） | CFFEX MO 股指期权 |

## 粒度选择

| 用户问法 | 粒度 | 命令（基目录相对路径） |
|---|---|---|
| 今天 / 最新 / 盘后 | 日度 | `python3 scripts/analysis-engine/analyze_option_futures.py --json` |
| 本周 / 周度复盘 | 周度 | `python3 scripts/analysis-engine/analyze_weekly_option_futures.py --json`（`--weeks 1` 默认，ISO 周聚合周均 PCR / IV） |

拿不准时选日度（默认全品种、回溯 30 天），并在报告注明粒度与数据窗口。

## 阶段一：数据采集（必做）

1. 先用 `skill` 工具加载 `option-futures-linkage` 技能，记下加载结果给出的
   基目录（`Base directory for this skill: ...`）；引擎入口在其
   `scripts/analysis-engine/` 下；

2. 采集命令（**从工作区根执行**，脚本用基目录拼接全路径、输出相对工作区
   落 `data/`；该引擎 `--json` 输出干净——进度日志被引擎自身 guard，
   可直接重定向；stderr 不会混入 JSON）：

   ```bash
   mkdir -p data reports
   B="<option-futures-linkage 基目录>/scripts/analysis-engine"
   # 日度（默认全部品种，回溯 30 天）
   python3 "$B/analyze_option_futures.py" --json > data/of.json
   # 周度（周均 PCR / 周 ATM IV / 周涨跌与周持仓变化）
   python3 "$B/analyze_weekly_option_futures.py" --json > data/of.json
   # 收窄：--symbols IF IM --days 5
   ```

3. 读取 `data/of.json`：`symbols[IF|IH|IC|IM].{option(PCR/IV/IV斜率),
   futures(基差/持仓), linkage}` 每品种联动方向（偏多/略偏多/中性/略偏空/
   偏空）与五维联动评分（-6..+6）+ `composite.{avg_score, market_env,
   symbol_scores}` 综合研判。

依赖：脚本需要 TUSHARE_TOKEN 与 pandas（数据源凭据已由壳注入环境，缺
token 时脚本明确报错——此时按「无数据」口径处理，禁止编造数值）。

## 阶段二：交叉解读（本场景核心）

1. 逐品种（IF/IC/IH/IM 对应期权）对齐三组信号：

   | 信号源 | 指标 | 印证问题 |
   |---|---|---|
   | 期权（of.json 的 option 维） | PCR（成交/持仓）、ATM IV、IV 斜率 | 情绪与保险需求方向 |
   | 期货（of.json 的 futures 维） | 基差率、多空持仓变化 | 现实多头空头力量 |
   | 联动引擎（linkage 维） | 五维信号矩阵、联动评分 | 两者共振/背离结论 |

2. 需要「深度」时用 `subagent` 并行委派两翼补充（委派 prompt 必须写明：
   先 `skill` 加载对应技能、要执行的命令、输出格式；返回数值原样转述）：

   | 两翼 | 加载技能 | 用法与重点 |
   |---|---|---|
   | 席位明细 | futures-analysis | 从工作区根跑 `analyze_futures.py --type holding --json --symbols <品种>`（JSON 前有一行日志，需 `sed -n '/^{/,$p'` 截取到 `data/holding.json`），取前 20 席位与中信风向标印证期货维 |
   | 波动率环境 | options-volatility | 计算器（非取数器）：把联动输出的 ATM IV 喂 `--action iv-rv --iv X --rv-20d ... --json` 或 `--action regime`，判断 IV 相对历史分位与拥挤度 |

3. 信号矛盾时明确标注「背离」并给出两种解读（情绪领先 vs 套保压制），
   禁止强行统一口径。

## 阶段三：报告交付（必做）

1. 按 `html-report` 技能的报告 JSON 契约（其 `references/report-schema.md`）
   构造联动报告：
   - 结论卡：composite 综合评分、市场环境、共振/背离品种计数、一句话结论；
   - 图表：分品种联动评分（bar）、周均 PCR 与期指净持仓变化对照
     （line/bar 双系列）、基差率时间序列（line）；
   - 分节正文：每品种小节 = 期权维明细表 + 期货维明细表 + 联动信号
     矩阵 + 2-3 条交叉解读（带数据依据，背离显式标注）；
   - 风险提示与参考来源（Tushare 接口名 + 数据日期）；
2. 保存为 `reports/report.json` 后用 html-report 技能渲染器产出单文件 HTML
   （渲染器路径用 html-report 技能加载结果给出的基目录拼接，从工作区根执行）：

   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/option-futures-linkage.html
   ```

3. 用 report_archive 工具（契约见 html-report 技能）归档报告库：
4. 向用户给出文件绝对路径交付 `reports/option-futures-linkage.html`，消息区给出综合
   评分、各品种联动方向与共振/背离关键信号摘要。

## 输出纪律（强约束）

- 三组信号数值**原样转述**，禁止改写数值或丢弃信号矩阵；
- 口径固定：基差 = 期货 − 现货（升水为正）；PCR = 认沽/认购；
- 背离必须显式标注并给两种解读，不得回避或强行统一；
- 期权与期货数据交易日对齐（披露 T+1 口径），错位时注明；
- 缺失维度诚实标注「无数据」及原因，禁止以「中性」掩盖；
- 结论必须带综合评分、方向与数据日期；全文为研究参考口径，
  不构成投资建议。

