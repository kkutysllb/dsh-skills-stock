# market-linkage-engine

独立的、可复用的 **A 股市场联动分析引擎**，覆盖 8 大资金与情绪维度，输出结构化分析报告 + 一句话市场情绪总结。

## 八大分析维度

| # | 维度 | 数据源 | 核心指标 |
|---|------|--------|----------|
| 1 | 主力资金流向 | Tushare `moneyflow` / `moneyflow_dc` | 个股/板块净流入、主力净额 |
| 2 | 北向资金流向 | Tushare `hsgt` / `hsgt_top10` | 沪深股通净额、连续性、十大活跃股 |
| 3 | 两融趋势 | Tushare `margin` / `margin_detail` | 融资余额、净买入、杠杆水平 |
| 4 | 股指期货基差 | Tushare `fut_daily` / `index_daily` | IF/IC/IH/IM 升贴水、基差率 |
| 5 | 7 大期权 ETF 波动率 | Tushare `opt_daily` | PCR、IV、认购/认沽活跃度 |
| 6 | 9 大宽基 ETF 份额 | Tushare `fund_share` / `fund_daily` | 份额净申赎、与价格背离 |
| 7 | Shibor 利率走势 | Tushare `shibor` / `shibor_lpr` | 各期限利率变化、期限利差 |
| 8 | 龙虎榜分析 | Tushare `top_list` / `top_inst` | 上榜个股、机构净买卖 |

## 安装

```bash
# 1. 先安装公共库
pip install -e ../common

# 2. 安装本引擎
pip install -e .
```

## 使用

### 命令行

```bash
# 日度分析（默认最近交易日）
python -m market_linkage_engine daily

# 指定交易日
python -m market_linkage_engine daily 20240105

# 周度分析（中期趋势）
python -m market_linkage_engine weekly

# 启用同花顺问财实时数据
python -m market_linkage_engine daily --iwencai

# 输出 JSON / 一句话总结
python -m market_linkage_engine daily -f json
python -m market_linkage_engine daily -f summary

# 写入文件
python -m market_linkage_engine daily -o report.md
```

### Python API

```python
from market_linkage_engine import LinkageEngine

engine = LinkageEngine()                    # 默认仅用 Tushare
# engine = LinkageEngine(use_iwencai=True)  # 启用问财实时数据

daily = engine.run_daily()                  # 日度联动分析
weekly = engine.run_weekly()                # 周度联动分析

print(engine.to_summary(daily))             # 一句话总结
print(engine.to_markdown(daily))            # 完整 Markdown 报告
```

## 环境变量

```bash
# .env 文件
TUSHARE_TOKEN=your_tushare_pro_token
IWENCAI_TOKEN=your_iwencai_token    # 可选，启用问财时需要
```

## 架构

```
src/market_linkage_engine/
├── __init__.py              # 包入口，导出 LinkageEngine
├── __main__.py              # CLI 命令行入口
├── engine.py                # 核心编排器（聚合 8 维度）
├── config.py                # 配置常量（标的/阈值/品种映射）
├── utils.py                 # 通用格式化/工具函数
├── data/
│   └── fetcher.py           # 数据获取层（Tushare + 问财）
└── analyzers/
    ├── base.py              # 分析器基类
    ├── main_capital.py      # 1. 主力资金
    ├── northbound.py        # 2. 北向资金
    ├── margin.py            # 3. 两融
    ├── futures_basis.py     # 4. 股指期货基差
    ├── options_vol.py       # 5. 期权 ETF 波动率
    ├── broad_etf_share.py   # 6. 宽基 ETF 份额
    ├── shibor.py            # 7. Shibor 利率
    └── dragon_tiger.py      # 8. 龙虎榜
```

## 综合评分逻辑

每个维度输出 0-100 评分与偏向（bullish/bearish/neutral），引擎聚合为：
- **avg_score**：8 维度均分
- **bull/bear 计数**：偏多/偏空维度数
- **sentiment**：综合情绪（偏多/偏空/中性震荡）
- **action**：操作建议

## 数据时效

- **Tushare Pro**：T+1 结构化历史数据（主要数据源）
- **同花顺问财**：实时/盘中数据补充（可选，需启用 `--iwencai`）

## License

MIT
