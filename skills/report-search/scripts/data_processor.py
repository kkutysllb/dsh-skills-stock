#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能数据处理模块
"""

import json
import csv
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from config import get_config


class DataProcessor:
    """数据处理类"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化数据处理类
        
        Args:
            config_file: 配置文件路径
        """
        self.config = get_config(config_file)
        
        # 设置日志
        self.config.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # 初始化关键词提取器（简单版本）
        self._init_keyword_extractor()
    
    def _init_keyword_extractor(self) -> None:
        """初始化关键词提取器（简单实现）"""
        # 行业关键词
        self.industry_keywords = [
            "人工智能", "芯片", "半导体", "新能源", "电动汽车", "医药", "医疗", "金融",
            "银行", "保险", "证券", "消费", "零售", "制造", "工业", "科技", "互联网",
            "软件", "硬件", "通信", "5G", "物联网", "云计算", "大数据", "区块链"
        ]
        
        # 报告类型关键词
        self.report_type_keywords = [
            "研究报告", "分析报告", "行业报告", "深度报告", "投资报告", "市场报告",
            "趋势报告", "前景分析", "投资建议", "评级报告", "目标价"
        ]
    
    def filter_by_date(self, articles: List[Dict[str, Any]], 
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        按日期过滤研究报告
        
        Args:
            articles: 研究报告列表
            date_from: 开始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            
        Returns:
            过滤后的研究报告列表
        """
        if not articles:
            return []
        
        filtered_articles = []
        
        try:
            # 解析日期范围
            from_date = None
            to_date = None
            
            if date_from:
                from_date = datetime.strptime(date_from, "%Y-%m-%d")
            
            if date_to:
                to_date = datetime.strptime(date_to, "%Y-%m-%d")
            
            # 过滤文章
            for article in articles:
                publish_date_str = article.get("publish_date", "")
                
                if not publish_date_str:
                    # 如果没有发布日期，默认保留
                    filtered_articles.append(article)
                    continue
                
                try:
                    # 尝试解析发布日期
                    # 格式可能是 "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD"
                    if " " in publish_date_str:
                        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d")
                    
                    # 检查是否在日期范围内
                    if from_date and publish_date < from_date:
                        continue
                    
                    if to_date and publish_date > to_date:
                        continue
                    
                    filtered_articles.append(article)
                    
                except ValueError:
                    # 日期格式解析失败，保留文章
                    filtered_articles.append(article)
            
            self.logger.info(f"按日期过滤: 从 {len(articles)} 篇过滤到 {len(filtered_articles)} 篇")
            
        except Exception as e:
            self.logger.error(f"按日期过滤失败: {e}")
            # 出错时返回原始数据
            return articles
        
        return filtered_articles
    
    def filter_by_days(self, articles: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
        """
        按最近N天过滤研究报告
        
        Args:
            articles: 研究报告列表
            days: 最近N天
            
        Returns:
            过滤后的研究报告列表
        """
        if not articles or days <= 0:
            return articles
        
        try:
            # 计算截止日期
            cutoff_date = datetime.now() - timedelta(days=days)
            
            filtered_articles = []
            for article in articles:
                publish_date_str = article.get("publish_date", "")
                
                if not publish_date_str:
                    # 如果没有发布日期，默认保留
                    filtered_articles.append(article)
                    continue
                
                try:
                    # 尝试解析发布日期
                    if " " in publish_date_str:
                        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        publish_date = datetime.strptime(publish_date_str, "%Y-%m-%d")
                    
                    # 检查是否在最近N天内
                    if publish_date >= cutoff_date:
                        filtered_articles.append(article)
                        
                except ValueError:
                    # 日期格式解析失败，保留文章
                    filtered_articles.append(article)
            
            self.logger.info(f"按最近 {days} 天过滤: 从 {len(articles)} 篇过滤到 {len(filtered_articles)} 篇")
            
            return filtered_articles
            
        except Exception as e:
            self.logger.error(f"按天数过滤失败: {e}")
            return articles
    
    def sort_articles(self, articles: List[Dict[str, Any]], 
                     sort_by: str = "date",
                     sort_order: str = "desc") -> List[Dict[str, Any]]:
        """
        排序研究报告
        
        Args:
            articles: 研究报告列表
            sort_by: 排序字段 (date, relevance)
            sort_order: 排序顺序 (asc, desc)
            
        Returns:
            排序后的研究报告列表
        """
        if not articles:
            return []
        
        try:
            # 创建可排序的副本
            sorted_articles = articles.copy()
            
            if sort_by == "date":
                # 按日期排序
                def get_date(article):
                    publish_date_str = article.get("publish_date", "")
                    if not publish_date_str:
                        return datetime.min
                    
                    try:
                        if " " in publish_date_str:
                            return datetime.strptime(publish_date_str, "%Y-%m-%d %H:%M:%S")
                        else:
                            return datetime.strptime(publish_date_str, "%Y-%m-%d")
                    except ValueError:
                        return datetime.min
                
                sorted_articles.sort(key=get_date, reverse=(sort_order == "desc"))
                
            elif sort_by == "relevance":
                # 按相关性排序（简单实现：按标题长度和关键词匹配）
                def get_relevance_score(article):
                    title = article.get("title", "").lower()
                    summary = article.get("summary", "").lower()
                    
                    score = 0
                    
                    # 标题长度（适中为好）
                    title_len = len(title)
                    if 10 <= title_len <= 50:
                        score += 1
                    
                    # 包含关键词
                    for keyword in self.industry_keywords + self.report_type_keywords:
                        if keyword in title or keyword in summary:
                            score += 2
                    
                    # 包含数字（可能表示目标价或日期）
                    if any(char.isdigit() for char in title):
                        score += 1
                    
                    return score
                
                sorted_articles.sort(key=get_relevance_score, reverse=(sort_order == "desc"))
            
            self.logger.info(f"按 {sort_by} 排序 ({sort_order}): 排序 {len(sorted_articles)} 篇研究报告")
            
            return sorted_articles
            
        except Exception as e:
            self.logger.error(f"排序失败: {e}")
            return articles
    
    def extract_key_info(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        提取关键信息
        
        Args:
            articles: 研究报告列表
            
        Returns:
            包含提取信息的研究报告列表
        """
        if not articles:
            return []
        
        processed_articles = []
        
        for article in articles:
            processed_article = article.copy()
            
            # 提取标题中的关键信息
            title = article.get("title", "")
            summary = article.get("summary", "")
            
            # 提取投资评级
            rating_keywords = ["买入", "增持", "持有", "减持", "卖出", "推荐", "谨慎推荐"]
            rating = None
            for keyword in rating_keywords:
                if keyword in title or keyword in summary:
                    rating = keyword
                    break
            
            # 提取目标价
            target_price = None
            import re
            price_patterns = [
                r"目标价\s*[:：]?\s*(\d+(?:\.\d+)?)\s*元",
                r"(\d+(?:\.\d+)?)\s*元\s*目标价",
                r"目标价\s*(\d+(?:\.\d+)?)"
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, title + " " + summary)
                if match:
                    target_price = match.group(1)
                    break
            
            # 提取行业
            industry = None
            for keyword in self.industry_keywords:
                if keyword in title or keyword in summary:
                    industry = keyword
                    break
            
            # 添加提取的信息
            processed_article["extracted_info"] = {
                "rating": rating,
                "target_price": target_price,
                "industry": industry,
                "has_analysis": any(keyword in summary for keyword in ["分析", "逻辑", "原因", "因素"])
            }
            
            processed_articles.append(processed_article)
        
        self.logger.info(f"提取关键信息: 处理 {len(processed_articles)} 篇研究报告")
        
        return processed_articles
    
    def save_to_csv(self, articles: List[Dict[str, Any]], filepath: str) -> None:
        """
        保存研究报告到CSV文件
        
        Args:
            articles: 研究报告列表
            filepath: 输出文件路径
        """
        if not articles:
            self.logger.warning("没有研究报告可保存")
            return
        
        try:
            # 准备CSV数据
            csv_data = []
            for article in articles:
                row = {
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "url": article.get("url", ""),
                    "publish_date": article.get("publish_date", "")
                }
                
                # 添加提取的信息
                if "extracted_info" in article:
                    extracted = article["extracted_info"]
                    row["rating"] = extracted.get("rating", "")
                    row["target_price"] = extracted.get("target_price", "")
                    row["industry"] = extracted.get("industry", "")
                    row["has_analysis"] = extracted.get("has_analysis", False)
                
                csv_data.append(row)
            
            # 保存到CSV
            df = pd.DataFrame(csv_data)
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            self.logger.info(f"保存到CSV: {len(articles)} 篇研究报告 -> {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存到CSV失败: {e}")
            raise
    
    def save_to_json(self, articles: List[Dict[str, Any]], filepath: str) -> None:
        """
        保存研究报告到JSON文件
        
        Args:
            articles: 研究报告列表
            filepath: 输出文件路径
        """
        if not articles:
            self.logger.warning("没有研究报告可保存")
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"保存到JSON: {len(articles)} 篇研究报告 -> {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存到JSON失败: {e}")
            raise
    
    def save_to_markdown(self, articles: List[Dict[str, Any]], filepath: str) -> None:
        """
        保存研究报告到Markdown文件
        
        Args:
            articles: 研究报告列表
            filepath: 输出文件路径
        """
        if not articles:
            self.logger.warning("没有研究报告可保存")
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# 研究报告汇总\n\n")
                f.write(f"**数据来源**: 同花顺问财财经资讯搜索接口\n\n")
                f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**报告数量**: {len(articles)} 篇\n\n")
                
                for i, article in enumerate(articles, 1):
                    f.write(f"## {i}. {article.get('title', '无标题')}\n\n")
                    
                    # 基本信息
                    f.write(f"**发布时间**: {article.get('publish_date', '未知')}\n\n")
                    f.write(f"**原文链接**: [{article.get('url', '')}]({article.get('url', '')})\n\n")
                    
                    # 摘要
                    summary = article.get("summary", "")
                    if summary:
                        f.write(f"**摘要**: {summary}\n\n")
                    
                    # 提取的信息
                    if "extracted_info" in article:
                        extracted = article["extracted_info"]
                        
                        info_lines = []
                        if extracted.get("rating"):
                            info_lines.append(f"- **投资评级**: {extracted['rating']}")
                        if extracted.get("target_price"):
                            info_lines.append(f"- **目标价**: {extracted['target_price']}元")
                        if extracted.get("industry"):
                            info_lines.append(f"- **所属行业**: {extracted['industry']}")
                        if extracted.get("has_analysis"):
                            info_lines.append(f"- **包含分析**: 是")
                        
                        if info_lines:
                            f.write("**提取信息**:\n")
                            for line in info_lines:
                                f.write(f"{line}\n")
                            f.write("\n")
                    
                    f.write("---\n\n")
            
            self.logger.info(f"保存到Markdown: {len(articles)} 篇研究报告 -> {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存到Markdown失败: {e}")
            raise
    
    def analyze_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析研究报告
        
        Args:
            articles: 研究报告列表
            
        Returns:
            分析结果
        """
        if not articles:
            return {"error": "没有研究报告可分析"}
        
        try:
            analysis = {
                "total_count": len(articles),
                "date_range": None,
                "industry_distribution": {},
                "rating_distribution": {},
                "avg_summary_length": 0,
                "analysis_coverage": 0
            }
            
            # 分析日期范围
            dates = []
            for article in articles:
                publish_date_str = article.get("publish_date", "")
                if publish_date_str:
                    try:
                        if " " in publish_date_str:
                            date = datetime.strptime(publish_date_str, "%Y-%m-%d %H:%M:%S")
                        else:
                            date = datetime.strptime(publish_date_str, "%Y-%m-%d")
                        dates.append(date)
                    except ValueError:
                        pass
            
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                analysis["date_range"] = {
                    "start": min_date.strftime("%Y-%m-%d"),
                    "end": max_date.strftime("%Y-%m-%d"),
                    "days": (max_date - min_date).days
                }
            
            # 分析行业分布
            for article in articles:
                if "extracted_info" in article:
                    industry = article["extracted_info"].get("industry")
                    if industry:
                        analysis["industry_distribution"][industry] = \
                            analysis["industry_distribution"].get(industry, 0) + 1
            
            # 分析评级分布
            for article in articles:
                if "extracted_info" in article:
                    rating = article["extracted_info"].get("rating")
                    if rating:
                        analysis["rating_distribution"][rating] = \
                            analysis["rating_distribution"].get(rating, 0) + 1
            
            # 分析摘要长度
            summary_lengths = []
            for article in articles:
                summary = article.get("summary", "")
                if summary:
                    summary_lengths.append(len(summary))
            
            if summary_lengths:
                analysis["avg_summary_length"] = sum(summary_lengths) / len(summary_lengths)
            
            # 分析分析覆盖率
            articles_with_analysis = 0
            for article in articles:
                if "extracted_info" in article:
                    if article["extracted_info"].get("has_analysis"):
                        articles_with_analysis += 1
            
            if articles:
                analysis["analysis_coverage"] = articles_with_analysis / len(articles)
            
            self.logger.info(f"分析研究报告: {len(articles)} 篇")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"分析研究报告失败: {e}")
            return {"error": f"分析失败: {str(e)}"}


if __name__ == "__main__":
    # 测试数据处理模块
    import sys
    
    # 测试数据
    test_articles = [
        {
            "title": "人工智能行业研究报告：买入评级，目标价120元",
            "summary": "本报告分析了人工智能行业的发展趋势，包括技术突破、应用场景、市场规模等方面的内容。",
            "url": "https://example.com/reports/ai-2024",
            "publish_date": "2024-01-15 09:30:00"
        },
        {
            "title": "芯片行业分析报告：增持评级",
            "summary": "报告详细介绍了芯片行业的最新发展动态和投资机会。",
            "url": "https://example.com/reports/chip-2024",
            "publish_date": "2024-01-14 14:20:00"
        },
        {
            "title": "新能源汽车行业报告",
            "summary": "分析新能源汽车行业的发展前景和投资建议。",
            "url": "https://example.com/reports/ev-2024",
            "publish_date": "2024-01-13 11:15:00"
        }
    ]
    
    try:
        processor = DataProcessor()
        
        # 测试过滤
        print("测试按日期过滤...")
        filtered = processor.filter_by_date(test_articles, date_from="2024-01-14")
        print(f"过滤后: {len(filtered)} 篇")
        
        # 测试排序
        print("\n测试排序...")
        sorted_articles = processor.sort_articles(test_articles, sort_by="date", sort_order="desc")
        print(f"排序后第一篇标题: {sorted_articles[0].get('title')}")
        
        # 测试提取关键信息
        print("\n测试提取关键信息...")
        processed = processor.extract_key_info(test_articles)
        for article in processed:
            print(f"标题: {article.get('title')}")
            print(f"评级: {article.get('extracted_info', {}).get('rating')}")
            print(f"目标价: {article.get('extracted_info', {}).get('target_price')}")
            print()
        
        # 测试分析
        print("\n测试分析...")
        analysis = processor.analyze_articles(processed)
        print(f"总数量: {analysis.get('total_count')}")
        print(f"行业分布: {analysis.get('industry_distribution')}")
        print(f"评级分布: {analysis.get('rating_distribution')}")
        
        # 测试保存
        print("\n测试保存...")
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            json_path = os.path.join(tmpdir, "test.json")
            md_path = os.path.join(tmpdir, "test.md")
            
            processor.save_to_csv(processed, csv_path)
            processor.save_to_json(processed, json_path)
            processor.save_to_markdown(processed, md_path)
            
            print(f"CSV文件大小: {os.path.getsize(csv_path)} 字节")
            print(f"JSON文件大小: {os.path.getsize(json_path)} 字节")
            print(f"Markdown文件大小: {os.path.getsize(md_path)} 字节")
            
            print("\n测试完成!")
            
    except Exception as e:
        print(f"测试失败: {e}")
        sys.exit(1)