#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股缠论买卖点分析脚本

基于缠论理论对个股进行完整的形态学和动力学分析，识别三类买卖点。
数据通过 Tushare Pro API 实时获取，不依赖本地数据库。

核心功能：
  - 形态学分析：K线处理、分型识别、笔构建、线段构建、中枢识别
  - 动力学分析：MACD背驰、三类买卖点识别
  - 多级别联立：5分钟/30分钟/日线递归关系和区间套策略
  - 交易建议：入场价、止损位、止盈位

用法:
    # 单级别分析（日线）
    python scripts/analyze_stock_chan.py --stock 600519
    python scripts/analyze_stock_chan.py --stock 宁德时代

    # 多级别分析（推荐）
    python scripts/analyze_stock_chan.py --stock 茅台 --multi-level

    # 指定级别
    python scripts/analyze_stock_chan.py --stock 300750.SZ --level 30min

    # JSON 输出
    python scripts/analyze_stock_chan.py --stock 600519 --json
"""

import sys
import os
import io
import json
import argparse
import logging
import warnings
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# 屏蔽警告
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# ── 路径初始化 ──────────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Tushare API ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, '.env'))
from kk_common import get_finance_data_gateway
import pandas as pd

# ── 缠论模块 ────────────────────────────────────────────────────────────────
from chan_theory_v2.core.chan_engine import ChanEngine, AnalysisLevel, ChanAnalysisResult
from chan_theory_v2.models.kline import KLine, KLineList
from chan_theory_v2.models.enums import TimeLevel
from chan_theory_v2.config.chan_config import ChanConfig
from chan_theory_v2.models.dynamics import DynamicsConfig
from chan_theory_v2.core.trading_calendar import get_nearest_trading_date

# ── 日志 ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  数据获取层
# ═══════════════════════════════════════════════════════════════════════════

# 金融数据网关实例（延迟初始化，走 kk_common，不直接 import tushare）
_pro_api = None

def _get_pro_api():
    """获取（缓存的）金融数据网关实例。"""
    global _pro_api
    if _pro_api is None:
        _pro_api = get_finance_data_gateway()
    return _pro_api


def _fetch_kline_data(ts_code, asset, start_date, end_date, freq):
    """
    Fetch K-line data with fallback: try pro_bar first (richer data),
    fall back to pro.daily/weekly/monthly/pro_bar (minute) if pro_bar
    is unavailable for this token tier.

    Returns a DataFrame or None.
    """
    # Try pro_bar first
    try:
        df = get_finance_data_gateway().pro_bar(
            ts_code=ts_code, asset=asset,
            start_date=start_date, end_date=end_date, freq=freq
        )
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.debug(f'pro_bar failed ({e}), falling back to direct API')

    # Fallback to direct pro API for daily/weekly/monthly
    if freq in ('D', 'W', 'M') or freq in ('daily', 'weekly', 'monthly'):
        pro = _get_pro_api()
        api_map = {'D': 'daily', 'W': 'weekly', 'M': 'monthly',
                   'daily': 'daily', 'weekly': 'weekly', 'monthly': 'monthly'}
        api_name = api_map.get(freq, 'daily')
        try:
            api_func = getattr(pro, api_name, None)
            if api_func:
                df = api_func(ts_code=ts_code,
                              start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    return df
        except Exception as e:
            logger.debug(f'pro.{api_name} also failed: {e}')

    # For minute data, try pro_bar with adj='' explicitly
    if freq not in ('D', 'W', 'M', 'daily', 'weekly', 'monthly'):
        try:
            pro = _get_pro_api()
            # stk_mins supports 5min/15min/30min/60min
            min_freq = freq.replace('min', 'min')
            df = pro.stk_mins(ts_code=ts_code, freq=min_freq,
                              start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.debug(f'pro.stk_mins failed: {e}')

    return None


# ═══════════════════════════════════════════════════════════════════════════

class ChanDataFetcher:
    """缠论数据获取器（基于 Tushare Pro API）"""

    # 级别配置：(Tushare freq参数, 回溯天数, TimeLevel)
    LEVEL_CONFIG = {
        '5min':   ('5min',   5,    TimeLevel.MIN_5),
        '15min':  ('15min',  10,   TimeLevel.MIN_15),
        '30min':  ('30min',  30,   TimeLevel.MIN_30),
        '60min':  ('60min',  60,   TimeLevel.MIN_60),
        '90min':  ('60min',  90,   TimeLevel.MIN_90),
        '120min': ('60min',  120,  TimeLevel.MIN_120),
        'daily':  ('daily',  365,  TimeLevel.DAILY),
        'weekly': ('weekly', 1095, TimeLevel.WEEKLY),
        'monthly':('monthly',2555, TimeLevel.MONTHLY),
    }

    # 指数名称映射表
    INDEX_MAP = {
        '上证指数': '000001.SH', 'sh': '000001.SH', 'shanghai': '000001.SH',
        '深证成指': '399001.SZ', 'sz': '399001.SZ', 'shenzhen': '399001.SZ',
        '创业板指': '399006.SZ', 'cyb': '399006.SZ', 'chinext': '399006.SZ',
        '沪深300': '000300.SH', 'hs300': '000300.SH',
        '上证50': '000016.SH', 'sz50': '000016.SH',
        '中证500': '000905.SH', 'zz500': '000905.SH',
        '中证1000': '000852.SH', 'zz1000': '000852.SH',
        '科创50': '000688.SH', 'kc50': '000688.SH',
    }

    def __init__(self):
        token = os.environ.get('TUSHARE_TOKEN', '')
        if not token:
            raise ValueError('TUSHARE_TOKEN 环境变量未设置')
        self.pro = get_finance_data_gateway()
        self._stock_basic_cache = None

    def _get_stock_basic(self) -> pd.DataFrame:
        """缓存股票基本信息"""
        if self._stock_basic_cache is None:
            try:
                self._stock_basic_cache = self.pro.stock_basic(
                    exchange='', list_status='L',
                    fields='ts_code,name'
                )
            except Exception:
                self._stock_basic_cache = pd.DataFrame(columns=['ts_code', 'name'])
        return self._stock_basic_cache

    def normalize_index_code(self, index_input: str) -> Optional[tuple]:
        """标准化指数代码，返回: (ts_code, index_name) 或 None"""
        if index_input in self.INDEX_MAP:
            ts_code = self.INDEX_MAP[index_input]
            name_map = {v: k for k, v in self.INDEX_MAP.items()}
            name = name_map.get(ts_code, index_input)
            return (ts_code, name)

        if '.' in index_input and len(index_input.split('.')[0]) == 6:
            name_map = {v: k for k, v in self.INDEX_MAP.items()}
            name = name_map.get(index_input, index_input)
            return (index_input, name)

        if index_input.isdigit() and len(index_input) == 6:
            suffix = '.SH' if index_input[0] in ['0', '5', '6'] else '.SZ'
            ts_code = index_input + suffix
            name_map = {v: k for k, v in self.INDEX_MAP.items()}
            name = name_map.get(ts_code, ts_code)
            return (ts_code, name)

        return None

    def get_index_klines(self, ts_code: str, level: str = 'daily',
                         min_count: int = 100) -> Optional[KLineList]:
        """获取指数K线数据（通过 Tushare API）"""
        if level not in ['daily', 'weekly', 'monthly']:
            logger.warning(f'指数不支持{level}级别，自动降级为daily')
            level = 'daily'

        if level not in self.LEVEL_CONFIG:
            logger.error(f'不支持的级别: {level}')
            return None

        _, lookback_days, time_level = self.LEVEL_CONFIG[level]

        try:
            current_date = datetime.now().date()
            end_date = current_date
            start_date = end_date - timedelta(days=lookback_days)

            df = _fetch_kline_data(
                ts_code=ts_code, asset='I',
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                freq=level
            )
            if df is None or df.empty:
                return None

            df = df.sort_values('trade_date').reset_index(drop=True)

            klines = []
            for _, row in df.iterrows():
                try:
                    ts_obj = datetime.strptime(str(row['trade_date']), '%Y%m%d')
                    klines.append(KLine(
                        timestamp=ts_obj,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=int(float(row.get('vol', row.get('amount', 0)))),
                        level=time_level
                    ))
                except Exception:
                    continue

            if len(klines) < min_count:
                logger.warning(f'指数{ts_code} {level}级别K线不足: {len(klines)} < {min_count}')

            return KLineList(klines, time_level) if klines else None

        except Exception as e:
            logger.error(f'获取指数K线失败: {e}')
            return None

    def normalize_stock_code(self, stock_input: str) -> Optional[tuple]:
        """标准化股票代码（通过 Tushare API 查询），返回: (ts_code, stock_name) 或 None"""
        try:
            df = self._get_stock_basic()
            if df.empty:
                return None

            # 如果已经是标准格式
            if '.' in stock_input and len(stock_input.split('.')[0]) == 6:
                match = df[df['ts_code'] == stock_input]
                if not match.empty:
                    return (match.iloc[0]['ts_code'], match.iloc[0]['name'])

            # 尝试作为股票代码查询
            if stock_input.isdigit() and len(stock_input) == 6:
                suffix = '.SH' if stock_input[0] in ['6', '5'] else '.SZ'
                ts_code = stock_input + suffix
                match = df[df['ts_code'] == ts_code]
                if not match.empty:
                    return (match.iloc[0]['ts_code'], match.iloc[0]['name'])

            # 尝试作为股票名称查询
            match = df[df['name'].str.contains(stock_input, case=False, na=False)]
            if not match.empty:
                return (match.iloc[0]['ts_code'], match.iloc[0]['name'])

        except Exception:
            pass
        return None

    def get_klines(self, ts_code: str, level: str = 'daily',
                   min_count: int = 100) -> Optional[KLineList]:
        """获取K线数据（通过 Tushare API）"""
        if level not in self.LEVEL_CONFIG:
            logger.error(f'不支持的级别: {level}')
            return None

        ts_freq, lookback_days, time_level = self.LEVEL_CONFIG[level]

        try:
            current_date = datetime.now().date()
            end_date = current_date
            start_date = end_date - timedelta(days=lookback_days)

            if level in ['daily', 'weekly', 'monthly']:
                df = _fetch_kline_data(
                    ts_code=ts_code, asset='E',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    freq=ts_freq
                )
                if df is None or df.empty:
                    return None

                df = df.sort_values('trade_date').reset_index(drop=True)

                klines = []
                for _, row in df.iterrows():
                    try:
                        ts_obj = datetime.strptime(str(row['trade_date']), '%Y%m%d')
                        klines.append(KLine(
                            timestamp=ts_obj,
                            open=float(row['open']),
                            high=float(row['high']),
                            low=float(row['low']),
                            close=float(row['close']),
                            volume=int(float(row.get('vol', row.get('amount', 0)))),
                            level=time_level
                        ))
                    except Exception:
                        continue
            else:
                # 分钟线
                df = _fetch_kline_data(
                    ts_code=ts_code, asset='E',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    freq=ts_freq
                )
                if df is None or df.empty:
                    return None

                # Tushare 分钟线 trade_time 格式: '2025-01-15 10:30:00'
                df = df.sort_values('trade_time').reset_index(drop=True)

                # 对于 90min 和 120min，需要从 60min 重采样
                if level in ['90min', '120min']:
                    df['trade_time'] = pd.to_datetime(df['trade_time'])
                    df.set_index('trade_time', inplace=True)
                    resample_freq = '90T' if level == '90min' else '120T'
                    df = df.resample(resample_freq, label='right', closed='right').agg({
                        'open': 'first', 'high': 'max',
                        'low': 'min', 'close': 'last', 'vol': 'sum'
                    }).dropna()
                    df.reset_index(inplace=True)

                klines = []
                time_col = 'trade_time'
                for _, row in df.iterrows():
                    try:
                        val = row[time_col]
                        if isinstance(val, str):
                            ts_obj = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                        else:
                            ts_obj = val.to_pydatetime()
                        klines.append(KLine(
                            timestamp=ts_obj,
                            open=float(row['open']),
                            high=float(row['high']),
                            low=float(row['low']),
                            close=float(row['close']),
                            volume=int(float(row.get('vol', row.get('amount', 0)))),
                            level=time_level
                        ))
                    except Exception:
                        continue

            if len(klines) < min_count:
                logger.warning(f'{ts_code} {level} K线数量不足: {len(klines)} < {min_count}')
                return None

            return KLineList(klines, time_level)

        except Exception as e:
            logger.error(f'{ts_code} {level} K线获取失败: {e}')
            return None


# ═══════════════════════════════════════════════════════════════════════════
#  缠论分析器
# ═══════════════════════════════════════════════════════════════════════════

class StockChanAnalyzer:
    """缠论分析器（支持个股和指数）"""

    def __init__(self):
        self.fetcher = ChanDataFetcher()
        self.engine = ChanEngine(
            chan_config=ChanConfig(),
            dynamics_config=DynamicsConfig()
        )

    def analyze_single_level(self, ts_code: str, stock_name: str,
                            level: str = 'daily',
                            target_type: str = 'stock') -> Optional[Dict[str, Any]]:
        """
        单级别缠论分析

        Args:
            ts_code: 股票/指数代码
            stock_name: 股票/指数名称
            level: 时间级别
            target_type: "stock" 或 "index"
        """
        # 获取K线数据
        if target_type == 'index':
            klines = self.fetcher.get_index_klines(ts_code, level)
        else:
            klines = self.fetcher.get_klines(ts_code, level)
        if klines is None:
            return None

        # 执行缠论分析
        try:
            time_level = self.fetcher.LEVEL_CONFIG[level][2]
            result = self.engine.analyze(
                data=klines,
                symbol=ts_code,
                time_level=time_level,
                analysis_level=AnalysisLevel.COMPLETE
            )

            formatted = self._format_result(result, stock_name, level)
            formatted['target_type'] = target_type
            return formatted

        except Exception as e:
            logger.error(f'缠论分析失败: {e}')
            return None

    def analyze_multi_level(self, ts_code: str, stock_name: str,
                           levels: List[str] = None,
                           target_type: str = 'stock') -> Optional[Dict[str, Any]]:
        """
        多级别缠论分析（增强版）

        借鉴 czsc 库的多级别联立决策思想，实现：
        1. 各级别独立分析
        2. 多级别买卖点确认
        3. 一致性分析和综合决策

        Args:
            ts_code: 股票代码
            stock_name: 股票名称
            levels: 时间级别列表

        Returns:
            多级别分析结果字典 或 None
        """
        if levels is None:
            # 默认全周期分析：指数只用日周月，个股用全周期
            if target_type == 'index':
                levels = ['daily', 'weekly', 'monthly']
            else:
                levels = ['5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']

        # 获取各级别K线数据
        level_data = {}
        failed_levels = []
        for level in levels:
            if target_type == 'index':
                klines = self.fetcher.get_index_klines(ts_code, level)
            else:
                klines = self.fetcher.get_klines(ts_code, level)
            if klines is not None:
                time_level = self.fetcher.LEVEL_CONFIG[level][2]
                level_data[time_level] = klines
            else:
                failed_levels.append(level)

        if not level_data:
            logger.error('所有级别数据获取失败')
            return None

        if failed_levels:
            logger.warning(f'部分级别数据获取失败: {", ".join(failed_levels)}')

        # 执行多级别分析
        try:
            # 使用增强版多级别分析
            analysis_result = self.engine.analyze_multi_level(level_data, ts_code)
            
            # 格式化结果
            return self._format_multi_level_result_enhanced(
                analysis_result, stock_name, list(level_data.keys())
            )

        except Exception as e:
            logger.error(f'多级别缠论分析失败: {e}')
            return None

    def _format_result(self, result: ChanAnalysisResult,
                      stock_name: str, level: str) -> Dict[str, Any]:
        """格式化单级别分析结果"""
        stats = result.get_statistics()

        # 买卖点信息
        buy_points = []
        sell_points = []
        for point in result.buy_sell_points:
            point_info = {
                'type': str(point.point_type),
                'price': round(point.price, 2),
                'timestamp': point.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'reliability': round(point.reliability, 3),
                'strength': round(point.strength, 3),
                'confirmed_by_higher': point.confirmed_by_higher_level,
                'confirmed_by_lower': point.confirmed_by_lower_level,
            }
            if point.point_type.is_buy():
                buy_points.append(point_info)
            else:
                sell_points.append(point_info)

        # 最新信号
        latest_signals = result.get_latest_signals(3)
        latest_signal_info = []
        for signal in latest_signals:
            latest_signal_info.append({
                'type': str(signal.point_type),
                'price': round(signal.price, 2),
                'timestamp': signal.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'reliability': round(signal.reliability, 3),
            })

        # 活跃中枢
        active_zhongshus = result.get_active_zhongshus()
        zhongshu_info = []
        for zs in active_zhongshus:
            zhongshu_info.append({
                'high': round(zs.high, 2),
                'low': round(zs.low, 2),
                'start_time': zs.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'stability': round(zs.stability, 3),
            })

        # ── 构建图表数据（K线 + 笔 + 线段 + 中枢 + 买卖点） ──
        chart_data = self._build_chart_data(result)

        formatted = {
            'stock_code': result.symbol,
            'stock_name': stock_name,
            'analysis_time': result.analysis_time.strftime('%Y-%m-%d %H:%M:%S'),
            'time_level': level,
            'morphology': {
                'klines_count': stats['klines_count'],
                'processed_klines_count': stats['processed_klines_count'],
                'fenxings_count': stats['fenxings_count'],
                'bis_count': stats['bis_count'],
                'segs_count': stats['segs_count'],
                'zhongshus_count': stats['zhongshus_count'],
            },
            'dynamics': {
                'backchi_count': stats['backchi_count'],
                'buy_points_count': stats['buy_points_count'],
                'sell_points_count': stats['sell_points_count'],
                'buy_points': buy_points,
                'sell_points': sell_points,
            },
            'assessment': {
                'trend_direction': stats['trend_direction'],
                'trend_strength': round(stats['trend_strength'], 3),
                'risk_level': round(stats['risk_level'], 3),
                'confidence_score': round(stats['confidence_score'], 3),
            },
            'trend_analysis': result.trend_analysis.to_dict() if result.trend_analysis else {'trend_type': result.trend_type.value, 'trend_type_cn': str(result.trend_type)},
            'trading_advice': {
                'recommended_action': stats['recommended_action'],
                'entry_price': round(result.entry_price, 2) if result.entry_price else None,
                'stop_loss': round(result.stop_loss, 2) if result.stop_loss else None,
                'take_profit': round(result.take_profit, 2) if result.take_profit else None,
            },
            'latest_signals': latest_signal_info,
            'active_zhongshus': zhongshu_info,
            'chart_data': chart_data,
        }

        # ── 添加信号融合评分 ──
        try:
            from chan_theory_v2.core.signal_scorer import get_signal_scorer
            scorer = get_signal_scorer()
            score_result = scorer.score_from_chan_result(result, result.time_level)
            formatted['signal_scores'] = score_result.to_dict()
        except Exception as e:
            logger.debug(f'信号融合评分计算失败: {e}')
            formatted['signal_scores'] = None

        return formatted

    def _build_chart_data(self, result: ChanAnalysisResult) -> Dict[str, Any]:
        """构建ECharts K线图所需的图表数据"""
        # K线数据（OHLCV）— 取最近120根，避免数据过大
        klines = result.processed_klines or result.klines
        # 取最近120根K线
        recent_klines = klines[-120:] if len(klines) > 120 else list(klines)

        kline_data = []
        dates = []
        volumes = []
        for kline in recent_klines:
            dt_str = kline.timestamp.strftime('%Y-%m-%d %H:%M')
            dates.append(dt_str)
            kline_data.append([
                round(kline.open, 2),
                round(kline.close, 2),
                round(kline.low, 2),
                round(kline.high, 2),
            ])
            volumes.append(round(kline.volume, 0))

        # 笔数据 — 连接分型端点的折线
        bi_lines = []
        for bi in result.bis:
            bi_lines.append({
                'start_time': bi.start_time.strftime('%Y-%m-%d %H:%M'),
                'end_time': bi.end_time.strftime('%Y-%m-%d %H:%M'),
                'start_price': round(bi.start_price, 2),
                'end_price': round(bi.end_price, 2),
                'direction': bi.direction.value,
            })

        # 线段数据 — 比笔更粗的折线
        seg_lines = []
        for seg in result.segs:
            seg_lines.append({
                'start_time': seg.start_time.strftime('%Y-%m-%d %H:%M'),
                'end_time': seg.end_time.strftime('%Y-%m-%d %H:%M'),
                'start_price': round(seg.start_price, 2),
                'end_price': round(seg.end_price, 2),
                'direction': seg.direction.value,
            })

        # 中枢数据 — 矩形区间
        zhongshu_zones = []
        for zs in result.zhongshus:
            zhongshu_zones.append({
                'start_time': zs.start_time.strftime('%Y-%m-%d %H:%M'),
                'end_time': zs.end_time.strftime('%Y-%m-%d %H:%M'),
                'high': round(zs.high, 2),
                'low': round(zs.low, 2),
                'center': round(zs.center, 2),
            })

        # 买卖点标记
        markers = []
        for point in result.buy_sell_points:
            dt_str = point.timestamp.strftime('%Y-%m-%d %H:%M')
            marker = {
                'time': dt_str,
                'price': round(point.price, 2),
                'type': 'buy' if point.point_type.is_buy() else 'sell',
                'label': str(point.point_type),
                'reliability': round(point.reliability, 3),
                'strength': round(point.strength, 3),
            }
            markers.append(marker)

        return {
            'dates': dates,
            'kline': kline_data,
            'volumes': volumes,
            'bi_lines': bi_lines,
            'seg_lines': seg_lines,
            'zhongshu_zones': zhongshu_zones,
            'markers': markers,
        }

    def _format_multi_level_result(self, results: Dict[TimeLevel, ChanAnalysisResult],
                                   stock_name: str, time_levels: List[TimeLevel] = None) -> Dict[str, Any]:
        """格式化多级别分析结果（旧版，保留兼容）"""
        level_map = {
            TimeLevel.MIN_5: '5min',
            TimeLevel.MIN_15: '15min',
            TimeLevel.MIN_30: '30min',
            TimeLevel.MIN_60: '60min',
            TimeLevel.MIN_90: '90min',
            TimeLevel.MIN_120: '120min',
            TimeLevel.DAILY: 'daily',
            TimeLevel.WEEKLY: 'weekly',
            TimeLevel.MONTHLY: 'monthly',
        }

        formatted_results = {}
        for time_level, result in results.items():
            level_str = level_map.get(time_level, time_level.value)
            formatted_results[level_str] = self._format_result(result, stock_name, level_str)

        # 多级别一致性分析：基于方向对齐度计算
        # 先获取综合方向（从consensus中提取，若不存在则用多数方向）
        directions = {}
        for time_level, result in results.items():
            directions[time_level] = getattr(result, 'trend_direction', 'consolidation')
        dir_counts = {}
        for d in directions.values():
            dir_counts[d] = dir_counts.get(d, 0) + 1
        overall_direction = max(dir_counts, key=dir_counts.get) if dir_counts else 'consolidation'

        consistency_scores = {}
        for time_level, result in results.items():
            level_str = level_map.get(time_level, time_level.value)
            level_dir = directions.get(time_level, 'consolidation')
            confidence = getattr(result, 'confidence_score', 0.5)
            if level_dir == overall_direction:
                # 方向一致：得分 = 置信度
                consistency_scores[level_str] = round(confidence, 3)
            elif level_dir == 'consolidation':
                # 震荡：部分一致，折半
                consistency_scores[level_str] = round(confidence * 0.5, 3)
            else:
                # 方向相反：不一致
                consistency_scores[level_str] = round(max(0, 1 - confidence), 3)

        return {
            'stock_name': stock_name,
            'analysis_type': 'multi_level',
            'levels': list(formatted_results.keys()),
            'level_results': formatted_results,
            'consistency_scores': consistency_scores,
        }

    def _format_multi_level_result_enhanced(self, analysis_result: Dict[str, Any],
                                            stock_name: str, 
                                            time_levels: List[TimeLevel] = None) -> Dict[str, Any]:
        """格式化增强版多级别分析结果"""
        level_map = {
            TimeLevel.MIN_5: '5min',
            TimeLevel.MIN_15: '15min',
            TimeLevel.MIN_30: '30min',
            TimeLevel.MIN_60: '60min',
            TimeLevel.MIN_90: '90min',
            TimeLevel.MIN_120: '120min',
            TimeLevel.DAILY: 'daily',
            TimeLevel.WEEKLY: 'weekly',
            TimeLevel.MONTHLY: 'monthly',
        }

        # 获取各级别结果
        level_results = analysis_result.get('level_results', {})
        consensus = analysis_result.get('consensus')
        summary = analysis_result.get('summary', {})

        # 格式化各级别结果
        formatted_results = {}
        for time_level, result in level_results.items():
            level_str = level_map.get(time_level, time_level.value)
            formatted_results[level_str] = self._format_result(result, stock_name, level_str)

        # 构建一致性得分：基于方向对齐度（非买卖点确认率）
        overall_dir = summary.get('overall_direction', 'consolidation') if summary else 'consolidation'
        consistency_scores = {}
        for time_level, result in level_results.items():
            level_str = level_map.get(time_level, time_level.value)
            level_dir = getattr(result, 'trend_direction', 'consolidation')
            confidence = getattr(result, 'confidence_score', 0.5)
            if level_dir == overall_dir:
                consistency_scores[level_str] = round(confidence, 3)
            elif level_dir == 'consolidation':
                consistency_scores[level_str] = round(confidence * 0.5, 3)
            else:
                consistency_scores[level_str] = round(max(0, 1 - confidence), 3)

        # 添加综合决策信息
        consensus_info = {}
        if consensus and summary:
            consensus_info = {
                'overall_direction': summary.get('overall_direction', 'unknown'),
                'overall_confidence': summary.get('overall_confidence', 0.0),
                'consistency_score': summary.get('consistency_score', 0.0),
                'recommended_action': summary.get('recommended_action', 'wait'),
                'position_size': summary.get('position_size', 0.0),
                'signal_distribution': summary.get('signal_distribution', {})
            }

        return {
            'stock_name': stock_name,
            'analysis_type': 'multi_level_enhanced',
            'levels': list(formatted_results.keys()),
            'level_results': formatted_results,
            'consistency_scores': consistency_scores,
            'consensus': consensus_info,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  格式化输出
# ═══════════════════════════════════════════════════════════════════════════

def print_header(stock_name: str, ts_code: str, analysis_type: str, type_label: str = ''):
    """打印报告头"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    type_cn = '多级别联立分析' if analysis_type == 'multi' else '单级别分析'
    label = f'{type_label}' if type_label else ''

    print()
    print('═' * 80)
    print(f'  📊  {stock_name}（{ts_code}）{label}缠论买卖点分析报告')
    print('═' * 80)
    print(f'  分析类型：{type_cn}')
    print(f'  分析时间：{now}')
    print(f'  数据来源：Tushare Pro API')
    print(f'  分析引擎：缠论引擎 V2.0（形态学 + 动力学）')
    print('─' * 80)


