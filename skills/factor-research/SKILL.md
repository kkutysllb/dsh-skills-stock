---
name: factor-research
description: 量化因子研究公共技能包——整合因子方法论、IC/IR分析引擎、分层回测、基本面筛选、多因子选股和小盘成长股挖掘，覆盖因子定义→有效性检验→组合构建→选股应用全链路，开箱即用的跨平台技能包。
version: 1.1.0
license: Apache-2.0
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# factor-research — 量化因子研究技能包

## 概述

本技能包整合四大因子研究能力，覆盖因子定义→有效性检验→组合构建→选股应用全链路：

| 能力模块 | 来源 | 功能 |
|---------|------|------|
| **因子研究框架** | factor-research | IC/IR 分析、分层回测、因子组合 |
| **基本面因子筛选** | fundamental-filter | PE/PB/ROE 多条件价值/成长筛选 |
| **量化因子选股** | 量化因子选股 | 六因子模型 + 因子择时 + 拥挤度 |
| **小盘成长股挖掘** | 小盘成长股挖掘 | 小市值高成长公司筛选 + 专精特新 |

## 使用方式

### CLI — 因子有效性分析

```bash
# IC/IR 分析 + 分层回测
python3 scripts/cli.py analyze \
  --factor-csv factor.csv \
  --return-csv return.csv \
  --output-dir ./output \
  --n-groups 5
```

输入 CSV 格式：`index=日期`, `columns=股票代码`

### CLI — 基本面因子筛选

```bash
# 输出筛选参数
python3 scripts/cli.py filter \
  --codes 000001.SZ,600036.SH,000858.SZ \
  --pe-max 20 --pb-max 3 --roe-min 8
```

### CLI — 因子面板构造（1.1.0，防前视偏差）

```bash
# 行情面板 → 动量/波动率/下行偏差/换手率/规模/β 子指标 + 前瞻收益矩阵
python3 scripts/cli.py build \
  --close close.csv --benchmark hs300.csv --period 20 --outdir ./panels
```

收益矩阵约定：`收益 = close[t+N]/close[t] - 1`（因子 t 日对齐 t+N 持有收益），
禁止用 t 日收益（前视偏差）。

### CLI — 六因子选股（1.1.0）

```bash
# 子指标面板目录（文件名=子指标名）→ 六因子得分 + 综合得分 TopN
python3 scripts/cli.py multifactor \
  --panels-dir ./panels --top-n 20 [--weights-json '{"value":0.2,...}']
```

### CLI — 因子择时（1.1.0）

```bash
# 指定经济周期，或由宏观三要素自动判定
python3 scripts/cli.py timing --cycle recovery_early
python3 scripts/cli.py timing --gdp-trend 0.8 --inflation 0.2 --interest-trend -0.1
```

cycle: `recovery_early / expansion_mid / expansion_late / downturn / trough_rebound`

### CLI — 小盘成长挖掘（1.1.0）

```bash
# 特征 CSV（index=code，列 total_mv_yi / revenue_cagr3_pct 等）→ 硬门槛 + 质量评分 + 星级
python3 scripts/cli.py smallcap --input features.csv --top-n 20
```

### CLI — 多因子组合（1.1.0 支持显式 IC 权重）

```bash
python3 scripts/cli.py combine \
  --factor-csv f1.csv f2.csv f3.csv \
  --method equal_weight|ic_weight|orthogonal \
  [--weights-json '[0.2,0.5,0.3]'] [--output composite.csv]
```

### Python — 因子引擎直接调用

```python
import sys
sys.path.insert(0, 'scripts/analysis')
from factor_engine import compute_ic_series, ic_summary, quantile_backtest

ic_df = compute_ic_series(factor_df, return_df)
summary = ic_summary(ic_df)
bt = quantile_backtest(factor_df, return_df, n_groups=5)
```

### Python — 多因子组合（ic_weight 需显式 weights）

```python
from factor_engine import factor_combination

# 等权组合
composite = factor_combination([value_f, momentum_f, quality_f], method='equal_weight')

# IC 加权（1.1.0：必须传 weights，不再静默退化为等权）
composite = factor_combination([value_f, momentum_f], method='ic_weight', weights=[0.7, 0.3])

# 正交化
composite = factor_combination([value_f, momentum_f], method='orthogonal')
```

### 测试（1.1.0）

```bash
cd scripts && python3 -m pytest tests/ -v   # 28 项：六因子/择时/小盘/构造/CLI 全子命令
```

## IC/IR 判断标准

| 指标 | 阈值 | 含义 |
|------|------|------|
| IC 均值 | > 0.03 | 因子具有基本预测力 |
| IC 均值 | > 0.05 | 因子具有较强预测力 |
| IC 均值 | > 0.10 | 异常高，检查前视偏差 |
| IR | > 0.5 | 因子稳定有效 |
| IR | > 1.0 | 极强（非常罕见） |
| IC>0 占比 | > 55% | 方向稳定 |

## 六因子模型

| 因子 | 主要指标 | 学术基础 |
|------|---------|---------|
| 价值 | 盈利收益率、PB倒数、FCF收益率 | Fama-French HML |
| 动量 | 12-1月价格动量、盈利修正 | Carhart 四因子 |
| 质量 | ROE、盈利稳定性、低杠杆 | QMJ |
| 低波动 | 已实现波动率、Beta、下行偏差 | 低波动异象 |
| 规模 | 总市值 | Fama-French SMB |
| 成长 | 营收增速、利润增速、利润率扩张 | 成长溢价 |

## 因子择时框架

| 经济周期 | 利好因子 | 不利因子 |
|---------|---------|---------|
| 复苏初期 | 规模、动量、成长 | 低波动 |
| 扩张中期 | 动量、质量 | 价值 |
| 扩张末期 | 质量、价值 | 规模、成长 |
| 下行/衰退 | 低波动、质量 | 动量、规模 |
| 触底回升 | 价值、规模 | 低波动 |

## 知识库文件

| 文件 | 内容 |
|------|------|
| `references/factor-methodology.md` | 六因子详细定义、评分方法、择时框架、A股特殊性 |
| `references/small-cap-screening-criteria.md` | 小盘成长股筛选标准、质量评分模型、风险框架 |
| `references/multifactor-output-template.md` | 多因子选股报告模板 |
| `references/smallcap-output-template.md` | 小盘成长股报告模板 |

## Python 依赖

```bash
# 依赖已预装，无需执行 pip install
```

## 注意事项

- **前视偏差**: 因子值用 T 日数据，收益必须用 T+1 到 T+N 数据
- **行业中性**: 建议在申万一级行业内做 Z-score 标准化
- **去极值**: 在 2.5/97.5 百分位缩尾处理
- **幸存者偏差**: 回测应包含已退市股票
- **因子拥挤**: 定期检查因子 IC 时序衰减
- **分析结果仅供参考，不构成投资建议**

