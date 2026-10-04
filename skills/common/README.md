# common

kk_Skills 公共库 — 消除各技能包间的重复代码。

## 模块

| 模块 | 说明 | 提取来源 |
|------|------|----------|
| `kk_common.finance_data_gateway` | 金融数据网关（**分析技能访问 Tushare 的首选入口**） | 对齐参考包 `finance_data_gateway` |
| `kk_common.iwencai_client` | 同花顺问财 OpenAPI 统一客户端 | `market-analysis/cli.py`、`hithink-futures/cli.py` |
| `kk_common.tushare_client` | Tushare Pro API 统一客户端 | `market-analysis/analysis/tushare_client.py`、`futures-analysis/analysis/tushare_client.py` |
| `kk_common.formatters` | 金融分析格式化工具集 | 各项目 `analyze_*.py` 中的格式化辅助函数 |

## 数据访问边界（强制）

所有分析类技能获取 Tushare 数据时，**禁止直接 `import tushare` / `ts.pro_api()`**，唯一允许直接 import 的位置是 `tushare-data` 技能与本库 `tushare_client.py` 内部。其余脚本一律走网关或客户端：

```python
# 首选：金融数据网关
from kk_common import get_finance_data_gateway
gw = get_finance_data_gateway()
df = gw.daily(ts_code="600519.SH")

# 备选：兼容客户端
from kk_common import get_tushare_client
client = get_tushare_client()
df = client.daily(ts_code="600519.SH")
```

## 安装

```bash
# 开发模式安装（项目根目录执行）
pip install -e common/

# 或安装所有技能包的公共依赖
pip install -e common/[dev]
```

## 使用

```python
# 问财客户端
from kk_common import IwencaiClient
client = IwencaiClient(skill_name="hithink-market-query")
result = client.query("贵州茅台最新价格")

# 金融数据网关（分析技能首选）
from kk_common import get_finance_data_gateway
gw = get_finance_data_gateway()
df = gw.daily(ts_code="600519.SH")
df = gw.fina_indicator(ts_code="600519.SH")  # 财务指标
df = gw.fut_holding(symbol="IF2605.CFX")     # 期货持仓

# Tushare 客户端
from kk_common import get_tushare_client
client = get_tushare_client()
df = client.daily(ts_code="600519.SH")

# 格式化工具
from kk_common import pct, bar, signal_cn, md_table
print(pct(3.5))          # "+3.50%"
print(signal_cn("buy"))  # "买入"
print(md_table(["指标", "值"], [["PE", "15.2"]]))
```

## 运行测试

```bash
cd common
python -m pytest tests/ -v
```
