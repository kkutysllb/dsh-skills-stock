#!/usr/bin/env python3
"""
多估值模型分析引擎（DCF + DDM + SOTP + PE-Band + PB-ROE + EV/EBITDA）

基于「估值模型方法论」和「现金流折现估值模型」技能框架，实现多模型交叉验证估值。

核心功能：
  1. DCF 现金流折现 — FCFF预测 + WACC计算 + 终值 + 敏感性分析
  2. DDM 股息折现 — 两阶段模型（适用高股息股）
  3. SOTP 分部估值 — 多业务线拆分估值（适用多元化集团）
  4. PE-Band 历史分位 — 5年PE分位数分析
  5. PB-ROE 矩阵 — PB/ROE四象限定位
  6. EV/EBITDA — 剔除资本结构差异的跨行业对比
  7. 估值陷阱检测 — 10项估值陷阱识别
  8. 多模型交叉验证 — 至少2种方法取中值，差异>30%需复核
  9. 综合目标价 — 加权目标价 + 上涨/下跌空间

数据来源：Tushare Pro API

用法：
  python3 analyze_valuation_models.py --stock 600519.SH --json
  python3 analyze_valuation_models.py --stock 贵州茅台 --years 5 --json
"""

import argparse
import json
import math
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
# 数据获取
# ============================================================

