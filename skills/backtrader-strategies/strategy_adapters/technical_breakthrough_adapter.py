#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术突破策略适配器 - Tushare API 版本
多重技术指标确认突破信号

策略特点：
- 多重技术指标确认突破信号
- 重点关注量价配合的技术突破
- 适合短中线技术操作
- 基于 pct_chg、turnover_rate 等可用指标
"""

import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
import pandas as pd
import numpy as np

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(os.path.dirname(current_dir))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Tushare API 数据获取
try:
    from kk_common import get_finance_data_gateway
    _TUSHARE_AVAILABLE = True
except ImportError:
    _TUSHARE_AVAILABLE = False


class TechnicalBreakthroughAdapter:
    """技术突破策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "技术突破策略"
        self.strategy_type = "technical"
        self.description = "多重技术指标确认的突破选股策略"
        
        # 初始化 Tushare API
        if not _TUSHARE_AVAILABLE:
            raise RuntimeError("tushare 未安装，请执行 pip install tushare")
        from dotenv import load_dotenv
        load_dotenv()
        token = os.environ.get('TUSHARE_TOKEN', '')
        if not token:
            raise ValueError('TUSHARE_TOKEN 环境变量未设置')
        self.pro = get_finance_data_gateway()
        self._stock_basic_cache = None
        
        # 策略参数
        self.params = {
            'rsi_min': 45.0,              # RSI 下限
            'rsi_max': 85.0,              # RSI 上限
            'turnover_rate_min': 1.0,     # 换手率下限(%)
            'turnover_rate_max': 15.0,    # 换手率上限(%)
            'min_market_cap': 500000,     # 最低市值(万元)
            'exclude_st': True,           # 排除ST
            'breakthrough_threshold': 70,  # 突破评分阈值
            # 评分权重
            'rsi_weight': 0.20,
            'macd_weight': 0.20,
            'volume_weight': 0.25,
            'trend_weight': 0.15,
            'breakthrough_weight': 0.20,
        }
    
    def _get_stock_basic(self) -> pd.DataFrame:
        """缓存获取股票基础信息"""
        if self._stock_basic_cache is None:
            self._stock_basic_cache = self.pro.stock_basic(
                exchange='', list_status='L',
                fields='ts_code,name,industry,list_date'
            )
        return self._stock_basic_cache
    
    def _get_latest_trade_date(self) -> str:
        """获取最新交易日期（带缓存和 daily_basic 回退验证）"""
        if hasattr(self, '_latest_trade_date_cache') and self._latest_trade_date_cache:
            return self._latest_trade_date_cache
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            df = self.pro.trade_cal(
                exchange='SSE', is_open=1,
                start_date=start_date, end_date=end_date
            )
            if df is not None and not df.empty:
                candidates = sorted(df['cal_date'].tolist(), reverse=True)
                for d in candidates:
                    try:
                        test = self.pro.daily_basic(trade_date=d)
                        if test is not None and not test.empty:
                            self._latest_trade_date_cache = d
                            return d
                    except Exception:
                        continue
        except Exception as e:
            print(f"获取最新交易日期失败: {e}")
        self._latest_trade_date_cache = datetime.now().strftime('%Y%m%d')
        return self._latest_trade_date_cache
    
    def _update_params(self, kwargs: Dict[str, Any]):
        """更新策略参数"""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
    
    def _get_pool_suffix_filter(self, stock_pool: str) -> str:
        """根据股票池名返回后缀过滤条件"""
        pool_map = {
            'main': ('.SH', '.SZ'),
            'gem': ('.SZ',),
            'star': ('.SH',),
        }
        return pool_map.get(stock_pool, '')
    
    async def _resolve_stock_pool(self, stock_pools: List[str]) -> List[str]:
        """解析股票池代码（保留兼容）"""
        return []
    
    def _fetch_stock_history(self, ts_code: str, latest_date: str, lookback_days: int = 120) -> pd.DataFrame:
        """获取单只股票历史日线数据"""
        try:
            start_dt = datetime.strptime(latest_date, '%Y%m%d') - timedelta(days=lookback_days)
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_dt.strftime('%Y%m%d'),
                end_date=latest_date
            )
            if df is not None and not df.empty:
                df = df.sort_values('trade_date')
                for col in ['close', 'vol']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
            return df if df is not None else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    
    # ─── 真实技术指标计算 ───────────────────────────────────
    
    def _compute_rsi(self, closes: pd.Series, period: int = 14) -> float:
        """计算 RSI"""
        try:
            closes = closes.dropna()
            if len(closes) < period:
                return None
            delta = closes.diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.rolling(window=period, min_periods=period).mean()
            avg_loss = loss.rolling(window=period, min_periods=period).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-10)
            rsi = 100 - (100 / (1 + rs))
            return round(rsi.iloc[-1], 2) if not rsi.empty else None
        except Exception:
            return None
    
    def _compute_macd(self, closes: pd.Series) -> dict:
        """计算 MACD(12,26,9)，返回 DIFF/DEA/MACD柱"""
        try:
            closes = closes.dropna()
            if len(closes) < 35:
                return {'diff': 0, 'dea': 0, 'macd': 0, 'golden_cross': False}
            ema12 = closes.ewm(span=12, adjust=False).mean()
            ema26 = closes.ewm(span=26, adjust=False).mean()
            diff = ema12 - ema26
            dea = diff.ewm(span=9, adjust=False).mean()
            macd_bar = 2 * (diff - dea)
            # 金叉判断：前一天 DIFF < DEA，今天 DIFF > DEA
            golden_cross = (diff.iloc[-2] < dea.iloc[-2]) and (diff.iloc[-1] > dea.iloc[-1])
            return {
                'diff': round(diff.iloc[-1], 4),
                'dea': round(dea.iloc[-1], 4),
                'macd': round(macd_bar.iloc[-1], 4),
                'golden_cross': golden_cross
            }
        except Exception:
            return {'diff': 0, 'dea': 0, 'macd': 0, 'golden_cross': False}
    
    def _compute_ema(self, closes: pd.Series, period: int) -> float:
        """计算 EMA"""
        try:
            closes = closes.dropna()
            if len(closes) < period:
                return round(closes.iloc[-1], 2)
            return round(closes.ewm(span=period, adjust=False).mean().iloc[-1], 2)
        except Exception:
            return 0.0
    
    def _compute_bollinger(self, closes: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
        """计算布林带"""
        try:
            closes = closes.dropna()
            if len(closes) < period:
                c = closes.iloc[-1]
                return {'upper': round(c * 1.05, 2), 'middle': round(c, 2), 'lower': round(c * 0.95, 2)}
            middle = closes.rolling(window=period).mean()
            std = closes.rolling(window=period).std()
            upper = middle + std_dev * std
            lower = middle - std_dev * std
            return {
                'upper': round(upper.iloc[-1], 2),
                'middle': round(middle.iloc[-1], 2),
                'lower': round(lower.iloc[-1], 2)
            }
        except Exception:
            c = closes.iloc[-1] if not closes.empty else 0
            return {'upper': round(c * 1.05, 2), 'middle': round(c, 2), 'lower': round(c * 0.95, 2)}
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           trade_date: str = None,
                           **kwargs) -> Dict[str, Any]:
        """技术突破策略选股"""
        try:
            self._update_params(kwargs)
            
            if trade_date:
                target_date = trade_date.replace('-', '')
            else:
                target_date = self._get_latest_trade_date()
            
            # Step 1: 获取 daily_basic（带回退）
            daily_basic = self.pro.daily_basic(trade_date=target_date)
            if daily_basic is None or daily_basic.empty:
                for offset in range(1, 6):
                    fb = (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=offset)).strftime('%Y%m%d')
                    daily_basic = self.pro.daily_basic(trade_date=fb)
                    if daily_basic is not None and not daily_basic.empty:
                        target_date = fb
                        break
                if daily_basic is None or daily_basic.empty:
                    return self._empty_result()
            
            # Step 2: 获取 daily
            daily_price = self.pro.daily(trade_date=target_date)
            if daily_price is None or daily_price.empty:
                return self._empty_result()
            
            merged = daily_basic.merge(
                daily_price[['ts_code', 'pct_chg', 'vol', 'amount', 'pre_close']],
                on='ts_code', how='left'
            )
            
            # 基础筛选
            mask = (
                (merged['close'] > 0) &
                (merged['total_mv'] >= self.params['min_market_cap']) &
                (merged['turnover_rate'].notna()) &
                (merged['turnover_rate'] >= self.params['turnover_rate_min']) &
                (merged['turnover_rate'] <= self.params['turnover_rate_max'])
            )
            merged = merged[mask]
            
            # 市值筛选
            if market_cap == "large":
                merged = merged[merged['total_mv'] >= 5000000]
            elif market_cap == "mid":
                merged = merged[(merged['total_mv'] >= 1000000) & (merged['total_mv'] <= 5000000)]
            elif market_cap == "small":
                merged = merged[merged['total_mv'] <= 1000000]
            else:
                merged = merged[merged['total_mv'] >= 500000]
            
            # 股票池筛选（基于后缀）
            if stock_pool != "all":
                pool_filter = self._get_pool_suffix_filter(stock_pool)
                if pool_filter:
                    merged = merged[merged['ts_code'].str.endswith(pool_filter)]
            
            if merged.empty:
                return self._empty_result()
            
            # Step 3: 关联股票基本信息（防列名冲突）
            stock_basic = self._get_stock_basic()
            stock_basic_cols = stock_basic.drop(columns=['name', 'industry'], errors='ignore')
            merged = merged.merge(stock_basic_cols, on='ts_code', how='left')
            
            # 过滤北交所
            merged = merged[~merged['ts_code'].str.startswith(('8', '920'), na=False)]
            
            # 过滤ST
            if self.params['exclude_st']:
                merged = merged.drop(columns=['name', 'industry'], errors='ignore').merge(
                    stock_basic[['ts_code', 'name', 'industry']], on='ts_code', how='left'
                )
                merged = merged[~merged['name'].str.contains('ST', case=False, na=False)]
            
            if merged.empty:
                return self._empty_result()
            
            # Step 4: 快速预评分选候选（用当日可见数据）
            merged['pct_chg'] = pd.to_numeric(merged['pct_chg'], errors='coerce').fillna(0)
            merged['turnover_rate'] = pd.to_numeric(merged['turnover_rate'], errors='coerce').fillna(0)
            # 简单预评分：涨幅 + 换手率
            merged['pre_score'] = (
                merged['pct_chg'].clip(lower=-5, upper=10) * 5 +
                merged['turnover_rate'].clip(upper=20) * 2
            )
            candidates = merged.nlargest(limit * 3, 'pre_score')
            
            # Step 5: 获取历史数据，计算真实技术指标并评分
            scored = []
            for _, row in candidates.iterrows():
                ts_code = row['ts_code']
                close = row['close']
                pct_chg = row['pct_chg']
                turnover_rate = row['turnover_rate']
                
                # 获取历史日线（120天覆盖约80个交易日，支持MACD 26周期）
                hist = self._fetch_stock_history(ts_code, target_date, lookback_days=120)
                if hist is None or hist.empty or len(hist) < 5:
                    continue
                
                closes = hist['close'].dropna()
                vols = hist['vol'].dropna() if 'vol' in hist.columns else pd.Series()
                
                # ── 真实技术指标 ──
                rsi = self._compute_rsi(closes, period=14)
                macd_info = self._compute_macd(closes)
                ema20 = self._compute_ema(closes, 20)
                ema50 = self._compute_ema(closes, 50)
                boll = self._compute_bollinger(closes, period=20)
                # 真实量比：今日成交量 / 近20日均量
                if len(vols) >= 20:
                    avg_vol_20 = vols.tail(21).head(20).mean()  # 不含今日
                    today_vol = row.get('vol', 0) or 0
                    volume_ratio = round(today_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0
                else:
                    volume_ratio = 1.0
                
                # ── RSI 参数过滤 ──
                if rsi is not None and (rsi < self.params['rsi_min'] or rsi > self.params['rsi_max']):
                    continue
                
                # ── 评分计算（各因子 0~100 归一化） ──
                rsi_score = max(0, (rsi - 30) * 1.43) if rsi else 50  # RSI 30~100 → 0~100
                macd_score = 50  # 基础分
                if macd_info['golden_cross']:
                    macd_score = 100  # MACD金叉满分
                elif macd_info['diff'] > macd_info['dea']:
                    macd_score = 70  # DIFF > DEA
                elif macd_info['diff'] > 0:
                    macd_score = 50
                else:
                    macd_score = 20
                
                vol_score = min(100, turnover_rate * 6.67)  # 0~15% → 0~100
                
                # 趋势得分：收盘价相对 EMA20/EMA50 位置
                trend_score = 50
                if ema20 > 0 and ema50 > 0:
                    if close > ema20:
                        trend_score += 30
                    if close > ema50:
                        trend_score += 20
                
                # 突破得分：布林带位置 + 量比
                boll_score = 50
                if boll['upper'] > boll['middle']:
                    boll_pos = (close - boll['lower']) / (boll['upper'] - boll['lower']) if boll['upper'] > boll['lower'] else 0.5
                    boll_score = min(100, max(0, boll_pos * 100))
                breakthrough_bonus = min(30, max(0, (volume_ratio - 1) * 15))  # 放量加分
                breakthrough_score = min(100, boll_score + breakthrough_bonus)
                
                score = (
                    rsi_score * self.params['rsi_weight'] +
                    macd_score * self.params['macd_weight'] +
                    vol_score * self.params['volume_weight'] +
                    trend_score * self.params['trend_weight'] +
                    breakthrough_score * self.params['breakthrough_weight']
                )
                
                is_breakthrough = score >= self.params['breakthrough_threshold']
                
                scored.append({
                    'ts_code': ts_code,
                    'name': row.get('name', ''),
                    'industry': row.get('industry', ''),
                    'close': round(close, 2),
                    'pe': round(row.get('pe') or 0, 2),
                    'pb': round(row.get('pb') or 0, 2),
                    'total_mv': round((row.get('total_mv') or 0) / 10000, 2),
                    'pct_chg': round(pct_chg, 2),
                    'turnover_rate': round(turnover_rate, 2),
                    'rsi': rsi,
                    'macd_diff': macd_info['diff'],
                    'macd_dea': macd_info['dea'],
                    'macd_bar': macd_info['macd'],
                    'macd_golden': macd_info['golden_cross'],
                    'ema_20': ema20,
                    'ema_50': ema50,
                    'boll_upper': boll['upper'],
                    'boll_middle': boll['middle'],
                    'boll_lower': boll['lower'],
                    'volume_ratio': volume_ratio,
                    'breakthrough_signal': is_breakthrough,
                    'score': round(score, 1),
                })
            
            # Step 6: 排序和截取
            scored.sort(key=lambda x: x['score'], reverse=True)
            top_stocks = scored[:limit]
            
            # Step 7: 生成理由
            for s in top_stocks:
                s['reason'] = self._generate_reason(s)
            
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'total_count': len(top_stocks),
                'stocks': top_stocks,
                'timestamp': datetime.now().isoformat(),
                'parameters': {
                    'market_cap': market_cap,
                    'stock_pool': stock_pool,
                    'limit': limit,
                    **self.params
                }
            }
            
        except Exception as e:
            print(f"❌ 技术突破策略选股失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'error': str(e),
                'total_count': 0,
                'stocks': [],
                'timestamp': datetime.now().isoformat()
            }
    
    def _generate_reason(self, result: Dict) -> str:
        """生成选股理由（基于真实技术指标）"""
        reasons = []
        
        pct_chg = result.get('pct_chg', 0)
        rsi = result.get('rsi')
        macd_golden = result.get('macd_golden', False)
        volume_ratio = result.get('volume_ratio', 1)
        close = result.get('close', 0)
        ema20 = result.get('ema_20', 0)
        boll_upper = result.get('boll_upper', 0)
        score = result.get('score', 0)
        
        # 均线位置
        if ema20 and close > ema20:
            reasons.append("站上20日EMA")
        
        # 涨幅
        if pct_chg >= 5:
            reasons.append(f"强势上涨{pct_chg:.1f}%")
        elif pct_chg >= 2:
            reasons.append(f"温和上涨{pct_chg:.1f}%")
        elif pct_chg > 0:
            reasons.append(f"微涨{pct_chg:.1f}%")
        
        # RSI
        if rsi is not None:
            if rsi >= 70:
                reasons.append(f"RSI{rsi:.0f}强势")
            elif rsi >= 50:
                reasons.append(f"RSI{rsi:.0f}适中")
        
        # 放量
        if volume_ratio >= 2:
            reasons.append(f"放量{volume_ratio:.1f}倍")
        elif volume_ratio >= 1.5:
            reasons.append(f"温和放量{volume_ratio:.1f}倍")
        
        # MACD
        if macd_golden:
            reasons.append("MACD金叉")
        
        # 布林带突破
        if boll_upper and close >= boll_upper:
            reasons.append("突破布林上轨")
        
        reasons.append(f"评分{score:.0f}")
        
        return "；".join(reasons)
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'total_count': 0,
            'stocks': [],
            'timestamp': datetime.now().isoformat(),
            'parameters': {}
        }


# 测试函数
async def test_technical_breakthrough_adapter():
    """测试技术突破策略适配器"""
    adapter = TechnicalBreakthroughAdapter()
    result = await adapter.screen_stocks(
        market_cap="all", 
        stock_pool="all", 
        limit=10
    )
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   涨跌幅: {stock['pct_chg']}%, RSI: {stock['rsi']}, 评分: {stock['score']}")


if __name__ == "__main__":
    asyncio.run(test_technical_breakthrough_adapter())