def print_single_level_result(result: Dict[str, Any]):
    """打印单级别分析结果"""
    level_cn_map = {
        '5min': '5分钟', '15min': '15分钟', '30min': '30分钟',
        '60min': '60分钟', '90min': '90分钟', '120min': '120分钟',
        'daily': '日线', 'weekly': '周线', 'monthly': '月线'
    }
    level_cn = level_cn_map.get(result['time_level'], result['time_level'])

    print(f"\n{'─' * 80}")
    print(f"  📈 {level_cn}级别分析")
    print(f"{'─' * 80}")

    # 形态学统计
    morph = result['morphology']
    print(f"\n  【形态学分析】")
    print(f"    K线处理: {morph['klines_count']} → {morph['processed_klines_count']} 根")
    print(f"    分型识别: {morph['fenxings_count']} 个")
    print(f"    笔构建:   {morph['bis_count']} 个")
    print(f"    线段构建: {morph['segs_count']} 个")
    print(f"    中枢识别: {morph['zhongshus_count']} 个")

    # 动力学分析
    dyn = result['dynamics']
    print(f"\n  【动力学分析】")
    print(f"    背驰分析: {dyn['backchi_count']} 个")
    print(f"    买点识别: {dyn['buy_points_count']} 个")
    print(f"    卖点识别: {dyn['sell_points_count']} 个")

    # 买卖点详情
    if dyn['buy_points']:
        print(f"\n  【买入信号】")
        for i, point in enumerate(dyn['buy_points'][:5], 1):
            confirmed = '✓' if point['confirmed_by_higher'] or point['confirmed_by_lower'] else ''
            print(f"    {i}. {point['type']} @{point['price']}元 "
                  f"(可靠度:{point['reliability']:.1%} 强度:{point['strength']:.2f}) "
                  f"{confirmed} {point['timestamp']}")

    if dyn['sell_points']:
        print(f"\n  【卖出信号】")
        for i, point in enumerate(dyn['sell_points'][:5], 1):
            confirmed = '✓' if point['confirmed_by_higher'] or point['confirmed_by_lower'] else ''
            print(f"    {i}. {point['type']} @{point['price']}元 "
                  f"(可靠度:{point['reliability']:.1%} 强度:{point['strength']:.2f}) "
                  f"{confirmed} {point['timestamp']}")

    # 综合评估
    assess = result['assessment']
    trend_cn = {'up': '上升趋势', 'down': '下降趋势', 'consolidation': '震荡整理'}.get(assess['trend_direction'], '未确定')
    print(f"\n  【综合评估】")
    print(f"    趋势方向: {trend_cn}")
    print(f"    趋势强度: {assess['trend_strength']:.1%}")
    print(f"    风险等级: {assess['risk_level']:.1%}")
    print(f"    可信度:   {assess['confidence_score']:.1%}")

    # 走势类型分析
    ta = result.get('trend_analysis')
    if ta and ta.get('trend_type') != 'unknown':
        print(f"\n  【走势类型分析】")
        print(f"    走势类型: {ta['trend_type_cn']}")
        ct = ta.get('current_trend')
        if ct:
            print(f"    当前走势段: {ct['type_cn']}")
            print(f"    起始价格: {ct['start_price']}元")
            print(f"    线段端点: {ct['end_price']}元")
            print(f"    最新收盘: {ct.get('latest_price', ta.get('latest_price', 'N/A'))}元")
            print(f"    区间涨幅: {ct.get('latest_change_pct', ct['change_pct'])}%")
        if ta.get('latest_price') and ta.get('data_start_price'):
            total_change = (ta['latest_price'] - ta['data_start_price']) / ta['data_start_price'] * 100 if ta['data_start_price'] > 0 else 0
            print(f"    数据区间: {ta['data_start_price']}元 → {ta['latest_price']}元 ({total_change:+.2f}%)")

    # 交易建议
    advice = result['trading_advice']
    action_cn = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'wait': '观望'}.get(advice['recommended_action'], '观望')
    print(f"\n  【交易建议】")
    print(f"    操作建议: {action_cn}")
    if advice['entry_price']:
        print(f"    入场价位: {advice['entry_price']}元")
    if advice['stop_loss']:
        print(f"    止损价位: {advice['stop_loss']}元")
    if advice['take_profit']:
        print(f"    止盈价位: {advice['take_profit']}元")

    # 活跃中枢
    if result['active_zhongshus']:
        print(f"\n  【活跃中枢】")
        for i, zs in enumerate(result['active_zhongshus'][:3], 1):
            print(f"    {i}. 区间: {zs['low']:.2f} - {zs['high']:.2f}元 "
                  f"(稳定度:{zs['stability']:.1%}) {zs['start_time']}")

    # 信号融合评分
    if result.get('signal_scores'):
        ss = result['signal_scores']
        print(f"\n  【信号融合评分】")
        print(f"    综合评分: {ss['final_score']:.1f}/100")
        dir_cn = {'bullish': '看多', 'bearish': '看空', 'neutral': '中性'}.get(ss['direction'], '中性')
        str_cn = {'strong': '强', 'medium': '中', 'weak': '弱'}.get(ss['strength'], '弱')
        print(f"    方向: {dir_cn} | 强度: {str_cn}")
        # 各类别评分
        if ss.get('category_scores'):
            cat_cn = {'cxt': '缠论形态', 'tas': '技术指标', 'vol': '成交量',
                      'bar': 'K线基础', 'pos': '位置', 'jcc': 'K线组合', 'sta': '统计'}
            scores_line = []
            for cat, score in ss['category_scores'].items():
                cn = cat_cn.get(cat, cat)
                scores_line.append(f"{cn}:{score:+.0f}")
            print(f"    各维度: {', '.join(scores_line)}")