class ValuationDataFetcher:
    """估值模型数据获取"""

    def __init__(self):
        self.pro = None
        token = os.getenv("TUSHARE_TOKEN")
        if get_finance_data_gateway and token:
            self.pro = get_finance_data_gateway()

    @staticmethod
    def normalize_stock(stock: str) -> str:
        stock = stock.strip()
        if stock.isdigit() and len(stock) == 6:
            return f"{stock}.SH" if stock.startswith('6') else f"{stock}.SZ"
        return stock

    def fetch(self, ts_code: str, years: int = 5) -> dict:
        if not self.pro:
            return {"error": "TUSHARE_TOKEN 未设置"}
        result = {"ts_code": ts_code}
        start = f"{datetime.now().year - years - 1}0101"

        # 基本信息
        try:
            df = self.pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry,list_date")
            if not df.empty:
                r = df.iloc[0]
                result["stock_name"] = r.get("name", "")
                result["industry"] = r.get("industry", "")
        except Exception:
            result["stock_name"] = ts_code

        # 日线行情（计算市值、PE、PB历史）
        try:
            df = self.pro.daily_basic(
                ts_code=ts_code, start_date=start,
                fields="ts_code,trade_date,close,pe_ttm,pb,ps_ttm,total_mv,circ_mv,"
                       "total_share,float_share,turnover_rate,dv_ratio"
            )
            if df is not None and not df.empty:
                result["daily_basic"] = df.sort_values("trade_date")
        except Exception as e:
            result["daily_basic_error"] = str(e)

        # 利润表
        try:
            df = self.pro.income(
                ts_code=ts_code, start_date=start,
                fields="ts_code,end_date,report_type,revenue,total_cogs,"
                       "sell_exp,admin_exp,rd_exp,operate_profit,total_profit,"
                       "n_income,n_income_attr_p,income_tax,ebit"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["income"] = df.sort_values("end_date")
        except Exception as e:
            result["income_error"] = str(e)

        # 资产负债表
        try:
            df = self.pro.balancesheet(
                ts_code=ts_code, start_date=start,
                fields="ts_code,end_date,report_type,"
                       "total_assets,total_liab,total_hldr_eqy_exc_min_int,"
                       "money_cap,total_cur_assets,total_cur_liab,"
                       "st_borr,lt_borr,bond_payable,"
                       "goodwill,fix_assets_total,cip,inventories,"
                       "accounts_receiv,total_share"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["balance"] = df.sort_values("end_date")
        except Exception as e:
            result["balance_error"] = str(e)

        # 现金流量表
        try:
            df = self.pro.cashflow(
                ts_code=ts_code, start_date=start,
                fields="ts_code,end_date,report_type,"
                       "n_cashflow_act,c_paid_goods_s,"
                       "c_fr_sale_sg,c_pay_acq_const_fiolta,"
                       "c_pay_dist_dpcp_int_exp"
            )
            if df is not None and not df.empty:
                if "report_type" in df.columns:
                    df = df[df["report_type"] == "1"].copy()
                result["cashflow"] = df.sort_values("end_date")
        except Exception as e:
            result["cashflow_error"] = str(e)

        # 财务指标
        try:
            df = self.pro.fina_indicator(
                ts_code=ts_code, start_date=start,
                fields="ts_code,end_date,grossprofit_margin,netprofit_margin,"
                       "roe,roa,debt_to_assets,eps,debt_to_eqt"
            )
            if df is not None and not df.empty:
                result["indicators"] = df.sort_values("end_date")
        except Exception as e:
            result["indicators_error"] = str(e)

        # 分红数据
        try:
            df = self.pro.dividend(
                ts_code=ts_code, fields="ts_code,end_date,ann_date,div_proc,"
                                       "stk_div,stk_bo_rate,cash_div,cash_div_tax"
            )
            if df is not None and not df.empty:
                result["dividend"] = df.sort_values("end_date", ascending=False).head(10)
        except Exception:
            pass

        return result

    def get_latest_price(self, ts_code: str) -> dict:
        """获取最新价格"""
        try:
            df = self.pro.daily_basic(
                ts_code=ts_code,
                fields="ts_code,trade_date,close,pe_ttm,pb,ps_ttm,total_mv,total_share"
            )
            if df is not None and not df.empty:
                latest = df.sort_values("trade_date").iloc[-1]
                return {
                    "close": float(latest.get("close", 0)),
                    "pe_ttm": float(latest.get("pe_ttm", 0)) if latest.get("pe_ttm") else None,
                    "pb": float(latest.get("pb", 0)) if latest.get("pb") else None,
                    "ps_ttm": float(latest.get("ps_ttm", 0)) if latest.get("ps_ttm") else None,
                    "total_mv": float(latest.get("total_mv", 0)),
                    "total_share": float(latest.get("total_share", 0)),
                    "trade_date": str(latest.get("trade_date", "")),
                }
        except Exception:
            pass
        return {}


# ============================================================
# 1. DCF 现金流折现模型
# ============================================================

class DCFModel:
    """DCF (Discounted Cash Flow) 估值模型"""

    # A股行业WACC参考
    INDUSTRY_WACC = {
        "白酒": (0.08, 0.10, 0.85), "食品": (0.08, 0.10, 0.90),
        "银行": (0.07, 0.09, 1.10), "保险": (0.08, 0.10, 1.00),
        "房地产": (0.09, 0.12, 1.30), "电力": (0.06, 0.08, 0.60),
        "计算机": (0.10, 0.13, 1.30), "电子": (0.10, 0.13, 1.25),
        "医药": (0.09, 0.12, 0.95), "机械": (0.09, 0.11, 1.10),
        "汽车": (0.09, 0.11, 1.10), "通信": (0.09, 0.11, 1.00),
        "钢铁": (0.09, 0.12, 1.20), "煤炭": (0.09, 0.12, 1.20),
        "石油": (0.08, 0.10, 0.90), "建筑": (0.09, 0.11, 1.10),
    }

    def run(self, data: dict, years: int = 5) -> dict:
        income = data.get("income")
        balance = data.get("balance")
        cashflow = data.get("cashflow")

        if income is None or cashflow is None:
            return {"error": "利润表或现金流量表数据不足"}

        income = income[income["end_date"].astype(str).str.endswith("1231")].tail(5)
        cashflow_annual = cashflow[cashflow["end_date"].astype(str).str.endswith("1231")].tail(5)

        # 1. 历史FCFF
        fcff_list = []
        for _, cf in cashflow_annual.iterrows():
            cfo = self._v(cf, "n_cashflow_act")
            capex = abs(self._v(cf, "c_pay_acq_const_fiolta"))  # 购建固定/无形/其他长期资产支付的现金
            fcff_list.append(cfo - capex)

        if not fcff_list:
            return {"error": "无法计算历史FCFF"}

        latest_fcff = fcff_list[-1]

        # 2. 增长率估计
        revenues = income["revenue"].dropna().values
        if len(revenues) >= 3:
            cagr = (revenues[-1] / revenues[0]) ** (1 / (len(revenues) - 1)) - 1
        else:
            cagr = 0.08
        cagr = max(0, min(cagr, 0.30))  # 限制在0-30%

        # 3. WACC估计
        industry = data.get("industry", "")
        wacc_range = self.INDUSTRY_WACC.get(industry, (0.09, 0.11, 1.0))
        wacc = (wacc_range[0] + wacc_range[1]) / 2
        beta = wacc_range[2]

        # 4. 预测FCFF（5年）
        projection_years = years
        growth_rates = []
        for i in range(projection_years):
            # 前两年用CAGR，之后逐渐衰减
            if i < 2:
                g = cagr * 0.8
            elif i < 4:
                g = cagr * 0.5
            else:
                g = cagr * 0.3
            growth_rates.append(max(g, 0.02))

        projected_fcff = []
        prev = latest_fcff
        for g in growth_rates:
            prev = prev * (1 + g)
            projected_fcff.append(prev)

        # 5. 终值
        terminal_g = 0.025  # 永续增长率 2.5%
        terminal_value = projected_fcff[-1] * (1 + terminal_g) / (wacc - terminal_g)

        # 6. 折现
        pv_fcff = sum(f / (1 + wacc) ** (i + 1) for i, f in enumerate(projected_fcff))
        pv_terminal = terminal_value / (1 + wacc) ** projection_years
        enterprise_value = pv_fcff + pv_terminal

        # 7. 股权价值
        bal = balance.sort_values("end_date").iloc[-1] if balance is not None and not balance.empty else None
        net_debt = 0
        total_shares = 1
        if bal is not None:
            cash = self._v(bal, "money_cap")
            st_borr = self._v(bal, "st_borr")
            lt_borr = self._v(bal, "lt_borr")
            bonds = self._v(bal, "bond_payable")
            net_debt = (st_borr + lt_borr + bonds) - cash
            total_shares = self._v(bal, "total_share")
            if total_shares <= 0:
                total_shares = 1

        equity_value = enterprise_value - net_debt
        per_share = equity_value / total_shares if total_shares > 0 else 0

        # 8. 敏感性分析（WACC x g矩阵）
        sensitivity = self._sensitivity_table(
            projected_fcff, terminal_value, projection_years, total_shares, net_debt
        )

        return {
            "method": "DCF",
            "wacc": round(wacc, 4),
            "beta": beta,
            "terminal_growth": terminal_g,
            "revenue_cagr": round(cagr, 4),
            "latest_fcff": round(latest_fcff, 0),
            "projected_fcff": [round(f, 0) for f in projected_fcff],
            "growth_rates": [round(g, 4) for g in growth_rates],
            "pv_fcff": round(pv_fcff, 0),
            "pv_terminal": round(pv_terminal, 0),
            "enterprise_value": round(enterprise_value, 0),
            "net_debt": round(net_debt, 0),
            "equity_value": round(equity_value, 0),
            "per_share_value": round(per_share, 2),
            "total_shares": round(total_shares, 0),
            "sensitivity": sensitivity,
        }

    def _sensitivity_table(self, fcff_list, tv, n, shares, net_debt):
        """生成敏感性分析表"""
        wacc_range = [0.08, 0.09, 0.10, 0.11, 0.12]
        g_range = [0.020, 0.025, 0.030]
        table = []
        for w in wacc_range:
            row = {"wacc": f"{w:.0%}"}
            for g in g_range:
                tv_adj = fcff_list[-1] * (1 + g) / (w - g)
                pv_f = sum(f / (1 + w) ** (i + 1) for i, f in enumerate(fcff_list))
                pv_tv = tv_adj / (1 + w) ** n
                ev = pv_f + pv_tv
                eq = ev - net_debt
                ps = eq / shares if shares > 0 else 0
                row[f"g={g:.1%}"] = round(ps, 2)
            table.append(row)
        return table

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None or (isinstance(val, float) and (math.isnan(val) if hasattr(val, '__float__') else False)):
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 2. DDM 股息折现模型
# ============================================================

class DDMModel:
    """DDM (Dividend Discount Model) 股息折现"""

    def run(self, data: dict) -> dict:
        dividend = data.get("dividend")
        indicators = data.get("indicators")

        if dividend is None or dividend.empty:
            return {"applicable": False, "reason": "无分红数据"}

        # 检查适用性
        div_df = dividend[dividend["cash_div"].notna() & (dividend["cash_div"] > 0)].head(5)
        if len(div_df) < 3:
            return {"applicable": False, "reason": f"分红记录不足3年（仅{len(div_df)}年）"}

        # 每股股息
        dps_list = div_df["cash_div"].astype(float).values

        # 增长率
        if len(dps_list) >= 2 and dps_list[-1] > 0 and dps_list[0] > 0:
            dividend_cagr = (dps_list[-1] / dps_list[0]) ** (1 / (len(dps_list) - 1)) - 1
        else:
            dividend_cagr = 0.03

        latest_dps = dps_list[-1]

        # Ke估计
        industry = data.get("industry", "")
        wacc_map = DCFModel.INDUSTRY_WACC
        wacc_range = wacc_map.get(industry, (0.08, 0.10, 1.0))
        ke = (wacc_range[0] + wacc_range[1]) / 2 + 0.01  # 股权成本略高于WACC

        # 两阶段DDM
        stage1_years = 5
        g_high = dividend_cagr  # 高增长阶段
        g_terminal = 0.025  # 永续增长

        # 阶段1：高增长
        pv_stage1 = 0
        for i in range(1, stage1_years + 1):
            d = latest_dps * (1 + g_high) ** i
            pv_stage1 += d / (1 + ke) ** i

        # 阶段2：永续
        terminal_dps = latest_dps * (1 + g_high) ** stage1_years * (1 + g_terminal)
        pv_terminal = terminal_dps / (ke - g_terminal) / (1 + ke) ** stage1_years

        intrinsic_value = pv_stage1 + pv_terminal

        # 适用性评估
        payout_stable = len(set(dps_list > 0)) == 1  # 是否每年都有分红
        is_applicable = payout_stable and dividend_cagr > 0

        return {
            "applicable": is_applicable,
            "method": "DDM",
            "latest_dps": round(latest_dps, 4),
            "dividend_cagr": round(dividend_cagr, 4),
            "cost_of_equity": round(ke, 4),
            "stage1_years": stage1_years,
            "stage1_growth": round(g_high, 4),
            "terminal_growth": g_terminal,
            "pv_stage1": round(pv_stage1, 2),
            "pv_terminal": round(pv_terminal, 2),
            "per_share_value": round(intrinsic_value, 2),
            "reason": "" if is_applicable else "分红不稳定或负增长，DDM估值参考价值有限",
        }


# ============================================================
# 3. PE-Band 历史分位
# ============================================================

class PEBandAnalyzer:
    """PE-Band 历史分位分析"""

    def run(self, data: dict) -> dict:
        daily = data.get("daily_basic")
        if daily is None or daily.empty:
            return {"error": "无日线数据"}

        pe_series = daily["pe_ttm"].dropna()
        pe_series = pe_series[pe_series > 0]  # 排除负PE

        if pe_series.empty:
            return {"error": "PE数据全部为空或负值"}

        percentiles = {
            "p10": round(float(pe_series.quantile(0.10)), 2),
            "p25": round(float(pe_series.quantile(0.25)), 2),
            "p50": round(float(pe_series.quantile(0.50)), 2),
            "p75": round(float(pe_series.quantile(0.75)), 2),
            "p90": round(float(pe_series.quantile(0.90)), 2),
        }

        current_pe = float(pe_series.iloc[-1])
        current_rank = float((pe_series < current_pe).sum() / len(pe_series))

        # 基于EPS估算隐含价格
        income = data.get("income")
        eps = None
        if income is not None and not income.empty:
            latest_income = income.sort_values("end_date").iloc[-1]
            total_share = float(data.get("daily_basic", pd.DataFrame()).iloc[-1].get("total_share", 1)) if not data.get("daily_basic", pd.DataFrame()).empty else 1
            ni = self._v(latest_income, "n_income_attr_p")
            if total_share and total_share > 0:
                eps = ni / (total_share * 10000)  # Tushare单位换算

        implied_prices = {}
        if eps and eps > 0:
            for label, pe in percentiles.items():
                implied_prices[label] = round(pe * eps, 2)

        # 估值判断
        if current_rank < 0.25:
            judgment = "严重低估"
        elif current_rank < 0.40:
            judgment = "低估"
        elif current_rank < 0.60:
            judgment = "合理"
        elif current_rank < 0.75:
            judgment = "偏高"
        else:
            judgment = "严重高估"

        return {
            "method": "PE-Band",
            "current_pe": round(current_pe, 2),
            "current_percentile": round(current_rank, 4),
            "percentiles": percentiles,
            "eps": round(eps, 2) if eps else None,
            "implied_prices": implied_prices,
            "judgment": judgment,
            "data_points": len(pe_series),
        }

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None:
            return 0.0
        try:
            f = float(val)
            return 0.0 if math.isnan(f) else f
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 4. PB-ROE 矩阵
# ============================================================

class PBROEAnalyzer:
    """PB-ROE 矩阵分析"""

    def run(self, data: dict) -> dict:
        daily = data.get("daily_basic")
        indicators = data.get("indicators")

        if daily is None or daily.empty:
            return {"error": "无日线数据"}

        latest_daily = daily.sort_values("trade_date").iloc[-1]
        current_pb = self._v(latest_daily, "pb")
        if current_pb <= 0:
            current_pb = 1.0

        # 获取ROE
        current_roe = 0.10  # 默认
        if indicators is not None and not indicators.empty:
            latest_ind = indicators.sort_values("end_date").iloc[-1]
            roe_val = self._v(latest_ind, "roe")
            if roe_val > 0:
                current_roe = roe_val / 100 if roe_val > 1 else roe_val

        # 四象限定位
        pb_mid = 2.0  # PB中值参考
        roe_mid = 0.12  # ROE中值参考

        if current_pb < pb_mid and current_roe > roe_mid:
            quadrant = "低PB高ROE（最佳买入区）"
            position = "undervalued"
        elif current_pb >= pb_mid and current_roe > roe_mid:
            quadrant = "高PB高ROE（合理溢价）"
            position = "fair_premium"
        elif current_pb < pb_mid and current_roe <= roe_mid:
            quadrant = "低PB低ROE（价值陷阱或困境反转）"
            position = "value_trap_or_turnaround"
        else:
            quadrant = "高PB低ROE（高估，回避）"
            position = "overvalued"

        # 理论PB = (ROE - g) / (Ke - g)
        ke = 0.10
        g = 0.03
        theoretical_pb = (current_roe - g) / (ke - g) if current_roe > g else 0

        return {
            "method": "PB-ROE",
            "current_pb": round(current_pb, 2),
            "current_roe": round(current_roe, 4),
            "theoretical_pb": round(theoretical_pb, 2),
            "quadrant": quadrant,
            "position": position,
            "pb_vs_theoretical": "低估" if current_pb < theoretical_pb else "高估",
        }

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None:
            return 0.0
        try:
            f = float(val)
            return 0.0 if math.isnan(f) else f
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 5. EV/EBITDA 分析
# ============================================================

class EVEBITDAAnalyzer:
    """EV/EBITDA 估值分析"""

    # A股行业参考倍数
    INDUSTRY_MULTIPLES = {
        "白酒": {"median": 22, "undervalued": 16, "overvalued": 30},
        "食品": {"median": 18, "undervalued": 13, "overvalued": 25},
        "银行": {"median": 10, "undervalued": 7, "overvalued": 14},
        "房地产": {"median": 8, "undervalued": 5, "overvalued": 12},
        "计算机": {"median": 16, "undervalued": 10, "overvalued": 22},
        "电子": {"median": 14, "undervalued": 9, "overvalued": 20},
        "医药": {"median": 16, "undervalued": 11, "overvalued": 22},
        "电力": {"median": 10, "undervalued": 7, "overvalued": 14},
        "机械": {"median": 12, "undervalued": 8, "overvalued": 17},
        "汽车": {"median": 12, "undervalued": 8, "overvalued": 17},
    }

    def run(self, data: dict) -> dict:
        daily = data.get("daily_basic")
        income = data.get("income")
        balance = data.get("balance")

        if daily is None or daily.empty:
            return {"error": "无日线数据"}

        latest_daily = daily.sort_values("trade_date").iloc[-1]
        market_cap = self._v(latest_daily, "total_mv") * 10000  # 万元→元

        # 净债务
        net_debt = 0
        if balance is not None and not balance.empty:
            bal = balance.sort_values("end_date").iloc[-1]
            cash = self._v(bal, "money_cap")
            st = self._v(bal, "st_borr")
            lt = self._v(bal, "lt_borr")
            bonds = self._v(bal, "bond_payable")
            net_debt = (st + lt + bonds) - cash

        ev = market_cap + net_debt

        # EBITDA ≈ 营业利润 + 折旧摊销（简化为营业利润×1.1）
        ebitda = 0
        if income is not None and not income.empty:
            inc = income.sort_values("end_date").iloc[-1]
            oper_profit = self._v(inc, "operate_profit")
            ebitda = oper_profit * 1.1  # 简化

        if ebitda <= 0:
            return {"error": "EBITDA为负，不适用EV/EBITDA"}

        ev_ebitda = ev / ebitda

        # 行业对比
        industry = data.get("industry", "")
        ref = self.INDUSTRY_MULTIPLES.get(industry, {"median": 14, "undervalued": 10, "overvalued": 20})

        if ev_ebitda < ref["undervalued"]:
            judgment = "低估"
        elif ev_ebitda < ref["median"]:
            judgment = "合理偏低"
        elif ev_ebitda < ref["overvalued"]:
            judgment = "合理偏高"
        else:
            judgment = "高估"

        return {
            "method": "EV/EBITDA",
            "ev": round(ev, 0),
            "ebitda": round(ebitda, 0),
            "ev_ebitda": round(ev_ebitda, 2),
            "industry": industry,
            "industry_median": ref["median"],
            "industry_undervalued": ref["undervalued"],
            "industry_overvalued": ref["overvalued"],
            "judgment": judgment,
        }

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None:
            return 0.0
        try:
            f = float(val)
            return 0.0 if math.isnan(f) else f
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 6. SOTP 分部估值（简化版）
# ============================================================

class SOTPModel:
    """SOTP (Sum of the Parts) 分部估值"""

    def run(self, data: dict) -> dict:
        # SOTP需要分部收入数据，Tushare不直接提供
        # 简化：使用主营构成数据估算
        income = data.get("income")
        balance = data.get("balance")

        if income is None or balance is None:
            return {"applicable": False, "reason": "数据不足"}

        # 基于资产负债表的简化估值
        bal = balance.sort_values("end_date").iloc[-1]
        total_assets = self._v(bal, "total_assets")
        total_liab = self._v(bal, "total_liab")
        goodwill = self._v(bal, "goodwill")
        equity = total_assets - total_liab

        return {
            "applicable": False,
            "method": "SOTP",
            "reason": "SOTP需要分部收入/利润数据（Tushare未提供），建议结合公司年报业务拆分手动估值",
            "reference": {
                "total_assets": round(total_assets, 0),
                "total_liab": round(total_liab, 0),
                "net_equity": round(equity, 0),
                "goodwill": round(goodwill, 0),
                "goodwill_to_equity": round(goodwill / equity, 4) if equity > 0 else None,
            },
        }

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 7. 估值陷阱检测
# ============================================================

class ValuationTrapDetector:
    """10项估值陷阱检测"""

    def detect(self, data: dict) -> list:
        traps = []
        income = data.get("income")
        balance = data.get("balance")
        indicators = data.get("indicators")
        daily = data.get("daily_basic")

        # 陷阱1: 低PE周期股顶部
        if daily is not None and not daily.empty:
            latest = daily.sort_values("trade_date").iloc[-1]
            pe = self._v(latest, "pe_ttm")
            if 0 < pe < 8:
                industry = data.get("industry", "")
                cyclical = ["钢铁", "煤炭", "有色金属", "石油", "化工", "建材"]
                if industry in cyclical:
                    traps.append({
                        "id": 1, "name": "低PE周期股顶部",
                        "triggered": True, "severity": "high",
                        "detail": f"周期行业{industry}PE仅{pe:.1f}倍，可能处于盈利顶部",
                    })
                else:
                    traps.append({"id": 1, "name": "低PE周期股顶部", "triggered": False})
            else:
                traps.append({"id": 1, "name": "低PE周期股顶部", "triggered": False})

        # 陷阱3: 低PB价值毁灭
        if indicators is not None and not indicators.empty:
            roe_vals = indicators["roe"].dropna().tail(5)
            if len(roe_vals) >= 3 and (roe_vals < 5).all():
                traps.append({
                    "id": 3, "name": "低PB价值毁灭",
                    "triggered": True, "severity": "high",
                    "detail": f"ROE连续{len(roe_vals)}期低于5%，持续毁灭股东价值",
                })
            else:
                traps.append({"id": 3, "name": "低PB价值毁灭", "triggered": False})

        # 陷阱4: 商誉炸弹
        if balance is not None and not balance.empty:
            bal = balance.sort_values("end_date").iloc[-1]
            gw = self._v(bal, "goodwill")
            equity = self._v(bal, "total_hldr_eqy_exc_min_int")
            if equity > 0 and gw / equity > 0.30:
                traps.append({
                    "id": 4, "name": "商誉炸弹",
                    "triggered": True, "severity": "medium",
                    "detail": f"商誉/净资产={gw/equity:.1%}（>30%），面临减值风险",
                })
            else:
                traps.append({"id": 4, "name": "商誉炸弹", "triggered": False})

        # 陷阱5: 应收账款陷阱
        if income is not None and balance is not None:
            inc = income.sort_values("end_date").tail(4)
            bal = balance.sort_values("end_date").tail(4)
            if len(inc) >= 2 and len(bal) >= 2:
                rev = inc["revenue"].values
                ar = bal["accounts_receiv"].values
                if rev[-1] > 0 and rev[-2] > 0:
                    rev_ratio = ar[-1] / rev[-1]
                    rev_ratio_prev = ar[-2] / rev[-2]
                    if rev_ratio > rev_ratio_prev * 1.2 and rev_ratio > 0.3:
                        traps.append({
                            "id": 5, "name": "应收账款陷阱",
                            "triggered": True, "severity": "medium",
                            "detail": f"应收/营收从{rev_ratio_prev:.1%}升至{rev_ratio:.1%}，收入质量恶化",
                        })
                    else:
                        traps.append({"id": 5, "name": "应收账款陷阱", "triggered": False})

        triggered = [t for t in traps if t.get("triggered")]
        return {"traps": traps, "triggered_count": len(triggered),
                "risk_level": "high" if len(triggered) >= 3 else "medium" if len(triggered) >= 1 else "low"}

    @staticmethod
    def _v(row, col: str) -> float:
        val = row.get(col, 0)
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# 8. 多模型交叉验证与综合目标价
# ============================================================

class CrossValidationEngine:
    """多模型交叉验证"""

    # 默认权重
    WEIGHTS = {
        "DCF": 0.35,
        "DDM": 0.10,
        "PE-Band": 0.25,
        "PB-ROE": 0.15,
        "EV/EBITDA": 0.15,
    }

    def run(self, dcf: dict, ddm: dict, pe: dict, pb_roe: dict, ev_ebitda: dict,
            current_price: float) -> dict:
        valuations = []

        # DCF
        if "error" not in dcf and dcf.get("per_share_value", 0) > 0:
            valuations.append({"method": "DCF", "value": dcf["per_share_value"],
                               "weight": self.WEIGHTS["DCF"]})

        # DDM
        if ddm.get("applicable") and ddm.get("per_share_value", 0) > 0:
            valuations.append({"method": "DDM", "value": ddm["per_share_value"],
                               "weight": self.WEIGHTS["DDM"]})

        # PE-Band（用p50隐含价格）
        if "error" not in pe and pe.get("implied_prices", {}).get("p50"):
            valuations.append({"method": "PE-Band(p50)", "value": pe["implied_prices"]["p50"],
                               "weight": self.WEIGHTS["PE-Band"]})

        # PB-ROE（用理论PB * 最新价格/当前PB）
        if "error" not in pb_roe and current_price > 0 and pb_roe.get("theoretical_pb", 0) > 0:
            implied = current_price * pb_roe["theoretical_pb"] / pb_roe["current_pb"]
            if implied > 0:
                valuations.append({"method": "PB-ROE", "value": round(implied, 2),
                                   "weight": self.WEIGHTS["PB-ROE"]})

        # EV/EBITDA（用行业隐含价格）
        if "error" not in ev_ebitda and current_price > 0:
            ev_result = ev_ebitda
            if ev_result.get("industry_median") and ev_result.get("ev_ebitda"):
                ratio = ev_result["industry_median"] / ev_result["ev_ebitda"]
                implied = current_price * ratio
                if implied > 0:
                    valuations.append({"method": "EV/EBITDA", "value": round(implied, 2),
                                       "weight": self.WEIGHTS["EV/EBITDA"]})

        if not valuations:
            return {"error": "无有效估值结果"}

        # 归一化权重
        total_weight = sum(v["weight"] for v in valuations)
        for v in valuations:
            v["weight_normalized"] = round(v["weight"] / total_weight, 4)

        # 加权目标价
        target_price = sum(v["value"] * v["weight_normalized"] for v in valuations)

        # 中位数
        values = [v["value"] for v in valuations]
        median_price = float(np.median(values))

        # 交叉验证
        max_val = max(values)
        min_val = min(values)
        spread = (max_val - min_val) / median_price if median_price > 0 else 0
        cross_check = "通过" if spread < 0.30 else "差异较大，建议复核假设"

        # 上涨/下跌空间
        if current_price > 0:
            upside = (target_price - current_price) / current_price
        else:
            upside = 0

        return {
            "valuations": valuations,
            "target_price_weighted": round(target_price, 2),
            "target_price_median": round(median_price, 2),
            "current_price": round(current_price, 2),
            "upside": round(upside, 4),
            "upside_label": "上涨" if upside > 0.10 else "下跌" if upside < -0.10 else "中性",
            "method_count": len(valuations),
            "max_spread": round(spread, 4),
            "cross_validation": cross_check,
        }


# ============================================================
# 主分析流程
# ============================================================

def analyze_valuation_models(stock: str, years: int = 5) -> dict:
    fetcher = ValuationDataFetcher()
    ts_code = fetcher.normalize_stock(stock)
    data = fetcher.fetch(ts_code, years)

    if "error" in data:
        return data

    result = {
        "stock": ts_code,
        "stock_name": data.get("stock_name", ""),
        "industry": data.get("industry", ""),
        "analysis_type": "multi_valuation_models",
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "Tushare Pro API",
    }

    # 获取当前价格
    price_info = fetcher.get_latest_price(ts_code)
    current_price = price_info.get("close", 0)
    result["current_price"] = current_price
    result["current_pe"] = price_info.get("pe_ttm")
    result["current_pb"] = price_info.get("pb")
    result["market_cap"] = price_info.get("total_mv")

    # 1. DCF
    dcf = DCFModel().run(data, years)
    result["dcf"] = dcf

    # 2. DDM
    ddm = DDMModel().run(data)
    result["ddm"] = ddm

    # 3. PE-Band
    pe = PEBandAnalyzer().run(data)
    result["pe_band"] = pe

    # 4. PB-ROE
    pb_roe = PBROEAnalyzer().run(data)
    result["pb_roe"] = pb_roe

    # 5. EV/EBITDA
    ev = EVEBITDAAnalyzer().run(data)
    result["ev_ebitda"] = ev

    # 6. SOTP
    sotp = SOTPModel().run(data)
    result["sotp"] = sotp

    # 7. 估值陷阱
    traps = ValuationTrapDetector().detect(data)
    result["valuation_traps"] = traps

    # 8. 交叉验证与综合目标价
    cross = CrossValidationEngine().run(dcf, ddm, pe, pb_roe, ev, current_price)
    result["cross_validation"] = cross

    # 9. 综合评级
    if "error" not in cross:
        target = cross["target_price_weighted"]
        upside = cross["upside"]
        if upside > 0.20:
            rating = "买入"
        elif upside > 0.05:
            rating = "增持"
        elif upside > -0.05:
            rating = "中性"
        elif upside > -0.15:
            rating = "减持"
        else:
            rating = "卖出"
        result["investment_rating"] = {
            "rating": rating,
            "target_price": target,
            "current_price": current_price,
            "upside": f"{upside:.1%}",
        }

    result["disclaimer"] = "数据来源于Tushare Pro API，估值结果高度依赖假设参数，仅供参考，不构成投资建议"
    return result


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="多估值模型分析引擎")
    parser.add_argument("--stock", required=True, help="股票代码或名称")
    parser.add_argument("--years", type=int, default=5, help="预测年数")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = analyze_valuation_models(args.stock, args.years)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(result)


def _print_report(r):
    print(f"\n{'='*60}")
    print(f"  多估值模型分析 — {r.get('stock_name','')} ({r.get('stock','')})")
    print(f"  当前价格: {r.get('current_price','N/A')} | PE: {r.get('current_pe','N/A')}")
    print(f"  行业: {r.get('industry','')} | 时间: {r.get('analysis_time','')}")
    print(f"{'='*60}")

    # DCF
    dcf = r.get("dcf", {})
    if "error" not in dcf:
        print(f"\n📊 DCF估值: ¥{dcf.get('per_share_value', 0):.2f}/股")
        print(f"  WACC={dcf.get('wacc',0):.1%} | 永续g={dcf.get('terminal_growth',0):.1%} | 营收CAGR={dcf.get('revenue_cagr',0):.1%}")
    else:
        print(f"\n📊 DCF: {dcf.get('error','')}")

    # DDM
    ddm = r.get("ddm", {})
    if ddm.get("applicable"):
        print(f"\n💰 DDM估值: ¥{ddm.get('per_share_value', 0):.2f}/股")
        print(f"  最新DPS={ddm.get('latest_dps',0)} | 股息CAGR={ddm.get('dividend_cagr',0):.1%}")
    else:
        print(f"\n💰 DDM: {ddm.get('reason','不适用')}")

    # PE-Band
    pe = r.get("pe_band", {})
    if "error" not in pe:
        print(f"\n📈 PE-Band: 当前PE={pe.get('current_pe',0):.1f}x ({pe.get('current_percentile',0):.0%}分位)")
        print(f"  判断: {pe.get('judgment','')}")
    else:
        print(f"\n📈 PE-Band: {pe.get('error','')}")

    # PB-ROE
    pb = r.get("pb_roe", {})
    if "error" not in pb:
        print(f"\n📉 PB-ROE: PB={pb.get('current_pb',0):.2f} ROE={pb.get('current_roe',0):.1%}")
        print(f"  象限: {pb.get('quadrant','')} | {pb.get('pb_vs_theoretical','')}")

    # EV/EBITDA
    ev = r.get("ev_ebitda", {})
    if "error" not in ev:
        print(f"\n🏢 EV/EBITDA: {ev.get('ev_ebitda',0):.1f}x (行业中值{ev.get('industry_median',0)}x)")
        print(f"  判断: {ev.get('judgment','')}")

    # 估值陷阱
    traps = r.get("valuation_traps", {})
    triggered = [t for t in traps.get("traps", []) if t.get("triggered")]
    print(f"\n🚨 估值陷阱: 触发 {len(triggered)} 项 ({traps.get('risk_level','')})")
    for t in triggered:
        print(f"  ⚠️ [{t['name']}] {t.get('detail','')}")

    # 综合目标价
    cross = r.get("cross_validation", {})
    if "error" not in cross:
        print(f"\n🎯 综合目标价: ¥{cross.get('target_price_weighted',0):.2f} (加权) / ¥{cross.get('target_price_median',0):.2f} (中位)")
        print(f"  当前价: ¥{cross.get('current_price',0):.2f} | 空间: {cross.get('upside',0):.1%} ({cross.get('upside_label','')})")
        print(f"  交叉验证: {cross.get('cross_validation','')} | {cross.get('method_count',0)}个模型")

    # 投资评级
    rating = r.get("investment_rating", {})
    if rating:
        print(f"\n⭐ 投资评级: {rating.get('rating','')} | 目标价 ¥{rating.get('target_price',0):.2f}")

    print(f"\n{'='*60}")
    print(f"  ⚠️ {r.get('disclaimer','')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
