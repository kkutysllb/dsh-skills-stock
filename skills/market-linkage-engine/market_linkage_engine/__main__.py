"""
市场联动分析引擎 — 命令行入口

用法:
    python -m market_linkage_engine                  # 默认日度分析
    python -m market_linkage_engine daily            # 日度分析
    python -m market_linkage_engine weekly           # 周度分析
    python -m market_linkage_engine daily 20240105   # 指定交易日
    python -m market_linkage_engine daily --iwencai  # 启用问财实时数据
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="A 股市场联动分析引擎（8 大维度）"
    )
    parser.add_argument(
        "report_type",
        nargs="?",
        default="daily",
        choices=["daily", "weekly"],
        help="报告类型：daily（日度）/ weekly（周度），默认 daily",
    )
    parser.add_argument(
        "trade_date",
        nargs="?",
        default=None,
        help="交易日期 YYYYMMDD（默认最近交易日）",
    )
    parser.add_argument(
        "--iwencai", "-i",
        action="store_true",
        help="启用同花顺问财实时数据补充",
    )
    parser.add_argument(
        "--format", "-f",
        default="markdown",
        choices=["markdown", "json", "summary"],
        help="输出格式：markdown / json / summary（一句话），默认 markdown",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径（默认打印到 stdout）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 延迟导入，避免 --help 时连接 Tushare
    from .engine import LinkageEngine

    engine = LinkageEngine(use_iwencai=args.iwencai)

    if args.report_type == "daily":
        report = engine.run_daily(trade_date=args.trade_date)
    else:
        report = engine.run_weekly(end_date=args.trade_date)

    # 渲染输出
    if args.format == "markdown":
        output = engine.to_markdown(report)
    elif args.format == "json":
        output = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    else:  # summary
        output = engine.to_summary(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"报告已写入: {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
