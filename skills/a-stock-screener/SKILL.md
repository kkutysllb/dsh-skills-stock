---
name: a-stock-screener
description:  A 股对话式选股助手 (Orchestrator Pattern) —— 用户用自然语言描述"想要什么样的股票"， 本 skill 解析意图 → 选择策略 → 拉取数据 → 套用过滤 → 多因子打分 → 输出选股报告。 内置 10 种经典选股策略（价值/高股息/成长/动量/技术突破/超跌反弹/涨停龙头/机构资金追踪/ 缠论背驰/多因子横截面），工作流五阶段编排，支持无网络 mock 模式离线运行。 适用于 stock-analysis / factor-research / selection-strategies / data-fetch 等 skill 的上层"选股入口"场景。
version: 1.0.1
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# a-stock-screener 使用说明

A 股对话式选股（Orchestrator Pattern）：用户用自然语言描述"想要什么样的股票"，
本 skill 解析意图 → 匹配策略 → 拉取数据 → 多因子打分 → 输出选股结果。

## 运行方式

```bash
cd <本技能包根>/scripts
python3 cli.py --query "高股息低估蓝筹股" --top 10        # 问财+Tushare 真实数据
python3 cli.py --query "创业板成长股" --top 20 --mock     # 无网络冒烟
```

数据源：问财（IWENCAI_API_KEY）优先，Tushare 兜底；`--mock` 走内置伪数据。

## 模糊意图澄清（强制）

当用户请求**笼统**（如「帮我选股」「选几只股票」「推荐一下」），未给出任何可执行
参数（策略/市值/股票池/数量）时，必须先调用 `ask_clarification` 收集意图，
`fields` 使用下方模板**原样传递**（不得增删字段、不得改写选项文案）：

```json
{
  "question": "想按什么条件选股？请选择策略与范围（不填的项使用默认值）：",
  "clarification_type": "ambiguous_requirement",
  "fields": [
    {"name": "strategy", "label": "选股策略（可多选）", "type": "multi_select", "required": true,
     "options": ["多因子横截面", "价值投资", "成长股", "高股息", "动量突破", "技术突破", "超跌反弹", "涨停龙头", "主力资金追踪", "缠论背驰"]},
    {"name": "market_cap", "label": "市值范围", "type": "select", "required": false,
     "options": ["不限制", "大盘(>200亿)", "中盘(50-200亿)", "小盘(20-50亿)", "微盘(<20亿)"]},
    {"name": "pool", "label": "股票池", "type": "select", "required": false,
     "options": ["全部A股", "沪深300", "中证500", "中证1000", "上证50", "创业板"]},
    {"name": "top_n", "label": "返回数量 TopN", "type": "number", "required": false, "placeholder": "默认 10"},
    {"name": "sort_by", "label": "排序偏好", "type": "select", "required": false,
     "options": ["综合评分", "股息率", "市盈率", "市净率", "涨跌幅"]}
  ]
}
```

用户确认后返回形如「选股策略: 高股息、价值投资\n市值范围: 大盘(>200亿)\n…」的文本：

1. **策略多选** → 将每个策略的关键词拼入 `--query`（如 `--query "高股息 价值投资 大盘蓝筹"`），
   或并行调用 selection-strategies 对应脚本，汇总时标注多策略交集；
2. **数量** → `--top <N>`；**市值/股票池** → 拼入 `--query`（问财自然语言可解析），
   或加 selection-strategies 脚本参数（`--market-cap large|mid|small`、
   `--pool hs300|zz500|zz1000`、`--stock-pool gem`）；脚本不支持的选项（微盘/上证50）
   回退最接近值并在报告注明；
3. 用户明确表示「你来定」→ 默认 `--query "多因子精选"`，TopN 10。

## 注意事项

- 表单字段上限 16 个、每字段 24 选项、单字段 200 字符，模板在限内，禁止自行扩增；
- 金额/市值等数值字段保持用户原文，禁止改写口径；
- 输出必须包含：命中清单（代码/名称/评分/关键指标）+ 多策略交集（共振）+ TopN 建议。

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
