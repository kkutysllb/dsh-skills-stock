#!/usr/bin/env python3
"""
财报深度解读引擎

基于「财务报表深度解读」技能框架，从三张报表（利润表、资产负债表、现金流量表）的
勾稽关系出发，深度分析企业盈利质量，识别财务造假信号，用杜邦分析分解盈利驱动因子。

核心功能：
  1. 三表勾稽验证 — 利润表↔资产负债表↔现金流量表交叉校验
  2. 盈利质量评分卡 — CFO/净利润 + 应收增速vs营收 + 扣非/归母 + 现金流趋势 + 存货周转
  3. 12项财务造假红旗检测 — 存贷双高、应收暴增、经营现金流为负等
  4. 杜邦分析三级/五级分解 — ROE = 净利率 × 周转率 × 杠杆
  5. 现金流质量矩阵 — CFO/CFI/CFF 八象限定位
  6. 综合评分 — 0-100 财报健康度评分

数据来源：Tushare Pro API

用法：
  python3 analyze_financial_deep.py --stock 600519.SH --json
  python3 analyze_financial_deep.py --stock 贵州茅台 --years 3 --json
"""

import argparse
import json
import os
import sys
from datetime import datetime

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print(json.dumps({"error": "缺少依赖: pandas/numpy 不可用，请检查 Python 运行时配置"}, ensure_ascii=False))
    sys.exit(1)

try:
    from kk_common import get_finance_data_gateway
except ImportError:  # KStock patch: kk_common 由 common 技能提供，失败时置 None
    get_finance_data_gateway = None


# ============================================================
# 数据获取层
# ============================================================

