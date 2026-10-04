#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论MACD背驰选股脚本

基于缠论 MACD 红绿柱面积对比算法，全市场批量扫描背驰信号。
数据通过 Tushare Pro API 实时获取，不依赖本地数据库。

算法核心：
  底背驰 = 绿柱面积扩张 + 价格创新低 + MACD金叉确认 → 买入信号
  顶背驰 = 红柱面积萎缩 + 价格创新高 + MACD死叉确认 → 卖出信号

用法:
    # 扫描全市场（默认模式，取前50名）
    python scripts/run_chan_stock_selector.py

    # 指定股票池扫描
    python scripts/run_chan_stock_selector.py --pool hs300
    python scripts/run_chan_stock_selector.py --pool zz500
    python scripts/run_chan_stock_selector.py --pool zz1000

    # 指定时间周期
    python scripts/run_chan_stock_selector.py --freq 30min
    python scripts/run_chan_stock_selector.py --freq daily

    # 控制输出数量和信号类型
    python scripts/run_chan_stock_selector.py --top 20
    python scripts/run_chan_stock_selector.py --signal buy     # 仅买入信号
    python scripts/run_chan_stock_selector.py --signal sell    # 仅卖出信号
    python scripts/run_chan_stock_selector.py --signal all     # 买卖信号

    # 输出 JSON
    python scripts/run_chan_stock_selector.py --json

    # 组合示例
    python scripts/run_chan_stock_selector.py --pool hs300 --freq 30min --top 30 --signal buy
