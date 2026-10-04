---
name: strategy-backtest-theme
description:  策略研究回测场景（编排手册）。用户问「写个策略回测 / 双均线策略表现 / 参数扫描 / 走前验证」等策略研究类问题时触发。编排 strategy-research （SignalEngine 合约 + 回测引擎库 + 内置三模板）+ 自建 driver 拉真实数据 + html-report 回测报告与报告库归档。产出：单文件 HTML 回测看板。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 策略研究回测场景（编排手册）

本技能是**场景编排层**：按 SignalEngine 合约写策略、用回测引擎库跑真实
数据、参数扫描/走前验证进阶，交付回测看板。**产物分区纪律**见顶部「dsh 适配说明」——策略代码落 `scripts/`、数据落 `data/`、报告落
`reports/`，从工作区根执行。

## 触发条件

- 「写个 XX 策略回测」「双均线/RSI/MACD 策略表现」「参数寻优」「走前验证」；
- 纯选股不触发（走选股流水线）；纯因子检验走 factor-research。

## 引擎形态（重要，2.0 与 1.x 的差异）

- `cli.py demo`（dual_ma/rsi/macd）用的是**合成 MOCK 数据**——只用于
  验证参数链路与演示，**禁止作为回测结论**；
- 真实回测 = 自建 driver 脚本调 `analysis/backtest_engine.py` 的
  `run_backtest()`（库形态，含 A 股涨跌停/手续费/滑点规则）；
- `cli.py validate --file` 校验自写策略语法；`cli.py list` 列内置模板；
  模板参考 `<基目录>/scripts/templates/signal_engine_template.py`，
  合约与示例 `<基目录>/references/strategy-examples.md`。

## 阶段一：策略编写（必做）

1. `skill` 加载 strategy-research，记基目录；
2. 写 `scripts/config.json`（标的/日期/资金/费率）与
   `scripts/signal_engine.py`（按 SignalEngine 合约，从模板起步）：

   ```json
   {"source": "tushare", "codes": ["000001.SZ"], "start_date": "2025-01-01",
    "end_date": "2025-12-31", "initial_cash": 1000000, "commission": 0.001}
   ```

3. 语法校验：

   ```bash
   python3 "<strategy-research 基目录>/scripts/cli.py" validate \
     --file scripts/signal_engine.py
   ```

## 阶段二：真实数据回测（必做）

自建 driver `scripts/run_bt.py`（范式）：从 kk_common 网关拉 config 中
标的的日线 → 构造 data_map（{code: DataFrame}，index 日期，列
open/high/low/close/volume）→ import 策略 → 调
`analysis.backtest_engine.run_backtest` → metrics（总收益/年化/夏普/
最大回撤/胜率/交易次数）+ `evaluate_strategy` 评审落 `data/bt.json`。
kk_common 解析：`PYTHONPATH` 加 `<strategy-research 基目录>/../../common/src`
（或按脚本自身位置注入，参考其他引擎写法）。

- 回测分钟级以上窗口属长任务——run_in_background 后台化后收
  `job_output`；
- A 股规则（涨跌停/双向费率）默认开启，`--no-a-share-rules` 仅研究口径。

## 阶段三：进阶（可选，用户要「优化/稳健性」时）

- 参数扫描：`analysis/param_sweep.py`（run_param_sweep）；
- 走前验证：`analysis/walk_forward.py`（run_walk_forward）；
- 均以 driver 方式调用，输出落 `data/`。

## 阶段四：报告交付（必做）

1. html-report 契约构造 `reports/report.json`：评分卡（年化/夏普/回撤/
   胜率）、净值曲线 vs 基准（line）、参数扫描热力（bar）；分节正文 =
   策略逻辑 / 回测口径 / 结果 / 敏感性 / 风险；
2. 渲染 `-o reports/backtest-<策略名>.html`，归档报告库，向用户给出文件绝对路径交付。

## 阶段五：归档策略库（必做，交付后收口）

把本次策略回测沉淀为「策略库」资产——工作台侧栏「策略库」面板可随时
回看净值曲线叠加、跨版本对比、重跑。dsh 下走本插件注册的同名四库 agent 工具（投研工作台对应库面板随时回看），三步（工具调用，失败不阻塞交付）：

1. `strategy_create`（{name, hypothesis}）建策略资产，返回 `strategy_id`；
2. `strategy_save_version`（{strategy_id, code, params, change_note, parent_version}）存代码版本：code=策略信号/回测核心代码全文（≤512KB）；parent_version 传 `strategy_get_latest` 读到的当前版本（乐观锁）；
3. `strategy_record_backtest`（{strategy_id, version, data_start, data_end, rules, metrics, equity?, trades?}）存回测结果：rules 原样抄录 A 股交易规则（可带 `report_id` 建看板链）；metrics 面板渲染键 total_return_pct / annual_return_pct / sharpe_ratio / max_drawdown_pct / win_rate_pct / trade_count；equity=净值序列（≤2MB），trades=交易清单（≤4MB）。

- **多策略研究**（一次对比 N 个策略/参数组）：每策略建独立资产，
  name 带标识区分（如「双均线·20/60」「双均线·5/20」）；禁止因
  "策略多"整体跳过归档只交报告；
- **重跑同一策略**：不要 *_create 新策略——用 *_list 定位既有 id 后迭代；代码或参数变化时*_save_version 落新版本（sha256 变才换版）；
  run 一律挂当前版本；
- metrics 面板渲染键（**漏了对应列显示「—」**）：`total_return_pct` /
  `annual_return_pct` / `sharpe_ratio` / `max_drawdown_pct` /
  `win_rate_pct` / `trade_count`；漏检可事后 UPDATE metrics_json 补；
- equity 兼容 `[{date,equity}]` 与 `{dates,values}`（面板归一后叠加）；
- **trades.json 建议同时含 positions 键**（精确口径）：`{"trades":[...],
  "positions":[{"date":"YYYY-MM-DD","holdings":[{"code","quantity",
  "weight" 可选}]}]}`——面板的调仓记录优先用快照差分；只有 trades
  流水时面板自动推导（买卖累计），标注「流水推导口径」；
- 引擎不可达时在最终回复里明说「未归档策略库」，其余交付照常。

## 输出纪律（强约束）

- metrics 数值**原样转述**；demo(MOCK) 结果不得出现在结论里；
- 回测口径必须注明（窗口/费率/滑点/A 股规则/复权）；
- 过拟合警示：参数扫描最优点必须附走前验证或样本外结果；
- 缺失诚实标注；结论带数据日期；全文为研究参考口径，不构成投资建议。

