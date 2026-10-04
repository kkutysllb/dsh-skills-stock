#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超跌反弹策略适配器 - Tushare API 版本
多维度识别超跌反弹机会的选股策略
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


class OversoldReboundAdapter:
    """超跌反弹策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "超跌反弹策略"
        self.strategy_type = "rebound"
        self.description = "多维度识别超跌反弹机会的选股策略"
        
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
    
    def _fetch_stock_history(self, ts_code: str, latest_date: str, lookback_days: int = 90) -> pd.DataFrame:
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
                df['close'] = pd.to_numeric(df['close'], errors='coerce')
            return df
        except Exception:
            return pd.DataFrame()
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           rsi_max: float = 50.0,
                           rsi_min: float = 10.0,
                           volume_ratio_min: float = 1.0,
                           pe_max: float = 100.0,
                           pb_max: float = 20.0,
                           **kwargs) -> Dict[str, Any]:
        """超跌反弹策略选股"""
        try:
            latest_date = self._get_latest_trade_date()
            print(f"查询日期: {latest_date}")
            
            # Step 1: 获取 daily_basic 数据（带回退）
            daily_basic = self.pro.daily_basic(trade_date=latest_date)
            if daily_basic is None or daily_basic.empty:
                for offset in range(1, 6):
                    fallback_date = (datetime.strptime(latest_date, '%Y%m%d') - timedelta(days=offset)).strftime('%Y%m%d')
                    daily_basic = self.pro.daily_basic(trade_date=fallback_date)
                    if daily_basic is not None and not daily_basic.empty:
                        latest_date = fallback_date
                        break
                if daily_basic is None or daily_basic.empty:
                    return self._empty_result()
            
            # Step 2: 获取 daily 数据
            daily_price = self.pro.daily(trade_date=latest_date)
            if daily_price is None or daily_price.empty:
                return self._empty_result()
            
            # 合并
            merged = daily_basic.merge(
                daily_price[['ts_code', 'pct_chg', 'vol', 'amount', 'pre_close']],
                on='ts_code', how='left'
            )
            
            # 基础筛选
            mask = (
                (merged['close'] > 0) &
                (merged['total_mv'] >= 100000) &
                (merged['pe'] > 0) & (merged['pe'] <= pe_max) &
                (merged['pb'] > 0) & (merged['pb'] <= pb_max) &
                (merged['turnover_rate'].notna()) &
                (merged['turnover_rate'] >= 0.5) & (merged['turnover_rate'] <= 50)
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
                merged = merged[merged['total_mv'] >= 100000]
            
            # 股票池筛选（基于后缀）
            if stock_pool != "all":
                pool_filter = self._get_pool_suffix_filter(stock_pool)
                if pool_filter:
                    merged = merged[merged['ts_code'].str.endswith(pool_filter)]
            
            if merged.empty:
                return self._empty_result()
            
            # 关联股票基本信息（防列名冲突）
            stock_basic = self._get_stock_basic()
            stock_basic_cols = stock_basic.drop(columns=['name', 'industry'], errors='ignore')
            merged = merged.merge(stock_basic_cols, on='ts_code', how='left')
            
            # 过滤北交所（8开头和920开头）
            merged = merged[~merged['ts_code'].str.startswith(('8', '920'), na=False)]
            
            # 过滤ST
            if 'name' in merged.columns:
                merged = merged[~merged['name'].str.contains('ST', case=False, na=False)]
            
            # 重新关联 name（防冲突丢失）
            merged = merged.drop(columns=['name', 'industry'], errors='ignore').merge(
                stock_basic[['ts_code', 'name', 'industry']], on='ts_code', how='left'
            )
            
            # Step 3: 计算超跌反弹评分
            merged['pct_chg'] = pd.to_numeric(merged['pct_chg'], errors='coerce').fillna(0)
            merged['turnover_rate'] = pd.to_numeric(merged['turnover_rate'], errors='coerce').fillna(0)
            
            # 超跌程度：pct_chg 越低，超跌越深
            oversold_pct_chg = (-merged['pct_chg']).clip(lower=0)
            
            # 换手率相对活跃度（与中位数比较）
            median_turnover = merged['turnover_rate'].median()
            volume_proxy = merged['turnover_rate'] / max(median_turnover, 0.1)
            
            # 综合评分
            merged['score'] = (
                20 +  # 基础分
                oversold_pct_chg * 2 +  # 超跌程度得分
                (volume_proxy - 1).clip(lower=0) * 3 +  # 放量得分
                np.where(merged['pct_chg'] > 0, 10,  # 当日反弹
                    np.where(merged['pct_chg'] > -3, 5, 0))  # 微跌
            ).clip(upper=100).round(1)
            
            # 反弹信号
            merged['rebound_signal'] = merged['score'] >= 40
            
            # 预选 top candidates（取 limit*3 用于后续精细筛选）
            merged = merged.sort_values('score', ascending=False).head(limit * 3)
            
            # Step 4: 批量获取历史数据并计算真实技术指标
            processed_results = []
            for _, result in merged.iterrows():
                ts_code = result.get('ts_code')
                close = result.get('close', 0) or 0
                pct_chg = result.get('pct_chg', 0) or 0
                turnover_rate = result.get('turnover_rate', 0) or 0
                
                # 获取历史日线（90天覆盖约60个交易日）
                hist_df = self._fetch_stock_history(ts_code, latest_date, lookback_days=90)
                
                if hist_df is not None and not hist_df.empty and len(hist_df) >= 5:
                    closes = hist_df['close'].dropna()
                    # 真实 MA 计算（取最后N根K线）
                    ma_20 = round(closes.tail(20).mean(), 2) if len(closes) >= 20 else round(closes.mean(), 2)
                    ma_60 = round(closes.tail(60).mean(), 2) if len(closes) >= 60 else round(closes.mean(), 2)
                    # 真实 RSI 计算
                    rsi = self._compute_rsi(closes)
                else:
                    ma_20 = close
                    ma_60 = close
                    rsi = None  # 无法计算时返回 None，不造假
                
                # 用 RSI 参数过滤
                if rsi is not None:
                    if rsi < rsi_min or rsi > rsi_max:
                        continue
                
                # 用换手率参数过滤
                if turnover_rate < volume_ratio_min:
                    continue
                
                # 超跌幅度（当日涨跌幅即为超跌/反弹幅度）
                oversold_pct = round(pct_chg, 2)
                
                stock_info = {
                    'ts_code': ts_code,
                    'name': result.get('name', ''),
                    'industry': result.get('industry', ''),
                    'close': round(close, 2),
                    'pe': round(result.get('pe') or 0, 2),
                    'pb': round(result.get('pb') or 0, 2),
                    'total_mv': round((result.get('total_mv') or 0) / 10000, 2),  # 亿元
                    'pct_chg': round(pct_chg, 2),
                    'turnover_rate': round(turnover_rate, 2),
                    'rsi': round(rsi, 2) if rsi is not None else None,
                    'ma_20': ma_20,
                    'ma_60': ma_60,
                    'oversold_pct': oversold_pct,
                    'rebound_signal': bool(result.get('rebound_signal', False)),
                    'score': round(result.get('score', 0) or 0, 2),
                    'reason': self._generate_reason({
                        'rsi': rsi,
                        'pct_chg': pct_chg,
                        'turnover_rate': turnover_rate,
                        'score': result.get('score', 0)
                    })
                }
                processed_results.append(stock_info)
            
            # 截取 limit 条
            processed_results = processed_results[:limit]
            
            print(f"找到 {len(processed_results)} 只超跌股票")
            
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'total_count': len(processed_results),
                'stocks': processed_results,
                'timestamp': datetime.now().isoformat(),
                'parameters': {
                    'market_cap': market_cap,
                    'stock_pool': stock_pool,
                    'limit': limit,
                    'rsi_max': rsi_max,
                    'rsi_min': rsi_min,
                    'volume_ratio_min': volume_ratio_min,
                    'pe_max': pe_max,
                    'pb_max': pb_max
                }
            }
            
        except Exception as e:
            print(f"❌ 超跌反弹策略选股失败: {e}")
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
    
    def _compute_rsi(self, closes: pd.Series, period: int = 12) -> float:
        """计算 RSI"""
        try:
            closes = pd.to_numeric(closes, errors='coerce').dropna()
            if len(closes) < period:
                return 50.0
            delta = closes.diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.rolling(window=period, min_periods=period).mean()
            avg_loss = loss.rolling(window=period, min_periods=period).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-10)
            rsi = 100 - (100 / (1 + rs))
            return round(rsi.iloc[-1], 2) if not rsi.empty else 50.0
        except Exception:
            return 50.0
    
    def _generate_reason(self, result: Dict) -> str:
        """生成选股理由"""
        reasons = []
        
        rsi = result.get('rsi')
        pct_chg = result.get('pct_chg', 0)
        turnover_rate = result.get('turnover_rate', 0)
        score = result.get('score', 0)
        
        if rsi is not None:
            if rsi <= 30:
                reasons.append(f"RSI{rsi:.0f}超跌")
            elif rsi <= 45:
                reasons.append(f"RSI{rsi:.0f}偏低")
        
        if turnover_rate >= 5:
            reasons.append(f"高换手{turnover_rate:.1f}%")
        elif turnover_rate >= 3:
            reasons.append(f"活跃换手{turnover_rate:.1f}%")
        
        if pct_chg > 0:
            reasons.append(f"反弹{pct_chg:.1f}%")
        elif pct_chg > -3:
            reasons.append("跌幅有限")
        else:
            reasons.append(f"超跌{pct_chg:.1f}%")
        
        reasons.append(f"反弹评分{score:.0f}")
        
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
async def test_oversold_rebound_adapter():
    """测试超跌反弹策略适配器"""
    adapter = OversoldReboundAdapter()
    result = await adapter.screen_stocks(limit=10)
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   RSI: {stock['rsi']}, 超跌幅度: {stock['oversold_pct']}%, 评分: {stock['score']}")


if __name__ == "__main__":
    asyncio.run(test_oversold_rebound_adapter())
