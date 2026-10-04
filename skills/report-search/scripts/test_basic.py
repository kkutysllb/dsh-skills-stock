#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能基础测试
"""

import os
import sys
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config, get_config
from data_processor import DataProcessor
from api_client import APIClient, APIError


class TestConfig(unittest.TestCase):
    """配置模块测试"""
    
    def setUp(self):
        """测试前准备"""
        self.config = Config()
    
    def test_default_config(self):
        """测试默认配置"""
        self.assertEqual(self.config.get("api.base_url"), "https://openapi.iwencai.com")
        self.assertEqual(self.config.get("api.endpoint"), "/v1/comprehensive/search")
        self.assertEqual(self.config.get("search.channels"), ["report"])
        self.assertEqual(self.config.get("search.app_id"), "AIME_SKILL")
    
    def test_get_api_url(self):
        """测试获取API URL"""
        api_url = self.config.get_api_url()
        self.assertEqual(api_url, "https://openapi.iwencai.com/v1/comprehensive/search")
    
    def test_validation(self):
        """测试配置验证"""
        # 测试空配置
        config = Config()
        with self.assertRaises(ValueError):
            config.config["api"]["base_url"] = ""
            config.validate()
    
    def test_environment_variables(self):
        """测试环境变量"""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            config = Config()
            self.assertEqual(config.get("logging.level"), "DEBUG")
    
    def test_config_file_loading(self):
        """测试配置文件加载"""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "api": {
                    "timeout": 60
                }
            }, f)
            config_file = f.name
        
        try:
            config = Config(config_file)
            self.assertEqual(config.get("api.timeout"), 60)
        finally:
            os.unlink(config_file)


class TestDataProcessor(unittest.TestCase):
    """数据处理模块测试"""
    
    def setUp(self):
        """测试前准备"""
        self.processor = DataProcessor()
        self.test_articles = [
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
    
    def test_filter_by_date(self):
        """测试按日期过滤"""
        # 过滤2024-01-14之后的文章
        filtered = self.processor.filter_by_date(
            self.test_articles,
            date_from="2024-01-14"
        )
        self.assertEqual(len(filtered), 2)
        
        # 过滤2024-01-14到2024-01-15之间的文章
        # date_to 用 > 比较，2024-01-15 00:00:00 只匹配 14:20 那条
        filtered = self.processor.filter_by_date(
            self.test_articles,
            date_from="2024-01-14",
            date_to="2024-01-15"
        )
        self.assertEqual(len(filtered), 1)
    
    def test_filter_by_days(self):
        """测试按最近N天过滤"""
        # 注意：这个测试依赖于当前时间
        # 这里我们主要测试函数是否能正常运行
        filtered = self.processor.filter_by_days(self.test_articles, days=30)
        self.assertIsInstance(filtered, list)
    
    def test_sort_articles(self):
        """测试排序"""
        # 按日期降序排序
        sorted_articles = self.processor.sort_articles(
            self.test_articles,
            sort_by="date",
            sort_order="desc"
        )
        self.assertEqual(sorted_articles[0]["title"], "人工智能行业研究报告：买入评级，目标价120元")
        
        # 按相关性排序
        sorted_articles = self.processor.sort_articles(
            self.test_articles,
            sort_by="relevance",
            sort_order="desc"
        )
        self.assertIsInstance(sorted_articles, list)
    
    def test_extract_key_info(self):
        """测试提取关键信息"""
        processed = self.processor.extract_key_info(self.test_articles)
        
        self.assertEqual(len(processed), 3)
        
        # 检查提取的信息
        for article in processed:
            self.assertIn("extracted_info", article)
            extracted = article["extracted_info"]
            
            self.assertIn("rating", extracted)
            self.assertIn("target_price", extracted)
            self.assertIn("industry", extracted)
            self.assertIn("has_analysis", extracted)
    
    def test_save_to_csv(self):
        """测试保存到CSV"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test.csv"
            self.processor.save_to_csv(self.test_articles, str(csv_path))
            
            self.assertTrue(csv_path.exists())
            self.assertGreater(csv_path.stat().st_size, 0)
    
    def test_save_to_json(self):
        """测试保存到JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            self.processor.save_to_json(self.test_articles, str(json_path))
            
            self.assertTrue(json_path.exists())
            
            # 验证JSON格式
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertIsInstance(data, list)
                self.assertEqual(len(data), 3)
    
    def test_save_to_markdown(self):
        """测试保存到Markdown"""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "test.md"
            self.processor.save_to_markdown(self.test_articles, str(md_path))
            
            self.assertTrue(md_path.exists())
            
            # 验证Markdown内容
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("# 研究报告汇总", content)
                self.assertIn("数据来源", content)
    
    def test_analyze_articles(self):
        """测试分析研究报告"""
        processed = self.processor.extract_key_info(self.test_articles)
        analysis = self.processor.analyze_articles(processed)
        
        self.assertIn("total_count", analysis)
        self.assertEqual(analysis["total_count"], 3)
        
        self.assertIn("industry_distribution", analysis)
        self.assertIn("rating_distribution", analysis)
        self.assertIn("avg_summary_length", analysis)
        self.assertIn("analysis_coverage", analysis)


class TestAPIClient(unittest.TestCase):
    """API客户端模块测试"""
    
    def setUp(self):
        """测试前准备"""
        # 模拟环境变量
        self.env_patch = patch.dict(os.environ, {"IWENCAI_API_KEY": "test_key"})
        self.env_patch.start()
        
        self.client = APIClient()
    
    def tearDown(self):
        """测试后清理"""
        self.env_patch.stop()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.client.api_key, "test_key")
        self.assertEqual(self.client.api_url, "https://openapi.iwencai.com/v1/comprehensive/search")
    
    @patch('requests.post')
    def test_search_reports_success(self, mock_post):
        """测试搜索研究报告成功（透明传递模式，返回完整dict）"""
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "测试报告",
                    "summary": "测试摘要",
                    "url": "https://example.com/test",
                    "publish_date": "2024-01-01 00:00:00"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 调用搜索（透明传递模式，返回完整dict而非list）
        response = self.client.search_reports("测试", limit=5)
        
        # 验证返回的是完整API响应dict（透明传递）
        self.assertIsInstance(response, dict)
        self.assertIn("data", response)
        self.assertEqual(len(response["data"]), 1)
        self.assertEqual(response["data"][0]["title"], "测试报告")
        
        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://openapi.iwencai.com/v1/comprehensive/search")
        
        # 验证请求头
        headers = call_args[1]['headers']
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Authorization'], 'Bearer test_key')
        
        # 验证请求体
        json_data = call_args[1]['json']
        self.assertEqual(json_data['channels'], ['report'])
        self.assertEqual(json_data['app_id'], 'AIME_SKILL')
        self.assertEqual(json_data['query'], '测试')
    
    @patch('requests.post')
    def test_search_reports_api_error(self, mock_post):
        """测试API错误（透明传递模式，错误响应也原样返回dict）"""
        # 模拟API错误响应
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "message": "认证失败"
        }
        mock_post.return_value = mock_response
        
        # 透明传递模式：API错误响应也原样返回dict，不抛APIError
        response = self.client.search_reports("测试")
        self.assertIsInstance(response, dict)
        self.assertIn("message", response)
        self.assertEqual(response["message"], "认证失败")
    
    @patch('requests.post')
    def test_search_reports_network_error(self, mock_post):
        """测试网络错误（透明传递模式，网络层错误抛ConnectionError）"""
        # 模拟网络错误
        mock_post.side_effect = ConnectionError("网络连接失败")
        
        # 透明传递模式：网络层错误（非API响应）直接抛ConnectionError
        with self.assertRaises(ConnectionError) as context:
            self.client.search_reports("测试")
        
        self.assertIn("网络连接失败", str(context.exception))
    
    def test_batch_search(self):
        """测试批量搜索（透明传递模式，返回Dict[str, Dict]）"""
        # 模拟search_reports方法，返回透明传递的dict
        with patch.object(self.client, 'search_reports') as mock_search:
            mock_search.return_value = {
                "data": [
                    {"title": "测试报告1"},
                    {"title": "测试报告2"}
                ]
            }
            
            # 调用批量搜索
            queries = ["查询1", "查询2"]
            results = self.client.batch_search(queries, limit_per_query=2)
            
            # 验证结果：batch_search返回Dict[str, Dict]
            self.assertIsInstance(results, dict)
            self.assertEqual(len(results), 2)
            self.assertIn("查询1", results)
            self.assertIn("查询2", results)
            # 每个query的值是透明传递的API响应dict
            self.assertIsInstance(results["查询1"], dict)
            self.assertIn("data", results["查询1"])
            self.assertEqual(len(results["查询1"]["data"]), 2)
            
            # 验证调用次数
            self.assertEqual(mock_search.call_count, 2)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """测试前准备"""
        # 模拟环境变量
        self.env_patch = patch.dict(os.environ, {"IWENCAI_API_KEY": "test_key"})
        self.env_patch.start()
    
    def tearDown(self):
        """测试后清理"""
        self.env_patch.stop()
    
    @patch('requests.post')
    def test_end_to_end_workflow(self, mock_post):
        """测试端到端工作流程（透明传递模式：API返回dict，需提取list后再处理）"""
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "人工智能报告",
                    "summary": "人工智能行业分析",
                    "url": "https://example.com/ai",
                    "publish_date": "2024-01-15 09:30:00"
                },
                {
                    "title": "芯片报告",
                    "summary": "芯片行业分析",
                    "url": "https://example.com/chip",
                    "publish_date": "2024-01-14 14:20:00"
                }
            ]
        }
        mock_post.return_value = mock_response
        
        # 初始化组件
        client = APIClient()
        processor = DataProcessor()
        
        # 搜索研究报告（透明传递模式，返回完整dict）
        api_response = client.search_reports("人工智能", limit=5)
        
        # 从透明传递的dict中提取文章列表（模拟真实使用场景中的数据提取）
        self.assertIsInstance(api_response, dict)
        self.assertIn("data", api_response)
        articles = api_response["data"]
        self.assertIsInstance(articles, list)
        
        # 数据处理（现在articles是list，可以传给DataProcessor）
        processed = processor.extract_key_info(articles)
        sorted_articles = processor.sort_articles(processed, sort_by="date", sort_order="desc")
        
        # 验证结果
        self.assertEqual(len(sorted_articles), 2)
        self.assertEqual(sorted_articles[0]["title"], "人工智能报告")
        
        # 验证提取的信息
        self.assertIn("extracted_info", sorted_articles[0])
        extracted = sorted_articles[0]["extracted_info"]
        self.assertIn("rating", extracted)
        self.assertIn("target_price", extracted)
        self.assertIn("industry", extracted)
        self.assertIn("has_analysis", extracted)


def run_tests():
    """运行测试"""
    # 创建测试套件
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTest(unittest.makeSuite(TestConfig))
    suite.addTest(unittest.makeSuite(TestDataProcessor))
    suite.addTest(unittest.makeSuite(TestAPIClient))
    suite.addTest(unittest.makeSuite(TestIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("研报搜索技能基础测试")
    print("=" * 80)
    
    # 运行测试
    result = run_tests()
    
    # 输出测试结果
    print("\n" + "=" * 80)
    print(f"测试结果: {result.testsRun} 个测试用例")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures or result.errors:
        sys.exit(1)
    else:
        print("\n所有测试通过!")