# industry-analysis

A股行业六维一体深度分析引擎 — 跨平台技能包

## 简介

本技能包提供完整的行业深度分析能力，整合六大核心维度，可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 六大分析维度

| 维度 | 能力 | 数据源 |
|------|------|--------|
| 结构层 | 产业链上中下游拆解+核心公司 | pywencai |
| 数据层 | 估值排名/财务/盈利/板块行情 | 问财 API |
| 框架层 | 五模块产业链解读 | 知识框架 |
| 研究层 | 券商研报+机构评级 | 问财 API |
| 资讯层 | 政策/技术/竞争/投融资动态 | 问财 API |
| 宏观层 | 全球宏观周期定位与行业映射 | 宏观框架 |

## 快速开始

```bash
# 安装
chmod +x install.sh && ./install.sh

# 配置
export IWENCAI_API_KEY="your_key"

# 产业链分析
python3 scripts/analyze_industry.py "新能源汽车"

# 深度分析
python3 scripts/analyze_industry.py "人工智能" --depth detailed --json

# 行业估值排名
python3 scripts/industry-query-cli.py --query "A股行业估值排名"
```

## 目录结构

```
industry-analysis/
├── SKILL.md                          # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── analyze_industry.py           # 产业链分析脚本
│   ├── industry-query-cli.py         # 行业数据查询CLI
│   ├── requirements.txt
│   └── package.sh                    # 打包脚本
├── references/                       # 参考文档（6个，72K+）
│   ├── industry-chain-framework.md   # 产业链解读五模块框架 V3.0
│   ├── analysis-framework.md         # 详细分析方法论
│   ├── output-template.md            # 标准化报告模板
│   ├── data-sources.md               # 可靠数据源参考
│   ├── global-macro.md               # 全球宏观分析框架
│   └── chart-specs.md                # 图表可视化规范
├── models/
│   └── industry_models.py            # Pydantic 数据模型
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+
- 同花顺问财 API 密钥（IWENCAI_API_KEY）

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/industry-analysis.skill` + `dist/industry-analysis-2.0.0.tar.gz`

## 许可证

MIT License
