#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能命令行接口模块
"""

import argparse
import sys
import os
import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from api_client import APIClient, APIError
from data_processor import DataProcessor
from config import get_config


class ResearchReportCLI:
    """研报搜索命令行接口类"""
    
    def __init__(self):
        """初始化CLI"""
        self.config = get_config()
        self.config.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        self.api_client = None
        self.data_processor = None
    
    def initialize(self, config_file: Optional[str] = None) -> None:
        """初始化组件"""
        try:
            self.api_client = APIClient(config_file)
            self.data_processor = DataProcessor(config_file)
            self.logger.info("CLI初始化完成")
        except Exception as e:
            self.logger.error(f"CLI初始化失败: {e}")
            raise
    
    def parse_arguments(self) -> argparse.Namespace:
        """解析命令行参数"""
        parser = argparse.ArgumentParser(
            description="研报搜索技能 - 搜索和分析财经研究报告",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用示例:
  # 基本搜索
  python research_report_search.py -q "人工智能行业研究报告"
  
  # 限制结果数量
  python research_report_search.py -q "芯片行业" -l 5
  
  # 导出为CSV格式
  python research_report_search.py -q "新能源汽车" -o results.csv -f csv
  
  # 批量处理
  python research_report_search.py -i queries.txt -o ./results -f json
  
  # 时间范围搜索
  python research_report_search.py -q "医药行业" --date-from "2024-01-01" --date-to "2024-03-31"
  
  # 获取帮助
  python research_report_search.py -h
            """
        )
        
        # 基本搜索参数
        parser.add_argument(
            "-q", "--query",
            help="搜索关键词（支持中文）",
            type=str
        )
        
        parser.add_argument(
            "-o", "--output",
            help="输出文件路径",
            type=str
        )
        
        parser.add_argument(
            "-f", "--format",
            help="输出格式（csv, json, text, markdown）",
            choices=["csv", "json", "text", "markdown"],
            default="text"
        )
        
        parser.add_argument(
            "-l", "--limit",
            help="结果数量限制",
            type=int,
            default=10
        )
        
        # 批量处理参数
        parser.add_argument(
            "-i", "--input",
            help="输入文件路径（支持批量查询）",
            type=str
        )
        
        parser.add_argument(
            "--input-format",
            help="输入文件格式（txt, csv, json）",
            choices=["txt", "csv", "json"],
            default="txt"
        )
        
        parser.add_argument(
            "--output-dir",
            help="输出目录（批量处理时使用）",
            type=str
        )
        
        # 过滤与排序参数
        parser.add_argument(
            "--date-from",
            help="开始日期（YYYY-MM-DD）",
            type=str
        )
        
        parser.add_argument(
            "--date-to",
            help="结束日期（YYYY-MM-DD）",
            type=str
        )
        
        parser.add_argument(
            "-d", "--days",
            help="最近N天",
            type=int
        )
        
        parser.add_argument(
            "--sort-by",
            help="排序字段",
            choices=["date", "relevance"],
            default="date"
        )
        
        parser.add_argument(
            "--sort-order",
            help="排序顺序",
            choices=["asc", "desc"],
            default="desc"
        )
        
        # 其他参数
        parser.add_argument(
            "-v", "--verbose",
            help="详细输出模式",
            action="store_true"
        )
        
        parser.add_argument(
            "--debug",
            help="调试模式",
            action="store_true"
        )
        
        parser.add_argument(
            "--config",
            help="配置文件路径",
            type=str
        )
        
        parser.add_argument(
            "--test",
            help="测试API连接",
            action="store_true"
        )
        
        return parser.parse_args()
    
    def load_queries_from_file(self, filepath: str, file_format: str = "txt") -> List[str]:
        """从文件加载查询"""
        try:
            queries = []
            
            if file_format == "txt":
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            queries.append(line)
            
            elif file_format == "csv":
                import pandas as pd
                df = pd.read_csv(filepath)
                if 'query' in df.columns:
                    queries = df['query'].dropna().tolist()
                else:
                    # 使用第一列
                    queries = df.iloc[:, 0].dropna().tolist()
            
            elif file_format == "json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        queries = [str(item) for item in data if item]
                    elif isinstance(data, dict) and 'queries' in data:
                        queries = [str(q) for q in data['queries'] if q]
            
            self.logger.info(f"从文件加载 {len(queries)} 个查询: {filepath}")
            return queries
            
        except Exception as e:
            self.logger.error(f"加载查询文件失败 {filepath}: {e}")
            raise
    
    def process_single_query(self, args: argparse.Namespace) -> Dict[str, Any]:
        """处理单个查询"""
        result = {
            "query": args.query,
            "success": False,
            "articles": [],
            "error": None
        }
        
        try:
            # 搜索研究报告
            self.logger.info(f"搜索研究报告: {args.query}")
            response = self.api_client.search_reports(args.query, args.limit)
            
            # 检查是否为错误响应
            if isinstance(response, dict) and "error" in response:
                # 应用层可以选择性展示关键错误信息
                error_type = response.get("error", "unknown")
                status_code = response.get("status_code", 0)
                raw_response = response.get("raw_response", "")
                
                # 对于常见错误（如401），只显示raw_response
                if status_code == 401 and raw_response:
                    print(f"\n{'=' * 60}")
                    print(f"API错误 (状态码: {status_code}):")
                    print(f"{'=' * 60}")
                    print(raw_response)
                    print(f"{'=' * 60}")
                else:
                    # 其他错误显示完整信息
                    print(f"\n{'=' * 60}")
                    print(f"API错误响应:")
                    print(f"{'=' * 60}")
                    print(json.dumps(response, indent=2, ensure_ascii=False))
                    print(f"{'=' * 60}")
                
                result["error"] = response.get("error", "unknown_error")
                result["status_code"] = status_code
                return result
            
            # 从API响应中提取文章列表
            articles = []
            if isinstance(response, dict):
                # 优先使用 data 字段，兼容 result 字段
                if "data" in response:
                    articles = response["data"]
                    result["total"] = response.get("total", len(articles))
                elif "result" in response:
                    articles = response["result"]
                    result["total"] = response.get("total", len(articles))
            elif isinstance(response, list):
                articles = response
            
            # 数据处理
            if articles:
                # 按日期过滤
                if args.date_from or args.date_to:
                    articles = self.data_processor.filter_by_date(
                        articles, args.date_from, args.date_to
                    )
                
                # 按最近N天过滤
                if args.days:
                    articles = self.data_processor.filter_by_days(articles, args.days)
                
                # 排序
                articles = self.data_processor.sort_articles(
                    articles, args.sort_by, args.sort_order
                )
                
                # 提取关键信息
                articles = self.data_processor.extract_key_info(articles)
            
            result["articles"] = articles
            result["success"] = True
            result["count"] = len(articles)
            
            self.logger.info(f"搜索完成: 找到 {len(articles)} 篇研究报告")
            
        except APIError as e:
            result["error"] = str(e)
            self.logger.error(f"API错误: {e}")
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"处理查询失败: {e}")
        
        return result
    
    def process_batch_queries(self, args: argparse.Namespace) -> Dict[str, Any]:
        """处理批量查询"""
        result = {
            "success": False,
            "queries": {},
            "total_articles": 0,
            "error": None
        }
        
        try:
            # 加载查询
            queries = self.load_queries_from_file(args.input, args.input_format)
            
            if not queries:
                result["error"] = "没有找到有效的查询"
                return result
            
            # 批量搜索
            self.logger.info(f"批量处理 {len(queries)} 个查询")
            batch_results = self.api_client.batch_search(queries, args.limit)
            
            # 处理每个查询的结果
            processed_results = {}
            total_articles = 0
            
            for query, response in batch_results.items():
                # 从API响应中提取文章列表
                articles = []
                if isinstance(response, dict):
                    # 优先使用 data 字段，兼容 result 字段
                    if "data" in response:
                        articles = response["data"]
                    elif "result" in response:
                        articles = response["result"]
                elif isinstance(response, list):
                    articles = response
                
                if articles:
                    # 数据处理
                    if args.date_from or args.date_to:
                        articles = self.data_processor.filter_by_date(
                            articles, args.date_from, args.date_to
                        )
                    
                    if args.days:
                        articles = self.data_processor.filter_by_days(articles, args.days)
                    
                    articles = self.data_processor.sort_articles(
                        articles, args.sort_by, args.sort_order
                    )
                    
                    articles = self.data_processor.extract_key_info(articles)
                
                processed_results[query] = {
                    "articles": articles,
                    "count": len(articles)
                }
                total_articles += len(articles)
            
            result["queries"] = processed_results
            result["total_articles"] = total_articles
            result["success"] = True
            
            self.logger.info(f"批量处理完成: {len(queries)} 个查询, 共 {total_articles} 篇研究报告")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"批量处理失败: {e}")
        
        return result
    
    def save_results(self, result: Dict[str, Any], args: argparse.Namespace) -> None:
        """保存结果"""
        try:
            if not result.get("success"):
                self.logger.warning("结果不成功，跳过保存")
                return
            
            output_format = args.format.lower()
            
            # 单个查询结果
            if "query" in result:
                articles = result.get("articles", [])
                
                if not articles:
                    self.logger.warning("没有研究报告可保存")
                    return
                
                if args.output:
                    output_path = args.output
                    
                    if output_format == "csv":
                        self.data_processor.save_to_csv(articles, output_path)
                    elif output_format == "json":
                        self.data_processor.save_to_json(articles, output_path)
                    elif output_format == "markdown":
                        self.data_processor.save_to_markdown(articles, output_path)
                    elif output_format == "text":
                        self._save_to_text(articles, output_path)
                    else:
                        self.logger.error(f"不支持的输出格式: {output_format}")
                
                else:
                    # 输出到控制台
                    self._print_to_console(articles, output_format)
            
            # 批量查询结果
            elif "queries" in result:
                if args.output_dir:
                    output_dir = Path(args.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    for query, query_result in result["queries"].items():
                        articles = query_result.get("articles", [])
                        
                        if articles:
                            # 创建安全的文件名
                            safe_query = "".join(c if c.isalnum() else "_" for c in query)
                            if len(safe_query) > 50:
                                safe_query = safe_query[:50]
                            
                            if output_format == "csv":
                                output_path = output_dir / f"{safe_query}.csv"
                                self.data_processor.save_to_csv(articles, str(output_path))
                            elif output_format == "json":
                                output_path = output_dir / f"{safe_query}.json"
                                self.data_processor.save_to_json(articles, str(output_path))
                            elif output_format == "markdown":
                                output_path = output_dir / f"{safe_query}.md"
                                self.data_processor.save_to_markdown(articles, str(output_path))
                            elif output_format == "text":
                                output_path = output_dir / f"{safe_query}.txt"
                                self._save_to_text(articles, str(output_path))
                    
                    # 保存汇总文件
                    summary_path = output_dir / f"summary.{output_format}"
                    if output_format == "json":
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
                    
                    self.logger.info(f"批量结果保存到目录: {output_dir}")
                
                else:
                    # 输出汇总信息到控制台
                    self._print_batch_summary(result)
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
            raise
    
    def _save_to_text(self, articles: List[Dict[str, Any]], filepath: str) -> None:
        """保存到文本文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"研究报告搜索结果\n")
            f.write(f"数据来源: 同花顺问财财经资讯搜索接口\n")
            f.write(f"搜索时间: {self._get_current_time()}\n")
            f.write(f"报告数量: {len(articles)} 篇\n")
            f.write("=" * 80 + "\n\n")
            
            for i, article in enumerate(articles, 1):
                f.write(f"{i}. {article.get('title', '无标题')}\n")
                f.write(f"   发布时间: {article.get('publish_date', '未知')}\n")
                f.write(f"   原文链接: {article.get('url', '')}\n")
                
                summary = article.get("summary", "")
                if summary:
                    f.write(f"   摘要: {summary[:200]}...\n")
                
                # 提取的信息
                if "extracted_info" in article:
                    extracted = article["extracted_info"]
                    info_parts = []
                    
                    if extracted.get("rating"):
                        info_parts.append(f"评级: {extracted['rating']}")
                    if extracted.get("target_price"):
                        info_parts.append(f"目标价: {extracted['target_price']}元")
                    if extracted.get("industry"):
                        info_parts.append(f"行业: {extracted['industry']}")
                    
                    if info_parts:
                        f.write(f"   提取信息: {', '.join(info_parts)}\n")
                
                f.write("\n")
        
        self.logger.info(f"保存到文本文件: {len(articles)} 篇研究报告 -> {filepath}")
    
    def _print_to_console(self, articles: List[Dict[str, Any]], output_format: str) -> None:
        """输出到控制台"""
        if output_format == "text":
            print(f"\n研究报告搜索结果")
            print(f"数据来源: 同花顺问财财经资讯搜索接口")
            print(f"搜索时间: {self._get_current_time()}")
            print(f"报告数量: {len(articles)} 篇")
            print("=" * 80)
            
            for i, article in enumerate(articles, 1):
                print(f"\n{i}. {article.get('title', '无标题')}")
                print(f"   发布时间: {article.get('publish_date', '未知')}")
                print(f"   原文链接: {article.get('url', '')}")
                
                summary = article.get("summary", "")
                if summary:
                    print(f"   摘要: {summary[:150]}...")
                
                # 提取的信息
                if "extracted_info" in article:
                    extracted = article["extracted_info"]
                    info_parts = []
                    
                    if extracted.get("rating"):
                        info_parts.append(f"评级: {extracted['rating']}")
                    if extracted.get("target_price"):
                        info_parts.append(f"目标价: {extracted['target_price']}元")
                    if extracted.get("industry"):
                        info_parts.append(f"行业: {extracted['industry']}")
                    
                    if info_parts:
                        print(f"   提取信息: {', '.join(info_parts)}")
            
            print("\n" + "=" * 80)
            
        elif output_format == "json":
            print(json.dumps(articles, ensure_ascii=False, indent=2))
        
        else:
            # 默认简单输出
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article.get('title', '无标题')}")
                if i >= 10:  # 只显示前10条
                    print(f"... 还有 {len(articles) - 10} 条结果")
                    break
    
    def _print_batch_summary(self, result: Dict[str, Any]) -> None:
        """输出批量处理摘要"""
        print(f"\n批量处理结果摘要")
        print(f"数据来源: 同花顺问财财经资讯搜索接口")
        print(f"处理时间: {self._get_current_time()}")
        print(f"查询数量: {len(result.get('queries', {}))}")
        print(f"总报告数量: {result.get('total_articles', 0)}")
        print("=" * 80)
        
        for query, query_result in result.get("queries", {}).items():
            count = query_result.get("count", 0)
            print(f"  {query}: {count} 篇")
        
        print("=" * 80)
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def test_connection(self) -> bool:
        """测试API连接"""
        try:
            self.logger.info("测试API连接...")
            success = self.api_client.test_connection()
            
            if success:
                print("API连接测试成功")
                self.logger.info("API连接测试成功")
            else:
                print("API连接测试失败")
                self.logger.warning("API连接测试失败")
            
            return success
            
        except Exception as e:
            print(f"API连接测试失败: {e}")
            self.logger.error(f"API连接测试失败: {e}")
            return False
    
    def run(self) -> int:
        """运行CLI"""
        try:
            # 解析参数
            args = self.parse_arguments()
            
            # 设置日志级别
            if args.debug:
                logging.getLogger().setLevel(logging.DEBUG)
            elif args.verbose:
                logging.getLogger().setLevel(logging.INFO)
            
            # 初始化
            self.initialize(args.config)
            
            # 测试模式
            if args.test:
                return 0 if self.test_connection() else 1
            
            # 检查必要的参数
            if not args.query and not args.input:
                print("错误: 必须指定查询参数 (-q/--query) 或输入文件 (-i/--input)")
                return 1
            
            # 处理查询
            if args.input:
                # 批量处理
                result = self.process_batch_queries(args)
            else:
                # 单个查询
                result = self.process_single_query(args)
            
            # 保存结果
            if result.get("success"):
                self.save_results(result, args)
                
                # 显示成功消息
                if args.input:
                    print(f"\n批量处理完成: {result.get('total_articles', 0)} 篇研究报告")
                else:
                    print(f"\n搜索完成: {result.get('count', 0)} 篇研究报告")
                
                return 0
            else:
                print(f"\n处理失败: {result.get('error', '未知错误')}")
                return 1
            
        except KeyboardInterrupt:
            print("\n用户中断")
            return 130
        except Exception as e:
            self.logger.error(f"CLI运行失败: {e}")
            print(f"错误: {e}")
            return 1


def main():
    """主函数"""
    cli = ResearchReportCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())