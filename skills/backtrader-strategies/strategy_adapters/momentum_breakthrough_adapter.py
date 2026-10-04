#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动量突破策略适配器 - Tushare API 版本
基于价格动量和技术指标的选股逻辑

策略特点：
- 基于价格动量和技术突破信号
- 重点关注量价配合的突破股票
- 适合短中线趋势跟随
- 使用 pct_chg、turnover_rate 等可用指标替代 MongoDB 预计算技术因子
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


class MomentumBreakthroughAdapter:
    """动量突破策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "动量突破策略"
        self.strategy_type = "momentum"
        self.description = "基于价格动量和技术突破的选股策略"
        
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
            'volume_ratio_min': 1.5,     # 换手率最低阈值
            'min_price': 2.0,             # 最低股价
            'max_price': 500.0,           # 最高股价
            'pct_chg_weight': 0.30,       # 涨跌幅权重
            'volume_weight': 0.25,        # 换手率权重
            'trend_weight': 0.20,         # 趋势权重
            'breakthrough_weight': 0.15,  # 突破信号权重
            'strength_weight': 0.10,      # 相对强度权重
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
                # trade_cal 返回降序，按日期倒序尝试找到有 daily_basic 数据的最新日
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
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           trade_date: str = None,
                           **kwargs) -> Dict[str, Any]:
        """
        动量突破策略选股
        
        Args:
            market_cap: 市值范围 (large/mid/small/all)
            stock_pool: 股票池 (all/main/gem/star)
            limit: 返回股票数量
            trade_date: 指定交易日期
            **kwargs: 其他参数
            
        Returns:
            选股结果字典
        """
        try:
            self._update_params(kwargs)
            
            # 确定目标日期
            if trade_date:
                target_date = trade_date.replace('-', '')
            else:
                target_date = self._get_latest_trade_date()
            
            # Step 1: 获取 daily_basic 数据（带回退）
            daily_basic = self.pro.daily_basic(trade_date=target_date)
            if daily_basic is None or daily_basic.empty:
                for offset in range(1, 6):
                    fallback_date = (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=offset)).strftime('%Y%m%d')
                    daily_basic = self.pro.daily_basic(trade_date=fallback_date)
                    if daily_basic is not None and not daily_basic.empty:
                        target_date = fallback_date
                        break
                if daily_basic is None or daily_basic.empty:
                    return self._empty_result()
            
            # Step 2: 获取 daily 数据
            daily_price = self.pro.daily(trade_date=target_date)
            if daily_price is None or daily_price.empty:
                return self._empty_result()
            
            # 合并 daily_basic 和 daily
            merged = daily_basic.merge(
                daily_price[['ts_code', 'pct_chg', 'vol', 'amount', 'pre_close']],
                on='ts_code', how='left'
            )
            
            # 基础筛选
            mask = (
                (merged['close'] > self.params['min_price']) &
                (merged['close'] < self.params['max_price']) &
                (merged['total_mv'] > 0) &
                (merged['turnover_rate'].notna()) &
                (merged['turnover_rate'] > 0)
            )
            merged = merged[mask]
            
            # 市值筛选
            if market_cap == "large":
                merged = merged[merged['total_mv'] >= 5000000]
            elif market_cap == "mid":
                merged = merged[(merged['total_mv'] >= 1000000) & (merged['total_mv'] <= 5000000)]
            elif market_cap == "small":
                merged = merged[merged['total_mv'] <= 1000000]
            
            # 股票池筛选（基于后缀）
            if stock_pool != "all":
                pool_filter = self._get_pool_suffix_filter(stock_pool)
                if pool_filter:
                    merged = merged[merged['ts_code'].str.endswith(pool_filter)]
            
            if merged.empty:
                return self._empty_result()
            
            # Step 3: 关联股票基本信息
            stock_basic = self._get_stock_basic()
            # 去掉 stock_basic 中与 merged 冲突的列名
            stock_basic_cols = stock_basic.drop(columns=['name', 'industry'], errors='ignore')
            merged = merged.merge(stock_basic_cols, on='ts_code', how='left')
            
            # 过滤北交所（8开头和920开头）
            merged = merged[~merged['ts_code'].str.startswith(('8', '920'), na=False)]
            
            # 过滤ST
            if 'name' in merged.columns:
                merged = merged[~merged['name'].str.contains('ST', case=False, na=False)]
            
            # 重新关联 stock_basic 获取 name（避免列名冲突后丢失）
            merged = merged.drop(columns=['name', 'industry'], errors='ignore').merge(
                stock_basic[['ts_code', 'name', 'industry']], on='ts_code', how='left'
            )
            
            # Step 4: 计算动量评分（基于真实可用指标）
            merged['pct_chg'] = pd.to_numeric(merged['pct_chg'], errors='coerce').fillna(0)
            merged['turnover_rate'] = pd.to_numeric(merged['turnover_rate'], errors='coerce').fillna(0)
            
            # RPS 相对强度评分（基于 pct_chg）
            merged['rps_score'] = merged['pct_chg'].apply(
                lambda x: 80 + x * 2 if x > 5 else 60 + x * 4
            ).clip(lower=0, upper=100)
            
            # 突破信号判断（涨幅>2% + 换手率超过绝对阈值）
            merged['breakthrough_signal'] = (
                (merged['pct_chg'] > 2) &
                (merged['turnover_rate'] >= self.params['volume_ratio_min'])
            )
            
            # 价格趋势信号（涨幅 > 0，不再称作 MACD 金叉）
            merged['up_trend'] = merged['pct_chg'] > 0
            
            # 综合评分计算（各因子归一化到 0~100 后加权）
            pct_score = merged['pct_chg'].clip(lower=-10, upper=10) * 5 + 50  # -10~10 映射到 0~100
            turnover_score = merged['turnover_rate'].clip(upper=20) * 5  # 0~20 映射到 0~100
            uptrend_score = merged['up_trend'].astype(int) * 100  # 0 或 100
            breakthrough_score = merged['breakthrough_signal'].astype(int) * 100  # 0 或 100
            
            merged['score'] = (
                pct_score * self.params['pct_chg_weight'] +
                turnover_score * self.params['volume_weight'] +
                uptrend_score * self.params['trend_weight'] +
                breakthrough_score * self.params['breakthrough_weight'] +
                merged['rps_score'] * self.params['strength_weight']
            ).round(1)
            
            # Step 5: 计算期间收益率（对 top candidates）
            top_candidates = merged.nlargest(limit * 3, 'score')
            
            period_returns = {}
            for ts_code in top_candidates['ts_code'].tolist():
                period_returns[ts_code] = self._calculate_period_return(ts_code, 60)
            
            top_candidates['period_return'] = top_candidates['ts_code'].map(period_returns)
            top_candidates['momentum_20'] = top_candidates['period_return']
            
            # Step 6: 排序和限制
            top_candidates = top_candidates.nlargest(limit, 'score')
            
            # Step 7: 处理结果
            processed_results = self._process_results(top_candidates)
            
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
                    **self.params
                }
            }
            
        except Exception as e:
            print(f"❌ 动量突破策略选股失败: {e}")
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
    
    def _calculate_period_return(self, ts_code: str, days: int = 60) -> float:
        """计算指定天数的收益率"""
        try:
            end_date = self._get_latest_trade_date()
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            start_dt = end_dt - timedelta(days=days + 10)  # 多取10天缓冲
            
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_dt.strftime('%Y%m%d'),
                end_date=end_date
            )
            
            if df is None or df.empty or len(df) < 2:
                return 0.0
            
            df = df.sort_values('trade_date')
            earliest_close = df.iloc[0]['close']
            latest_close = df.iloc[-1]['close']
            
            if earliest_close > 0:
                return round((latest_close - earliest_close) / earliest_close * 100, 2)
            
            return 0.0
            
        except Exception as e:
            return 0.0
    
    def _process_results(self, results_df: pd.DataFrame) -> List[Dict]:
        """处理查询结果（仅输出真实可用指标）"""
        processed = []
        
        for _, result in results_df.iterrows():
            pct_chg = result.get('pct_chg', 0) or 0
            turnover_rate = result.get('turnover_rate', 0) or 0
            score = result.get('score', 0) or 0
            breakthrough_signal = result.get('breakthrough_signal', False)
            up_trend = result.get('up_trend', False)
            
            stock_info = {
                'ts_code': result.get('ts_code'),
                'name': result.get('name', ''),
                'industry': result.get('industry', ''),
                
                # 基础指标
                'close': round(result.get('close') or 0, 2),
                'pe': round(result.get('pe') or 0, 2),
                'pb': round(result.get('pb') or 0, 2),
                'total_mv': round((result.get('total_mv') or 0) / 10000, 2),  # 亿元
                'pct_chg': round(pct_chg, 2),
                'turnover_rate': round(turnover_rate, 2),
                
                # 动量指标（真实计算）
                'period_return': round(result.get('period_return', 0) or 0, 2),
                'rps_score': round(result.get('rps_score', 0) or 0, 1),
                
                # 信号指标
                'breakthrough_signal': bool(breakthrough_signal),
                'up_trend': bool(up_trend),
                
                # 综合评分
                'score': round(score, 1),
                
                # 选股理由
                'reason': self._generate_reason({
                    'pct_chg': pct_chg,
                    'turnover_rate': turnover_rate,
                    'breakthrough_signal': breakthrough_signal,
                    'up_trend': up_trend,
                    'score': score,
                })
            }
            processed.append(stock_info)
        
        return processed
    
    def _generate_reason(self, result: Dict) -> str:
        """生成选股理由"""
        reasons = []
        
        pct_chg = result.get('pct_chg', 0)
        turnover_rate = result.get('turnover_rate', 0)
        breakthrough_signal = result.get('breakthrough_signal', False)
        up_trend = result.get('up_trend', False)
        score = result.get('score', 0)
        
        # 价格动量
        if pct_chg >= 5:
            reasons.append(f"强势上涨{pct_chg:.1f}%")
        elif pct_chg >= 2:
            reasons.append(f"温和上涨{pct_chg:.1f}%")
        elif pct_chg >= 0:
            reasons.append(f"微涨{pct_chg:.1f}%")
        elif pct_chg < 0:
            reasons.append(f"回调{pct_chg:.1f}%")
        
        # 换手率
        if turnover_rate >= 5:
            reasons.append(f"高换手{turnover_rate:.1f}%")
        elif turnover_rate >= 2:
            reasons.append(f"活跃换手{turnover_rate:.1f}%")
        
        # 技术信号
        if breakthrough_signal:
            reasons.append("突破信号")
        
        if up_trend:
            reasons.append("多头趋势")
        
        reasons.append(f"评分{score:.0f}")
        
        return "；".join(reasons)
    
    def _get_pool_suffix_filter(self, stock_pool: str) -> str:
        """根据股票池名返回后缀过滤条件"""
        pool_map = {
            'main': ('.SH', '.SZ'),  # 主板
            'gem': ('.SZ',),          # 创业板
            'star': ('.SH',),         # 科创板
        }
        return pool_map.get(stock_pool, '')
    
    async def _resolve_stock_pool(self, stock_pools: List[str]) -> List[str]:
        """解析股票池代码（保留兼容）"""
        return []
    
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
async def test_momentum_breakthrough_adapter():
    """测试动量突破策略适配器"""
    adapter = MomentumBreakthroughAdapter()
    result = await adapter.screen_stocks(
        market_cap="all", 
        stock_pool="all", 
        limit=10
    )
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   涨跌幅: {stock['pct_chg']}%, 评分: {stock['score']}, 理由: {stock['reason']}")


if __name__ == "__main__":
    asyncio.run(test_momentum_breakthrough_adapter())
