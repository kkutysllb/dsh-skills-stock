#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能使用示例
符合iwencai-skill-creator规范
"""

import os
import sys
import json
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import APIClient, APIError
from data_processor import DataProcessor


def example_basic_search():
    """示例1: 基本搜索（响应透明传递示例）"""
    print("=" * 80)
    print("示例1: 基本搜索（响应透明传递示例）")
    print("=" * 80)
    
    try:
        # 初始化API客户端
        client = APIClient()
        
        # 搜索研究报告（注意：现在返回完整的API响应）
        query = "人工智能行业研究报告"
        response_data = client.search_reports(query)
        
        print(f"搜索关键词: {query}")
        print(f"完整API响应结构: {list(response_data.keys())}")
        
        # 从响应中提取数据（调用方决定如何处理）
        articles = response_data.get("data", [])
        print(f"找到 {len(articles)} 篇研究报告:")
        
        for i, article in enumerate(articles[:5], 1):  # 只显示前5篇
            print(f"\n{i}. {article.get('title', '无标题')}")
            print(f"   摘要: {article.get('summary', '无摘要')[:100]}...")
            print(f"   发布时间: {article.get('publish_date', '未知')}")
            print(f"   原文链接: {article.get('url', '')}")
        
        # 显示响应元数据（透明传递的一部分）
        if "metadata" in response_data:
            print(f"\n响应元数据: {response_data.get('metadata', {})}")
        
        print("\n" + "=" * 80)
        
    except APIError as e:
        print(f"API错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


def example_with_data_processing():
    """示例2: 带数据处理的搜索（CLI工具使用示例）"""
    print("\n" + "=" * 80)
    print("示例2: 带数据处理的搜索（CLI工具使用示例）")
    print("=" * 80)
    print("注意：此示例展示CLI工具的后处理功能，AI代理调用时应使用透明传递方式")
    print("=" * 80)
    
    try:
        # 初始化API客户端和数据处理
        client = APIClient()
        processor = DataProcessor()
        
        # 搜索研究报告（获取完整API响应）
        query = "芯片行业分析报告"
        response_data = client.search_reports(query)
        
        # 从响应中提取数据（CLI工具的后处理）
        articles = response_data.get("data", [])
        
        print(f"搜索关键词: {query}")
        print(f"完整API响应接收完成，提取到 {len(articles)} 篇研究报告数据")
        
        # 数据处理
        # 1. 按日期排序（最新在前）
        articles = processor.sort_articles(articles, sort_by="date", sort_order="desc")
        
        # 2. 提取关键信息
        articles = processor.extract_key_info(articles)
        
        # 3. 分析结果
        analysis = processor.analyze_articles(articles)
        
        print(f"\n分析结果:")
        print(f"  总数量: {analysis.get('total_count')}")
        print(f"  日期范围: {analysis.get('date_range', {}).get('start')} 到 {analysis.get('date_range', {}).get('end')}")
        print(f"  行业分布: {analysis.get('industry_distribution')}")
        print(f"  评级分布: {analysis.get('rating_distribution')}")
        print(f"  平均摘要长度: {analysis.get('avg_summary_length'):.1f} 字符")
        print(f"  分析覆盖率: {analysis.get('analysis_coverage'):.1%}")
        
        # 显示前3篇
        print(f"\n前3篇研究报告:")
        for i, article in enumerate(articles[:3], 1):
            print(f"\n{i}. {article.get('title', '无标题')}")
            print(f"   发布时间: {article.get('publish_date', '未知')}")
            
            extracted = article.get('extracted_info', {})
            if extracted.get('rating'):
                print(f"   投资评级: {extracted['rating']}")
            if extracted.get('target_price'):
                print(f"   目标价: {extracted['target_price']}元")
            if extracted.get('industry'):
                print(f"   所属行业: {extracted['industry']}")
        
        print("\n" + "=" * 80)
        
    except APIError as e:
        print(f"API错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


def example_save_to_files():
    """示例3: 保存到文件（CLI工具使用示例）"""
    print("\n" + "=" * 80)
    print("示例3: 保存到文件（CLI工具使用示例）")
    print("=" * 80)
    print("注意：此示例展示CLI工具的导出功能，AI代理调用时应使用透明传递方式")
    print("=" * 80)
    
    try:
        # 初始化API客户端和数据处理
        client = APIClient()
        processor = DataProcessor()
        
        # 搜索研究报告（获取完整API响应）
        query = "新能源汽车投资分析"
        response_data = client.search_reports(query)
        
        # 从响应中提取数据（CLI工具的后处理）
        articles = response_data.get("data", [])
        
        print(f"搜索关键词: {query}")
        print(f"完整API响应接收完成，提取到 {len(articles)} 篇研究报告数据")
        
        # 数据处理
        articles = processor.sort_articles(articles, sort_by="relevance", sort_order="desc")
        articles = processor.extract_key_info(articles)
        
        # 创建输出目录
        output_dir = Path("example_output")
        output_dir.mkdir(exist_ok=True)
        
        # 保存到不同格式
        # 1. 保存到CSV
        csv_path = output_dir / "research_reports.csv"
        processor.save_to_csv(articles, str(csv_path))
        print(f"  保存到CSV: {csv_path}")
        
        # 2. 保存到JSON
        json_path = output_dir / "research_reports.json"
        processor.save_to_json(articles, str(json_path))
        print(f"  保存到JSON: {json_path}")
        
        # 3. 保存到Markdown
        md_path = output_dir / "research_reports.md"
        processor.save_to_markdown(articles, str(md_path))
        print(f"  保存到Markdown: {md_path}")
        
        # 显示文件大小
        print(f"\n生成的文件:")
        for filepath in [csv_path, json_path, md_path]:
            if filepath.exists():
                size_kb = filepath.stat().st_size / 1024
                print(f"  {filepath.name}: {size_kb:.1f} KB")
        
        print("\n" + "=" * 80)
        
    except APIError as e:
        print(f"API错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


def example_batch_processing():
    """示例4: 批量处理（响应透明传递示例）"""
    print("\n" + "=" * 80)
    print("示例4: 批量处理（响应透明传递示例）")
    print("=" * 80)
    print("注意：batch_search现在返回完整的API响应字典")
    print("=" * 80)
    
    try:
        # 初始化API客户端
        client = APIClient()
        
        # 批量查询
        queries = [
            "人工智能行业趋势",
            "芯片技术发展",
            "新能源政策分析",
            "医药创新研究"
        ]
        
        print(f"批量处理 {len(queries)} 个查询:")
        
        # 批量搜索（现在返回完整的API响应字典）
        batch_results = client.batch_search(queries, limit_per_query=3)
        
        total_articles = 0
        for query, response_data in batch_results.items():
            # 从每个响应中提取数据
            articles = response_data.get("data", [])
            count = len(articles)
            total_articles += count
            print(f"  {query}: {count} 篇研究报告")
            
            # 显示每篇的标题
            for i, article in enumerate(articles[:2], 1):  # 只显示前2篇
                title = article.get('title', '无标题')
                if len(title) > 50:
                    title = title[:47] + "..."
                print(f"    {i}. {title}")
            
            if count > 2:
                print(f"    ... 还有 {count - 2} 篇")
        
        print(f"\n总计: {total_articles} 篇研究报告")
        
        print("\n" + "=" * 80)
        
    except APIError as e:
        print(f"API错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


def example_cli_usage():
    """示例5: CLI使用方式"""
    print("\n" + "=" * 80)
    print("示例5: CLI使用方式")
    print("=" * 80)
    
    print("CLI命令行使用示例:")
    print()
    print("1. 基本搜索:")
    print("   python research_report_search.py -q \"人工智能行业研究报告\"")
    print()
    print("2. 限制结果数量:")
    print("   python research_report_search.py -q \"芯片行业\" -l 5")
    print()
    print("3. 导出为CSV格式:")
    print("   python research_report_search.py -q \"新能源汽车\" -o results.csv -f csv")
    print()
    print("4. 批量处理:")
    print("   python research_report_search.py -i queries.txt -o ./results -f json")
    print()
    print("5. 时间范围搜索:")
    print("   python research_report_search.py -q \"医药行业\" --date-from \"2024-01-01\" --date-to \"2024-03-31\"")
    print()
    print("6. 获取帮助:")
    print("   python research_report_search.py -h")
    print()
    print("7. 测试API连接:")
    print("   python research_report_search.py --test")
    
    print("\n" + "=" * 80)


def example_curl_usage():
    """示例6: curl使用方式"""
    print("\n" + "=" * 80)
    print("示例6: curl使用方式")
    print("=" * 80)
    
    print("curl命令行使用示例:")
    print()
    print("1. 基本搜索 (Unix/Linux/macOS):")
    print("   curl -X POST \"https://openapi.iwencai.com/v1/comprehensive/search\" \\")
    print("     -H \"Content-Type: application/json\" \\")
    print("     -H \"Authorization: Bearer $IWENCAI_API_KEY\" \\")
    print("     -H \"X-Claw-Call-Type: normal\" \\")
    print("     -H \"X-Claw-Skill-Id: report-search\" \\")
    print("     -H \"X-Claw-Skill-Version: 2.0.0\" \\")
    print("     -H \"X-Claw-Plugin-Id: none\" \\")
    print("     -H \"X-Claw-Plugin-Version: none\" \\")
    print("     -H \"X-Claw-Trace-Id: $(python -c 'import secrets; print(secrets.token_hex(32))')\" \\")
    print("     -d '{")
    print("       \"channels\": [\"report\"],")
    print("       \"app_id\": \"AIME_SKILL\",")
    print("       \"query\": \"人工智能行业研究报告\"")
    print("     }'")
    print()
    print("2. Windows PowerShell:")
    print("   $traceId = python -c \"import secrets; print(secrets.token_hex(32))\"")
    print("   curl.exe -X POST \"https://openapi.iwencai.com/v1/comprehensive/search\" \\")
    print("     -H \"Content-Type: application/json\" \\")
    print("     -H \"Authorization: Bearer $env:IWENCAI_API_KEY\" \\")
    print("     -H \"X-Claw-Call-Type: normal\" \\")
    print("     -H \"X-Claw-Skill-Id: report-search\" \\")
    print("     -H \"X-Claw-Skill-Version: 2.0.0\" \\")
    print("     -H \"X-Claw-Plugin-Id: none\" \\")
    print("     -H \"X-Claw-Plugin-Version: none\" \\")
    print("     -H \"X-Claw-Trace-Id: $traceId\" \\")
    print("     -d '{")
    print("       \"channels\": [\"report\"],")
    print("       \"app_id\": \"AIME_SKILL\",")
    print("       \"query\": \"人工智能行业研究报告\"")
    print("     }'")
    print()
    print("注意: 每次请求都会生成新的64字符Trace ID")
    
    print("\n" + "=" * 80)


def main():
    """主函数"""
    print("研报搜索技能使用示例")
    print("版本: 2.0.0")
    print("规范: 符合iwencai-skill-creator要求")
    print("=" * 80)
    
    # 检查API Key
    if not os.getenv("IWENCAI_API_KEY"):
        print("警告: 请先设置环境变量 IWENCAI_API_KEY")
        print("示例: export IWENCAI_API_KEY=\"your_api_key_here\"")
        print()
        print("以下示例将模拟运行，不会实际调用API")
        print("=" * 80)
    
    # 运行示例
    example_basic_search()
    example_with_data_processing()
    example_save_to_files()
    example_batch_processing()
    example_cli_usage()
    example_curl_usage()
    
    print("\n示例运行完成!")
    print("请参考以上示例使用研报搜索技能。")


if __name__ == "__main__":
    main()
