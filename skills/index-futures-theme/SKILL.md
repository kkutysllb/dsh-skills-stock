---
name: index-futures-theme
description:  股指期货专题分析场景（编排手册）。用户问「期指分析 / 股指期货 / IF IC IH IM / 基差 / 贴水升水 / 期指多空持仓 / 中信席位」等股指期货类问题时触发。编排 futures-analysis 四维引擎（行情趋势 / 基差期限结构 / 前 20 席位持仓 / 综合研判 100 分）+ 可选期权与问财交叉 + html-report 看板交付与报告库 归档。产出：单文件 HTML 期指专题看板。
version: 2.2.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 股指期货专题分析场景（编排手册）

本技能是**场景编排层**：自身不带数据脚本，编排 futures-analysis 引擎技能
完成一次完整的股指期货专题分析并交付 HTML 看板。被分派本场景的代理
（主代理或子代理）按三阶段执行。

## 触发条件

- 「期指分析」「股指期货」「IF/IC/IH/IM」「基差」「升贴水」「期指持仓」
  「多头持仓 空头持仓」「中信席位」等期指类问题；
- 大盘方向的期指佐证（可与市场联动场景的期指基差维度衔接）；
- 单只个股问题**不**触发本场景。

## 粒度选择

| 用户问法 | 粒度 | 命令（基目录相对路径） |
|---|---|---|
| 今天 / 最新 / 收盘 | 日度 | `python3 scripts/analysis-engine/analyze_futures.py --json` |
| 本周 / 上周 / 周度复盘 | 周度 | `python3 scripts/analysis-engine/analyze_weekly_futures.py --json`（`--weeks 0`=上周，1=上上周） |

拿不准时选日度（默认全品种 IF/IC/IH/IM、回溯 30 天），并在报告注明
粒度与数据窗口。

## 阶段一：数据采集（必做）

1. 先用 `skill` 工具加载 `futures-analysis` 技能，记下加载结果给出的基目录
   （`Base directory for this skill: ...`）；引擎入口在其
   `scripts/analysis-engine/` 下；

2. 采集命令（**从工作区根执行**，脚本用基目录拼接全路径、输出相对工作区
   落 `data/`；引擎在 JSON 前会打一行采集日志，**必须 sed 截取**）：

   ```bash
   mkdir -p data reports
   B="<futures-analysis 基目录>/scripts/analysis-engine"
   # 日度（全品种四维：price / contango / holding + composite）
   python3 "$B/analyze_futures.py" --json 2>/dev/null \
     | sed -n '/^{/,$p' > data/futures.json
   # 周度（周涨跌 / 周 OI 变化 / 周持仓过滤 + 综合研判）
   python3 "$B/analyze_weekly_futures.py" --json 2>/dev/null \
     | sed -n '/^{/,$p' > data/futures.json
   ```

3. **禁止裸 `>` 直接生成 JSON 文件**（引擎在 JSON 前打印一行采集日志，
   裸重定向会把日志混进文件导致解析失败），也不要 cd 进引擎目录执行
   （会把产物写进只读技能目录）；`--type` 局部口径不冒充全量（专题报告
   需要四维齐备，`--type` 仅用于用户点名单维追问时补充）；

4. 常用收窄参数：`--symbols IF IC`（单/多品种）、`--days 15`（缩短回溯）；

5. 读取 `data/futures.json`：`symbols[IF|IC|IH|IM].{price, contango, holding,
   contracts}` 各维明细 + `composite.{avg_score(0-100), market_env,
   divergence_signal, suggestions, details}`（分品种评分与建议）。

依赖：脚本需要 TUSHARE_TOKEN 与 pandas（数据源凭据已由壳注入环境，缺
token 时脚本明确报错——此时按「无数据」口径处理，禁止编造数值）。

## 阶段二：解读与交叉（可选，用户要「深度/详细」时执行）

用 `subagent` 工具并行委派补充解读（委派 prompt 必须写明：先 `skill`
加载对应技能、要执行的命令、输出格式；返回数值原样转述）：

| 交叉源 | 加载技能 | 用法与重点 |
|---|---|---|
| 期权隐含预期 | option-futures-linkage | 从工作区根跑其日度联动引擎（脚本全路径 + `--json > data/of.json`，输出干净可直接重定向），取对应品种 PCR / ATM IV / 联动方向印证期指研判 |
| 盘中/延时行情 | hithink-futures | `python3 scripts/cli.py --query "IF主力合约 最新行情"`（问财口径，需 IWENCAI_API_KEY，缺则跳过并注明） |
| 大盘环境 | macro-query | Shibor 与宏观资金面背景 |

不需要深度解读时跳过本阶段，直接进入阶段三。

## 阶段三：报告交付（必做）

1. 按 `html-report` 技能的报告 JSON 契约（其 `references/report-schema.md`）
   构造期指专题报告：
   - 评分卡：composite 综合评分、市场环境、品种分化信号、一句话结论；
   - 图表：基差率时间序列（line）、四品种前 20 席位多空净持仓对比（bar）、
     分品种综合评分（bar）；
   - 分节正文：每品种小节 = 行情趋势 + 基差与期限结构 + 持仓排名表
     （含中信 vs 其他机构多空变化）+ 2-3 条解读（带数据依据）；
   - 风险提示与参考来源（Tushare 接口名 + 数据日期）；
2. 保存为 `reports/report.json` 后用 html-report 技能渲染器产出单文件 HTML
   （渲染器路径用 html-report 技能加载结果给出的基目录拼接，从工作区根执行）：

   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/index-futures.html
   ```

3. 用 report_archive 工具（契约见 html-report 技能）归档报告库：
4. 向用户给出文件绝对路径交付 `reports/index-futures.html`，消息区给出综合评分、
   市场环境、品种分化与中信席位关键信号摘要。

## 输出纪律（强约束）

- 引擎数值与表格**原样转述**，禁止改写数值或丢弃持仓表；
- 基差 = 期货 − 现货，升水为正；口径不得颠倒；
- 品种分化（IF/IC/IH/IM）必须分开陈述，禁止一锅炖；
- 持仓数据注明交易日（T+1 披露）；缺失维度诚实标注「无数据」及原因
  （如 Tushare 无权限），禁止以「中性」掩盖；
- 结论必须带综合评分、方向与数据日期；方向性判断给依据与反证信号；
- 全文为研究参考口径，不构成投资建议。

