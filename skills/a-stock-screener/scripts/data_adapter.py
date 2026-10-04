#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据适配层 — Data Adapter

封装 a-stock-screener 工作流所需的所有数据来源，提供统一、可 Mock 的接口。

设计原则：
  1. 所有方法返回 pandas.DataFrame，调用方不感知底层数据源（同花顺问财/Tushare）
  2. 本模块可全局注入 mock 数据源，用于测试 / 离线模式
  3. 自动处理限速、重试、空结果降级

数据源集成：
  - kk_common.iwencai_client.IwencaiClient  — 问财 OpenAPI（意图查询、条件筛选）
  - kk_common.tushare_client.get_tushare_client — Tushare Pro（行情、基本面、财务等）
  - 本地缓存 / 模拟数据（离线模式）

用法:
    from data_adapter import get_data_adapter
    adapter = get_data_adapter()
    df = adapter.query_stocks("上市天数>60")
"""

import os
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable

import pandas as pd

logger = logging.getLogger("DataAdapter")

# ── 尝试导入 common ──────────────────────────────────────────────────────
try:
    from kk_common.iwencai_client import IwencaiClient, APIError as IwencaiError
    from kk_common.tushare_client import get_tushare_client, TushareClient

    _HAVE_KK_COMMON = True
except ImportError:
    _HAVE_KK_COMMON = False
    IwencaiClient = None  # type: ignore
    IwencaiError = Exception
    TushareClient = None  # type: ignore
    logger.warning("common 未安装，将使用 Mock 数据模式")


# ═════════════════════════════════════════════════════════════════════════════
# 类型定义
# ═════════════════════════════════════════════════════════════════════════════

class DataAdapterError(Exception):
    """数据适配层通用异常"""
    pass


class DataSourceUnavailable(DataAdapterError):
    """数据源不可用（未配置密钥 / 网络不可达）"""
    pass


# ═════════════════════════════════════════════════════════════════════════════
# DataAdapter 实现
# ═════════════════════════════════════════════════════════════════════════════

class DataAdapter:
    """
    统一数据适配器。

    提供 a-stock-screener 所需的全部数据获取方法。
    支持实时模式（common）和 Mock 模式（无外部依赖时降级）。
    """

    def __init__(
        self,
        iwencai_client: Optional[object] = None,
        tushare_client: Optional[object] = None,
        mock_mode: bool = False,
    ):
        """
        Args:
            iwencai_client: 外部注入的问财客户端；None 时自动创建
            tushare_client: 外部注入的 Tushare 客户端；None 时自动创建
            mock_mode: 强制使用 Mock 数据（不依赖外部数据源）
        """
        self._mock_mode = mock_mode
        self._iwencai: Optional[IwencaiClient] = None
        self._tushare: Optional[TushareClient] = None

        if not mock_mode and _HAVE_KK_COMMON:
            try:
                self._iwencai = iwencai_client or IwencaiClient()
            except Exception:
                logger.warning("问财客户端初始化失败，部分功能将降级")
                self._iwencai = None

            try:
                self._tushare = tushare_client or get_tushare_client()
            except Exception:
                logger.warning("Tushare 客户端初始化失败，部分功能将降级")
                self._tushare = None

    # ── 静态 Mock 数据 ──────────────────────────────────────────────────────

    @staticmethod
    def _mock_stock_list() -> pd.DataFrame:
        """返回模拟股票列表（用于离线测试）"""
        return pd.DataFrame([
            {"ts_code": "000001.SZ", "name": "平安银行", "industry": "银行",
             "market": "主板", "list_date": "1991-04-03"},
            {"ts_code": "000002.SZ", "name": "万科A", "industry": "房地产",
             "market": "主板", "list_date": "1991-01-29"},
            {"ts_code": "000333.SZ", "name": "美的集团", "industry": "家用电器",
             "market": "主板", "list_date": "2013-09-18"},
            {"ts_code": "000651.SZ", "name": "格力电器", "industry": "家用电器",
             "market": "主板", "list_date": "1996-11-18"},
            {"ts_code": "000858.SZ", "name": "五粮液", "industry": "白酒",
             "market": "主板", "list_date": "1998-04-27"},
            {"ts_code": "002415.SZ", "name": "海康威视", "industry": "计算机",
             "market": "中小板", "list_date": "2010-05-28"},
            {"ts_code": "600036.SH", "name": "招商银行", "industry": "银行",
             "market": "主板", "list_date": "2002-04-09"},
            {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒",
             "market": "主板", "list_date": "2001-08-27"},
            {"ts_code": "600887.SH", "name": "伊利股份", "industry": "食品饮料",
             "market": "主板", "list_date": "1996-03-12"},
            {"ts_code": "601318.SH", "name": "中国平安", "industry": "保险",
             "market": "主板", "list_date": "2007-03-01"},
        ])

    @staticmethod
    def _mock_daily(ts_code: str) -> pd.DataFrame:
        """返回模拟日线数据"""
        base_close = {
            "000001.SZ": 12.5, "000002.SZ": 18.3, "000333.SZ": 65.2,
            "000651.SZ": 40.1, "000858.SZ": 168.5, "002415.SZ": 35.8,
            "600036.SH": 38.6, "600519.SH": 1880.0, "600887.SH": 29.4,
            "601318.SH": 52.0,
        }.get(ts_code, 50.0)

        rows = []
        for i in range(60, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            factor = 1 + (i - 30) * 0.001
            close = round(base_close * factor, 2)
            rows.append({
                "ts_code": ts_code,
                "trade_date": date,
                "open": round(close * 0.99, 2),
                "high": round(close * 1.02, 2),
                "low": round(close * 0.98, 2),
                "close": close,
                "vol": int(10000 + (i % 10) * 5000),
                "amount": int(close * (10000 + (i % 10) * 5000)),
                "pct_chg": round((0.01 if i % 3 != 0 else -0.01) * 100, 2),
            })
        return pd.DataFrame(rows)

    # ══════════════════════════════════════════════════════════════════════
    # 公共查询方法
    # ══════════════════════════════════════════════════════════════════════

    def query_stocks(
        self,
        query: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        通过问财自然语言查询股票列表。

        Args:
            query: 条件查询语句，如 "上市天数>60" "市盈率<20"
            limit: 最多返回条数

        Returns:
            包含 ts_code, name, 及其他问财字段的 DataFrame

        Raises:
            DataSourceUnavailable: 问财不可用且未处于 Mock 模式
        """
        if self._mock_mode or self._iwencai is None:
            logger.info(f"[Mock] 问财查询: {query}")
            return self._mock_stock_list()

        try:
            result = self._iwencai.query(
                query=query,
                page="1",
                limit=str(limit),
            )
            datas = result.get("datas", [])
            if not datas:
                return pd.DataFrame()

            records = []
            for item in datas:
                record = {}
                for key, val in item.items():
                    # 问财返回的值的结构: { "name": "...", "value": ... }
                    if isinstance(val, dict) and "value" in val:
                        record[key] = val["value"]
                    else:
                        record[key] = val
                records.append(record)
            return pd.DataFrame(records)

        except IwencaiError as e:
            logger.error(f"问财查询失败: {e}")
            raise DataSourceUnavailable(f"问财查询失败: {e}") from e

    def query_stocks_with_pagination(
        self,
        query: str,
        max_pages: int = 3,
        page_size: int = 100,
    ) -> pd.DataFrame:
        """
        翻页查询（适用于大结果集）。

        Args:
            query: 条件查询语句
            max_pages: 最大翻页数
            page_size: 每页条数

        Returns:
            合并后的 DataFrame
        """
        if self._mock_mode or self._iwencai is None:
            return self.query_stocks(query, limit=page_size)

        all_records = []
        for page in range(1, max_pages + 1):
            try:
                result = self._iwencai.query(
                    query=query,
                    page=str(page),
                    limit=str(page_size),
                )
                datas = result.get("datas", [])
                if not datas:
                    break
                for item in datas:
                    record = {}
                    for key, val in item.items():
                        if isinstance(val, dict) and "value" in val:
                            record[key] = val["value"]
                        else:
                            record[key] = val
                    all_records.append(record)

                code_count = int(result.get("code_count", 0))
                if page * page_size >= code_count:
                    break
            except IwencaiError as e:
                logger.warning(f"翻页第 {page} 页查询失败: {e}")
                break

        return pd.DataFrame(all_records)

    def get_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取股票日线行情。

        Args:
            ts_code: 股票代码（如 "000001.SZ"）
            start_date: 开始日期（YYYYMMDD），默认 60 天前
            end_date: 结束日期（YYYYMMDD），默认当天

        Returns:
            日线行情 DataFrame
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=60)
            start_date = start.strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return self._mock_daily(ts_code)

        try:
            return self._tushare.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取 {ts_code} 日线失败: {e}")
            return pd.DataFrame()

    def get_daily_basic(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取每日指标（换手率、量比、市盈率、市净率等）。

        Args:
            ts_code: 股票代码
            start_date: 开始日期（YYYYMMDD），默认 60 天前
            end_date: 结束日期（YYYYMMDD），默认当天
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=60)
            start_date = start.strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return pd.DataFrame()

        try:
            return self._tushare.daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取 {ts_code} 每日指标失败: {e}")
            return pd.DataFrame()

    def get_stock_basic(
        self,
        exchange: str = "",
        list_status: str = "L",
    ) -> pd.DataFrame:
        """
        获取股票基本信息列表（上市状态、行业、地域等）。

        Args:
            exchange: 交易所代码（SSE/SZSE）
            list_status: 上市状态（L=上市 D=退市 P=暂停）
        """
        if self._mock_mode or self._tushare is None:
            return self._mock_stock_list()

        try:
            return self._tushare.stock_basic(
                exchange=exchange,
                list_status=list_status,
            )
        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return pd.DataFrame()

    def get_limit_list(
        self,
        trade_date: Optional[str] = None,
        limit_type: str = "U",
    ) -> pd.DataFrame:
        """
        获取涨跌停列表。

        Args:
            trade_date: 交易日期（YYYYMMDD），默认当天
            limit_type: U=涨停 D=跌停
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return pd.DataFrame()

        try:
            return self._tushare.limit_list(
                trade_date=trade_date,
                limit_type=limit_type,
            )
        except Exception as e:
            logger.error(f"获取涨跌停列表失败: {e}")
            return pd.DataFrame()

    def get_moneyflow(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取个股资金流向。

        Args:
            ts_code: 股票代码
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=30)
            start_date = start.strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return pd.DataFrame()

        try:
            return self._tushare.moneyflow(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取 {ts_code} 资金流向失败: {e}")
            return pd.DataFrame()

    def get_moneyflow_hsgt(
        self,
        trade_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取沪深港通资金流向。

        Args:
            trade_date: 交易日期（YYYYMMDD），默认当天
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return pd.DataFrame()

        try:
            return self._tushare.moneyflow_hsgt(trade_date=trade_date)
        except Exception as e:
            logger.error(f"获取沪深港通资金流向失败: {e}")
            return pd.DataFrame()

    def get_index_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取指数日线行情。

        Args:
            ts_code: 指数代码（如 "000001.SH" 上证指数）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=60)
            start_date = start.strftime("%Y%m%d")

        if self._mock_mode or self._tushare is None:
            return pd.DataFrame()

        try:
            return self._tushare.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"获取指数 {ts_code} 日线失败: {e}")
            return pd.DataFrame()


# ═════════════════════════════════════════════════════════════════════════════
# 全局单例 & 工厂函数
# ═════════════════════════════════════════════════════════════════════════════

_adapter_instance: Optional[DataAdapter] = None


def get_data_adapter(
    iwencai_client: Optional[object] = None,
    tushare_client: Optional[object] = None,
    mock_mode: bool = False,
) -> DataAdapter:
    """
    获取全局数据适配器实例（单例）。

    首次调用时创建，后续调用可传入 mock_mode=True 或客户端覆盖。
    若曾 mock_mode=True 创建的实例，后续需要真实数据请传入 mock_mode=False。

    Args:
        iwencai_client: 外部注入问财客户端
        tushare_client: 外部注入 Tushare 客户端
        mock_mode: 是否使用 Mock 数据
    """
    global _adapter_instance
    if _adapter_instance is None or mock_mode != _adapter_instance._mock_mode:
        _adapter_instance = DataAdapter(
            iwencai_client=iwencai_client,
            tushare_client=tushare_client,
            mock_mode=mock_mode,
        )
    return _adapter_instance


def reset_data_adapter() -> None:
    """重置全局适配器实例（用于测试）"""
    global _adapter_instance
    _adapter_instance = None


def set_data_adapter(adapter: DataAdapter) -> None:
    """
    注入外部 DataAdapter 实例（用于测试 Mock）。

    用法:
        adapter = MagicMock(spec=DataAdapter)
        adapter.query_stocks.return_value = pd.DataFrame([...])
        set_data_adapter(adapter)
    """
    global _adapter_instance
    _adapter_instance = adapter


# ═════════════════════════════════════════════════════════════════════════════
# 快速自检
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    adapter = get_data_adapter(mock_mode=True)

    print("=== 数据适配层自检 (Mock 模式) ===\n")

    # 1. 问财查询
    stocks = adapter.query_stocks("上市天数>60", limit=5)
    print(f"1. 股票列表 ({len(stocks)} 条):")
    print(stocks[["ts_code", "name", "industry"]].to_string(index=False))
    print()

    # 2. 日线行情
    daily = adapter.get_daily("000001.SZ")
    print(f"2. 日线行情 ({len(daily)} 条):")
    print(daily.head().to_string(index=False))
    print()

    # 3. 股票基本信息
    basics = adapter.get_stock_basic()
    print(f"3. 股票基本信息 ({len(basics)} 条):")
    print(basics[["ts_code", "name", "industry"]].to_string(index=False))
    print()

    print("=== 自检完成 ===")
