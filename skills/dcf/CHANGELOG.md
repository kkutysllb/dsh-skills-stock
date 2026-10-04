# Changelog

## [1.0.1] - 2026-08-10

### Fixed
- `scripts/validate_dcf.py` `_check_wacc_range` 调用 `workbook_values.get('WACC')`，
  openpyxl `Workbook` 对象无 `.get` 方法 → WACC 范围校验恒失败（`'Workbook' object
  has no attribute 'get'`）。修复：改用 `'WACC' in workbook_values.sheetnames` 判断后索引。
- 验证：构造真实 DCF 模型（DCF/WACC/Sensitivity 三表、54 条公式）跑通
  `validate_dcf.py`（PASS，终值 g<WACC 通过）与 `recalc.py`（公式 54、错误引用 0）。

## [1.0.0] - 2026-07-03

### Added
- Initial standardized package structure.
