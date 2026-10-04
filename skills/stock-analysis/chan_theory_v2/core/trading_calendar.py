#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易日历工具（Tushare Pro API 版本）
提供交易日期相关的功能，如获取最近交易日、判断是否为交易日等
数据完全通过 Tushare Pro API 获取，不依赖本地数据库。
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Union, List, Dict

logger = logging.getLogger(__name__)

# ── Tushare API ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(os.path.dirname(_script_dir))
    load_dotenv(os.path.join(_project_root, '.env'))
    from kk_common import get_finance_data_gateway
    _TS_AVAILABLE = True
except ImportError:
    _TS_AVAILABLE = False

# Tushare Pro API 实例（延迟初始化）
_pro = None


def _get_pro_api():
    """获取（缓存的）金融数据网关实例。"""
    global _pro
    if _pro is None:
        if not _TS_AVAILABLE:
            raise RuntimeError("kk_common 不可用，请检查 Python 运行时配置")
        _pro = get_finance_data_gateway()
    return _pro


class TradingCalendar:
    """
    交易日历工具类（Tushare Pro API 版本）
    """

    def __init__(self):
        self._calendar_cache = None
        self._cache_year = None

    def _get_calendar(self, year: int = None) -> List[Dict]:
        """获取指定年份的交易日历（带缓存）"""
        if year is None:
            year = datetime.now().year

        if self._calendar_cache is not None and self._cache_year == year:
            return self._calendar_cache

        try:
            pro = _get_pro_api()
            df = pro.trade_cal(
                exchange='SSE',
                start_date=f'{year}0101',
                end_date=f'{year}1231',
                fields='cal_date,is_open'
            )
            if df is not None and not df.empty:
                self._calendar_cache = df.to_dict('records')
                self._cache_year = year
                return self._calendar_cache
        except Exception as e:
            logger.warning(f'Tushare 交易日历查询失败: {e}')

        # 降级：使用简单的周末判断
        return self._fallback_calendar(year)

    def _fallback_calendar(self, year: int) -> List[Dict]:
        """降级方案：排除周末的简单日历"""
        from datetime import date
        records = []
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        d = start
        while d <= end:
            is_open = 0 if d.weekday() >= 5 else 1
            records.append({'cal_date': d.strftime('%Y%m%d'), 'is_open': is_open})
            d += timedelta(days=1)
        return records

    def _get_open_dates(self, year: int = None) -> List[str]:
        """获取开盘日期列表"""
        cal = self._get_calendar(year)
        return [r['cal_date'] for r in cal if r.get('is_open') == 1]

    def get_nearest_trading_date(self, target_date: Union[datetime, str],
                                direction: str = 'backward') -> Optional[datetime]:
        """获取最近的交易日"""
        if isinstance(target_date, str):
            if '-' in target_date:
                target_date = datetime.strptime(target_date, '%Y-%m-%d')
            else:
                target_date = datetime.strptime(target_date, '%Y%m%d')

        target_date = datetime(target_date.year, target_date.month, target_date.day)
        target_str = target_date.strftime('%Y%m%d')

        # 获取当年和前后一年的日历
        year = target_date.year
        open_dates = []
        for y in [year - 1, year, year + 1]:
            open_dates.extend(self._get_open_dates(y))
        open_dates = sorted(set(open_dates))

        if direction == 'backward':
            candidates = [d for d in open_dates if d <= target_str]
            if candidates:
                return datetime.strptime(candidates[-1], '%Y%m%d')
        else:
            candidates = [d for d in open_dates if d >= target_str]
            if candidates:
                return datetime.strptime(candidates[0], '%Y%m%d')

        logger.warning(f"未找到{target_str}附近的交易日")
        return None

    def is_trading_day(self, date: Union[datetime, str]) -> bool:
        """判断指定日期是否为交易日"""
        if isinstance(date, str):
            if '-' in date:
                date = datetime.strptime(date, '%Y-%m-%d')
            else:
                date = datetime.strptime(date, '%Y%m%d')

        date_str = date.strftime('%Y%m%d')
        open_dates = self._get_open_dates(date.year)
        return date_str in open_dates

    def get_trading_dates(self, start_date: Union[datetime, str],
                         end_date: Union[datetime, str]) -> List[datetime]:
        """获取指定日期范围内的所有交易日"""
        if isinstance(start_date, str):
            if '-' in start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            else:
                start_date = datetime.strptime(start_date, '%Y%m%d')

        if isinstance(end_date, str):
            if '-' in end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
            else:
                end_date = datetime.strptime(end_date, '%Y%m%d')

        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # 获取涉及年份的交易日
        open_dates = []
        for y in range(start_date.year, end_date.year + 1):
            open_dates.extend(self._get_open_dates(y))
        open_dates = sorted(set(open_dates))

        trading_dates = []
        for d in open_dates:
            if start_str <= d <= end_str:
                trading_dates.append(datetime.strptime(d, '%Y%m%d'))

        return trading_dates

    def get_previous_n_trading_days(self, date: Union[datetime, str], n: int) -> List[datetime]:
        """获取指定日期前N个交易日"""
        if isinstance(date, str):
            if '-' in date:
                date = datetime.strptime(date, '%Y-%m-%d')
            else:
                date = datetime.strptime(date, '%Y%m%d')

        date_str = date.strftime('%Y%m%d')

        open_dates = []
        for y in [date.year - 1, date.year]:
            open_dates.extend(self._get_open_dates(y))
        open_dates = sorted(set(open_dates))

        candidates = [d for d in open_dates if d <= date_str]
        selected = candidates[-n:] if len(candidates) >= n else candidates

        return [datetime.strptime(d, '%Y%m%d') for d in selected]


# 单例模式
_trading_calendar_instance = None


def get_trading_calendar() -> TradingCalendar:
    global _trading_calendar_instance
    if _trading_calendar_instance is None:
        _trading_calendar_instance = TradingCalendar()
    return _trading_calendar_instance


def reset_trading_calendar() -> None:
    global _trading_calendar_instance
    _trading_calendar_instance = None


reset_trading_calendar()


def get_nearest_trading_date(target_date: Union[datetime, str],
                           direction: str = 'backward') -> Optional[datetime]:
    return get_trading_calendar().get_nearest_trading_date(target_date, direction)


def is_trading_day(date: Union[datetime, str]) -> bool:
    return get_trading_calendar().is_trading_day(date)


def get_trading_dates(start_date: Union[datetime, str],
                     end_date: Union[datetime, str]) -> List[datetime]:
    return get_trading_calendar().get_trading_dates(start_date, end_date)


def get_previous_n_trading_days(date: Union[datetime, str], n: int) -> List[datetime]:
    return get_trading_calendar().get_previous_n_trading_days(date, n)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    today = datetime.now()
    nearest = get_nearest_trading_date(today)
    print(f"今天: {today.strftime('%Y-%m-%d')}")
    print(f"最近交易日: {nearest.strftime('%Y-%m-%d') if nearest else 'None'}")
    print(f"今天是否交易日: {is_trading_day(today)}")

    start = today - timedelta(days=30)
    days = get_trading_dates(start, today)
    print(f"过去30天的交易日: {len(days)} 天")

    prev = get_previous_n_trading_days(today, 5)
    print(f"前5个交易日: {[d.strftime('%Y-%m-%d') for d in prev]}")