"""

import sys
import os
import json
import time
import argparse
import logging
import warnings
import pandas as pd

# 屏蔽 tushare 内部 FutureWarning（Series.fillna method 参数弃用警告）
warnings.filterwarnings('ignore', category=FutureWarning)
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any

# ── 路径初始化 ──────────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── 数据库 ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, '.env'))
from kk_common import get_finance_data_gateway

# ── 缠论模块 ────────────────────────────────────────────────────────────────
from chan_theory_v2.models.simple_backchi import SimpleBackchiAnalyzer
from chan_theory_v2.models.dynamics import MacdCalculator, MacdData
from chan_theory_v2.models.kline import KLine, KLineList
from chan_theory_v2.models.enums import TimeLevel
from chan_theory_v2.core.trading_calendar import get_nearest_trading_date

# ── 日志 ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Tushare API 数据获取层
# ═══════════════════════════════════════════════════════════════════════════

class TushareChanDataFetcher:
    """
    基于 Tushare Pro API 的缠论数据获取器
    全部数据通过 Tushare API 实时获取，适用于发布包
    """

    # 级别 → 回溯天数 + TimeLevel
    FREQ_MAP = {
        '30min': (30, TimeLevel.MIN_30),
        '60min': (40, TimeLevel.MIN_60),
        'daily': (90, TimeLevel.DAILY),
    }

    # 指数成分股映射
    INDEX_POOL_MAP = {
        'hs300':  '000300.SH',
        'zz500':  '000905.SH',
        'zz1000': '000852.SH',
        'gz2000': '399303.SZ',
        'zza500': '000510.SH',
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

    # ── 股票池获取 ──────────────────────────────────────────────────────────

    def get_stock_list(self, pool: str = 'all') -> List[Dict[str, str]]:
        """获取股票池列表（通过 Tushare API）"""
        try:
            df = self._get_stock_basic()
            if df.empty:
                return []

            # 过滤 ST、退市等
            import re
            mask = ~df['name'].str.contains('ST|退市|暂停|B$|N|C', regex=True, na=False)
            df = df[mask].reset_index(drop=True)

            if pool == 'all':
                return [{'symbol': row['ts_code'], 'name': row['name']} for _, row in df.iterrows()]
            else:
                # 按指数成分股筛选
                index_code = self.INDEX_POOL_MAP.get(pool)
                if index_code:
                    try:
                        # 获取最新成分股
                        iw_df = self.pro.index_weight(
                            index_code=index_code,
                            fields='con_code,trade_date'
                        )
                        if iw_df is not None and not iw_df.empty:
                            latest_date = iw_df['trade_date'].max()
                            codes = iw_df[iw_df['trade_date'] == latest_date]['con_code'].tolist()
                            # 匹配名称
                            name_df = df[df['ts_code'].isin(codes)]
                            name_map = dict(zip(name_df['ts_code'], name_df['name']))
                            result = [{'symbol': c, 'name': name_map.get(c, c)} for c in codes]
                            print(f'  ✓ {pool.upper()}（{latest_date}）：{len(result)} 只成分股')
                            return result
                    except Exception:
                        pass
                # 降级为全市场
                return [{'symbol': row['ts_code'], 'name': row['name']} for _, row in df.iterrows()]
        except Exception as e:
            logger.error(f'获取股票池失败: {e}')
            return []

    # ── K线获取 ─────────────────────────────────────────────────────────────

    def get_klines(self, symbol: str, freq: str = '30min',
                   min_count: int = 30) -> Optional[KLineList]:
        """通过 Tushare API 获取K线数据"""
        try:
            freq_conf = self.FREQ_MAP.get(freq, self.FREQ_MAP['30min'])
            lookback_days, time_level = freq_conf

            current_date = datetime.now().date()
            end_date = current_date
            start_date = end_date - timedelta(days=lookback_days)

            if freq == 'daily':
                df = get_finance_data_gateway().pro_bar(
                    ts_code=symbol, asset='E',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    freq='daily'
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
                df = get_finance_data_gateway().pro_bar(
                    ts_code=symbol, asset='E',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    freq=freq
                )
                if df is None or df.empty:
                    return None
                df = df.sort_values('trade_time').reset_index(drop=True)

                klines = []
                for _, row in df.iterrows():
                    try:
                        val = row['trade_time']
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
                return None

            return KLineList(klines, time_level)

        except Exception as e:
            logger.debug(f'{symbol} K线获取失败: {e}')
            return None

    # ── 股票名称查询 ─────────────────────────────────────────────────────────

    def get_stock_name(self, symbol: str) -> str:
        """通过 Tushare API 查询股票名称"""
        try:
            df = self._get_stock_basic()
            match = df[df['ts_code'] == symbol]
            if not match.empty:
                return match.iloc[0]['name']
        except Exception:
            pass
        return symbol


# ═══════════════════════════════════════════════════════════════════════════
#  缠论背驰选股核心逻辑
# ═══════════════════════════════════════════════════════════════════════════

class ChanStockSelector:
    """
    缠论MACD背驰选股器（Tushare直连版，支持多信号融合评分）
    直接调用 SimpleBackchiAnalyzer 完成背驰判断
    可选启用 SignalScorer 多信号融合评分
    """

    def __init__(self, freq: str = '30min', use_signal_scorer: bool = True):
        self.freq = freq
        self.use_signal_scorer = use_signal_scorer
        self.fetcher = TushareChanDataFetcher()
        self.macd_calc = MacdCalculator()
        self.analyzer  = SimpleBackchiAnalyzer()
        self._signal_scorer = None

    @property
    def signal_scorer(self):
        """延迟加载信号评分器"""
        if self._signal_scorer is None and self.use_signal_scorer:
            try:
                from chan_theory_v2.core.signal_scorer import SignalScorer
                self._signal_scorer = SignalScorer()
            except Exception:
                self.use_signal_scorer = False
        return self._signal_scorer

    # ── 单股分析 ─────────────────────────────────────────────────────────────

    def analyze_one(self, symbol: str, name: str) -> Optional[Dict[str, Any]]:
        """
        分析单只股票的背驰情况

        Returns:
            信号字典 或 None（无信号/数据不足）
        """
        klines = self.fetcher.get_klines(symbol, self.freq, min_count=30)
        if klines is None:
            return None

        close_prices = [k.close for k in klines]
        macd_data: List[MacdData] = self.macd_calc.calculate(close_prices)

        if len(macd_data) < 20:
            return None

        backchi_type, reliability, description = self.analyzer.analyze_backchi(
            klines, macd_data
        )

        if backchi_type is None or reliability < 0.3:
            return None

        # MACD 近期金叉/死叉（放宽确认窗口，避免双重过滤过严）
        # SimpleBackchiAnalyzer 已在背驰区域后5根K线内检查过金叉/死叉
        # 此处用更大窗口确认趋势方向一致性
        confirm_window = 8 if self.freq == 'daily' else 15
        has_golden = self._has_golden_cross(macd_data, window=confirm_window)
        has_death  = self._has_death_cross(macd_data, window=confirm_window)

        signal_type = '观望'
        if backchi_type == 'bottom' and has_golden:
            signal_type = '买入'
        elif backchi_type == 'top' and has_death:
            signal_type = '卖出'
        else:
            # 背驰已确认但无近期金叉/死叉，仍记录为弱信号
            if backchi_type == 'bottom':
                signal_type = '买入(待确认)'
            elif backchi_type == 'top':
                signal_type = '卖出(待确认)'
            else:
                return None

        current_price = klines[-1].close
        backchi_score = self._score(reliability, description, signal_type,
                            has_golden, has_death)

        # ── 多信号融合评分（可选） ──
        signal_fusion = None
        if self.use_signal_scorer and self.signal_scorer and len(klines) >= 50:
            try:
                fusion_result = self._calc_signal_fusion(klines)
                if fusion_result is not None:
                    signal_fusion = fusion_result.to_dict()
                    # 融合评分 = 背驰评分×60% + 信号融合评分×40%
                    fusion_score = fusion_result.final_score
                    score = round(backchi_score * 0.6 + fusion_score * 0.4, 2)
                else:
                    score = backchi_score
            except Exception:
                score = backchi_score
        else:
            score = backchi_score

        # 止损止盈
        if signal_type == '买入':
            stop_loss   = current_price * 0.95
            take_profit = current_price * (1 + reliability * 0.15)
        else:
            stop_loss   = current_price * 1.05
            take_profit = current_price * (1 - reliability * 0.15)

        return {
            'symbol':       symbol,
            'name':         name,
            'signal_type':  signal_type,
            'backchi_type': backchi_type,
            'reliability':  round(reliability, 3),
            'score':        round(score, 2),
            'backchi_score': round(backchi_score, 2),
            'signal_fusion': signal_fusion,
            'description':  description,
            'current_price': current_price,
            'stop_loss':    round(stop_loss, 2),
            'take_profit':  round(take_profit, 2),
            'has_golden':   has_golden,
            'has_death':    has_death,
            'signal_strength': self._signal_strength(score),
            'recommendation':  self._recommendation(signal_type, score),
            'kline_count':   len(klines),
        }

    # ── 全量选股 ─────────────────────────────────────────────────────────────

    def run(self, pool: str = 'all', signal_filter: str = 'all',
            top_n: int = 50) -> List[Dict[str, Any]]:
        """
        执行全量选股

        Args:
            pool:          股票池（all/hs300/zz500/zz1000）
            signal_filter: 信号过滤（all/buy/sell）
            top_n:         返回结果数量

        Returns:
            按综合评分降序排列的信号列表
        """
        stocks = self.fetcher.get_stock_list(pool)
        if not stocks:
            print('[错误] 股票池为空')
            return []

        total     = len(stocks)
        signals   = []
        processed = 0
        found     = 0

        print(f'\n  股票池：{pool.upper()} ({total} 只)  |  周期：{self.freq}  |  信号：{signal_filter}')
        print(f'  开始扫描...\n')

        for stock in stocks:
            symbol = stock['symbol']
            name   = stock['name']
            processed += 1

            if processed % 100 == 0:
                pct = processed / total * 100
                print(f'  进度：{processed}/{total} ({pct:.1f}%)  已找到信号：{found} 个')

            result = self.analyze_one(symbol, name)
            if result is None:
                continue

            # 信号类型过滤
            if signal_filter == 'buy'  and result['signal_type'] != '买入':
                continue
            if signal_filter == 'sell' and result['signal_type'] != '卖出':
                continue

            signals.append(result)
            found += 1

        # 按综合评分降序
        signals.sort(key=lambda x: x['score'], reverse=True)
        return signals[:top_n]

    # ── 辅助方法 ─────────────────────────────────────────────────────────────

    def _has_golden_cross(self, macd_data: List[MacdData], window: int = 3) -> bool:
        """最近window根K线内是否出现金叉"""
        if len(macd_data) < window:
            return False
        recent = macd_data[-window:]
        for i in range(1, len(recent)):
            p, c = recent[i - 1], recent[i]
            if p.dif <= p.dea and c.dif > c.dea and c.macd >= 0:
                return True
        return False

    def _has_death_cross(self, macd_data: List[MacdData], window: int = 3) -> bool:
        """最近window根K线内是否出现死叉"""
        if len(macd_data) < window:
            return False
        recent = macd_data[-window:]
        for i in range(1, len(recent)):
            p, c = recent[i - 1], recent[i]
            if p.dif >= p.dea and c.dif < c.dea and c.macd <= 0:
                return True
        return False

    def _score(self, reliability: float, description: str,
               signal_type: str, has_golden: bool, has_death: bool) -> float:
        """多维度综合评分（0-100）"""
        score = 0.0

        # 1. 背驰基础可靠度 30分
        score += reliability * 30

        # 2. MACD面积比 25分
        import re
        m = re.search(r'面积比([\d.]+)', description)
        if m:
            ar = float(m.group(1))
            if ar >= 50:   score += 25
            elif ar >= 20: score += 20 + (ar - 20) / 30 * 5
            elif ar >= 10: score += 15 + (ar - 10) / 10 * 5
            elif ar >= 5:  score += 10 + (ar - 5)  / 5  * 5
            else:          score += 5  + ar
        else:
            score += 12.5

        # 3. 价格背离度 20分
        m2 = re.search(r'价差([\d.]+)%', description)
        if m2:
            pd_ = float(m2.group(1))
            if pd_ >= 2.0:   score += 20
            elif pd_ >= 1.0: score += 15 + (pd_ - 1.0) * 5
            elif pd_ >= 0.5: score += 10 + (pd_ - 0.5) * 10
            else:            score += 5  + pd_ * 10
        else:
            score += 10

        # 4. 技术确认质量 15分
        if signal_type in ('买入', '卖出') and (has_golden or has_death):
            score += 15
        elif signal_type in ('买入(待确认)', '卖出(待确认)'):
            score += 5  # 弱信号，等待确认
        else:
            score += 7

        # 5. 微调（hash 避免分数完全相同）
        score += hash(signal_type + str(reliability)) % 100 / 10000

        return min(score, 100.0)

    @staticmethod
    def _signal_strength(score: float) -> str:
        if score >= 80: return '强'
        if score >= 60: return '中'
        return '弱'

    @staticmethod
    def _recommendation(signal_type: str, score: float) -> str:
        strength = '强烈推荐' if score >= 80 else '建议' if score >= 60 else '谨慎'
        return f'{strength}{signal_type}'

    def _calc_signal_fusion(self, klines):
        """基于K线数据生成信号融合评分"""
        try:
            from chan_theory_v2.signals import tas, bar, vol, pos, sta, jcc
            freq_map = {'30min': '30分钟', '60min': '60分钟', 'daily': '日线'}
            freq = freq_map.get(self.freq, self.freq)
            signals = {}
            bars_raw = list(klines)

            # tas 技术指标信号
            if len(bars_raw) >= 50:
                for fn_name, fn in [('tas_macd_cross', tas.tas_macd_cross),
                                     ('tas_double_ma', tas.tas_double_ma),
                                     ('tas_ma_system', tas.tas_ma_system),
                                     ('tas_dif_zero', tas.tas_dif_zero)]:
                    try: signals[fn_name] = fn(freq, bars_raw)
                    except Exception: pass
            if len(bars_raw) >= 30:
                for fn_name, fn in [('tas_boll_status', tas.tas_boll_status),
                                     ('tas_kdj_cross', tas.tas_kdj_cross),
                                     ('tas_rsi_status', tas.tas_rsi_status),
                                     ('tas_volume_price', tas.tas_volume_price)]:
                    try: signals[fn_name] = fn(freq, bars_raw)
                    except Exception: pass

            # vol 成交量信号
            if len(bars_raw) >= 20:
                for fn_name, fn in [('vol_ratio_signal', vol.vol_ratio_signal),
                                     ('vol_single_ma', vol.vol_single_ma),
                                     ('vol_break', vol.vol_break)]:
                    try: signals[fn_name] = fn(freq, bars_raw)
                    except Exception: pass

            # bar K线基础信号
            if len(bars_raw) >= 10:
                for fn_name, fn in [('bar_zdf', bar.bar_zdf),
                                     ('bar_section_momentum', bar.bar_section_momentum)]:
                    try: signals[fn_name] = fn(freq, bars_raw)
                    except Exception: pass

            # pos 位置信号
            if len(bars_raw) >= 20:
                for fn_name, fn in [('pos_above_ma', pos.pos_above_ma),
                                     ('pos_boll_position', pos.pos_boll_position)]:
                    try: signals[fn_name] = fn(freq, bars_raw)
                    except Exception: pass

            if not signals:
                return None
            return self.signal_scorer.score_all_signals(signals)
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════════════════
#  格式化输出
# ═══════════════════════════════════════════════════════════════════════════

def _pct(v: float, d: int = 2) -> str:
    s = '+' if v > 0 else ''
    return f'{s}{v:.{d}f}%'


def print_header(pool: str, freq: str, signal_filter: str):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pool_cn = {'all': '全市场', 'hs300': '沪深300', 'zz500': '中证500', 'zz1000': '中证1000'}.get(pool, pool)
    signal_cn = {'all': '全部', 'buy': '买入', 'sell': '卖出'}.get(signal_filter, signal_filter)

    print()
    print('═' * 72)
    print('  🔍  缠论 MACD 背驰选股报告')
    print('═' * 72)
    print(f'  股票池：{pool_cn}  |  分析周期：{freq}  |  信号类型：{signal_cn}')
    print(f'  分析时间：{now}')
    print(f'  数据来源：Tushare Pro API')
    print('─' * 72)


def print_results(signals: List[Dict[str, Any]], top_n: int):
    if not signals:
        print('\n  未发现符合条件的背驰信号\n')
        return

    buy_signals  = [s for s in signals if s['signal_type'] == '买入']
    sell_signals = [s for s in signals if s['signal_type'] == '卖出']

    print(f'\n  共发现 {len(signals)} 个信号（买入：{len(buy_signals)} | 卖出：{len(sell_signals)}）\n')

    # 表头
    print(f"  {'排名':>4}  {'代码':<12}  {'名称':<10}  {'信号':^4}  {'评分':>6}  {'强度':^4}  "
          f"{'可靠度':>6}  {'现价':>8}  {'止损':>8}  {'止盈':>8}  {'建议'}")
    print('  ' + '─' * 100)

    for i, sig in enumerate(signals, 1):
        signal_mark = '▲' if sig['signal_type'] == '买入' else '▼'
        strength_cn = {'强': '★★★', '中': '★★☆', '弱': '★☆☆'}.get(sig['signal_strength'], '')

        print(
            f"  {i:>4}  {sig['symbol']:<12}  {sig['name']:<10}  "
            f"{signal_mark}{sig['signal_type']:^3}  "
            f"{sig['score']:>6.1f}  {strength_cn:^6}  "
            f"{sig['reliability']:>6.1%}  "
            f"{sig['current_price']:>8.2f}  "
            f"{sig['stop_loss']:>8.2f}  "
            f"{sig['take_profit']:>8.2f}  "
            f"{sig['recommendation']}"
        )


def print_detail(signals: List[Dict[str, Any]], show_top: int = 10):
    """打印前N名的详细信号说明"""
    if not signals:
        return

    detail_signals = signals[:show_top]
    print(f'\n{"═" * 72}')
    print(f'  📊  Top {len(detail_signals)} 信号详情')
    print(f'{"═" * 72}')

    for i, sig in enumerate(detail_signals, 1):
        signal_icon = '🟢' if sig['signal_type'] == '买入' else '🔴'
        cross_info = '金叉✓' if sig['has_golden'] else '死叉✓' if sig['has_death'] else ''

        print(f'\n  {i}. {signal_icon} {sig["name"]}（{sig["symbol"]}）')
        print(f'     信号类型：{sig["signal_type"]}  |  强度：{sig["signal_strength"]}  |  综合评分：{sig["score"]:.1f}/100')
        if sig.get('backchi_score'):
            fusion_info = ''
            if sig.get('signal_fusion') and sig['signal_fusion'].get('final_score'):
                fusion_info = f"  |  信号融合：{sig['signal_fusion']['final_score']:.1f}"
            print(f'     背驰评分：{sig["backchi_score"]:.1f}{fusion_info}')
        print(f'     背驰类型：{"底背驰" if sig["backchi_type"] == "bottom" else "顶背驰"}  |  可靠度：{sig["reliability"]:.1%}  |  {cross_info}')
        print(f'     背驰描述：{sig["description"]}')
        print(f'     关键价位：现价 {sig["current_price"]:.2f}元  止损 {sig["stop_loss"]:.2f}元  止盈 {sig["take_profit"]:.2f}元')
        print(f'     投资建议：{sig["recommendation"]}')
        print(f'     参考K线：{sig["kline_count"]} 根')


def print_summary(signals: List[Dict[str, Any]], elapsed: float):
    print(f'\n{"─" * 72}')
    buy_cnt  = sum(1 for s in signals if s['signal_type'] == '买入')
    sell_cnt = sum(1 for s in signals if s['signal_type'] == '卖出')
    strong   = sum(1 for s in signals if s['signal_strength'] == '强')

    print(f'  扫描耗时：{elapsed:.1f}s  |  买入信号：{buy_cnt}  |  卖出信号：{sell_cnt}  |  强信号：{strong}')
    print(f'\n  ⚠️  免责声明：缠论技术分析仅供学习参考，不构成投资建议。股市有风险，投资需谨慎。')
    print(f'  📊  数据来源：Tushare Pro API  |  分析引擎：缠论 MACD 背驰算法 V2.0（多信号融合）')
    print()


# ═══════════════════════════════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='缠论MACD背驰选股 - 基于Tushare Pro API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  python scripts/run_chan_stock_selector.py
  python scripts/run_chan_stock_selector.py --pool hs300 --freq 30min --signal buy --top 30
  python scripts/run_chan_stock_selector.py --pool zz500 --freq daily --top 20
  python scripts/run_chan_stock_selector.py --pool hs300 --json
        '''
    )

    parser.add_argument('--pool', choices=['all', 'hs300', 'zz500', 'zz1000', 'gz2000', 'zza500'],
                        default='hs300',
                        help='股票池（默认：hs300）')
    parser.add_argument('--freq', choices=['30min', '60min', 'daily'],
                        default='30min',
                        help='分析周期（默认：30min）')
    parser.add_argument('--signal', choices=['all', 'buy', 'sell'],
                        default='all',
                        help='信号类型过滤（默认：all）')
    parser.add_argument('--top', type=int, default=50,
                        help='输出前N名（默认：50）')
    parser.add_argument('--detail', type=int, default=10,
                        help='打印详细说明的前N名（默认：10）')
    parser.add_argument('--no-signal-fusion', action='store_true',
                        help='禁用多信号融合评分（仅使用纯背驰评分）')
    parser.add_argument('--json', action='store_true',
                        help='以 JSON 格式输出结果')

    args = parser.parse_args()

    start_time = time.time()

    print_header(args.pool, args.freq, args.signal)

    # 执行选股
    selector = ChanStockSelector(freq=args.freq, use_signal_scorer=not args.no_signal_fusion)
    signals  = selector.run(
        pool=args.pool,
        signal_filter=args.signal,
        top_n=args.top
    )

    elapsed = time.time() - start_time

    # 输出
    if args.json:
        output = {
            'scan_time': datetime.now().isoformat(),
            'pool':      args.pool,
            'freq':      args.freq,
            'signal':    args.signal,
            'elapsed_s': round(elapsed, 1),
            'total':     len(signals),
            'signals':   signals
        }
        print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    else:
        print_results(signals, args.top)
        print_detail(signals, show_top=args.detail)
        print_summary(signals, elapsed)


if __name__ == '__main__':
    main()
