#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KWorks 金融数据网关。

分析技能只依赖本模块定义的稳定接口，不直接初始化 Tushare 或访问
``pro_api``。当前适配器复用 common 的兼容客户端；后续替换为官方
``tushare-data`` 运行时实现时，分析技能无需改动。

数据访问边界（强制）：
  - 唯一允许直接 ``import tushare`` 的位置是 ``tushare-data`` 官方适配包
    与本仓库 ``kk_common.tushare_client`` 的实现内部。
  - 其余分析脚本一律通过 ``get_finance_data_gateway()`` 或
    ``get_tushare_client()`` 访问，禁止 ``import tushare`` / ``ts.pro_api()``。
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

import pandas as pd

from kk_common import market_data_cache
from kk_common.tushare_client import TushareClient, get_tushare_client


def _as_dataframe(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, list):
        return pd.DataFrame(value)
    try:
        return pd.DataFrame(value)
    except Exception:
        return pd.DataFrame()


class FinanceDataAdapter(Protocol):
    def request(self, endpoint: str, **kwargs: Any) -> pd.DataFrame:
        ...


class TushareDataAdapter:
    """将官方 Tushare 数据请求收敛到一个可替换适配器。"""

    def __init__(self, client: Optional[TushareClient] = None):
        self.client = client or get_tushare_client()

    def request(self, endpoint: str, **kwargs: Any) -> pd.DataFrame:
        """调用已封装接口，缺少封装时调用官方 ``pro`` 接口。

        ``fut_mapping`` 等接口仍可能因上游客户端版本差异未被兼容层
        封装，因此只允许通过此适配器访问原始官方接口。
        """
        method = getattr(self.client, endpoint, None)
        if callable(method):
            try:
                return _as_dataframe(method(**kwargs))
            except Exception:
                return pd.DataFrame()

        pro = getattr(self.client, "pro", None)
        method = getattr(pro, endpoint, None) if pro is not None else None
        if not callable(method):
            return pd.DataFrame()
        try:
            return _as_dataframe(method(**kwargs))
        except Exception:
            return pd.DataFrame()


