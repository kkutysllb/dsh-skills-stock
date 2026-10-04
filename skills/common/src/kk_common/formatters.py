"""
common 金融分析格式化工具集

提供所有分析技能包共享的格式化输出函数。
这些函数原本分散在多个项目的分析引擎脚本中（如 analyze_technical.py），
现在统一到此模块，消除重复代码。
"""

from typing import Optional, Union, List, Any


# ==============================================================================
# 核心格式化函数
# ==============================================================================

def pct(val: float, decimals: int = 2) -> str:
    """格式化百分比值，带 +/- 符号"""
    sign = '+' if val > 0 else ''
    return f"{sign}{val:.{decimals}f}%"


def bar(val: float, max_val: float, width: int = 20, fill: str = '█', empty: str = '░') -> str:
    """生成文本进度条"""
    if max_val == 0:
        return empty * width
    filled = int(abs(val) / max_val * width)
    return fill * filled + empty * (width - filled)


def score_bar(score: float, max_score: float = 100, width: int = 20) -> str:
    """带颜色语义的评分进度条"""
    return bar(score, max_score, width)


def signal_cn(direction: str) -> str:
    """信号方向转中文"""
    return {'buy': '买入', 'sell': '卖出', 'neutral': '观望'}.get(direction, '观望')


def signal_mark(direction: str) -> str:
    """信号方向转符号标记"""
    return {'buy': '▲', 'sell': '▼', 'neutral': '─'}.get(direction, '─')


def trend_icon(trend: str) -> str:
    """趋势文字转 Emoji 图标"""
    if '上升' in trend or '上涨' in trend:
        return '📈'
    elif '下降' in trend or '下跌' in trend:
        return '📉'
    else:
        return '➡️'


def sentiment_icon(sentiment: str) -> str:
    """情绪文字转 Emoji 图标"""
    if '乐观' in sentiment or '积极' in sentiment or '好' in sentiment:
        return '😊'
    elif '悲观' in sentiment or '消极' in sentiment or '差' in sentiment:
        return '😟'
    else:
        return '😐'


def format_number(num: Optional[float], decimals: int = 2, default: str = '--') -> str:
    """安全格式化数字，None 返回默认值"""
    if num is None:
        return default
    return f"{num:.{decimals}f}"


# ==============================================================================
# 技术指标格式化
# ==============================================================================

def fmt_ma(ma5: Optional[float], ma10: Optional[float], ma20: Optional[float],
           ma60: Optional[float] = None) -> str:
    """格式化均线指标"""
    parts = [
        f"MA5={format_number(ma5)}",
        f"MA10={format_number(ma10)}",
        f"MA20={format_number(ma20)}",
    ]
    if ma60 is not None:
        parts.append(f"MA60={format_number(ma60)}")
    return " | ".join(parts)


def fmt_macd(dif: Optional[float], dea: Optional[float], macd_bar: Optional[float]) -> str:
    """格式化 MACD 指标"""
    return f"DIF={format_number(dif)} | DEA={format_number(dea)} | MACD={format_number(macd_bar)}"


def fmt_rsi(rsi6: Optional[float], rsi12: Optional[float], rsi24: Optional[float]) -> str:
    """格式化 RSI 指标"""
    return f"RSI6={format_number(rsi6)} | RSI12={format_number(rsi12)} | RSI24={format_number(rsi24)}"


def fmt_kdj(k: Optional[float], d: Optional[float], j: Optional[float]) -> str:
    """格式化 KDJ 指标"""
    return f"K={format_number(k)} | D={format_number(d)} | J={format_number(j)}"


def fmt_boll(mid: Optional[float], upper: Optional[float], lower: Optional[float]) -> str:
    """格式化布林带指标"""
    return f"MID={format_number(mid)} | UPPER={format_number(upper)} | LOWER={format_number(lower)}"


# ==============================================================================
# Markdown 表格工具
# ==============================================================================

def md_table(headers: List[str], rows: List[List[Any]]) -> str:
    """生成 Markdown 表格

    Args:
        headers: 表头列表
        rows: 数据行列表，每行为与 headers 等长的值列表

    Returns:
        Markdown 格式的表格字符串
    """
    if not headers:
        return ""

    # 构造分隔行
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"

    # 表头行
    header_row = "| " + " | ".join(str(h) for h in headers) + " |"

    # 数据行
    data_rows = []
    for row in rows:
        data_row = "| " + " | ".join(str(cell) for cell in row) + " |"
        data_rows.append(data_row)

    return header_row + "\n" + separator + "\n" + "\n".join(data_rows)


def md_header(text: str, level: int = 2) -> str:
    """生成 Markdown 标题"""
    return "#" * level + " " + text
