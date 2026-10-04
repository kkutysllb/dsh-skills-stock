---
name: option-futures-linkage
description: 期指期权联动分析引擎——以沪深300/上证50/中证500/中证1000四大期指为轴，联动其对应期权（SSE 300ETF/50ETF/500ETF期权 + CFFEX MO中证1000股指期权）的认沽认购（成交量/持仓量PCR）、波动率（ATM IV/加权IV，BS反解）、IV斜率（认沽/认购端回归、Risk Reversal）、认沽认购IV差等期权维度与期指趋势/基差/持仓维度做5维联动信号分析（共振/背离），输出日粒度/周粒度双粒度联动报告与分品种评分。
version: 1.1.0
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# 期指期权联动分析技能

## 用途

对四大期指品种（IF/IH/IC/IM）做 **期权 × 期指联动分析**，从认沽认购、波动率、IV斜率、PCR 等期权维度与期指行情/基差/持仓维度交叉验证，识别共振与背离信号，输出日粒度 / 周粒度双维度报告。

## 品种映射（期指 → 期权标的）

| 期指 | 现货指数 | 期权标的 | 交易所 |
|------|----------|----------|--------|
| IF（沪深300） | 000300.SH | 300ETF 期权（510300.SH） | SSE |
| IH（上证50） | 000016.SH | 50ETF 期权（510050.SH） | SSE |
| IC（中证500） | 000905.SH | 500ETF 期权（510500.SH） | SSE |
| IM（中证1000） | 000852.SH | MO 中证1000 股指期权（000852.SH 指数为标的） | CFFEX |

> 注：CFFEX 股指期权仅 IO/HO/MO 三个品种（无中证500 股指期权），中证1000 无 ETF 期权，故 IC 用 500ETF 期权、IM 用 CFFEX MO，属混合映射方案。

## 数据源（Tushare Pro API）

- `opt_basic(exchange=)`：期权合约基础信息（按交易所拉全量后本地按 opt_code 过滤；**不支持 opt_code 参数**）
- `opt_daily(exchange=, start_date=, end_date=)`：期权日行情（区间全市场；**无 IV 字段**，隐含波动率由 BS 公式 + brentq 反解）
- `fund_daily` / `index_daily`：ETF / 指数价格（**不支持 trade_date 单日参数，必须用区间**）
- `fut_mapping` / `fut_daily`：期指主力合约与行情

## 执行方式

```bash
# 日粒度（默认全部品种，回溯30天）
cd <本技能包根>/scripts/analysis-engine
python3 analyze_option_futures.py
python3 analyze_option_futures.py --symbols IF IM --days 5
python3 analyze_option_futures.py --json

# 周粒度（默认最近1周）
python3 analyze_weekly_option_futures.py
python3 analyze_weekly_option_futures.py --symbols IF IH --weeks 2
python3 analyze_weekly_option_futures.py --json
```

报告章节（日粒度）：一、市场概览 → 二、逐品种联动分析（期权维度 / 期指维度 / 联动信号）→ 三、分品种联动对比 → 四、综合研判 → 五、投资建议 → 六、小s的总结。
周粒度同构，期权指标为周均聚合（周均PCR/周ATM IV/周加权IV），期指为周涨跌幅/周基差/周持仓变化，另附周内每日期权指标明细表。

## 联动信号（5 维，评分 -6 ~ +6）

| 维度 | 期权侧信号 | 期指侧信号 | 共振判据 |
|------|-----------|-----------|----------|
| 认沽认购比×趋势 | 成交量PCR（>1.2偏空 / <0.8偏多） | 均线趋势 | 偏空PCR+空头趋势 → 共振偏空(-2) |
| 波动率×涨跌 | 加权IV（>30高 / <18低） | 当日/周涨跌 | IV高+下跌 → 恐慌加剧(-1) |
| IV斜率×基差 | Risk Reversal（认沽-认购IV） | 基差贴升水 | 认沽贵+贴水 → 双偏空共振(-2) |
| 认沽认购IV差×持仓 | ATM 认沽-认购 IV 差 | OI 变化 | 增仓+认沽IV高 → 空头力量增强(-1) |
| 持仓PCR×基差 | 持仓量PCR | 基差贴升水 | 偏空持仓PCR+贴水 → 共振偏空(-1) |

联动评分 ≤-3 偏空 / ≥3 偏多 / ±1~2 略偏空多 / 0 中性。期权/期指/联动三侧加权得 0-100 综合分。

## 注意事项

- 必须先配置 TUSHARE_TOKEN 环境变量，否则数据网关返回空
- opt_daily 区间一次可拉全市场（SSE 数千行/CFFEX 千余行），本地按 opt_code 过滤合约
- BS 反解仅对 vol>0 且 settle>内在价值的活跃合约进行，深度实值合约 IV 缺失属正常
- 周粒度以 ISO 自然周聚合，跨年周标签形如 2026-W31

## 凭据配置（dsh 适配）

本技能脚本运行需要以下密钥（缺失时脚本会明确报错，不会编造数据）：

| 环境变量 | 用途 | 获取渠道 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro 数据接口（行情/财务/宏观主源） | tushare.pro 个人主页 |

dsh 宿主会把名字含 TOKEN/KEY/SECRET/PASSWORD 的进程环境变量从 bash 子进程中剥离，
因此统一走**凭据文件**约定。插件数据根（下称「数据根」）= 宿主 home 下的
`dsh-skills-stock/`，宿主 home 按 `$QILIN_HOME → $DSH_HOME → ~/.dsh` 解析
（未设环境变量时即 `~/.dsh/dsh-skills-stock`；工作台设置页「数据源」会显示绝对路径）：

1. 把密钥写入 `<数据根>/secrets.env`（权限 0600）：
   ```bash
   TUSHARE_TOKEN=你的密钥
   ```
2. 运行技能脚本时，在同一条 bash 命令里先加载再执行（bash 内 export 的变量可以传给子进程）：
   ```bash
   set -a; source <数据根>/secrets.env; set +a
   cd scripts && python3 <脚本名> <参数>
   ```

Python 依赖（pandas/numpy/scipy/tushare/akshare 等）按脚本报错提示 `pip install` 即可；
`../common` 公共库由脚本自动 `pip install -e` 安装（候选路径已按 dsh 插件布局解析）。
