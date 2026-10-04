# strategy-research

量化策略研究公共技能包 — 策略设计/编码/回测/评估全链路。

## 特性

- **SignalEngine 合约**：标准化的策略信号接口，值范围 [-1.0, 1.0]
- **3种经典策略模板**：双均线/RSI/MACD，开箱即用
- **回测引擎**：计算总收益/年化/夏普/最大回撤/胜率/交易次数
- **评审标准**：硬性门控 + 评分规则 + 行动建议
- **多市场支持**：A股(tushare) / 美股(yfinance) / 港股(yfinance) / 加密货币(okx)
- **配置驱动**：config.json 标准格式，自动检测市场

## 快速开始

```bash
# 安装依赖
pip install pandas numpy

# 策略演示回测
python3 scripts/cli.py demo --strategy dual_ma
python3 scripts/cli.py demo --strategy rsi
python3 scripts/cli.py demo --strategy macd

# 列出策略
python3 scripts/cli.py list

# 验证策略文件
python3 scripts/cli.py validate --file my_strategy.py
```

## 自定义策略

1. 复制 `scripts/templates/signal_engine_template.py` 为 `signal_engine.py`
2. 实现 `generate()` 方法
3. 运行回测评估

## 目录结构

```
strategy-research/
├── SKILL.md                              # 技能定义
├── scripts/
│   ├── cli.py                            # 统一 CLI 入口
│   ├── analysis/
│   │   ├── backtest_engine.py            # 回测引擎
│   │   └── strategy_templates.py         # 策略模板（dual_ma/rsi/macd）
│   └── templates/
│       └── signal_engine_template.py     # SignalEngine 基类模板
├── references/
│   └── strategy-examples.md              # 策略调用示例
└── adapters/                             # 平台适配器
```

## License

Apache-2.0
