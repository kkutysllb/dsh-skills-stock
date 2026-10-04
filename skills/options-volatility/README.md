# options-volatility

期权波动率分析引擎 — 跨平台技能包

## 简介

本技能包提供完整的期权波动率分析能力，覆盖实现波动率计算、IV vs RV 对比、波动率曲面分析、波动率环境判断等核心功能。纯数学计算，不强制依赖外部数据源。

### 核心能力

| 能力 | 说明 |
|------|------|
| 实现波动率 | 多窗口(20d/60d/90d/252d)年化波动率，支持 Close-to-Close/Parkinson/Garman-Klass |
| IV vs RV | 隐含与实现波动率对比，高估/低估信号判断 |
| 波动率曲面 | ATM Vol 期限结构、25d RR、25d BF 摘要 |
| 环境判断 | IV Rank/Percentile 计算，低/正常/高/危机四级分类 |
| 策略推荐 | 基于波动率环境的策略选择决策树 |

## 快速开始

```bash
# 安装
chmod +x install.sh && ./install.sh

# 实现波动率（命令行价格序列）
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action realized-vol --prices 100,101,102,100,99,98,100,102,105,103

# IV vs RV 对比
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action iv-rv --iv 0.25 --rv-20d 0.18 --rv-60d 0.20 --rv-90d 0.22

# 波动率曲面
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action surface --atm-1m 0.22 --atm-3m 0.24 --atm-6m 0.25 --atm-1y 0.26

# 波动率环境
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action regime --iv-current 0.25 --iv-52w-low 0.15 --iv-52w-high 0.40

# JSON 输出
python3 scripts/analysis-engine/analyze_option_volatility.py \
  --action iv-rv --iv 0.25 --rv-20d 0.18 --json
```

## 目录结构

```
options-volatility/
├── SKILL.md                              # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── analysis-engine/
│   │   └── analyze_option_volatility.py  # CLI 入口脚本
│   ├── analysis/
│   │   ├── realized_vol.py               # 实现波动率计算引擎
│   │   └── vol_engine.py                 # 波动率分析综合引擎
│   ├── requirements.txt
│   └── package.sh                        # 打包脚本
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+
- numpy, scipy, pandas（自动安装）

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/options-volatility.skill` + `dist/options-volatility-1.0.0.tar.gz`

## 许可证

MIT License