def print_multi_level_result(result: Dict[str, Any]):
    """打印多级别分析结果"""
    print(f"\n{'═' * 80}")
    print(f"  🔍 多级别联立分析结果")
    print(f"{'═' * 80}")

    # 分组显示：分时周期 + 日周月周期
    intraday_levels = ['5min', '15min', '30min', '60min', '90min', '120min']
    daily_levels = ['daily', 'weekly', 'monthly']

    # 分时周期
    intraday_found = [l for l in result['levels'] if l in intraday_levels]
    if intraday_found:
        print(f"\n{'━' * 80}")
        print(f"  📊 分时周期分析")
        print(f"{'━' * 80}")
        for level in intraday_found:
            level_result = result['level_results'][level]
            print_single_level_result(level_result)

    # 日周月周期
    daily_found = [l for l in result['levels'] if l in daily_levels]
    if daily_found:
        print(f"\n{'━' * 80}")
        print(f"  📈 日周月周期分析")
        print(f"{'━' * 80}")
        for level in daily_found:
            level_result = result['level_results'][level]
            print_single_level_result(level_result)

    # 级别一致性
    print(f"\n{'─' * 80}")
    print(f"  【多级别一致性分析】")
    print(f"{'─' * 80}")

    level_cn_map = {
        '5min': '5分钟', '15min': '15分钟', '30min': '30分钟',
        '60min': '60分钟', '90min': '90分钟', '120min': '120分钟',
        'daily': '日线', 'weekly': '周线', 'monthly': '月线'
    }

    for level, score in result['consistency_scores'].items():
        level_cn = level_cn_map.get(level, level)
        print(f"    {level_cn}: {score:.1%}")
    
    # 打印综合决策（增强版）
    if 'consensus' in result and result['consensus']:
        consensus = result['consensus']
        print(f"\n{'━' * 80}")
        print(f"  【📊 多级别综合决策】")
        print(f"{'━' * 80}")
        
        direction_cn = {
            'up': '看涨 📈', 
            'down': '看跌 📉', 
            'consolidation': '震荡 ↔️',
            'unknown': '未知 ❓'
        }
        
        print(f"    综合方向: {direction_cn.get(consensus.get('overall_direction', 'unknown'), '未知')}")
        print(f"    综合可信度: {consensus.get('overall_confidence', 0):.1%}")
        print(f"    一致性得分: {consensus.get('consistency_score', 0):.1%}")
        
        action_cn = {
            'buy': '买入 🟢', 
            'sell': '卖出 🔴', 
            'hold': '持有 🟡', 
            'wait': '观望 ⚪'
        }
        print(f"    建议操作: {action_cn.get(consensus.get('recommended_action', 'wait'), '观望')}")
        print(f"    建议仓位: {consensus.get('position_size', 0):.1%}")
        
        # 信号分布
        dist = consensus.get('signal_distribution', {})
        if dist:
            print(f"\n    信号分布:")
            print(f"      看涨: {dist.get('bullish', 0)} 个级别")
            print(f"      看跌: {dist.get('bearish', 0)} 个级别")
            print(f"      中性: {dist.get('neutral', 0)} 个级别")


