# Changelog

## [1.0.1] - 2026-08-11

### Fixed
- 多因子选股"有效股票不足3只"根因：`fetch_daily` 调 `pro.trade_cal(..., limit=40)`
  时网关封装 `TushareClient.trade_cal` 缺 `limit` 参数 → TypeError 被吞 → 返回空
  交易日历 → 历史行情 hist_df 恒空 → 动量/反转/波动率/量比四因子全 NaN 被滤除。
  修复：common `trade_cal` 补 `limit` 参数（透传官方接口）。
- `fetch_daily` 历史行情改按交易日批量拉取（每日 1 次覆盖全池，约 lookback 次调用），
  替代原逐股 5538 次调用（慢 ~180 倍且易限流）；交易日历异常时自然日推算兜底。
- `get_trade_date` T+1 延迟：`limit=2` 取上一交易日（当日行情次日才入库，
  否则报"截面日 20260811 无行情数据"）。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
