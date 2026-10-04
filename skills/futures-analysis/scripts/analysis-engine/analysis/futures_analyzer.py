#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股指期货数据获取与分析模块

基于 Tushare Pro API 获取股指期货行情、持仓、基差数据，
并提供综合分析评分。

提供:
  - FuturesDataFetcher: 数据采集（行情K线、主力合约、机构持仓）
  - FuturesAnalyzer: 综合分析（趋势、基差、持仓信号、评分）
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd

# 金融数据网关初始化（走 kk_common，不直接 import tushare）
try:
    from kk_common import get_finance_data_gateway
    pro = get_finance_data_gateway()
except Exception:
    pro = None


# 品种代码映射: 简称 → Tushare 合约前缀
SYMBOL_MAP = {
    'IF': {'name': '沪深300股指期货', 'code_prefix': 'IF', 'index': '000300.SH'},
    'IC': {'name': '中证500股指期货', 'code_prefix': 'IC', 'index': '000905.SH'},
    'IH': {'name': '上证50股指期货', 'code_prefix': 'IH', 'index': '000016.SH'},
    'IM': {'name': '中证1000股指期货', 'code_prefix': 'IM', 'index': '000852.SH'},
}


class FuturesDataFetcher:
    """股指期货数据采集器"""

    def __init__(self):
        self.pro = pro

    def get_dominant_contract(self, symbol: str) -> Optional[str]:
        """获取主力合约代码

        fut_mapping 返回全市场合约映射（ts_code 为连续合约代码，如 IF.CFX、
        IFL.CFX；mapping_ts_code 为该连续合约映射的实际合约），同一交易日有多行
        映射，取最新交易日中出现最多的 mapping_ts_code 作为主力（众数）。
        """
        if not self.pro:
            return None
        try:
            df = self.pro.fut_mapping(symbol=symbol)
            if df is not None and not df.empty and 'mapping_ts_code' in df.columns:
                filtered = df[df['ts_code'].astype(str).str.startswith(symbol)]
                if not filtered.empty:
                    latest_date = filtered['trade_date'].max()
                    latest_rows = filtered[filtered['trade_date'] == latest_date]
                    codes = latest_rows['mapping_ts_code'].dropna().tolist()
                    if codes:
                        from collections import Counter
                        code = Counter(codes).most_common(1)[0][0]
                        return str(code)
        except Exception:
            pass
        # Fallback: construct a plausible contract
        year = datetime.now().year
        month = datetime.now().month
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        return f"{symbol}{str(next_year)[-2:]}{next_month:02d}"

    def get_daily_bars(self, ts_code: str, days: int = 30) -> pd.DataFrame:
        """获取日线行情"""
        if not self.pro:
            return pd.DataFrame()
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
        try:
            df = self.pro.fut_daily(ts_code=ts_code,
                                    start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df.sort_values('trade_date').reset_index(drop=True)
        except Exception:
            pass
        # Try without ts_code (get all then filter)
        try:
            df = self.pro.fut_daily(start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                filtered = df[df['ts_code'].str.startswith(ts_code[:2])]
                if not filtered.empty:
                    return filtered.sort_values('trade_date').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()

    def get_index_data(self, index_code: str, days: int = 30) -> pd.DataFrame:
        """获取现货指数数据"""
        if not self.pro:
            return pd.DataFrame()
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
        try:
            df = self.pro.index_daily(ts_code=index_code,
                                      start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df.sort_values('trade_date').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()

    def get_holding_data(self, ts_code: str) -> pd.DataFrame:
        """获取最近一个交易日机构持仓数据（兼容旧接口）"""
        history = self.get_holding_history(ts_code, n_days=1)
        return history[-1]['df'] if history else pd.DataFrame()

    def get_holding_history(self, ts_code: str, n_days: int = 6) -> List[Dict]:
        """获取最近 n_days 个交易日的机构持仓数据

        fut_holding 的 symbol 参数为短格式（如 IF2703），需去除交易所后缀；
        每次调用只返回一个交易日的全部席位持仓，因此需逐日回溯调用，
        直到凑齐 n_days 个有数据的交易日。

        Returns:
            [{'trade_date': 'YYYYMMDD', 'df': DataFrame}, ...] 按日期升序
        """
        if not self.pro:
            return []
        symbol = ts_code.split('.')[0]
        result = []
        seen = set()
        day = datetime.now()
        for _ in range(40):  # 最多回溯 40 个自然日凑齐 n_days 个交易日
            if len(result) >= n_days:
                break
            d = day.strftime('%Y%m%d')
            day -= timedelta(days=1)
            if d in seen:
                continue
            seen.add(d)
            try:
                df = self.pro.fut_holding(symbol=symbol, trade_date=d)
            except Exception:
                continue
            if df is not None and not df.empty:
                result.append({'trade_date': d, 'df': df})
        result.sort(key=lambda x: x['trade_date'])
        return result


def _safe_float(v):
    """NaN 安全浮点转换（fut_daily 部分字段存在 NaN）"""
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v):
    """NaN 安全整数转换"""
    return int(_safe_float(v))


def _citic_others_snapshot(day_df: pd.DataFrame, long_c: str, short_c: str,
                          long_chg_c: Optional[str], short_chg_c: Optional[str]) -> Dict:
    """计算单日中信 vs 其他机构多空单持仓与操作变化快照

    中信 = broker 含'中信'的席位；其他 = 前20席位汇总 - 中信。
    """
    snap = {'citic_long': 0, 'citic_short': 0, 'citic_long_chg': 0, 'citic_short_chg': 0,
            'others_long': 0, 'others_short': 0, 'others_long_chg': 0, 'others_short_chg': 0}
    if day_df is None or day_df.empty:
        return snap
    try:
        valid = day_df.dropna(subset=[long_c, short_c]) if long_c and short_c else day_df
        total_long = float(valid[long_c].sum()) if long_c else 0
        total_short = float(valid[short_c].sum()) if short_c else 0
        total_long_chg = float(valid[long_chg_c].sum()) if long_chg_c else 0
        total_short_chg = float(valid[short_chg_c].sum()) if short_chg_c else 0
        snap['others_long'] = int(total_long)
        snap['others_short'] = int(total_short)
        snap['others_long_chg'] = int(total_long_chg)
        snap['others_short_chg'] = int(total_short_chg)
        if 'broker' in day_df.columns:
            citic = day_df[day_df['broker'].astype(str).str.contains('中信', na=False)]
            if not citic.empty:
                r = citic.iloc[0]
                c_long = float(r.get(long_c, 0) or 0) if long_c else 0
                c_short = float(r.get(short_c, 0) or 0) if short_c else 0
                c_lchg = float(r.get(long_chg_c, 0) or 0) if long_chg_c else 0
                c_schg = float(r.get(short_chg_c, 0) or 0) if short_chg_c else 0
                snap['citic_long'] = int(c_long)
                snap['citic_short'] = int(c_short)
                snap['citic_long_chg'] = int(c_lchg)
                snap['citic_short_chg'] = int(c_schg)
                snap['others_long'] = int(total_long - c_long)
                snap['others_short'] = int(total_short - c_short)
                snap['others_long_chg'] = int(total_long_chg - c_lchg)
                snap['others_short_chg'] = int(total_short_chg - c_schg)
    except Exception:
        pass
    return snap


def _chg_action(v: float, long_side: bool = True) -> str:
    """操作方向描述：加多/减多（多单），加空/减空（空单）"""
    if v > 0:
        return '加多' if long_side else '加空'
    if v < 0:
        return '减多' if long_side else '减空'
    return '未变'


def _pair_conclusion(c: float, o: float, pos_label: str, neg_label: str) -> str:
    """双方操作对比结论：同向/分歧/观望"""
    if c > 0 and o > 0:
        return f'同向{pos_label}'
    if c < 0 and o < 0:
        return f'同向{neg_label}'
    if (c > 0 and o < 0) or (c < 0 and o > 0):
        return '方向分歧'
    if c == 0 and o == 0:
        return '均未变'
    return '一方观望'


def _overall_signal(c_lc: float, c_sc: float, o_lc: float, o_sc: float) -> str:
    """综合信号：一致做多/一致做空/操作方向分歧/一方观望"""
    c_nc = c_lc - c_sc
    o_nc = o_lc - o_sc
    if c_nc > 0 and o_nc > 0:
        return '一致做多'
    if c_nc < 0 and o_nc < 0:
        return '一致做空'
    if (c_nc > 0 and o_nc < 0) or (c_nc < 0 and o_nc > 0):
        return '操作方向分歧'
    if c_nc == 0 and o_nc == 0:
        return '均未变（观望）'
    return '一方观望'


class FuturesAnalyzer:
    """股指期货综合分析器"""

    def __init__(self, fetcher: FuturesDataFetcher):
        self.fetcher = fetcher

    def analyze_all(self, symbols: List[str] = None, days: int = 30) -> Dict[str, Any]:
        """
        全量分析

        Returns:
            {
                'symbols': {symbol: {'contracts':..., 'price':..., 'contango':..., 'holding':...}},
                'composite': {'avg_score':..., 'market_env':..., 'details':...}
            }
        """
        if symbols is None:
            symbols = ['IF', 'IC', 'IH', 'IM']

        all_symbols = {}
        details = {}
        scores = {}

        for sym in symbols:
            sym_info = SYMBOL_MAP.get(sym, {})
            sym_data = self._analyze_symbol(sym, sym_info, days)
            if sym_data:
                all_symbols[sym] = sym_data
                score, detail = self._score_symbol(sym_data)
                scores[sym] = score
                details[sym] = detail

        avg_score = sum(scores.values()) / len(scores) if scores else 50
        market_env = self._market_environment(avg_score)

        return {
            'symbols': all_symbols,
            'composite': {
                'avg_score': round(avg_score, 1),
                'market_env': market_env,
                'symbol_scores': scores,
                'details': details,
                'suggestions': self._generate_suggestions(avg_score, details),
                'divergence_signal': self._divergence_signal(scores),
            }
        }

    def _analyze_symbol(self, sym: str, sym_info: dict, days: int) -> Dict[str, Any]:
        """分析单个品种"""
        result = {'contracts': {}, 'price': {}, 'contango': {}, 'holding': {}}

        # 获取主力合约
        main_contract = self.fetcher.get_dominant_contract(sym)
        result['contracts'] = {
            'main_contract': main_contract or f'{sym}主力',
            'contracts': [main_contract] if main_contract else [],
        }

        # 行情数据（fut_daily 需完整合约代码，如 IF2609.CFX）
        prefix = sym_info.get('code_prefix', sym)
        bars = self.fetcher.get_daily_bars(main_contract or prefix, days)
        if bars is not None and not bars.empty:
            result['price'] = self._analyze_price(bars)

        # 基差数据
        index_code = sym_info.get('index', '')
        if index_code:
            index_df = self.fetcher.get_index_data(index_code, days)
            if index_df is not None and not index_df.empty:
                result['contango'] = self._analyze_contango(bars, index_df)

        # 持仓数据（多日历史，支撑当日/每日/每周操作变化对比）
        if main_contract:
            holding_history = self.fetcher.get_holding_history(main_contract)
            if holding_history:
                result['holding'] = self._analyze_holding(holding_history)

        return result

    def _analyze_price(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析价格趋势"""
        if df.empty:
            return {}

        latest = df.iloc[-1]
        close = float(latest.get('close', 0))
        settle = float(latest.get('settle', close))
        pre_settle = float(latest.get('pre_settle', close))
        # fut_daily 无 pct_chg 字段：用收盘价与昨收价计算当日涨跌幅
        pre_close = float(latest.get('pre_close', 0))
        pct_chg = round((close - pre_close) / pre_close * 100, 2) if pre_close else 0.0
        vol = int(float(latest.get('vol', 0)))
        oi = int(float(latest.get('oi', 0)))

        # 均线
        closes = df['close'].astype(float)
        ma5 = float(closes.tail(5).mean()) if len(closes) >= 5 else close
        ma10 = float(closes.tail(10).mean()) if len(closes) >= 10 else close
        ma20 = float(closes.tail(20).mean()) if len(closes) >= 20 else close

        # 趋势判断
        if close > ma5 > ma10 > ma20:
            trend = '多头排列'
        elif close < ma5 < ma10 < ma20:
            trend = '空头排列'
        elif close > ma5:
            trend = '偏多震荡'
        else:
            trend = '偏空震荡'

        # 振幅
        high20 = float(df['high'].astype(float).tail(20).max()) if len(df) >= 20 else float(df['high'].astype(float).max())
        low20 = float(df['low'].astype(float).tail(20).min()) if len(df) >= 20 else float(df['low'].astype(float).min())
        avg_amp = float(((df['high'].astype(float) - df['low'].astype(float)) / df['close'].astype(float).replace(0, float('nan'))).tail(10).mean() * 100) if len(df) >= 10 else 0

        # OI 变化
        oi_chg = int(float(latest.get('oi_chg', 0)))
        vol_5d = int(df['vol'].astype(float).tail(5).mean()) if len(df) >= 5 else vol

        # 历史数据（用于图表）
        history = []
        for _, row in df.tail(30).iterrows():
            history.append({
                'date': str(row.get('trade_date', '')),
                'close': float(row.get('close', 0)),
                'vol': int(float(row.get('vol', 0))),
                'oi': int(float(row.get('oi', 0))),
            })

        # 逐日明细（周度逐日走势表用；df 已按 trade_date 升序）
        daily = []
        prev_close = None
        for _, row in df.iterrows():
            td = str(row.get('trade_date', ''))
            if len(td) == 8:
                td = f"{td[:4]}-{td[4:6]}-{td[6:]}"
            c = _safe_float(row.get('close'))
            pc = _safe_float(row.get('pre_close')) or prev_close or 0
            pct = round((c - pc) / pc * 100, 2) if pc else 0.0
            daily.append({
                'date': td,
                'close': c,
                'settle': _safe_float(row.get('settle')) or c,
                'pct_chg': pct,
                'vol': _safe_int(row.get('vol')),
                'oi': _safe_int(row.get('oi')),
                'oi_chg': _safe_int(row.get('oi_chg')),
            })
            prev_close = c

        return {
            'latest_date': str(latest.get('trade_date', '-')),
            'close': close,
            'settle': settle,
            'pct_chg': pct_chg,
            'daily': daily,
            'ma5': round(ma5, 1),
            'ma10': round(ma10, 1),
            'ma20': round(ma20, 1),
            'trend': trend,
            'high20': round(high20, 1),
            'low20': round(low20, 1),
            'avg_amplitude_10d': round(avg_amp, 2),
            'oi': oi,
            'oi_chg': oi_chg,
            'oi_trend': '增仓' if oi_chg > 0 else '减仓' if oi_chg < 0 else '持平',
            'vol': vol,
            'vol_5d_avg': vol_5d,
            'vol_signal': '放量' if vol > vol_5d * 1.2 else '缩量' if vol < vol_5d * 0.8 else '正常',
            'history': history,
        }

    def _analyze_contango(self, fut_df: pd.DataFrame, index_df: pd.DataFrame) -> Dict[str, Any]:
        """分析基差/贴升水"""
        if fut_df.empty or index_df.empty:
            return {}

        fut_close = float(fut_df.iloc[-1].get('close', 0))
        spot_close = float(index_df.iloc[-1].get('close', 0))

        if spot_close == 0:
            return {}

        basis = fut_close - spot_close
        basis_rate = (basis / spot_close) * 100

        if basis_rate > 0.5:
            sentiment = '升水（偏多预期）'
        elif basis_rate < -0.5:
            sentiment = '贴水（偏空预期）'
        else:
            sentiment = '基差正常'

        # 逐日基差率（按 trade_date 对齐期货与现货），周均 = 最近 5 个交易日均值
        daily = []
        try:
            fut_merge = fut_df[['trade_date', 'close']].dropna()
            spot_merge = index_df[['trade_date', 'close']].dropna()
            merged = fut_merge.merge(spot_merge, on='trade_date', suffixes=('_fut', '_spot'))
            for _, row in merged.tail(5).iterrows():
                td = str(row.get('trade_date', ''))
                if len(td) == 8:
                    td = f"{td[:4]}-{td[4:6]}-{td[6:]}"
                s = float(row.get('close_spot', 0))
                f = float(row.get('close_fut', 0))
                if s == 0:
                    continue
                b = f - s
                daily.append({'date': td, 'basis': round(b, 2), 'basis_pct': round(b / s * 100, 4)})
        except Exception:
            daily = []
        week_avg_basis_pct = round(sum(d['basis_pct'] for d in daily) / len(daily), 3) if daily else None

        return {
            'spot_price': round(spot_close, 1),
            'futures_price': round(fut_close, 1),
            'near_basis': round(basis, 1),
            'near_basis_rate': round(basis_rate, 2),
            'avg_basis_rate': round(basis_rate, 2),
            'week_avg_basis_pct': week_avg_basis_pct,
            'daily': daily,
            'sentiment': sentiment,
        }

    def _analyze_holding(self, history: Any) -> Dict[str, Any]:
        """分析机构持仓（支持多日历史）

        history: 单日 DataFrame，或 [{'trade_date': 'YYYYMMDD', 'df': DataFrame}, ...]（升序）。
        Tushare fut_holding 字段：broker / long_hld / short_hld / long_chg / short_chg。
        输出结构对齐 analyze_futures.py 的打印格式（top10_long/top10_short 席位明细、
        中信 vs 其他机构汇总与信号、当日/每日/每周多空单操作变化对比）。
        """
        # 兼容单日 DataFrame 输入
        if isinstance(history, pd.DataFrame):
            history = [{'trade_date': datetime.now().strftime('%Y%m%d'), 'df': history}]
        if not history:
            return {}
        df = history[-1]['df']  # 最新交易日
        if df.empty:
            return {}

        # 字段兼容解析（供单日分析与多日趋势共用）
        def pick(*names):
            for n in names:
                if n in df.columns:
                    return n
            return None

        long_c = pick('long_vol', 'long_hld')
        short_c = pick('short_vol', 'short_hld')
        long_chg_c = pick('long_chg')
        short_chg_c = pick('short_chg')

        result = {
            'top10_long': [],
            'top10_short': [],
            'citic_signal': '-',
            'position_signal': '-',
            'chg_signal': '-',
            'total_long': 0, 'total_short': 0,
            'net_position': 0, 'net_chg': 0, 'ls_ratio': 0.0,
            'citic_long': 0, 'citic_short': 0, 'citic_net': 0, 'citic_net_chg': 0,
            'others_long': 0, 'others_short': 0, 'others_net': 0, 'others_net_chg': 0,
            'others_signal': '-', 'citic_vs_others_signal': '-',
        }

        try:
            if long_c and short_c:
                valid = df.dropna(subset=[long_c, short_c])
                total_long = float(valid[long_c].sum())
                total_short = float(valid[short_c].sum())
                net = total_long - total_short
                result['total_long'] = int(total_long)
                result['total_short'] = int(total_short)
                result['net_position'] = int(net)
                result['ls_ratio'] = round(total_long / total_short, 3) if total_short else 0.0
                if total_long > total_short * 1.05:
                    result['position_signal'] = '净多头（偏多）'
                elif total_short > total_long * 1.05:
                    result['position_signal'] = '净空头（偏空）'
                else:
                    result['position_signal'] = '多空均衡'

                # 当日多空单变化信号
                if long_chg_c and short_chg_c:
                    net_chg = float(valid[long_chg_c].sum()) - float(valid[short_chg_c].sum())
                    result['net_chg'] = int(net_chg)
                    if net_chg > 0:
                        result['chg_signal'] = '净增仓'
                    elif net_chg < 0:
                        result['chg_signal'] = '净减仓'
                    else:
                        result['chg_signal'] = '持平'

                # 多头/空头前 10 席位
                top_long = valid.nlargest(10, long_c)
                top_short = valid.nlargest(10, short_c)
                result['top10_long'] = [
                    {'broker': str(r.get('broker', '-')),
                     'long_hld': int(float(r.get(long_c, 0))),
                     'long_chg': int(float(r.get(long_chg_c, 0))) if long_chg_c else 0}
                    for _, r in top_long.iterrows()
                ]
                result['top10_short'] = [
                    {'broker': str(r.get('broker', '-')),
                     'short_hld': int(float(r.get(short_c, 0))),
                     'short_chg': int(float(r.get(short_chg_c, 0))) if short_chg_c else 0}
                    for _, r in top_short.iterrows()
                ]

                # 中信期货信号（净持仓 + 当日净变化）
                if 'broker' in df.columns:
                    citic = df[df['broker'].astype(str).str.contains('中信', na=False)]
                    if not citic.empty:
                        citic_row = citic.iloc[0]
                        c_long = float(citic_row.get(long_c, 0) or 0)
                        c_short = float(citic_row.get(short_c, 0) or 0)
                        c_net = c_long - c_short
                        c_net_chg = (float(citic_row.get(long_chg_c, 0) or 0)
                                     - float(citic_row.get(short_chg_c, 0) or 0)) if long_chg_c and short_chg_c else 0
                        result['citic_long'] = int(c_long)
                        result['citic_short'] = int(c_short)
                        result['citic_net'] = int(c_net)
                        result['citic_net_chg'] = int(c_net_chg)
                        result['citic_signal'] = '偏多' if c_net > 0 else '偏空' if c_net < 0 else '中性'

                        # 其他十九家 = 总量 - 中信
                        others_long = total_long - c_long
                        others_short = total_short - c_short
                        result['others_long'] = int(others_long)
                        result['others_short'] = int(others_short)
                        result['others_net'] = int(others_long - others_short)
                        result['others_net_chg'] = int(result['net_chg'] - c_net_chg)
                        result['others_signal'] = ('偏多' if others_long > others_short else
                                                   '偏空' if others_short > others_long else '中性')

                        # 中信 vs 其他：比较净持仓方向
                        if c_net > 0 and (others_long - others_short) > 0:
                            result['citic_vs_others_signal'] = '同向做多'
                        elif c_net < 0 and (others_long - others_short) < 0:
                            result['citic_vs_others_signal'] = '同向做空'
                        elif c_net == 0 and (others_long - others_short) == 0:
                            result['citic_vs_others_signal'] = '均中性'
                        else:
                            result['citic_vs_others_signal'] = '方向分歧'
        except Exception:
            pass

        # ── 中信 vs 其他机构 当日多空单操作变化对比 ──
        try:
            snap = _citic_others_snapshot(df, long_c, short_c, long_chg_c, short_chg_c)
            c_lc = snap['citic_long_chg']
            c_sc = snap['citic_short_chg']
            o_lc = snap['others_long_chg']
            o_sc = snap['others_short_chg']
            c_nc = c_lc - c_sc
            o_nc = o_lc - o_sc
            result['citic_long_chg'] = c_lc
            result['citic_short_chg'] = c_sc
            result['others_long_chg'] = o_lc
            result['others_short_chg'] = o_sc
            result['citic_vs_others_chg_analysis'] = {
                'citic': {
                    'long_chg': c_lc, 'short_chg': c_sc, 'net_chg': c_nc,
                    'long_action': _chg_action(c_lc, True),
                    'short_action': _chg_action(c_sc, False),
                    'net_dir': '净加多' if c_nc > 0 else '净减空' if c_nc < 0 else '未变',
                },
                'others': {
                    'long_chg': o_lc, 'short_chg': o_sc, 'net_chg': o_nc,
                    'long_action': _chg_action(o_lc, True),
                    'short_action': _chg_action(o_sc, False),
                    'net_dir': '净加多' if o_nc > 0 else '净减空' if o_nc < 0 else '未变',
                },
                'comparison': {
                    'long_chg_conclusion': _pair_conclusion(c_lc, o_lc, '加多', '减多'),
                    'short_chg_conclusion': _pair_conclusion(c_sc, o_sc, '加空', '减空'),
                    'net_chg_conclusion': _pair_conclusion(c_nc, o_nc, '做多', '做空'),
                    'overall_signal': _overall_signal(c_lc, c_sc, o_lc, o_sc),
                },
            }
        except Exception:
            pass

        # ── 每日多空单操作变化趋势（中信 vs 其他） ──
        try:
            daily_trends = []
            for item in history:
                s = _citic_others_snapshot(item['df'], long_c, short_c, long_chg_c, short_chg_c)
                daily_trends.append({
                    'trade_date': item['trade_date'],
                    'citic_long_chg': s['citic_long_chg'],
                    'citic_short_chg': s['citic_short_chg'],
                    'citic_net_chg': s['citic_long_chg'] - s['citic_short_chg'],
                    'others_long_chg': s['others_long_chg'],
                    'others_short_chg': s['others_short_chg'],
                    'others_net_chg': s['others_long_chg'] - s['others_short_chg'],
                })
            result['daily_trends'] = daily_trends
        except Exception:
            pass

        # ── 每周多空单操作变化对比（最近 5 个交易日累计） ──
        try:
            recent = history[-5:]
            if len(recent) >= 2:
                wk = {'citic_long_chg': 0, 'citic_short_chg': 0,
                      'others_long_chg': 0, 'others_short_chg': 0}
                for item in recent:
                    s = _citic_others_snapshot(item['df'], long_c, short_c, long_chg_c, short_chg_c)
                    wk['citic_long_chg'] += s['citic_long_chg']
                    wk['citic_short_chg'] += s['citic_short_chg']
                    wk['others_long_chg'] += s['others_long_chg']
                    wk['others_short_chg'] += s['others_short_chg']
                c_nc = wk['citic_long_chg'] - wk['citic_short_chg']
                o_nc = wk['others_long_chg'] - wk['others_short_chg']
                result['weekly_chg_analysis'] = {
                    'citic': {
                        'long_chg': wk['citic_long_chg'], 'short_chg': wk['citic_short_chg'],
                        'net_chg': c_nc,
                    },
                    'others': {
                        'long_chg': wk['others_long_chg'], 'short_chg': wk['others_short_chg'],
                        'net_chg': o_nc,
                    },
                    'comparison': {
                        'net_chg_conclusion': _pair_conclusion(c_nc, o_nc, '做多', '做空'),
                        'overall_signal': _overall_signal(wk['citic_long_chg'], wk['citic_short_chg'],
                                                          wk['others_long_chg'], wk['others_short_chg']),
                    },
                    'days': len(recent),
                }
        except Exception:
            pass

        return result

    def _score_symbol(self, sym_data: dict) -> tuple:
        """评分单个品种"""
        score = 50
        detail = {'trend': '-', 'sentiment': '-', 'position_signal': '-',
                  'citic_signal': '-', 'citic_vs_others_signal': '-'}

        price = sym_data.get('price', {})
        if price:
            detail['trend'] = price.get('trend', '-')
            if '多头' in detail['trend']:
                score += 15
            elif '空头' in detail['trend']:
                score -= 15
            if price.get('pct_chg', 0) > 0:
                score += 5
            elif price.get('pct_chg', 0) < 0:
                score -= 5

        contango = sym_data.get('contango', {})
        if contango:
            detail['sentiment'] = contango.get('sentiment', '-')
            if '升水' in detail['sentiment']:
                score += 10
            elif '贴水' in detail['sentiment']:
                score -= 10

        holding = sym_data.get('holding', {})
        if holding:
            detail['position_signal'] = holding.get('position_signal', '-')
            detail['citic_signal'] = holding.get('citic_signal', '-')
            if '偏多' in detail['position_signal']:
                score += 10
            elif '偏空' in detail['position_signal']:
                score -= 10
            if detail['citic_signal'] == '偏多':
                score += 5
            elif detail['citic_signal'] == '偏空':
                score -= 5

        score = max(0, min(100, score))
        return score, detail

    def _market_environment(self, avg_score: float) -> str:
        if avg_score >= 65:
            return '偏多'
        elif avg_score <= 35:
            return '偏空'
        else:
            return '中性'

    def _divergence_signal(self, scores: dict) -> str:
        if not scores:
            return '-'
        max_s = max(scores.values())
        min_s = min(scores.values())
        diff = max_s - min_s
        if diff > 25:
            return f'品种分化明显（差值{diff}）'
        elif diff > 10:
            return f'品种略有分化（差值{diff}）'
        return f'品种走势一致（差值{diff}）'

    def _generate_suggestions(self, avg_score: float, details: dict) -> List[str]:
        suggestions = []
        if avg_score >= 65:
            suggestions.append('市场情绪偏多，可关注做多机会')
        elif avg_score <= 35:
            suggestions.append('市场情绪偏空，注意风险控制')
        else:
            suggestions.append('市场情绪中性，建议观望')

        for sym, d in details.items():
            if d.get('citic_signal') == '偏空':
                suggestions.append(f'{sym}：中信持仓偏空，注意风险')
            if '贴水' in d.get('sentiment', ''):
                suggestions.append(f'{sym}：基差贴水，市场预期偏空')

        return suggestions
