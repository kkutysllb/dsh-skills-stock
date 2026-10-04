---
name: options-payoff
description: 期权盈亏分析引擎——Black-Scholes 定价、Greeks 计算、多腿策略盈亏图、盈亏平衡点、隐含波动率反解、波动率情景分析，开箱即用的跨平台技能包。
version: 1.0.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# options-payoff — 期权盈亏分析技能包

## 概述

本技能包提供完整的期权盈亏分析能力，覆盖 Black-Scholes 定价、Greeks 计算、多腿组合盈亏分析、隐含波动率反解等核心功能。纯数学计算，不依赖外部数据源，可在任何平台开箱即用。

## 支持的策略类型

### 单腿策略
| 策略 | 方向 | 权利金 | 最大盈利 | 最大亏损 |
|------|------|--------|----------|----------|
| Long Call | 看多 | 支付 | 无限 | 权利金 |
| Long Put | 看空 | 支付 | 行权价-权利金 | 权利金 |
| Short Call | 中性/略空 | 收入 | 权利金 | 无限 |
| Short Put | 中性/略多 | 收入 | 权利金 | 行权价-权利金 |

### 垂直价差
| 策略 | 结构 | 净权利金 |
|------|------|----------|
| Bull Call Spread | 买低K Call + 卖高K Call | 净支出 |
| Bear Put Spread | 买高K Put + 卖低K Put | 净支出 |
| Bull Put Spread | 卖高K Put + 买低K Put | 净收入 |
| Bear Call Spread | 卖低K Call + 买高K Call | 净收入 |

### 跨式/宽跨式
| 策略 | 结构 | 市场观点 |
|------|------|----------|
| Long Straddle | 买 ATM Call + 买 ATM Put | 大幅波动 |
| Short Straddle | 卖 ATM Call + 卖 ATM Put | 区间震荡 |
| Long Strangle | 买 OTM Call + 买 OTM Put | 大幅波动，低成本 |
| Short Strangle | 卖 OTM Call + 卖 OTM Put | 窄幅震荡 |

### 蝶式/铁蝶式
| 策略 | 结构 | 特点 |
|------|------|------|
| Long Butterfly | 买K1 + 卖2×K2 + 买K3 | 低成本赌到期在K2附近 |
| Iron Butterfly | 卖K2 Call + 卖K2 Put + 买K3 Call + 买K1 Put | 净收入，最大盈利在K2 |

### 鹰式/铁鹰式
| 策略 | 结构 | 特点 |
|------|------|------|
| Iron Condor | 卖K2 Put + 买K1 Put + 卖K3 Call + 买K4 Call | 最常见中性策略，双限风险 |

### 保护/对冲策略
| 策略 | 结构 | 用途 |
|------|------|------|
| Covered Call | 持标+卖Call | 增强收益 |
| Protective Put | 持标+买Put | 下行保护 |
| Collar | 持标+买Put(K1)+卖Call(K2) | 零成本区间锁定 |

## Black-Scholes 定价模型

### 核心假设
- 标的价格遵循几何布朗运动（对数正态分布）
- 无风险利率 `r` 恒定
- 波动率 `σ` 恒定（历史或隐含）
- 无股息，或用连续股息率 `q` 调整
- 仅适用于欧式期权

### 公式
```
S = 标的现价, K = 行权价, T = 到期时间(年)
r = 无风险利率, σ = 年化波动率, q = 连续股息率
N = 标准正态CDF

d1 = [ln(S/K) + (r - q + σ²/2) × T] / (σ × √T)
d2 = d1 - σ × √T

Call = S × e^(-qT) × N(d1) - K × e^(-rT) × N(d2)
Put  = K × e^(-rT) × N(-d2) - S × e^(-qT) × N(-d1)
```

### Put-Call Parity
```
Call - Put = S × e^(-qT) - K × e^(-rT)
```

## Greeks

### Delta（价格敏感度）
```
Delta(Call) = e^(-qT) × N(d1)     [0, 1]
Delta(Put)  = e^(-qT) × (N(d1)-1) [-1, 0]
```
ATM ≈ ±0.5，深度实值 → ±1，深度虚值 → 0

### Gamma（Delta 变化率）
```
Gamma = e^(-qT) × N'(d1) / (S × σ × √T)
```
Call 和 Put 的 Gamma 相同；ATM 附近最大，临近到期爆炸

