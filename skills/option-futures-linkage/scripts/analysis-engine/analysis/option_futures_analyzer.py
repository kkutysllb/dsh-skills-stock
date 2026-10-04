#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期指期权联动分析核心模块

数据源：Tushare Pro API
  - opt_basic / opt_daily：期权合约与日行情（SSE ETF 期权 + CFFEX 股指期权）
  - fund_daily：ETF 价格（ETF 期权标的）
  - index_daily：现货指数（股指期权标的与基差计算）
  - fut_mapping / fut_daily：期指主力合约与行情

期权维度：认沽认购（成交量/持仓量 PCR）、波动率（ATM IV/加权 IV，BS 反解）、
IV 斜率（认沽端/认购端回归斜率、Risk Reversal）、认沽认购 IV 差。
期指维度：行情趋势（均线/OI）、基差贴升水。
联动维度：期权信号 × 期指信号共振/背离，分品种评分。

提供:
  - OptionFuturesFetcher: 数据采集
  - OptionFuturesAnalyzer: 期权/期指/联动综合分析
"""

import os
import sys
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

try:
    from scipy.stats import norm
    from scipy.optimize import brentq
    _HAS_SCIPY = True
except Exception:
    # 无 scipy 时使用纯 Python 降级（近似正态 CDF + Newton-Raphson 反解），
    # 保证 IV 反解在沙箱/受限环境仍可用（精度略低但方向与量级正确）。
    norm = None
    _HAS_SCIPY = False


def _norm_cdf(x: float) -> float:
    """标准正态 CDF 近似（Abramowitz & Stegun 26.2.17，误差 < 1e-7）。"""
    x = float(x)
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804014327 * math.exp(-0.5 * x * x)
    p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return 1.0 - p if x > 0 else p


def _norm_pdf(x: float) -> float:
    """标准正态 PDF。"""
    return 0.3989422804014327 * math.exp(-0.5 * x * x)

# 金融数据网关初始化（走 kk_common，不直接 import tushare）
try:
    from kk_common import get_finance_data_gateway
    pro = get_finance_data_gateway()
except Exception:
    pro = None


# 品种映射：期指品种 → 期权标的（SSE ETF 期权 / CFFEX 股指期权）
SYMBOL_MAP = {
    'IF': {'name': '沪深300', 'opt_exchange': 'SSE', 'opt_code': 'OP510300.SH',
           'underlying': '510300.SH', 'underlying_type': 'etf', 'index': '000300.SH'},
    'IH': {'name': '上证50', 'opt_exchange': 'SSE', 'opt_code': 'OP510050.SH',
           'underlying': '510050.SH', 'underlying_type': 'etf', 'index': '000016.SH'},
    'IC': {'name': '中证500', 'opt_exchange': 'SSE', 'opt_code': 'OP510500.SH',
           'underlying': '510500.SH', 'underlying_type': 'etf', 'index': '000905.SH'},
    'IM': {'name': '中证1000', 'opt_exchange': 'CFFEX', 'opt_code': 'OP000852.SH',
           'underlying': '000852.SH', 'underlying_type': 'index', 'index': '000852.SH'},
}

# 无风险利率（近似值）
RISK_FREE_RATE = 0.02


def _fmt_date(d: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    if d and len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return str(d)


def _num(val):
    if val is None:
        return '0'
    v = float(val)
    if abs(v) >= 10000:
        return f"{v / 10000:.1f}万"
    return f"{v:,.0f}"


def _pct(val):
    if val is None:
        return '0.00%'
    return f"{float(val):+.2f}%"


# ======================================================================
#  Black-Scholes 期权定价与隐含波动率反解
# ======================================================================

def bs_price(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> float:
    """欧式期权 BS 定价（有 scipy 用 scipy.norm，否则用近似 CDF）"""
    if sigma <= 0 or T <= 0 or S <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    cdf = norm.cdf if _HAS_SCIPY else _norm_cdf
    if is_call:
        return S * cdf(d1) - K * math.exp(-r * T) * cdf(d2)
    return K * math.exp(-r * T) * cdf(-d2) - S * cdf(-d1)


def _is_call(cp) -> bool:
    """call_put 字段兼容 'C'/'P' 与中文 认购/认沽"""
    s = str(cp)
    return s.upper().startswith('C') or '认购' in s


def implied_vol(S: float, K: float, T: float, price: float, is_call: bool,
                r: float = RISK_FREE_RATE) -> Optional[float]:
    """反解隐含波动率；无解返回 None

    有 scipy 用 brentq；无 scipy 用 Newton-Raphson 迭代（vega 作导数），
    两者共用 bs_price（近似 CDF），保证沙箱环境 IV 反解可用。
    """
    if S <= 0 or K <= 0 or T <= 0 or price <= 0:
        return None
    # 内在价值检查：价格必须高于内在价值
    intrinsic = max(S - K, 0) if is_call else max(K - S, 0)
    if price <= intrinsic + 1e-9:
        return None
    if _HAS_SCIPY:
        try:
            return brentq(lambda s: bs_price(S, K, T, r, s, is_call) - price,
                          1e-4, 5.0, xtol=1e-6, maxiter=100)
        except Exception:
            return None
    # 无 scipy：Newton-Raphson 反解（初值取 Brenner-Subrahmanyam 近似）
    try:
        sigma = math.sqrt(2.0 * abs(math.log(S / K) + r * T) / T) if K > 0 else 0.2
        sigma = min(max(sigma, 0.05), 2.0)
        for _ in range(100):
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            p = bs_price(S, K, T, r, sigma, is_call)
            f = p - price
            if abs(f) < 1e-6:
                break
            vega = S * _norm_pdf(d1) * math.sqrt(T)
            if vega < 1e-10:
                return None
            new_sigma = sigma - f / vega
            if new_sigma <= 1e-4 or new_sigma > 5.0:
                return None
            sigma = new_sigma
        return sigma if 0 < sigma < 5.0 else None
    except Exception:
        return None


def _derive_iv_curve(ivs: List[dict], spot: float, opt: dict) -> None:
    """从 IV 明细列表推导 ATM/加权 IV、斜率、RR、IV 差、明细行（就地写入 opt）

    ivs 元素: {'ts_code', 'call_put', 'K', 'T', 'iv', 'vol', 'moneyness'}
    """
    if not ivs:
        return
    iv_df = pd.DataFrame(ivs)

    # ATM IV：剩余期限 60 天内 |moneyness-1| 最小的合约 IV
    near = iv_df[iv_df['T'] <= 60 / 365]
    if not near.empty:
        atm_idx = (near['moneyness'] - 1).abs().idxmin()
        opt['atm_iv'] = round(float(near.loc[atm_idx, 'iv']) * 100, 2)
    # 加权 IV（按成交量）
    total_vol = float(iv_df['vol'].sum())
    if total_vol > 0:
        opt['weighted_iv'] = round(float((iv_df['iv'] * iv_df['vol']).sum() / total_vol) * 100, 2)

    # IV 斜率（认沽端 / 认购端回归，OTM 端 IV ~ K 线性回归）
    near_otm = iv_df[iv_df['T'] <= 60 / 365]
    if not near_otm.empty:
        for side, is_call, filt in [('put', False, near_otm['moneyness'] < 1.0),
                                    ('call', True, near_otm['moneyness'] > 1.0)]:
            sub = near_otm[filt]
            if len(sub) >= 3:
                slope = np.polyfit(sub['K'].astype(float), sub['iv'].astype(float), 1)[0]
                opt[f'iv_slope_{side}'] = round(float(slope) * 1000, 3)  # 千分位斜率
        # Risk Reversal：近月 OTM 虚值端 IV 差（认沽 - 认购）
        put_otm = near_otm[(~near_otm['call_put'].apply(_is_call)) & (near_otm['moneyness'] < 1.0)]
        call_otm = near_otm[(near_otm['call_put'].apply(_is_call)) & (near_otm['moneyness'] > 1.0)]
        if not put_otm.empty and not call_otm.empty:
            put_iv = float(put_otm['iv'].mean())
            call_iv = float(call_otm['iv'].mean())
            opt['risk_reversal'] = round((put_iv - call_iv) * 100, 2)
            # 认沽认购 IV 差（ATM 附近 ±5%）
            atm_sub = near_otm[(near_otm['moneyness'] - 1).abs() < 0.05]
            if not atm_sub.empty:
                p_mask = ~atm_sub['call_put'].apply(_is_call)
                c_mask = atm_sub['call_put'].apply(_is_call)
                p_atm = float(atm_sub[p_mask]['iv'].mean()) if p_mask.any() else None
                c_atm = float(atm_sub[c_mask]['iv'].mean()) if c_mask.any() else None
                if p_atm is not None and c_atm is not None:
                    opt['put_call_iv_diff'] = round((p_atm - c_atm) * 100, 2)

    # 明细行（供表格）
    for _, r in iv_df.sort_values('vol', ascending=False).head(8).iterrows():
        opt['detail_rows'].append({
            'ts_code': r['ts_code'], 'call_put': r['call_put'],
            'K': float(r['K']), 'iv': round(float(r['iv']) * 100, 2),
            'vol': int(r['vol']),
        })


# ======================================================================
#  数据采集
# ======================================================================

class OptionFuturesFetcher:
    """期指期权数据采集器"""

    def __init__(self):
        self.pro = pro
        self._opt_basic_cache: Dict[str, pd.DataFrame] = {}

    def get_opt_basic(self, exchange: str) -> pd.DataFrame:
        """期权合约基础信息（按交易所缓存）"""
        if exchange in self._opt_basic_cache:
            return self._opt_basic_cache[exchange]
        if not self.pro:
            return pd.DataFrame()
        try:
            df = self.pro.opt_basic(exchange=exchange)
            if df is None or df.empty:
                df = pd.DataFrame()
        except Exception:
            df = pd.DataFrame()
        self._opt_basic_cache[exchange] = df
        return df

    def get_opt_daily(self, exchange: str, start_date: str, end_date: str) -> pd.DataFrame:
        """期权日行情（区间，全市场后本地过滤）"""
        if not self.pro:
            return pd.DataFrame()
        try:
            df = self.pro.opt_daily(exchange=exchange,
                                    start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_underlying_price(self, underlying: str, underlying_type: str,
                             trade_date: str) -> Optional[float]:
        """获取期权标的价格（ETF 用 fund_daily，股指期权用 index_daily）

        注：fund_daily/index_daily 均不支持 trade_date 单日参数，需用区间查询。
        """
        if not self.pro:
            return None
        try:
            if underlying_type == 'etf':
                df = self.pro.fund_daily(ts_code=underlying,
                                         start_date=trade_date, end_date=trade_date)
            else:
                df = self.pro.index_daily(ts_code=underlying,
                                          start_date=trade_date, end_date=trade_date)
            if df is not None and not df.empty:
                return float(df.iloc[0].get('close', 0))
        except Exception:
            pass
        return None

    def get_index_series(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """现货指数序列（基差计算）"""
        if not self.pro:
            return pd.DataFrame()
        try:
            df = self.pro.index_daily(ts_code=index_code,
                                      start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df.sort_values('trade_date').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()

    def get_dominant_contract(self, symbol: str) -> Optional[str]:
        """获取期指主力合约

        fut_mapping 同一交易日有多行映射（不同连续合约 ts_code 各自指向实际
        合约），取最新交易日中出现最多的 mapping_ts_code 作为主力（众数）。
        与 futures-analysis 技能口径一致。
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
        return None

    def get_futures_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """期指日行情"""
        if not self.pro:
            return pd.DataFrame()
        try:
            df = self.pro.fut_daily(ts_code=ts_code,
                                    start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                return df.sort_values('trade_date').reset_index(drop=True)
        except Exception:
            pass
        return pd.DataFrame()


# ======================================================================
#  综合分析
# ======================================================================

class OptionFuturesAnalyzer:
    """期指期权联动综合分析器"""

    def __init__(self, fetcher: OptionFuturesFetcher):
        self.fetcher = fetcher

    def analyze_all(self, symbols: List[str] = None, days: int = 30) -> Dict[str, Any]:
        """全量分析（日粒度）

        Returns:
            {'symbols': {sym: {...}}, 'composite': {...}}
        """
        if symbols is None:
            symbols = list(SYMBOL_MAP.keys())

        end = datetime.now()
        end_date = end.strftime('%Y%m%d')
        start_date = (end - timedelta(days=days * 2)).strftime('%Y%m%d')

        all_symbols = {}
        scores = {}
        details = {}
        for sym in symbols:
            sym_info = SYMBOL_MAP.get(sym, {})
            if not sym_info:
                continue
            sym_data = self._analyze_symbol(sym, sym_info, start_date, end_date)
            if sym_data:
                all_symbols[sym] = sym_data
                score, detail = self._score_symbol(sym_data)
                scores[sym] = score
                details[sym] = detail

        avg_score = sum(scores.values()) / len(scores) if scores else 50
        return {
            'symbols': all_symbols,
            'composite': {
                'avg_score': round(avg_score, 1),
                'market_env': '偏多' if avg_score >= 65 else '偏空' if avg_score <= 35 else '中性',
                'symbol_scores': scores,
                'details': details,
                'divergence_signal': self._divergence_signal(scores),
            },
        }

    # ------------------------------------------------------------------
    #  单品种分析
    # ------------------------------------------------------------------

    def _analyze_symbol(self, sym: str, sym_info: dict,
                        start_date: str, end_date: str) -> Dict[str, Any]:
        result = {}

        # 期权维度
        opt = self._analyze_option(sym_info, start_date, end_date)
        result['option'] = opt

        # 期指维度
        fut = self._analyze_futures(sym, sym_info, start_date, end_date)
        result['futures'] = fut

        # 联动分析
        result['linkage'] = self._analyze_linkage(sym, opt, fut)

        return result

    # ------------------------------------------------------------------
    #  期权维度分析
    # ------------------------------------------------------------------

    def _analyze_option(self, sym_info: dict, start_date: str, end_date: str) -> Dict[str, Any]:
        """期权维度：认沽认购 PCR、波动率（ATM/加权 IV）、IV 斜率、RR"""
        opt = {
            'error': None,
            'trade_date': None, 'underlying_price': None,
            'pcr_vol': None, 'pcr_oi': None,
            'atm_iv': None, 'weighted_iv': None,
            'iv_slope_put': None, 'iv_slope_call': None,
            'risk_reversal': None, 'put_call_iv_diff': None,
            'detail_rows': [],
        }
        exchange = sym_info.get('opt_exchange')
        opt_code = sym_info.get('opt_code')
        underlying = sym_info.get('underlying')
        underlying_type = sym_info.get('underlying_type')

        basic = self.fetcher.get_opt_basic(exchange)
        if basic.empty:
            opt['error'] = 'opt_basic 无数据'
            return opt
        contracts = basic[basic['opt_code'] == opt_code]
        if contracts.empty:
            opt['error'] = f'{opt_code} 无合约'
            return opt

        daily = self.fetcher.get_opt_daily(exchange, start_date, end_date)
        if daily.empty:
            opt['error'] = 'opt_daily 无数据'
            return opt

        # 过滤本品种合约并合并合约信息
        valid_codes = set(contracts['ts_code'])
        merged = daily[daily['ts_code'].isin(valid_codes)].merge(
            contracts[['ts_code', 'call_put', 'exercise_price', 's_month', 'maturity_date']],
            on='ts_code', how='left')
        if merged.empty:
            opt['error'] = '本品种无成交'
            return opt

        # 取最新交易日
        merged = merged.sort_values('trade_date')
        latest_date = str(merged['trade_date'].iloc[-1])
        today = merged[merged['trade_date'] == latest_date].copy()
        today['vol'] = pd.to_numeric(today.get('vol', 0), errors='coerce').fillna(0)
        today['oi'] = pd.to_numeric(today.get('oi', 0), errors='coerce').fillna(0)
        today['settle'] = pd.to_numeric(today.get('settle', 0), errors='coerce').fillna(0)
        today['close'] = pd.to_numeric(today.get('close', 0), errors='coerce').fillna(0)

        opt['trade_date'] = latest_date

        # 标的价格
        spot = self.fetcher.get_underlying_price(underlying, underlying_type, latest_date)
        if spot is None or spot <= 0:
            opt['error'] = '标的价格缺失'
            return opt
        opt['underlying_price'] = spot

        # ── 认沽认购 PCR ──
        calls = today[today['call_put'].apply(_is_call)]
        puts = today[~today['call_put'].apply(_is_call)]
        vol_call = float(calls['vol'].sum())
        vol_put = float(puts['vol'].sum())
        oi_call = float(calls['oi'].sum())
        oi_put = float(puts['oi'].sum())
        if vol_call > 0:
            opt['pcr_vol'] = round(vol_put / vol_call, 3)
        if oi_call > 0:
            opt['pcr_oi'] = round(oi_put / oi_call, 3)

        # ── 隐含波动率（BS 反解，活跃合约） ──
        active = today[(today['vol'] > 0) & (today['settle'] > 0)].copy()
        ivs = []
        for _, r in active.iterrows():
            is_call = _is_call(r['call_put'])
            K = float(r['exercise_price'])
            maturity = str(r.get('maturity_date', ''))
            if len(maturity) != 8:
                continue
            T = max((datetime.strptime(maturity, '%Y%m%d')
                     - datetime.strptime(latest_date, '%Y%m%d')).days, 1) / 365.0
            price = float(r['settle'])
            iv = implied_vol(spot, K, T, price, is_call)
            if iv is not None:
                ivs.append({'ts_code': r['ts_code'], 'call_put': r['call_put'],
                            'K': K, 'T': T, 'iv': iv, 'vol': float(r['vol']),
                            'moneyness': K / spot})
        if not ivs:
            opt['error'] = 'IV 反解失败'
            return opt

        # ATM IV / 加权 IV / 斜率 / RR / IV 差 / 明细（统一推导）
        _derive_iv_curve(ivs, spot, opt)

        return opt

    # ------------------------------------------------------------------
    #  期指维度分析
    # ------------------------------------------------------------------

    def _analyze_futures(self, sym: str, sym_info: dict,
                         start_date: str, end_date: str) -> Dict[str, Any]:
        fut = {'error': None, 'main_contract': None, 'trade_date': None,
               'close': None, 'pct_chg': None, 'trend': '-',
               'basis': None, 'basis_rate': None, 'basis_signal': '-',
               'oi': None, 'oi_chg': None}

        main_contract = self.fetcher.get_dominant_contract(sym)
        if not main_contract:
            fut['error'] = '主力合约获取失败'
            return fut
        fut['main_contract'] = main_contract

        bars = self.fetcher.get_futures_daily(main_contract, start_date, end_date)
        if bars is None or bars.empty:
            fut['error'] = '期指行情缺失'
            return fut
        bars = bars.sort_values('trade_date').reset_index(drop=True)
        latest = bars.iloc[-1]
        fut['trade_date'] = str(latest.get('trade_date', ''))
        fut['close'] = float(latest.get('close', 0))
        fut['pct_chg'] = float(latest.get('pct_chg', 0))
        fut['oi'] = int(float(latest.get('oi', 0) or 0))
        fut['oi_chg'] = int(float(latest.get('oi_chg', 0) or 0))

        closes = bars['close'].astype(float)
        close = float(latest['close'])
        ma5 = float(closes.tail(5).mean()) if len(closes) >= 5 else close
        ma10 = float(closes.tail(10).mean()) if len(closes) >= 10 else close
        ma20 = float(closes.tail(20).mean()) if len(closes) >= 20 else close
        if close > ma5 > ma10 > ma20:
            fut['trend'] = '多头排列'
        elif close < ma5 < ma10 < ma20:
            fut['trend'] = '空头排列'
        elif close > ma5:
            fut['trend'] = '偏多震荡'
        else:
            fut['trend'] = '偏空震荡'

        # 基差：期指 - 现货指数
        index_code = sym_info.get('index', '')
        index_df = self.fetcher.get_index_series(index_code, start_date, end_date)
        if index_df is not None and not index_df.empty:
            spot = float(index_df.iloc[-1].get('close', 0))
            if spot > 0:
                basis = close - spot
                fut['basis'] = round(basis, 2)
                fut['basis_rate'] = round(basis / spot * 100, 2)
                if fut['basis_rate'] > 0.5:
                    fut['basis_signal'] = '升水（偏多预期）'
                elif fut['basis_rate'] < -0.5:
                    fut['basis_signal'] = '贴水（偏空预期）'
                else:
                    fut['basis_signal'] = '正常'

        return fut

    # ------------------------------------------------------------------
    #  联动分析
    # ------------------------------------------------------------------

    def _analyze_linkage(self, sym: str, opt: Dict, fut: Dict) -> Dict[str, Any]:
        """期权 × 期指 联动信号分析"""
        link = {'signals': [], 'score': 0, 'direction': '中性', 'summary': []}

        def add(name, opt_sig, fut_sig, conclusion, score):
            link['signals'].append({
                'name': name, 'option_signal': opt_sig,
                'futures_signal': fut_sig, 'conclusion': conclusion, 'score': score,
            })
            link['score'] += score

        if opt.get('error'):
            add('数据完整性', '期权数据缺失', '-', '无法联动', 0)
            return link

        # 1) 认沽认购 PCR × 期指趋势
        pcr = opt.get('pcr_vol')
        pcr_sig = '中性'
        if pcr is not None:
            pcr_sig = '偏空保护' if pcr > 1.2 else '偏多情绪' if pcr < 0.8 else '中性'
        trend = fut.get('trend', '-')
        trend_sig = '空头' if '空头' in trend else '多头' if '多头' in trend else '震荡'
        if ('偏空' in pcr_sig or '保护' in pcr_sig) and '空头' in trend:
            add('认沽认购比×趋势', pcr_sig, trend_sig, '共振偏空', -2)
        elif ('偏多' in pcr_sig) and '多头' in trend:
            add('认沽认购比×趋势', pcr_sig, trend_sig, '共振偏多', 2)
        elif ('偏空' in pcr_sig or '保护' in pcr_sig) and '多头' in trend:
            add('认沽认购比×趋势', pcr_sig, trend_sig, '背离（期权偏空/期指偏多）', 0)
        else:
            add('认沽认购比×趋势', pcr_sig, trend_sig, '中性', 0)

        # 2) IV 水平 × 期指涨跌
        wiv = opt.get('weighted_iv')
        iv_sig = '高波动'
        if wiv is not None:
            iv_sig = '高波动' if wiv > 30 else '低波动' if wiv < 18 else '正常'
        pct = fut.get('pct_chg') or 0
        if iv_sig == '高波动' and pct < -1:
            add('波动率×涨跌', iv_sig, f'下跌{pct:.1f}%', '恐慌加剧（IV高+下跌）', -1)
        elif iv_sig == '高波动' and pct > 1:
            add('波动率×涨跌', iv_sig, f'上涨{pct:.1f}%', '高波动上行（分歧大）', 0)
        elif iv_sig == '低波动' and '多头' in trend:
            add('波动率×涨跌', iv_sig, trend_sig, '低波动上行（情绪平稳偏多）', 1)
        else:
            add('波动率×涨跌', iv_sig, f'{pct:+.1f}%', '中性', 0)

        # 3) IV 斜率（RR）× 基差
        rr = opt.get('risk_reversal')
        rr_sig = '中性'
        if rr is not None:
            rr_sig = '认沽端偏贵（偏空）' if rr > 0.5 else '认购端偏贵（偏多）' if rr < -0.5 else '中性'
        basis_sig = fut.get('basis_signal', '-')
        if ('认沽' in rr_sig and '偏空' in rr_sig) and '贴水' in basis_sig:
            add('IV斜率×基差', rr_sig, basis_sig, '双偏空共振（认沽贵+贴水）', -2)
        elif ('认购' in rr_sig and '偏多' in rr_sig) and '升水' in basis_sig:
            add('IV斜率×基差', rr_sig, basis_sig, '双偏多共振（认购贵+升水）', 2)
        elif ('认沽' in rr_sig) and '升水' in basis_sig:
            add('IV斜率×基差', rr_sig, basis_sig, '背离（期权偏空/基差偏多）', 0)
        else:
            add('IV斜率×基差', rr_sig, basis_sig, '中性', 0)

        # 4) 认沽认购 IV 差 × 持仓变化
        pcd = opt.get('put_call_iv_diff')
        oi_chg = fut.get('oi_chg') or 0
        pcd_sig = '中性'
        if pcd is not None:
            pcd_sig = '认沽IV高（偏空）' if pcd > 1.5 else '认购IV高（偏多）' if pcd < -1.5 else '中性'
        oi_sig = '增仓' if oi_chg > 0 else '减仓' if oi_chg < 0 else '持平'
        if '认沽IV高' in pcd_sig and oi_chg > 0:
            add('认沽认购IV差×持仓', pcd_sig, f'增仓{oi_chg:+,}', '增仓+认沽IV高（空头力量增强）', -1)
        elif '认购IV高' in pcd_sig and oi_chg > 0:
            add('认沽认购IV差×持仓', pcd_sig, f'增仓{oi_chg:+,}', '增仓+认购IV高（多头力量增强）', 1)
        else:
            add('认沽认购IV差×持仓', pcd_sig, oi_sig, '中性', 0)

        # 5) 持仓 PCR（机构保护头寸） × 基差
        pcr_oi = opt.get('pcr_oi')
        pcr_oi_sig = '中性'
        if pcr_oi is not None:
            pcr_oi_sig = '保护性认沽多（偏空）' if pcr_oi > 1.0 else '认购持仓多（偏多）' if pcr_oi < 0.7 else '中性'
        if ('偏空' in pcr_oi_sig) and '贴水' in basis_sig:
            add('持仓PCR×基差', pcr_oi_sig, basis_sig, '共振偏空', -1)
        elif ('偏多' in pcr_oi_sig) and '升水' in basis_sig:
            add('持仓PCR×基差', pcr_oi_sig, basis_sig, '共振偏多', 1)
        else:
            add('持仓PCR×基差', pcr_oi_sig, basis_sig, '中性', 0)

        # 汇总
        score = link['score']
        if score <= -3:
            link['direction'] = '偏空'
        elif score >= 3:
            link['direction'] = '偏多'
        elif score <= -1:
            link['direction'] = '略偏空'
        elif score >= 1:
            link['direction'] = '略偏多'
        else:
            link['direction'] = '中性'

        for s in link['signals']:
            if s['score'] != 0:
                link['summary'].append(f"{s['name']}: {s['conclusion']}")
        if not link['summary']:
            link['summary'].append('各维度信号平淡，无明显共振')

        return link

    # ------------------------------------------------------------------
    #  评分
    # ------------------------------------------------------------------

    def _score_symbol(self, sym_data: dict) -> tuple:
        """联动评分 0-100：50 基准，期权/期指/联动加权"""
        score = 50
        detail = {'direction': '-', 'pcr_vol': None, 'atm_iv': None,
                  'rr': None, 'trend': '-', 'basis_signal': '-', 'linkage': '-'}

        opt = sym_data.get('option', {})
        fut = sym_data.get('futures', {})
        link = sym_data.get('linkage', {})

        detail['pcr_vol'] = opt.get('pcr_vol')
        detail['atm_iv'] = opt.get('atm_iv')
        detail['rr'] = opt.get('risk_reversal')
        detail['trend'] = fut.get('trend', '-')
        detail['basis_signal'] = fut.get('basis_signal', '-')
        detail['direction'] = link.get('direction', '-')
        detail['linkage'] = link.get('score', 0)

        # 期权侧 ±20
        pcr = opt.get('pcr_vol')
        if pcr is not None:
            score += 8 if pcr < 0.8 else -8 if pcr > 1.2 else 0
        rr = opt.get('risk_reversal')
        if rr is not None:
            score += 6 if rr < -0.5 else -6 if rr > 0.5 else 0
        wiv = opt.get('weighted_iv')
        if wiv is not None and wiv > 30:
            score -= 6
        # 期指侧 ±20
        trend = fut.get('trend', '-')
        if '多头' in trend:
            score += 10
        elif '空头' in trend:
            score -= 10
        basis = fut.get('basis_signal', '-')
        if '升水' in basis:
            score += 5
        elif '贴水' in basis:
            score -= 5
        # 联动 ±10
        score += link.get('score', 0) * 2.5

        score = max(0, min(100, int(round(score))))
        return score, detail

    def _divergence_signal(self, scores: dict) -> str:
        if not scores:
            return '-'
        diff = max(scores.values()) - min(scores.values())
        if diff > 25:
            return f'品种分化明显（差值{diff}）'
        elif diff > 10:
            return f'品种略有分化（差值{diff}）'
        return f'品种走势一致（差值{diff}）'

    # ------------------------------------------------------------------
    #  周粒度分析
    # ------------------------------------------------------------------

    def analyze_weekly(self, symbols: List[str] = None, weeks: int = 1) -> Dict[str, Any]:
        """周粒度分析：按自然周聚合期权/期指指标后做联动分析

        Returns:
            {'symbols': {sym: {...}}, 'composite': {...}}
        """
        if symbols is None:
            symbols = list(SYMBOL_MAP.keys())

        end = datetime.now()
        end_date = end.strftime('%Y%m%d')
        start_date = (end - timedelta(days=weeks * 14 + 7)).strftime('%Y%m%d')

        all_symbols = {}
        scores = {}
        details = {}
        for sym in symbols:
            sym_info = SYMBOL_MAP.get(sym, {})
            if not sym_info:
                continue
            sym_data = self._analyze_symbol_weekly(sym, sym_info, start_date, end_date)
            if sym_data:
                all_symbols[sym] = sym_data
                score, detail = self._score_symbol(sym_data)
                scores[sym] = score
                details[sym] = detail

        avg_score = sum(scores.values()) / len(scores) if scores else 50
        return {
            'symbols': all_symbols,
            'composite': {
                'avg_score': round(avg_score, 1),
                'market_env': '偏多' if avg_score >= 65 else '偏空' if avg_score <= 35 else '中性',
                'symbol_scores': scores,
                'details': details,
                'divergence_signal': self._divergence_signal(scores),
            },
        }

    def _analyze_symbol_weekly(self, sym: str, sym_info: dict,
                               start_date: str, end_date: str) -> Dict[str, Any]:
        """单品种周粒度：逐日计算期权指标后按自然周聚合，期指用周涨跌/周基差"""
        result = {'week_label': '-', 'option': {}, 'futures': {}, 'linkage': {}}

        exchange = sym_info.get('opt_exchange')
        opt_code = sym_info.get('opt_code')
        underlying = sym_info.get('underlying')
        underlying_type = sym_info.get('underlying_type')

        basic = self.fetcher.get_opt_basic(exchange)
        daily = self.fetcher.get_opt_daily(exchange, start_date, end_date)
        if basic.empty or daily.empty:
            result['option'] = {'error': '期权数据缺失'}
            result['linkage'] = self._analyze_linkage(sym, result['option'], result['futures'])
            return result
        valid_codes = set(basic[basic['opt_code'] == opt_code]['ts_code'])
        merged = daily[daily['ts_code'].isin(valid_codes)].merge(
            basic[['ts_code', 'call_put', 'exercise_price', 'maturity_date']],
            on='ts_code', how='left')
        if merged.empty:
            result['option'] = {'error': '本品种无成交'}
            result['linkage'] = self._analyze_linkage(sym, result['option'], result['futures'])
            return result

        # ── 逐交易日计算期权指标 ──
        day_rows = []
        last_day = None
        for d, day in merged.groupby('trade_date'):
            d = str(d)
            day = day.copy()
            for col in ('vol', 'oi', 'settle'):
                if col in day.columns:
                    day[col] = pd.to_numeric(day[col], errors='coerce').fillna(0)
                else:
                    day[col] = 0
            spot = self.fetcher.get_underlying_price(underlying, underlying_type, d)
            if spot is None or spot <= 0:
                continue
            calls = day[day['call_put'].apply(_is_call)]
            puts = day[~day['call_put'].apply(_is_call)]
            vc = float(calls['vol'].sum())
            vp = float(puts['vol'].sum())
            oc = float(calls['oi'].sum())
            op = float(puts['oi'].sum())
            pcr_vol = round(vp / vc, 3) if vc > 0 else None
            pcr_oi = round(op / oc, 3) if oc > 0 else None

            # 当日活跃合约 BS 反解 IV
            active = day[(day['vol'] > 0) & (day['settle'] > 0)]
            ivs = []
            for _, r in active.iterrows():
                maturity = str(r.get('maturity_date', ''))
                if len(maturity) != 8:
                    continue
                T = max((datetime.strptime(maturity, '%Y%m%d')
                         - datetime.strptime(d, '%Y%m%d')).days, 1) / 365.0
                iv = implied_vol(spot, float(r['exercise_price']), T,
                                 float(r['settle']), _is_call(r['call_put']))
                if iv is not None:
                    ivs.append({'ts_code': r['ts_code'], 'call_put': r['call_put'],
                                'K': float(r['exercise_price']), 'T': T, 'iv': iv,
                                'vol': float(r['vol']),
                                'moneyness': float(r['exercise_price']) / spot})
            day_opt = {'detail_rows': []}
            _derive_iv_curve(ivs, spot, day_opt)
            day_rows.append({'trade_date': d, 'pcr_vol': pcr_vol, 'pcr_oi': pcr_oi,
                             'atm_iv': day_opt.get('atm_iv'),
                             'weighted_iv': day_opt.get('weighted_iv'),
                             'ivs': ivs, 'spot': spot})
            last_day = {'date': d, 'ivs': ivs, 'spot': spot}

        if not day_rows:
            result['option'] = {'error': '区间内无期权成交'}
            result['linkage'] = self._analyze_linkage(sym, result['option'], result['futures'])
            return result

        # ── 按 ISO 自然周分组，取最近一周 ──
        for row in day_rows:
            dd = datetime.strptime(row['trade_date'], '%Y%m%d')
            iso = dd.isocalendar()
            row['week'] = f"{iso[0]}-W{iso[1]:02d}"
        week_groups = {}
        for row in day_rows:
            week_groups.setdefault(row['week'], []).append(row)
        week_label = sorted(week_groups.keys())[-1]
        rows_this_week = week_groups[week_label]
        result['week_label'] = week_label

        # ── 周均期权指标 ──
        opt_w = {'error': None, 'week_label': week_label,
                 'pcr_vol': None, 'pcr_oi': None, 'atm_iv': None, 'weighted_iv': None,
                 'risk_reversal': None, 'put_call_iv_diff': None,
                 'iv_slope_put': None, 'iv_slope_call': None, 'detail_rows': []}
        for key in ('pcr_vol', 'pcr_oi'):
            vals = [r[key] for r in rows_this_week if r[key] is not None]
            if vals:
                opt_w[key] = round(sum(vals) / len(vals), 3)
        ivs_all = [iv for r in rows_this_week for iv in r['ivs']]
        if ivs_all:
            _derive_iv_curve(ivs_all, rows_this_week[-1]['spot'], opt_w)
        # 最新交易日斜率/RR/IV差/明细快照
        if last_day and last_day['ivs']:
            snap = {'detail_rows': []}
            _derive_iv_curve(last_day['ivs'], last_day['spot'], snap)
            for k in ('risk_reversal', 'put_call_iv_diff', 'iv_slope_put', 'iv_slope_call'):
                if snap.get(k) is not None:
                    opt_w[k] = snap[k]
            opt_w['detail_rows'] = snap['detail_rows']
            opt_w['snapshot_date'] = last_day['date']
        result['option'] = opt_w

        # ── 期指周指标 ──
        fut_w = {'error': None, 'main_contract': None, 'week_label': week_label,
                 'close': None, 'pct_chg': None, 'trend': '-',
                 'basis': None, 'basis_rate': None, 'basis_signal': '-',
                 'oi': None, 'oi_chg': None}
        main_contract = self.fetcher.get_dominant_contract(sym)
        fut_w['main_contract'] = main_contract
        week_first = rows_this_week[0]['trade_date']
        if main_contract:
            fut_bars = self.fetcher.get_futures_daily(main_contract, start_date, end_date)
            if fut_bars is not None and not fut_bars.empty:
                fb = fut_bars.copy()
                fb['trade_date'] = fb['trade_date'].astype(str)
                fb = fb.sort_values('trade_date').reset_index(drop=True)
                week_bars = fb[fb['trade_date'] >= week_first]
                if len(week_bars) >= 2:
                    first, last = week_bars.iloc[0], week_bars.iloc[-1]
                    first_close = float(first['close'])
                    last_close = float(last['close'])
                    fut_w['close'] = last_close
                    fut_w['pct_chg'] = round((last_close / first_close - 1) * 100, 2)
                    fut_w['oi'] = int(float(last.get('oi', 0) or 0))
                    fut_w['oi_chg'] = int(fut_w['oi'] - float(first.get('oi', 0) or 0))
                    chg = fut_w['pct_chg']
                    if chg > 1:
                        fut_w['trend'] = '多头（周涨）'
                    elif chg < -1:
                        fut_w['trend'] = '空头（周跌）'
                    else:
                        fut_w['trend'] = '震荡（周平）'
        # 周基差：周末期指收盘 - 周末现货指数收盘
        if fut_w.get('close'):
            index_df = self.fetcher.get_index_series(sym_info.get('index', ''), start_date, end_date)
            if index_df is not None and not index_df.empty:
                idx = index_df.copy()
                idx['trade_date'] = idx['trade_date'].astype(str)
                idx = idx.sort_values('trade_date').reset_index(drop=True)
                idx_week = idx[idx['trade_date'] >= week_first]
                if not idx_week.empty:
                    idx_last = float(idx_week.iloc[-1]['close'])
                    if idx_last > 0:
                        basis = fut_w['close'] - idx_last
                        fut_w['basis'] = round(basis, 2)
                        fut_w['basis_rate'] = round(basis / idx_last * 100, 2)
                        if fut_w['basis_rate'] > 0.5:
                            fut_w['basis_signal'] = '升水（偏多预期）'
                        elif fut_w['basis_rate'] < -0.5:
                            fut_w['basis_signal'] = '贴水（偏空预期）'
                        else:
                            fut_w['basis_signal'] = '正常'
        result['futures'] = fut_w

        # ── 联动分析（复用日粒度联动打分） ──
        result['linkage'] = self._analyze_linkage(sym, opt_w, fut_w)
        result['daily_series'] = rows_this_week
        return result
