---
name: options-volatility
description: 期权波动率分析引擎——隐含波动率/实现波动率计算、波动率曲面分析、IV-RV对比、波动率交易策略评估，开箱即用的跨平台技能包。
version: 1.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# options-volatility — 期权波动率分析技能包

## 概述

本技能包提供完整的期权波动率分析能力，覆盖实现波动率计算、隐含波动率与实现波动率对比、波动率曲面分析、波动率环境判断等核心功能。纯数学计算（历史数据可通过参数或CSV输入），不强制依赖外部数据源。

## 核心分析流程

### 步骤 1: 实现波动率计算

从历史价格序列计算多窗口年化波动率：

```python
# Close-to-Close Realized Volatility
RV = sqrt(252) × std(ln(P_t / P_{t-1}), window)

# Parkinson Volatility (使用日内高低价)
PV = sqrt(252 / (4 × ln(2)) × mean(ln(H_t/L_t))²)

# Garman-Klass Volatility
GK = sqrt(252 × mean(0.5×ln(H/L)² - (2×ln(2)-1)×ln(C/O)²))
```

支持窗口：20d（1个月）、60d（3个月）、90d（6个月近似）、252d（1年）

### 步骤 2: IV vs RV 对比

| 指标 | 说明 |
|------|------|
| IV-RV Spread | 隐含波动率 - 实现波动率 |
| Vol Premium | (IV - RV) / RV × 100% |
| Signal | Rich (IV>RV+阈值) / Cheap (IV<RV-阈值) / Fair |

### 步骤 3: 波动率曲面摘要

| Tenor | ATM Vol | 25d RR | 25d BF |
|-------|---------|--------|--------|
| 1M | ... | ... | ... |
| 3M | ... | ... | ... |
| 6M | ... | ... | ... |
| 1Y | ... | ... | ... |

- **ATM Vol**: 平值期权隐含波动率
- **25d RR (Risk Reversal)**: 25d Call Vol - 25d Put Vol，衡量偏斜方向
- **25d BF (Butterfly)**: (25d Call Vol + 25d Put Vol)/2 - ATM Vol，衡量微笑曲率

### 步骤 4: 波动率环境判断

```
IV Rank = (current_IV - IV_52w_low) / (IV_52w_high - IV_52w_low) × 100
IV Percentile = 过去252天中 IV 低于当前值的天数占比
```

| 区间 | 分类 | 策略建议 |
|------|------|----------|
| IV Rank < 20 | 低波动率 | 买方策略（Long Straddle/Strangle） |
| IV Rank 20-80 | 正常波动率 | 价差策略（Vertical/Calendar） |
| IV Rank > 80 | 高波动率 | 卖方策略（Short Straddle/Iron Condor） |

## 使用方式

### CLI 分析脚本

```bash
# 从CSV文件计算实现波动率
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action realized-vol --csv prices.csv --date-col date --price-col close

# 从命令行传入价格序列
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action realized-vol --prices 100,101,102,100,99,98,100,102,105,103

# IV vs RV 对比
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action iv-rv --iv 0.25 --rv-20d 0.18 --rv-60d 0.20 --rv-90d 0.22

# 波动率曲面分析（传入各期限数据）
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action surface \
  --atm-1m 0.22 --atm-3m 0.24 --atm-6m 0.25 --atm-1y 0.26 \
  --rr-1m -0.03 --rr-3m -0.02 --rr-6m -0.01 --rr-1y 0.00 \
  --bf-1m 0.02 --bf-3m 0.025 --bf-6m 0.03 --bf-1y 0.035

# 波动率环境判断
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action regime --iv-current 0.25 --iv-52w-low 0.15 --iv-52w-high 0.40 \
  --iv-history 0.20,0.22,0.18,0.25,0.30,0.28,0.25

# 完整分析
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action full --csv prices.csv --iv 0.25 --iv-52w-low 0.15 --iv-52w-high 0.40

# JSON 输出
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action iv-rv --iv 0.25 --rv-20d 0.18 --json
```

## 引擎模块

| 模块 | 说明 |
|------|------|
| `scripts/analysis-engine/realized_vol.py` | 多方法实现波动率计算引擎 |
| `scripts/analysis-engine/vol_engine.py` | 波动率分析综合引擎 |
| `scripts/analysis-engine/analyze_option_volatility.py` | CLI 入口脚本 |

## 注意事项

- 本技能包仅用于研究和分析，不构成投资建议
- 实现波动率基于历史数据计算，不代表未来走势
- 波动率曲面数据可通过外部MCP工具获取后传入分析

