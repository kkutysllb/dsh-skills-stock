# Changelog

## [2.0.2] - 2026-08-10

### Fixed
- 消除 pywencai 误导：`__init__` 不再提示「请执行 pip install pywencai」（此前 Agent
  看到该提示误判技能不可用，去 pip install 失败后放弃主路径）；
  `requires.packages` 与 `metadata.install` 移除 pywencai（沙箱预装依赖不再尝试
  安装它）；SKILL.md/脚本 docstring 统一说明主数据源为问财网关 CLI（纯标准库，
  无需额外安装），pywencai 仅为可选增强。
- 验证：模拟无 pywencai 环境运行 `analyze_industry.py "光通信" --depth brief --json`
  成功（100 只概念股、行业分布、产业链结构齐全）。

## [2.0.1] - 2026-08-10

### Fixed
- `scripts/analyze_industry.py` 数据层 pywencai 与 Node 22 不兼容：
  pywencai 内部调用 node 脚本，Node 22 的 `punycode` 弃用警告打印到 stdout
  污染 JSON 输出，导致解析失败返回 None（`'NoneType' object has no attribute 'get'`）。
  修复：`WencaiDataLayer.query()` 优先走本项目自带网关 CLI
  （`industry-query-cli.py`，IWENCAI_API_KEY，跨 Node 版本稳定），pywencai 降级为兜底。
- `get_industry_overview` 网关返回的「所属同花顺行业」列为 list（pywencai 为字符串），
  `value_counts()` 报 `unhashable type: 'list'`。修复：explode 扁平化后统计。
- `analyze_industry()` 入口可用性检查改为「网关 CLI 或 pywencai 任一可用」。

## [2.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
