---
name: market-linkage-engine
description:  A 股市场联动分析引擎。独立、可复用的多维度资金与情绪联动分析工具，覆盖 8 大维度： 主力资金流向、北向资金流向、两融趋势、股指期货基差、7 大期权 ETF 波动率、 9 大宽基 ETF 份额变化、Shibor 利率走势、龙虎榜分析。 数据源：Tushare Pro API + 同花顺问财 OpenAPI。 输出：日度/周度联动报告 + 综合情绪评分 + 一句话市场总结。
version: 1.0.2
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# market-linkage-engine 使用说明

A 股市场联动分析引擎，独立覆盖 8 大资金与情绪维度，输出结构化联动报告 + 综合情绪评分 + 一句话市场总结。

## 运行方式（日粒度 / 周粒度）

```bash
# 日度联动分析（默认最近交易日，短窗口：北向5日/两融20日/期权5日）
python3 -m market_linkage_engine daily

# 周度联动分析（长窗口看中期趋势：北向20日/两融30日/期权10日/Shibor60日）
python3 -m market_linkage_engine weekly

# 指定交易日 / 指定输出格式 / 写入文件
python3 -m market_linkage_engine daily 20260731
python3 -m market_linkage_engine weekly -f summary      # 一句话总结
python3 -m market_linkage_engine daily -f json -o report.json
```

> **输出规范（必须遵守）**：写入 JSON 文件必须用 `-o/--output` 参数（如
> `python3 -m market_linkage_engine weekly 20260731 -f json -o ./linkage.json`）。
> **禁止**用 shell 重定向 `> file` 或 `2>&1` 生成文件：引擎日志输出到 stderr，
> 重定向会把日志混入 JSON（`json.load` 报 `Extra data`，历史已因此多次失败）。
> 重定向输出到 `--output` 的 Markdown 报告也建议同样避免。

Python API：`LinkageEngine().run_daily()` / `run_weekly()`，`to_markdown()` / `to_summary()`。

## 八大维度

| # | 维度 | 核心指标 |
|---|------|----------|
| 1 | 主力资金流向 | 全市场净额、流入/流出榜、板块 TOP |
| 2 | 北向资金流向 | 沪深股通净额、N 日累计、连续性、十大活跃股 |
| 3 | 两融趋势 | 融资余额、净买入、30 日趋势、融资 TOP20 |
| 4 | 股指期货基差 | IF/IC/IH/IM 主力合约基差率、升贴水信号（基差=期货-现货，升水为正） |
| 5 | 7 大期权 ETF 波动率 | 认购/认沽成交与持仓 PCR、ATM IV（BS 反解）、指数涨跌 |
| 6 | 9 大宽基 ETF 份额 | 份额净申赎、与价格背离/同步信号 |
| 7 | Shibor 利率走势 | 各期限利率、期限利差、流动性判断 |
| 8 | 龙虎榜分析 | 上榜个股、机构净买卖 TOP |

## 输出与评分口径

- 每维度输出 0-100 评分与偏向（bullish / bearish / neutral），聚合为综合评分、偏多/偏空计数与操作建议；
- 数据源：Tushare Pro（T+1），可选同花顺问财实时补充（`--iwencai`）；
- **金额单位**：Tushare hsgt / moneyflow 系列金额均为**万元**（报告已换算为亿元，÷10000）；北向 detail 的 `latest_sh / latest_sz` 在 `analyze()` 中已换算为**亿元**，`to_markdown` 渲染时直接格式化、禁止再次 ÷10000（1.0.2 已修复历史双重换算 bug）；
- **缺失必须诚实标注**：某维度数据源无权限或无数据时，报告显示「无数据」及原因，禁止以「中性」掩盖缺失；
- **期权覆盖**：7 大品种中 6 只为 ETF 期权（SSE/SZSE，标的为 ETF 价格），中证1000 用中金所股指期权（CFFEX，IM，opt_code=OP000852，标的为 000852 指数点位）；BS 反解 ATM IV 时标的价格与行权价必须同量级（ETF 用元、股指期权用点位）。
- **日/周粒度差异**：daily 报告周期 1-5 日，weekly 拉长窗口至 20-60 日看中期趋势；期指基差每日重算主力合约。

## 在 KStock 场景中的使用

市场环境维度（产品场景手册场景第 4 条）：子代理先阅读本文件前 80 行，再执行 `cd <本技能包根> && python3 -m market_linkage_engine daily`（周度：`weekly`），将 8 维表格与联动评分原样转述（不得改写数值、不得丢弃表格）。
---

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro 数据接口（行情/财务/宏观主源） | tushare.pro 个人主页 |
| `IWENCAI_API_KEY` | 同花顺问财 OpenAPI（自然语言数据查询） | 问财开放平台控制台 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   TUSHARE_TOKEN=你的密钥
   IWENCAI_API_KEY=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
