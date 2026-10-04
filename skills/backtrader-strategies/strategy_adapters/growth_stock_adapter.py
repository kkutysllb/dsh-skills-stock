#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成长股策略适配器 - Tushare API 版本
寻找高成长性、高盈利能力的成长股

策略特点：
- 寻找高成长性、高盈利能力的成长股
- 基于最近12个季度财务数据分析
- 分级筛选：成长性 + 盈利能力 + 财务安全
- 适合中长线成长投资
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


class GrowthStockAdapter:
    """成长股策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "成长股策略"
        self.strategy_type = "growth"
        self.description = "寻找高成长性、高盈利能力的成长股"
        
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
            'eps_growth_min': 10,
            'revenue_growth_min': 8,
            'roic_min': 6,
            'gross_margin_min': 15,
            'net_margin_min': 5,
            'debt_ratio_max': 80,
            'quick_ratio_min': 0.5,
            'peg_min': 0.2,
            'peg_max': 1.5,
            'growth_weight': 0.4,
            'profitability_weight': 0.35,
            'innovation_weight': 0.15,
            'safety_weight': 0.1,
            'quarters_needed': 4,
            'max_quarters': 12
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
        """获取最新有数据的交易日期（带缓存）"""
        if hasattr(self, '_latest_trade_date_cache'):
            return self._latest_trade_date_cache
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
            df = self.pro.trade_cal(
                exchange='SSE', is_open=1,
                start_date=start_date, end_date=end_date
            )
            if df is not None and not df.empty:
                # trade_cal 返回可能倒序，按日期降序尝试
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
    
    def _get_recent_periods(self, date_str: str, num_periods: int = 12) -> List[str]:
        """根据日期计算最近N个财报报告期"""
        try:
            if '-' in date_str:
                current_date = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                current_date = datetime.strptime(date_str, '%Y%m%d')
        except Exception:
            current_date = datetime.now()
        
        periods = []
        quarter_months = [3, 6, 9, 12]
        year = current_date.year
        q_idx = -1
        for i, m in enumerate(quarter_months):
            if current_date.month > m or (current_date.month == m and current_date.day >= 25):
                q_idx = i
        
        for _ in range(num_periods):
            if q_idx < 0:
                year -= 1
                q_idx = 3
            month = quarter_months[q_idx]
            day = 30 if month != 12 else 31
            periods.append(f"{year}{month:02d}{day}")
            q_idx -= 1
        
        return periods
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20) -> Dict[str, Any]:
        """
        成长股策略选股
        
        Args:
            market_cap: 市值范围 (large/mid/small/all)
            stock_pool: 股票池 (all/main/gem/star)
            limit: 返回股票数量
            
        Returns:
            选股结果字典
        """
        try:
            latest_date = self._get_latest_trade_date()
            print(f"  📅 最新交易日: {latest_date}")
            
            # Step 1: 获取 daily_basic 做粗筛（估值 + 流动性）
            daily_df = self.pro.daily_basic(trade_date=latest_date)
            if daily_df is None or daily_df.empty:
                print("  ❌ daily_basic 无数据")
                return self._empty_result()
            
            # 过滤停牌（close > 0）和北交所股票
            daily_df = daily_df[
                (daily_df['close'] > 0) &
                (~daily_df['ts_code'].str.endswith('.BJ'))
            ]
            print(f"  📊 daily_basic 候选: {len(daily_df)} 只")
            
            # 市值筛选（提前过滤，减少 fina_indicator 调用量）
            if market_cap == "large":
                daily_df = daily_df[daily_df['total_mv'] >= 5000000]
            elif market_cap == "mid":
                daily_df = daily_df[(daily_df['total_mv'] >= 1000000) & (daily_df['total_mv'] <= 5000000)]
            elif market_cap == "small":
                daily_df = daily_df[daily_df['total_mv'] <= 1000000]
            
            # 股票池筛选
            if stock_pool != "all":
                pool_filter = self._get_pool_suffix_filter(stock_pool)
                if pool_filter:
                    daily_df = daily_df[daily_df['ts_code'].str.endswith(pool_filter)]
            
            if daily_df.empty:
                print("  ❌ 粗筛后无候选")
                return self._empty_result()
            
            # 取 top 200 只按换手率排序，减少 API 调用
            daily_df = daily_df.sort_values('turnover_rate', ascending=False).head(200)
            candidate_codes = daily_df['ts_code'].tolist()
            print(f"  🔍 粗筛候选: {len(candidate_codes)} 只，开始获取财务数据...")
            
            # Step 2: 逐股获取 fina_indicator（必须传 ts_code）
            periods = self._get_recent_periods(latest_date, num_periods=12)
            
            all_fina = []
            for i, ts_code in enumerate(candidate_codes):
                try:
                    df = self.pro.fina_indicator(
                        ts_code=ts_code,
                        fields='ts_code,end_date,roe,roe_waa,roic,'
                               'grossprofit_margin,netprofit_margin,'
                               'debt_to_assets,quick_ratio,current_ratio,'
                               'basic_eps_yoy,or_yoy,netprofit_yoy,eps'
                    )
                    if df is not None and not df.empty:
                        # 只保留目标报告期的数据
                        if 'end_date' in df.columns:
                            df = df[df['end_date'].isin(periods)]
                        if not df.empty:
                            all_fina.append(df)
                except Exception:
                    continue
                
                if (i + 1) % 50 == 0:
                    print(f"    已查询 {i + 1}/{len(candidate_codes)} 只...")
            
            if not all_fina:
                print("  ❌ 无财务数据")
                return self._empty_result()
            
            fina_df = pd.concat(all_fina, ignore_index=True)
            fina_df = fina_df.sort_values(['ts_code', 'end_date'], ascending=[True, False])
            print(f"  📈 财务数据: {len(fina_df)} 条，覆盖 {fina_df['ts_code'].nunique()} 只股票")
            
            # Step 2: 计算每个股票的财务指标均值
            numeric_cols = ['basic_eps_yoy', 'or_yoy', 'roic', 'grossprofit_margin',
                          'netprofit_margin', 'debt_to_assets', 'quick_ratio']
            for col in numeric_cols:
                if col in fina_df.columns:
                    fina_df[col] = pd.to_numeric(fina_df[col], errors='coerce').fillna(0)
            
            # 按 ts_code 分组计算均值
            def calc_group_avg(g):
                max_q = self.params['max_quarters']
                return pd.Series({
                    'avg_eps_growth': g['basic_eps_yoy'].head(max_q).mean() if 'basic_eps_yoy' in g.columns else 0,
                    'avg_revenue_growth': g['or_yoy'].head(max_q).mean() if 'or_yoy' in g.columns else 0,
                    'avg_roic': g['roic'].head(8).mean() if 'roic' in g.columns else 0,
                    'avg_gross_margin': g['grossprofit_margin'].head(8).mean() if 'grossprofit_margin' in g.columns else 0,
                    'avg_net_margin': g['netprofit_margin'].head(8).mean() if 'netprofit_margin' in g.columns else 0,
                    'avg_debt_ratio': g['debt_to_assets'].head(8).mean() if 'debt_to_assets' in g.columns else 0,
                    'avg_quick_ratio': g['quick_ratio'].head(8).mean() if 'quick_ratio' in g.columns else 0,
                    'financial_periods': len(g)
                })
            
            fina_avg = fina_df.groupby('ts_code').apply(calc_group_avg).reset_index()
            
            # 过滤财务数据不足的
            fina_avg = fina_avg[fina_avg['financial_periods'] >= self.params['quarters_needed']]
            
            if fina_avg.empty:
                return self._empty_result()
            
            # Step 3: 关联 daily_basic 估值数据（已粗筛过，直接 merge）
            daily_cols = daily_df[['ts_code', 'close', 'pe', 'pb', 'total_mv', 'turnover_rate']].copy()
            fina_avg = fina_avg.merge(daily_cols, on='ts_code', how='inner')
            
            # 关联 daily 数据获取 pct_chg
            try:
                daily_price = self.pro.daily(trade_date=latest_date)
                if daily_price is not None and not daily_price.empty:
                    fina_avg = fina_avg.merge(
                        daily_price[['ts_code', 'pct_chg']],
                        on='ts_code', how='left'
                    )
                    fina_avg['pct_chg'] = fina_avg['pct_chg'].fillna(0)
                else:
                    fina_avg['pct_chg'] = 0
            except Exception:
                fina_avg['pct_chg'] = 0
            
            # Step 4: 应用筛选条件
            # 核心成长性条件（二选一）
            growth_mask = (
                (fina_avg['avg_eps_growth'] >= self.params['eps_growth_min']) |
                (fina_avg['avg_revenue_growth'] >= self.params['revenue_growth_min'])
            )
            
            # 盈利能力条件（三选二）
            profit_mask = (
                ((fina_avg['avg_roic'] >= self.params['roic_min']).astype(int) +
                 (fina_avg['avg_gross_margin'] >= self.params['gross_margin_min']).astype(int) +
                 (fina_avg['avg_net_margin'] >= self.params['net_margin_min']).astype(int)) >= 2
            )
            
            # 财务安全
            safety_mask = (
                (fina_avg['avg_debt_ratio'] < self.params['debt_ratio_max']) &
                (fina_avg['avg_quick_ratio'] > self.params['quick_ratio_min']) &
                (fina_avg['pe'].notna()) & (fina_avg['pb'].notna())
            )
            
            fina_avg = fina_avg[growth_mask & profit_mask & safety_mask]
            
            # 市值筛选
            if market_cap == "large":
                fina_avg = fina_avg[fina_avg['total_mv'] >= 5000000]
            elif market_cap == "mid":
                fina_avg = fina_avg[(fina_avg['total_mv'] >= 1000000) & (fina_avg['total_mv'] <= 5000000)]
            elif market_cap == "small":
                fina_avg = fina_avg[fina_avg['total_mv'] <= 1000000]
            
            # 股票池筛选
            if stock_pool != "all":
                resolved_pool = await self._resolve_stock_pool([stock_pool])
                if resolved_pool:
                    fina_avg = fina_avg[fina_avg['ts_code'].isin(resolved_pool)]
            
            if fina_avg.empty:
                return self._empty_result()
            
            # 关联股票基本信息
            stock_basic = self._get_stock_basic()
            fina_avg = fina_avg.merge(stock_basic, on='ts_code', how='left')
            
            # Step 5: 计算 PEG
            avg_eps_last4 = fina_df.groupby('ts_code').apply(
                lambda g: g['basic_eps_yoy'].head(4).mean() if 'basic_eps_yoy' in g.columns else 0
            ).reset_index(name='avg_eps_growth_4q')
            fina_avg = fina_avg.merge(avg_eps_last4, on='ts_code', how='left')
            fina_avg['avg_eps_growth_4q'] = fina_avg['avg_eps_growth_4q'].fillna(0)
            
            pe_safe = fina_avg['pe'].clip(lower=0.01)
            eps_growth_safe = fina_avg['avg_eps_growth_4q'].clip(lower=0.01)
            fina_avg['peg_ratio'] = pe_safe / eps_growth_safe
            fina_avg['peg_ratio'] = fina_avg['peg_ratio'].clip(upper=999)
            
            # Step 6: 计算综合评分
            fina_avg['score'] = (
                (fina_avg['avg_eps_growth'].clip(upper=50) * 0.4) +
                (fina_avg['avg_revenue_growth'].clip(upper=50) * 0.4) +
                (fina_avg['avg_roic'].clip(upper=25) * 0.7) +
                (fina_avg['avg_gross_margin'].clip(upper=80) * 0.25) +
                (fina_avg['avg_net_margin'].clip(upper=40) * 0.5) +
                ((fina_avg['avg_debt_ratio'] < 50).astype(int) * 5) +
                ((fina_avg['avg_quick_ratio'] > 1.2).astype(int) * 5) +
                ((fina_avg['peg_ratio'].between(self.params['peg_min'], self.params['peg_max'])).astype(int) * 10)
            ).round(1)
            
            # Step 7: 排序和限制
            fina_avg = fina_avg.sort_values('score', ascending=False).head(limit)
            
            # Step 8: 处理结果
            processed_results = self._process_results(fina_avg)
            
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'total_count': len(processed_results),
                'stocks': processed_results,
                'timestamp': datetime.now().isoformat(),
                'parameters': {
                    'market_cap': market_cap,
                    'stock_pool': stock_pool,
                    'limit': limit
                }
            }
            
        except Exception as e:
            print(f"❌ 成长股策略选股失败: {e}")
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
    
    def _process_results(self, final_df: pd.DataFrame) -> List[Dict]:
        """处理查询结果"""
        processed = []
        
        for _, result in final_df.iterrows():
            eps_growth = result.get('avg_eps_growth', 0) or 0
            revenue_growth = result.get('avg_revenue_growth', 0) or 0
            roic = result.get('avg_roic', 0) or 0
            gross_margin = result.get('avg_gross_margin', 0) or 0
            net_margin = result.get('avg_net_margin', 0) or 0
            
            stock_info = {
                'ts_code': result.get('ts_code'),
                'name': result.get('name', ''),
                'industry': result.get('industry', ''),
                
                # 基础指标
                'close': round(result.get('close', 0) or 0, 2),
                'pe': round(result.get('pe', 0) or 0, 2),
                'pb': round(result.get('pb', 0) or 0, 2),
                'total_mv': round(result.get('total_mv', 0) or 0, 0),
                'pct_chg': round(result.get('pct_chg', 0) or 0, 2),
                
                # 成长性指标
                'avg_eps_growth': eps_growth,
                'avg_revenue_growth': revenue_growth,
                'eps_yoy': eps_growth,
                'revenue_yoy': revenue_growth,
                
                # 盈利能力指标
                'avg_roic': roic,
                'avg_gross_margin': gross_margin,
                'avg_net_margin': net_margin,
                
                # 估值指标
                'peg_ratio': round(result.get('peg_ratio', 0) or 0, 2),
                
                # 财务安全指标
                'avg_debt_ratio': result.get('avg_debt_ratio', 0) or 0,
                'avg_quick_ratio': result.get('avg_quick_ratio', 0) or 0,
                
                # 创新指标（简化估算）
                'latest_rd_rate': self._estimate_rd_rate(result.get('industry', '')),
                
                # 综合评分
                'score': round(result.get('score', 0) or 0, 1),
                'growth_score': self._calc_growth_score(eps_growth, revenue_growth),
                'profitability_score': self._calc_profitability_score(roic, gross_margin, net_margin),
                
                # 选股理由
                'reason': self._generate_reason(result)
            }
            processed.append(stock_info)
        
        return processed
    
    def _estimate_rd_rate(self, industry: str) -> float:
        """根据行业估算研发费用率"""
        high_tech = ['医疗保健', '化学制药', '生物制药', '通信设备', '电子制造',
                     '软件服务', 'IT设备', '半导体', '芯片', '科技硬件',
                     '计算机设备', '电子元件', '通信服务']
        return 3.5 if industry in high_tech else 1.2
    
    def _calc_growth_score(self, eps_growth: float, revenue_growth: float) -> float:
        """成长分（0~100）"""
        def _map(v: float) -> float:
            v = max(0, v)
            if v <= 10:
                return v * 2.0
            elif v <= 30:
                return 20 + (v - 10) * 1.5
            elif v <= 100:
                return 50 + (v - 30) * (30 / 70)
            else:
                import math
                return min(100, 80 + math.log10(v / 100 + 1) * 20)
        return round(_map(eps_growth) * 0.5 + _map(revenue_growth) * 0.5, 1)
    
    def _calc_profitability_score(self, roic: float, gross_margin: float, net_margin: float) -> float:
        """盈利分（0~100）"""
        def _roic(v: float) -> float:
            v = max(0, v)
            if v <= 8:   return v * 3.0
            elif v <= 20: return 24 + (v - 8) * 3.5
            else:         return min(100, 66 + (v - 20) * 1.5)
        def _margin(v: float, cap: float = 50) -> float:
            v = max(0, min(v, cap))
            return v / cap * 100
        return round(
            _roic(roic) * 0.4 +
            _margin(gross_margin, 60) * 0.35 +
            _margin(net_margin, 40) * 0.25, 1)
    
    def _generate_reason(self, result) -> str:
        """生成选股理由"""
        reasons = []
        
        eps_growth = result.get('avg_eps_growth', 0) or 0
        revenue_growth = result.get('avg_revenue_growth', 0) or 0
        roic = result.get('avg_roic', 0) or 0
        peg_ratio = result.get('peg_ratio', 0) or 0
        score = result.get('score', 0) or 0
        
        if eps_growth >= 20:
            reasons.append(f"EPS增长{eps_growth:.1f}%优秀")
        elif eps_growth >= 10:
            reasons.append(f"EPS增长{eps_growth:.1f}%良好")
            
        if revenue_growth >= 15:
            reasons.append(f"营收增长{revenue_growth:.1f}%强劲")
        elif revenue_growth >= 8:
            reasons.append(f"营收增长{revenue_growth:.1f}%稳健")
        
        if roic >= 15:
            reasons.append(f"ROIC{roic:.1f}%优秀")
        elif roic >= 10:
            reasons.append(f"ROIC{roic:.1f}%良好")
        
        if 0.5 <= peg_ratio <= 1.0:
            reasons.append(f"PEG{peg_ratio:.1f}合理估值")
        elif 0.2 <= peg_ratio < 0.5:
            reasons.append(f"PEG{peg_ratio:.1f}低估")
        
        reasons.append(f"综合评分{score:.1f}分")
        
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
async def test_growth_stock_adapter():
    """测试成长股策略适配器"""
    adapter = GrowthStockAdapter()
    result = await adapter.screen_stocks(market_cap="all", stock_pool="all", limit=10)
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   EPS增长: {stock['avg_eps_growth']}%, 营收增长: {stock['avg_revenue_growth']}%")
        print(f"   评分: {stock['score']}, 理由: {stock['reason']}")


if __name__ == "__main__":
    asyncio.run(test_growth_stock_adapter())
