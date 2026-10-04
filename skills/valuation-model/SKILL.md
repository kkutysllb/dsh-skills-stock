---
name: valuation-model
description: 估值方法论，涵盖 DCF、DDM、SOTP 等绝对估值，以及 PE-Band、PB-ROE、EV-EBITDA 等相对估值，并包含敏感性分析与估值陷阱识别。
version: 1.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# Valuation Methodology

## 执行方式（先读这里）

**禁止自行编写数据分析脚本**：本技能提供现成 CLI，直接调用即可完成 PE-Band 估值：

```bash
cd <本技能包根>/scripts && python3 pe_band_cli.py 600519.SH
# 可选：--years N 指定历史年数（默认 5）
```

输出包含：当前估值快照（收盘价/PE-TTM/静态 PE/PB/总市值）、近 N 年 PE_TTM 月末序列、10/25/50/75/90 分位表（含 min/max/mean）、当前 PE 分位判定结论、估值陷阱提示（Top10 中的关键项）。

脚本内部自动安装 common 依赖（`pip install -e ../common`），无需手动操作；`TUSHARE_TOKEN` 从凭据文件注入运行环境（运行前 source 凭据文件，见「凭据配置」），脚本直接读取。数据缺失时脚本会如实标注「缺失」，**禁止编造数据**；如需补充 DCF/DDM/SOTP 等绝对估值或 PB-ROE 矩阵，基于脚本输出继续分析。

## Overview

Systematic corporate valuation framework covering absolute valuation (`DCF / DDM / SOTP`) and relative valuation (`PE / PB / EV-EBITDA`), including sensitivity-analysis methods and a checklist for identifying valuation traps.

## Absolute Valuation Methods

### 1. DCF (Discounted Cash Flow)

**Core formulas**:

```
Enterprise value = Σ FCF_t / (1+WACC)^t + TV / (1+WACC)^n
Equity value = enterprise value - net debt
Per-share value = equity value / total shares outstanding
```

**Detailed steps**:

#### Step 1: Forecast free cash flow (usually 5 years)

```
FCFF = EBIT × (1-tax rate) + depreciation & amortization - capex - increase in working capital

Simplified version:
FCFF ≈ operating cash flow - capex
```

| Year | Revenue (100m RMB) | EBIT (100m RMB) | FCFF (100m RMB) | Growth |
|------|---------|---------|---------|------|
| 2026E | 120 | 24 | 18 | +15% |
| 2027E | 138 | 28 | 21 | +15% |
| 2028E | 155 | 31 | 24 | +12% |
| 2029E | 170 | 34 | 26 | +10% |
| 2030E | 182 | 36 | 28 | +7% |

#### Step 2: Calculate WACC

```
WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1-T)

Ke (cost of equity) = Rf + β × (Rm - Rf)
  - Rf: 10-year government bond yield (about 2.5% for China A-shares)
  - β: industry average or company beta (1.0-1.5)
  - Rm-Rf: equity risk premium (about 5-7% for China A-shares)

Kd: cost of debt (loan rate, about 4-5%)
T: income tax rate (25%)
```

**Reference WACC ranges for China A-shares**:

| Industry | WACC Range | Reference β |
|------|---------|------|
| Consumer | 8-10% | 0.8-1.0 |
| Technology | 10-13% | 1.2-1.5 |
| Financials | 7-9% | 1.0-1.2 |
| Cyclicals | 9-12% | 1.0-1.4 |
| Utilities | 6-8% | 0.5-0.8 |

#### Step 3: Terminal Value

```
Perpetual-growth method: TV = FCF_n × (1+g) / (WACC - g)
  - g: perpetual growth rate (usually 2-3%, should not exceed GDP growth)

Exit-multiple method: TV = EBITDA_n × EV/EBITDA multiple
  - Reference the industry average or historical median
```

#### Step 4: Sensitivity Analysis

```markdown
### DCF Sensitivity Analysis (per-share value, RMB)

| WACC \ g | 2.0% | 2.5% | 3.0% |
|----------|------|------|------|
| 9.0% | 32.5 | 35.8 | 40.2 |
| 9.5% | 28.3 | 30.8 | 34.0 |
| 10.0% | 24.8 | 26.7 | 29.1 |
| 10.5% | 22.0 | 23.5 | 25.3 |
| 11.0% | 19.6 | 20.8 | 22.2 |
```

### 2. DDM (Dividend Discount Model)

**Applicable to**: high-dividend stocks (banks, utilities, mature consumer companies).

```
Two-stage DDM:
P = Σ D_t / (1+Ke)^t + D_n × (1+g) / [(Ke-g) × (1+Ke)^n]

Gordon model (single stage):
P = D_1 / (Ke - g)
```

**Applicability checklist**:
- [x] Has paid dividends continuously for more than 3 years
- [x] Stable payout ratio (>30%)
- [x] Strong earnings predictability
- [ ] Usually not suitable for high-growth stocks (no dividends / low payout)

### 3. SOTP (Sum of the Parts)

**Applicable to**: diversified conglomerates.

```
Group value = Σ valuation of each business segment + net cash - holding-company discount

Example (a group company):
| Segment | Revenue (100m RMB) | Valuation Method | Valuation (100m RMB) |
|------|---------|---------|---------|
| Baijiu | 80 | 30x PE | 600 |
| Real estate | 50 | 0.6x PB | 120 |
| Financials | 30 | 1.0x PB | 200 |
| Total | | | 920 |
| Holding-company discount | | -15% | -138 |
| Group valuation | | | 782 |
```

## Relative Valuation Methods

### 1. PE Band

