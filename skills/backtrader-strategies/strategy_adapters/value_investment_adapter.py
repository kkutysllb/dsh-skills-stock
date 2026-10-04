#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
价值投资策略适配器 - Tushare API 版本（巴菲特风格）
从API层提取的核心选股逻辑

策略特点：
- 巴菲特式严格质量选股：高ROE、高毛利率、低负债、合理估值
- PE < 25, PB < 3, 总市值 > 100亿
- 基于历史财报均值（8季度）计算综合评分（4大支柱）
- 盈利能力(40%) + 利润质量(25%) + 财务安全(20%) + 合理估值(15%)
- 上市 > 3年的成熟企业
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


class ValueInvestmentAdapter:
    """价值投资策略适配器 - 基于 Tushare API"""
    
    def __init__(self):
        self.strategy_name = "巴菲特价值投资策略"
        self.strategy_type = "fundamental"
        self.description = "巴菲特式严格质量选股：高ROE、高毛利率、低负债、合理估值"
        
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
        
        # 策略参数 - 巴菲特式严格选股标准
        self.params = {
            # 估值筛选 - 巴菲特偏好合理估值
            'pe_max': 25,           # PE < 25 (巴菲特偏好15以下，A股适配放宽)
            'pb_max': 3,            # PB < 3 (巴菲特偏好1.5以下，A股适配放宽)
            'pe_ttm_min': 0,        # 确保TTM市盈率有效
            'total_mv_min': 1000000,  # 总市值 > 100亿 (成熟大企业)
            
            # 盈利能力 - 巴菲特核心标准
            'roe_min': 15,          # ROE >= 15% (巴菲特核心门槛)
            'roe_avg_min': 15,      # 历史ROE均值 >= 15%
            'roe_stable_threshold': 12,  # ROE稳定性最低要求
            
            # 利润质量 - 护城河指标
            'gross_margin_min': 30,     # 毛利率 >= 30% (巴菲特式护城河)
            'net_margin_min': 10,       # 净利率 >= 10% (优质企业标准)
            
            # 成长性要求
            'growth_score_min': 50,      # 成长性评分 >= 50
            'profitability_score_min': 60, # 盈利能力评分 >= 60
            
            # 财务健康度 - 巴菲特偏好低负债
            'debt_ratio_max': 50,        # 资产负债率 <= 50% (巴菲特偏好低负债)
            'current_ratio_min': 1.5,    # 流动比率 >= 1.5 (短期偿债能力强)
            
            # 上市时间要求
            'listing_days_min': 1095,    # 上市 > 3年 (成熟企业)
            
            # 权重配置
            'technical_weight': 0.1,     # 技术面权重
            'fundamental_weight': 0.8,   # 基本面权重
            'special_weight': 0.1        # 特殊因子权重
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
        """获取最新交易日期"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            df = self.pro.trade_cal(
                exchange='SSE', is_open=1,
                start_date=start_date, end_date=end_date
            )
            if df is not None and not df.empty:
                return df['cal_date'].iloc[-1]
        except Exception as e:
            print(f"获取最新交易日期失败: {e}")
        return datetime.now().strftime('%Y%m%d')
    
    def _get_recent_periods(self, date_str: str, num_periods: int = 8) -> List[str]:
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
        # 找到当前或最近已过的季度
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
    
    def _get_financial_data(self, ts_codes: List[str], target_date: str) -> pd.DataFrame:
        """获取财务指标数据（最近8个季度，含巴菲特护城河指标）"""
        periods = self._get_recent_periods(target_date, num_periods=8)
        
        all_fina = []
        for ts_code in ts_codes:
            try:
                df = self.pro.fina_indicator(
                    ts_code=ts_code,
                    fields='ts_code,end_date,roe,roe_yearly,current_ratio,quick_ratio,'
                           'debt_to_assets,debt_to_eqt,profit_dedt,netprofit_yoy,basic_eps_yoy,'
                           'grossprofit_margin,netprofit_margin,or_yoy'
                )
                if df is not None and not df.empty:
                    # 只保留目标报告期的数据
                    if 'end_date' in df.columns:
                        df = df[df['end_date'].isin(periods)]
                    if not df.empty:
                        all_fina.append(df)
            except Exception as e:
                print(f"获取财务数据 ts_code={ts_code} 失败: {e}")
                continue
        
        if not all_fina:
            return pd.DataFrame()
        
        result = pd.concat(all_fina, ignore_index=True)
        # 按 ts_code 和 end_date 排序（最新的在前）
        result = result.sort_values(['ts_code', 'end_date'], ascending=[True, False])
        # 过滤掉 ROE 为空的记录
        if 'roe' in result.columns:
            result['roe'] = pd.to_numeric(result['roe'], errors='coerce')
            result = result[result['roe'].notna() & (result['roe'] > 0)]
        
        return result
    
    async def screen_stocks(self,
                           trade_date: str = None,
                           market_cap: str = "all",
                           stock_pool: str = "all", 
                           limit: int = 20) -> Dict[str, Any]:
        """
        价值投资策略选股
        
        Args:
            trade_date: 交易日期（回测系统使用）
            market_cap: 市值范围 (large/mid/small/all)
            stock_pool: 股票池 (all/main/gem/star/shenwan_value)
            limit: 返回股票数量
            
        Returns:
            选股结果字典
        """
        try:
            # 确定目标日期
            if trade_date:
                target_date = trade_date.replace('-', '')
            else:
                target_date = self._get_latest_trade_date()
            
            # Step 1: 获取 daily_basic 数据
            daily_df = self.pro.daily_basic(trade_date=target_date)
            if daily_df is None or daily_df.empty:
                return self._empty_result()
            
            # 同时获取 daily 数据（用于 pct_chg）
            daily_price = self.pro.daily(trade_date=target_date)
            
            # Step 2: 基础筛选
            mask = (
                (daily_df['pe'] > 0) & (daily_df['pe'] <= self.params['pe_max']) &
                (daily_df['pb'] > 0) & (daily_df['pb'] <= self.params['pb_max']) &
                (daily_df['total_mv'] > self.params['total_mv_min'])
            )
            daily_df = daily_df[mask]
            
            # 市值筛选
            if market_cap == "large":
                daily_df = daily_df[daily_df['total_mv'] >= 5000000]
            elif market_cap == "mid":
                daily_df = daily_df[(daily_df['total_mv'] >= 1000000) & (daily_df['total_mv'] <= 5000000)]
            elif market_cap == "small":
                daily_df = daily_df[daily_df['total_mv'] <= 1000000]
            
            # 股票池筛选
            if stock_pool == "shenwan_value":
                value_stocks = self._get_shenwan_value_stocks()
                if value_stocks:
                    daily_df = daily_df[daily_df['ts_code'].isin(value_stocks)]
            elif stock_pool != "all":
                resolved_pool = await self._resolve_stock_pool([stock_pool])
                if resolved_pool:
                    daily_df = daily_df[daily_df['ts_code'].isin(resolved_pool)]
            
            if daily_df.empty:
                return self._empty_result()
            
            # Step 3: 关联股票基本信息
            stock_basic = self._get_stock_basic()
            merged = daily_df.merge(stock_basic, on='ts_code', how='left')
            
            # 过滤上市时间（防止时间穿越 + 巴菲特式成熟企业要求）
            merged['list_date'] = merged['list_date'].fillna('99991231')
            merged = merged[merged['list_date'] <= target_date]
            # 巴菲特要求：上市至少3年
            cutoff_date = (datetime.strptime(target_date, '%Y%m%d') - timedelta(days=self.params['listing_days_min'])).strftime('%Y%m%d')
            merged = merged[merged['list_date'] <= cutoff_date]
            
            # 关联 daily 数据获取 pct_chg
            if daily_price is not None and not daily_price.empty:
                price_cols = daily_price[['ts_code', 'pct_chg']].copy()
                merged = merged.merge(price_cols, on='ts_code', how='left')
                merged['pct_chg'] = merged['pct_chg'].fillna(0)
            else:
                merged['pct_chg'] = 0
            
            if merged.empty:
                return self._empty_result()
            
            # Step 4: 获取财务数据
            candidate_codes = merged['ts_code'].tolist()
            fina_df = self._get_financial_data(candidate_codes, target_date)
            
            if fina_df is None or fina_df.empty:
                return self._empty_result()
            
            # Step 5: 计算财务指标均值（含巴菲特护城河指标）
            for col in ['roe', 'current_ratio', 'debt_to_assets', 'netprofit_yoy', 'roe_yearly',
                        'grossprofit_margin', 'netprofit_margin', 'or_yoy']:
                if col in fina_df.columns:
                    fina_df[col] = pd.to_numeric(fina_df[col], errors='coerce').fillna(0)
            
            # 按股票分组，取最近8条记录，计算均值
            fina_avg = fina_df.groupby('ts_code').apply(
                lambda g: pd.Series({
                    'avg_roe': g['roe'].head(8).mean() if 'roe' in g.columns else 0,
                    'avg_roe_yearly': g['roe_yearly'].head(8).mean() if 'roe_yearly' in g.columns else 0,
                    'avg_current_ratio': g['current_ratio'].head(8).mean() if 'current_ratio' in g.columns else 0,
                    'avg_debt_ratio': g['debt_to_assets'].head(8).mean() if 'debt_to_assets' in g.columns else 0,
                    'avg_profit_growth': g['netprofit_yoy'].head(8).mean() if 'netprofit_yoy' in g.columns else 0,
                    'avg_gross_margin': g['grossprofit_margin'].head(8).mean() if 'grossprofit_margin' in g.columns else 0,
                    'avg_net_margin': g['netprofit_margin'].head(8).mean() if 'netprofit_margin' in g.columns else 0,
                    'avg_revenue_growth': g['or_yoy'].head(8).mean() if 'or_yoy' in g.columns else 0,
                    'financial_periods': len(g)
                })
            ).reset_index()
            
            # Step 6: 合并数据
            final = merged.merge(fina_avg, on='ts_code', how='inner')
            
            # 过滤财务数据不足4期的
            final = final[final['financial_periods'] >= 4]
            
            # Step 7: 应用巴菲特式核心筛选条件
            final = final[
                (final['avg_roe'] >= self.params['roe_avg_min']) &
                (final['avg_current_ratio'] >= self.params['current_ratio_min']) &
                (final['avg_debt_ratio'] <= self.params['debt_ratio_max']) &
                (final['avg_profit_growth'] >= 10) &
                (final['avg_gross_margin'] >= self.params['gross_margin_min']) &
                (final['avg_net_margin'] >= self.params['net_margin_min'])
            ]
            
            if final.empty:
                return self._empty_result()
            
            # Step 8: 巴菲特4大支柱综合评分
            # 支柱1: 盈利能力 (ROE) - 40%权重，ROE 15%起评，30%+满分
            profitability = (final['avg_roe'] / 15).clip(upper=2) * 20
            # 支柱2: 利润质量 (毛利率+净利率) - 25%权重
            profit_quality = (
                (final['avg_gross_margin'] / 30).clip(upper=1.5) * 0.6 +
                (final['avg_net_margin'] / 10).clip(upper=2) * 0.4
            ) * 25
            # 支柱3: 财务安全 (低负债+高流动) - 20%权重
            financial_safety = (
                (1 - final['avg_debt_ratio'] / 100).clip(lower=0) * 0.7 +
                (final['avg_current_ratio'] / 2).clip(upper=1) * 0.3
            ) * 20
            # 支柱4: 合理估值 (PE+PB) - 15%权重
            valuation = (
                (1 - final['pe'] / 50).clip(lower=0) * 0.6 +
                (1 - final['pb'] / 6).clip(lower=0) * 0.4
            ) * 15
            
            final['value_score'] = (
                profitability + profit_quality + financial_safety + valuation
            )
            final['value_score'] = final['value_score'].round(2)
            
            # Step 9: 排序
            final = final.sort_values('value_score', ascending=False).head(100)
            
            # Step 10: 处理结果
            processed_results = self._process_results(final, limit)
            
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
            print(f"❌ 价值投资策略选股失败: {e}")
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
    
    def _process_results(self, final_df: pd.DataFrame, limit: int) -> List[Dict]:
        """处理查询结果 - 巴菲特价值投资"""
        processed = []
        
        for _, row in final_df.head(limit).iterrows():
            stock_info = {
                'ts_code': row.get('ts_code'),
                'name': row.get('name', ''),
                'industry': row.get('industry', ''),
                
                # 估值指标
                'pe': round(row.get('pe', 0) or 0, 2),
                'pb': round(row.get('pb', 0) or 0, 2),
                'pe_ttm': round(row.get('pe_ttm', 0) or 0, 2) if pd.notna(row.get('pe_ttm')) else 0,
                'close': row.get('close', 0) or 0,
                'pct_chg': round(row.get('pct_chg', 0) or 0, 2),
                'total_mv': round(row.get('total_mv', 0) or 0, 2),
                
                # 财务指标
                'roe': round(row.get('avg_roe', 0) or 0, 2),
                'avg_roe': round(row.get('avg_roe', 0) or 0, 2),
                'avg_roe_yearly': round(row.get('avg_roe_yearly', 0) or 0, 2),
                'avg_current_ratio': round(row.get('avg_current_ratio', 0) or 0, 2),
                'avg_debt_ratio': round(row.get('avg_debt_ratio', 0) or 0, 2),
                'avg_profit_growth': round(row.get('avg_profit_growth', 0) or 0, 2),
                
                # 巴菲特护城河指标
                'avg_gross_margin': round(row.get('avg_gross_margin', 0) or 0, 2),
                'avg_net_margin': round(row.get('avg_net_margin', 0) or 0, 2),
                'avg_revenue_growth': round(row.get('avg_revenue_growth', 0) or 0, 2),
                
                # 评分
                'total_score': round(row.get('value_score', 0) or 0, 2),
                'growth_score': round(row.get('avg_profit_growth', 0) or 0, 1),
                'profitability_score': round((row.get('avg_roe', 0) or 0) * 4, 1),
                
                # 财务数据期数
                'financial_periods': int(row.get('financial_periods', 0)),
                
                # 选股理由
                'reason': self._generate_reason(row)
            }
            processed.append(stock_info)
        
        return processed
    
    def _generate_reason(self, row) -> str:
        """生成选股理由 - 基于巴菲特4大支柱"""
        reasons = []
        
        avg_roe = row.get('avg_roe', 0) or 0
        avg_current_ratio = row.get('avg_current_ratio', 0) or 0
        avg_debt_ratio = row.get('avg_debt_ratio', 0) or 0
        avg_profit_growth = row.get('avg_profit_growth', 0) or 0
        avg_gross_margin = row.get('avg_gross_margin', 0) or 0
        avg_net_margin = row.get('avg_net_margin', 0) or 0
        pe = row.get('pe', 0) or 0
        pb = row.get('pb', 0) or 0
        value_score = row.get('value_score', 0) or 0
        
        # 盈利能力评价 (ROE)
        if avg_roe >= 20:
            reasons.append(f"ROE{avg_roe:.1f}%卓越")
        elif avg_roe >= 15:
            reasons.append(f"ROE{avg_roe:.1f}%优秀")
        
        # 护城河评价 (毛利率)
        if avg_gross_margin >= 40:
            reasons.append(f"毛利率{avg_gross_margin:.1f}%强护城河")
        elif avg_gross_margin >= 30:
            reasons.append(f"毛利率{avg_gross_margin:.1f}%有护城河")
        
        # 净利率评价
        if avg_net_margin >= 15:
            reasons.append(f"净利率{avg_net_margin:.1f}%优质")
        elif avg_net_margin >= 10:
            reasons.append(f"净利率{avg_net_margin:.1f}%良好")
            
        # 财务安全评价
        if avg_debt_ratio <= 30:
            reasons.append(f"负债率{avg_debt_ratio:.1f}%极低")
        elif avg_debt_ratio <= 50:
            reasons.append(f"负债率{avg_debt_ratio:.1f}%健康")
        
        # 现金流评价
        if avg_current_ratio >= 2.0:
            reasons.append(f"流动比率{avg_current_ratio:.1f}高现金流")
        elif avg_current_ratio >= 1.5:
            reasons.append(f"流动比率{avg_current_ratio:.1f}稳健")
        
        # 估值评价
        if pe <= 15:
            reasons.append(f"PE{pe:.1f}倍低估")
        elif pe <= 25:
            reasons.append(f"PE{pe:.1f}倍合理")
            
        if pb <= 2:
            reasons.append(f"PB{pb:.1f}倍低估")
        elif pb <= 3:
            reasons.append(f"PB{pb:.1f}倍适中")
            
        reasons.append(f"巴菲评分{value_score:.1f}分")
        
        return "；".join(reasons)
    
    def _get_shenwan_value_stocks(self) -> List[str]:
        """获取申万传统价值行业股票池（向后兼容）"""
        try:
            value_industries = [
                '银行', '房地产', '钢铁', '煤炭', '石油石化', 
                '公用事业', '交通运输', '建筑装饰', '建筑材料',
                '汽车', '机械设备', '基础化工', '电力设备'
            ]
            stock_basic = self._get_stock_basic()
            filtered = stock_basic[stock_basic['industry'].isin(value_industries)]
            return filtered['ts_code'].tolist()
        except Exception as e:
            print(f"获取申万传统价值行业股票池失败: {e}")
            return []
    
    async def _resolve_stock_pool(self, stock_pools: List[str]) -> List[str]:
        """解析股票池代码"""
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
async def test_value_investment_adapter():
    """测试价值投资策略适配器"""
    adapter = ValueInvestmentAdapter()
    result = await adapter.screen_stocks(market_cap="all", stock_pool="all", limit=10)
    
    print(f"策略名称: {result['strategy_name']}")
    print(f"选股数量: {result['total_count']}")
    
    for i, stock in enumerate(result['stocks'][:5], 1):
        print(f"{i}. {stock['name']} ({stock['ts_code']})")
        print(f"   PE: {stock['pe']}, PB: {stock['pb']}, ROE: {stock['roe']}%")
        print(f"   评分: {stock['total_score']}, 理由: {stock['reason']}")


if __name__ == "__main__":
    asyncio.run(test_value_investment_adapter())
