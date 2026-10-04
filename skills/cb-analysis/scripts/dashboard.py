#!/usr/bin/env python3
"""
可转债全景数据看板 CLI — hithink-cb-dashboard

支持以下模式：
  dashboard          — 全景看板（所有模块汇总）
  forced-redeem      — 强赎时间表补充版
  downrev-count      — 下修天计数表格
  small-scale        — 前10名最小流通规模
  limit-stock        — 正股涨停/跌停的转债
  dragon-tiger       — 当日龙虎榜
  issuance           — 转债发行进度提醒
  top10              — TOP10 排行榜
  bond-cushion       — 配债安全垫
  rights-recovery    — 配债填权
  time-option        — 时间期权价值
  hard-redeem        — 刚兑标的
  maturity-price     — 到期赎回价对比
  premium-analysis   — 溢价率分析
  grid-trading       — 网格交易标的
  monster-bond       — 妖债监控
  arbitrage          — 套利机会

数据源：同花顺问财 (iwencai) OpenAPI
严格遵循 X-Claw-* Header 规范，使用 Python3 标准库，无第三方依赖。
"""

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


# ─── 常量 ────────────────────────────────────────────────────────────
SKILL_NAME = "hithink-cb-dashboard"
SKILL_VERSION = "1.0.0"
DEFAULT_API_URL = "https://openapi.iwencai.com/v1/query2data"
DEFAULT_TIMEOUT = 30
DEFAULT_LIMIT = "20"


# ─── 异常 ────────────────────────────────────────────────────────────
class CBDashboardAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


# ─── 通用 API 层 ─────────────────────────────────────────────────────
def _trace_id() -> str:
    """生成 64 字符十六进制全局唯一追踪 ID。"""
    return secrets.token_hex(32)


def _api_key(cli_key: Optional[str] = None) -> str:
    """获取 API 密钥：优先 CLI 参数，其次环境变量。"""
    key = cli_key or os.environ.get("IWENCAI_API_KEY", "")
    if not key:
        raise CBDashboardAPIError(
            "API 密钥未设置。请通过 --api-key 或环境变量 IWENCAI_API_KEY 指定。\n"
            "首次使用获取指引：打开 https://www.iwencai.com/skillhub → 登录 → "
            "点击 Skill → 安装方式-Agent用户-复制您的 IWENCAI_API_KEY。"
        )
    return key


