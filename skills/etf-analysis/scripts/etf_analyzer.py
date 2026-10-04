#!/usr/bin/env python3
"""
ETF Analyzer v2 — 基于 Tushare Pro 的 ETF 全维度分析工具
覆盖：列表查询、日行情、净值、份额变化、规模、跟踪指数、四类ETF分类、筛选对比等

用法:
  python cli.py list --params key=value ...     # ETF列表（含分类标签）
  python cli.py daily --params ts_code=...      # 日行情
  python cli.py nav --params ts_code=...        # 净值数据
  python cli.py shares --params ts_code=...     # 份额变化
  python cli.py scale --params ts_code=...      # 规模分析
  python cli.py compare --params ts_codes=...   # 横向对比
  python cli.py screen --params type=wide ...   # 分类筛选
  python cli.py sector --params sector=...      # 行业ETF
  python cli.py index --params ts_code=...      # 跟踪指数分析
  python cli.py classify                       # 四类ETF分类概览
  python cli.py portfolio --params ts_code=...  # 持仓数据
  python cli.py managers --params ts_code=...   # 基金经理
  python cli.py dividends --params ts_code=...  # 分红记录
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta

TOKEN = os.environ.get("TUSHARE_TOKEN", "")
if not TOKEN:
    print(json.dumps({"error": "TUSHARE_TOKEN 环境变量未设置"}))
    sys.exit(1)

from kk_common import get_finance_data_gateway
pro = get_finance_data_gateway()

# ──────────────────────────────────────────────
# ETF 分类常量
# ──────────────────────────────────────────────
WIDE_BASE_KEYWORDS = [
    "沪深300", "中证500", "中证1000", "中证800", "中证2000", "中证A50", "中证A500",
    "上证50", "上证180", "上证380", "上证指数",
    "创业板指", "创业板50", "科创50", "科创100", "科创A50",
    "深证成指", "深证100", "深证成指",
    "北证50", "北证",
    "MSCI", "msci", "纳斯达克", "标普500", "标普",
    "恒生指数", "恒生国企", "恒生科技", "H股", "港股通",
    "股息", "价值", "成长", "质量", "低波动", "红利",
]
CROSS_BORDER_KEYWORDS = [
    "纳斯达克", "纳指", "标普", "道琼斯", "恒生", "恒指", "日经",
    "德国", "法国", "英国", "越南", "印度", "韩国", "日本", "美国",
    "港股", "中概", "互联", "中韩", "东南亚", "全球",
    "MSCI", "msci", "QDII", "qdii", "H股", "港股通",
    "恒生科技", "恒生互联网", "中美", "中美互联网",
    "港元", "汇率", "估值汇率", "折算",
]
COMMODITY_TYPES = ["黄金现货合约", "商品型", "能源化工期货型", "有色金属期货型",
                    "豆粕期货型", "白银期货型", "原油主题基金", "原油期货型"]
MONEY_TYPES = ["货币型", "货币市场型"]


def get_latest_trade_date():
    trade_date = datetime.now().strftime("%Y%m%d")
    for _ in range(15):
        try:
            cal = pro.trade_cal(exchange="SSE", trade_date=trade_date, is_open="1")
            if not cal.empty: return trade_date
        except: pass
        trade_date = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    return trade_date


def classify_etf_type(name, benchmark, invest_type):
    bm = str(benchmark or "") + str(name or "")
    if invest_type in MONEY_TYPES: return "货币ETF"
    if invest_type in COMMODITY_TYPES or any(k in bm for k in ["黄金","原油","豆粕","白银","期货","商品","能源"]):
        return "商品ETF"
    # 跨境ETF判断（排除纯宽基）
    is_wide = any(k in bm for k in WIDE_BASE_KEYWORDS)
    is_cross = any(k in bm for k in CROSS_BORDER_KEYWORDS)
    if is_cross and not is_wide: return "跨境ETF"
    if is_wide: return "宽基ETF"
    return "行业/主题ETF"


class ETFAnalyzer:

    def list_etfs(self, market=None, invest_type=None, status="L",
                   start_date=None, end_date=None, limit=100):
        params = {"market": market or "E", "status": status}
        if invest_type: params["invest_type"] = invest_type
        try:
            df = pro.fund_basic(**params)
        except Exception as e:
            return {"error": str(e)}
        records = df.to_dict(orient="records")
        if start_date:
            records = [r for r in records if str(r.get("list_date","0")) >= start_date.replace("-","")]
        if end_date:
            records = [r for r in records if str(r.get("list_date","99999999")) <= end_date.replace("-","")]
        for r in records:
            for k in ["found_date","list_date","issue_date","delist_date","due_date"]:
                if k in r and r[k]:
                    try:
                        d = str(r[k])
                        if len(d) == 8: r[k] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                    except: pass
            r["etf_type"] = classify_etf_type(r.get("name",""), r.get("benchmark",""), r.get("invest_type",""))
        return {"data": records[:limit], "total": len(records), "count": min(limit, len(records))}

    def daily_quote(self, ts_code, start_date=None, end_date=None, limit=120):
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date.replace("-","")
        if end_date: params["end_date"] = end_date.replace("-","")
        try:
            df = pro.fund_daily(**params)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无行情数据: {ts_code}"}
        df = df.sort_values("trade_date")
        records = df.tail(limit).to_dict(orient="records")
        for r in records:
            if "trade_date" in r and r["trade_date"]:
                try:
                    d = str(r["trade_date"])
                    r["trade_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                except: pass
        return {"data": records, "count": len(records)}

    def nav_history(self, ts_code, start_date=None, end_date=None, limit=120):
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date.replace("-","")
        if end_date: params["end_date"] = end_date.replace("-","")
        try:
            df = pro.fund_nav(**params)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无净值数据: {ts_code}"}
        df = df.sort_values("nav_date")
        records = df.tail(limit).to_dict(orient="records")
        for r in records:
            for k in ["nav_date","ann_date"]:
                if k in r and r[k]:
                    try:
                        d = str(r[k])
                        r[k] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                    except: pass
        return {"data": records, "count": len(records)}

    def share_changes(self, ts_code, start_date=None, end_date=None, limit=60):
        """获取ETF份额变化（单位：亿份）"""
        params = {"ts_code": ts_code}
        if start_date: params["start_date"] = start_date.replace("-","")
        if end_date: params["end_date"] = end_date.replace("-","")
        try:
            df = pro.fund_share(**params)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无份额数据: {ts_code}"}
        df = df.sort_values("trade_date")
        records = df.tail(limit).to_dict(orient="records")
        for r in records:
            if "trade_date" in r and r["trade_date"]:
                try:
                    d = str(r["trade_date"])
                    r["trade_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                except: pass
            if "fd_share" in r and r["fd_share"] is not None:
                # fd_share unit is 万份 → convert to 亿份 by /1e4
                r["fd_share_yi"] = round(r["fd_share"] / 1e4, 4)
        if len(records) >= 2:
            records.reverse()
            for i in range(1, len(records)):
                prev = records[i-1].get("fd_share", 0) or 0
                curr = records[i].get("fd_share", 0) or 0
                if prev and prev != 0:
                    records[i]["share_change_pct"] = round((curr - prev) / prev * 100, 4)
                    # fd_share diff is in 万份 → convert to 亿份 by /1e4
                    records[i]["share_change_abs"] = round((curr - prev) / 1e4, 4)
            records.reverse()
        return {"data": records, "count": len(records)}

    def get_scale(self, ts_code, trade_date=None):
        """规模分析：30日日均成交额 + 最新份额 + 估算规模"""
        end = trade_date or get_latest_trade_date()
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
        try:
            df = pro.fund_daily(ts_code=ts_code, start_date=start, end_date=end)
            df_share = pro.fund_share(ts_code=ts_code, trade_date=end)
            nav_df = pro.fund_nav(ts_code=ts_code)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无行情数据: {ts_code}"}
        # Unit contracts (verified against Tushare official docs + ground truth):
        #   fund_daily.amount         → 千元  (convert to 亿元: / 1e5)
        #   fund_share.fd_share       → 万份  (convert to 亿份: / 1e4)
        avg_amount = df["amount"].mean()
        latest = df.sort_values("trade_date", ascending=False).iloc[0]
        share_latest = None
        if df_share is not None and not df_share.empty:
            share_latest = round(df_share.iloc[0].get("fd_share", 0) / 1e4, 4)
        nav_latest = {}
        scale_est = None
        if nav_df is not None and not nav_df.empty:
            nav_latest = nav_df.sort_values("nav_date", ascending=False).iloc[0]
        price = latest["close"]
        nav_val = nav_latest.get("unit_nav", price) if nav_latest else price
        if nav_val and nav_val > 0 and share_latest:
            # scale_est: 净值(元) × 亿份 = 亿元
            scale_est = round(nav_val * share_latest, 2)
        return {
            "ts_code": ts_code,
            "trade_date": str(latest["trade_date"]),
            "latest_price": latest["close"],
            "pct_chg": latest["pct_chg"],
            "amount_yi": round(latest["amount"] / 1e5, 4),
            "avg_daily_amount_30d_yi": round(avg_amount / 1e5, 4),
            "latest_share_yi": share_latest,
            "estimated_scale_yi": scale_est,
            "unit_nav": nav_latest.get("unit_nav") if nav_latest else None,
        }

    def compare(self, ts_codes):
        trade_date = get_latest_trade_date()
        start_20 = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
        start_60 = (datetime.strptime(trade_date, "%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")
        results = []
        for code in ts_codes:
            try:
                daily = pro.fund_daily(ts_code=code, trade_date=trade_date)
                fund = pro.fund_basic(ts_code=code)
                nav_df = pro.fund_nav(ts_code=code)
                share_df = pro.fund_share(ts_code=code, trade_date=trade_date)
                df_20 = pro.fund_daily(ts_code=code, start_date=start_20, end_date=trade_date)
                df_60 = pro.fund_daily(ts_code=code, start_date=start_60, end_date=trade_date)
                nav_latest = nav_df.sort_values("nav_date", ascending=False).iloc[0] if nav_df is not None and not nav_df.empty else {}
                d = daily.iloc[0] if daily is not None and not daily.empty else {}
                f = fund.iloc[0] if fund is not None and not fund.empty else {}
                ret_20d = None
                ret_60d = None
                if df_20 is not None and not df_20.empty and len(df_20) >= 2:
                    ret_20d = round((df_20.iloc[-1]["close"] / df_20.iloc[0]["close"] - 1) * 100, 2)
                if df_60 is not None and not df_60.empty and len(df_60) >= 2:
                    ret_60d = round((df_60.iloc[-1]["close"] / df_60.iloc[0]["close"] - 1) * 100, 2)
                share_latest = None
                if share_df is not None and not share_df.empty:
                    # fd_share unit is 万份 → 亿份: /1e4
                    share_latest = round(share_df.iloc[0].get("fd_share", 0) / 1e4, 4)
                results.append({
                    "ts_code": code,
                    "name": f.get("name", code),
                    "etf_type": classify_etf_type(f.get("name",""), f.get("benchmark",""), f.get("invest_type","")),
                    "track_benchmark": f.get("benchmark", ""),
                    "price": d.get("close"),
                    "pct_chg": d.get("pct_chg"),
                    "amount_yi": round(d.get("amount", 0) / 1e5, 4),
                    "vol": d.get("vol"),
                    "pre_close": d.get("pre_close"),
                    "unit_nav": nav_latest.get("unit_nav"),
                    "accum_nav": nav_latest.get("accum_nav"),
                    "nav_date": str(nav_latest.get("nav_date", "")),
                    "return_20d": ret_20d,
                    "return_60d": ret_60d,
                    "latest_share_yi": share_latest,
                    "management": f.get("management", ""),
                    "m_fee": f.get("m_fee", 0),
                    "found_date": str(f.get("found_date", ""))[:10],
                })
            except Exception as e:
                results.append({"ts_code": code, "error": str(e)})
        return {"data": results, "count": len(results), "trade_date": trade_date}

    def screen(self, etf_type=None, min_scale=None, max_scale=None,
               invest_type=None, min_pct_chg=None, max_pct_chg=None,
               market="E", limit=30):
        """多条件ETF筛选，支持四类ETF分类"""
        etf_list = self.list_etfs(market=market, status="L", limit=1000)
        if "error" in etf_list:
            return etf_list
        etfs = etf_list.get("data", [])
        trade_date = get_latest_trade_date()
        results = []
        for etf in etfs:
            code = etf["ts_code"]
            if etf_type and etf.get("etf_type","") != etf_type: continue
            if invest_type and etf.get("invest_type","") != invest_type: continue
            try:
                daily = pro.fund_daily(ts_code=code, trade_date=trade_date)
                if daily is None or daily.empty: continue
                d = daily.iloc[0]
                pct_chg = d["pct_chg"]
                # fund_daily.amount is in 千元 → divide by 1e5 to get 亿元
                amount_yi = d["amount"] / 1e5 if d["amount"] else 0
                scale_est = amount_yi * 10
                if min_pct_chg is not None and pct_chg < min_pct_chg: continue
                if max_pct_chg is not None and pct_chg > max_pct_chg: continue
                if min_scale and scale_est < min_scale: continue
                if max_scale and scale_est > max_scale: continue
                results.append({
                    "ts_code": code,
                    "name": etf["name"],
                    "etf_type": etf.get("etf_type",""),
                    "track_benchmark": etf.get("benchmark", ""),
                    "invest_type": etf.get("invest_type",""),
                    "price": d["close"],
                    "pct_chg": round(pct_chg, 3),
                    "amount_yi": round(amount_yi, 4),
                    "scale_est_yi": round(scale_est, 2),
                    "management": etf.get("management", ""),
                    "found_date": str(etf.get("found_date",""))[:10],
                    "m_fee": etf.get("m_fee", ""),
                })
            except Exception: continue
            if len(results) >= limit: break
        results.sort(key=lambda x: x.get("scale_est_yi", 0), reverse=True)
        return {"data": results, "count": len(results), "trade_date": trade_date}

    def sector_etfs(self, sector_name, limit=10):
        results = []
        trade_date = get_latest_trade_date()
        etf_list = self.list_etfs(market="E", status="L", limit=1000)
        if "error" not in etf_list:
            matched = [e for e in etf_list.get("data", [])
                       if sector_name in str(e.get("name",""))
                       or sector_name in str(e.get("benchmark",""))]
            for e in matched[:limit]:
                try:
                    daily = pro.fund_daily(ts_code=e["ts_code"], trade_date=trade_date)
                    d = daily.iloc[0] if daily is not None and not daily.empty else {}
                    results.append({
                        "ts_code": e["ts_code"],
                        "name": e["name"],
                        "etf_type": e.get("etf_type",""),
                        "track_benchmark": str(e.get("benchmark",""))[:60],
                        "price": d.get("close"),
                        "pct_chg": d.get("pct_chg"),
                        "amount_yi": round(d.get("amount",0)/1e5,4) if d.get("amount") else None,
                        "management": e.get("management",""),
                    })
                except: pass
        return {"data": results, "count": len(results)}

    def index_analysis(self, ts_code):
        """跟踪指数详细分析"""
        try:
            fund = pro.fund_basic(ts_code=ts_code)
        except Exception as e:
            return {"error": str(e)}
        if fund is None or fund.empty:
            return {"error": f"未找到ETF: {ts_code}"}
        f = fund.iloc[0]
        benchmark = f.get("benchmark", "")
        name = f.get("name", "")
        etf_type = classify_etf_type(name, benchmark, f.get("invest_type",""))
        index_code = ""
        index_map = {
            "沪深300":"000300.SH","中证500":"000905.SH","中证1000":"000852.SH",
            "上证50":"000016.SH","创业板指":"399006.SZ","科创50":"000688.SH",
            "中证800":"000906.SH","上证180":"000010.SH","深证成指":"399001.SZ",
            "北证50":"899050.BJ",
        }
        for idx_name, idx_code in index_map.items():
            if idx_name in benchmark:
                index_code = idx_code
                break
        publisher = ""
        if "中证" in benchmark: publisher = "中证指数有限公司"
        elif "上证" in benchmark: publisher = "上海证券交易所"
        elif "深证" in benchmark: publisher = "深圳证券交易所"
        index_data = {}
        if index_code:
            try:
                trade_date = get_latest_trade_date()
                idx_daily = pro.index_daily(ts_code=index_code, trade_date=trade_date)
                if idx_daily is not None and not idx_daily.empty:
                    d = idx_daily.iloc[0]
                    index_data = {"index_code": index_code, "index_name": benchmark, "index_price": d.get("close"), "index_pct_chg": d.get("pct_chg")}
            except: pass
        return {
            "ts_code": ts_code, "name": name, "etf_type": etf_type,
            "track_benchmark": benchmark, "index_code": index_code,
            "publisher": publisher, "invest_type": f.get("invest_type",""),
            "management": f.get("management",""), "m_fee": f.get("m_fee",""), "c_fee": f.get("c_fee",""),
            "index_data": index_data,
        }

    def classify_summary(self, market="E", limit_per_type=5):
        """四类ETF分类概览"""
        trade_date = get_latest_trade_date()
        etf_list = self.list_etfs(market=market, status="L", limit=1000)
        if "error" in etf_list: return etf_list
        all_etfs = etf_list.get("data", [])
        categories = {"宽基ETF": [], "行业/主题ETF": [], "跨境ETF": [], "商品ETF": [], "货币ETF": []}
        for e in all_etfs:
            t = e.get("etf_type","")
            if t in categories: categories[t].append(e)
        results = {}
        for cat_name, cat_etfs in categories.items():
            top_etfs = []
            for etf in cat_etfs[:limit_per_type * 3]:
                try:
                    daily = pro.fund_daily(ts_code=etf["ts_code"], trade_date=trade_date)
                    d = daily.iloc[0] if daily is not None and not daily.empty else {}
                    top_etfs.append({
                        "ts_code": etf["ts_code"], "name": etf["name"],
                        "track_benchmark": str(etf.get("benchmark",""))[:50],
                        "price": d.get("close"), "pct_chg": d.get("pct_chg"),
                        "amount_yi": round(d.get("amount",0)/1e5,4) if d.get("amount") else None,
                        "m_fee": etf.get("m_fee",""),
                    })
                except: pass
            top_etfs.sort(key=lambda x: x.get("amount_yi") or 0, reverse=True)
            results[cat_name] = {"count": len(cat_etfs), "top_by_trade": top_etfs[:limit_per_type]}
        return {"categories": results, "trade_date": trade_date, "total_etfs": len(all_etfs)}

    def portfolio(self, ts_code, end_date=None, limit=20):
        params = {"ts_code": ts_code}
        if end_date: params["end_date"] = end_date.replace("-","")
        try:
            df = pro.fund_portfolio(**params)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无持仓数据: {ts_code}"}
        records = df.head(limit).to_dict(orient="records")
        for r in records:
            if "mkv" in r and r["mkv"]:
                r["mkv_yi"] = round(r["mkv"] / 1e8, 4)
        return {"data": records, "count": len(records)}

    def managers(self, ts_code):
        try:
            df = pro.fund_manager(ts_code=ts_code)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"error": f"无经理数据: {ts_code}"}
        return {"data": df.to_dict(orient="records"), "count": len(df)}

    def dividends(self, ts_code):
        try:
            df = pro.fund_div(ts_code=ts_code)
        except Exception as e:
            return {"error": str(e)}
        if df is None or df.empty:
            return {"data": [], "count": 0}
        records = df.to_dict(orient="records")
        for r in records:
            for k in ["ann_date","record_date","ex_date","pay_date","base_date"]:
                if k in r and r[k]:
                    try:
                        d = str(r[k])
                        r[k] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                    except: pass
        return {"data": records, "count": len(records)}


def parse_params(param_strings):
    params = {}
    if not param_strings: return params
    for p in param_strings:
        if "=" in p:
            key, value = p.split("=", 1)
            try:
                if "." in value: value = float(value)
                elif value.lstrip("-").isdigit(): value = int(value)
            except ValueError: pass
            params[key] = value
    return params


def main():
    parser = argparse.ArgumentParser(
        description="ETF Analyzer v2 — 基于 Tushare Pro 的 ETF 全维度分析",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("action", nargs="?", default="list",
                        help="操作: list|daily|nav|shares|scale|compare|screen|sector|index|classify|portfolio|managers|dividends")
    parser.add_argument("--params", nargs="*", default=[], help="参数 key=value ...")
    parser.add_argument("--output", default="json", choices=["json","table"], help="输出格式")
    args = parser.parse_args()

    params = parse_params(args.params)
    analyzer = ETFAnalyzer()
    result = {}
    action = args.action.lower()

    if action == "list":
        result = analyzer.list_etfs(
            market=params.get("market"), invest_type=params.get("invest_type"),
            status=params.get("status","L"), start_date=params.get("start_date"),
            end_date=params.get("end_date"), limit=int(params.get("limit", 50)),
        )
    elif action == "daily":
        result = analyzer.daily_quote(
            ts_code=params.get("ts_code"), start_date=params.get("start_date"),
            end_date=params.get("end_date"), limit=int(params.get("limit", 120)),
        )
    elif action == "nav":
        result = analyzer.nav_history(
            ts_code=params.get("ts_code"), start_date=params.get("start_date"),
            end_date=params.get("end_date"), limit=int(params.get("limit", 120)),
        )
    elif action == "shares":
        result = analyzer.share_changes(
            ts_code=params.get("ts_code"), start_date=params.get("start_date"),
            end_date=params.get("end_date"), limit=int(params.get("limit", 60)),
        )
    elif action == "scale":
        result = analyzer.get_scale(ts_code=params.get("ts_code"), trade_date=params.get("trade_date"))
    elif action == "portfolio":
        result = analyzer.portfolio(
            ts_code=params.get("ts_code"), end_date=params.get("end_date"),
            limit=int(params.get("limit", 20)),
        )
    elif action == "managers":
        result = analyzer.managers(ts_code=params.get("ts_code"))
    elif action == "dividends":
        result = analyzer.dividends(ts_code=params.get("ts_code"))
    elif action == "compare":
        codes = [c.strip() for c in params.get("ts_codes","").split(",") if c.strip()]
        result = analyzer.compare(codes)
    elif action == "screen":
        result = analyzer.screen(
            etf_type=params.get("etf_type"), min_scale=params.get("min_scale"),
            max_scale=params.get("max_scale"), invest_type=params.get("invest_type"),
            min_pct_chg=params.get("min_pct_chg"), max_pct_chg=params.get("max_pct_chg"),
            market=params.get("market","E"), limit=int(params.get("limit", 30)),
        )
    elif action == "sector":
        result = analyzer.sector_etfs(
            sector_name=params.get("sector",""), limit=int(params.get("limit", 10)),
        )
    elif action == "index":
        result = analyzer.index_analysis(ts_code=params.get("ts_code"))
    elif action == "classify":
        result = analyzer.classify_summary(
            market=params.get("market","E"),
            limit_per_type=int(params.get("limit", 5)),
        )
    else:
        result = {"error": f"未知操作: {action}"}

    if args.output == "table":
        import pandas as pd
        if "data" in result and isinstance(result["data"], list):
            print(pd.DataFrame(result["data"]).to_string(index=False))
        elif "categories" in result:
            for cat, data in result["categories"].items():
                print(f"\n=== {cat} (共{data['count']}只) ===")
                if data["top_by_trade"]:
                    print(pd.DataFrame(data["top_by_trade"]).to_string(index=False))
        else:
            print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