```
Historical PE percentile analysis:
- Take the past 5 years of PE_TTM time series
- Compute the 10% / 25% / 50% / 75% / 90% percentiles
- Judge overvaluation / undervaluation from the current PE percentile

| Percentile | PE | Implied Price | Interpretation |
|------|-----|---------|------|
| 90% | 35x | 52.5 | Severely overvalued |
| 75% | 28x | 42.0 | Rich |
| 50% | 22x | 33.0 | Fair |
| 25% | 16x | 24.0 | Cheap |
| 10% | 12x | 18.0 | Severely undervalued |
| Current | 18x | 27.0 | Cheap (30th percentile) |
```

### 2. PB-ROE Matrix

```
Theoretical relationship: PB = (ROE - g) / (Ke - g)
Practical use: plot companies in the industry on a PB vs ROE scatter chart

| Quadrant | PB | ROE | Interpretation |
|------|-----|-----|------|
| Lower right | Low PB | High ROE | Undervalued (best buy zone) |
| Upper right | High PB | High ROE | Fair (quality premium) |
| Lower left | Low PB | Low ROE | Value trap or distressed turnaround |
| Upper left | High PB | Low ROE | Overvalued (avoid) |
```

### 3. EV/EBITDA

```
EV = market cap + net debt (interest-bearing debt - cash)
EBITDA = operating profit + depreciation + amortization

Advantages:
- Removes capital-structure differences (vs PE)
- Removes depreciation-policy differences
- Suitable for asset-heavy industries (telecom / energy / infrastructure)

Reference EV/EBITDA ranges by China A-share industry:
| Industry | Median | Undervalued | Overvalued |
|------|--------|------|------|
| Consumer | 15-20x | <12x | >25x |
| Technology | 12-18x | <10x | >22x |
| Energy | 6-10x | <5x | >12x |
| Utilities | 8-12x | <6x | >15x |
```

## Valuation-Trap Detection

### Top 10 Valuation Traps

| # | Trap | Detection Method | Typical Example |
|---|------|---------|---------|
| 1 | Low-PE cyclical at the peak | PE is lowest when earnings are highest and about to fall | Coal at 5x PE in 2021 was the top |
| 2 | High-PE growth can be justified | `PEG < 1` means the growth rate supports the valuation | 30x PE + 40% growth = PEG 0.75 |
| 3 | Low-PB value destruction | Sustained `ROE < Ke` means shareholder value is being destroyed | Long-term loss-making asset-heavy company |
| 4 | Goodwill bomb | Goodwill / net assets >30% implies impairment risk | Underperforming acquisition after paying a high premium |
| 5 | Accounts-receivable trap | Rising receivables / revenue ratio = poor revenue quality | Government receivables + high customer concentration |
| 6 | Capitalization trap | Capitalizing R&D / interest flatters profit | PE doubles after true expensing |
| 7 | One-off gains | Large gap between recurring net profit and reported net profit | Asset sales / government subsidies boost earnings |
| 8 | Share dilution | Stock options / convertible bonds reduce EPS | PE should be based on diluted EPS |
| 9 | Related-party transactions | Buy cheap from related parties / sell high to them | Profit shifted outside the listed entity |
| 10 | FX swings | High overseas-revenue share means large currency sensitivity | RMB appreciation erodes exporter profits |

## Analysis Framework

### Valuation-Method Selection Decision Tree

```
What type of company is it?
├── Mature and stable (consumer / utilities / banks)
│   ├── High dividend -> DDM
│   └── Low dividend -> DCF + PE Band
├── High growth (tech / pharma / new energy)
│   └── DCF (high-growth phase) + PEG + PS
├── Cyclical (coal / steel / nonferrous)
│   └── PB + EV/EBITDA (avoid PE)
├── Diversified conglomerate
│   └── SOTP
└── Loss-making company
    └── PS (price-to-sales) + EV/Sales
```

### Cross-Validation

```
Use at least 2 valuation methods and take the middle value:
1. DCF -> intrinsic value
2. Comparable PE -> market pricing
3. If the difference >30% -> check whether assumptions are reasonable
```

## Output Format

```markdown
## Valuation Analysis: [Company Name / Code]

### Valuation Summary
| Method | Per-Share Value | Weight | Notes |
|------|---------|------|------|
| DCF | ¥32.5 | 50% | WACC=10%, g=2.5% |
| Comparable PE | ¥28.0 | 30% | Industry average 22x, EPS=1.27 |
| PB-ROE | ¥30.0 | 20% | Fair PB=2.5x |
| **Composite Target Price** | **¥30.8** | | Current price 25.0, upside +23% |

### Sensitivity Analysis
[WACC vs growth-rate matrix]

### Valuation-Trap Check
- [x] Is PE a falsely low cyclical peak? -> No
- [x] Goodwill / net asset ratio -> 12%, safe
- [x] Receivables / revenue trend -> Stable, not deteriorating
- [ ] Gap in recurring net profit -> 15% difference, subsidy dependence worth attention

### Investment Rating: Buy
Target price ¥30.8, current price ¥25.0, upside 23%
```

## Notes

1. **DCF is highly sensitive to assumptions**: a 1% change in WACC can move valuation by 20%+, so sensitivity analysis is mandatory
2. **Comparable companies must truly be comparable**: same industry + same scale + same stage; do not apply leader PE multiples to small companies
3. **China A-share valuation system is unique**: shell value / liquidity premium / policy premium mean US-equity standards cannot be copied directly
4. **Valuation is not a target price**: markets can remain irrational for a long time, and valuation is an anchor, not a trading signal
5. **Special handling for cyclicals**: use normalized earnings (mid-cycle earnings), not current earnings
6. **Not suitable for cryptocurrencies**: traditional valuation frameworks do not apply to BTC / ETH; use on-chain metrics instead (see `onchain-analysis`)

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro 数据接口（行情/财务/宏观主源） | tushare.pro 个人主页 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   TUSHARE_TOKEN=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
