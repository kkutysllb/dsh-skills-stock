#!/usr/bin/env python3
"""
可转债多维度分析 CLI — hithink-cb-analyzer

支持两种模式：
  single  — 单只可转债六维度深度分析
  compare — 多只可转债批量横向对比

数据源：同花顺问财 (iwencai) OpenAPI
严格遵循 X-Claw-* Header 规范，使用 Python3 标准库，无第三方依赖。
"""

import argparse
import json
import math
import os
import secrets
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


# ─── 常量 ────────────────────────────────────────────────────────────
SKILL_NAME = "hithink-cb-analyzer"
SKILL_VERSION = "1.0.0"
DEFAULT_API_URL = "https://openapi.iwencai.com/v1/query2data"
DEFAULT_TIMEOUT = 30


# ─── 异常 ────────────────────────────────────────────────────────────
class CBAnalyzerAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


# ─── 通用 API 层 ─────────────────────────────────────────────────────
def _trace_id() -> str:
    return secrets.token_hex(32)


def _api_key(cli_key: Optional[str] = None) -> str:
    key = cli_key or os.environ.get("IWENCAI_API_KEY", "")
    if not key:
        raise CBAnalyzerAPIError(
            "API 密钥未设置。请通过 --api-key 或环境变量 IWENCAI_API_KEY 指定。"
        )
    return key