class FinanceDataGateway:
    """金融技能统一数据入口。

    方法名与 Tushare 官方接口保持一致，方便分析器表达数据意图；实现
    由 ``FinanceDataAdapter`` 注入，单元测试和产品运行时均可替换。
    """

    def __init__(self, adapter: Optional[FinanceDataAdapter] = None):
        self.adapter = adapter or TushareDataAdapter()

    def request(self, endpoint: str, **kwargs: Any) -> pd.DataFrame:
        # KStock patch: 白名单接口过本地磁盘缓存（增量合并，跨任务复用），
        # 其余接口直连。详见 kk_common.market_data_cache 模块头注释。
        if market_data_cache.handles(endpoint):
            return market_data_cache.wrap_request(
                endpoint, kwargs,
                lambda p: _as_dataframe(self.adapter.request(endpoint, **p)),
            )
        return _as_dataframe(self.adapter.request(endpoint, **kwargs))

    # ── 股票基础 / 行情 ───────────────────────────────────────────────
    def stock_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("stock_basic", **kwargs)

    def trade_cal(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("trade_cal", **kwargs)

    def daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("daily", **kwargs)

    def daily_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("daily_basic", **kwargs)

    def weekly(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("weekly", **kwargs)

    def monthly(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("monthly", **kwargs)

    def stk_mins(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("stk_mins", **kwargs)

    def pro_bar(self, **kwargs: Any) -> pd.DataFrame:
        """复权行情（Tushare 顶层便捷函数，支持 qfq/hfq）。"""
        return self.request("pro_bar", **kwargs)

    def namechange(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("namechange", **kwargs)

    def hs_const(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("hs_const", **kwargs)

    # ── 财务 / 公司质量 ───────────────────────────────────────────────
    def income(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("income", **kwargs)

    def balancesheet(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("balancesheet", **kwargs)

    def cashflow(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("cashflow", **kwargs)

    def fina_indicator(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fina_indicator", **kwargs)

    def fina_mainbz(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fina_mainbz", **kwargs)

    def dividend(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("dividend", **kwargs)

    # ── 股东 ─────────────────────────────────────────────────────────
    def stk_holdertrade(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("stk_holdertrade", **kwargs)

    def stk_holdernumber(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("stk_holdernumber", **kwargs)

    def top10_holders(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("top10_holders", **kwargs)

    def top10_floatholders(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("top10_floatholders", **kwargs)

    def stk_surv(self, **kwargs: Any) -> pd.DataFrame:
        """机构调研明细（Tushare stk_surv）。"""
        return self.request("stk_surv", **kwargs)

    # ── 公司 / 事件 ──────────────────────────────────────────────────
    def stock_company(self, **kwargs: Any) -> pd.DataFrame:
        """上市公司基本信息（董事长/主营/员工等，Tushare stock_company）。"""
        return self.request("stock_company", **kwargs)

    def report_rc(self, **kwargs: Any) -> pd.DataFrame:
        """业绩快报（Tushare report_rc）。"""
        return self.request("report_rc", **kwargs)

    # ── 筹码 / 资金 ──────────────────────────────────────────────────
    def cyq_chips(self, **kwargs: Any) -> pd.DataFrame:
        """每日筹码分布（Tushare cyq_chips）。"""
        return self.request("cyq_chips", **kwargs)

    # ── 指数 / 板块 ──────────────────────────────────────────────────
    def index_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("index_basic", **kwargs)

    def index_daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("index_daily", **kwargs)

    def index_weight(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("index_weight", **kwargs)

    def index_member(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("index_member", **kwargs)

    def sw_daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("sw_daily", **kwargs)

    def industry(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("industry", **kwargs)

    # ── 资金流 / 情绪 ────────────────────────────────────────────────
    def moneyflow(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("moneyflow", **kwargs)

    def moneyflow_dc(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("moneyflow_dc", **kwargs)

    def moneyflow_ind_ths(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("moneyflow_ind_ths", **kwargs)

    def moneyflow_hsgt(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("moneyflow_hsgt", **kwargs)

    def hsgt(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("hsgt", **kwargs)

    def hsgt_top10(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("hsgt_top10", **kwargs)

    def margin(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("margin", **kwargs)

    def margin_detail(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("margin_detail", **kwargs)

    def top_list(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("top_list", **kwargs)

    def top_inst(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("top_inst", **kwargs)

    def limit_list(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("limit_list", **kwargs)

    def limit_list_d(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("limit_list_d", **kwargs)

    # ── 基金 / ETF ───────────────────────────────────────────────────
    def fund_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_basic", **kwargs)

    def fund_daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_daily", **kwargs)

    def fund_share(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_share", **kwargs)

    def fund_nav(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_nav", **kwargs)

    def fund_div(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_div", **kwargs)

    def fund_manager(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_manager", **kwargs)

    def fund_portfolio(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fund_portfolio", **kwargs)

    # ── 期货 / 期权 ──────────────────────────────────────────────────
    def fut_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fut_basic", **kwargs)

    def fut_daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fut_daily", **kwargs)

    def fut_holding(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fut_holding", **kwargs)

    def fut_wm(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fut_wm", **kwargs)

    def fut_mapping(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("fut_mapping", **kwargs)

    def opt_basic(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("opt_basic", **kwargs)

    def opt_daily(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("opt_daily", **kwargs)

    # ── 宏观 / 利率 ──────────────────────────────────────────────────
    def shibor(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("shibor", **kwargs)

    def shibor_lpr(self, **kwargs: Any) -> pd.DataFrame:
        return self.request("shibor_lpr", **kwargs)


_finance_data_gateway: Optional[FinanceDataGateway] = None


def get_finance_data_gateway() -> FinanceDataGateway:
    global _finance_data_gateway
    if _finance_data_gateway is None:
        _finance_data_gateway = FinanceDataGateway()
    return _finance_data_gateway


def reset_finance_data_gateway(gateway: Optional[FinanceDataGateway] = None) -> None:
    global _finance_data_gateway
    _finance_data_gateway = gateway
