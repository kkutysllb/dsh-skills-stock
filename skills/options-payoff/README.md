# options-payoff

期权盈亏分析引擎 — 跨平台技能包

## 简介

本技能包提供完整的期权盈亏分析能力，基于 Black-Scholes 模型，覆盖定价、Greeks、隐含波动率、多腿组合盈亏分析等核心功能。纯数学计算，不依赖外部数据源，可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 核心能力

| 能力 | 说明 |
|------|------|
| BS 定价 | 欧式 Call/Put 定价，支持连续股息率 |
| Greeks 计算 | Delta/Gamma/Theta/Vega/Rho 五大希腊值 |
| 隐含波动率 | Newton-Raphson + 二分法，精度 1e-6 |
| 盈亏分析 | 多腿组合到期盈亏曲线、理论价值曲线 |
| 盈亏平衡点 | 数值求解 0~2 个 BEP |
| 策略推荐 | 基于市场观点和波动率环境的决策树 |

## 快速开始

```bash
# 安装依赖
chmod +x install.sh && ./install.sh

# 单腿期权定价 + Greeks
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action price --type call --S 100 --K 100 --T 0.25 --r 0.03 --sigma 0.20

# 隐含波动率反解
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action iv --type call --S 100 --K 100 --T 0.25 --r 0.03 --price 5.0

# 多腿组合盈亏分析（Long Straddle）
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action payoff \
  --legs "call,long,100,1,3.5,0.25,0.20" "put,long,100,1,2.8,0.25,0.20" \
  --S 100 --r 0.03

# Iron Condor 盈亏分析
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action payoff \
  --legs "put,short,90,1,1.5,0.083,0.20" "put,long,85,1,0.5,0.083,0.20" \
         "call,short,110,1,1.5,0.083,0.20" "call,long,115,1,0.5,0.083,0.20" \
  --S 100 --r 0.03

# JSON 格式输出
python3 scripts/analysis-engine/analyze_option_payoff.py \
  --action price --type call --S 100 --K 100 --T 0.25 --r 0.03 --sigma 0.20 --json
```

## 目录结构

```
options-payoff/
├── SKILL.md                              # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── analysis-engine/
│   │   └── analyze_option_payoff.py      # CLI 入口脚本
│   ├── analysis/
│   │   ├── bs_model.py                   # Black-Scholes 定价 + Greeks + IV
│   │   └── payoff_engine.py             # 多腿组合盈亏引擎
│   ├── requirements.txt
│   └── package.sh                        # 打包脚本
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+
- numpy, scipy（自动安装）

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/options-payoff.skill` + `dist/options-payoff-1.0.0.tar.gz`

## 许可证

MIT License
