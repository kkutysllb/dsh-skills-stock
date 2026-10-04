---
name: cb-panorama
description:  可转债全景分析场景（编排手册）。用户问「可转债全景 / 转债市场温度 / 转债 估值 / 双低策略池 / 转债周报」等可转债市场类问题时触发。编排 cb-analysis 周度综合引擎（市场温度/规模结构/估值全景/资金情绪/双低池/条款事件， Tushare）+ 问财看板与筛选（16 模块日度补充）+ html-report 看板交付与 报告库归档。产出：单文件 HTML 全景看板。
version: 2.2.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 可转债全景分析场景（编排手册）

本技能是**场景编排层**：以 cb-analysis 周度综合引擎为主轴、问财看板/筛选
做日度补充，完成全市场可转债全景分析并交付 HTML 看板。被分派本场景的代理
（主代理或子代理）按三阶段执行；**产物分区纪律**见顶部「dsh 适配说明」——
引擎输出一律落 `data/`、报告落 `reports/`，从工作区根执行。

## 触发条件

- 「可转债全景」「转债市场分析」「转债估值」「双低策略池」「转债周报」；
- 单只转债深度问题**不**触发本场景（`cli.py analyze --mode single`
  单券六维直接走引擎，无需全景编排）。

## 粒度选择

| 用户问法 | 粒度 | 主轴 |
|---|---|---|
| 转债全景 / 周报 / 本周 | 周度综合引擎（ISO 自然周聚合，主轴） | `analyze_weekly_cb.py`（默认 1 周；`--weeks 2` 含上周对比） |
| 今日转债 / 转债快照 / 某模块 | 日度看板 + 筛选 | `cli.py dashboard --module <模块>` / `cli.py select --query …` |

拿不准时选周度主轴，并在报告注明分析周（week_labels）与数据日期。

## 阶段一：数据采集（必做）

1. 先用 `skill` 工具加载 `cb-analysis` 技能，记下加载结果给出的基目录
   （`Base directory for this skill: ...`）；引擎入口在其 `scripts/` 与
   `scripts/analysis-engine/` 下；

2. 周度主轴**双捕获**（从工作区根执行，脚本用基目录拼接全路径；该引擎
   `--json` 输出干净可直接重定向，但综合研判评分只在 markdown 输出里）：

   ```bash
   mkdir -p data reports
   B="<cb-analysis 基目录>/scripts"
   # 六模块原始数据（表格与图表取数）
   python3 "$B/analysis-engine/analyze_weekly_cb.py" --json > data/cb-weekly.json
   # 综合研判（0-100 评分 + 积极/风险信号；第二次执行命中磁盘缓存，很快）
   python3 "$B/analysis-engine/analyze_weekly_cb.py" > data/cb-weekly.md
   ```

3. `data/cb-weekly.json` 结构：`index_weekly[周]`（中证转债指数周涨跌/
   周均成交/每日明细）、`market`（存续只数/总余额/新上市/退市）、
   `valuation`（周初周末对比：均价/中位价/溢价率/双低/余额/价格分档 +
   `double_low_top10` 双低池）、`funds`（周成交）、`events`（强赎/下修
   条款事件，含公告日期）、`week_labels`/`trade_date`；
   综合研判评分与信号从 `data/cb-weekly.md` 的「综合研判」节**原样转述**；

4. 日度补充（问财口径，需要时）：

   ```bash
   # 16 模块看板：forced-redeem 强赎 / downrev-count 下修 / top10 /
   # dragon-tiger 龙虎榜 / monster-bond 妖债 / arbitrage 套利 …（输出干净 JSON）
   python3 "$B/cli.py" dashboard --module forced-redeem > data/cb-forced.json
   # 自然语言筛选——必须用问财原生字段表述（转股溢价率/价格/规模/评级），
   # 复合指标（如「双低」）问财不识别，用周度引擎的 double_low_top10
   python3 "$B/cli.py" select --query "转股溢价率低于10%的可转债" --limit 20 > data/cb-select.json
   ```

   问财空结果时引擎返回 `empty_data_tip`（建议放宽条件）——如实转述，
   不要编造数据；`--call-type retry` 可标记重试；

5. 个券深挖（可选）：`analyze --mode single --bonds "XX转债"`（问财六维
   + 综合评分）；`cb_data.py basic|daily|terms|ytm --code 128044.SZ`
   （Tushare 数据层：发行/条款/到期收益率）。

依赖：周度引擎与 cb_data 需 TUSHARE_TOKEN；dashboard/select/analyze 需
IWENCAI_API_KEY（均由壳注入环境；缺哪个就跳过对应模块并注明「无数据」
及原因，禁止编造数值）。

## 阶段二：解读与补充（可选，用户要「深度/详细」时执行）

用 `subagent` 工具并行委派（委派 prompt 必须写明：先 `skill` 加载对应
技能、要执行的命令与输出路径、输出格式；返回数值原样转述）：

| 补充 | 加载技能 | 重点 |
|---|---|---|
| 双低池正股联动 | stock-analysis | 双低池 TOP10 标的的正股趋势与联动信号 |
| 宏观利率背景 | macro-query | 转债估值对利率与资金面敏感，Shibor 走势做背景 |
| 条款事件影响 | （复用 events 数据） | 强赎公告/下修逐条列出影响标的与博弈含义 |

## 阶段三：报告交付（必做）

1. 按 `html-report` 技能的报告 JSON 契约（其 `references/report-schema.md`）
   构造可转债全景报告，写 `reports/report.json`：
   - 评分卡：综合研判评分（0-100，取自 markdown 输出）、市场温度一句话
     （指数周涨跌 + 周成交）、积极/风险信号；
   - 图表：中证转债指数周内每日收盘与成交额（line）、价格分档分布对比
     （bar，周初 vs 周末）、双低池 TOP10 双低值（bar）；
   - 分节正文：市场温度（周涨跌表）/ 规模结构 / 估值全景（均价·溢价率·
     双低）/ 资金情绪 / 双低池 TOP10 完整表格 / 条款事件表（含公告日期）；
   - 风险提示与参考来源（Tushare/问财接口名 + 数据日期）；
2. 渲染（从工作区根执行）：

   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/cb-panorama.html
   ```

3. 用 report_archive 工具（契约见 html-report 技能）归档报告库：
4. 向用户给出文件绝对路径交付 `reports/cb-panorama.html`，消息区给出综合研判评分、
   市场温度与关键信号（强赎/下修事件数、双低池头部标的）摘要。

## 输出纪律（强约束）

- 六模块数值与表格**原样转述**，综合研判 0-100 分口径不得改写；
- 双低池 TOP10 表格完整保留，不得截断或重排；
- 条款事件注明公告日期；周度口径注明分析周（ISO 周标签）与数据日期；
- 金额/余额口径按引擎输出（亿元），不要再次换算；
- 问财空结果按 `empty_data_tip` 如实转述并建议放宽条件；缺失维度诚实
  标注「无数据」及原因（如缺 TUSHARE_TOKEN / IWENCAI_API_KEY），
  禁止以「中性」掩盖；
- 结论必须带综合评分、市场温度与数据日期；全文为研究参考口径，
  不构成投资建议。

