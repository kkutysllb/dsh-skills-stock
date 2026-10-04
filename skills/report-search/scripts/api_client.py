#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能API客户端模块
符合iwencai-skill-creator规范
"""

import os
import json
import time
import logging
import secrets
from typing import Dict, List, Any, Optional, Tuple
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from config import get_config


class APIError(Exception):
    """API错误异常类"""
    pass


class APIClient:
    """API客户端类"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化API客户端
        
        Args:
            config_file: 配置文件路径
        """
        self.config = get_config(config_file)
        self.api_url = self.config.get_api_url()
        self.api_key = self.config.get_api_key()
        self.timeout = self.config.get("api.timeout")
        self.max_retries = self.config.get("api.max_retries")
        self.retry_delay = self.config.get("api.retry_delay")
        self.skill_id = "report-search"
        self.skill_version = "2.0.0"
        
        # 设置日志
        self.config.setup_logging()
        self.logger = logging.getLogger(__name__)
    
    def _generate_trace_id(self) -> str:
        """生成64字符的Trace ID"""
        return secrets.token_hex(32)
    
    def _get_headers(self, call_type: str = "normal") -> Dict[str, str]:
        """获取请求头（包含X-Claw-* Header）"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Claw-Call-Type": call_type,
            "X-Claw-Skill-Id": self.skill_id,
            "X-Claw-Skill-Version": self.skill_version,
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": self._generate_trace_id()
        }
        return headers
    
    def _prepare_payload(self, query: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """准备请求体"""
        payload = {
            "channels": self.config.get("search.channels"),
            "app_id": self.config.get("search.app_id"),
            "query": query
        }
        
        # 可以添加其他参数
        if limit:
            # 注意：实际接口可能不支持limit参数，这里只是示例
            pass
        
        return payload
    
    def _make_request_raw(self, payload: Dict[str, Any], call_type: str = "normal") -> Dict[str, Any]:
        """
        发送请求（带重试机制，完全透明传递响应）
        
        根据问财OpenAPI网关规范条件六，此方法必须透明传递所有API响应，
        包括错误响应，不做任何修改、过滤或重组。
        """
        for attempt in range(self.max_retries + 1):
            try:
                headers = self._get_headers(call_type)
                
                self.logger.debug(f"发送API请求 (尝试 {attempt + 1}/{self.max_retries + 1}): {payload}")
                self.logger.debug(f"Trace ID: {headers['X-Claw-Trace-Id']}")
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                self.logger.debug(f"API响应状态码: {response.status_code}")
                
                try:
                    return response.json()
                except ValueError:
                    self.logger.warning(f"API返回非JSON响应，状态码: {response.status_code}")
                    return {
                        "error": "invalid_json_response",
                        "raw_response": response.text,
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                    
            except Timeout:
                self.logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (attempt + 1)
                    self.logger.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise
                    
            except ConnectionError:
                self.logger.warning(f"连接错误 (尝试 {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    raise
                    
            except RequestException as e:
                self.logger.error(f"请求异常: {e}")
                if attempt < self.max_retries:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    time.sleep(self.retry_delay)
                else:
                    raise
        
        raise Exception(f"请求失败，已达到最大重试次数: {self.max_retries + 1}")
    
    def search_reports(self, query: str, limit: Optional[int] = None, call_type: str = "normal") -> Dict[str, Any]:
        """
        搜索研究报告（原始响应，完全透明传递）
        
        Args:
            query: 搜索关键词
            limit: 结果数量限制（注意：此参数仅用于向后兼容，实际限制应由调用方处理）
            call_type: 调用类型，normal或retry
            
        Returns:
            完整的API响应数据（符合响应透明传递要求）
            
        Note:
            根据问财OpenAPI网关规范条件六，此方法必须透明传递所有API响应，
            包括错误响应，不做任何修改、过滤或重组。
            调用方需要自己处理响应数据。这是推荐的使用方式。
        """
        try:
            self.logger.info(f"搜索研究报告: {query}")
            
            payload = self._prepare_payload(query, limit)
            
            response_data = self._make_request_raw(payload, call_type)
            
            self.logger.info(f"API响应接收完成")
            return response_data
            
        except Exception as e:
            self.logger.error(f"搜索研究报告时发生错误: {e}")
            raise
    
    def batch_search(self, queries: List[str], limit_per_query: Optional[int] = None, call_type: str = "normal") -> Dict[str, Dict[str, Any]]:
        """
        批量搜索研究报告（透明传递版本）
        
        Args:
            queries: 搜索关键词列表
            limit_per_query: 每个查询的结果数量限制（注意：此参数仅用于向后兼容）
            call_type: 调用类型，normal或retry
            
        Returns:
            字典，键为查询词，值为对应的透明传递的API响应
            
        Note:
            此方法完全透明传递API响应，符合问财规范条件六。
            调用方需要自己处理响应数据。
        """
        results = {}
        
        for i, query in enumerate(queries):
            try:
                self.logger.info(f"批量搜索 [{i+1}/{len(queries)}]: {query}")
                response_data = self.search_reports(query, limit_per_query, call_type=call_type)
                results[query] = response_data
                
                if i < len(queries) - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                self.logger.error(f"查询 '{query}' 搜索失败: {str(e)}")
                results[query] = {"error": "search_failed", "message": str(e)}
        
        return results
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            连接是否成功
        """
        try:
            self.logger.info("测试API连接...")
            
            test_query = "测试"
            test_payload = self._prepare_payload(test_query)
            
            response = self._make_request_raw(test_payload)
            
            if "error" not in response:
                self.logger.info("API连接测试成功")
                return True
            else:
                self.logger.warning(f"API连接测试失败: {response}")
                return False
                
        except Exception as e:
            self.logger.error(f"API连接测试异常: {e}")
            return False


if __name__ == "__main__":
    import sys
    
    if not os.getenv("IWENCAI_API_KEY"):
        print("请设置环境变量 IWENCAI_API_KEY")
        sys.exit(1)
    
    try:
        client = APIClient()
        
        if client.test_connection():
            print("API连接测试成功")
        else:
            print("API连接测试失败")
            sys.exit(1)
            
        test_queries = ["人工智能", "芯片行业"]
        for query in test_queries:
            print(f"\n搜索: {query}")
            try:
                response = client.search_reports(query, limit=3)
                print(f"API响应类型: {type(response)}")
                if isinstance(response, dict):
                    print(f"响应键: {list(response.keys())}")
            except Exception as e:
                print(f"搜索失败: {e}")
                
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        sys.exit(1)