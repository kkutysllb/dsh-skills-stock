"""
common — kk_Skills 公共库

提供所有技能包共享的四大核心模块：

1. **iwencai_client** — 同花顺问财 OpenAPI 统一客户端
   - API 密钥管理、请求头构造、查询执行、响应解析
   - 严格遵循问财 OpenAPI 网关规范

2. **tushare_client** — Tushare Pro API 统一客户端
   - 股票/期货/ETF/基金/宏观经济全量接口封装
   - 自动限速、环境变量密钥管理

3. **finance_data_gateway** — 金融数据网关（分析技能首选入口）
   - 方法名与 Tushare 官方接口一致，实现可替换
   - 分析技能必须通过本网关访问 Tushare，禁止直接 import tushare

4. **formatters** — 金融分析格式化工具集
   - 百分比、进度条、信号标记、趋势图标、评分条
   - Markdown 表格生成、技术指标格式化
"""

from kk_common.iwencai_client import (
    APIError,
    IwencaiClient,
    generate_trace_id,
    build_headers,
)

from kk_common.tushare_client import TushareClient, get_tushare_client, reset_tushare_client
from kk_common.finance_data_gateway import (
    FinanceDataGateway,
    TushareDataAdapter,
    get_finance_data_gateway,
    reset_finance_data_gateway,
)

from kk_common.formatters import (
    pct,
    bar,
    score_bar,
    signal_cn,
    signal_mark,
    trend_icon,
    sentiment_icon,
    format_number,
    fmt_ma,
    fmt_macd,
    fmt_rsi,
    fmt_kdj,
    fmt_boll,
    md_table,
    md_header,
)

__all__ = [
    # iwencai_client
    "APIError",
    "IwencaiClient",
    "generate_trace_id",
    "build_headers",
    # tushare_client
    "TushareClient",
    "get_tushare_client",
    "reset_tushare_client",
    # finance_data_gateway
    "FinanceDataGateway",
    "TushareDataAdapter",
    "get_finance_data_gateway",
    "reset_finance_data_gateway",
    # formatters
    "pct",
    "bar",
    "score_bar",
    "signal_cn",
    "signal_mark",
    "trend_icon",
    "sentiment_icon",
    "format_number",
    "fmt_ma",
    "fmt_macd",
    "fmt_rsi",
    "fmt_kdj",
    "fmt_boll",
    "md_table",
    "md_header",
]