def _headers(api_key: str, trace_id: str, call_type: str = "normal") -> dict:
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
) -> dict:
    """调用问财 API，返回解析后的 dict。"""
    tid = _trace_id()
    payload = {
        "query": query_str,
        "page": "1",
        "limit": "10",
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
                return {"text_response": "", "trace_id": tid}
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    parsed["trace_id"] = tid
                    return parsed
                return {"data": parsed, "trace_id": tid}
            except json.JSONDecodeError:
                return {"text_response": body, "trace_id": tid}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        raise CBAnalyzerAPIError(
            f"HTTP {e.code}: {e.reason}", status_code=e.code, response=err_body
        )
    except urllib.error.URLError as e:
        raise CBAnalyzerAPIError(f"网络错误: {e.reason}")


def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全转为 float。"""
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


def _find_row(datas: List[dict], bond_name: str) -> Optional[dict]:
    """在 datas 中按名称/代码模糊匹配行。"""
    if not datas:
        return None
    for row in datas:
        for v in row.values():
            if bond_name in str(v):
                return row
    return None


# ─── 查询构造器 ──────────────────────────────────────────────────────
QUERIES_SINGLE = {
    "basic": lambda b: (
        f"{b}可转债 转股溢价率 转股价值 纯债价值 纯债溢价率 "
        f"到期收益率 剩余期限 收盘价 转股溢价 双低值"
    ),
    "stock": lambda b: (
        f"{b}正股 涨跌幅 PE PB 市值 所属行业 板块"
    ),
    "bond_protection": lambda b: (
        f"{b}可转债 信用评级 回售起始日 下修触发条件 "
        f"到期赎回价 票面利率 利率类型"
    ),
    "capital": lambda b: (
        f"{b}可转债 成交额 换手率 成交额变化 涨跌幅 成交量"
    ),
}

QUERIES_COMPARE = lambda bonds: (
    f"{', '.join(bonds)}可转债 转股溢价率 转股价值 纯债价值 "
    f"纯债溢价率 到期收益率 剩余期限 收盘价 信用评级 "
    f"成交额 换手率 涨跌幅 正股涨跌幅"
)


# ─── 评分引擎 ────────────────────────────────────────────────────────
def _score_basic(row: dict) -> Tuple[float, dict]:
    """基本指标评分 (0-100)，权重占综合 25%。"""
    premium = _safe_float(row.get("转股溢价率", row.get("转股溢价率[20260508]")))
    ytm = _safe_float(row.get("到期收益率", row.get("到期收益率[20260508]")))

    # 转股溢价率评分：越低越好
    if premium < 0:
        s_prem = 100
    elif premium < 10:
        s_prem = 90 + (10 - premium)
    elif premium < 20:
        s_prem = 70 + (20 - premium) * 2
    elif premium < 40:
        s_prem = 40 + (40 - premium)
    else:
        s_prem = max(0, 40 - (premium - 40))

    # 到期收益率评分
    if ytm > 5:
        s_ytm = 100
    elif ytm > 0:
        s_ytm = 70 + ytm * 6
    elif ytm > -10:
        s_ytm = 60 + ytm * 3
    else:
        s_ytm = max(0, 30 + ytm)

    score = s_prem * 0.7 + s_ytm * 0.3
    details = {"转股溢价率评分": round(s_prem, 1), "到期收益率评分": round(s_ytm, 1)}
    return round(score, 1), details


def _score_stock(row: dict) -> Tuple[float, dict]:
    """正股联动评分 (0-100)，权重占综合 20%。"""
    pe = _safe_float(row.get("PE", row.get("市盈率")))
    pb = _safe_float(row.get("PB", row.get("市净率")))
    chg = _safe_float(row.get("涨跌幅", row.get("正股涨跌幅", row.get("正股涨跌幅[20260508]"))))

    # PE 评分：10-30 合理
    if 10 <= pe <= 30:
        s_pe = 85
    elif 0 < pe < 10:
        s_pe = 75
    elif 30 < pe <= 50:
        s_pe = 60
    elif pe > 50:
        s_pe = max(20, 60 - (pe - 50))
    else:
        s_pe = 50  # PE 未知或负值

    # PB 评分
    if 0.5 <= pb <= 3:
        s_pb = 80
    elif 0 < pb < 0.5:
        s_pb = 60
    elif pb > 3:
        s_pb = max(30, 60 - (pb - 3) * 5)
    else:
        s_pb = 50

    # 正股涨跌幅
    if chg > 5:
        s_chg = 90
    elif chg > 0:
        s_chg = 70 + chg * 4
    elif chg > -5:
        s_chg = 50 + chg * 4
    else:
        s_chg = max(20, 50 + chg * 3)

    score = s_pe * 0.35 + s_pb * 0.25 + s_chg * 0.40
    details = {"PE评分": round(s_pe, 1), "PB评分": round(s_pb, 1), "正股涨跌评分": round(s_chg, 1)}
    return round(score, 1), details


def _score_protection(row: dict) -> Tuple[float, dict]:
    """债底保护评分 (0-100)，权重占综合 20%。"""
    rating = _safe_str(row.get("信用评级", row.get("债券评级")))
    has_downrev = "有" if _safe_str(row.get("下修触发条件")) != "-" else "无"
    redeem = _safe_float(row.get("到期赎回价", row.get("赎回价")))

    # 信用评级评分
    rating_scores = {"AAA": 100, "AA+": 90, "AA": 80, "AA-": 70, "A+": 55, "A": 45}
    s_rating = rating_scores.get(rating, 50)

    # 下修条款加分
    s_downrev = 90 if has_downrev == "有" else 50

    # 赎回价评分
    if redeem >= 110:
        s_redeem = 80
    elif redeem >= 105:
        s_redeem = 65
    elif redeem > 0:
        s_redeem = 50
    else:
        s_redeem = 50

    score = s_rating * 0.50 + s_downrev * 0.30 + s_redeem * 0.20
    details = {"信用评级评分": round(s_rating, 1), "下修条款评分": round(s_downrev, 1),
               "赎回价评分": round(s_redeem, 1), "信用评级": rating, "有下修条款": has_downrev}
    return round(score, 1), details


def _score_time(row: dict) -> Tuple[float, dict]:
    """时间价值评分 (0-100)，权重占综合 10%。"""
    years = _safe_float(row.get("剩余期限年数", row.get("剩余期限", row.get("剩余期限[20260508]"))))

    # 剩余期限：1-3 年最优
    if 1.0 <= years <= 3.0:
        s_time = 90
    elif 0.5 <= years < 1.0:
        s_time = 70
    elif 3.0 < years <= 5.0:
        s_time = 70 - (years - 3.0) * 10
    elif years > 5.0:
        s_time = max(30, 50 - (years - 5.0) * 5)
    elif 0 < years < 0.5:
        s_time = 50 + years * 40
    else:
        s_time = 50

    details = {"剩余期限(年)": round(years, 2), "时间价值评分": round(s_time, 1)}
    return round(s_time, 1), details


def _score_capital(row: dict) -> Tuple[float, dict]:
    """资金面评分 (0-100)，权重占综合 15%。"""
    amount = _safe_float(row.get("成交额", row.get("成交额[20260508]")))
    turnover = _safe_float(row.get("换手率", row.get("换手率[20260508]")))

    # 成交额：活跃但不过热
    if amount > 5e8:
        s_amount = 75
    elif amount > 1e8:
        s_amount = 85
    elif amount > 5e7:
        s_amount = 70
    elif amount > 0:
        s_amount = 60
    else:
        s_amount = 50

    # 换手率
    if 5 <= turnover <= 30:
        s_turnover = 80
    elif turnover > 30:
        s_turnover = max(40, 80 - (turnover - 30) * 2)
    elif turnover > 0:
        s_turnover = 50 + turnover * 2
    else:
        s_turnover = 50

    score = s_amount * 0.5 + s_turnover * 0.5
    details = {"成交额活跃度评分": round(s_amount, 1), "换手率评分": round(s_turnover, 1)}
    return round(score, 1), details


def _score_arbitrage(row: dict) -> Tuple[float, dict]:
    """套利信号评分 (0-100)，权重占综合 10%。"""
    premium = _safe_float(row.get("转股溢价率", row.get("转股溢价率[20260508]")))
    dl_val = _safe_float(row.get("双低值"))

    # 转股套利空间
    if premium < 0:
        s_arb = 100  # 折价
    elif premium < 5:
        s_arb = 90
    elif premium < 15:
        s_arb = 70 + (15 - premium) * 2
    elif premium < 30:
        s_arb = 50 + (30 - premium)
    else:
        s_arb = max(20, 50 - (premium - 30))

    # 双低值加分
    if dl_val > 0 and dl_val < 130:
        s_dl = 85
    elif dl_val > 0 and dl_val < 150:
        s_dl = 70
    elif dl_val > 0:
        s_dl = max(30, 70 - (dl_val - 150) * 0.5)
    else:
        s_dl = 50

    score = s_arb * 0.7 + s_dl * 0.3
    details = {"转股套利评分": round(s_arb, 1), "双低值评分": round(s_dl, 1)}
    return round(score, 1), details


def compute_composite(basic_row: dict, stock_row: dict, protect_row: dict,
                      time_row: dict, capital_row: dict) -> dict:
    """计算综合评分与各维度评分。"""
    s_basic, d_basic = _score_basic(basic_row)
    s_stock, d_stock = _score_stock(stock_row)
    s_prot, d_prot = _score_protection(protect_row)
    s_time, d_time = _score_time(time_row)
    s_cap, d_cap = _score_capital(capital_row)

    # 套利信号复用 basic_row
    s_arb, d_arb = _score_arbitrage(basic_row)

    composite = (
        s_basic * 0.25 + s_stock * 0.20 + s_prot * 0.20
        + s_time * 0.10 + s_cap * 0.15 + s_arb * 0.10
    )

    # 投资建议
    if composite >= 80:
        advice = "⭐ 强烈推荐"
    elif composite >= 65:
        advice = "✅ 推荐"
    elif composite >= 50:
        advice = "⚠️ 观望"
    else:
        advice = "❌ 回避"

    return {
        "综合评分": round(composite, 1),
        "投资建议": advice,
        "各维度评分": {
            "📊 基本指标(25%)": {"得分": s_basic, "详情": d_basic},
            "📈 正股联动(20%)": {"得分": s_stock, "详情": d_stock},
            "🛡️ 债底保护(20%)": {"得分": s_prot, "详情": d_prot},
            "⏰ 时间价值(10%)": {"得分": s_time, "详情": d_time},
            "💰 资金面(15%)": {"得分": s_cap, "详情": d_cap},
            "📉 套利信号(10%)": {"得分": s_arb, "详情": d_arb},
        },
    }


# ─── 分析模式 ────────────────────────────────────────────────────────
def analyze_single(bond: str, api_key: str, call_type: str = "normal",
                   timeout: int = DEFAULT_TIMEOUT) -> dict:
    """单只可转债六维度深度分析。"""
    results = {}
    raw_data = {}

    for dim, query_fn in QUERIES_SINGLE.items():
        q = query_fn(bond)
        try:
            resp = _query(q, api_key, call_type, timeout)
            datas = resp.get("datas", [])
            row = _find_row(datas, bond) if datas else None
            if row:
                results[dim] = row
                raw_data[dim] = {"query": q, "status": "OK", "data_count": len(datas)}
            else:
                results[dim] = {}
                raw_data[dim] = {"query": q, "status": "EMPTY", "data_count": 0}
        except CBAnalyzerAPIError as e:
            results[dim] = {}
            raw_data[dim] = {"query": q, "status": "ERROR", "error": e.message}

    # 计算综合评分
    scores = compute_composite(
        results.get("basic", {}),
        results.get("stock", {}),
        results.get("bond_protection", {}),
        results.get("basic", {}),  # 时间价值字段在 basic 查询中
        results.get("capital", {}),
    )

    return {
        "mode": "single",
        "bond": bond,
        "综合评分": scores["综合评分"],
        "投资建议": scores["投资建议"],
        "各维度评分": scores["各维度评分"],
        "维度数据": {
            "📊 基本指标": results.get("basic", {}),
            "📈 正股联动": results.get("stock", {}),
            "🛡️ 债底保护": results.get("bond_protection", {}),
            "💰 资金面": results.get("capital", {}),
        },
        "查询日志": raw_data,
    }


def analyze_compare(bonds: List[str], api_key: str, call_type: str = "normal",
                    timeout: int = DEFAULT_TIMEOUT) -> dict:
    """多只可转债批量横向对比。"""
    # Step 1: 综合查询获取核心指标
    q_all = QUERIES_COMPARE(bonds)
    try:
        resp = _query(q_all, api_key, call_type, timeout)
        all_datas = resp.get("datas", [])
    except CBAnalyzerAPIError as e:
        return {"mode": "compare", "error": e.message, "bonds": bonds}

    # Step 2: 为每只可转债匹配数据行
    bond_results = {}
    for bond in bonds:
        row = _find_row(all_datas, bond)
        if row:
            bond_results[bond] = row
        else:
            bond_results[bond] = None

    # Step 3: 补充查询 — 正股数据
    for bond in bonds:
        if bond_results[bond] is None:
            # 尝试单独查询
            q = QUERIES_SINGLE["basic"](bond)
            try:
                resp2 = _query(q, api_key, call_type, timeout)
                row = _find_row(resp2.get("datas", []), bond)
                bond_results[bond] = row
            except CBAnalyzerAPIError:
                bond_results[bond] = None

    # Step 4: 计算每只的综合评分
    comparison = []
    for bond, row in bond_results.items():
        if row is None:
            comparison.append({
                "可转债": bond, "状态": "未找到数据", "综合评分": 0, "投资建议": "❌ 无数据"
            })
            continue

        scores = compute_composite(row, row, row, row, row)
        comparison.append({
            "可转债": bond,
            "证券代码": _safe_str(row.get("证券代码")),
            "收盘价": _safe_str(row.get("收盘价")),
            "转股溢价率": _safe_float(row.get("转股溢价率", row.get("转股溢价率[20260508]"))),
            "到期收益率": _safe_float(row.get("到期收益率", row.get("到期收益率[20260508]"))),
            "纯债价值": _safe_float(row.get("纯债价值", row.get("纯债价值[20260508]"))),
            "剩余期限": _safe_float(row.get("剩余期限年数", row.get("剩余期限[20260508]"))),
            "信用评级": _safe_str(row.get("信用评级")),
            "成交额": _safe_str(row.get("成交额")),
            "涨跌幅": _safe_float(row.get("涨跌幅")),
            "综合评分": scores["综合评分"],
            "投资建议": scores["投资建议"],
            "各维度得分": {
                k: v["得分"] for k, v in scores["各维度评分"].items()
            },
        })

    # Step 5: 按综合评分排序
    comparison.sort(key=lambda x: x.get("综合评分", 0), reverse=True)

    # Step 6: 标注各维度冠军
    valid = [c for c in comparison if c.get("综合评分", 0) > 0]
    champions = {}
    if valid:
        champions["综合评分最高"] = valid[0]["可转债"]
        # 溢价率最低
        premium_sorted = sorted(valid, key=lambda x: x.get("转股溢价率", 999))
        champions["转股溢价率最低"] = premium_sorted[0]["可转债"]
        # 到期收益率最高
        ytm_sorted = sorted(valid, key=lambda x: x.get("到期收益率", -999), reverse=True)
        champions["到期收益率最高"] = ytm_sorted[0]["可转债"]

    return {
        "mode": "compare",
        "对比数量": len(bonds),
        "有效数据": len(valid),
        "对比结果": comparison,
        "各维度冠军": champions,
        "推荐标的": valid[0]["可转债"] if valid else "无",
    }


# ─── CLI 入口 ────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="可转债多维度分析工具 — hithink-cb-analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单只可转债深度分析
  python3 scripts/cli.py --mode single --bonds "精达转债"

  # 批量横向对比
  python3 scripts/cli.py --mode compare --bonds "精达转债,立讯转债,天业转债"

  # 指定 API 密钥
  python3 scripts/cli.py --mode single --bonds "110074.SH" --api-key "your-key"

环境变量:
  IWENCAI_API_KEY    API 密钥（必填，也可通过 --api-key 传入）
        """
    )

    parser.add_argument("--mode", "-m", type=str, choices=["single", "compare"],
                        required=True, help="分析模式: single 或 compare")
    parser.add_argument("--bonds", "-b", type=str, required=True,
                        help="可转债名称或代码，多个用英文逗号分隔")
    parser.add_argument("--api-key", type=str, default=None,
                        help="API 密钥（默认从环境变量读取）")
    parser.add_argument("--call-type", type=str, choices=["normal", "retry"],
                        default="normal", help="调用类型（默认: normal）")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"请求超时时间（秒，默认: {DEFAULT_TIMEOUT}）")
    return parser.parse_args()


def main():
    args = parse_args()
    api_key = _api_key(args.api_key)
    bonds = [b.strip() for b in args.bonds.split(",") if b.strip()]

    try:
        if args.mode == "single":
            if len(bonds) != 1:
                print(json.dumps({
                    "error": "single 模式仅支持单只可转债，请传入 1 个名称或代码"
                }, ensure_ascii=False, indent=2))
                sys.exit(1)
            result = analyze_single(bonds[0], api_key, args.call_type, args.timeout)
        else:
            if len(bonds) < 2:
                print(json.dumps({
                    "error": "compare 模式需要至少 2 只可转债进行对比"
                }, ensure_ascii=False, indent=2))
                sys.exit(1)
            result = analyze_compare(bonds, api_key, args.call_type, args.timeout)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    except CBAnalyzerAPIError as e:
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
