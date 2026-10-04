#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare Pro API 公共客户端（common 版）
为所有技能包提供统一 Tushare 数据访问层。

用法:
    from kk_common import get_tushare_client
    client = get_tushare_client()
    df = client.fut_daily(ts_code='IF2605.CFX')
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta

import pandas as pd

try:
    import tushare as ts
    _TUSHARE_AVAILABLE = True
except ImportError:  # KStock patch: tushare 非必需依赖，软导入避免 import 即崩
    ts = None
    _TUSHARE_AVAILABLE = False

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logger = logging.getLogger('TushareClient')

# Tushare API 调用间隔（秒）
API_INTERVAL = 0.35

# 最后一次调用时间
_last_call_time = 0.0


def _rate_limit():
    """API 频率限制"""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < API_INTERVAL:
        time.sleep(API_INTERVAL - elapsed)
    _last_call_time = time.time()


def _to_dataframe(result: Any) -> pd.DataFrame:
    """将结果转换为 DataFrame"""
    if result is None or (isinstance(result, pd.DataFrame) and result.empty):
        return pd.DataFrame()
    if isinstance(result, list):
        return pd.DataFrame(result)
    return result


class TushareClient:
    """Tushare Pro API 公共客户端"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化 Tushare API

        Args:
            token: Tushare Pro Token，如果为 None 则从环境变量获取
        """
        if not _TUSHARE_AVAILABLE:
            raise ImportError("tushare 未安装：无法访问 Tushare 数据（请安装 tushare 或 tushare-data 运行时）")
        self.token = token or os.getenv('TUSHARE_TOKEN')
        if not self.token:
            raise ValueError("未找到 TUSHARE_TOKEN，请配置环境变量或在 .env 文件中设置")

        # 设置 token
        ts.set_token(self.token)

        # 获取 API 对象
        self.pro = ts.pro_api()

        logger.info("Tushare API 初始化成功")

    # =============================================================================
    # 股票相关接口
    # =============================================================================

    def stock_basic(self, ts_code: Optional[str] = None, name: Optional[str] = None,
                   exchange: str = '', list_status: str = 'L',
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票基本信息

        Args:
            ts_code: 股票代码，如 600519.SH（与官方接口一致，按单只过滤）
            name: 股票名称，如 贵州茅台（与官方接口一致）
            exchange: 交易所代码 (SSE/SZSE/BSE/NEEQ)
            list_status: 上市状态 (L=上市, D=退市, P=暂停)
            fields: 返回字段

        Returns:
            股票基本信息 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.stock_basic(
                ts_code=ts_code,
                name=name,
                exchange=exchange,
                list_status=list_status,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return pd.DataFrame()

    def daily(self, ts_code: Optional[str] = None,
              trade_date: Optional[str] = None,
              start_date: Optional[str] = None,
              end_date: Optional[str] = None,
              fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取日线行情

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            日线行情 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取日线行情失败: {e}")
            return pd.DataFrame()

    def daily_basic(self, ts_code: Optional[str] = None,
                    trade_date: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取每日指标（PE、PB等）

        Returns:
            每日指标 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.daily_basic(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取每日指标失败: {e}")
            return pd.DataFrame()

    def trade_cal(self, exchange: str = 'SSE',
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  is_open: Optional[str] = None,
                  limit: Optional[int] = None) -> pd.DataFrame:
        """
        获取交易日历

        Args:
            exchange: 交易所代码 (SSE/SZSE)
            start_date: 开始日期
            end_date: 结束日期
            is_open: 是否交易 (1=是, 0=否)
            limit: 返回行数限制（与官方接口一致；此前缺失导致
                   pro.trade_cal(..., limit=N) 抛 TypeError 返回空）

        Returns:
            交易日历 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.trade_cal(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
                is_open=is_open,
                limit=limit
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return pd.DataFrame()

    def index_basic(self, market: Optional[str] = None,
                    fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取指数基本信息

        Args:
            market: 交易所代码 (SSE/SZSE/CFFEX)
            fields: 返回字段

        Returns:
            指数基本信息 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.index_basic(
                market=market,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取指数基本信息失败: {e}")
            return pd.DataFrame()

    def index_daily(self, ts_code: str,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取指数日线行情

        Args:
            ts_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            指数日线 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取指数日线失败: {e}")
            return pd.DataFrame()

    def fut_basic(self, exchange: Optional[str] = None,
                  fut_type: Optional[str] = None,
                  fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期货基本信息

        Args:
            exchange: 交易所代码
            fut_type: 期货类型
            fields: 返回字段

        Returns:
            期货基本信息 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fut_basic(
                exchange=exchange,
                fut_type=fut_type,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期货基本信息失败: {e}")
            return pd.DataFrame()

    def fut_daily(self, ts_code: Optional[str] = None,
                  trade_date: Optional[str] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期货日线行情

        Args:
            ts_code: 期货代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            期货日线 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fut_daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期货日线失败: {e}")
            return pd.DataFrame()

    def fut_holding(self, symbol: Optional[str] = None,
                    trade_date: Optional[str] = None,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None,
                    exchange: Optional[str] = None,
                    limit: Optional[int] = None,
                    fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期货持仓数据（会员持仓排名）

        Args:
            symbol: 合约代码（如 IF2603）
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码
            limit: 返回数量限制
            fields: 返回字段

        Returns:
            期货持仓 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fut_holding(
                symbol=symbol,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
                limit=limit,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期货持仓数据失败: {e}")
            return pd.DataFrame()

    def fut_wm(self, symbol: Optional[str] = None,
               trade_date: Optional[str] = None,
               start_date: Optional[str] = None,
               end_date: Optional[str] = None,
               fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期货仓单数据

        Args:
            symbol: 品种代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            期货仓单 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fut_wm(
                symbol=symbol,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期货仓单数据失败: {e}")
            return pd.DataFrame()

    def fund_basic(self, market: Optional[str] = None,
                   status: Optional[str] = None,
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取基金基本信息

        Args:
            market: 交易所代码
            status: 状态
            fields: 返回字段

        Returns:
            基金基本信息 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fund_basic(
                market=market,
                status=status,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取基金基本信息失败: {e}")
            return pd.DataFrame()

    def fund_daily(self, ts_code: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取基金日线行情

        Args:
            ts_code: 基金代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            基金日线 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.fund_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取基金日线失败: {e}")
            return pd.DataFrame()

    def fund_share(self, ts_code: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   market: Optional[str] = None,
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取基金规模（份额）数据，用于分析ETF申赎变化

        Args:
            ts_code: 基金代码（如 510050.SH）
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码（SH上交所，SZ深交所）
            fields: 返回字段

        Returns:
            基金份额 DataFrame，含 ts_code, trade_date, fd_share（万份）
        """
        _rate_limit()
        try:
            df = self.pro.fund_share(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                market=market,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取基金份额失败: {e}")
            return pd.DataFrame()

    def opt_basic(self, exchange: str = 'SSE',
                  fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期权基本信息

        Args:
            exchange: 交易所代码
            fields: 返回字段

        Returns:
            期权基本信息 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.opt_basic(
                exchange=exchange,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期权基本信息失败: {e}")
            return pd.DataFrame()

    def opt_daily(self, ts_code: Optional[str] = None,
                  trade_date: Optional[str] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  exchange: Optional[str] = None,
                  fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取期权日线行情

        Args:
            ts_code: 期权代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码（SSE/SZSE）
            fields: 返回字段 (ts_code,trade_date,exchange,close,open,high,low,pre_close,settle,vol,amount,oi)

        Returns:
            期权日线 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.opt_daily(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取期权日线失败: {e}")
            return pd.DataFrame()

    def index_weight(self, index_code: str,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取指数成分及权重

        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            指数成分权重 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.index_weight(
                index_code=index_code,
                start_date=start_date,
                end_date=end_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取指数权重失败: {e}")
            return pd.DataFrame()

    def index_member(self, index_code: str) -> pd.DataFrame:
        """
        获取指数成分股

        Args:
            index_code: 指数代码

        Returns:
            指数成分股 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.index_member(index_code=index_code)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取指数成分股失败: {e}")
            return pd.DataFrame()

    def limit_list(self, trade_date: Optional[str] = None,
                   aa_ts_code: Optional[str] = None,
                   limit_type: Optional[str] = None,
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取涨跌停列表

        Args:
            trade_date: 交易日期
            aa_ts_code: 股票代码
            limit_type: 涨跌停类型 (U=涨停, D=跌停)
            fields: 返回字段

        Returns:
            涨跌停列表 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.limit_list(
                trade_date=trade_date,
                aa_ts_code=aa_ts_code,
                limit_type=limit_type,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取涨跌停列表失败: {e}")
            return pd.DataFrame()

    def moneyflow(self, trade_date: Optional[str] = None,
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取资金流向

        Args:
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            资金流向 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.moneyflow(
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取资金流向失败: {e}")
            return pd.DataFrame()

    def moneyflow_dc(self, ts_code: Optional[str] = None,
                     trade_date: Optional[str] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取个股主力资金流向（大单资金流向）

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
            fields: 返回字段

        Returns:
            个股主力资金流向 DataFrame
            字段: trade_date, ts_code, name, pct_change, close,
                  net_amount(主力净流入), buy_elg_amount(超大单净流入),
                  buy_lg_amount(大单净流入), buy_md_amount(中单净流入),
                  buy_sm_amount(小单净流入)
        """
        _rate_limit()
        try:
            df = self.pro.moneyflow_dc(
                ts_code=ts_code,
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取个股主力资金流向失败: {e}")
            return pd.DataFrame()

    def top_list(self, trade_date: str,
                 fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取龙虎榜个股列表

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            fields: 返回字段

        Returns:
            龙虎榜 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.top_list(
                trade_date=trade_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取龙虎榜数据失败: {e}")
            return pd.DataFrame()

    def top_inst(self, trade_date: str,
                 fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取龙虎榜机构明细

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            fields: 返回字段

        Returns:
            龙虎榜机构明细 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.top_inst(
                trade_date=trade_date,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取龙虎榜机构明细失败: {e}")
            return pd.DataFrame()

    def margin(self, trade_date: Optional[str] = None,
               exchange_id: Optional[str] = None,
               start_date: Optional[str] = None,
               end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取融资融券汇总

        Args:
            trade_date: 交易日期
            exchange_id: 交易所代码 (SSE/SZSE)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            融资融券 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.margin(
                trade_date=trade_date,
                exchange_id=exchange_id,
                start_date=start_date,
                end_date=end_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取融资融券失败: {e}")
            return pd.DataFrame()

    def moneyflow_ind_ths(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取同花顺行业资金流向

        Args:
            trade_date: 交易日期

        Returns:
            行业资金流向 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.moneyflow_ind_ths(trade_date=trade_date)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取行业资金流向失败: {e}")
            return pd.DataFrame()

    def moneyflow_hsgt(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取沪深港通资金流向

        Args:
            trade_date: 交易日期

        Returns:
            沪深港通资金流向 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.moneyflow_hsgt(trade_date=trade_date)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取沪深港通失败: {e}")
            return pd.DataFrame()

    def hsgt_top10(self, trade_date: str,
                   market: Optional[str] = None) -> pd.DataFrame:
        """
        获取沪深港通十大成交股

        Args:
            trade_date: 交易日期 (YYYYMMDD)
            market: 市场 (north=北向, south=南向)。None 表示取全部后由调用方过滤

        Returns:
            十大成交股 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.hsgt_top10(trade_date=trade_date)
            df = _to_dataframe(df)
            if market and "market" in df.columns:
                df = df[df["market"] == market].reset_index(drop=True)
            return df
        except Exception as e:
            logger.error(f"获取沪深港通十大成交股失败: {e}")
            return pd.DataFrame()

    def shibor(self, start_date: Optional[str] = None,
               end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取 Shibor 银行间拆放利率（上海银行间同业拆放利率）

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            Shibor 利率 DataFrame，含 date 列
        """
        _rate_limit()
        try:
            df = self.pro.shibor(start_date=start_date, end_date=end_date)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取 Shibor 利率失败: {e}")
            return pd.DataFrame()

    def shibor_lpr(self, start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取 LPR 贷款基础利率（Shibor LPR 国债收益率曲线）

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            LPR 利率 DataFrame，含 date 列
        """
        _rate_limit()
        try:
            df = self.pro.shibor_lpr(start_date=start_date, end_date=end_date)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取 LPR 利率失败: {e}")
            return pd.DataFrame()

    def hsgt(self, trade_date: Optional[str] = None,
             start_date: Optional[str] = None,
             end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取沪深港通数据（备用接口）

        Args:
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            沪深港通 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.moneyflow_hsgt(
                trade_date=trade_date,
                start_date=start_date,
                end_date=end_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.debug(f"moneyflow_hsgt failed ({e}), trying hsgt")
            try:
                df = self.pro.hsgt(
                    trade_date=trade_date,
                    start_date=start_date,
                    end_date=end_date
                )
                return _to_dataframe(df)
            except Exception as e2:
                logger.error(f"获取沪深港通数据失败: {e2}")
                return pd.DataFrame()

    def margin_detail(self, ts_code: Optional[str] = None,
                      trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取融资融券明细

        Args:
            ts_code: 股票代码
            trade_date: 交易日期

        Returns:
            融资融券明细 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.margin_detail(
                ts_code=ts_code,
                trade_date=trade_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取融资融券明细失败: {e}")
            return pd.DataFrame()

    def namechange(self, ts_code: Optional[str] = None,
                   name: Optional[str] = None,
                   fields: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票名称变更记录

        Args:
            ts_code: 股票代码
            name: 名称
            fields: 返回字段

        Returns:
            名称变更 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.namechange(
                ts_code=ts_code,
                name=name,
                fields=fields
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取名称变更失败: {e}")
            return pd.DataFrame()

    def hs_const(self, hs_type: Optional[str] = 'SH') -> pd.DataFrame:
        """
        获取沪深股通成分

        Args:
            hs_type: 类型 (SH=沪股通, SZ=深股通)

        Returns:
            沪深股通成分 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.hs_const(hs_type=hs_type)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取沪深股通成分失败: {e}")
            return pd.DataFrame()

    def sw_daily(self, ts_code: Optional[str] = None,
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取申万行业日线

        Args:
            ts_code: 行业代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            申万行业日线 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.sw_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取申万行业日线失败: {e}")
            return pd.DataFrame()

    def ConceptBoard(self, src: str = 'SW') -> pd.DataFrame:
        """
        获取概念板块

        Args:
            src: 来源 (SW=申万)

        Returns:
            概念板块 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.ConceptBoard(src=src)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取概念板块失败: {e}")
            return pd.DataFrame()

    def industry(self, code: Optional[str] = None) -> pd.DataFrame:
        """
        获取行业板块

        Args:
            code: 行业代码

        Returns:
            行业板块 DataFrame
        """
        _rate_limit()
        try:
            df = self.pro.industry(code=code)
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取行业板块失败: {e}")
            return pd.DataFrame()

    def pro_bar(self, ts_code: Optional[str] = None, asset: str = 'E',
                start_date: Optional[str] = None, end_date: Optional[str] = None,
                freq: str = 'D', adj: Optional[str] = None, **kwargs: Any) -> pd.DataFrame:
        """
        获取股票/指数/基金/期货的复权行情（Tushare 顶层便捷函数 pro_bar）。

        与 ``pro.daily`` 不同，``pro_bar`` 支持前复权(qfq)/后复权(hfq)，
        是缠论、技术分析等需要连续复权序列场景的标准入口。

        Args:
            ts_code: 标的代码
            asset: 资产类别 E=股票 I=指数 FD=基金 FT=期货
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            freq: 频率 D=日 W=周 M=月
            adj: 复权类型 None=不复权 qfq=前复权 hfq=后复权

        Returns:
            复权行情 DataFrame
        """
        _rate_limit()
        # 兼容小写频率（daily/weekly/monthly）：tushare 库 pro_bar 仅识别大写 D/W/M，
        # 传小写会导致内部各频率分支均不命中、data 未赋值而抛 UnboundLocalError。
        if freq in ('daily', 'weekly', 'monthly'):
            freq = freq[0].upper()
        import contextlib
        import io
        _stdout_buf = io.StringIO()
        try:
            # tushare 库 pro_bar 内部存在裸 print(e) 到 stdout 的缺陷
            # （except 分支不 return、循环继续），会污染 JSON 等结构化输出，
            # 此处重定向其 stdout 到缓冲区，仅记入日志。
            with contextlib.redirect_stdout(_stdout_buf):
                df = ts.pro_bar(
                    ts_code=ts_code, asset=asset,
                    start_date=start_date, end_date=end_date,
                    freq=freq, adj=adj, **kwargs,
                )
            _internal_output = _stdout_buf.getvalue().strip()
            if _internal_output:
                logger.debug(f"pro_bar 内部输出: {_internal_output}")
            return _to_dataframe(df)
        except Exception as e:
            logger.error(f"获取 pro_bar 行情失败: {e}")
            return pd.DataFrame()


# 全局客户端实例
_tushare_client: Optional['TushareClient'] = None


def get_tushare_client() -> 'TushareClient':
    """获取全局 Tushare 客户端实例"""
    global _tushare_client
    if _tushare_client is None:
        _tushare_client = TushareClient()
    return _tushare_client


def reset_tushare_client(client: Optional['TushareClient'] = None) -> None:
    """重置全局 Tushare 客户端实例。

    用途：
      - 单元测试中注入 mock client / 新 token
      - 运行期切换 token 后强制重建实例

    Args:
        client: 指定新实例；None 表示清空，下次 get_tushare_client() 时重建
    """
    global _tushare_client
    _tushare_client = client


# 向后兼容别名（原 api.tushare_api.get_tushare_api）
get_tushare_api = get_tushare_client
