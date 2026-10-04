# Changelog

## [1.0.2] - 2026-08-10

### Fixed
- `analyzers/northbound.py` 北向报告沪股通/深股通拆分字段显示 `0.0亿`：
  根因是 `to_markdown` 对 `detail.latest_sh / latest_sz`（在 `analyze()`
  中已由万元÷10000 换算为亿元）再次 ÷10000，双重换算导致 15.99 亿显示为
  0.0亿。渲染改为直接格式化亿元值；沪股通/深股通任一侧缺列时显示 `-`，
  不再静默显示 0。
- `analyzers/northbound.py` 拆分字段 NaN 防护：`hgt/sgt` 列存在但当日为
  NaN 时返回 `None`（此前 `float(nan)/10000` 会把 NaN 写入 JSON detail，
  非法 JSON 且渲染为 `nan亿`）。
- 修正 `analyze()` 信号评分处过时注释（误写"百万元 /100"，实际为
  "万元 /10000"），避免后续维护误用。

## [1.0.1] - 2026-08-04

### Fixed
- `data/fetcher.py` 的 kk_common 自动注入路径多算一级：
  `../../../../common/src` 指向不存在的 `skills/common/src`，导致自动注入从未
  生效（只能依赖 PYTHONPATH 或 site-packages 兜底）。修正为 `../../../common/src`
  （到 `public/` 后取同级 `common/src`），任何目录结构正确的部署都可自动导入。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