def print_summary():
    """打印总结"""
    print(f"\n{'─' * 80}")
    print(f"  ⚠️  免责声明：缠论技术分析仅供学习参考，不构成投资建议。")
    print(f'  📊  数据来源：Tushare Pro API  |  分析引擎：缠论引擎 V2.0（多信号融合）')
    print()


# ═══════════════════════════════════════════════════════════════════════════
#  图表生成（matplotlib 缠论K线图）
# ═══════════════════════════════════════════════════════════════════════════

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.dates as mdates
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


class ChanChartGenerator:
    """缠论图表生成器（matplotlib）"""

    COLORS = {
        'bg_dark': '#1a1a2e',
        'bg_panel': '#16213e',
        'gold': '#e6b800',
        'white': '#ffffff',
        'gray': '#888888',
        'red': '#e74c3c',
        'green': '#2ecc71',
        'orange': '#f39c12',
        'yellow': '#f1c40f',
        'purple': '#9b59b6',
        'light_green': '#82e0aa',
        'blue': '#3498db',
    }

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        plt.rcParams['font.sans-serif'] = ['SimHei', 'PingFang SC', 'STHeiti', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['figure.facecolor'] = self.COLORS['bg_dark']
        plt.rcParams['axes.facecolor'] = self.COLORS['bg_panel']
        plt.rcParams['axes.edgecolor'] = self.COLORS['gray']
        plt.rcParams['axes.labelcolor'] = self.COLORS['white']
        plt.rcParams['text.color'] = self.COLORS['white']
        plt.rcParams['xtick.color'] = self.COLORS['white']
        plt.rcParams['ytick.color'] = self.COLORS['white']

    def generate_kline_chart(self, result: dict, stock_name: str,
                             level: str = 'daily') -> Optional[str]:
        """生成缠论K线图（含笔、线段、中枢、买卖点标注）"""
        if not HAS_MPL:
            return None

        cd = result.get('chart_data')
        if not cd or not cd.get('kline'):
            return None

        dates = cd['dates']
        klines = cd['kline']       # [[open, close, low, high], ...]
        volumes = cd.get('volumes', [])
        bi_lines = cd.get('bi_lines', [])
        seg_lines = cd.get('seg_lines', [])
        zs_zones = cd.get('zhongshu_zones', [])
        markers = cd.get('markers', [])

        n = len(dates)
        x = np.arange(n)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9),
                                        gridspec_kw={'height_ratios': [4, 1]},
                                        sharex=True)
        fig.patch.set_facecolor(self.COLORS['bg_dark'])

        # ── K线 ──
        for i, k in enumerate(klines):
            o, c, lo, hi = k
            color = self.COLORS['red'] if c >= o else self.COLORS['green']
            # 影线
            ax1.plot([x[i], x[i]], [lo, hi], color=color, linewidth=0.8)
            # 实体
            body_lo = min(o, c)
            body_hi = max(o, c)
            rect = FancyBboxPatch((x[i] - 0.35, body_lo), 0.7, max(body_hi - body_lo, 0.01),
                                   boxstyle="square,pad=0",
                                   facecolor=color, edgecolor=color, linewidth=0.5)
            ax1.add_patch(rect)

        # ── 笔（橙色折线） ──
        if bi_lines:
            date_idx_map = self._build_date_idx_map(dates)
            for bi in bi_lines:
                si = self._find_idx(date_idx_map, dates, bi['start_time'])
                ei = self._find_idx(date_idx_map, dates, bi['end_time'])
                ax1.plot([si, ei], [bi['start_price'], bi['end_price']],
                         color=self.COLORS['orange'], linewidth=1.2, alpha=0.85, zorder=5)
                ax1.scatter([si], [bi['start_price']], color=self.COLORS['orange'], s=12, zorder=6)
                ax1.scatter([ei], [bi['end_price']], color=self.COLORS['orange'], s=12, zorder=6)

        # ── 线段（紫色粗线） ──
        if seg_lines:
            for seg in seg_lines:
                si = self._find_idx(date_idx_map, dates, seg['start_time'])
                ei = self._find_idx(date_idx_map, dates, seg['end_time'])
                ax1.plot([si, ei], [seg['start_price'], seg['end_price']],
                         color=self.COLORS['purple'], linewidth=2.5, alpha=0.9, zorder=7)
                ax1.scatter([si], [seg['start_price']], color=self.COLORS['purple'],
                            s=30, marker='D', zorder=8)
                ax1.scatter([ei], [seg['end_price']], color=self.COLORS['purple'],
                            s=30, marker='D', zorder=8)

        # ── 中枢（半透明矩形） ──
        for zs in zs_zones:
            si = self._find_idx(date_idx_map, dates, zs['start_time'])
            ei = self._find_idx(date_idx_map, dates, zs['end_time'])
            rect = patches.Rectangle((si - 0.5, zs['low']), ei - si + 1, zs['high'] - zs['low'],
                                      linewidth=1, edgecolor=self.COLORS['blue'],
                                      facecolor=self.COLORS['blue'], alpha=0.15, zorder=3)
            ax1.add_patch(rect)
            ax1.axhline(y=zs['high'], xmin=si/n, xmax=ei/n, color=self.COLORS['blue'],
                        linewidth=0.6, linestyle='--', alpha=0.4)
            ax1.axhline(y=zs['low'], xmin=si/n, xmax=ei/n, color=self.COLORS['blue'],
                        linewidth=0.6, linestyle='--', alpha=0.4)

        # ── 买卖点标记 ──
        for m in markers:
            mi = self._find_idx(date_idx_map, dates, m['time'])
            if m['type'] == 'buy':
                ax1.scatter([mi], [m['price']], color=self.COLORS['red'],
                            s=100, marker='^', zorder=10, edgecolors='white', linewidths=0.5)
                ax1.annotate(m['label'], (mi, m['price']),
                             textcoords="offset points", xytext=(0, 12),
                             fontsize=7, color=self.COLORS['red'], ha='center', zorder=10)
            else:
                ax1.scatter([mi], [m['price']], color=self.COLORS['green'],
                            s=100, marker='v', zorder=10, edgecolors='white', linewidths=0.5)
                ax1.annotate(m['label'], (mi, m['price']),
                             textcoords="offset points", xytext=(0, -15),
                             fontsize=7, color=self.COLORS['green'], ha='center', zorder=10)

        # ── 成交量 ──
        for i, v in enumerate(volumes):
            k = klines[i]
            color = self.COLORS['red'] if k[1] >= k[0] else self.COLORS['green']
            ax2.bar(x[i], v, width=0.7, color=color, alpha=0.6)

        # ── 格式化 ──
        step = max(1, n // 20)
        ax1.set_xticks(x[::step])
        ax1.set_xticklabels([dates[i].replace(' 00:00', '') for i in range(0, n, step)],
                            fontsize=7, rotation=30)
        ax1.set_title(f'{stock_name}（{result.get("stock_code", "")}）缠论分析 · {level}',
                      fontsize=14, color=self.COLORS['gold'], pad=10)
        ax1.grid(True, alpha=0.15)
        ax2.grid(True, alpha=0.1)
        ax2.set_ylabel('成交量', fontsize=9)

        # 图例
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color=self.COLORS['orange'], linewidth=1.5, label='笔'),
            Line2D([0], [0], color=self.COLORS['purple'], linewidth=2.5, label='线段'),
            patches.Patch(facecolor=self.COLORS['blue'], alpha=0.15, label='中枢'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor=self.COLORS['red'],
                   markersize=8, label='买点', linestyle='None'),
            Line2D([0], [0], marker='v', color='w', markerfacecolor=self.COLORS['green'],
                   markersize=8, label='卖点', linestyle='None'),
        ]
        ax1.legend(handles=legend_elements, loc='upper left', fontsize=8,
                   facecolor=self.COLORS['bg_panel'], edgecolor=self.COLORS['gray'],
                   labelcolor=self.COLORS['white'])

        plt.tight_layout()

        # 保存
        safe_name = stock_name.replace(' ', '').replace('*', 'ST')
        filepath = os.path.join(self.output_dir, f'chan_kline_{safe_name}_{level}.png')
        plt.savefig(filepath, dpi=150, facecolor=self.COLORS['bg_dark'],
                    bbox_inches='tight', pad_inches=0.2)
        plt.close(fig)
        return filepath

    def generate_consistency_chart(self, result: dict, stock_name: str) -> Optional[str]:
        """生成多级别一致性评分图"""
        if not HAS_MPL:
            return None

        scores = result.get('consistency_scores', {})
        if not scores:
            return None

        level_cn = {
            '5min': '5分钟', '15min': '15分钟', '30min': '30分钟',
            '60min': '60分钟', '90min': '90分钟', '120min': '120分钟',
            'daily': '日线', 'weekly': '周线', 'monthly': '月线',
        }
        labels = [level_cn.get(k, k) for k in scores.keys()]
        values = [v * 100 for v in scores.values()]

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor(self.COLORS['bg_dark'])

        colors = [self.COLORS['red'] if v >= 70 else self.COLORS['yellow'] if v >= 40
                  else self.COLORS['green'] for v in values]
        bars = ax.bar(labels, values, color=colors, alpha=0.8, width=0.6)

        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f'{v:.0f}%', ha='center', fontsize=9, color=self.COLORS['white'])

        ax.set_ylim(0, 105)
        ax.set_title(f'{stock_name} 多级别一致性评分', fontsize=13,
                     color=self.COLORS['gold'], pad=10)
        ax.set_ylabel('一致性 (%)', fontsize=10)
        ax.grid(axis='y', alpha=0.15)

        plt.tight_layout()
        safe_name = stock_name.replace(' ', '').replace('*', 'ST')
        filepath = os.path.join(self.output_dir, f'chan_consistency_{safe_name}.png')
        plt.savefig(filepath, dpi=150, facecolor=self.COLORS['bg_dark'], bbox_inches='tight')
        plt.close(fig)
        return filepath

    def _build_date_idx_map(self, dates: list) -> dict:
        """构建日期→索引的映射"""
        m = {}
        for i, d in enumerate(dates):
            m[d] = i
            m[d[:10]] = i  # 短格式
        return m

    def _find_idx(self, date_map: dict, dates: list, time_str: str) -> int:
        """查找时间对应的索引"""
        if time_str in date_map:
            return date_map[time_str]
        prefix = time_str[:10]
        if prefix in date_map:
            return date_map[prefix]
        # 二分查找
        for i, d in enumerate(dates):
            if d >= time_str:
                return i
        return len(dates) - 1