### Theta（时间衰减，每天）
```
Theta(Call) = [-S×e^(-qT)×N'(d1)×σ/(2√T) - r×K×e^(-rT)×N(d2) + q×S×e^(-qT)×N(d1)] / 365
Theta(Put)  = [-S×e^(-qT)×N'(d1)×σ/(2√T) + r×K×e^(-rT)×N(-d2) - q×S×e^(-qT)×N(-d1)] / 365
```

### Vega（波动率敏感度，每 1% vol 变化）
```
Vega = S × e^(-qT) × N'(d1) × √T / 100
```

### Rho（利率敏感度，每 1% 利率变化）
```
Rho(Call) = K × T × e^(-rT) × N(d2) / 100
Rho(Put)  = -K × T × e^(-rT) × N(-d2) / 100
```

## 隐含波动率反解（Newton-Raphson）

```
迭代: σ_{n+1} = σ_n - [BS(σ_n) - P_market] / Vega(σ_n)
停止: |BS(σ_n) - P_market| < 1e-6
初始: σ_0 = √(2π/T) × P_market/S  (Brenner-Subrahmanyam)
Vega ≈ 0 时切换二分法
IV > 500% 视为异常值过滤
```

## 盈亏图分析

### 到期盈亏曲线
```
对每个腿 i (Call/Put, Long/Short, K_i, 数量 n_i):
  Payoff_i(S_T) = n_i × direction_i × max(0, S_T - K_i)  # Call
  Payoff_i(S_T) = n_i × direction_i × max(0, K_i - S_T)  # Put
组合盈亏 = Σ Payoff_i - 净权利金成本
```

### 盈亏平衡点
- 用 `scipy.optimize.brentq` 数值求解
- 单腿：Long Call BEP = K + 权利金
- 多腿：0~2 个 BEP

### 波动率情景矩阵
生成 `σ × [0.5, 0.75, 1.0, 1.25, 1.5]` 情景，观察 Vega 敏感度

## 策略选择决策树

```
市场观点
├── 强烈看多 → Long Call / Bull Call Spread
├── 温和看多 → Covered Call / Bull Put Spread
├── 温和看空 → Protective Put / Bear Call Spread
├── 强烈看空 → Long Put / Bear Put Spread
├── 区间震荡（低IV）→ Short Strangle / Iron Condor / Iron Butterfly
└── 预期大波动（低IV）→ Long Straddle / Long Strangle / Back Spread
```

### 波动率环境 → 策略映射
| IV 区间 | 适用策略 | 回避策略 |
|---------|----------|----------|
| 低IV (<20%分位) | Long Straddle, Long Strangle | 卖方策略 |
| 正常IV (20-80%) | Vertical Spreads, Calendar | 单腿非对称仓位 |
| 高IV (>80%分位) | Short Straddle, Iron Condor | 买方单腿 |

## 使用方式

### CLI 分析脚本

```bash
# 单腿期权定价 + Greeks
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action price --type call --S 100 --K 100 --T 0.25 --r 0.03 --sigma 0.20

# 隐含波动率反解
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action iv --type call --S 100 --K 100 --T 0.25 --r 0.03 --price 5.0

# 多腿组合盈亏分析
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action payoff \
  --legs "call,long,100,1,3.5,0.25,0.20" "put,long,100,1,2.8,0.25,0.20"

# Iron Condor 盈亏分析
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action payoff \
  --legs "put,short,90,1,1.5,0.083,0.20" "put,long,85,1,0.5,0.083,0.20" \
         "call,short,110,1,1.5,0.083,0.20" "call,long,115,1,0.5,0.083,0.20" \
  --S 100 --r 0.03

# JSON 输出
python3 scripts/analysis-engine/analyze_option_payoff.py --action price --type call --S 100 --K 100 --T 0.25 --r 0.03 --sigma 0.20 --json
```

## 引擎模块

| 模块 | 说明 |
|------|------|
| `scripts/analysis-engine/bs_model.py` | Black-Scholes 定价 + Greeks + 隐含波动率 |
| `scripts/analysis-engine/payoff_engine.py` | 多腿组合盈亏计算引擎 |
| `scripts/analysis-engine/analyze_option_payoff.py` | CLI 入口脚本 |

## 注意事项

- 本技能包仅用于研究和回测，不构成投资建议
- Black-Scholes 模型适用于欧式期权，美式期权需使用二叉树等模型
- 隐含波动率反解可能对深度虚值/实值期权不收敛

