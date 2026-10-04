#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财报分析引擎
老爸专属财报分析功能 - 第二步：数据分析

支持对接 FinancialReportCrawler 采集的真实 Tushare Pro 数据
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


class FinancialAnalyzer:
    """财报分析引擎"""
    
    def __init__(self):
        self.analysis_results = {}
    
    def analyze_annual_reports(self, annual_reports: List[Dict]) -> Dict:
        """
        分析年报数据 - 同比分析
        
        Args:
            annual_reports: 年报数据列表
            
        Returns:
            年报分析结果
        """
        if not annual_reports:
            return {"error": "没有可用的年报数据"}
        
        # 转换为DataFrame便于分析
        df = pd.DataFrame(annual_reports)
        df['report_date'] = pd.to_datetime(df['report_date'])
        df = df.sort_values('report_date')
        
        analysis_result = {
            'analysis_type': 'annual',
            'periods_analyzed': len(df),
            'revenue_analysis': self._analyze_revenue(df),
            'profit_analysis': self._analyze_profit(df),
            'cash_flow_analysis': self._analyze_cash_flow(df),
            'gross_margin_analysis': self._analyze_gross_margin(df),
            'product_analysis': self._analyze_products(df),
            'contract_liabilities_analysis': self._analyze_contract_liabilities(df),
            'inventory_analysis': self._analyze_inventory(df),
            'valuation_indicators': self._analyze_valuation_indicators(df),
            'overall_trend': self._analyze_overall_trend(df),
            'investment_suggestions': self._generate_investment_suggestions(df)
        }
        
        return analysis_result
    
    def analyze_quarterly_reports(self, quarterly_reports: List[Dict]) -> Dict:
        """
        分析季报数据 - 环比分析
        
        Args:
            quarterly_reports: 季报数据列表
            
        Returns:
            季报分析结果
        """
        if not quarterly_reports:
            return {"error": "没有可用的季报数据"}
        
        # 转换为DataFrame便于分析
        df = pd.DataFrame(quarterly_reports)
        df['report_date'] = pd.to_datetime(df['report_date'])
        df = df.sort_values('report_date')
        
        # 只分析最近4个季度
        recent_quarters = df.tail(4)
        
        analysis_result = {
            'analysis_type': 'quarterly',
            'periods_analyzed': len(recent_quarters),
            'revenue_analysis': self._analyze_revenue_quarterly(recent_quarters),
            'profit_analysis': self._analyze_profit_quarterly(recent_quarters),
            'cash_flow_analysis': self._analyze_cash_flow_quarterly(recent_quarters),
            'gross_margin_analysis': self._analyze_gross_margin_quarterly(recent_quarters),
            'product_analysis': self._analyze_products_quarterly(recent_quarters),
            'contract_liabilities_analysis': self._analyze_contract_liabilities_quarterly(recent_quarters),
            'inventory_analysis': self._analyze_inventory_quarterly(recent_quarters),
            'quarterly_trend': self._analyze_quarterly_trend(recent_quarters),
            'seasonal_patterns': self._analyze_seasonal_patterns(df),
            'investment_suggestions': self._generate_quarterly_suggestions(recent_quarters)
        }
        
        return analysis_result
    
    def _analyze_revenue(self, df: pd.DataFrame) -> Dict:
        """分析营业收入"""
        analysis = {}
        
        if len(df) >= 2:
            # 同比分析
            current_revenue = df.iloc[-1]['revenue']
            previous_revenue = df.iloc[-2]['revenue']
            yoy_growth = (current_revenue - previous_revenue) / previous_revenue * 100
            
            analysis['current_revenue'] = current_revenue
            analysis['yoy_growth'] = round(yoy_growth, 2)
            analysis['revenue_trend'] = '增长' if yoy_growth > 0 else '下降'
            
            # 历史趋势
            revenue_trend = df['revenue'].pct_change().dropna()
            analysis['avg_growth_rate'] = round(revenue_trend.mean() * 100, 2)
            analysis['growth_stability'] = '稳定' if revenue_trend.std() < 0.1 else '波动'
            
            # 多期时间序列（供前端图表使用）
            analysis['historical_revenues'] = [round(float(v), 2) for v in df['revenue'].tolist()]
            analysis['historical_dates'] = [str(d)[:10] if hasattr(d, 'strftime') else str(d) for d in df['report_date'].tolist()]
        
        return analysis
    
    def _analyze_revenue_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度营业收入"""
        analysis = {}
        
        if len(df) >= 2:
            # 环比分析
            qoq_growths = []
            for i in range(1, len(df)):
                current = df.iloc[i]['revenue']
                previous = df.iloc[i-1]['revenue']
                if previous > 0:
                    growth = (current - previous) / previous * 100
                    qoq_growths.append(growth)
            
            analysis['current_quarter_revenue'] = df.iloc[-1]['revenue']
            analysis['qoq_growth_rates'] = [round(g, 2) for g in qoq_growths]
            analysis['avg_qoq_growth'] = round(np.mean(qoq_growths), 2) if qoq_growths else 0
            # 多期季度数据（供前端图表使用）
            analysis['quarterly_revenues'] = [round(float(v), 2) for v in df['revenue'].tolist()]
            analysis['quarterly_dates'] = [str(d)[:10] if hasattr(d, 'strftime') else str(d) for d in df['report_date'].tolist()]
        
        return analysis
    
    def _analyze_profit(self, df: pd.DataFrame) -> Dict:
        """分析净利润"""
        analysis = {}
        
        if len(df) >= 2:
            current_profit = df.iloc[-1]['net_profit']
            previous_profit = df.iloc[-2]['net_profit']
            yoy_growth = (current_profit - previous_profit) / abs(previous_profit) * 100
            
            analysis['current_profit'] = current_profit
            analysis['yoy_growth'] = round(yoy_growth, 2)
            analysis['profit_margin'] = round(current_profit / df.iloc[-1]['revenue'] * 100, 2) if df.iloc[-1]['revenue'] > 0 else 0
            analysis['profit_quality'] = '优质' if yoy_growth > 10 else '一般'
            
            # 多期时间序列（供前端图表使用）
            analysis['historical_profits'] = [round(float(v), 2) for v in df['net_profit'].tolist()]
        
        return analysis
    
    def _analyze_profit_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度净利润"""
        analysis = {}
        
        if len(df) >= 2:
            qoq_growths = []
            profit_margins = []
            
            for i in range(len(df)):
                profit = df.iloc[i]['net_profit']
                revenue = df.iloc[i]['revenue']
                if revenue > 0:
                    margin = profit / revenue * 100
                    profit_margins.append(margin)
                
                if i > 0:
                    previous_profit = df.iloc[i-1]['net_profit']
                    if abs(previous_profit) > 0:
                        growth = (profit - previous_profit) / abs(previous_profit) * 100
                        qoq_growths.append(growth)
            
            analysis['profit_margins'] = [round(m, 2) for m in profit_margins]
            analysis['qoq_growth_rates'] = [round(g, 2) for g in qoq_growths]
        
        return analysis
    
    def _analyze_cash_flow(self, df: pd.DataFrame) -> Dict:
        """分析现金流"""
        analysis = {}
        
        if len(df) >= 2:
            current_cash = df.iloc[-1]['cash_flow']
            previous_cash = df.iloc[-2]['cash_flow']
            
            analysis['current_cash_flow'] = current_cash
            analysis['yoy_growth'] = round((current_cash - previous_cash) / abs(previous_cash) * 100, 2) if abs(previous_cash) > 0 else 0
            analysis['cash_flow_health'] = '健康' if current_cash > 0 else '紧张'
        
        return analysis
    
    def _analyze_cash_flow_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度现金流"""
        analysis = {}
        
        if len(df) >= 2:
            cash_flows = df['cash_flow'].tolist()
            analysis['quarterly_cash_flows'] = [round(cf, 2) for cf in cash_flows]
            analysis['cash_flow_stability'] = '稳定' if np.std(cash_flows) < np.mean(cash_flows) * 0.3 else '波动'
        
        return analysis
    
    def _analyze_gross_margin(self, df: pd.DataFrame) -> Dict:
        """分析毛利率"""
        analysis = {}
        
        if len(df) >= 2:
            margins = df['gross_margin'].tolist()
            analysis['current_margin'] = round(margins[-1], 2)
            analysis['margin_trend'] = '上升' if margins[-1] > margins[-2] else '下降'
            analysis['avg_margin'] = round(np.mean(margins), 2)
            analysis['margin_stability'] = '稳定' if np.std(margins) < 5 else '波动'
            
            # 多期时间序列（供前端图表使用）
            analysis['historical_margins'] = [round(float(v), 2) for v in margins]
        
        return analysis
    
    def _analyze_gross_margin_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度毛利率"""
        analysis = {}
        
        margins = df['gross_margin'].tolist()
        analysis['quarterly_margins'] = [round(m, 2) for m in margins]
        analysis['seasonal_variation'] = '明显' if max(margins) - min(margins) > 10 else '平稳'
        
        return analysis
    
    def _analyze_products(self, df: pd.DataFrame) -> Dict:
        """
        分析主营业务构成（需 df 含 'main_business_data' 列，或由外部传入）
        如无详细产品数据则返回占位信息
        """
        analysis = {}
        analysis['product_analysis'] = "需要具体产品数据"
        analysis['capacity_utilization'] = "需要具体产能数据"
        return analysis

    def analyze_main_business(self, main_business_df: 'pd.DataFrame') -> Dict:
        """
        分析主营业务构成（来自 FinancialReportCrawler.get_main_business）

        Args:
            main_business_df: 包含 end_date / bz_item / bz_sales / bz_profit / bz_cost 的 DataFrame

        Returns:
            主营业务分析结果
        """
        analysis = {}
        if main_business_df is None or main_business_df.empty:
            return {'error': '无主营业务数据'}

        df = main_business_df.copy()
        df['end_date'] = pd.to_datetime(df['end_date'])

        # 取最新报告期
        latest_date = df['end_date'].max()
        latest = df[df['end_date'] == latest_date].copy()

        # 去重（同一期可能因 update_flag 存在重复）
        latest = latest.drop_duplicates(subset=['bz_item'])

        total_sales = latest['bz_sales'].sum()
        analysis['latest_period'] = str(latest_date)[:10]
        analysis['total_sales'] = round(float(total_sales), 2)

        # 各产品占比
        items = []
        for _, row in latest.iterrows():
            sales = float(row.get('bz_sales') or 0)
            profit = float(row.get('bz_profit') or 0)
            cost = float(row.get('bz_cost') or 0)
            gross = round((profit / sales * 100), 2) if sales > 0 else 0
            items.append({
                'name': row['bz_item'],
                'sales': round(sales, 2),
                'profit': round(profit, 2),
                'cost': round(cost, 2),
                'gross_margin_pct': gross,
                'sales_share_pct': round(sales / total_sales * 100, 2) if total_sales > 0 else 0
            })
        items.sort(key=lambda x: x['sales'], reverse=True)
        analysis['products'] = items

        # 主要产品同比变化（对比上一报告期）
        periods = sorted(df['end_date'].unique(), reverse=True)
        if len(periods) >= 2:
            prev_date = periods[1]
            prev = df[df['end_date'] == prev_date].drop_duplicates(subset=['bz_item'])
            yoy_changes = []
            for item in items:
                prev_row = prev[prev['bz_item'] == item['name']]
                if not prev_row.empty:
                    prev_sales = float(prev_row.iloc[0].get('bz_sales') or 0)
                    if prev_sales > 0:
                        chg = round((item['sales'] - prev_sales) / prev_sales * 100, 2)
                        yoy_changes.append({'name': item['name'], 'yoy_sales_pct': chg})
            analysis['yoy_changes'] = yoy_changes

        return analysis

    def _analyze_products_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度产品数据"""
        return self._analyze_products(df)
    
    def _analyze_contract_liabilities(self, df: pd.DataFrame) -> Dict:
        """
        分析合同负债（预收款）
        合同负债代表客户已预付但尚未交付的收入，增长说明订单景气度高
        """
        analysis = {}

        if 'contract_liabilities' not in df.columns:
            return analysis

        liabilities = df['contract_liabilities'].tolist()
        periods = df['report_date'].astype(str).tolist()

        # 历史序列（只保留非零值）
        history = [
            {'period': p[:7], 'value': round(v, 2)}
            for p, v in zip(periods, liabilities)
        ]
        analysis['history'] = history
        analysis['current_liabilities'] = liabilities[-1]

        if len(liabilities) >= 2:
            prev = liabilities[-2]
            curr = liabilities[-1]
            analysis['growth_rate'] = round((curr - prev) / abs(prev) * 100, 2) if abs(prev) > 0 else 0

            # 计算历史最大、最小值
            valid = [v for v in liabilities if v > 0]
            if valid:
                analysis['max_value'] = round(max(valid), 2)
                analysis['min_value'] = round(min(valid), 2)

            # 连续增长期数
            grow_count = 0
            for i in range(len(liabilities) - 1, 0, -1):
                if liabilities[i] > liabilities[i - 1]:
                    grow_count += 1
                else:
                    break
            analysis['consecutive_growth_periods'] = grow_count

            # 趋势信号
            if grow_count >= 2:
                analysis['future_revenue_indicator'] = '持续扩张，订单景气'
            elif curr > prev:
                analysis['future_revenue_indicator'] = '积极，预示收入增长'
            elif curr == 0 and prev == 0:
                analysis['future_revenue_indicator'] = '无预收款（非预收款模式）'
            else:
                analysis['future_revenue_indicator'] = '谨慎，预收款下降'

        return analysis

    def _analyze_contract_liabilities_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度合同负债"""
        return self._analyze_contract_liabilities(df)

    def _analyze_inventory(self, df: pd.DataFrame) -> Dict:
        """
        分析库存（存货）对比
        库存增速 vs 营收增速对比，判断产销是否匹配：
          - 库存增速 >> 营收增速：积压风险
          - 库存增速 << 营收增速：产能紧张，供不应求（利好）
          - 库存增速 ≈ 营收增速：健康匹配
        """
        analysis = {}

        if 'inventories' not in df.columns:
            return analysis

        inventories = df['inventories'].tolist()
        revenues = df['revenue'].tolist()
        periods = df['report_date'].astype(str).tolist()

        # 历史库存序列
        analysis['history'] = [
            {'period': p[:7], 'value': round(v, 2)}
            for p, v in zip(periods, inventories)
        ]
        analysis['current_inventory'] = inventories[-1]

        if len(inventories) >= 2:
            prev_inv = inventories[-2]
            curr_inv = inventories[-1]
            prev_rev = revenues[-2]
            curr_rev = revenues[-1]

            inv_growth = round((curr_inv - prev_inv) / abs(prev_inv) * 100, 2) if abs(prev_inv) > 0 else 0
            rev_growth = round((curr_rev - prev_rev) / abs(prev_rev) * 100, 2) if abs(prev_rev) > 0 else 0

            analysis['inventory_growth_rate'] = inv_growth
            analysis['revenue_growth_rate'] = rev_growth
            analysis['inv_to_rev_ratio'] = round(curr_inv / curr_rev * 100, 2) if curr_rev > 0 else 0  # 库存/营收

            # 存货周转率
            if 'inv_turn' in df.columns:
                turns = df['inv_turn'].tolist()
                analysis['inv_turn_current'] = round(turns[-1], 2) if turns[-1] else 0
                analysis['inv_turn_trend'] = '加速' if len(turns) >= 2 and turns[-1] > turns[-2] else '减缓'

            # 产销匹配信号
            diff = inv_growth - rev_growth
            if curr_inv == 0:
                analysis['signal'] = '无库存数据（可能为轻资产/服务业）'
            elif diff > 15:
                analysis['signal'] = '库存积压风险（库存增速显著高于收入）'
            elif diff < -15:
                analysis['signal'] = '供不应求（库存增速显著低于收入增速）'
            else:
                analysis['signal'] = '产销基本匹配'

            # 连续增长期数
            grow_count = 0
            for i in range(len(inventories) - 1, 0, -1):
                if inventories[i] > inventories[i - 1]:
                    grow_count += 1
                else:
                    break
            analysis['consecutive_growth_periods'] = grow_count

        return analysis

    def _analyze_inventory_quarterly(self, df: pd.DataFrame) -> Dict:
        """分析季度库存"""
        return self._analyze_inventory(df)
    
    def _analyze_valuation_indicators(self, df: pd.DataFrame) -> Dict:
        """
        分析估值与盈利能力指标（ROE / ROA / 资产负债率）
        需要 df 含 roe / roa / debt_to_assets / total_assets / total_liab 字段
        """
        analysis = {}
        last = df.iloc[-1]

        for field in ('roe', 'roa', 'debt_to_assets', 'total_assets', 'total_liab'):
            val = last.get(field, 0)
            analysis[field] = round(float(val), 4) if val and not pd.isna(val) else 0

        # ROE 趋势
        if 'roe' in df.columns and len(df) >= 2:
            roe_list = df['roe'].dropna().tolist()
            if len(roe_list) >= 2:
                analysis['roe_trend'] = '上升' if roe_list[-1] > roe_list[-2] else '下降'
                analysis['avg_roe'] = round(float(np.mean(roe_list)), 2)

        # 评级
        roe_val = analysis.get('roe', 0)
        analysis['profitability_grade'] = '优秀' if roe_val > 20 else '良好' if roe_val > 10 else '一般'

        return analysis

    def _analyze_overall_trend(self, df: pd.DataFrame) -> Dict:
        """分析整体趋势（综合评分）"""
        trend = {}

        scores = []

        # 收入增长得分
        if len(df) >= 2:
            revenue_growth = (df.iloc[-1]['revenue'] - df.iloc[-2]['revenue']) / df.iloc[-2]['revenue']
            scores.append(10 if revenue_growth > 0.1 else 5 if revenue_growth > 0 else 0)

        # 利润率得分
        if df.iloc[-1]['revenue'] > 0:
            profit_margin = df.iloc[-1]['net_profit'] / df.iloc[-1]['revenue']
            scores.append(10 if profit_margin > 0.15 else 5 if profit_margin > 0.05 else 0)

        # 现金流得分
        scores.append(10 if df.iloc[-1]['cash_flow'] > 0 else 0)

        # ROE 得分（有该字段时）
        roe = df.iloc[-1].get('roe', None)
        if roe is not None and not pd.isna(roe):
            scores.append(10 if float(roe) > 20 else 5 if float(roe) > 10 else 0)

        trend['composite_score'] = round(np.mean(scores), 1) if scores else 0
        trend['investment_grade'] = '优秀' if trend['composite_score'] >= 8 else '良好' if trend['composite_score'] >= 5 else '一般'

        return trend
    
    def _analyze_quarterly_trend(self, df: pd.DataFrame) -> Dict:
        """分析季度趋势"""
        trend = {}
        
        # 季度连续性分析
        revenues = df['revenue'].tolist()
        profits = df['net_profit'].tolist()
        
        trend['revenue_continuity'] = '连续增长' if all(revenues[i] > revenues[i-1] for i in range(1, len(revenues))) else '波动'
        trend['profit_continuity'] = '连续盈利' if all(p > 0 for p in profits) else '波动盈利'
        
        return trend
    
    def _analyze_seasonal_patterns(self, df: pd.DataFrame) -> Dict:
        """分析季节性模式"""
        # 这里可以实现季节性分析逻辑
        return {'seasonal_analysis': '需要更多历史数据'}
    
    def _generate_investment_suggestions(self, df: pd.DataFrame) -> List[str]:
        """生成投资建议"""
        suggestions = []
        
        if len(df) < 2:
            return ["数据不足，建议观望"]
        
        # 基于财务指标生成建议
        revenue_growth = (df.iloc[-1]['revenue'] - df.iloc[-2]['revenue']) / df.iloc[-2]['revenue']
        profit_margin = df.iloc[-1]['net_profit'] / df.iloc[-1]['revenue'] if df.iloc[-1]['revenue'] > 0 else 0
        
        if revenue_growth > 0.1 and profit_margin > 0.1:
            suggestions.append("财务表现优秀，建议重点关注")
        elif revenue_growth > 0 and profit_margin > 0.05:
            suggestions.append("财务稳健，可以考虑配置")
        else:
            suggestions.append("财务表现一般，建议谨慎投资")
        
        if df.iloc[-1]['cash_flow'] < 0:
            suggestions.append("现金流紧张，注意风险")
        
        return suggestions
    
    def _generate_quarterly_suggestions(self, df: pd.DataFrame) -> List[str]:
        """生成季度投资建议"""
        suggestions = []
        
        # 季度连续性建议
        revenues = df['revenue'].tolist()
        if all(revenues[i] > revenues[i-1] for i in range(1, len(revenues))):
            suggestions.append("季度收入连续增长，趋势向好")
        
        # 季节性建议
        suggestions.append("关注下一季度业绩预期")
        
        return suggestions


