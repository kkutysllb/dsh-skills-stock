#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行业分析数据模型
基于同花顺问财产业链解读技能
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class IndustryChainNode(BaseModel):
    """产业链节点"""
    node_name: str = Field(..., description="节点名称（如：上游-原材料）")
    position: str = Field(..., description="产业链位置（上游/中游/下游）")
    description: str = Field("", description="节点描述")
    key_companies: List[str] = Field(default_factory=list, description="核心公司列表")
    bargaining_power: str = Field("", description="议价能力分析")
    profit_margin: str = Field("", description="利润空间分析")
    competitive_landscape: str = Field("", description="竞争格局")


class IndustryChainAnalysis(BaseModel):
    """产业链分析结果"""
    industry_name: str = Field(..., description="行业名称")
    analysis_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d"), description="分析日期")
    
    # 产业链结构
    upstream: List[IndustryChainNode] = Field(default_factory=list, description="上游环节")
    midstream: List[IndustryChainNode] = Field(default_factory=list, description="中游环节")
    downstream: List[IndustryChainNode] = Field(default_factory=list, description="下游环节")
    
    # 核心发现
    core_companies: List[Dict] = Field(default_factory=list, description="具备长期竞争优势的核心公司")
    investment_value: str = Field("", description="中期投资价值判断")
    risk_warnings: List[str] = Field(default_factory=list, description="风险提示")
    
    # 行业动态
    market_size: str = Field("", description="市场规模")
    growth_rate: str = Field("", description="增长率")
    industry_lifecycle: str = Field("", description="行业生命周期阶段")
    
    # 政策环境
    policy_environment: str = Field("", description="政策环境分析")
    
    # 技术趋势
    technology_trends: List[str] = Field(default_factory=list, description="技术发展趋势")


class IndustryOverview(BaseModel):
    """行业概览"""
    industry_name: str = Field(..., description="行业名称")
    industry_code: str = Field("", description="行业代码")
    description: str = Field("", description="行业简介")
    total_companies: int = Field(0, description="行业内公司总数")
    market_cap: str = Field("", description="总市值")
    pe_ratio: float = Field(0, description="平均市盈率")
    pb_ratio: float = Field(0, description="平均市净率")


class StockInIndustry(BaseModel):
    """行业内个股"""
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field(..., description="股票名称")
    current_price: float = Field(0, description="当前价格")
    change_percent: float = Field(0, description="涨跌幅")
    market_cap: float = Field(0, description="市值（亿）")
    pe_ratio: float = Field(0, description="市盈率")
    position_in_chain: str = Field("", description="在产业链中的位置")


class IndustryAnalysisResult(BaseModel):
    """行业分析完整结果"""
    overview: IndustryOverview = Field(..., description="行业概览")
    chain_analysis: IndustryChainAnalysis = Field(..., description="产业链分析")
    key_stocks: List[StockInIndustry] = Field(default_factory=list, description="重点个股")
    analysis_summary: List[str] = Field(default_factory=list, description="分析摘要")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v else None
        }
