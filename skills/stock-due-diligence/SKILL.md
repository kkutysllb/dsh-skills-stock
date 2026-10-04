---
name: stock-due-diligence
description:  个股尽调全景场景（编排手册）。用户问「XX 股票怎么样 / 个股深度分析 / 尽调 / 全维度研报」等单只股票深度问题时触发。并行编排 stock-analysis 引擎群 （公司信息/估值/财务深挖/盈利预测/筹码/新闻）+ financial-statement 三表 + valuation-model PE-Band + html-report 看板交付与报告库归档。 产出：单文件 HTML 个股尽调看板。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 个股尽调全景场景（编排手册）

本技能是**场景编排层**：并行采集 stock-analysis 引擎群与补充引擎，完成
单只股票的全维度尽调并交付 HTML 看板。被分派本场景的代理（主代理或子代理）
按三阶段执行；**产物分区纪律**见顶部「dsh 适配说明」——引擎输出一律落
`data/`、报告落 `reports/`，从工作区根执行。

## 触发条件

- 「XX 股票怎么样」「深度分析 XX」「XX 尽调」「XX 全维度研报」；
- 行业/板块整体问题**不**触发（走行业分析）；纯行情查询走行情技能。

## 阶段一：并行数据采集（必做，多引擎可用 subagent 或后台化并行）

先在工作区根 `mkdir -p data reports`。命令统一形态：脚本用技能加载结果
给出的基目录拼接全路径、`--json > data/xxx.json` 落盘。股票代码口径
**以带交易所后缀为准**（600519.SH / 000001.SZ）——估值引擎不认裸代码
（实测「600519」报「无法识别股票」，600519.SH 通过）。

| 引擎 | 加载技能 | 命令要点（全路径 + 落 data/） |
|---|---|---|
| 公司信息 | stock-analysis | `…/analysis-engine/analyze_stock_company_info.py --stock <代码或名称> --json > data/co.json`（名称/裸代码均可） |
| 估值全景 | stock-analysis | `…/analysis-engine/analyze_stock_valuation.py --stock 600519.SH --json > data/val.json`（**必须带后缀**；输出 current/historical_percentile/industry_percentile/ratings） |
| 财务深挖 | stock-analysis | `…/analysis-engine/analyze_financial_deep.py --stock <代码或名称> --years 3 --json > data/fd.json` |
| 盈利预测 | stock-analysis | `…/analysis-engine/analyze_stock_earnings_forecast.py --stock <代码或名称> --json > data/ef.json`（券商覆盖机构数/EPS/NP 一致预期） |
| 三表关键指标 | financial-statement | `…/financial_cli.py 600519.SH --periods 4 > data/fs.txt`（markdown 表） |
| PE-Band | valuation-model | `…/pe_band_cli.py 600519.SH --years 5 > data/peband.txt`（markdown 估值带） |

- 可选补充（按用户问题域）：筹码 `analyze_stock_chips.py`（--stock + --date）、
  舆情 `analyze_stock_news.py --days 7`、机构调研 `analyze_stock_institute_research.py`、
  股东 `analyze_stock_shareholder.py`、技术面 `analyze_technical.py`——
  CLI 形态同上（--stock + --json）；
- 多引擎互不依赖：按长任务纪律并行（subagent 分派或 run_in_background），
  禁止串行干等；输出先校验退出码与 JSON 完整性（error 键）再使用。

依赖：TUSHARE_TOKEN（壳已注入；缺 token 明确报错——按「无数据」口径
处理，禁止编造数值）。

## 阶段二：汇总研判

1. 基本面分层汇总：公司质地（行业/主营）→ 财务（三表 + 深挖）→
   估值（百分位 + PE-Band + 评级）→ 预期（一致预期 EPS/增速）；
2. 交叉校验：估值百分位与 PE-Band 结论矛盾时回查数据日期；
3. 风险清单：财务深挖的风险项 + 估值高位 + 预期下修信号逐条列出。

## 阶段三：报告交付（必做）

1. 按 `html-report` 技能契约构造报告 JSON 写 `reports/report.json`：
   - 评分卡：估值百分位、一致预期 EPS、综合结论一句话；
   - 图表：估值历史百分位（line）、营收/净利趋势（bar，取自财务深挖）、
     PE-Band 区间（line）；
   - 分节正文：公司概况 / 财务 / 估值 / 盈利预测 / 风险，每节明细表 +
     2-3 条解读（带数据依据）；
   - 风险提示与参考来源（Tushare 接口 + 数据日期）；
2. 渲染（从工作区根执行）：

   ```bash
   python3 "<html-report 技能包根>/scripts/render_report.py" \
     reports/report.json -o reports/stock-dd-<代码>.html
   ```

3. 归档报告库（html-report 技能的 report_archive 工具，读 reports/ 下产物）；
4. 向用户给出文件绝对路径交付 HTML，消息区给出估值百分位、一致预期与关键风险摘要。

## 输出纪律（强约束）

- 各引擎数值与表格**原样转述**，禁止改写或丢弃表格；
- 估值口径（TTM/百分位窗口）按引擎输出注明；数据日期逐节标注；
- 缺失维度诚实标注「无数据」及原因，禁止以「中性」掩盖；
- 结论必须分层（质地/财务/估值/预期）并给依据与反证；全文为研究参考
  口径，不构成投资建议。

