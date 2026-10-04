---
name: common
description: kk_Skills 公共库——金融数据网关（FinanceDataGateway）+ iWencai/Tushare 统一客户端 + 金融分析格式化工具集；分析技能必须通过 get_finance_data_gateway() 访问 Tushare，禁止直接 import tushare
version: 1.1.1
license: MIT
author: kk-quant
source: KStock vendor/skills（经 dsh-skills-stock 适配，勿在镜像侧直接修改）
---

> **dsh 适配说明**：本技能适配自 KStock（A 股量化智能体）技能包，注册为 dsh runtime skill。
> - 本技能包根即激活提示（skill_resources）给出的资源基目录：正文中的 `scripts/`、`references/`、`../common` 等相对路径以该目录为基准解析；`<本技能包根>` 占位符（多见于 cd 命令）替换为该绝对路径后再执行。
> - 产物（报告 HTML、图表、JSON、Excel）一律写入**当前工作目录**（QiLin 沙箱的工作区/缓存路径语义已按 dsh 语义替换）。
> - 数据缺失时如实标注「缺失」，**禁止编造数据**。

# common

kk_Skills 公共库。提供金融数据网关、iWencai / Tushare 统一客户端与金融分析格式化工具集，供股票类技能复用。

## 数据访问边界（强制）

本仓库所有分析类技能获取 Tushare 数据时，**必须遵循以下边界，禁止绕过**：

1. **唯一允许直接 `import tushare` 的位置**：
   - `tushare-data` 技能（官方适配包）
   - 本库 `tushare_client.py` 的实现内部
2. **其余所有分析脚本**禁止 `import tushare` / `ts.pro_api()`，必须通过以下方式访问：
   ```python
   # 首选：金融数据网关（方法名与 Tushare 官方接口一致，实现可替换）
   from kk_common import get_finance_data_gateway
   gw = get_finance_data_gateway()
   df = gw.daily(ts_code='600519.SH', start_date='20260101', end_date='20260725')

   # 备选：兼容客户端（含显式参数签名的封装方法）
   from kk_common import get_tushare_client
   client = get_tushare_client()
   df = client.daily(ts_code='600519.SH')
   ```
3. `FinanceDataGateway` 封装了全部 49 个常用 Tushare 接口（股票/财务/股东/指数/资金流/基金/期货/期权/宏观），实现由 `FinanceDataAdapter` 注入，单元测试可注入 mock，后续可无缝切换到 `tushare-data` 官方运行时。
4. 缺少 token / 接口权限时返回空 DataFrame，**禁止编造数据**。

详见 [README.md](./README.md)。

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
