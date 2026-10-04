# factor-research

量化因子研究 — 跨平台技能包

## 简介

整合四大因子研究能力的跨平台技能包，覆盖因子定义→有效性检验→组合构建→选股应用全链路：

- **因子研究框架** — IC/IR 分析、分层回测、因子组合（等权/IC加权/正交化）
- **基本面因子筛选** — PE/PB/ROE 多条件价值/成长筛选
- **量化因子选股** — 六因子模型（价值/动量/质量/低波/规模/成长）+ 因子择时
- **小盘成长股挖掘** — 20-200亿市值高成长公司筛选 + 专精特新

可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

## 快速开始

```bash
# 安装依赖
pip install pandas numpy scipy

# IC/IR 分析 + 分层回测
python3 scripts/cli.py analyze \
  --factor-csv factor.csv \
  --return-csv return.csv \
  --output-dir ./output

# 基本面因子筛选
python3 scripts/cli.py filter \
  --codes 000001.SZ,600036.SH \
  --pe-max 20 --pb-max 3 --roe-min 8

# 帮助
python3 scripts/cli.py help
```

## 目录结构

```
factor-research/
├── SKILL.md              # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── cli.py            # CLI 统一入口
│   ├── analysis/
│   │   ├── factor_engine.py      # IC/IR 分析 + 分层回测 + 因子组合
│   │   └── fundamental_filter.py # 基本面因子筛选引擎
│   ├── package.sh        # 打包脚本
│   └── requirements.txt  # Python 依赖
├── references/           # 知识库（因子方法论/筛选标准/报告模板）
└── adapters/             # 平台适配
```

## 环境要求

- Python 3.8+
- 依赖: `pandas`, `numpy`, `scipy`

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出: `dist/factor-research.skill` + `dist/factor-research-1.0.0.tar.gz`

## 许可证

Apache License 2.0
