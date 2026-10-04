---
name: stock-screening-theme
description:  自然语言选股流水线场景（编排手册）。用户问「帮我选股 / 筛选 XX 特征的 股票 / 高股息低估蓝筹 / 找标的」等选股类问题时触发。编排 a-stock-screener （自然语言→多策略筛选）→ 批量个股快评（stock-analysis 引擎群）→ html-report 汇总看板与报告库归档。产出：单文件 HTML 选股清单看板。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 自然语言选股流水线场景（编排手册）

本技能是**场景编排层**：a-stock-screener 把自然语言条件映射为多策略组合
初筛，再对头部标的批量快评，交付汇总看板。**产物分区纪律**见顶部「dsh 适配说明」——引擎输出落 `data/`、报告落 `reports/`，从工作区根执行。

## 触发条件

- 「帮我选股」「筛选 XX 的股票」「找几只高股息低估的」「小盘成长选股」；
- 单只股票深度问题不触发（走个股尽调场景）。

## 阶段一：初筛（必做）

```bash
mkdir -p data reports
python3 "<a-stock-screener 基目录>/scripts/cli.py" \
  --query "高股息低估蓝筹股" --top 20 --json > data/screen.json
```

- 输出含 `strategies_used`（命中的策略组合，如 value_dividend/value_low_pe）
  与逐股评分；`--top` 控制返回数（默认 10，选股清单建议 20）；
- **`--mock` 禁止用于正式交付**（伪数据，仅调试链路用）；
- 条件表述贴近问财/策略原生语义（股息率/PE/PB/ROE/市值/成长性），
  复合诗意表述（「穿越牛熊的长跑者」）会被降级映射，结果注明策略解释。

依赖：TUSHARE_TOKEN / IWENCAI_API_KEY（壳已注入；缺则按「无数据」口径，
禁止编造）。

## 阶段二：批量快评（必做，按长任务纪律并行）

对初筛 top N（用户未指定时取前 10）并行采集快评（subagent 分派或
run_in_background；基目录 = stock-analysis 技能加载结果）：

| 维度 | 命令要点 |
|---|---|
| 公司信息 | `analyze_stock_company_info.py --stock <代码> --json > data/quick-<代码>.json` |
| 估值 | `analyze_stock_valuation.py --stock <代码带后缀> --json`（必须 .SH/.SZ 后缀） |

每股一份 `data/quick-*.json`；收齐后统一校验退出码与 error 键。

## 阶段三：汇总交付（必做）

1. html-report 契约构造 `reports/report.json`：
   - 评分卡：命中策略组合 + 入选数 + 一句话画像；
   - 图表：入选股综合评分（bar）、估值百分位分布（bar）；
   - 分节正文：清单总表（代码/名称/评分/策略命中/估值百分位）+ 每股
     2-3 条快评；落选说明（策略解释，帮助用户放宽/收紧条件）；
   - 风险提示与参考来源（接口名 + 数据日期）；
2. 渲染 `-o reports/screening.html`，归档报告库，向用户给出文件绝对路径交付。

## 阶段四：归档选股库（必做，交付后收口）

把本次选股沉淀为「选股库」方案资产——工作台侧栏「选股库」面板可随时
回看、重跑、跨期重合对比（保留/新增/剔除）。dsh 下走本插件注册的同名四库 agent 工具（投研工作台对应库面板随时回看），三步（工具调用，失败不阻塞交付）：

1. `selection_create`（{name, criteria}）建选股方案（一句话口径），返回 `selection_id`；
2. `selection_save_version`（{selection_id, criteria_json, change_note, parent_version}）存口径版本：criteria_json.summary 必填；
3. `selection_record_run`（{selection_id, version, trade_date, universe, rules, metrics, report?, picks?}）存执行结果：picks=[{code,name,score,strategies,rank}]（code 带交易所后缀），report=报告全文。

- **重跑同一方案**：不要 *_create 新方案——用 *_list 定位既有 id 后迭代；口径变化时*_save_version 落新版本（change_note 说明差异）；
  run 一律挂当前版本。这样面板的跨期重合对比才成立；
- `rules.report_id`（**有则必填**）= 阶段三报告库归档返回的 report_id
  ——选股库「看板」按钮直接内嵌该 HTML 看板弹窗；缺链或报告已删自动
  回退纯文本附件，不影响功能；
- picks 的 `code` 必须带交易所后缀（`002170.SZ`）——重合分析按 code
  精确匹配，无后缀会对不上；Top20 建议全量入库（≤4MB 上限）；
- metrics 面板渲染键：**`hit_count`（命中数，必填 = picks 条数）**/
  `strategy_count`（策略数）/ `consensus_count`（共振股数，跨策略重合
  命中）/ `top_n`——漏 hit_count 面板命中列会显示「—」；漏检即补
  （可事后 UPDATE metrics_json）。其余自由指标（漏斗口径如
  pool_initial/gates_passed、report_metrics 卡片数组）存着不展示；
- 引擎不可达时在最终回复里明说「未归档选股库」，其余交付照常（与
  报告库归档同款降级语义）。

## 输出纪律（强约束）

- 策略命中与评分**原样转述**，禁止重算或重排；
- 快评数值原样转述；估值必须带后缀代码口径；
- mock 模式结果禁止进入交付物；
- 缺失诚实标注「无数据」及原因；结论带数据日期；全文为研究参考口径，
  不构成投资建议。