def _headers(api_key: str, trace_id: str, call_type: str = "normal") -> dict:
    """构造符合问财网关规范的请求头。"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": SKILL_NAME,
        "X-Claw-Skill-Version": SKILL_VERSION,
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": trace_id,
    }


def _query(
    query_str: str,
    api_key: str,
    call_type: str = "normal",
    timeout: int = DEFAULT_TIMEOUT,
    limit: str = DEFAULT_LIMIT,
) -> dict:
    """调用问财 API，返回解析后的 dict。"""
    tid = _trace_id()
    payload = {
        "query": query_str,
        "page": "1",
        "limit": limit,
        "is_cache": "1",
        "expand_index": "true",
    }
    hdrs = _headers(api_key, tid, call_type)
    req = urllib.request.Request(
        DEFAULT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=hdrs,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            if not body.strip():
                return {"text_response": "", "trace_id": tid, "datas": []}
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    parsed["trace_id"] = tid
                    return parsed
                return {"data": parsed, "trace_id": tid, "datas": []}
            except json.JSONDecodeError:
                return {"text_response": body, "trace_id": tid, "datas": []}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        raise CBDashboardAPIError(
            f"HTTP {e.code}: {e.reason}", status_code=e.code, response=err_body
        )
    except urllib.error.URLError as e:
        raise CBDashboardAPIError(f"网络错误: {e.reason}")


def _query_with_retry(
    queries: List[str],
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
    limit: str = DEFAULT_LIMIT,
) -> List[dict]:
    """执行一组查询，每个查询最多重试 1 次（简化条件）。返回所有成功的 datas 列表。"""
    all_datas = []
    for q in queries:
        try:
            resp = _query(q, api_key, "normal", timeout, limit)
            datas = resp.get("datas", [])
            if datas:
                all_datas.append({"query": q, "datas": datas, "status": "OK"})
            else:
                # 重试：简化查询
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, limit)
                datas2 = resp2.get("datas", [])
                if datas2:
                    all_datas.append({"query": retry_q, "datas": datas2, "status": "RETRY_OK"})
                else:
                    all_datas.append({"query": q, "datas": [], "status": "EMPTY"})
        except CBDashboardAPIError as e:
            all_datas.append({"query": q, "datas": [], "status": "ERROR", "error": e.message})
    return all_datas


def _simplify_query(query: str) -> str:
    """简化查询语句用于重试——去掉过于具体的字段列表，保留核心筛选条件。"""
    # 去掉「取前N名」「按X排序」等排序/限制子句
    parts = query.split("可转债")
    if len(parts) >= 2:
        # 保留主筛选条件，去掉详细字段
        prefix = parts[0]
        return f"{prefix}可转债"
    return query


# ─── 通用工具函数 ────────────────────────────────────────────────────
def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val: Any, default: str = "-") -> str:
    if val is None:
        return default
    return str(val).strip()


def _extract_fields(row: dict, fields: List[str]) -> dict:
    """从一行数据中提取指定字段，支持带日期后缀的字段名模糊匹配。"""
    result = {}
    for field in fields:
        # 先精确匹配
        if field in row:
            result[field] = row[field]
            continue
        # 模糊匹配：字段名在 key 中出现
        for k, v in row.items():
            if field in k:
                result[field] = v
                break
        if field not in result:
            result[field] = None
    return result


# ═══════════════════════════════════════════════════════════════════════
# 模块一：强赎时间表补充版
# ═══════════════════════════════════════════════════════════════════════

# A. 已公告强赎 —— 最后交易日 / 赎回价格
Q_FORCED_REDEEM_A = "已公告强赎的可转债 可转债代码 可转债简称 最后交易日 赎回价格 强赎触发条件 正股收盘价 转股价 转股溢价率"

# B. 不强赎区间
Q_FORCED_REDEEM_B = "公告不强赎的可转债 可转债代码 可转债简称 不强赎截止日期 正股收盘价 转股价 强赎触发价"

# C. 强赎但未公布具体时间
Q_FORCED_REDEEM_C = "已触发强赎的可转债 可转债代码 可转债简称 强赎触发日期 正股收盘价 转股价 强赎触发比例"

# D. 强赎倒计时
Q_FORCED_REDEEM_D = "接近强赎触发的可转债 可转债代码 可转债简称 强赎触发进度 正股收盘价 转股价 距强赎触发还需涨跌幅"


def module_forced_redeem(api_key: str, timeout: int) -> dict:
    """强赎时间表补充版。"""
    queries = [
        ("A_已公告强赎", Q_FORCED_REDEEM_A),
        ("B_不强赎区间", Q_FORCED_REDEEM_B),
        ("C_强赎未公布具体时间", Q_FORCED_REDEEM_C),
        ("D_强赎倒计时", Q_FORCED_REDEEM_D),
    ]
    results = {}
    for label, q in queries:
        try:
            resp = _query(q, api_key, "normal", timeout, "20")
            datas = resp.get("datas", [])
            if not datas:
                # 重试一次简化查询
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, "20")
                datas = resp2.get("datas", [])
            results[label] = {
                "datas": datas,
                "count": len(datas),
                "status": "OK" if datas else "EMPTY",
            }
        except CBDashboardAPIError as e:
            results[label] = {"datas": [], "count": 0, "status": "ERROR", "error": e.message}

    return {
        "module": "forced_redeem",
        "title": "🔴 强赎时间表补充版",
        "data": results,
        "summary": _summary_forced_redeem(results),
    }


def _summary_forced_redeem(results: dict) -> str:
    """生成强赎时间表的文字摘要。"""
    parts = []
    for label, info in results.items():
        cnt = info.get("count", 0)
        status = info.get("status", "")
        if status == "OK":
            parts.append(f"{label}: {cnt} 只")
        elif status == "EMPTY":
            parts.append(f"{label}: 暂无数据")
        else:
            parts.append(f"{label}: 查询异常")
    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# 模块二：下修天计数表格
# ═══════════════════════════════════════════════════════════════════════

# 参考 集思录 (jisilu.cn) 下修数据结构：
# - 下修触发价：正股连续N日收盘价低于转股价的X%时触发
# - 满足天数/剩余天数：距完全满足下修条件的进度

Q_DOWNREV_1 = "即将满足下修条件的可转债 可转债代码 可转债简称 下修触发价 正股收盘价 转股价 满足下修条件天数 剩余需满足天数"
Q_DOWNREV_2 = "下修触发进度 可转债 可转债代码 可转债简称 下修触发价 正股收盘价 转股价 下修进度"
Q_DOWNREV_3 = "接近下修触发日的可转债 可转债代码 可转债简称 下修触发价 正股收盘价 转股价"


def module_downrev_count(api_key: str, timeout: int) -> dict:
    """下修天计数表格。"""
    queries = [Q_DOWNREV_1, Q_DOWNREV_2, Q_DOWNREV_3]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    # 合并去重（按可转债代码）
    seen_codes = set()
    merged_datas = []
    for qr in query_results:
        for row in qr.get("datas", []):
            code = _safe_str(row.get("可转债代码", ""))
            if code and code not in seen_codes:
                seen_codes.add(code)
                # 标注剩余天数 ≤ 5 的重点标的
                remain_days = _safe_float(
                    row.get("剩余需满足天数", row.get("距触发剩余天数", None)),
                    default=999
                )
                row["_priority"] = "HIGH" if remain_days <= 5 else "NORMAL"
                row["_remaining_days"] = remain_days
                merged_datas.append(row)

    # 按剩余天数排序（优先显示即将触发的）
    merged_datas.sort(key=lambda x: x.get("_remaining_days", 999))

    return {
        "module": "downrev_count",
        "title": "🟡 下修天计数表格",
        "data": merged_datas,
        "count": len(merged_datas),
        "high_priority_count": sum(1 for d in merged_datas if d.get("_priority") == "HIGH"),
        "tip": (
            "参考集思录数据结构 (jisilu.cn)。"
            "优先标注剩余满足天数 ≤ 5 天的标的。"
            "实际下修触发条件请以公告为准。"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块三：前10名最小流通规模
# ═══════════════════════════════════════════════════════════════════════

Q_SMALL_SCALE = (
    "可转债 流通规模 成交额 正股所属行业 剩余期限 "
    "可转债代码 可转债简称 收盘价 转股溢价率 "
    "按流通规模从小到大排序 取前10名"
)


def module_small_scale(api_key: str, timeout: int) -> dict:
    """前10名最小流通规模。"""
    try:
        resp = _query(Q_SMALL_SCALE, api_key, "normal", timeout, "10")
        datas = resp.get("datas", [])
        if not datas:
            # 重试：简化
            retry_q = "可转债 流通规模最小的 取前10名"
            resp2 = _query(retry_q, api_key, "retry", timeout, "10")
            datas = resp2.get("datas", [])

        # 添加排名序号
        for i, row in enumerate(datas):
            row["_rank"] = i + 1

        return {
            "module": "small_scale",
            "title": "🟢 前10名最小流通规模",
            "data": datas,
            "count": len(datas),
            "status": "OK" if datas else "EMPTY",
        }
    except CBDashboardAPIError as e:
        return {
            "module": "small_scale",
            "title": "🟢 前10名最小流通规模",
            "data": [],
            "count": 0,
            "status": "ERROR",
            "error": e.message,
        }


# ═══════════════════════════════════════════════════════════════════════
# 模块四：正股涨停/跌停的转债
# ═══════════════════════════════════════════════════════════════════════

Q_LIMIT_UP = (
    "正股涨停的可转债 可转债代码 可转债简称 可转债涨跌幅 "
    "正股涨跌幅 正股名称 转股溢价率 成交额 转股价值"
)
Q_LIMIT_DOWN = (
    "正股跌停的可转债 可转债代码 可转债简称 可转债涨跌幅 "
    "正股涨跌幅 正股名称 转股溢价率 成交额 转股价值"
)


def module_limit_stock(api_key: str, timeout: int) -> dict:
    """正股涨停/跌停的转债。"""
    results = {}
    for label, q in [("涨停", Q_LIMIT_UP), ("跌停", Q_LIMIT_DOWN)]:
        try:
            resp = _query(q, api_key, "normal", timeout, "20")
            datas = resp.get("datas", [])
            if not datas:
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, "20")
                datas = resp2.get("datas", [])
            results[label] = {"datas": datas, "count": len(datas)}
        except CBDashboardAPIError as e:
            results[label] = {"datas": [], "count": 0, "error": e.message}

    return {
        "module": "limit_stock",
        "title": "🔵 正股涨停/跌停的转债",
        "data": results,
        "summary": (
            f"正股涨停: {results.get('涨停', {}).get('count', 0)} 只, "
            f"正股跌停: {results.get('跌停', {}).get('count', 0)} 只"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块五：当日龙虎榜
# ═══════════════════════════════════════════════════════════════════════

Q_DRAGON_TIGER_CB = (
    "上龙虎榜的可转债 可转债代码 可转债简称 涨跌幅 成交额 "
    "买入金额最大的前5名营业部 卖出金额最大的前5名营业部 净买入金额"
)
Q_DRAGON_TIGER_STOCK = (
    "可转债正股上龙虎榜 可转债代码 可转债简称 正股名称 正股涨跌幅 "
    "正股成交额 上榜原因 净买入金额"
)


def module_dragon_tiger(api_key: str, timeout: int) -> dict:
    """当日龙虎榜。"""
    results = {}
    for label, q in [("转债龙虎榜", Q_DRAGON_TIGER_CB), ("正股龙虎榜", Q_DRAGON_TIGER_STOCK)]:
        try:
            resp = _query(q, api_key, "normal", timeout, "20")
            datas = resp.get("datas", [])
            if not datas:
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, "20")
                datas = resp2.get("datas", [])
            results[label] = {"datas": datas, "count": len(datas)}
        except CBDashboardAPIError as e:
            results[label] = {"datas": [], "count": 0, "error": e.message}

    return {
        "module": "dragon_tiger",
        "title": "🟣 当日龙虎榜",
        "data": results,
        "summary": (
            f"转债上榜: {results.get('转债龙虎榜', {}).get('count', 0)} 只, "
            f"正股上榜: {results.get('正股龙虎榜', {}).get('count', 0)} 只"
        ),
        "example": "如本川转债、丽岛新材(正股)、ST三房(正股)等",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块六：转债发行进度提醒
# ═══════════════════════════════════════════════════════════════════════

Q_ISSUANCE_REGISTERED = (
    "证监会同意注册的可转债 正股简称 含权率 发行规模 转股价 "
    "可转债代码 正股代码"
)
Q_ISSUANCE_REVIEW = (
    "发审委通过的可转债 正股简称 含权率 发行规模 "
    "可转债代码 正股代码"
)
Q_ISSUANCE_BOARD = (
    "董事会预案的可转债 正股简称 含权率 发行规模 "
    "可转债代码 正股代码"
)
Q_ISSUANCE_SHAREHOLDER = (
    "股东大会通过的可转债 正股简称 含权率 发行规模 "
    "可转债代码 正股代码"
)

# 含权率阈值
EQUITY_RATIO_THRESHOLD = 15.0


def module_issuance(api_key: str, timeout: int) -> dict:
    """转债发行进度提醒。"""
    stages = [
        ("证监会同意注册", Q_ISSUANCE_REGISTERED),
        ("发审委通过", Q_ISSUANCE_REVIEW),
        ("股东大会通过", Q_ISSUANCE_SHAREHOLDER),
        ("董事会预案", Q_ISSUANCE_BOARD),
    ]
    results = {}
    all_high_priority = []

    for stage_name, q in stages:
        try:
            resp = _query(q, api_key, "normal", timeout, "30")
            datas = resp.get("datas", [])
            if not datas:
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, "30")
                datas = resp2.get("datas", [])

            # 标注高含权率标的
            for row in datas:
                ratio = _safe_float(row.get("含权率", None))
                row["_equity_ratio"] = ratio
                row["_high_priority"] = ratio >= EQUITY_RATIO_THRESHOLD
                if row["_high_priority"]:
                    all_high_priority.append({
                        "正股简称": _safe_str(row.get("正股简称")),
                        "含权率": ratio,
                        "阶段": stage_name,
                        "发行规模": _safe_str(row.get("发行规模")),
                        "可转债代码": _safe_str(row.get("可转债代码")),
                    })

            results[stage_name] = {
                "datas": datas,
                "count": len(datas),
                "high_ratio_count": sum(1 for r in datas if r.get("_high_priority")),
            }
        except CBDashboardAPIError as e:
            results[stage_name] = {"datas": [], "count": 0, "error": e.message}

    # 高含权率标的按含权率从高到低排序
    all_high_priority.sort(key=lambda x: x.get("含权率", 0), reverse=True)

    return {
        "module": "issuance",
        "title": "🟠 转债发行进度提醒",
        "data": results,
        "high_priority_bonds": all_high_priority,
        "high_priority_count": len(all_high_priority),
        "threshold": f"含权率 ≥ {EQUITY_RATIO_THRESHOLD}%",
        "example": "如宝钛股份(20.59%, 证监会同意注册)、湖北宜化(18.78%, 发审委通过)",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块七：TOP10 排行榜
# ═══════════════════════════════════════════════════════════════════════

TOP10_QUERIES = {
    "溢价率最低TOP10": (
        "转股溢价率最低的可转债 转股溢价率 转股价值 收盘价 到期收益率 "
        "可转债代码 可转债简称 剩余期限 "
        "按转股溢价率从低到高排序 取前10名"
    ),
    "双低值最低TOP10": (
        "双低值最低的可转债 双低值 收盘价 转股溢价率 纯债溢价率 "
        "可转债代码 可转债简称 剩余期限 "
        "按双低值从低到高排序 取前10名"
    ),
    "到期收益率最高TOP10": (
        "到期收益率最高的可转债 到期收益率 剩余期限 信用评级 收盘价 "
        "可转债代码 可转债简称 转股溢价率 "
        "按到期收益率从高到低排序 取前10名"
    ),
    "成交额最大TOP10": (
        "成交额最大的可转债 成交额 换手率 涨跌幅 转股溢价率 "
        "可转债代码 可转债简称 收盘价 "
        "按成交额从大到小排序 取前10名"
    ),
    "换手率最高TOP10": (
        "换手率最高的可转债 换手率 成交额 涨跌幅 流通规模 "
        "可转债代码 可转债简称 收盘价 "
        "按换手率从高到低排序 取前10名"
    ),
}


def module_top10(api_key: str, timeout: int) -> dict:
    """TOP10 排行榜。"""
    results = {}
    for rank_name, q in TOP10_QUERIES.items():
        try:
            resp = _query(q, api_key, "normal", timeout, "10")
            datas = resp.get("datas", [])
            if not datas:
                retry_q = _simplify_query(q)
                resp2 = _query(retry_q, api_key, "retry", timeout, "10")
                datas = resp2.get("datas", [])

            # 添加排名
            for i, row in enumerate(datas):
                row["_rank"] = i + 1

            results[rank_name] = {"datas": datas, "count": len(datas)}
        except CBDashboardAPIError as e:
            results[rank_name] = {"datas": [], "count": 0, "error": e.message}

    return {
        "module": "top10",
        "title": "⚪ TOP10 排行榜",
        "data": results,
        "rankings": list(TOP10_QUERIES.keys()),
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块八：配债安全垫
# ═══════════════════════════════════════════════════════════════════════

Q_BOND_CUSHION = (
    "含权率大于5%的可转债 含权率 正股收盘价 配债收益 "
    "可转债代码 可转债简称 正股简称 转股价 "
    "纯债价值 到期赎回价 收盘价 "
    "按含权率从高到低排序 取前20名"
)


def module_bond_cushion(api_key: str, timeout: int) -> dict:
    """配债安全垫：高含权率标的的正股安全边际分析。"""
    queries = [Q_BOND_CUSHION]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    cushion_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            equity_ratio = _safe_float(row.get("含权率"))
            stock_price = _safe_float(row.get("正股收盘价"))
            conv_price = _safe_float(row.get("转股价"))
            pure_bond = _safe_float(row.get("纯债价值"))
            maturity_price = _safe_float(row.get("到期赎回价"))
            cb_price = _safe_float(row.get("收盘价"))

            # 计算安全垫指标
            cushion_pct = 0
            if conv_price > 0:
                cushion_pct = (stock_price - conv_price) / conv_price * 100
            bond_floor_pct = 0
            if cb_price > 0 and pure_bond > 0:
                bond_floor_pct = (pure_bond / cb_price - 1) * 100

            row["_cushion_pct"] = round(cushion_pct, 2)
            row["_bond_floor_pct"] = round(bond_floor_pct, 2)
            row["_equity_ratio"] = equity_ratio
            row["_safety_level"] = (
                "高安全" if bond_floor_pct > 10 and equity_ratio > 10
                else "中等" if bond_floor_pct > 0
                else "低安全"
            )
            cushion_data.append(row)

    cushion_data.sort(key=lambda x: x.get("_equity_ratio", 0), reverse=True)

    return {
        "module": "bond_cushion",
        "title": "🛡️ 配债安全垫",
        "data": cushion_data,
        "count": len(cushion_data),
        "high_safety_count": sum(1 for d in cushion_data if d.get("_safety_level") == "高安全"),
        "summary": (
            f"高含权率标的 {len(cushion_data)} 只, "
            f"其中高安全 {sum(1 for d in cushion_data if d.get('_safety_level') == '高安全')} 只"
        ),
        "tip": "安全垫 = 正股相对转股价的安全边际 + 纯债价值托底。含权率越高，配债收益越大。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块九：配债填权
# ═══════════════════════════════════════════════════════════════════════

Q_RIGHTS_RECOVERY = (
    "即将发行可转债的正股 正股简称 正股代码 正股涨跌幅 "
    "含权率 发行规模 正股收盘价 正股所属行业 "
    "按含权率从高到低排序 取前20名"
)


def module_rights_recovery(api_key: str, timeout: int) -> dict:
    """配债填权：即将发行可转债的正股填权机会。"""
    queries = [Q_RIGHTS_RECOVERY]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    recovery_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            equity_ratio = _safe_float(row.get("含权率"))
            stock_change = _safe_float(row.get("正股涨跌幅"))
            row["_equity_ratio"] = equity_ratio
            row["_fill_direction"] = (
                "填权中" if stock_change > 0
                else "贴权中" if stock_change < 0
                else "持平"
            )
            recovery_data.append(row)

    recovery_data.sort(key=lambda x: x.get("_equity_ratio", 0), reverse=True)

    return {
        "module": "rights_recovery",
        "title": "📈 配债填权",
        "data": recovery_data,
        "count": len(recovery_data),
        "filling_count": sum(1 for d in recovery_data if d.get("_fill_direction") == "填权中"),
        "summary": (
            f"填权标的 {sum(1 for d in recovery_data if d.get('_fill_direction') == '填权中')} 只, "
            f"贴权标的 {sum(1 for d in recovery_data if d.get('_fill_direction') == '贴权中')} 只"
        ),
        "tip": "含权率越高的正股，配债后的填权动力越强。关注正股涨跌幅与含权率的匹配度。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十：时间期权价值
# ═══════════════════════════════════════════════════════════════════════

Q_TIME_OPTION = (
    "剩余期限1年以上的可转债 剩余期限 转股溢价率 到期收益率 "
    "可转债代码 可转债简称 收盘价 转股价值 纯债价值 "
    "按剩余期限从短到长排序 取前20名"
)


def module_time_option(api_key: str, timeout: int) -> dict:
    """时间期权价值：剩余期限与时间价值衰减分析。"""
    queries = [Q_TIME_OPTION]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    option_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            remain_term = _safe_float(row.get("剩余期限"))
            premium = _safe_float(row.get("转股溢价率"))
            cb_price = _safe_float(row.get("收盘价"))
            conv_value = _safe_float(row.get("转股价值"))
            pure_bond = _safe_float(row.get("纯债价值"))

            # 时间价值 = 转债价格 - max(转股价值, 纯债价值)
            intrinsic = max(conv_value, pure_bond)
            time_value = cb_price - intrinsic if cb_price > 0 and intrinsic > 0 else 0
            time_value_pct = (time_value / cb_price * 100) if cb_price > 0 else 0

            row["_time_value"] = round(time_value, 2)
            row["_time_value_pct"] = round(time_value_pct, 2)
            row["_time_decay"] = (
                "加速衰减" if remain_term < 1 else
                "中等衰减" if remain_term < 2 else
                "缓慢衰减"
            )
            row["_option_level"] = (
                "高时间价值" if time_value_pct > 20
                else "中等" if time_value_pct > 5
                else "低时间价值"
            )
            option_data.append(row)

    option_data.sort(key=lambda x: x.get("_time_value_pct", 0), reverse=True)

    return {
        "module": "time_option",
        "title": "⏰ 时间期权价值",
        "data": option_data,
        "count": len(option_data),
        "accelerating_decay_count": sum(1 for d in option_data if d.get("_time_decay") == "加速衰减"),
        "summary": (
            f"共 {len(option_data)} 只, "
            f"加速衰减 {sum(1 for d in option_data if d.get('_time_decay') == '加速衰减')} 只"
        ),
        "tip": "剩余期限越短，时间价值衰减越快。临近到期需关注强赎/回售/到期三大退出路径。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十一：刚兑标的
# ═══════════════════════════════════════════════════════════════════════

Q_HARD_REDEEM = (
    "到期收益率大于0的可转债 信用评级 纯债价值 到期收益率 "
    "可转债代码 可转债简称 收盘价 到期赎回价 剩余期限 "
    "正股简称 按到期收益率从高到低排序 取前20名"
)


def module_hard_redeem(api_key: str, timeout: int) -> dict:
    """刚兑标的：纯债价值>市价且到期收益率>0的标的。"""
    queries = [Q_HARD_REDEEM]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    hard_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            ytm = _safe_float(row.get("到期收益率"))
            pure_bond = _safe_float(row.get("纯债价值"))
            cb_price = _safe_float(row.get("收盘价"))
            maturity_price = _safe_float(row.get("到期赎回价"))
            rating = _safe_str(row.get("信用评级"))

            # 刚兑安全度评估
            bond_discount = (pure_bond / cb_price - 1) * 100 if cb_price > 0 else 0
            maturity_discount = (maturity_price / cb_price - 1) * 100 if cb_price > 0 else 0

            row["_ytm"] = ytm
            row["_bond_discount_pct"] = round(bond_discount, 2)
            row["_maturity_discount_pct"] = round(maturity_discount, 2)
            row["_hard_redeem_level"] = (
                "高确定性" if rating.startswith("AA") and ytm > 2 and bond_discount > 5
                else "中等" if rating.startswith("A") and ytm > 0
                else "低确定性"
            )
            hard_data.append(row)

    hard_data.sort(key=lambda x: x.get("_ytm", 0), reverse=True)

    return {
        "module": "hard_redeem",
        "title": "🏦 刚兑标的",
        "data": hard_data,
        "count": len(hard_data),
        "high_certainty_count": sum(1 for d in hard_data if d.get("_hard_redeem_level") == "高确定性"),
        "summary": (
            f"到期收益率>0 共 {len(hard_data)} 只, "
            f"高确定性 {sum(1 for d in hard_data if d.get('_hard_redeem_level') == '高确定性')} 只"
        ),
        "tip": "刚兑 = 持有到期按到期赎回价兑付。关注AA及以上评级、纯债价值>市价、YTM>2%的标的。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十二：到期赎回价对比
# ═══════════════════════════════════════════════════════════════════════

Q_MATURITY_PRICE = (
    "剩余期限3年以内的可转债 到期赎回价 收盘价 到期收益率 "
    "可转债代码 可转债简称 剩余期限 信用评级 转股溢价率 "
    "按剩余期限从短到长排序 取前20名"
)


def module_maturity_price(api_key: str, timeout: int) -> dict:
    """到期赎回价对比：到期赎回价 vs 当前收盘价。"""
    queries = [Q_MATURITY_PRICE]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    maturity_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            maturity_price = _safe_float(row.get("到期赎回价"))
            cb_price = _safe_float(row.get("收盘价"))
            ytm = _safe_float(row.get("到期收益率"))

            premium = (maturity_price / cb_price - 1) * 100 if cb_price > 0 else 0

            row["_maturity_premium_pct"] = round(premium, 2)
            row["_opportunity"] = (
                "折价机会" if premium > 5 and ytm > 3
                else "微利" if premium > 0
                else "溢价风险"
            )
            maturity_data.append(row)

    maturity_data.sort(key=lambda x: x.get("_maturity_premium_pct", 0), reverse=True)

    return {
        "module": "maturity_price",
        "title": "💰 到期赎回价对比",
        "data": maturity_data,
        "count": len(maturity_data),
        "discount_count": sum(1 for d in maturity_data if d.get("_opportunity") == "折价机会"),
        "summary": (
            f"共 {len(maturity_data)} 只, "
            f"折价机会 {sum(1 for d in maturity_data if d.get('_opportunity') == '折价机会')} 只"
        ),
        "tip": "到期赎回价 > 收盘价时，持有到期可获得确定收益。距离到期越近，确定性越高。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十三：溢价率分析
# ═══════════════════════════════════════════════════════════════════════

Q_PREMIUM_ANALYSIS = (
    "可转债 转股溢价率 纯债溢价率 双低值 收盘价 转股价值 "
    "可转债代码 可转债简称 剩余期限 成交额 "
    "按转股溢价率从低到高排序 取前30名"
)


def module_premium_analysis(api_key: str, timeout: int) -> dict:
    """溢价率分析：转股溢价率/纯债溢价率分布。"""
    queries = [Q_PREMIUM_ANALYSIS]
    query_results = _query_with_retry(queries, api_key, timeout, "30")

    premium_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            conv_premium = _safe_float(row.get("转股溢价率"))
            bond_premium = _safe_float(row.get("纯债溢价率"))
            dual_low = _safe_float(row.get("双低值"))

            row["_conv_premium"] = conv_premium
            row["_bond_premium"] = bond_premium
            row["_dual_low"] = dual_low
            row["_premium_zone"] = (
                "折价区" if conv_premium < 0
                else "低溢价" if conv_premium < 10
                else "中溢价" if conv_premium < 30
                else "高溢价"
            )
            premium_data.append(row)

    # 统计各区间分布
    zone_counts = {}
    for d in premium_data:
        zone = d.get("_premium_zone", "未知")
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    return {
        "module": "premium_analysis",
        "title": "📊 溢价率分析",
        "data": premium_data,
        "count": len(premium_data),
        "zone_distribution": zone_counts,
        "summary": (
            f"共 {len(premium_data)} 只, "
            f"折价 {zone_counts.get('折价区', 0)} / "
            f"低溢价 {zone_counts.get('低溢价', 0)} / "
            f"中溢价 {zone_counts.get('中溢价', 0)} / "
            f"高溢价 {zone_counts.get('高溢价', 0)}"
        ),
        "tip": "双低值(收盘价+溢价率*100)越低，安全边际越高。折价区存在转股套利空间。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十四：网格交易标的
# ═══════════════════════════════════════════════════════════════════════

Q_GRID_TRADING = (
    "可转债 日内振幅 换手率 成交额 收盘价 涨跌幅 "
    "可转债代码 可转债简称 流通规模 转股溢价率 "
    "按日内振幅从大到小排序 取前20名"
)


def module_grid_trading(api_key: str, timeout: int) -> dict:
    """网格交易标的：高波动率、活跃成交的可转债。"""
    queries = [Q_GRID_TRADING]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    grid_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            amplitude = _safe_float(row.get("日内振幅"))
            turnover = _safe_float(row.get("换手率"))
            volume = _safe_float(row.get("成交额"))
            price = _safe_float(row.get("收盘价"))

            row["_amplitude"] = amplitude
            row["_turnover"] = turnover
            row["_grid_suitability"] = (
                "优质网格" if amplitude > 5 and turnover > 10 and volume > 1
                else "适合网格" if amplitude > 3 and turnover > 5
                else "一般"
            )
            grid_data.append(row)

    grid_data.sort(key=lambda x: x.get("_amplitude", 0), reverse=True)

    return {
        "module": "grid_trading",
        "title": "📐 网格交易标的",
        "data": grid_data,
        "count": len(grid_data),
        "high_quality_count": sum(1 for d in grid_data if d.get("_grid_suitability") == "优质网格"),
        "summary": (
            f"高波动标的 {len(grid_data)} 只, "
            f"优质网格 {sum(1 for d in grid_data if d.get('_grid_suitability') == '优质网格')} 只"
        ),
        "tip": "网格交易适合日内振幅大、换手率高、成交活跃的标的。注意控制单只仓位。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十五：妖债监控
# ═══════════════════════════════════════════════════════════════════════

Q_MONSTER_BOND = (
    "涨跌幅大于3%的可转债 涨跌幅 换手率 成交额 收盘价 "
    "可转债代码 可转债简称 流通规模 转股溢价率 "
    "按换手率从高到低排序 取前20名"
)


def module_monster_bond(api_key: str, timeout: int) -> dict:
    """妖债监控：异常涨跌幅、超高换手率的投机标的。"""
    queries = [Q_MONSTER_BOND]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    monster_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            change = _safe_float(row.get("涨跌幅"))
            turnover = _safe_float(row.get("换手率"))
            volume = _safe_float(row.get("成交额"))
            scale = _safe_float(row.get("流通规模"))

            row["_change"] = change
            row["_turnover"] = turnover
            row["_monster_level"] = (
                "高度异常" if turnover > 100 or abs(change) > 10
                else "中度异常" if turnover > 50 or abs(change) > 5
                else "轻度异动"
            )
            monster_data.append(row)

    monster_data.sort(key=lambda x: x.get("_turnover", 0), reverse=True)

    return {
        "module": "monster_bond",
        "title": "👹 妖债监控",
        "data": monster_data,
        "count": len(monster_data),
        "high_abnormal_count": sum(1 for d in monster_data if d.get("_monster_level") == "高度异常"),
        "summary": (
            f"异动标的 {len(monster_data)} 只, "
            f"高度异常 {sum(1 for d in monster_data if d.get('_monster_level') == '高度异常')} 只"
        ),
        "tip": "妖债通常伴随小盘、高换手、高溢价率。追涨风险极大，适合观察不宜重仓。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 模块十六：套利机会
# ═══════════════════════════════════════════════════════════════════════

Q_ARBITRAGE = (
    "转股溢价率小于0的可转债 转股溢价率 转股价值 收盘价 "
    "可转债代码 可转债简称 成交额 换手率 剩余期限 "
    "按转股溢价率从低到高排序 取前20名"
)


def module_arbitrage(api_key: str, timeout: int) -> dict:
    """套利机会：转股折价标的的套利空间。"""
    queries = [Q_ARBITRAGE]
    query_results = _query_with_retry(queries, api_key, timeout, "20")

    arb_data = []
    for qr in query_results:
        for row in qr.get("datas", []):
            conv_premium = _safe_float(row.get("转股溢价率"))
            conv_value = _safe_float(row.get("转股价值"))
            cb_price = _safe_float(row.get("收盘价"))

            # 套利空间 = 转股价值 - 转债价格 (每张)
            arb_spread = conv_value - cb_price if conv_value > 0 and cb_price > 0 else 0
            arb_spread_pct = (arb_spread / cb_price * 100) if cb_price > 0 else 0

            row["_conv_premium"] = conv_premium
            row["_arb_spread"] = round(arb_spread, 2)
            row["_arb_spread_pct"] = round(arb_spread_pct, 2)
            row["_arb_feasibility"] = (
                "可执行" if arb_spread_pct > 1 and _safe_float(row.get("成交额")) > 0.5
                else "需观察" if arb_spread_pct > 0.5
                else "空间不足"
            )
            arb_data.append(row)

    arb_data.sort(key=lambda x: x.get("_arb_spread_pct", 0), reverse=True)

    return {
        "module": "arbitrage",
        "title": "🔄 套利机会",
        "data": arb_data,
        "count": len(arb_data),
        "executable_count": sum(1 for d in arb_data if d.get("_arb_feasibility") == "可执行"),
        "summary": (
            f"折价标的 {len(arb_data)} 只, "
            f"可执行套利 {sum(1 for d in arb_data if d.get('_arb_feasibility') == '可执行')} 只"
        ),
        "tip": "转股折价时买入转债并转股可获得套利。需考虑转股T+1和交易摩擦成本。",
    }


# ═══════════════════════════════════════════════════════════════════════
# 全景看板模式
# ═══════════════════════════════════════════════════════════════════════

def module_dashboard(api_key: str, timeout: int) -> dict:
    """全景看板：依次执行所有模块查询。"""
    dashboard = {
        "mode": "dashboard",
        "title": "📋 可转债全景数据看板",
        "modules": {},
    }

    module_funcs = [
        ("forced_redeem", module_forced_redeem),
        ("downrev_count", module_downrev_count),
        ("small_scale", module_small_scale),
        ("limit_stock", module_limit_stock),
        ("dragon_tiger", module_dragon_tiger),
        ("issuance", module_issuance),
        ("top10", module_top10),
        ("bond_cushion", module_bond_cushion),
        ("rights_recovery", module_rights_recovery),
        ("time_option", module_time_option),
        ("hard_redeem", module_hard_redeem),
        ("maturity_price", module_maturity_price),
        ("premium_analysis", module_premium_analysis),
        ("grid_trading", module_grid_trading),
        ("monster_bond", module_monster_bond),
        ("arbitrage", module_arbitrage),
    ]

    for mod_name, func in module_funcs:
        try:
            result = func(api_key, timeout)
            dashboard["modules"][mod_name] = result
        except Exception as e:
            dashboard["modules"][mod_name] = {
                "module": mod_name,
                "status": "ERROR",
                "error": str(e),
            }

    # 生成全景摘要
    summaries = []
    for mod_name, mod_data in dashboard["modules"].items():
        title = mod_data.get("title", mod_name)
        summary = mod_data.get("summary", "")
        if not summary:
            count = 0
            data = mod_data.get("data", {})
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, dict):
                        count += v.get("count", len(v.get("datas", [])))
            summary = f"共 {count} 条数据"
        summaries.append(f"{title}: {summary}")

    dashboard["overview"] = summaries
    return dashboard


# ═══════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════

MODE_MAP = {
    "dashboard": ("全景看板", module_dashboard),
    "forced-redeem": ("强赎时间表", module_forced_redeem),
    "downrev-count": ("下修天计数", module_downrev_count),
    "small-scale": ("最小流通规模", module_small_scale),
    "limit-stock": ("正股涨跌停", module_limit_stock),
    "dragon-tiger": ("龙虎榜", module_dragon_tiger),
    "issuance": ("发行进度", module_issuance),
    "top10": ("TOP10排行榜", module_top10),
    "bond-cushion": ("配债安全垫", module_bond_cushion),
    "rights-recovery": ("配债填权", module_rights_recovery),
    "time-option": ("时间期权价值", module_time_option),
    "hard-redeem": ("刚兑标的", module_hard_redeem),
    "maturity-price": ("到期赎回价对比", module_maturity_price),
    "premium-analysis": ("溢价率分析", module_premium_analysis),
    "grid-trading": ("网格交易标的", module_grid_trading),
    "monster-bond": ("妖债监控", module_monster_bond),
    "arbitrage": ("套利机会", module_arbitrage),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="可转债全景数据看板 — hithink-cb-dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 全景看板
  python3 scripts/cli.py --mode dashboard

  # 单模块
  python3 scripts/cli.py --mode forced-redeem
  python3 scripts/cli.py --mode downrev-count
  python3 scripts/cli.py --mode small-scale
  python3 scripts/cli.py --mode limit-stock
  python3 scripts/cli.py --mode dragon-tiger
  python3 scripts/cli.py --mode issuance
  python3 scripts/cli.py --mode top10

环境变量:
  IWENCAI_API_KEY    API 密钥（必填，也可通过 --api-key 传入）
        """
    )

    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=list(MODE_MAP.keys()),
        required=True,
        help="查询模式"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API 密钥（默认从环境变量 IWENCAI_API_KEY 读取）"
    )
    parser.add_argument(
        "--call-type",
        type=str,
        choices=["normal", "retry"],
        default="normal",
        help="调用类型（默认: normal）"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"请求超时时间（秒，默认: {DEFAULT_TIMEOUT}）"
    )
    parser.add_argument(
        "--limit",
        type=str,
        default=DEFAULT_LIMIT,
        help=f"每页条数（默认: {DEFAULT_LIMIT}）"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = _api_key(args.api_key)

    try:
        _, func = MODE_MAP[args.mode]
        result = func(api_key, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except CBDashboardAPIError as e:
        err_out = {"error": e.message}
        if e.status_code:
            err_out["status_code"] = e.status_code
        if e.response:
            err_out["response"] = e.response
        print(json.dumps(err_out, ensure_ascii=False, indent=2))
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n操作已取消。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(json.dumps({"error": f"发生错误: {str(e)}"}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
