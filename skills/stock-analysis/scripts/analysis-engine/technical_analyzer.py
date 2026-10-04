#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股技术分析引擎
技术分析功能 - 宏观趋势 + 微观择时

数据来源：Tushare Pro API（不依赖本地数据库）
宏观层：日线/周线/月线联动分析趋势（MA/MACD/RSI/KDJ/Bollinger/ATR/OBV）
微观层：5/15/30/60/90/120分钟联动分析量价、动量、背驰，生成买卖择时信号
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  指标计算工具（纯 pandas/numpy，无外部TA库依赖）
# ======================================================================

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _ma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def _macd(close: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """返回 (DIF, DEA, BAR)"""
    dif = _ema(close, fast) - _ema(close, slow)
    dea = _ema(dif, signal)
    bar = (dif - dea) * 2
    return dif, dea, bar


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _kdj(high: pd.Series, low: pd.Series, close: pd.Series,
         n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """返回 (K, D, J)"""
    low_n = low.rolling(window=n, min_periods=1).min()
    high_n = high.rolling(window=n, min_periods=1).max()
    rsv = (close - low_n) / (high_n - low_n + 1e-10) * 100
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def _bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """返回 (upper, mid, lower)"""
    mid = _ma(close, period)
    std = close.rolling(window=period, min_periods=1).std()
    return mid + std_dev * std, mid, mid - std_dev * std


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def _vwap(close: pd.Series, volume: pd.Series) -> pd.Series:
    """按全量数据计算 VWAP（当日累计成交均价）"""
    cum_vol = volume.cumsum()
    cum_vol_price = (close * volume).cumsum()
    return cum_vol_price / cum_vol.replace(0, np.nan)


def _roc(close: pd.Series, period: int = 5) -> pd.Series:
    return (close / close.shift(period) - 1) * 100


def _detect_divergence(close: pd.Series, macd_bar: pd.Series,
                        lookback: int = 10) -> Optional[str]:
    """
    检测最近 lookback 根 K 线内的背驰
    返回: '顶背驰' / '底背驰' / None
    """
    if len(close) < lookback + 2:
        return None
    c = close.iloc[-lookback:]
    b = macd_bar.iloc[-lookback:]

    # 顶背驰：价格创新高，但 MACD 柱缩短
    if c.iloc[-1] >= c.max() * 0.995:  # 价格接近区间高点
        recent_bar_max = b.iloc[-3:].max()
        prev_bar_max = b.iloc[:-3].max()
        if recent_bar_max < prev_bar_max * 0.85 and recent_bar_max > 0:
            return '顶背驰'

    # 底背驰：价格创新低，但 MACD 柱缩短（绝对值）
    if c.iloc[-1] <= c.min() * 1.005:  # 价格接近区间低点
        recent_bar_min = b.iloc[-3:].min()
        prev_bar_min = b.iloc[:-3].min()
        if recent_bar_min > prev_bar_min * 0.85 and recent_bar_min < 0:
            return '底背驰'

    return None


def _detect_rsi_divergence(close: pd.Series, rsi: pd.Series,
                             lookback: int = 10) -> Optional[str]:
    """RSI 背驰检测"""
    if len(close) < lookback + 2:
        return None
    c = close.iloc[-lookback:]
    r = rsi.iloc[-lookback:]

    # RSI 顶背驰
    if c.iloc[-1] >= c.max() * 0.995 and r.iloc[-1] < r.max() - 5:
        return 'RSI顶背驰'
    # RSI 底背驰
    if c.iloc[-1] <= c.min() * 1.005 and r.iloc[-1] > r.min() + 5:
        return 'RSI底背驰'
    return None


# ======================================================================
#  数据采集层
# ======================================================================

class TechnicalDataFetcher:
    """
    技术分析数据采集器
    所有数据直接从 Tushare Pro API 获取，不依赖本地数据库
    """

    def __init__(self, tushare_token: Optional[str] = None):
        from kk_common import get_finance_data_gateway
        from dotenv import load_dotenv

        env_path = os.path.join(_project_root, 'kk_stock_backend', '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
        else:
            load_dotenv()

        token = tushare_token or os.getenv('TUSHARE_TOKEN')
        if not token:
            raise ValueError("未找到 TUSHARE_TOKEN，请在 .env 中配置")

        self.pro = get_finance_data_gateway()
        print("[TechnicalDataFetcher] Tushare Pro 初始化成功")

    # ------------------------------------------------------------------ #
    #  K线数据
    # ------------------------------------------------------------------ #

    def fetch_klines(self, ts_code: str, freq: str = 'D', n: int = 300) -> pd.DataFrame:
        """
        获取 K 线数据

        Args:
            ts_code: 股票代码，如 '300750.SZ'
            freq: 'D'日线 / 'W'周线 / 'M'月线 / '5min' / '15min' / '30min' / '60min'
            n:    获取最近 n 根 K 线（日/周/月）或最近 n 天内的分钟线

        Returns:
            DataFrame，列包含 open/high/low/close/vol/amount，按时间升序
        """
        try:
            if freq in ('D', 'W', 'M'):
                return self._fetch_daily_weekly_monthly(ts_code, freq, n)
            else:
                return self._fetch_minute(ts_code, freq, n)
        except Exception as e:
            print(f"[警告] 获取 {ts_code} {freq} K线失败: {e}")
            return pd.DataFrame()

    def _fetch_daily_weekly_monthly(self, ts_code: str, freq: str, n: int) -> pd.DataFrame:
        """
        获取日/周/月线。
        使用 limit 参数而非 start_date+end_date 区间，确保始终拿到最新的 n 根 K 线。
        （若用日期区间且区间过大，Tushare 接口返回有条数上限，会截断最新的数据。）
        """
        end_date = datetime.now().strftime('%Y%m%d')
        # 多取 20% 以防节假日/停牌缺口，然后 tail(n) 精确截取
        fetch_n = int(n * 1.3) + 20

        api_map = {'D': self.pro.daily, 'W': self.pro.weekly, 'M': self.pro.monthly}
        df = api_map[freq](
            ts_code=ts_code,
            end_date=end_date,
            limit=fetch_n,
            fields='ts_code,trade_date,open,high,low,close,vol,amount,pre_close,change,pct_chg'
        )
        if df is None or df.empty:
            return pd.DataFrame()

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        df = df.tail(n).reset_index(drop=True)
        return df

    def _fetch_minute(self, ts_code: str, freq: str, n_days: int = 10) -> pd.DataFrame:
        """
        获取分钟线（stk_mins 接口）
        freq: '5min' / '15min' / '30min' / '60min'
        n_days: 获取最近 n_days 个交易日的数据
        """
        freq_map = {'5min': '5min', '15min': '15min', '30min': '30min', '60min': '60min'}
        ts_freq = freq_map.get(freq)
        if not ts_freq:
            return pd.DataFrame()

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=n_days * 2 + 10)  # 多取一些覆盖非交易日
        start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')

        try:
            df = self.pro.stk_mins(
                ts_code=ts_code,
                start_date=start_str,
                end_date=end_str,
                freq=ts_freq,
                fields='ts_code,trade_time,open,high,low,close,vol,amount'
            )
        except Exception as e:
            print(f"[警告] stk_mins({freq}) 失败: {e}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df['trade_time'] = pd.to_datetime(df['trade_time'])
        df = df.sort_values('trade_time').reset_index(drop=True)
        # 只保留最近 n_days 个交易日
        dates = df['trade_time'].dt.date.unique()
        if len(dates) > n_days:
            cutoff = sorted(dates)[-n_days]
            df = df[df['trade_time'].dt.date >= cutoff].reset_index(drop=True)
        return df

    def resample_to_90min(self, df_30min: pd.DataFrame) -> pd.DataFrame:
        """30min K线重采样为 90min"""
        return self._resample_minutes(df_30min, 3, '90min')

    def resample_to_120min(self, df_60min: pd.DataFrame) -> pd.DataFrame:
        """60min K线重采样为 120min"""
        return self._resample_minutes(df_60min, 2, '120min')

    def _resample_minutes(self, df: pd.DataFrame, factor: int, label: str) -> pd.DataFrame:
        """
        将分钟 K 线按 factor 倍数重采样，合并 OHLCV
        """
        if df.empty or 'trade_time' not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        df = df.set_index('trade_time').sort_index()

        # 按交易日分组再重采样，避免跨日合并
        results = []
        for date, day_df in df.groupby(df.index.date):
            day_df = day_df.reset_index()
            # 给每根K线一个序号，按 factor 分组
            day_df['group'] = day_df.index // factor
            agg = day_df.groupby('group').agg(
                trade_time=('trade_time', 'first'),
                open=('open', 'first'),
                high=('high', 'max'),
                low=('low', 'min'),
                close=('close', 'last'),
                vol=('vol', 'sum'),
                amount=('amount', 'sum'),
            ).reset_index(drop=True)
            results.append(agg)

        if not results:
            return pd.DataFrame()

        out = pd.concat(results, ignore_index=True)
        out = out.sort_values('trade_time').reset_index(drop=True)
        return out

    # ------------------------------------------------------------------ #
    #  日线衍生数据
    # ------------------------------------------------------------------ #

    def fetch_daily_basic(self, ts_code: str, n: int = 60) -> pd.DataFrame:
        """
        获取每日指标（换手率/PE/PB/主力净流入）
        接口：daily_basic
        """
        end_date = datetime.now().strftime('%Y%m%d')
        fetch_n = int(n * 1.3) + 20
        try:
            df = self.pro.daily_basic(
                ts_code=ts_code,
                end_date=end_date,
                limit=fetch_n,
                fields='ts_code,trade_date,turnover_rate,turnover_rate_f,pe,pe_ttm,pb,total_mv,circ_mv'
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').tail(n).reset_index(drop=True)
            return df
        except Exception as e:
            print(f"[警告] 获取 daily_basic 失败: {e}")
            return pd.DataFrame()

    def fetch_moneyflow(self, ts_code: str, n: int = 20) -> pd.DataFrame:
        """
        获取个股资金流向（moneyflow 接口）
        """
        end_date = datetime.now().strftime('%Y%m%d')
        fetch_n = int(n * 1.3) + 20
        try:
            df = self.pro.moneyflow(
                ts_code=ts_code,
                end_date=end_date,
                limit=fetch_n,
                fields='ts_code,trade_date,buy_sm_vol,sell_sm_vol,buy_md_vol,sell_md_vol,'
                       'buy_lg_vol,sell_lg_vol,buy_elg_vol,sell_elg_vol,net_mf_vol,net_mf_amount'
            )
            if df is None or df.empty:
                return pd.DataFrame()
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').tail(n).reset_index(drop=True)
            return df
        except Exception as e:
            print(f"[警告] 获取 moneyflow 失败: {e}")
            return pd.DataFrame()


# ======================================================================
#  技术分析引擎
# ======================================================================

class TechnicalAnalyzer:
    """
    个股技术分析引擎

    宏观层（日/周/月线联动）：趋势判断、MA排列、MACD/RSI/KDJ/布林/ATR
    微观层（5/15/30/60/90/120分钟联动）：量价分析、动量指标、背驰检测、买卖择时
    """

    def __init__(self, fetcher: Optional['TechnicalDataFetcher'] = None):
        self.fetcher = fetcher or TechnicalDataFetcher()

    # ------------------------------------------------------------------ #
    #  宏观趋势分析
    # ------------------------------------------------------------------ #

    def analyze_macro(self, ts_code: str) -> Dict:
        """
        宏观趋势分析：日线 + 周线 + 月线联动

        Returns:
            {
              'macro_trend': {'monthly': {...}, 'weekly': {...}, 'daily': {...}},
              'composite_score': 0-100,
              'trend_conclusion': str,
              'support_resistance': {'support': float, 'resistance': float},
              'turnover': {'avg10': float, 'latest': float},
              'moneyflow': {...},
            }
        """
        print("  [宏观] 获取月线数据...", end=' ', flush=True)
        df_m = self.fetcher.fetch_klines(ts_code, 'M', 36)
        print(f"✓ {len(df_m)} 根")

        print("  [宏观] 获取周线数据...", end=' ', flush=True)
        df_w = self.fetcher.fetch_klines(ts_code, 'W', 52)
        print(f"✓ {len(df_w)} 根")

        print("  [宏观] 获取日线数据...", end=' ', flush=True)
        df_d = self.fetcher.fetch_klines(ts_code, 'D', 300)
        print(f"✓ {len(df_d)} 根")

        print("  [宏观] 获取换手率/PE/PB...", end=' ', flush=True)
        df_basic = self.fetcher.fetch_daily_basic(ts_code, 60)
        print(f"✓ {len(df_basic)} 条")

        print("  [宏观] 获取资金流向...", end=' ', flush=True)
        df_mf = self.fetcher.fetch_moneyflow(ts_code, 20)
        print(f"✓ {len(df_mf)} 条")

        result = {
            'macro_trend': {},
            'kline_data': {},  # 存储原始K线数据用于图表渲染
            'composite_score': 0,
            'trend_conclusion': '数据不足',
            'support_resistance': {},
            'turnover': {},
            'moneyflow': {},
        }

        # 分析各周期
        monthly_ana = self._analyze_period(df_m, 'monthly')
        weekly_ana = self._analyze_period(df_w, 'weekly')
        daily_ana = self._analyze_period(df_d, 'daily')

        result['macro_trend'] = {
            'monthly': monthly_ana,
            'weekly': weekly_ana,
            'daily': daily_ana,
        }

        # 存储原始K线数据用于图表渲染
        result['kline_data'] = {
            'daily': self._df_to_dict(df_d) if not df_d.empty else {},
            'weekly': self._df_to_dict(df_w) if not df_w.empty else {},
            'monthly': self._df_to_dict(df_m) if not df_m.empty else {},
        }

        # 三级联动加权评分（月线权重最高）
        scores = [
            monthly_ana.get('score', 50) * 0.30,
            weekly_ana.get('score', 50) * 0.35,
            daily_ana.get('score', 50) * 0.35,
        ]
        composite = round(sum(scores), 1)
        result['composite_score'] = composite

        # 综合结论
        result['trend_conclusion'] = self._composite_conclusion(
            monthly_ana, weekly_ana, daily_ana, composite
        )

        # 支撑压力位（基于日线布林带 + 近期高低点）
        if not df_d.empty:
            result['support_resistance'] = self._calc_support_resistance(df_d)

        # 换手率
        if not df_basic.empty:
            tr = df_basic['turnover_rate'].dropna()
            result['turnover'] = {
                'avg10': round(float(tr.tail(10).mean()), 2),
                'latest': round(float(tr.iloc[-1]), 2),
                'pe_ttm': (round(float(df_basic['pe_ttm'].iloc[-1]), 2)
                           if 'pe_ttm' in df_basic.columns and df_basic['pe_ttm'].iloc[-1] is not None
                           and str(df_basic['pe_ttm'].iloc[-1]) not in ('nan', 'None') else 0),
                'pb': (round(float(df_basic['pb'].iloc[-1]), 2)
                       if 'pb' in df_basic.columns and df_basic['pb'].iloc[-1] is not None
                       and str(df_basic['pb'].iloc[-1]) not in ('nan', 'None') else 0),
            }

        # 资金流向
        if not df_mf.empty:
            mf = df_mf.tail(5)
            result['moneyflow'] = {
                'net_mf_vol_5d': round(float(mf['net_mf_vol'].sum()), 2),
                'net_mf_amount_5d': round(float(mf['net_mf_amount'].sum()), 2),
                'direction': '净流入' if mf['net_mf_vol'].sum() > 0 else '净流出',
                'large_order_net': round(float(
                    (mf['buy_elg_vol'] - mf['sell_elg_vol']).sum() +
                    (mf['buy_lg_vol'] - mf['sell_lg_vol']).sum()
                ), 2),
            }

        return result

    def _analyze_period(self, df: pd.DataFrame, period_name: str) -> Dict:
        """分析单个周期（日/周/月），计算所有技术指标并评分"""
        if df.empty or len(df) < 10:
            return {'score': 50, 'error': '数据不足'}

        close = df['close']
        high = df['high']
        low = df['low']
        vol = df['vol']

        ana = {'period': period_name}

        # --- MA ---
        ma5 = _ma(close, 5)
        ma10 = _ma(close, 10)
        ma20 = _ma(close, 20)
        ma60 = _ma(close, 60)
        ma120 = _ma(close, 120)
        ma250 = _ma(close, 250)

        cur = close.iloc[-1]
        ana['close'] = round(float(cur), 3)
        ana['ma5'] = round(float(ma5.iloc[-1]), 3)
        ana['ma10'] = round(float(ma10.iloc[-1]), 3)
        ana['ma20'] = round(float(ma20.iloc[-1]), 3)
        ana['ma60'] = round(float(ma60.iloc[-1]), 3)

        # MA 多空排列
        ma_vals = [ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1], ma60.iloc[-1]]
        if all(ma_vals[i] > ma_vals[i+1] for i in range(len(ma_vals)-1)):
            ana['ma_alignment'] = '多头排列'
        elif all(ma_vals[i] < ma_vals[i+1] for i in range(len(ma_vals)-1)):
            ana['ma_alignment'] = '空头排列'
        else:
            ana['ma_alignment'] = '混乱排列'

        # 价格相对 MA20 位置
        ana['above_ma20'] = bool(cur > ma20.iloc[-1])
        ana['above_ma60'] = bool(cur > ma60.iloc[-1])

        # --- MACD ---
        dif, dea, bar = _macd(close)
        ana['macd_dif'] = round(float(dif.iloc[-1]), 4)
        ana['macd_dea'] = round(float(dea.iloc[-1]), 4)
        ana['macd_bar'] = round(float(bar.iloc[-1]), 4)
        ana['macd_above_zero'] = bool(dif.iloc[-1] > 0)

        # MACD 信号
        if bar.iloc[-1] > 0 and bar.iloc[-2] < 0:
            ana['macd_signal'] = '金叉'
        elif bar.iloc[-1] < 0 and bar.iloc[-2] > 0:
            ana['macd_signal'] = '死叉'
        elif bar.iloc[-1] > bar.iloc[-2]:
            ana['macd_signal'] = '扩张'
        else:
            ana['macd_signal'] = '收缩'

        # --- RSI ---
        rsi14 = _rsi(close, 14)
        ana['rsi'] = round(float(rsi14.iloc[-1]), 2)
        if ana['rsi'] > 70:
            ana['rsi_zone'] = '超买'
        elif ana['rsi'] < 30:
            ana['rsi_zone'] = '超卖'
        else:
            ana['rsi_zone'] = '正常'

        # --- KDJ ---
        k, d, j = _kdj(high, low, close)
        ana['kdj_k'] = round(float(k.iloc[-1]), 2)
        ana['kdj_d'] = round(float(d.iloc[-1]), 2)
        ana['kdj_j'] = round(float(j.iloc[-1]), 2)

        if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            ana['kdj_signal'] = '金叉'
        elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
            ana['kdj_signal'] = '死叉'
        elif j.iloc[-1] > 80:
            ana['kdj_signal'] = '超买区'
        elif j.iloc[-1] < 20:
            ana['kdj_signal'] = '超卖区'
        else:
            ana['kdj_signal'] = '运行中'

        # --- Bollinger Bands ---
        boll_up, boll_mid, boll_low = _bollinger(close, 20, 2)
        ana['boll_upper'] = round(float(boll_up.iloc[-1]), 3)
        ana['boll_mid'] = round(float(boll_mid.iloc[-1]), 3)
        ana['boll_lower'] = round(float(boll_low.iloc[-1]), 3)

        boll_pos = (cur - boll_mid.iloc[-1]) / (boll_up.iloc[-1] - boll_mid.iloc[-1] + 1e-10)
        ana['boll_position'] = round(float(boll_pos), 3)
        if boll_pos > 0.8:
            ana['boll_zone'] = '上轨附近'
        elif boll_pos > 0.2:
            ana['boll_zone'] = '中轨上方'
        elif boll_pos > -0.2:
            ana['boll_zone'] = '中轨附近'
        elif boll_pos > -0.8:
            ana['boll_zone'] = '中轨下方'
        else:
            ana['boll_zone'] = '下轨附近'

        # --- ATR（波动率）---
        atr14 = _atr(high, low, close, 14)
        ana['atr'] = round(float(atr14.iloc[-1]), 3)
        ana['atr_pct'] = round(float(atr14.iloc[-1] / cur * 100), 2)  # ATR 占价格比例

        # --- OBV ---
        obv = _obv(close, vol)
        obv_ma5 = _ma(obv, 5)
        ana['obv_trend'] = '上升' if obv.iloc[-1] > obv_ma5.iloc[-5] else '下降'

        # --- 趋势方向 ---
        if len(df) >= 10:
            recent_slope = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10] * 100
            if recent_slope > 3:
                ana['trend'] = '上升'
            elif recent_slope < -3:
                ana['trend'] = '下降'
            else:
                ana['trend'] = '震荡'
            ana['recent_change_pct'] = round(float(recent_slope), 2)
        else:
            ana['trend'] = '未知'

        # --- 综合评分（0-100）---
        ana['score'] = self._score_period(ana)
        return ana

    def _score_period(self, ana: Dict) -> int:
        """
        对单周期打分（0-100），从多维度综合评估多空强弱
        50分为中性基准
        """
        score = 50

        # MA 排列 (+/-15)
        ma_map = {'多头排列': 15, '混乱排列': 0, '空头排列': -15}
        score += ma_map.get(ana.get('ma_alignment', '混乱排列'), 0)

        # 价格位置 (+/-5)
        if ana.get('above_ma20'):
            score += 5
        else:
            score -= 5
        if ana.get('above_ma60'):
            score += 5
        else:
            score -= 5

        # MACD (+/-15)
        macd_map = {'金叉': 15, '扩张': 8, '收缩': -5, '死叉': -15}
        score += macd_map.get(ana.get('macd_signal', '收缩'), 0)
        if ana.get('macd_above_zero'):
            score += 5
        else:
            score -= 5

        # RSI (+/-10)
        rsi = ana.get('rsi', 50)
        if 45 <= rsi <= 70:
            score += 10
        elif rsi > 70:
            score -= 5   # 超买区，谨慎
        elif rsi < 30:
            score += 5   # 超卖区，反弹潜力

        # KDJ (+/-10)
        kdj_map = {'金叉': 10, '超卖区': 8, '运行中': 0, '超买区': -5, '死叉': -10}
        score += kdj_map.get(ana.get('kdj_signal', '运行中'), 0)

        # 布林 (+/-5)
        boll_map = {
            '上轨附近': -5, '中轨上方': 5, '中轨附近': 0,
            '中轨下方': -3, '下轨附近': 3
        }
        score += boll_map.get(ana.get('boll_zone', '中轨附近'), 0)

        # OBV 量价配合 (+/-5)
        if ana.get('obv_trend') == '上升':
            score += 5
        else:
            score -= 5

        return max(0, min(100, score))

    def _composite_conclusion(self, monthly: Dict, weekly: Dict,
                               daily: Dict, score: float) -> str:
        """根据三级联动生成文字结论"""
        m_trend = monthly.get('trend', '未知')
        w_trend = weekly.get('trend', '未知')
        d_trend = daily.get('trend', '未知')

        if score >= 75:
            strength = '强势'
        elif score >= 60:
            strength = '偏强'
        elif score >= 45:
            strength = '中性'
        elif score >= 30:
            strength = '偏弱'
        else:
            strength = '弱势'

        # 三级联动描述
        parts = []
        if m_trend == '上升':
            parts.append('大趋势向上')
        elif m_trend == '下降':
            parts.append('大趋势向下')
        else:
            parts.append('大趋势震荡')

        if w_trend == '上升':
            parts.append('中期上行')
        elif w_trend == '下降':
            parts.append('中期调整')
        else:
            parts.append('中期盘整')

        if d_trend == '上升':
            parts.append('短线反弹')
        elif d_trend == '下降':
            parts.append('短线下行')
        else:
            parts.append('短线震荡')

        return f"{strength}（{'，'.join(parts)}）"

    def _df_to_dict(self, df: pd.DataFrame) -> Dict:
        """将K线DataFrame转换为dict格式，用于图表渲染，包含均线数据"""
        if df.empty:
            return {}
        # 转换日期为字符串格式
        dates = df['trade_date'].dt.strftime('%Y-%m-%d').tolist() if hasattr(df['trade_date'], 'dt') else [str(d) for d in df['trade_date']]

        # 计算均线
        close_s = df['close']
        ma5 = _ma(close_s, 5).round(2).tolist()
        ma10 = _ma(close_s, 10).round(2).tolist()
        ma20 = _ma(close_s, 20).round(2).tolist()
        ma60 = _ma(close_s, 60).round(2).tolist()

        result: Dict = {
            'dates': dates,
            'open': df['open'].tolist() if 'open' in df.columns else [],
            'high': df['high'].tolist() if 'high' in df.columns else [],
            'low': df['low'].tolist() if 'low' in df.columns else [],
            'close': df['close'].tolist() if 'close' in df.columns else [],
            'vol': df['vol'].tolist() if 'vol' in df.columns else [],
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
        }
        return result

    def _calc_support_resistance(self, df: pd.DataFrame) -> Dict:
        """计算近期支撑位和压力位"""
        if len(df) < 20:
            return {}

        recent = df.tail(60)
        close = recent['close']
        high = recent['high']
        low = recent['low']

        # 布林带作为参考
        _, mid, low_band = _bollinger(close, 20, 2)

        cur = float(close.iloc[-1])
        # 支撑：近60日低点、布林下轨、MA20
        support_candidates = [
            float(low.tail(20).min()),
            float(low_band.iloc[-1]),
            float(_ma(close, 20).iloc[-1]),
        ]
        support = round(max(s for s in support_candidates if s < cur * 1.05), 3)

        # 压力：近60日高点、布林上轨
        resistance_candidates = [
            float(high.tail(20).max()),
            float(_bollinger(close, 20, 2)[0].iloc[-1]),
        ]
        resistance = round(min(r for r in resistance_candidates if r > cur * 0.95), 3)

        return {
            'support': support,
            'resistance': resistance,
            'current': round(cur, 3),
            'distance_to_resistance_pct': round((resistance - cur) / cur * 100, 2),
            'distance_to_support_pct': round((cur - support) / cur * 100, 2),
        }

    # ------------------------------------------------------------------ #
    #  微观择时分析
    # ------------------------------------------------------------------ #

    def analyze_micro(self, ts_code: str, n_days: int = 10) -> Dict:
        """
        微观择时分析：5/15/30/60/90/120分钟联动

        Returns:
            {
              'signals': {
                '5min': {'direction': 'buy/sell/neutral', ...},
                ...
              },
              'composite_signal': 'buy/sell/neutral',
              'signal_strength': 0-10,
              'timing_conclusion': str,
              'divergence_alerts': [str],
            }
        """
        # 采集各周期数据
        print("  [微观] 获取5min K线...", end=' ', flush=True)
        df_5 = self.fetcher.fetch_klines(ts_code, '5min', n_days)
        print(f"✓ {len(df_5)} 根")

        print("  [微观] 获取15min K线...", end=' ', flush=True)
        df_15 = self.fetcher.fetch_klines(ts_code, '15min', n_days)
        print(f"✓ {len(df_15)} 根")

        print("  [微观] 获取30min K线...", end=' ', flush=True)
        df_30 = self.fetcher.fetch_klines(ts_code, '30min', n_days)
        print(f"✓ {len(df_30)} 根")

        print("  [微观] 获取60min K线...", end=' ', flush=True)
        df_60 = self.fetcher.fetch_klines(ts_code, '60min', n_days)
        print(f"✓ {len(df_60)} 根")

        print("  [微观] 合成90min K线...", end=' ', flush=True)
        df_90 = self.fetcher.resample_to_90min(df_30)
        print(f"✓ {len(df_90)} 根")

        print("  [微观] 合成120min K线...", end=' ', flush=True)
        df_120 = self.fetcher.resample_to_120min(df_60)
        print(f"✓ {len(df_120)} 根")

        frames = {
            '5min': df_5,
            '15min': df_15,
            '30min': df_30,
            '60min': df_60,
            '90min': df_90,
            '120min': df_120,
        }

        # 逐周期分析
        signals = {}
        for freq, df in frames.items():
            signals[freq] = self._analyze_minute_period(df, freq)

        # 综合信号（最小周期优先）
        composite, strength = self._composite_signal(signals)
        divergence_alerts = [
            f"{freq} {sig['divergence']}"
            for freq, sig in signals.items()
            if sig.get('divergence')
        ]

        return {
            'signals': signals,
            'composite_signal': composite,
            'signal_strength': strength,
            'timing_conclusion': self._timing_conclusion(signals, composite, strength),
            'divergence_alerts': divergence_alerts,
        }

    def _analyze_minute_period(self, df: pd.DataFrame, freq: str) -> Dict:
        """分析单个分钟周期"""
        if df.empty or len(df) < 10:
            return {
                'freq': freq, 'direction': 'neutral',
                'volume_price': '数据不足', 'macd_bar_sign': '?',
                'rsi': 50.0, 'divergence': None, 'score': 5.0,
                'error': '数据不足'
            }

        close = df['close'].astype(float)
        vol = df['vol'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)

        # --- MACD（全量数据做指标预热，保证准确性）---
        dif, dea, bar = _macd(close, fast=12, slow=26, signal=9)
        latest_bar = float(bar.iloc[-1])
        prev_bar = float(bar.iloc[-2]) if len(bar) > 1 else 0.0

        # --- RSI（全量预热）---
        rsi6 = _rsi(close, 6)
        rsi12 = _rsi(close, 12)
        rsi_val = float(rsi6.iloc[-1])

        # --- ROC ---
        roc5 = _roc(close, 5)
        roc_val = float(roc5.iloc[-1]) if len(roc5) > 5 else 0.0

        # ----------------------------------------------------------------
        # 量价 / VWAP 只取最后一个交易日数据，避免跨日累计失真
        # ----------------------------------------------------------------
        if 'trade_time' in df.columns:
            df_time = pd.to_datetime(df['trade_time'])
            last_date = df_time.dt.date.max()
            today_mask = df_time.dt.date == last_date
            close_today = close[today_mask]
            vol_today = vol[today_mask]
            amount_today = (
                df['amount'].astype(float)[today_mask]
                if 'amount' in df.columns
                else pd.Series(dtype=float)
            )
        else:
            # 日线等没有 trade_time 字段，直接用全量
            close_today = close
            vol_today = vol
            amount_today = (
                df['amount'].astype(float)
                if 'amount' in df.columns
                else pd.Series(dtype=float)
            )

        # --- 量价关系（基于当日最后一根K线与当日量均线）---
        vol_ma5_today = _ma(vol_today, min(5, len(vol_today)))
        latest_vol = float(vol_today.iloc[-1]) if not vol_today.empty else 0.0
        avg_vol = float(vol_ma5_today.iloc[-1]) if not vol_ma5_today.empty else 1.0
        price_chg = (
            float(close_today.iloc[-1] - close_today.iloc[-2])
            if len(close_today) > 1
            else 0.0
        )

        vol_ratio = latest_vol / avg_vol if avg_vol > 0 else 1.0
        if price_chg > 0 and vol_ratio > 1.1:
            volume_price = '价涨量增'
        elif price_chg > 0 and vol_ratio < 0.9:
            volume_price = '价涨量缩'
        elif price_chg < 0 and vol_ratio > 1.1:
            volume_price = '价跌量增'
        elif price_chg < 0 and vol_ratio < 0.9:
            volume_price = '价跌量缩'
        else:
            volume_price = '量价中性'

        # --- VWAP 偏离度（当日 VWAP，每日重置）---
        if not amount_today.empty and not vol_today.empty:
            # 用成交额/成交量更精准；若无 amount 则用 close*vol 近似
            if amount_today.sum() > 0:
                vwap_val = float(amount_today.sum() / vol_today.sum()) if vol_today.sum() > 0 else float(close_today.iloc[-1])
            else:
                vwap_today = _vwap(close_today.reset_index(drop=True), vol_today.reset_index(drop=True))
                vwap_val = float(vwap_today.iloc[-1])
            cur_close = float(close_today.iloc[-1])
            vwap_dev = round((cur_close - vwap_val) / vwap_val * 100, 2) if vwap_val > 0 else 0.0
        else:
            vwap_dev = 0.0

        # --- 背驰检测（全量数据，lookback只看近期）---
        divergence = _detect_divergence(close, bar, lookback=min(20, len(df)))
        if not divergence:
            divergence = _detect_rsi_divergence(close, rsi6, lookback=min(20, len(df)))

        # --- 方向判断 ---
        direction = self._judge_direction(
            latest_bar, prev_bar, rsi_val, volume_price, roc_val, dif.iloc[-1]
        )

        # --- 评分（0-10）---
        score = self._score_minute(direction, volume_price, latest_bar, rsi_val, divergence, vwap_dev)

        return {
            'freq': freq,
            'direction': direction,
            'volume_price': volume_price,
            'vol_ratio': round(vol_ratio, 2),
            'vwap_dev_pct': round(vwap_dev, 2),
            'macd_bar': round(latest_bar, 6),
            'macd_bar_sign': '+' if latest_bar > 0 else '-',
            'macd_bar_expanding': bool(abs(latest_bar) > abs(prev_bar)),
            'rsi6': round(rsi_val, 2),
            'rsi12': round(float(rsi12.iloc[-1]), 2),
            'roc5': round(roc_val, 2),
            'divergence': divergence,
            'score': score,
        }

    def _judge_direction(self, macd_bar: float, prev_bar: float,
                          rsi: float, volume_price: str, roc: float,
                          dif: float) -> str:
        """综合多指标判断方向"""
        buy_score = 0
        sell_score = 0

        # MACD 柱
        if macd_bar > 0 and macd_bar > prev_bar:
            buy_score += 2
        elif macd_bar > 0:
            buy_score += 1
        elif macd_bar < 0 and macd_bar < prev_bar:
            sell_score += 2
        else:
            sell_score += 1

        # DIF 位置
        if dif > 0:
            buy_score += 1
        else:
            sell_score += 1

        # RSI
        if 40 <= rsi <= 65:
            buy_score += 1
        elif rsi < 35:
            buy_score += 1  # 超卖反弹
        elif rsi > 70:
            sell_score += 2

        # 量价
        vp_buy = {'价涨量增': 2, '价跌量缩': 1, '量价中性': 0}
        vp_sell = {'价跌量增': 2, '价涨量缩': 1}
        buy_score += vp_buy.get(volume_price, 0)
        sell_score += vp_sell.get(volume_price, 0)

        # ROC
        if roc > 1:
            buy_score += 1
        elif roc < -1:
            sell_score += 1

        if buy_score >= sell_score + 2:
            return 'buy'
        elif sell_score >= buy_score + 2:
            return 'sell'
        else:
            return 'neutral'

    def _score_minute(self, direction: str, volume_price: str,
                       macd_bar: float, rsi: float,
                       divergence: Optional[str], vwap_dev: float) -> float:
        """对分钟周期打分（0-10）"""
        base = 5.0

        # 方向
        if direction == 'buy':
            base += 2.0
        elif direction == 'sell':
            base -= 2.0

        # 量价
        vp_score = {
            '价涨量增': 1.0, '价跌量缩': 0.5,
            '价涨量缩': -0.5, '价跌量增': -1.0,
            '量价中性': 0.0
        }
        base += vp_score.get(volume_price, 0)

        # MACD 柱方向
        if macd_bar > 0:
            base += 0.5
        else:
            base -= 0.5

        # RSI
        if 40 <= rsi <= 65:
            base += 0.5
        elif rsi > 75 or rsi < 25:
            base -= 0.5

        # 背驰（顶背驰降分，底背驰有潜力）
        if divergence:
            if '顶' in divergence:
                base -= 1.5
            elif '底' in divergence:
                base += 1.0

        # VWAP 偏离
        if vwap_dev > 2:
            base -= 0.5   # 价格高于 VWAP 太多，回调风险
        elif vwap_dev < -2:
            base += 0.3   # 低于 VWAP，有支撑

        return round(max(0.0, min(10.0, base)), 1)

    def _composite_signal(self, signals: Dict) -> Tuple[str, float]:
        """
        综合评分（最小周期优先）：
        5min 贡献4分，15/30min 各2分，60/90/120min 各0.67分
        """
        weights = {
            '5min': 4.0, '15min': 2.0, '30min': 2.0,
            '60min': 0.67, '90min': 0.67, '120min': 0.67
        }
        direction_val = {'buy': 1, 'neutral': 0, 'sell': -1}

        weighted_dir = 0.0
        weighted_score = 0.0
        total_w = 0.0

        for freq, w in weights.items():
            sig = signals.get(freq, {})
            d = direction_val.get(sig.get('direction', 'neutral'), 0)
            s = sig.get('score', 5.0)
            weighted_dir += d * w
            weighted_score += s * w
            total_w += w

        avg_dir = weighted_dir / total_w if total_w > 0 else 0
        avg_score = weighted_score / total_w if total_w > 0 else 5.0

        if avg_dir > 0.25:
            composite = 'buy'
        elif avg_dir < -0.25:
            composite = 'sell'
        else:
            composite = 'neutral'

        return composite, round(avg_score, 1)

    def _timing_conclusion(self, signals: Dict, composite: str, strength: float) -> str:
        """生成择时文字结论"""
        direction_cn = {'buy': '买入', 'sell': '卖出', 'neutral': '观望'}
        d_str = direction_cn.get(composite, '观望')

        if strength >= 7.5:
            intensity = '强烈'
        elif strength >= 6.5:
            intensity = '较强'
        elif strength >= 5.5:
            intensity = '中等'
        else:
            intensity = '弱'

        # 高低周期是否一致
        low_dir = signals.get('5min', {}).get('direction', 'neutral')
        high_dir = signals.get('60min', {}).get('direction', 'neutral')
        mid_dir = signals.get('30min', {}).get('direction', 'neutral')

        if low_dir == high_dir == composite:
            alignment = '多周期共振'
        elif low_dir != high_dir:
            high_cn = direction_cn.get(high_dir, '观望')
            alignment = f"60min级别{high_cn}压力需关注"
        else:
            alignment = '中低周期分歧'

        return f"{intensity}{d_str}信号（强度{strength}/10），{alignment}"


# ======================================================================
#  便捷接口
# ======================================================================

def analyze_stock_technical(
    stock_input: str,
    analysis_type: str = 'all',
    n_days_micro: int = 10,
) -> Dict:
    """
    便捷分析接口，自动完成股票解析 + 数据采集 + 分析

    Args:
        stock_input:   股票名称或代码（支持中文/6位/标准ts_code）
        analysis_type: 'all' / 'macro' / 'micro'
        n_days_micro:  微观分钟线回溯天数（默认10天）

    Returns:
        {
          'ts_code': str,
          'stock_name': str,
          'macro': {...},    # analysis_type 含 macro 时
          'micro': {...},    # analysis_type 含 micro 时
        }
    """
    import re as _re
    import os as _os
    from dotenv import load_dotenv
    load_dotenv()
    _token = _os.getenv('TUSHARE_TOKEN')
    if not _token:
        raise ValueError('未找到 TUSHARE_TOKEN，请在 .env 中配置')
    from kk_common import get_finance_data_gateway
    _pro = get_finance_data_gateway()

    stock_input = stock_input.strip()
    # 标准 ts_code
    if _re.match(r'^\d{6}\.(SH|SZ)$', stock_input, _re.IGNORECASE):
        ts_code = stock_input.upper()
    # 纯6位数字
    elif _re.match(r'^\d{6}$', stock_input):
        suffix = 'SH' if stock_input.startswith('6') else 'SZ'
        if stock_input.startswith('8') or stock_input.startswith('4'):
            suffix = 'BJ'
        ts_code = f"{stock_input}.{suffix}"
    else:
        # 按名称搜索
        df = _pro.stock_basic(name=stock_input, list_status='L', fields='ts_code,name')
        if df.empty:
            df_all = _pro.stock_basic(list_status='L', fields='ts_code,name')
            match = df_all[df_all['name'].str.contains(stock_input, na=False)]
            if match.empty:
                raise ValueError(f"未找到匹配的股票: {stock_input}")
            row = match.iloc[0]
        else:
            row = df.iloc[0]
        ts_code, stock_name = row['ts_code'], row['name']
        print(f"\n[技术分析] 股票: {stock_name}（{ts_code}）")
        fetcher = TechnicalDataFetcher()
        analyzer = TechnicalAnalyzer(fetcher)
        result = {'ts_code': ts_code, 'stock_name': stock_name}
        if analysis_type in ('all', 'macro'):
            print(f"\n[宏观分析] 开始采集数据...")
            result['macro'] = analyzer.analyze_macro(ts_code)
        if analysis_type in ('all', 'micro'):
            print(f"\n[微观分析] 开始采集分钟线数据...")
            result['micro'] = analyzer.analyze_micro(ts_code, n_days=n_days_micro)
        return result

    # 获取股票名称
    df_name = _pro.stock_basic(ts_code=ts_code, fields='ts_code,name')
    stock_name = df_name.iloc[0]['name'] if not df_name.empty else ts_code
    print(f"\n[技术分析] 股票: {stock_name}（{ts_code}）")

    fetcher = TechnicalDataFetcher()
    analyzer = TechnicalAnalyzer(fetcher)

    result = {'ts_code': ts_code, 'stock_name': stock_name}

    if analysis_type in ('all', 'macro'):
        print(f"\n[宏观分析] 开始采集数据...")
        result['macro'] = analyzer.analyze_macro(ts_code)

    if analysis_type in ('all', 'micro'):
        print(f"\n[微观分析] 开始采集分钟线数据...")
        result['micro'] = analyzer.analyze_micro(ts_code, n_days=n_days_micro)

    return result


if __name__ == '__main__':
    import json
    result = analyze_stock_technical('宁德时代', analysis_type='macro')
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