# ═══════════════════════════════════════════════════════════════════════════
#  Markdown 报告生成
# ═══════════════════════════════════════════════════════════════════════════

def _format_markdown_report(result: dict, analysis_type: str,
                             stock_name: str, ts_code: str,
                             charts: dict, output_dir: str) -> str:
    """生成 Markdown 格式的缠论分析报告（图文配合）"""
    lines = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _img(key: str) -> str:
        path = charts.get(key, '')
        if path:
            rel = os.path.relpath(path, output_dir)
            return f'\n![{key}]({rel})\n'
        return ''

    if analysis_type == 'single':
        r = result
        level_cn = {'5min': '5分钟', '15min': '15分钟', '30min': '30分钟',
                    '60min': '60分钟', '90min': '90分钟', '120min': '120分钟',
                    'daily': '日线', 'weekly': '周线', 'monthly': '月线'}.get(r['time_level'], r['time_level'])

        lines.extend([
            f'# 🕯️ {stock_name}（{ts_code}）缠论分析报告',
            '',
            f'> 分析时间：{now} | 级别：{level_cn} | 数据来源：Tushare Pro API',
            '',
            '---',
            '',
            '## 一、K线图（笔·线段·中枢·买卖点）',
            '',
            _img('kline'),
            '',
            '## 二、走势评估',
            '',
        ])

        assess = r.get('assessment', {})
        ta = r.get('trend_analysis', {})
        dir_cn = {'up': '上升', 'down': '下降', 'consolidation': '震荡'}.get(assess.get('trend_direction', ''), '未确定')
        lines.extend([
            f'| 指标 | 数值 |',
            f'|------|------|',
            f'| 走势类型 | {ta.get("trend_type_cn", "—")} |',
            f'| 趋势方向 | {dir_cn} |',
            f'| 趋势强度 | {assess.get("trend_strength", 0):.1%} |',
            f'| 置信度 | {assess.get("confidence_score", 0):.1%} |',
            f'| 风险等级 | {assess.get("risk_level", 0):.1%} |',
            '',
        ])

        # 形态学
        morph = r.get('morphology', {})
        lines.extend([
            '## 三、形态学结构',
            '',
            f'| 指标 | 数量 |',
            f'|------|------|',
            f'| K线数 | {morph.get("klines_count", 0)} |',
            f'| 有效K线 | {morph.get("processed_klines_count", 0)} |',
            f'| 分型数 | {morph.get("fenxings_count", 0)} |',
            f'| 笔数 | {morph.get("bis_count", 0)} |',
            f'| 线段数 | {morph.get("segs_count", 0)} |',
            f'| 中枢数 | {morph.get("zhongshus_count", 0)} |',
            '',
        ])

        # 买卖点
        dyn = r.get('dynamics', {})
        lines.append('## 四、买卖点信号\n')
        if dyn.get('buy_points_count', 0) > 0 or dyn.get('sell_points_count', 0) > 0:
            lines.append(f'买点 {dyn.get("buy_points_count", 0)} 个 | 卖点 {dyn.get("sell_points_count", 0)} 个\n')
            for bp in dyn.get('buy_points', [])[:5]:
                lines.append(f'- 🟢 **{bp["type"]}** @{bp["price"]}元 (可靠度:{bp["reliability"]:.1%})')
            for sp in dyn.get('sell_points', [])[:5]:
                lines.append(f'- 🔴 **{sp["type"]}** @{sp["price"]}元 (可靠度:{sp["reliability"]:.1%})')
        else:
            lines.append('当前周期未检测到买卖点信号')
        lines.append('')

        # 交易建议
        advice = r.get('trading_advice', {})
        action_cn = {'buy': '建议买入', 'sell': '建议卖出', 'hold': '持有', 'wait': '观望等待'}.get(advice.get('recommended_action', 'wait'), '观望')
        lines.extend([
            '## 五、交易建议',
            '',
            f'**操作建议：{action_cn}**',
            '',
            f'| 入场价 | 止损价 | 止盈价 |',
            f'|--------|--------|--------|',
            f'| {advice.get("entry_price") or "—"} | {advice.get("stop_loss") or "—"} | {advice.get("take_profit") or "—"} |',
            '',
        ])

        # 信号融合评分
        ss = r.get('signal_scores')
        if ss:
            lines.extend(['## 六、信号融合评分', ''])
            dir_cn2 = {'bullish': '看多', 'bearish': '看空', 'neutral': '中性'}.get(ss.get('direction', ''), '中性')
            lines.append(f'综合评分：**{ss.get("final_score", 0):.1f}**/100 | 方向：**{dir_cn2}** | 强度：{ss.get("strength", "—")}\n')
            if ss.get('category_scores'):
                cat_cn = {'cxt': '缠论形态', 'tas': '技术指标', 'vol': '成交量',
                          'bar': 'K线基础', 'pos': '位置', 'jcc': 'K线组合', 'sta': '统计'}
                lines.append('| 维度 | 评分 |')
                lines.append('|------|------|')
                for cat, score in ss['category_scores'].items():
                    lines.append(f'| {cat_cn.get(cat, cat)} | {score:+.0f} |')
                lines.append('')

    else:
        # 多级别
        consensus = result.get('consensus', {})
        lines.extend([
            f'# 🕯️ {stock_name}（{ts_code}）缠论多级别分析报告',
            '',
            f'> 分析时间：{now} | 级别：{" / ".join(result.get("levels", []))} | 数据来源：Tushare Pro API',
            '',
            '---',
            '',
            '## 一、多级别综合决策',
            '',
        ])

        if consensus:
            dir_cn = {'up': '看涨', 'down': '看跌', 'consolidation': '震荡', 'unknown': '未知'}.get(consensus.get('overall_direction', ''), '未知')
            action_cn = {'buy': '建议买入', 'sell': '建议卖出', 'hold': '持有', 'wait': '观望等待'}.get(consensus.get('recommended_action', 'wait'), '观望')
            lines.extend([
                f'| 指标 | 数值 |',
                f'|------|------|',
                f'| 综合方向 | {dir_cn} |',
                f'| 一致性 | {consensus.get("consistency_score", 0):.1%} |',
                f'| 置信度 | {consensus.get("overall_confidence", 0):.1%} |',
                f'| 操作建议 | {action_cn} |',
                f'| 建议仓位 | {consensus.get("position_size", 0):.0%} |',
                '',
            ])

        # 一致性图
        lines.extend(['## 二、多级别一致性评分', '', _img('consistency'), ''])

        # 各级别详情
        level_results = result.get('level_results', {})
        for level, lr in level_results.items():
            level_cn = {'5min': '5分钟', '15min': '15分钟', '30min': '30分钟',
                        '60min': '60分钟', '90min': '90分钟', '120min': '120分钟',
                        'daily': '日线', 'weekly': '周线', 'monthly': '月线'}.get(level, level)
            lines.extend([
                f'## 三·{level_cn} 级别详情',
                '',
            ])
            # 插入该级别的K线图
            kline_key = f'kline_{level}'
            if kline_key in charts:
                lines.append(_img(kline_key))
                lines.append('')

            assess = lr.get('assessment', {})
            ta = lr.get('trend_analysis', {})
            morph = lr.get('morphology', {})
            dir_cn = {'up': '上升', 'down': '下降', 'consolidation': '震荡'}.get(assess.get('trend_direction', ''), '—')
            lines.extend([
                f'**走势类型**：{ta.get("trend_type_cn", "—")} | **方向**：{dir_cn} | **强度**：{assess.get("trend_strength", 0):.1%} | **置信度**：{assess.get("confidence_score", 0):.1%}',
                '',
                f'笔={morph.get("bis_count", 0)} 线段={morph.get("segs_count", 0)} 中枢={morph.get("zhongshus_count", 0)} 买点={lr.get("dynamics",{}).get("buy_points_count",0)} 卖点={lr.get("dynamics",{}).get("sell_points_count",0)}',
                '',
            ])

    # 免责
    lines.extend([
        '---',
        '',
        '*免责声明：缠论买卖点不是100%准确，以上分析结果仅供参考，不构成投资建议。市场有风险，投资需谨慎。*',
        '',
        f'**报告生成：小s 智能体**',
        f'**分析引擎：缠论引擎 V2.0（形态学 + 动力学 + 信号融合）**',
    ])

    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='缠论买卖点分析 - 支持个股和指数，基于缠论理论的完整形态学和动力学分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  # 个股单级别分析
  python scripts/analyze_stock_chan.py --stock 600519 --level daily
  python scripts/analyze_stock_chan.py --stock 宁德时代 --level 30min

  # 个股多级别分析（默认全周期：分时+日周月）
  python scripts/analyze_stock_chan.py --stock 300750.SZ --multi-level

  # 指数分析（仅支持日/周/月线）
  python scripts/analyze_stock_chan.py --index 上证指数 --multi-level
  python scripts/analyze_stock_chan.py --index hs300 --level daily
  python scripts/analyze_stock_chan.py --index 000001.SH --multi-level

  # JSON 输出
  python scripts/analyze_stock_chan.py --stock 600519 --json
  python scripts/analyze_stock_chan.py --index 沪深300 --json
        '''
    )

    # --stock 和 --index 互斥
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument('--stock',
                       help='股票代码或名称（如：600519、茅台、300750.SZ）')
    target_group.add_argument('--index',
                       help='指数代码或名称（如：000001.SH、上证指数、hs300）')
    parser.add_argument('--level',
                       choices=['5min', '15min', '30min', '60min', '90min', '120min',
                               'daily', 'weekly', 'monthly'],
                       default='daily',
                       help='单级别分析的时间级别（默认：daily）')
    parser.add_argument('--multi-level', action='store_true',
                       help='多级别联立分析（指数默认日周月，个股默认全周期分时+日周月）')
    parser.add_argument('--levels', type=str,
                       help='自定义多级别分析的级别列表，逗号分隔（如：30min,60min,daily,weekly）')
    parser.add_argument('--json', action='store_true',
                       help='以 JSON 格式输出结果')
    parser.add_argument('--save', action='store_true',
                       help='保存报告到本地文件（含图表）')
    parser.add_argument('--output', '-o', type=str, default=None,
                       help='报告输出目录（默认：~/kk_Claw/kkStockClaw/ChanReport/）')

    args = parser.parse_args()

    # 初始化分析器
    analyzer = StockChanAnalyzer()

    # 确定目标类型
    if args.index:
        target_type = 'index'
        target_info = analyzer.fetcher.normalize_index_code(args.index)
        if target_info is None:
            print(f'[错误] 未找到指数: {args.index}')
            print(f'支持的指数名称: {", ".join(list(analyzer.fetcher.INDEX_MAP.keys())[:10])}...')
            sys.exit(1)
    else:
        target_type = 'stock'
        target_info = analyzer.fetcher.normalize_stock_code(args.stock)
        if target_info is None:
            print(f'[错误] 未找到股票: {args.stock}')
            sys.exit(1)

    ts_code, target_name = target_info

    # 执行分析
    if args.multi_level:
        # 解析自定义级别列表
        levels = None
        if args.levels:
            levels = [l.strip() for l in args.levels.split(',')]
            # 指数只能用日周月
            if target_type == 'index':
                invalid = [l for l in levels if l not in ['daily', 'weekly', 'monthly']]
                if invalid:
                    print(f'[警告] 指数不支持分钟线级别 {", ".join(invalid)}，已自动过滤')
                    levels = [l for l in levels if l in ['daily', 'weekly', 'monthly']]
            valid_levels = ['5min', '15min', '30min', '60min', '90min', '120min',
                          'daily', 'weekly', 'monthly']
            invalid = [l for l in levels if l not in valid_levels]
            if invalid:
                print(f'[错误] 无效的级别: {", ".join(invalid)}')
                sys.exit(1)

        result = analyzer.analyze_multi_level(ts_code, target_name, levels, target_type=target_type)
        analysis_type = 'multi'
    else:
        result = analyzer.analyze_single_level(ts_code, target_name, args.level, target_type=target_type)
        analysis_type = 'single'

    if result is None:
        print(f'[错误] 分析失败，请检查数据是否充足')
        sys.exit(1)

    # 确定输出目录
    output_dir = args.output or os.path.expanduser('~/kk_Claw/kkStockClaw/ChanReport')
    images_dir = os.path.join(output_dir, 'images')

    # 生成图表
    charts = {}
    if args.save and HAS_MPL:
        print('正在生成图表...')
        chart_gen = ChanChartGenerator(images_dir)

        if analysis_type == 'single':
            charts['kline'] = chart_gen.generate_kline_chart(result, target_name, args.level)
        else:
            # 多级别：为每个级别生成K线图
            for level, lr in result.get('level_results', {}).items():
                key = f'kline_{level}'
                charts[key] = chart_gen.generate_kline_chart(lr, target_name, level)
            charts['consistency'] = chart_gen.generate_consistency_chart(result, target_name)

        chart_count = sum(1 for v in charts.values() if v)
        print(f'  ✓ 生成 {chart_count} 张图表')

    # 输出结果
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        type_label = '指数' if target_type == 'index' else ''
        print_header(target_name, ts_code, analysis_type, type_label=type_label)
        if analysis_type == 'multi':
            print_multi_level_result(result)
        else:
            print_single_level_result(result)
        print_summary()

    # 保存报告
    if args.save:
        os.makedirs(output_dir, exist_ok=True)

        # 生成 Markdown 报告
        report_content = _format_markdown_report(
            result, analysis_type, target_name, ts_code, charts, output_dir)

        # 保存 Markdown
        safe_name = target_name.replace(' ', '').replace('*', 'ST')
        report_date = datetime.now().strftime('%Y%m%d_%H%M')
        md_filename = f'chan_{safe_name}_{ts_code.replace(".", "_")}_{report_date}.md'
        md_path = os.path.join(output_dir, md_filename)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        # 保存 JSON
        json_filename = f'chan_{safe_name}_{ts_code.replace(".", "_")}_{report_date}.json'
        json_path = os.path.join(output_dir, json_filename)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f'\n📄 报告已保存至:')
        print(f'  Markdown: {md_path}')
        print(f'  JSON:     {json_path}')
        chart_count = sum(1 for v in charts.values() if v)
        if chart_count:
            print(f'📊 共生成 {chart_count} 张图表，保存在: {images_dir}')


if __name__ == '__main__':
    main()
