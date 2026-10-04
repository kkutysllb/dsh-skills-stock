#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连板龙头策略适配器 - Tushare API 版本
基于涨跌停数据的真实连板分析
"""

import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
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


class LimitUpLeaderAdapter:
    """连板龙头策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "连板龙头策略"
        self.strategy_type = "limit_up"
        self.description = "基于涨跌停数据的真实连板分析"
        
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
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           min_limit_times: int = 2,
                           max_limit_times: int = 10,
                           max_open_times: int = 3,
                           min_turnover: float = 5.0,
                           max_turnover: float = 30.0,
                           **kwargs) -> Dict[str, Any]:
        """连板龙头策略选股"""
        try:
            print("  🔍 获取涨停数据...")
            
            # Step 1: 获取涨跌停数据（向最近有数据的交易日回溯）
            end_date = datetime.now().strftime('%Y%m%d')
            limit_df = None
            for offset in range(5):
                try_date = (datetime.now() - timedelta(days=offset)).strftime('%Y%m%d')
                df = self.pro.limit_list_d(
                    trade_date=try_date,
                    limit_type='U'
                )
                if df is not None and not df.empty:
                    limit_df = df
                    break
            
            if limit_df is None or limit_df.empty:
                return self._empty_result("找不到涨跌停数据")
            
            latest_date = limit_df['trade_date'].max()
            print(f"  📅 最新涨停日期: {latest_date}, 涨停股票: {len(limit_df)} 只")
            
            # 过滤北交所
            limit_df = limit_df[~limit_df['ts_code'].str.endswith('.BJ')]
            
            # 过滤连板条件
            mask = (
                (limit_df['limit_times'] >= min_limit_times) &
                (limit_df['limit_times'] <= max_limit_times) &
                (limit_df['open_times'] <= max_open_times)
            )
            limit_df = limit_df[mask]
            
            if limit_df.empty:
                return self._empty_result()
            
            # Step 2: 关联股票基本信息（limit_list_d 已自带 name/industry，避免列名冲突）
            stock_basic = self._get_stock_basic()
            stock_basic_cols = stock_basic.drop(columns=['name', 'industry'], errors='ignore')
            merged = limit_df.merge(stock_basic_cols, on='ts_code', how='left')
            
            # 过滤ST
            if 'name' in merged.columns:
                merged = merged[~merged['name'].str.contains('ST', case=False, na=False)]
            
            # Step 3: 关联 daily_basic 获取 turnover_rate（注意：limit_df 已有 close/total_mv，避免冲突）
            daily_basic = self.pro.daily_basic(trade_date=latest_date)
            if daily_basic is not None and not daily_basic.empty:
                # 只取 limit_df 没有的字段，避免列名冲突
                basic_cols = daily_basic[['ts_code', 'pe', 'pb', 'turnover_rate']].copy()
                merged = merged.merge(basic_cols, on='ts_code', how='left')
            else:
                merged['pe'] = 0
                merged['pb'] = 0
                merged['turnover_rate'] = 0
            
            # 落实换手率过滤
            if 'turnover_rate' in merged.columns:
                merged['turnover_rate'] = pd.to_numeric(merged['turnover_rate'], errors='coerce').fillna(0)
                merged = merged[
                    (merged['turnover_rate'] >= min_turnover) &
                    (merged['turnover_rate'] <= max_turnover)
                ]
            
            if merged.empty:
                return self._empty_result()
            
            # Step 4: 计算评分
            merged['score'] = (merged['limit_times'] * 10).astype(float)
            
            # 龙头判定
            merged['is_leader'] = (merged['limit_times'] >= 3) & (merged['open_times'] <= 1)
            
            # 排序
            merged = merged.sort_values(['score', 'limit_times'], ascending=[False, False]).head(limit)
            
            # Step 5: 处理结果
            processed_results = []
            for _, result in merged.iterrows():
                limit_times = int(result.get('limit_times', 0))
                open_times = int(result.get('open_times', 0))
                
                stock_info = {
                    'ts_code': result.get('ts_code'),
                    'name': result.get('name', ''),
                    'industry': result.get('industry', ''),
                    'close': round(result.get('close') or 0, 2),  # limit_list_d 自带 close
                    'pe': round(result.get('pe') or 0, 2),
                    'pb': round(result.get('pb') or 0, 2),
                    'total_mv': round((result.get('total_mv') or 0), 0),  # limit_list_d 自带 total_mv
                    'pct_chg': round(result.get('pct_chg') or 0, 2),  # limit_list_d 自带实际涨跌幅
                    'limit_times': limit_times,
                    'open_times': open_times,
                    'turnover_rate': round(result.get('turnover_rate') or 0, 2),
                    'amount': round((result.get('amount') or 0) / 100000000, 2),  # 亿元
                    'is_leader': bool(result.get('is_leader', False)),
                    'score': round(result.get('score', 0) or 0, 2),
                    'reason': self._generate_reason(limit_times, open_times)
                }
                processed_results.append(stock_info)
            
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
                    'min_limit_times': min_limit_times,
                    'max_limit_times': max_limit_times,
                    'max_open_times': max_open_times,
                    'min_turnover': min_turnover,
                    'max_turnover': max_turnover
                }
            }
            
        except Exception as e:
            print(f"❌ 连板龙头策略选股失败: {e}")
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
    
    def _generate_reason(self, limit_times: int, open_times: int) -> str:
        """生成选股理由"""
        reasons = []
        
        if limit_times >= 5:
            reasons.append(f"{limit_times}连板领涨")
        elif limit_times >= 3:
            reasons.append(f"{limit_times}连板强势")
        else:
            reasons.append(f"{limit_times}连板")
        
        if open_times == 0:
            reasons.append("一字板")
        elif open_times == 1:
            reasons.append("开板1次")
        else:
            reasons.append(f"开板{open_times}次")
        
        if limit_times >= 3 and open_times <= 1:
            reasons.append("板块龙头")
        
        return "；".join(reasons)
    
    def _empty_result(self, error: str = None) -> Dict[str, Any]:
        """返回空结果"""
        result = {
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type,
            'total_count': 0,
            'stocks': [],
            'timestamp': datetime.now().isoformat(),
            'parameters': {}
        }
        if error:
            result['error'] = error
        return result


# 测试函数
async def test_limit_up_leader_adapter():
    """测试连板龙头策略适配器"""
    adapter = LimitUpLeaderAdapter()
    result = await adapter.screen_stocks(limit=10)
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   连板: {stock['limit_times']}次, 评分: {stock['score']}, 理由: {stock['reason']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_limit_up_leader_adapter())
