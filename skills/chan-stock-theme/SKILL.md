---
name: chan-stock-theme
description:  缠论个股与选股场景（编排手册）。用户问「缠论分析 / 笔段中枢 / 背驰 / 三类买卖点 / MACD 背驰选股」等缠论类问题时触发。编排 stock-analysis 的 缠论双引擎（analyze_stock_chan 单股全息形态 / run_chan_stock_selector 全池背驰选股）+ chart-visualization 图表 + html-report 看板交付与 报告库归档。产出：单文件 HTML 缠论看板。
version: 2.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物写入**当前工作目录**，并按 scripts/（脚本）/ data/（引擎中间产物）/ reports/（报告 JSON 与 HTML）三目录归位（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 缠论个股与选股场景（编排手册）

本技能是**场景编排层**：以 stock-analysis 技能的缠论双引擎为主轴，完成
单股缠论全息分析或全池背驰选股并交付 HTML 看板。**产物分区纪律**见顶部「dsh 适配说明」——引擎输出一律落 `data/`、报告落 `reports/`，从
工作区根执行；三分区内的**子布局**见下文「工作区子布局（缠论场景）」。

## 触发条件

- 「缠论分析 XX」「XX 的笔/段/中枢」「背驰」「三类买卖点」→ 单股分析；
- 「缠论选股 / 背驰选股 / MACD 背驰的股票」→ 全池选股；
- 普通技术分析问题不触发本场景（走 analyze_technical）。

## 粒度选择

| 用户问法 | 路径 | 命令 |
|---|---|---|
| 点名个股 / 笔段中枢 / 买卖点 | 单股全息 | `analyze_stock_chan.py --stock <代码或名称> --level daily --json` |
| 选股 / 池扫描 | 全池背驰选股 | `run_chan_stock_selector.py --pool hs300 --top N --json` |

`--levels` 可多周期（如 `--levels 30min,daily,weekly`）；选股池：
all/hs300/zz500/zz1000/gz2000/zza500。

## 阶段一：数据采集（必做）

先在工作区根逐级建目录：`mkdir -p scripts "data/chan/<代码>"
"data/chan/select" reports`（选股场景再加 `data/chan/compare`）；基目录 =
stock-analysis 技能加载结果给出的 Base directory。

1. **单股**（实测 242 根日 K → 31 分型/笔/中枢/MACD 背驰全结构）：

   ```bash
   python3 "<stock-analysis 基目录>/scripts/analyze_stock_chan.py" \
     --stock 000001 --level daily --json > "data/chan/<代码>/daily.json"
   ```

   多级别研究逐级别落盘：`--levels 30min,daily,weekly` 拆成多条命令，
   每级别一文件（`30min.json` / `daily.json` / `weekly.json`）。

2. **全池选股**（hs300 = 300 只逐只拉 K 线 × Tushare 限速，实测 10 分钟
   级——**必须 run_in_background 后台化**，期间先搭报告骨架；收齐后
   `job_output` 校验退出码再解析）：

   ```bash
   python3 "<stock-analysis 基目录>/scripts/run_chan_stock_selector.py" \
     --pool hs300 --top 20 --json > "data/chan/select/hs300-$(date +%Y%m%d).json"
   ```

依赖：TUSHARE_TOKEN + pandas/dotenv（壳已注入/引导安装；缺则按「无数据」
口径处理，禁止编造）。

## 工作区子布局（缠论场景）

多标的 × 多级别 × 关联数据全部平铺在 `data/` 根，会把目录堆成上百个
`.json` / `.err` 混杂文件。在三分区（scripts / data / reports，见顶部「dsh 适配说明」）内按下表再分区：

| 路径 | 放什么 |
|------|--------|
| `data/chan/<代码>/<级别>.json` | 单股缠论引擎输出（一级别一文件：`5min`…`monthly`） |
| `data/chan/<代码>/<名称>.json` | 同标的关联数据（moneyflow / chips / daily / margin_detail 等） |
| `data/chan/select/<池名>-<YYYYMMDD>.json` | 全池选股结果（一池一日一文件） |
| `data/chan/compare/<主题>.json` | 对比类中间产物（compare-raw 等，**不放 reports/**） |

- stderr 重定向到同名 `.err`（`> <file> 2> <file>.err`），**解析成功后
  即删**；禁止 `.err` 与最终数据长期混放；
- 一切自建脚本（含 `build_*.py` 报告构造脚本）只落 `scripts/`，**禁止
  堆在工作区根**；
- `reports/` 只放 `report.json` + 渲染 HTML（`chan-<代码或池名>-<主题>-
  <YYYYMMDD>.html`）；对比数据等中间 json 一律归 `data/chan/`。

## 阶段二：解读

- 单股：morphology（K 线/分型/笔计数）→ 中枢区间 → 动力学（MACD 背驰
  信号）→ 买卖点分级，按引擎 JSON 结构逐层转述；
- 选股：信号表按 买/卖 分组，结合 `--signal buy` 收窄；头部标的可对
  top 5 逐只补单股全息分析（并行采集按子布局落 `data/chan/<代码>/`）。

## 阶段三：报告交付（必做）

1. html-report 契约构造 `reports/report.json`：
   - 评分卡：单股（当前级别/中枢区间/买卖点）或选股（买/卖信号计数）；
   - 图表：笔段结构示意（用 chart-visualization 或引擎 --save 输出图）、
     MACD 背驰对照（line/bar）；选股场景为信号强度 TOP20（bar）；
   - 分节正文：形态结构 / 中枢与买卖点 / 背驰信号 / 操作参考位；
   - 风险提示与参考来源（Tushare + 数据日期）；
2. 渲染 `-o "reports/chan-<代码或池名>-<主题>-<YYYYMMDD>.html"`，归档
   报告库，向用户给出文件绝对路径交付。

## 输出纪律（强约束）

- 笔/段/中枢/买卖点等结构数值**原样转述**，禁止改写或省略中枢区间；
- 买卖点必须带级别（30min/daily/weekly）与确认条件，禁止脱离级别谈点位；
- 全池选股注明池与扫描窗口（长任务后台化执行）；
- 缺失诚实标注「无数据」及原因；结论带数据日期；全文为研究参考口径，
  不构成投资建议。

