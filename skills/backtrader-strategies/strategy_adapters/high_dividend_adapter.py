#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高股息策略适配器 - Tushare API 版本
将复杂计算从MongoDB聚合管道移到Python层

策略特点：
- 专注于高股息收益的稳健股票
- 基础数据用 Tushare API 获取
- 复杂计算在Python层完成
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


class HighDividendAdapter:
    """高股息策略适配器 - Tushare API 版"""
    
    def __init__(self):
        self.strategy_name = "高股息策略"
        self.strategy_type = "dividend"
        self.description = "寻找高股息收益、分红稳定的优质股票"
        
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
        
        # 筛选参数（放宽条件）
        self.params = {
            'pe_max': 100,
            'pb_max': 20,
            'total_mv_min': 500000,   # 50亿最小市值（万元）
            'eps_min': 0.05,          # 最小EPS
            'dividend_yield_min': 1.0, # 最小股息率
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
    
    async def screen_stocks(self,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20,
                           **kwargs) -> Dict[str, Any]:
        """
        高股息策略选股
        
        Args:
            market_cap: 市值范围 (large/mid/small/all)
            stock_pool: 股票池 (all/main/gem/star)
            limit: 返回股票数量
            **kwargs: 其他参数
            
        Returns:
            选股结果字典
        """
        try:
            # 步骤1：获取基础股票数据
            basic_stocks = await self._get_basic_stocks(market_cap, stock_pool, limit * 5)
            
            if not basic_stocks:
                return self._empty_result()
            
            # 步骤2：获取财务数据
            enriched_stocks = await self._enrich_financial_data(basic_stocks)
            
            # 步骤3：Python层计算和筛选
            processed_stocks = await self._calculate_and_filter(enriched_stocks, limit)
            
            return {
                'strategy_name': self.strategy_name,
                'strategy_type': self.strategy_type,
                'total_count': len(processed_stocks),
                'stocks': processed_stocks,
                'timestamp': datetime.now().isoformat(),
                'parameters': {
                    'market_cap': market_cap,
                    'stock_pool': stock_pool,
                    'limit': limit
                }
            }
            
        except Exception as e:
            print(f"❌ 高股息策略选股失败: {e}")
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
    
    async def _get_basic_stocks(self, market_cap: str, stock_pool: str, pre_limit: int) -> List[Dict]:
        """获取基础股票数据"""
        try:
            latest_date = self._get_latest_trade_date()
            print(f"  📅 最新交易日: {latest_date}")
            
            # 获取 daily_basic 数据
            daily_df = self.pro.daily_basic(trade_date=latest_date)
            if daily_df is None or daily_df.empty:
                print("  ❌ daily_basic 无数据")
                return []
            
            # 基础筛选：过滤停牌和北交所
            mask = (
                (daily_df['close'] > 2.0) &
                (daily_df['total_mv'] > 500000) &
                (daily_df['pe'] > 0) & (daily_df['pe'] < 100) &
                (daily_df['pb'] > 0) & (daily_df['pb'] < 20) &
                (~daily_df['ts_code'].str.endswith('.BJ'))
            )
            daily_df = daily_df[mask]
            print(f"  📊 daily_basic 粗筛: {len(daily_df)} 只")
            
            # 市值筛选
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
            
            # 关联股票基本信息
            stock_basic = self._get_stock_basic()
            merged = daily_df.merge(stock_basic, on='ts_code', how='left')
            
            # 过滤ST股票
            if 'name' in merged.columns:
                merged = merged[~merged['name'].str.contains('ST', case=False, na=False)]
            
            # 获取 daily 数据 (pct_chg)
            daily_price = self.pro.daily(trade_date=latest_date)
            if daily_price is not None and not daily_price.empty:
                price_cols = daily_price[['ts_code', 'pct_chg', 'vol', 'amount']].copy()
                merged = merged.merge(price_cols, on='ts_code', how='left')
            
            # 按市值排序，取前 N
            merged = merged.sort_values('total_mv', ascending=False).head(pre_limit)
            
            # 转为字典列表
            return merged.to_dict('records')
            
        except Exception as e:
            print(f"获取基础股票数据失败: {e}")
            return []
    
    async def _enrich_financial_data(self, stocks: List[Dict]) -> List[Dict]:
        """批量获取财务数据 + 真实分红数据"""
        if not stocks:
            return []
        
        ts_codes = [stock['ts_code'] for stock in stocks]
        print(f"  🔍 获取 {len(ts_codes)} 只股票的财务和分红数据...")
        
        try:
            # 获取最新财务指标（包含 netprofit_margin）
            fina_data = {}
            for i, ts_code in enumerate(ts_codes):
                try:
                    df = self.pro.fina_indicator(
                        ts_code=ts_code,
                        fields='ts_code,end_date,eps,roe,roa,roic,debt_to_assets,'
                               'current_ratio,quick_ratio,profit_dedt,netprofit_yoy,'
                               'netprofit_margin,grossprofit_margin'
                    )
                    if df is not None and not df.empty:
                        # 过滤 NaN 行，取第一条有效记录
                        valid = df.dropna(subset=['eps', 'roe'], how='all')
                        if not valid.empty:
                            fina_data[ts_code] = valid.iloc[0].to_dict()
                except Exception:
                    continue
                if (i + 1) % 50 == 0:
                    print(f"    fina_indicator 已查询 {i + 1}/{len(ts_codes)}...")
            
            # 获取现金流数据（过滤 NaN）
            cash_data = {}
            for ts_code in ts_codes:
                try:
                    df = self.pro.cashflow(
                        ts_code=ts_code,
                        fields='ts_code,end_date,c_pay_dist_dpcp_int_exp,stot_cash_in_fnc_act'
                    )
                    if df is not None and not df.empty:
                        # 关键：过滤掉 NaN 行，取最新的有效记录
                        col = 'c_pay_dist_dpcp_int_exp'
                        valid = df[df[col].notna() & (df[col] != 0)]
                        if not valid.empty:
                            cash_data[ts_code] = valid.iloc[0].to_dict()
                except Exception:
                    continue
            
            # 获取真实分红数据（dividend API）
            dividend_data = {}
            for ts_code in ts_codes:
                try:
                    df = self.pro.dividend(ts_code=ts_code)
                    if df is not None and not df.empty:
                        # 取 cash_div > 0 的最新年报记录
                        annual = df[
                            (df['end_date'].str.endswith('1231')) &
                            (df['cash_div'] > 0)
                        ]
                        if not annual.empty:
                            dividend_data[ts_code] = annual.iloc[0].to_dict()
                except Exception:
                    continue
            print(f"  📈 财务: {len(fina_data)} 只, 现金流: {len(cash_data)} 只, 分红: {len(dividend_data)} 只")
            
            # 合并数据
            for stock in stocks:
                ts_code = stock['ts_code']
                stock['fina_data'] = fina_data.get(ts_code, {})
                stock['cash_data'] = cash_data.get(ts_code, {})
                stock['dividend_data'] = dividend_data.get(ts_code, {})
            
            return stocks
            
        except Exception as e:
            print(f"获取财务数据失败: {e}")
            return stocks
    
    async def _calculate_and_filter(self, stocks: List[Dict], limit: int) -> List[Dict]:
        """在Python层计算指标并筛选"""
        calculated_stocks = []
        
        for stock in stocks:
            try:
                metrics = self._calculate_dividend_metrics(stock)
                
                if self._meets_criteria(metrics):
                    metrics['score'] = self._calculate_score(metrics)
                    metrics['dividend_score'] = round(metrics['dividend_yield'] * 8, 1)
                    calculated_stocks.append(metrics)
                    
            except Exception as e:
                print(f"处理股票 {stock.get('ts_code')} 失败: {e}")
                continue
        
        calculated_stocks.sort(key=lambda x: x['score'], reverse=True)
        return calculated_stocks[:limit]
    
    def _calculate_dividend_metrics(self, stock: Dict) -> Dict:
        """计算股息相关指标"""
        fina = stock.get('fina_data', {})
        cash = stock.get('cash_data', {})
        div = stock.get('dividend_data', {})
        
        # 基础数据
        eps = fina.get('eps', 0) or 0
        close = stock.get('close', 0) or 0
        roe = fina.get('roe', 0) or 0
        roa = fina.get('roa', 0) or 0
        roic = fina.get('roic', 0) or 0
        debt_to_assets = fina.get('debt_to_assets', 0) or 0
        
        # 银行业特殊处理
        industry = stock.get('industry', '')
        if roic == 0 and industry in ['银行', '保险', '金融']:
            roic = roe * 0.8 if roe > 0 else 0
        
        # 真实股息率：用 dividend API 的 cash_div（每股分红，税前）/ 股价
        dividend_yield = 0
        cash_div = div.get('cash_div', 0) or 0  # 每股分红（元）
        if cash_div > 0 and close > 0:
            dividend_yield = (cash_div / close) * 100
        
        # 现金流分红数据
        dividend_paid = abs(cash.get('c_pay_dist_dpcp_int_exp', 0) or 0)
        net_profit = fina.get('profit_dedt', 0) or 0
        financing_inflow = cash.get('stot_cash_in_fnc_act', 0) or 0
        
        # 股息支付率
        payout_ratio = 0
        if dividend_paid > 0 and net_profit > 0:
            payout_ratio = min(100, (dividend_paid / net_profit) * 100)
        
        # 分红募资比
        dividend_fundraising_ratio = 0
        if dividend_paid > 0 and financing_inflow > 0:
            dividend_fundraising_ratio = min(200, (dividend_paid / financing_inflow) * 100)
        
        total_mv = stock.get('total_mv', 0) or 0
        
        # 真实净利润率（来自 fina_indicator）
        net_profit_margin = fina.get('netprofit_margin', 0) or 0
        
        return {
            'ts_code': stock.get('ts_code'),
            'name': stock.get('name', ''),
            'industry': stock.get('industry', ''),
            'close': round(close, 2),
            'pe': round(stock.get('pe', 0) or 0, 2),
            'pb': round(stock.get('pb', 0) or 0, 2),
            'pct_chg': round(stock.get('pct_chg', 0) or 0, 2),
            'total_mv': round(total_mv / 10000, 2),  # 转换为亿元
            
            # 股息指标
            'dividend_yield': round(dividend_yield, 2),
            'dv_ratio': round(dividend_yield, 2),
            'dv_ttm': round(dividend_yield, 2),
            'payout_ratio': round(payout_ratio, 2),
            'dividend_fundraising_ratio': round(dividend_fundraising_ratio, 2),
            'roe': round(roe, 2),
            'roa': round(roa, 2) if roa else 0,
            'roic': round(roic, 2) if roic else 0,
            'debt_ratio': round(debt_to_assets, 2) if debt_to_assets else 0,
            'eps': round(eps, 2),
            'net_profit_margin': round(net_profit_margin, 2),
            
            # 选股理由
            'reason': self._generate_reason({
                'dividend_yield': dividend_yield,
                'roe': roe,
                'payout_ratio': payout_ratio
            })
        }
    
    def _meets_criteria(self, metrics: Dict) -> bool:
        """检查是否满足筛选条件"""
        return (
            metrics['eps'] > self.params['eps_min'] and
            metrics['total_mv'] >= self.params['total_mv_min'] / 10000 and
            metrics['dividend_yield'] >= self.params['dividend_yield_min'] and
            metrics['pe'] > 0 and metrics['pe'] < self.params['pe_max'] and
            metrics['pb'] > 0 and metrics['pb'] < self.params['pb_max']
        )
    
    def _calculate_score(self, metrics: Dict) -> float:
        """计算综合评分"""
        score = 0
        
        # 股息率权重 40%
        score += metrics['dividend_yield'] * 8
        
        # ROE权重 20%
        score += min(metrics['roe'], 20) * 2
        
        # 市值稳定性 20%
        score += min(metrics['total_mv'] / 10, 10)
        
        # 分红稳定性 20%
        if metrics['payout_ratio'] > 20:
            score += min(metrics['payout_ratio'] / 5, 10)
        
        # 基础分
        score += 20
        
        return round(score, 1)
    
    def _generate_reason(self, metrics: Dict) -> str:
        """生成选股理由"""
        reasons = []
        
        dividend_yield = metrics.get('dividend_yield', 0)
        roe = metrics.get('roe', 0)
        payout_ratio = metrics.get('payout_ratio', 0)
        
        if dividend_yield >= 5:
            reasons.append(f"高股息率{dividend_yield:.1f}%")
        elif dividend_yield >= 3:
            reasons.append(f"股息率{dividend_yield:.1f}%")
        
        if roe >= 15:
            reasons.append(f"高ROE{roe:.1f}%")
        elif roe >= 10:
            reasons.append(f"ROE{roe:.1f}%")
        
        if payout_ratio >= 50:
            reasons.append("高分红比例")
        elif payout_ratio >= 20:
            reasons.append("稳定分红")
        
        return "；".join(reasons) if reasons else "财务稳健"
    
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
    
    def _get_pool_suffix_filter(self, stock_pool: str) -> str:
        """根据股票池名返回后缀过滤条件"""
        pool_map = {
            'main': ('.SH', '.SZ'),  # 主板
            'gem': ('.SZ',),          # 创业板
            'star': ('.SH',),         # 科创板
        }
        return pool_map.get(stock_pool, '')
    
    async def _resolve_stock_pool(self, pools: List[str]) -> List[str]:
        """解析股票池（保留兼容）"""
        return []


# 测试函数
async def test_high_dividend_adapter():
    """测试高股息策略适配器"""
    adapter = HighDividendAdapter()
    result = await adapter.screen_stocks(market_cap="all", stock_pool="all", limit=10)
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   股息率: {stock['dividend_yield']}%, ROE: {stock['roe']}%, 评分: {stock['score']}")


if __name__ == "__main__":
    asyncio.run(test_high_dividend_adapter())
