# Changelog

## [1.1.1] - 2026-08-11

### Fixed
- `TushareClient.trade_cal` 封装缺 `limit` 参数：`pro.trade_cal(..., limit=N)` 抛
  TypeError 被吞返回空 DataFrame，导致 selection-strategies 等技能拿不到交易日历。
  补 `limit: Optional[int] = None` 透传官方接口。


## [1.2.0] - 2026-08-02

### Fixed
- `TushareClient.stock_basic` 补 `ts_code`/`name` 参数：此前引擎按单只股票查询时
  TypeError 被网关静默吞掉返回空表，导致 10+ 个股分析引擎拿不到基本信息。
- `FinanceDataGateway` 补齐 4 个缺失接口封装：`stock_company` / `report_rc` /
  `stk_surv` / `cyq_chips`（引擎已调用但网关未封装会 AttributeError）。
- `TushareClient.pro_bar` 兼容小写频率（daily/weekly/monthly → D/W/M）：tushare 库
  pro_bar 仅识别大写，传小写时内部频率分支全不命中、`data` 未赋值而抛
  UnboundLocalError，最终回退到非复权 daily 接口。
- `TushareClient.pro_bar` 用 `contextlib.redirect_stdout` 隔离 tushare 库内部裸
  `print(e)` 到 stdout 的缺陷（异常分支不 return 且循环重试），避免污染
  `--json` 等结构化输出；重定向内容记入 debug 日志。

## [1.1.0] - 2026-07-25

### Added
- 新增 `finance_data_gateway` 模块：`FinanceDataGateway` / `TushareDataAdapter` /
  `get_finance_data_gateway()` / `reset_finance_data_gateway()`，显式封装全部 49 个
  常用 Tushare 接口（股票/财务/股东/指数/资金流/基金/期货/期权/宏观）。
- `__init__` 导出 gateway 四个符号。
- SKILL.md 声明数据访问边界：分析技能禁止直接 `import tushare`，必须通过本网关访问。

### Changed
- 描述、版本号、capabilities、tags 同步反映 finance-data-gateway 能力。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
