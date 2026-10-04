# hithink-futures

问财期货期权数据查询 — 跨平台技能包

## 简介

本技能包通过同花顺问财 OpenAPI 提供期货期权数据查询能力，支持自然语言输入。纯标准库实现，无第三方 Python 依赖，可在 OpenClaw、Claude Code、Qoder 等 Agent 架构中开箱即用。

### 查询类型

| 类型 | 示例 |
|------|------|
| 期货行情 | 沪铜期货最新行情、铁矿石涨跌幅 |
| 期权波动率 | 50ETF期权隐含波动率 |
| 产销数据 | 原油期货库存数据 |
| 会员持仓 | 螺纹钢期货会员持仓排名 |
| 行权数据 | 50ETF期权行权数据 |

## 快速开始

```bash
# 配置 API Key
export IWENCAI_API_KEY="your-api-key"

# 查询期货行情
python3 scripts/cli.py --query "沪铜期货最新行情"

# 查询期权波动率
python3 scripts/cli.py --query "50ETF期权隐含波动率"

# 翻页
python3 scripts/cli.py --query "期货行情" --page 2 --limit 20
```

## 目录结构

```
hithink-futures/
├── SKILL.md              # 跨平台技能定义
├── README.md
├── LICENSE
├── install.sh
├── scripts/
│   ├── cli.py            # CLI 入口（纯标准库，无第三方依赖）
│   ├── package.sh        # 打包脚本
│   └── requirements.txt  # 空（无第三方依赖）
└── adapters/
    ├── openclaw.md
    ├── claude.md
    └── generic.md
```

## 环境要求

- Python 3.8+（无第三方依赖）
- IWENCAI_API_KEY 环境变量

### API Key 获取

1. 打开 https://www.iwencai.com/skillhub
2. 登录
3. 点击 Skill → 安装方式 → Agent用户 → 复制 IWENCAI_API_KEY
4. 配置环境变量：`export IWENCAI_API_KEY="your-key"`

## 打包

```bash
chmod +x scripts/package.sh && scripts/package.sh
```

输出：`dist/hithink-futures.skill` + `dist/hithink-futures-1.0.0.tar.gz`

## 许可证

MIT License
