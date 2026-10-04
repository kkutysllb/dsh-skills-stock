#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金追踪策略适配器 - Tushare API 版本
基于融资融券数据的资金流向分析

策略特点：
- 追踪融资买入趋势
- 关注融资余额增长
- 基于融资融券数据的量化分析
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


class FundFlowTrackingAdapter:
    """资金追踪策略适配器 - 基于 Tushare API 融资融券数据"""
    
    def __init__(self):
        self.strategy_name = "资金追踪策略"
        self.strategy_type = "fund_flow"
        self.description = "基于融资融券数据追踪主力资金流向"
        
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
        
        # 策略参数（百分比，默认 5% 增长率）
        self.params = {
            'margin_buy_trend_min': 5.0,
            'margin_balance_growth_min': 5.0,
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
        """获取最新交易日（带缓存）"""
        if hasattr(self, '_latest_trade_date_cache'):
            return self._latest_trade_date_cache
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            df = self.pro.trade_cal(
                exchange='SSE', is_open=1,
                start_date=start_date, end_date=end_date
            )
            if df is not None and not df.empty:
                # trade_cal 返回可能倒序，取最大值确保拿到最新日期
                self._latest_trade_date_cache = df['cal_date'].max()
                return self._latest_trade_date_cache
        except Exception:
            pass
        self._latest_trade_date_cache = datetime.now().strftime('%Y%m%d')
        return self._latest_trade_date_cache
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           margin_buy_trend_min: float = 5.0,
                           margin_balance_growth_min: float = 5.0,
                           **kwargs) -> Dict[str, Any]:
        """
        资金追踪策略选股
        
        Args:
            market_cap: 市值范围
            stock_pool: 股票池
            limit: 返回股票数量
            margin_buy_trend_min: 融资买入趋势最小值
            margin_balance_growth_min: 融资余额增长最小值
            
        Returns:
            选股结果字典
        """
        try:
            print(f"🔥 资金追踪策略适配器开始执行")
            print(f"参数: market_cap={market_cap}, stock_pool={stock_pool}, limit={limit}")
            
            results = await self._optimized_fund_flow_screening(
                market_cap, stock_pool, limit,
                margin_buy_trend_min, margin_balance_growth_min
            )
            
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'total_count': len(results),
                'stocks': results,
                'timestamp': datetime.now().isoformat(),
                'parameters': {
                    'market_cap': market_cap,
                    'stock_pool': stock_pool,
                    'limit': limit,
                    'margin_buy_trend_min': margin_buy_trend_min,
                    'margin_balance_growth_min': margin_balance_growth_min
                }
            }
            
        except Exception as e:
            print(f"❌ 资金追踪策略选股失败: {e}")
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
    
    async def _optimized_fund_flow_screening(self, market_cap: str, stock_pool: str,
                                           limit: int, margin_buy_trend_min: float,
                                           margin_balance_growth_min: float) -> List[Dict[str, Any]]:
        """优化的资金追踪筛选"""
        try:
            # Step 1: 分批获取个股融资融券数据
            # margin_detail 单次最多返回6000行，全市场4300+只股票只够一天
            # 所以按日分页调用，汇总后做趋势分析
            print("🔍 开始获取融资融券数据...")
    
            end_date = self._get_latest_trade_date()
            end_dt = datetime.strptime(end_date, '%Y%m%d')
    
            # 获取最近 90 天的交易日列表
            print("  📅 获取交易日历...")
            trade_cal_df = self.pro.trade_cal(
                exchange='SSE', is_open=1,
                start_date=(end_dt - timedelta(days=90)).strftime('%Y%m%d'),
                end_date=end_date
            )
            all_trade_dates = sorted(trade_cal_df['cal_date'].tolist())
            print(f"  交易日数: {len(all_trade_dates)}")
    
            # 选取关键日期：从最近日期往回等距采样，确保包含最新交易日
            sample_size = min(12, len(all_trade_dates))
            step = max(1, len(all_trade_dates) // sample_size)
            # 先取最近的 sample_size*step 个交易日
            recent_window = all_trade_dates[-(sample_size * step):]
            # 从末尾反向等距采样，再反转回正序（保证末尾日期一定在采样中）
            selected_dates = recent_window[::-step][:sample_size][::-1]
            print(f"  采样日期: {len(selected_dates)} 个 ({selected_dates[0]} ~ {selected_dates[-1]})")
    
            # 按日分页获取
            margin_frames = []
            for d in selected_dates:
                df = self.pro.margin_detail(start_date=d, end_date=d)
                if df is not None and not df.empty:
                    margin_frames.append(df)
    
            if not margin_frames:
                print("无融资融券数据")
                return []
    
            margin_df = pd.concat(margin_frames, ignore_index=True)
            print(f"  总数据: {len(margin_df)} 条，覆盖 {margin_df['ts_code'].nunique()} 只股票")
            
            # 转换字段为数值
            for col in ['rzmre', 'rzye']:
                if col in margin_df.columns:
                    margin_df[col] = pd.to_numeric(margin_df[col], errors='coerce').fillna(0)
            
            # Step 2: 计算每只股票的融资趋势（最近采样点 vs 最早采样点）
            margin_df = margin_df.sort_values(['ts_code', 'trade_date'])
            
            margin_buy_scores = {}
            margin_balance_scores = {}
            
            for ts_code, group in margin_df.groupby('ts_code'):
                # 需要至少 6 个采样点来保证趋势有效性
                if len(group) < 6:
                    continue
            
                group = group.tail(12)
            
                # 融资买入趋势：最近2个采样点均值 vs 最早2个采样点均值
                recent_buy = group['rzmre'].iloc[-2:].mean()
                baseline_buy = group['rzmre'].iloc[:2].mean()
            
                if baseline_buy > 0:
                    buy_trend = (recent_buy - baseline_buy) / baseline_buy * 100
                    margin_buy_scores[ts_code] = buy_trend
            
                # 融资余额增长：最近2个采样点均值 vs 最早2个采样点均值
                recent_balance = group['rzye'].iloc[-2:].mean()
                baseline_balance = group['rzye'].iloc[:2].mean()
                
                if baseline_balance > 0:
                    balance_growth = (recent_balance - baseline_balance) / baseline_balance * 100
                    margin_balance_scores[ts_code] = balance_growth
            
            # Step 3: 综合评分筛选（不再用硬交集，改用加权综合分）
            # 对每只股票计算综合趋势分
            composite_scores = {}
            for ts_code in set(margin_buy_scores.keys()) | set(margin_balance_scores.keys()):
                buy_trend = margin_buy_scores.get(ts_code, 0)
                balance_growth = margin_balance_scores.get(ts_code, 0)
                # 综合分 = 融资买入趋势 * 0.6 + 融资余额增长 * 0.4
                composite = buy_trend * 0.6 + balance_growth * 0.4
                if composite >= margin_buy_trend_min * 0.6:  # 加权阈值
                    composite_scores[ts_code] = composite
            
            print(f"融资买入趋势候选: {len(margin_buy_scores)}只")
            print(f"融资余额增长候选: {len(margin_balance_scores)}只")
            print(f"综合筛选结果: {len(composite_scores)}只股票")
            
            if not composite_scores:
                return []
            
            # Step 4: 获取这些股票的详细信息（预构建索引避免循环内线性扫描）
            stock_basic = self._get_stock_basic()
            
            # 获取 ETF/LOF 基金名称（fund_basic）
            etf_name_map = {}
            try:
                fund_basic = self.pro.fund_basic(market='E')
                if fund_basic is not None and not fund_basic.empty:
                    etf_name_map = dict(zip(fund_basic['ts_code'], fund_basic['name']))
            except Exception:
                pass
            
            latest_date = self._get_latest_trade_date()
            daily_basic = self.pro.daily_basic(trade_date=latest_date)
            daily_price = self.pro.daily(trade_date=latest_date)
            
            # 构建 dict 索引，O(1) 查找
            name_map = dict(zip(stock_basic['ts_code'], stock_basic['name']))
            industry_map = dict(zip(stock_basic['ts_code'], stock_basic['industry']))
            
            price_map = {}
            if daily_price is not None and not daily_price.empty:
                for _, row in daily_price.iterrows():
                    code = row['ts_code']
                    price_map[code] = {
                        'close': float(row['close']) if pd.notna(row.get('close')) else None,
                        'pct_chg': float(row['pct_chg']) if 'pct_chg' in daily_price.columns and pd.notna(row.get('pct_chg')) else None,
                    }
            
            basic_map = {}
            if daily_basic is not None and not daily_basic.empty:
                for _, row in daily_basic.iterrows():
                    code = row['ts_code']
                    basic_map[code] = float(row['total_mv']) if pd.notna(row.get('total_mv')) else None
            
            results = []
            for ts_code in composite_scores:
                # 剔除北交所股票
                if ts_code.endswith('.BJ'):
                    continue

                try:
                    # 名称：先查 stock_basic，再查 ETF 名称
                    name = name_map.get(ts_code, '') or etf_name_map.get(ts_code, '')
                    industry = industry_map.get(ts_code, '')
                    
                    price_info = price_map.get(ts_code, {})
                    close = price_info.get('close')
                    pct_chg = price_info.get('pct_chg')
                    total_mv = basic_map.get(ts_code)
                    
                    margin_buy_trend = margin_buy_scores.get(ts_code)
                    margin_balance_growth = margin_balance_scores.get(ts_code)
                    composite = composite_scores[ts_code]
                    
                    # 动态评分：综合趋势分映射到 0-100
                    # 5% 增长率 → 60分，20%+ → 满分
                    base_score = min(100, max(0, round(composite * 2.0 + 50, 1)))
                    
                    result = {
                        'ts_code': ts_code,
                        'name': name,
                        'industry': industry,
                        'score': base_score,
                        'close': close,
                        'pct_chg': pct_chg,
                        'total_mv': total_mv,
                        'margin_buy_trend': round(margin_buy_trend, 2) if margin_buy_trend is not None else None,
                        'margin_balance_growth': round(margin_balance_growth, 2) if margin_balance_growth is not None else None,
                        'composite_trend': round(composite, 2),
                        'fund_tracking_score': base_score
                    }
                    results.append(result)
                    
                except Exception as e:
                    print(f"计算{ts_code}评分失败: {str(e)}")
                    continue
            
            print(f"📊 综合评分完成: {len(results)}只")
            return sorted(results, key=lambda x: x.get('score', 0), reverse=True)[:limit]
            
        except Exception as e:
            print(f"优化资金追踪筛选失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []


if __name__ == "__main__":
    async def test_adapter():
        adapter = FundFlowTrackingAdapter()
        result = await adapter.screen_stocks(limit=10)
        print(f"测试结果: 找到 {result['total_count']} 只股票")
        for stock in result['stocks'][:3]:
            print(f"  {stock['ts_code']} {stock['name']} 评分: {stock['score']}")
    
    asyncio.run(test_adapter())
