# futures-analysis

A股股指期货四维一体深度分析引擎 — 跨平台技能包

## 简介

本技能包提供完整的股指期货分析能力，覆盖 IF/IC/IH/IM 四大品种，整合四大核心维度，可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 四大分析维度

| 维度 | 能力 | 数据源 |
|------|------|--------|
| 行情趋势 | K线趋势/均线/振幅/OI变化 | Tushare API |
| 贴升水分析 | 基差/基差率/期限结构/情绪信号 | Tushare API |
| 机构持仓 | 前20席位/中信风向标/19家对比 | Tushare API |
| 综合研判 | 100分评分/品种分化/策略建议 | 综合计算 |

## 快速开始

```bash
# 安装
chmod +x install.sh && ./install.sh

# 配置
export TUSHARE_TOKEN="your_token"

# 日度全量分析（JSON输出）
python3 scripts/analysis-engine/analyze_futures.py --json

# 仅分析IF/IC持仓
python3 scripts/analysis-engine/analyze_futures.py --symbols IF IC --type holding --json

# 周度分析
python3 scripts/analysis-engine/analyze_weekly_futures.py --json
```

## 目录结构

```
futures-analysis/
├── SKILL.md                          # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── analysis-engine/
│   │   ├── analyze_futures.py        # 日度期货分析脚本
│   │   └── analyze_weekly_futures.py # 周度期货分析脚本
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── futures_analyzer.py       # 日度期货分析引擎
│   │   ├── weekly_futures_analyzer.py # 周度期货分析引擎
│   │   └── tushare_client.py         # Tushare数据客户端
│   ├── requirements.txt
│   └── package.sh                    # 打包脚本
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+
- Tushare Pro API 密钥（TUSHARE_TOKEN）

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/futures-analysis.skill` + `dist/futures-analysis-1.0.0.tar.gz`

## 许可证

MIT License