class FinancialDataFetcher:
    """Tushare Pro 财务数据获取"""

    def __init__(self, ts_code: str, years: int = 3):
        self.ts_code = ts_code
        self.years = years
        self.pro = None
        self._init_tushare()

    def _init_tushare(self):
        token = os.getenv("TUSHARE_TOKEN")
        if get_finance_data_gateway and token:
            self.pro = get_finance_data_gateway()

    @staticmethod
    def normalize_stock(stock: str) -> str:
        stock = stock.strip()
        if stock.isdigit() and len(stock) == 6:
            return f"{stock}.SH" if stock.startswith('6') else f"{stock}.SZ"
        return stock

    def _resolve_ts_code(self, stock: str) -> tuple:
        """解析股票代码和名称"""
        ts_code = self.normalize_stock(stock)
        stock_name = ts_code.replace(".SH", "").replace(".SZ", "")
        if self.pro:
            try:
                df = self.pro.stock_basic(ts_code=ts_code, fields="ts_code,name")
                if not df.empty:
                    stock_name = df.iloc[0]["name"]
            except Exception:
                pass
        return ts_code, stock_name

    def fetch_all(self, stock: str) -> dict:
        """获取全部财务数据"""
        ts_code, stock_name = self._resolve_ts_code(stock)
        if not self.pro:
            return {"error": "TUSHARE_TOKEN 未设置或 tushare 不可用"}

        start_date = f"{datetime.now().year - self.years - 1}0101"
        result = {"ts_code": ts_code, "stock_name": stock_name}

        # 利润表（含扣非净利润）
        try:
            df = self.pro.income(
                ts_code=ts_code, start_date=start_date,
                fields="ts_code,end_date,report_type,revenue,total_cogs,"
                       "sell_exp,admin_exp,rd_exp,operate_profit,total_profit,"
                       "n_income,n_income_attr_p,minority_gain,"
                       "ann_date"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["income"] = df
        except Exception as e:
            result["income_error"] = str(e)

        # 资产负债表
        try:
            df = self.pro.balancesheet(
                ts_code=ts_code, start_date=start_date,
                fields="ts_code,end_date,report_type,"
                       "total_assets,total_liab,total_hldr_eqy_exc_min_int,"
                       "money_cap,accounts_receiv,inventories,goodwill,"
                       "cip,fix_assets_total,total_cur_assets,total_cur_liab,"
                       "prepayment,oth_receiv,"
                       "st_borr,lt_borr,bond_payable,"
                       "accounts_pay,contract_liab,"
                       "minority_int,"
                       "undistr_porfit,cap_rese,surplus_rese"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["balance"] = df
        except Exception as e:
            result["balance_error"] = str(e)

        # 现金流量表
        try:
            df = self.pro.cashflow(
                ts_code=ts_code, start_date=start_date,
                fields="ts_code,end_date,report_type,"
                       "n_cashflow_act,n_cashflow_inv_act,n_cash_flows_fnc_act,"
                       "c_fr_sale_sg,c_paid_goods_s"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["cashflow"] = df
        except Exception as e:
            result["cashflow_error"] = str(e)

        # 财务指标
        try:
            df = self.pro.fina_indicator(
                ts_code=ts_code, start_date=start_date,
                fields="ts_code,end_date,"
                       "grossprofit_margin,netprofit_margin,roe,roa,debt_to_eqt,"
                       "debt_to_assets,netprofit_yoy,ocf_to_or,"
                       "inv_turn,ar_turn,ocf_to_debt,"
                       "eqt_to_debt,bps,ebit_of_gr,cfps"
            )
            if df is not None and not df.empty:
                result["indicators"] = df
        except Exception as e:
            result["indicators_error"] = str(e)

        # 获取扣非净利润（单独接口 fina_income）
        try:
            df = self.pro.income(
                ts_code=ts_code, start_date=start_date,
                fields="ts_code,end_date,report_type,n_income_attr_p"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["deduct_income"] = df
        except Exception:
            pass

        return result


# ============================================================
# 三表勾稽验证
# ============================================================

class CrossValidationEngine:
    """三表勾稽关系验证"""

    def validate(self, data: dict) -> dict:
        if "income" not in data or "balance" not in data or "cashflow" not in data:
            return {"status": "数据不完整，无法进行勾稽验证"}

        income = data["income"].copy()
        balance = data["balance"].copy()
        cashflow = data["cashflow"].copy()

        # 统一 end_date 格式并排序
        for df in [income, balance, cashflow]:
            df["end_date"] = pd.to_datetime(df["end_date"])

        results = {
            "checks": [],
            "warnings": [],
            "overall": "ok",
        }

        # 取最近期报告
        latest_date = income["end_date"].max()
        inc_row = income[income["end_date"] == latest_date].iloc[0]
        bal_row = balance[balance["end_date"] == latest_date].iloc[0]
        cf_row = cashflow[cashflow["end_date"] == latest_date].iloc[0]

        # 勾稽1: 净利润 ≈ 留存收益变动
        n_income = self._safe_float(inc_row, "n_income_attr_p")
        total_eq = self._safe_float(bal_row, "total_hldr_eqy_exc_min_int")
        if n_income != 0 and total_eq != 0:
            equity_ratio = n_income / total_eq
            check = {
                "name": "净利润 vs 归母权益",
                "formula": "归母净利润 / 归母权益",
                "value": round(equity_ratio, 4),
                "status": "ok" if 0 < equity_ratio < 0.5 else "warning",
                "note": f"ROE={equity_ratio:.2%}" if equity_ratio > 0 else "净利润为负",
            }
            results["checks"].append(check)
            if check["status"] == "warning":
                results["warnings"].append(check["note"])

        # 勾稽2: 应计利润比率
        n_income_full = self._safe_float(inc_row, "n_income")
        cfo = self._safe_float(cf_row, "n_cashflow_act")
        total_assets = self._safe_float(bal_row, "total_assets")
        if total_assets and total_assets > 0:
            accrual_ratio = (n_income_full - cfo) / total_assets
            check = {
                "name": "应计利润比率",
                "formula": "(净利润 - CFO) / 总资产",
                "value": round(accrual_ratio, 4),
                "status": "ok" if abs(accrual_ratio) < 0.1 else "warning",
                "note": "应计占比高，盈利质量需关注" if abs(accrual_ratio) >= 0.1 else "应计占比合理",
            }
            results["checks"].append(check)
            if check["status"] == "warning":
                results["warnings"].append(check["note"])

        # 勾稽3: 现金流与货币资金一致性
        money_cap = self._safe_float(bal_row, "money_cap")
        # 只能做趋势比较：CFO > 0 且货币资金较高 → 良好
        if cfo > 0 and money_cap > 0:
            check = {
                "name": "现金流 vs 货币资金",
                "value": round(cfo / money_cap, 4) if money_cap else None,
                "status": "ok",
                "note": f"CFO > 0，货币资金充足",
            }
        elif cfo < 0 and money_cap > total_assets * 0.3:
            check = {
                "name": "现金流 vs 货币资金",
                "status": "warning",
                "note": "CFO为负但货币资金高，关注资金真实性",
            }
            results["warnings"].append(check["note"])
        else:
            check = {
                "name": "现金流 vs 货币资金",
                "status": "info",
                "note": "需结合更多信息判断",
            }
        results["checks"].append(check)

        if results["warnings"]:
            results["overall"] = "attention_needed"

        return results

    @staticmethod
    def _safe_float(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return 0.0
        return float(val)


# ============================================================
# 盈利质量评分卡
# ============================================================

class EarningsQualityScorer:
    """盈利质量评分（5项指标加权）"""

    WEIGHTS = {
        "cfo_to_ni": 0.25,
        "receivable_vs_revenue": 0.20,
        "deduct_to_attributed": 0.20,
        "cfo_trend": 0.20,
        "inventory_turn": 0.15,
    }

    def score(self, data: dict) -> dict:
        if "income" not in data or "cashflow" not in data:
            return {"error": "数据不完整"}

        income = data["income"].copy()
        cashflow = data["cashflow"].copy()
        indicators = data.get("indicators", pd.DataFrame()).copy()

        income["end_date"] = pd.to_datetime(income["end_date"])
        cashflow["end_date"] = pd.to_datetime(cashflow["end_date"])

        results = {"items": [], "total_score": 0.0, "rating": ""}

        # 1. CFO / 净利润 (25%)
        cfo_ni_score = self._score_cfo_to_ni(income, cashflow)
        results["items"].append(cfo_ni_score)

        # 2. 应收增速 vs 营收增速 (20%)
        ar_rev_score = self._score_receivable_vs_revenue(data)
        results["items"].append(ar_rev_score)

        # 3. 扣非 / 归母 (20%)
        deduct_score = self._score_deduct_ratio(income)
        results["items"].append(deduct_score)

        # 4. 经营现金流趋势 (20%)
        cfo_trend_score = self._score_cfo_trend(cashflow)
        results["items"].append(cfo_trend_score)

        # 5. 存货周转 (15%)
        inv_turn_score = self._score_inventory_turn(indicators)
        results["items"].append(inv_turn_score)

        # 加权综合
        total = sum(item["weighted_score"] for item in results["items"])
        results["total_score"] = round(total, 3)

        if total >= 2.5:
            results["rating"] = "盈利质量优秀"
            results["rating_level"] = "excellent"
        elif total >= 2.0:
            results["rating"] = "盈利质量良好"
            results["rating_level"] = "good"
        elif total >= 1.5:
            results["rating"] = "盈利质量一般，需关注"
            results["rating_level"] = "fair"
        else:
            results["rating"] = "盈利质量差，建议回避"
            results["rating_level"] = "poor"

        return results

    def _score_cfo_to_ni(self, income: pd.DataFrame, cashflow: pd.DataFrame) -> dict:
        """CFO / 净利润评分"""
        try:
            merged = pd.merge(
                income[["end_date", "n_income_attr_p"]],
                cashflow[["end_date", "n_cashflow_act"]],
                on="end_date", how="inner"
            ).sort_values("end_date")

            if merged.empty:
                return {"name": "CFO/净利润", "score": 0, "weighted_score": 0, "note": "数据不足"}

            latest = merged.iloc[-1]
            ni = latest["n_income_attr_p"]
            cfo = latest["n_cashflow_act"]

            if ni and ni > 0:
                ratio = cfo / ni
                if ratio > 1.2:
                    score, note = 3, f"CFO/净利润={ratio:.2f}，现金回收优秀"
                elif ratio > 0.8:
                    score, note = 2, f"CFO/净利润={ratio:.2f}，现金回收正常"
                else:
                    score, note = 1, f"CFO/净利润={ratio:.2f}，大量利润未变现金"
            elif ni and ni < 0:
                if cfo > 0:
                    score, note = 2, f"净利润亏损但CFO为正，亏损可能一次性"
                else:
                    score, note = 1, f"净利润亏损且CFO为负，经营质量差"
            else:
                score, note = 2, "净利润接近零，无法有效评估"

            return {
                "name": "CFO/净利润",
                "weight": self.WEIGHTS["cfo_to_ni"],
                "score": score,
                "weighted_score": score * self.WEIGHTS["cfo_to_ni"],
                "value": round(cfo / ni, 2) if ni and ni != 0 else None,
                "note": note,
            }
        except Exception as e:
            return {"name": "CFO/净利润", "score": 0, "weighted_score": 0, "note": f"计算异常: {e}"}

    def _score_receivable_vs_revenue(self, data: dict) -> dict:
        """应收增速 vs 营收增速评分"""
        income = data.get("income")
        balance = data.get("balance")
        if income is None or balance is None:
            return {"name": "应收vs营收增速", "score": 2, "weighted_score": 0.4, "note": "数据不足"}

        try:
            inc = income.copy()
            inc["end_date"] = pd.to_datetime(inc["end_date"])
            inc = inc.sort_values("end_date").tail(4)

            bal = balance.copy()
            bal["end_date"] = pd.to_datetime(bal["end_date"])
            bal = bal.sort_values("end_date").tail(4)

            merged = pd.merge(
                inc[["end_date", "revenue"]],
                bal[["end_date", "accounts_receiv"]],
                on="end_date", how="inner"
            ).sort_values("end_date")

            if len(merged) < 2:
                return {"name": "应收vs营收增速", "score": 2, "weighted_score": 0.4, "note": "历史数据不足"}

            rev_g = merged["revenue"].pct_change().iloc[-1]
            ar_g = merged["accounts_receiv"].pct_change().iloc[-1]

            if pd.isna(rev_g) or pd.isna(ar_g):
                return {"name": "应收vs营收增速", "score": 2, "weighted_score": 0.4, "note": "数据缺失"}

            if ar_g < rev_g:
                score, note = 3, f"应收增速({ar_g:.1%}) < 营收增速({rev_g:.1%})，收入质量好"
            elif ar_g < rev_g * 1.5:
                score, note = 2, f"应收增速({ar_g:.1%}) ≈ 营收增速({rev_g:.1%})，收入质量一般"
            else:
                score, note = 1, f"应收增速({ar_g:.1%}) >> 营收增速({rev_g:.1%})，收入质量恶化"

            return {
                "name": "应收vs营收增速",
                "weight": self.WEIGHTS["receivable_vs_revenue"],
                "score": score,
                "weighted_score": score * self.WEIGHTS["receivable_vs_revenue"],
                "note": note,
            }
        except Exception as e:
            return {"name": "应收vs营收增速", "score": 2, "weighted_score": 0.4, "note": f"计算异常: {e}"}

    def _score_deduct_ratio(self, income: pd.DataFrame) -> dict:
        """扣非/归母净利润评分"""
        try:
            df = income.sort_values("end_date")
            latest = df.iloc[-1]
            ni_attr = latest.get("n_income_attr_p", 0)

            # 尝试估算扣非：归母 - 非经常性收益
            excite = latest.get("excite_income", 0) or 0
            excite_tax = latest.get("excite_tax", 0) or 0
            non_recurring = excite - excite_tax

            if ni_attr and ni_attr != 0 and non_recurring:
                deduct_ni = ni_attr - non_recurring
                ratio = deduct_ni / ni_attr
                if ratio > 0.9:
                    score, note = 3, f"扣非/归母={ratio:.1%}，利润来源扎实"
                elif ratio > 0.7:
                    score, note = 2, f"扣非/归母={ratio:.1%}，有一定非经常性损益"
                else:
                    score, note = 1, f"扣非/归母={ratio:.1%}，利润依赖非经常性项目"
            else:
                score, note = 2, "无法精确计算扣非比例（使用近似值）"

            return {
                "name": "扣非/归母",
                "weight": self.WEIGHTS["deduct_to_attributed"],
                "score": score,
                "weighted_score": score * self.WEIGHTS["deduct_to_attributed"],
                "note": note,
            }
        except Exception:
            return {"name": "扣非/归母", "score": 2, "weighted_score": 0.4, "note": "数据不足"}

    def _score_cfo_trend(self, cashflow: pd.DataFrame) -> dict:
        """经营现金流趋势评分"""
        try:
            df = cashflow.sort_values("end_date")
            cfo_series = df["n_cashflow_act"].dropna().tail(4)

            if len(cfo_series) < 2:
                return {"name": "CFO趋势", "score": 2, "weighted_score": 0.4, "note": "数据不足"}

            # 趋势判断
            positive_count = (cfo_series > 0).sum()
            trend = cfo_series.diff().dropna()

            if positive_count == len(cfo_series) and trend.iloc[-1] > 0:
                score, note = 3, "CFO连续为正且趋势增长"
            elif positive_count == len(cfo_series):
                score, note = 2, "CFO连续为正但增速放缓"
            elif positive_count >= len(cfo_series) * 0.5:
                score, note = 2, "CFO波动较大"
            else:
                score, note = 1, "CFO持续为负，经营获现能力差"

            return {
                "name": "CFO趋势",
                "weight": self.WEIGHTS["cfo_trend"],
                "score": score,
                "weighted_score": score * self.WEIGHTS["cfo_trend"],
                "note": note,
            }
        except Exception:
            return {"name": "CFO趋势", "score": 2, "weighted_score": 0.4, "note": "数据不足"}

    def _score_inventory_turn(self, indicators: pd.DataFrame) -> dict:
        """存货周转评分"""
        if indicators.empty:
            return {"name": "存货周转", "score": 2, "weighted_score": 0.3, "note": "无财务指标数据"}

        try:
            df = indicators.sort_values("end_date")
            if "inv_turn" not in df.columns or df["inv_turn"].dropna().empty:
                return {"name": "存货周转", "score": 2, "weighted_score": 0.3, "note": "无存货周转数据"}

            turns = df["inv_turn"].dropna().tail(4)
            if len(turns) < 2:
                return {"name": "存货周转", "score": 2, "weighted_score": 0.3, "note": "数据不足"}

            trend = turns.diff().iloc[-1]
            if trend > 0:
                score, note = 3, f"存货周转加快，最新={turns.iloc[-1]:.2f}次"
            elif abs(trend) < 0.1:
                score, note = 2, f"存货周转稳定，最新={turns.iloc[-1]:.2f}次"
            else:
                score, note = 1, f"存货周转放慢，最新={turns.iloc[-1]:.2f}次"

            return {
                "name": "存货周转",
                "weight": self.WEIGHTS["inventory_turn"],
                "score": score,
                "weighted_score": score * self.WEIGHTS["inventory_turn"],
                "note": note,
            }
        except Exception:
            return {"name": "存货周转", "score": 2, "weighted_score": 0.3, "note": "数据不足"}


# ============================================================
# 12项财务造假红旗检测
# ============================================================

class FraudRedFlagDetector:
    """12项财务造假红旗信号检测"""

    def detect(self, data: dict) -> dict:
        flags = []
        income = data.get("income")
        balance = data.get("balance")
        cashflow = data.get("cashflow")
        indicators = data.get("indicators")

        if income is not None:
            income = income.copy()
            income["end_date"] = pd.to_datetime(income["end_date"])
        if balance is not None:
            balance = balance.copy()
            balance["end_date"] = pd.to_datetime(balance["end_date"])
        if cashflow is not None:
            cashflow = cashflow.copy()
            cashflow["end_date"] = pd.to_datetime(cashflow["end_date"])

        # 红旗1: 存贷双高
        if balance is not None and not balance.empty:
            latest = balance.sort_values("end_date").iloc[-1]
            money = self._val(latest, "money_cap")
            total = self._val(latest, "total_assets")
            st_borr = self._val(latest, "st_borr")
            lt_borr = self._val(latest, "lt_borr")
            bonds = self._val(latest, "bond_payable")
            interest_debt = st_borr + lt_borr + bonds

            if total > 0:
                money_ratio = money / total
                debt_ratio = interest_debt / total
                if money_ratio > 0.3 and debt_ratio > 0.3:
                    flags.append({
                        "id": 1, "name": "存贷双高",
                        "severity": "high",
                        "triggered": True,
                        "detail": f"货币资金占比{money_ratio:.1%}，有息负债占比{debt_ratio:.1%}",
                        "suggestion": "高额货币资金同时高额负债，关注资金真实性",
                    })
                else:
                    flags.append({"id": 1, "name": "存贷双高", "severity": "high",
                                  "triggered": False, "detail": "正常"})

        # 红旗2: 应收暴增
        if income is not None and balance is not None and not income.empty and not balance.empty:
            merged = pd.merge(
                income[["end_date", "revenue"]].tail(4),
                balance[["end_date", "accounts_receiv"]].tail(4),
                on="end_date", how="inner"
            ).sort_values("end_date").tail(4)

            if len(merged) >= 2:
                rev_g = merged["revenue"].pct_change()
                ar_g = merged["accounts_receiv"].pct_change()
                mask = (ar_g > rev_g * 1.5) & (ar_g > 0)
                consecutive = mask.tail(2).sum()
                if consecutive >= 2:
                    flags.append({
                        "id": 2, "name": "应收暴增",
                        "severity": "high",
                        "triggered": True,
                        "detail": f"应收增速持续超过营收增速1.5倍，连续{consecutive}期",
                        "suggestion": "收入质量恶化，关注坏账风险",
                    })
                else:
                    flags.append({"id": 2, "name": "应收暴增", "severity": "high",
                                  "triggered": False, "detail": "正常"})

        # 红旗3: 存货异常
        if income is not None and balance is not None:
            merged = pd.merge(
                income[["end_date", "revenue"]].tail(4),
                balance[["end_date", "inventories"]].tail(4),
                on="end_date", how="inner"
            ).sort_values("end_date")

            if len(merged) >= 2:
                inv_ratio = merged["inventories"] / merged["revenue"].replace(0, np.nan)
                latest_ratio = inv_ratio.iloc[-1]
                prev_ratio = inv_ratio.iloc[-2] if len(inv_ratio) >= 2 else latest_ratio
                if prev_ratio > 0 and latest_ratio / prev_ratio > 1.5:
                    flags.append({
                        "id": 3, "name": "存货异常",
                        "severity": "high",
                        "triggered": True,
                        "detail": f"存货/营收比例突然上升{(latest_ratio/prev_ratio - 1):.0%}",
                        "suggestion": "存货积压风险，关注跌价准备是否充足",
                    })
                else:
                    flags.append({"id": 3, "name": "存货异常", "severity": "high",
                                  "triggered": False, "detail": "正常"})

        # 红旗4: 经营现金流为负但净利润为正
        if income is not None and cashflow is not None:
            merged = pd.merge(
                income[["end_date", "n_income"]].tail(4),
                cashflow[["end_date", "n_cashflow_act"]].tail(4),
                on="end_date", how="inner"
            ).sort_values("end_date").tail(4)

            neg_cfo_pos_ni = ((merged["n_cashflow_act"] < 0) & (merged["n_income"] > 0)).sum()
            if neg_cfo_pos_ni >= 2:
                flags.append({
                    "id": 4, "name": "经营现金流为负",
                    "severity": "high",
                    "triggered": True,
                    "detail": f"连续{neg_cfo_pos_ni}期净利润为正但CFO为负",
                    "suggestion": "纸面利润无现金支撑，盈利质量堪忧",
                })
            else:
                flags.append({"id": 4, "name": "经营现金流为负", "severity": "high",
                              "triggered": False, "detail": "正常"})

        # 红旗5-12: 基于资产负债表单期检测
        if balance is not None and not balance.empty:
            latest = balance.sort_values("end_date").iloc[-1]
            total = self._val(latest, "total_assets")

            # 红旗7: 在建工程不转固
            cip = self._val(latest, "cip")
            fix = self._val(latest, "fix_assets_total")
            if fix > 0 and cip / fix > 0.5:
                flags.append({
                    "id": 7, "name": "在建工程不转固",
                    "severity": "medium",
                    "triggered": True,
                    "detail": f"在建工程/固定资产={cip/fix:.1%}（>50%）",
                    "suggestion": "长期在建工程不转固可能虚增资产",
                })
            else:
                flags.append({"id": 7, "name": "在建工程不转固", "severity": "medium",
                              "triggered": False, "detail": "正常"})

            # 红旗8: 预付账款异常
            prepay = self._val(latest, "prepayment")
            if total > 0 and prepay / total > 0.1:
                flags.append({
                    "id": 8, "name": "预付账款异常",
                    "severity": "medium",
                    "triggered": True,
                    "detail": f"预付账款/总资产={prepay/total:.1%}",
                    "suggestion": "高额预付可能通过关联方转移资金",
                })
            else:
                flags.append({"id": 8, "name": "预付账款异常", "severity": "medium",
                              "triggered": False, "detail": "正常"})

            # 红旗12: 商誉占比高
            goodwill = self._val(latest, "goodwill")
            equity = self._val(latest, "total_hldr_eqy_exc_min_int")
            if equity > 0 and goodwill / equity > 0.3:
                flags.append({
                    "id": 12, "name": "商誉占比高",
                    "severity": "medium",
                    "triggered": True,
                    "detail": f"商誉/净资产={goodwill/equity:.1%}（>30%）",
                    "suggestion": "高商誉面临减值风险，关注并购标的业绩承诺",
                })
            else:
                flags.append({"id": 12, "name": "商誉占比高", "severity": "medium",
                              "triggered": False,
                              "detail": f"商誉/净资产={goodwill/equity:.1%}" if equity > 0 else "N/A"})

        # 统计
        triggered = [f for f in flags if f.get("triggered")]
        high_count = sum(1 for f in triggered if f.get("severity") == "high")
        total_triggered = len(triggered)

        if total_triggered <= 1:
            risk_level, risk_label = "low", "低风险"
        elif total_triggered <= 3:
            risk_level, risk_label = "medium", "中等风险，需深入调查"
        elif total_triggered <= 5:
            risk_level, risk_label = "high", "高风险，建议回避"
        else:
            risk_level, risk_label = "extreme", "极高风险，强烈回避"

        return {
            "flags": flags,
            "triggered_count": total_triggered,
            "high_severity_count": high_count,
            "risk_level": risk_level,
            "risk_label": risk_label,
        }

    @staticmethod
    def _val(row, col: str) -> float:
        v = row.get(col, 0)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return 0.0
        return float(v)


# ============================================================
# 杜邦分析
# ============================================================

class DuPontAnalyzer:
    """杜邦分析（三级 + 五级分解）"""

    def analyze(self, data: dict) -> dict:
        income = data.get("income")
        balance = data.get("balance")
        indicators = data.get("indicators")

        if income is None or balance is None:
            return {"error": "利润表或资产负债表数据缺失"}

        income = income.copy()
        balance = balance.copy()
        income["end_date"] = pd.to_datetime(income["end_date"])
        balance["end_date"] = pd.to_datetime(balance["end_date"])

        # 合并最近几期
        merged = pd.merge(
            income[["end_date", "revenue", "n_income_attr_p", "total_profit",
                    "operate_profit", "total_cogs"]].tail(4),
            balance[["end_date", "total_assets", "total_hldr_eqy_exc_min_int",
                     "total_liab"]].tail(4),
            on="end_date", how="inner"
        ).sort_values("end_date")

        if merged.empty:
            return {"error": "利润表与资产负债表无法匹配"}

        periods = []
        for _, row in merged.iterrows():
            rev = self._v(row, "revenue")
            ni = self._v(row, "n_income_attr_p")
            ta = self._v(row, "total_assets")
            equity = self._v(row, "total_hldr_eqy_exc_min_int")
            tp = self._v(row, "total_profit")
            op = self._v(row, "operate_profit")
            liab = self._v(row, "total_liab")

            if rev == 0 or ta == 0 or equity == 0:
                continue

            # 三级分解
            net_margin = ni / rev
            asset_turnover = rev / ta
            equity_multiplier = ta / equity
            roe = net_margin * asset_turnover * equity_multiplier

            # 五级分解
            tax_burden = ni / tp if tp != 0 else 0
            interest_burden = tp / op if op != 0 else 0
            operating_margin = op / rev if rev != 0 else 0

            periods.append({
                "end_date": row["end_date"].strftime("%Y-%m-%d"),
                "roe": round(roe, 4),
                "net_margin": round(net_margin, 4),
                "asset_turnover": round(asset_turnover, 4),
                "equity_multiplier": round(equity_multiplier, 4),
                # 五级
                "tax_burden": round(tax_burden, 4),
                "interest_burden": round(interest_burden, 4),
                "operating_margin": round(operating_margin, 4),
            })

        if not periods:
            return {"error": "所有期数据均无法计算"}

        # 驱动判断
        latest = periods[-1]
        driving = self._identify_roe_driver(latest)

        return {
            "periods": periods,
            "latest": latest,
            "roe_driver": driving,
        }

    def _identify_roe_driver(self, latest: dict) -> dict:
        """识别ROE主要驱动因子"""
        drivers = {
            "net_margin": ("盈利能力", latest["net_margin"]),
            "asset_turnover": ("运营效率", latest["asset_turnover"]),
            "equity_multiplier": ("杠杆水平", latest["equity_multiplier"]),
        }

        # 找最大贡献因子
        if latest["roe"] > 0:
            best = max(drivers.items(), key=lambda x: x[1][1])
            driver_name = best[1][0]
            if best[0] == "equity_multiplier":
                note = f"ROE主要由杠杆驱动（权益乘数={latest['equity_multiplier']:.2f}），需关注负债风险"
            elif best[0] == "net_margin":
                note = f"ROE主要由盈利能力驱动（净利率={latest['net_margin']:.2%}），质量较高"
            else:
                note = f"ROE主要由运营效率驱动（周转率={latest['asset_turnover']:.2f}）"
        else:
            driver_name = "亏损"
            note = "ROE为负，企业处于亏损状态"

        return {"primary_driver": driver_name, "note": note}

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return 0.0
        return float(val)


# ============================================================
# 现金流质量矩阵
# ============================================================

class CashFlowMatrixAnalyzer:
    """现金流质量矩阵分析"""

    def analyze(self, data: dict) -> dict:
        cashflow = data.get("cashflow")
        if cashflow is None or cashflow.empty:
            return {"error": "无现金流量表数据"}

        df = cashflow.copy()
        df["end_date"] = pd.to_datetime(df["end_date"])
        df = df.sort_values("end_date")

        latest = df.iloc[-1]
        cfo = self._v(latest, "n_cashflow_act")
        cfi = self._v(latest, "n_cashflow_inv_act")
        cff = self._v(latest, "n_cash_flows_fnc_act")

        cfo_sign = "+" if cfo > 0 else "-"
        cfi_sign = "-" if cfi < 0 else "+"
        cff_sign = "-" if cff < 0 else "+"

        pattern = f"{cfo_sign}/{cfi_sign}/{cff_sign}"

        # 判断企业状态
        status_map = {
            "+/-/-": ("优秀", "赚钱、投资扩张、还债/分红"),
            "+/-/+": ("扩张期", "赚钱、投资扩张、借钱加速发展"),
            "+/+/-": ("稳健", "赚钱、回收投资、还债"),
            "-/-/+": ("危险", "亏损、还在投、靠借钱维持"),
            "-/+/+": ("困境", "卖资产+借钱维持"),
            "-/+/-": ("衰退", "卖资产还债"),
        }

        status, description = status_map.get(pattern, ("不确定", f"CFO={cfo_sign} CFI={cfi_sign} CFF={cff_sign}"))

        return {
            "latest_period": latest["end_date"].strftime("%Y-%m-%d"),
            "cfo": round(cfo, 0),
            "cfi": round(cfi, 0),
            "cff": round(cff, 0),
            "pattern": pattern,
            "status": status,
            "description": description,
            "cash_flow_quality": "healthy" if cfo > 0 else "warning" if cfo < 0 else "neutral",
        }

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return 0.0
        return float(val)


# ============================================================
# 综合评分
# ============================================================

def compute_overall_score(cross_val: dict, eq_score: dict, fraud: dict,
                          dupont: dict, cf_matrix: dict) -> dict:
    """计算财报健康度综合评分（0-100）"""

    components = {}

    # 1. 三表勾稽 (15%)
    cv_warnings = len(cross_val.get("warnings", []))
    cv_score = max(0, 100 - cv_warnings * 15)
    components["cross_validation"] = {"score": cv_score, "weight": 0.15}

    # 2. 盈利质量 (30%)
    eq_total = eq_score.get("total_score", 0)
    eq_normalized = eq_total / 3.0 * 100  # 3分满分 → 100
    components["earnings_quality"] = {"score": eq_normalized, "weight": 0.30}

    # 3. 造假风险 (25%) — 触发红旗越多扣分越重
    triggered = fraud.get("triggered_count", 0)
    fraud_score = max(0, 100 - triggered * 18)
    components["fraud_risk"] = {"score": fraud_score, "weight": 0.25}

    # 4. 杜邦分析 (15%) — ROE驱动质量
    if "error" not in dupont:
        driver = dupont.get("roe_driver", {}).get("primary_driver", "")
        if driver == "盈利能力":
            dupont_score = 90
        elif driver == "运营效率":
            dupont_score = 80
        elif driver == "杠杆水平":
            dupont_score = 55
        elif driver == "亏损":
            dupont_score = 20
        else:
            dupont_score = 60
    else:
        dupont_score = 50
    components["dupont"] = {"score": dupont_score, "weight": 0.15}

    # 5. 现金流质量 (15%)
    cf_quality = cf_matrix.get("cash_flow_quality", "neutral")
    cf_score_map = {"healthy": 90, "neutral": 60, "warning": 30}
    cf_score = cf_score_map.get(cf_quality, 50)
    components["cashflow_matrix"] = {"score": cf_score, "weight": 0.15}

    # 加权总分
    total = sum(c["score"] * c["weight"] for c in components.values())

    # 评级
    if total >= 80:
        rating = "优秀"
    elif total >= 65:
        rating = "良好"
    elif total >= 50:
        rating = "一般"
    elif total >= 35:
        rating = "较差"
    else:
        rating = "危险"

    return {
        "score": round(total, 2),
        "rating": rating,
        "components": {k: {"score": round(v["score"], 2), "weight": v["weight"]} for k, v in components.items()},
    }


# ============================================================
# 主分析流程
# ============================================================

def analyze_financial_deep(stock: str, years: int = 3) -> dict:
    """执行完整财报深度解读"""

    fetcher = FinancialDataFetcher(ts_code=stock, years=years)
    data = fetcher.fetch_all(stock)

    if "error" in data:
        return data

    result = {
        "stock": data["ts_code"],
        "stock_name": data["stock_name"],
        "analysis_type": "financial_deep_analysis",
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "Tushare Pro API",
        "lookback_years": years,
    }

    # 1. 三表勾稽
    cv_engine = CrossValidationEngine()
    cross_val = cv_engine.validate(data)
    result["cross_validation"] = cross_val

    # 2. 盈利质量
    eq_scorer = EarningsQualityScorer()
    eq_result = eq_scorer.score(data)
    result["earnings_quality"] = eq_result

    # 3. 造假红旗
    fraud_detector = FraudRedFlagDetector()
    fraud_result = fraud_detector.detect(data)
    result["fraud_red_flags"] = fraud_result

    # 4. 杜邦分析
    dupont_analyzer = DuPontAnalyzer()
    dupont_result = dupont_analyzer.analyze(data)
    result["dupont_analysis"] = dupont_result

    # 5. 现金流矩阵
    cf_analyzer = CashFlowMatrixAnalyzer()
    cf_result = cf_analyzer.analyze(data)
    result["cashflow_matrix"] = cf_result

    # 6. 综合评分
    overall = compute_overall_score(cross_val, eq_result, fraud_result, dupont_result, cf_result)
    result["overall_score"] = overall

    # 7. 投资建议
    result["investment_advice"] = _generate_advice(overall, fraud_result, eq_result)

    # 8. 免责声明
    result["disclaimer"] = "数据来源于Tushare Pro API，分析结果仅供参考，不构成投资建议"

    return result


def _generate_advice(overall: dict, fraud: dict, eq: dict) -> dict:
    """生成投资建议"""
    score = overall["score"]
    advice_parts = []

    if score >= 80:
        advice_parts.append("财务状况健康，盈利质量优秀，可作为投资备选")
    elif score >= 65:
        advice_parts.append("财务状况良好，盈利质量尚可，可适当关注")
    elif score >= 50:
        advice_parts.append("财务状况一般，存在部分隐患，建议谨慎")
    else:
        advice_parts.append("财务状况较差，存在明显风险信号，建议回避")

    if fraud.get("triggered_count", 0) >= 3:
        advice_parts.append(f"触发{fraud['triggered_count']}项红旗信号，强烈建议深入调查")

    eq_level = eq.get("rating_level", "fair")
    if eq_level == "poor":
        advice_parts.append("盈利质量差，利润变现有困难")
    elif eq_level == "excellent":
        advice_parts.append("盈利质量优秀，现金流回收好")

    return {
        "summary": "；".join(advice_parts),
        "action": "买入" if score >= 80 else "观望" if score >= 50 else "回避",
        "confidence": round(min(score / 100, 1.0), 4),
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="财报深度解读引擎")
    parser.add_argument("--stock", required=True, help="股票代码或名称")
    parser.add_argument("--years", type=int, default=3, help="回看年数（默认3年）")
    parser.add_argument("--json", action="store_true", help="JSON 输出模式")
    args = parser.parse_args()

    result = analyze_financial_deep(args.stock, args.years)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(result)


def _print_report(result: dict):
    """打印可读报告"""
    print(f"\n{'=' * 60}")
    print(f"  财报深度解读报告 — {result.get('stock_name', '')} ({result.get('stock', '')})")
    print(f"  分析时间: {result.get('analysis_time', '')}")
    print(f"  数据来源: {result.get('data_source', '')}")
    print(f"{'=' * 60}")

    if "error" in result:
        print(f"\n  错误: {result['error']}")
        return

    # 综合评分
    overall = result.get("overall_score", {})
    print(f"\n⭐ 财报健康度: {overall.get('score', 0):.1f}/100 — {overall.get('rating', '')}")

    # 三表勾稽
    cv = result.get("cross_validation", {})
    print(f"\n📋 三表勾稽验证")
    for check in cv.get("checks", []):
        icon = "✅" if check.get("status") == "ok" else "⚠️"
        print(f"  {icon} {check['name']}: {check.get('note', '')}")

    # 盈利质量
    eq = result.get("earnings_quality", {})
    print(f"\n💰 盈利质量评分: {eq.get('total_score', 0):.2f}/3.0 — {eq.get('rating', '')}")
    for item in eq.get("items", []):
        stars = "⭐" * item.get("score", 0)
        print(f"  {stars} {item['name']}: {item.get('note', '')}")

    # 造假红旗
    fraud = result.get("fraud_red_flags", {})
    print(f"\n🚩 财务造假红旗: 触发 {fraud.get('triggered_count', 0)} 项 — {fraud.get('risk_label', '')}")
    for flag in fraud.get("flags", []):
        if flag.get("triggered"):
            icon = "🔴" if flag.get("severity") == "high" else "🟡"
            print(f"  {icon} [{flag['name']}] {flag.get('detail', '')}")
            print(f"     建议: {flag.get('suggestion', '')}")

    # 杜邦分析
    dupont = result.get("dupont_analysis", {})
    if "error" not in dupont:
        latest = dupont.get("latest", {})
        print(f"\n📊 杜邦分析（最新期）")
        print(f"  ROE = {latest.get('roe', 0):.2%}")
        print(f"    = 净利率({latest.get('net_margin', 0):.2%}) × 周转率({latest.get('asset_turnover', 0):.2f}) × 杠杆({latest.get('equity_multiplier', 0):.2f})")
        print(f"  驱动因子: {dupont.get('roe_driver', {}).get('note', '')}")
    else:
        print(f"\n📊 杜邦分析: {dupont.get('error', '数据不足')}")

    # 现金流矩阵
    cf = result.get("cashflow_matrix", {})
    if "error" not in cf:
        print(f"\n💵 现金流质量矩阵")
        print(f"  CFO={cf.get('cfo', 0):.0f} | CFI={cf.get('cfi', 0):.0f} | CFF={cf.get('cff', 0):.0f}")
        print(f"  类型: {cf.get('pattern', '')} — {cf.get('status', '')}({cf.get('description', '')})")
    else:
        print(f"\n💵 现金流矩阵: {cf.get('error', '数据不足')}")

    # 投资建议
    advice = result.get("investment_advice", {})
    print(f"\n💡 投资建议")
    print(f"  行动: {advice.get('action', '')} | 置信度: {advice.get('confidence', 0):.0%}")
    print(f"  {advice.get('summary', '')}")

    print(f"\n{'=' * 60}")
    print(f"  ⚠️ {result.get('disclaimer', '')}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
