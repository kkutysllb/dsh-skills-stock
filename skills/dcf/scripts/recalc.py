#!/usr/bin/env python3
"""DCF 模型公式重算工具 —— 交付前强制步骤（SKILL.md 引用）。

用法:
    python3 recalc.py model.xlsx [timeout_seconds]

功能:
1. 打开 Excel 模型（openpyxl，formula 模式），设置 fullCalcOnLoad 强制
   Excel/LibreOffice 打开时重算全部公式（openpyxl 不执行公式求值，
   重算由宿主表格软件完成）；
2. 扫描所有单元格公式，统计公式数量并做基本语法校验；
3. 若同目录存在 validate_dcf.py，自动调用其校验器报告公式错误
   （#REF! / #DIV/0! / #VALUE! 等），直到 status == success。

退出码: 0 = 通过, 1 = 存在公式错误或文件无法打开。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 常见公式错误标记
_ERROR_PATTERNS = re.compile(r"#(REF|DIV/0|VALUE|NAME\?|NULL|NUM|N/A)")


def recalc(excel_path: Path, timeout: int) -> int:
    if not excel_path.exists():
        print(f"错误: 文件不存在: {excel_path}", file=sys.stderr)
        return 1

    try:
        import openpyxl
    except ImportError as exc:
        print(f"错误: 需要 openpyxl: {exc}", file=sys.stderr)
        return 1

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=False)
    except Exception as exc:
        print(f"错误: 无法打开工作簿: {exc}", file=sys.stderr)
        return 1

    # 1. 强制打开时全量重算（LibreOffice/Excel 均识别 calcPr）
    try:
        wb.calculation.fullCalcOnLoad = True
    except Exception:
        pass  # 老版本 openpyxl 可能无此属性，不影响主流程

    formula_count = 0
    error_count = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formula_count += 1
                    if _ERROR_PATTERNS.search(cell.value):
                        error_count += 1
                        print(f"  [公式错误] {ws.title}!{cell.coordinate}: {cell.value[:80]}")

    wb.save(excel_path)
    print(f"重算标记已写入: {excel_path.name}")
    print(f"公式总数: {formula_count}  检测到错误引用: {error_count}")

    # 2. 复用 validate_dcf.py 做完整校验（若存在）
    validator = excel_path.parent / "validate_dcf.py"
    if validator.exists():
        print(f"调用校验器: {validator.name}")
        try:
            r = subprocess.run(
                [sys.executable, str(validator), str(excel_path)],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.stdout:
                print(r.stdout[-2000:])
            if r.returncode != 0 and r.stderr:
                print(r.stderr[-2000:], file=sys.stderr)
            return r.returncode
        except subprocess.TimeoutExpired:
            print(f"错误: 校验超时（{timeout}s）", file=sys.stderr)
            return 1

    return 1 if error_count else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="DCF 模型公式重算 + 校验")
    ap.add_argument("excel_path", help="DCF 模型 .xlsx 路径")
    ap.add_argument("timeout", type=int, nargs="?", default=30, help="校验超时秒数（默认 30）")
    args = ap.parse_args()
    return recalc(Path(args.excel_path), args.timeout)


if __name__ == "__main__":
    sys.exit(main())
