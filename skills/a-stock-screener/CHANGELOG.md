# Changelog

## [1.0.1] - 2026-08-10

### Fixed
- `workflow_engine.py` ResolveStep 策略匹配失效（历史 bug）：意图层粗粒度语义
  ID（`value` / `high_dividend` / `growth` / `momentum`）与注册中心细粒度策略
  ID（`value_dividend` / `value_low_pe` / `growth_high_roe` …）不同构，此前
  直接拿语义 ID 做 match 永远匹配失败，策略体系形同虚设（报告显示「默认」、
  打分退化为无策略 0 分）。
  修复：先精确 `registry.get(intent.strategy)`；未命中则回退用原始中文 query
  做关键词匹配（策略 tags 为中文）。修复后 "高股息低估蓝筹股" 命中
  `value_dividend + value_low_pe + value_low_pb`，"放量突破强势股" 命中
  `technical_volume + momentum_1m`。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
