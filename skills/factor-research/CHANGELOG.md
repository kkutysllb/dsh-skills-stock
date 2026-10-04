# Changelog

## [1.1.0] - 2026-08-10

### Added
- `scripts/analysis/multifactor.py`：六因子选股引擎（价值/动量/质量/低波动/规模/成长），
  子指标加权 → 百分位得分(0-100)，支持截面缩尾、行业中性化、自定义因子权重、TopN。
- `scripts/analysis/factor_timing.py`：因子择时引擎，经济周期（复苏初期/扩张中期/扩张末期/
  下行衰退/触底回升）→ 因子权重映射 + 利好/不利因子（对齐 references/factor-methodology.md），
  宏观三要素自动周期判定，拥挤度/IC 衰减检测。
- `scripts/analysis/small_cap_growth.py`：小盘成长挖掘引擎，20-200 亿市值 + 营收 CAGR>20%
  硬门槛，成长质量评分(0-100) + 星级评级（对齐 references/small-cap-screening-criteria.md）。
- `scripts/analysis/builder.py`：因子面板构造器，行情 → 动量/波动率/下行偏差/换手率/规模/β
  子指标 + 前瞻收益矩阵（收益=close[t+N]/close[t]-1，防前视偏差）。
- `scripts/cli.py` 新增 build / multifactor / timing / smallcap / combine 五个子命令。
- `scripts/tests/test_factor_research.py`：28 项 pytest 测试（六因子/择时/小盘/构造/CLI 全子命令），全部通过。

### Fixed
- `factor_engine.factor_combination` 的 `ic_weight` 分支此前为假实现（静默等于等权），
  现支持显式 `weights` 参数（list 或 dict），缺失时回退等权并注明。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
