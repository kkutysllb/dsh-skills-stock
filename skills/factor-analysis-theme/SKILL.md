---
name: factor-analysis-theme
description:  因子检验流水线场景（编排手册）。用户问「检验这个因子 / IC/IR 分析 / 分层回测 / 多因子选股 / 因子择时」等因子研究类问题时触发。编排 factor-research 八命令（build 因子面板防前视 → analyze IC/IR+分层 → filter/multifactor/timing/combine）+ html-report 报告与报告库归档。 产出：单文件 HTML 因子研究看板。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 因子检验流水线场景（编排手册）

本技能是**场景编排层**：factor-research 的 CLI 八命令构成「面板构造 →
有效性检验 → 组合应用」三段流水线，交付因子研究看板。**产物分区纪律**
见顶部「dsh 适配说明」——因子 CSV 与输出落 `data/`、自建脚本落 `scripts/`、
报告落 `reports/`，从工作区根执行。

## 触发条件

- 「检验这个因子」「IC/IR 怎么样」「分层回测」「六因子选股」「因子拥挤度」；
- 纯策略回测不触发（走策略回测场景）；纯选股走选股流水线。

## 命令地图（基目录 = factor-research 技能加载结果）

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `build` | 因子面板构造（**防前视偏差**） | `--close <收盘价CSV>` `--benchmark <基准CSV 可选>` |
| `analyze` | IC/IR 分析 + 分层回测 | `--factor-csv` `--return-csv` `--n-groups 5` |
| `filter` | 基本面因子筛选（实测真数据） | `--codes 600519.SH,000001.SZ` `--pe-max --pb-max --roe-min` |
| `multifactor` | 六因子选股 | `--panel-dir <子指标面板目录>` + TopN |
| `timing` | 因子择时与拥挤度 | 面板目录 |
| `smallcap` / `combine` | 小盘成长 / 多因子组合 | 面板目录 |

CSV 契约：`--close/--factor-csv/--return-csv` 均为 **index=date、
columns=股票代码** 的宽表，先落 `data/` 再引用。

## 阶段一：数据与面板（必做）

1. `skill` 加载 factor-research，记基目录；
2. 行情面板：从 kk_common 网关拉标的池日线（自建 `scripts/fetch_close.py`
   产出 `data/close.csv`，宽表口径如上）；
3. 因子面板：`build` 从行情派生动量/波动率/换手/规模/β 等子指标
   （防前视），或用户自带因子 CSV 落 `data/factor.csv`；
4. 前瞻收益矩阵由 build 一并产出（检验的对齐基准）。

依赖：TUSHARE_TOKEN（壳已注入；缺则按「无数据」口径，禁止编造）。

## 阶段二：检验（必做）

```bash
B="<factor-research 基目录>/scripts/cli.py"
python3 $B analyze --factor-csv data/factor.csv --return-csv data/fwd.csv \
  --n-groups 5 --output-dir data/ > data/ic.json
```

- IC 序列 / IR / 分层收益与多空组合是有效性结论的三支柱，缺一不可；
- 大面板检验属长任务——run_in_background 后台化后收 job_output；
- 稳健性：换分组数（3/5/10）与窗口重跑，结论只在一致性下成立。

## 阶段三：组合应用（可选，用户要「落地选股」时）

`filter`（基本面约束）→ `multifactor`（六因子打分 TopN）→ `timing`
（拥挤度调仓提示），逐级收窄，输出均落 `data/`。

## 阶段四：报告交付（必做）

1. html-report 契约构造 `reports/report.json`：评分卡（IC 均值/IR/多空
   年化）、IC 时间序列（bar）、分层净值（line，G1..G5+多空）；分节正文 =
   因子定义 / 面板口径（防前视）/ 检验结果 / 稳健性 / 组合应用；
2. 渲染 `-o reports/factor-<因子名>.html`，归档报告库，向用户给出文件绝对路径交付。

## 阶段五：归档因子库（必做，交付后收口）

把本次因子检验沉淀为「因子库」资产——工作台侧栏「因子库」面板可随时
回看 IC 曲线叠加、跨版本对比、重跑。dsh 下走本插件注册的同名四库 agent 工具（投研工作台对应库面板随时回看），三步（工具调用，失败不阻塞交付）：

1. `factor_create`（{name, hypothesis, category}）建因子资产，返回 `factor_id`；
2. `factor_save_version`（{factor_id, code, params, change_note, parent_version}）存因子代码版本（code 全文入库，禁止只留在会话工作区）；
3. `factor_record_run`（{factor_id, version, universe, data_start, data_end, config, metrics, ic_series?, layers?}）存检验结果：config 原样抄录检验配置；metrics 含 ic_mean / ir 等核心键；ic_series=逐期 IC（≤2MB），layers=分层回测（≤4MB）。

- **多因子/多变体研究**（一次检验 N 个变体，如「8 变体有效性」）：
  每个变体建独立因子资产——name 带变体标识区分（如「动量·20日月频」
  「动量·60日」「动量·10分组」），category 共用，hypothesis 写变体差异；
  逐变体走上面三步（代码/params 各自落版本，ic_summary 的五指标 +
  ic 序列 + 分层各自归 run）。禁止因"变体多"而整体跳过归档只交报告
  ——报告库与因子库是两个互补资产面；
- **重跑同一因子**：不要 *_create 新因子——用 *_list 定位既有 id 后迭代；代码或参数变化时*_save_version 落新版本（code 变了 sha256 才变，
  change_note 说明差异）；run 一律挂当前版本；
- metrics 面板渲染键（**漏了对应列显示「—」**）：`ic_mean` / `ir` /
  `ic_positive_pct` / `long_short_spread_pct` / `n_periods`；漏检可事后
  UPDATE metrics_json 补；
- ic_series 兼容 `[{date, ic}]` 对象数组与纯数值数组（面板做累计 IC）；
- 引擎不可达时在最终回复里明说「未归档因子库」，其余交付照常（与
  报告库归档同款降级语义）。

## 输出纪律（强约束）

- IC/IR/分层数值**原样转述**，禁止改写或只报最优层；
- 面板口径必须注明（构造窗口/复权/防前视处理）；
- 因子有效但拥挤（timing 高位）必须显式警示；
- 缺失诚实标注「无数据」及原因；结论带数据日期；全文为研究参考口径，
  不构成投资建议。

