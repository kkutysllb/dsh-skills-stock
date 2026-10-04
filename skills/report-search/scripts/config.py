#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能配置管理模块
"""

import os
import json
import logging
from typing import Dict, Any, Optional
import copy

# 默认配置
DEFAULT_CONFIG = {
    "api": {
        "base_url": "https://openapi.iwencai.com",
        "endpoint": "/v1/comprehensive/search",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0
    },
    "search": {
        "channels": ["report"],
        "app_id": "AIME_SKILL",
        "default_limit": 10,
        "default_days": 30,
        "min_articles_for_sufficient": 3
    },
    "output": {
        "default_format": "text",
        "csv_encoding": "utf-8-sig",
        "json_indent": 2
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}


class Config:
    """配置管理类"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径，如果为None则使用默认配置
        """
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        
        # 从配置文件加载配置（如果提供）
        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)
        
        # 从环境变量覆盖配置
        self.load_from_env()
        
        # 验证配置
        self.validate()
    
    def load_from_file(self, config_file: str) -> None:
        """从配置文件加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                self._merge_config(file_config)
            logging.info(f"从文件加载配置: {config_file}")
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"加载配置文件失败 {config_file}: {e}, 使用默认配置")
    
    def load_from_env(self) -> None:
        """从环境变量加载配置"""
        # API配置
        api_key = os.getenv("IWENCAI_API_KEY")
        if api_key:
            # API Key存储在环境变量中，不在配置中硬编码
            logging.info("从环境变量加载API Key")
        
        # 超时时间
        timeout = os.getenv("API_TIMEOUT")
        if timeout:
            try:
                self.config["api"]["timeout"] = int(timeout)
            except ValueError:
                pass
        
        # 日志级别
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            self.config["logging"]["level"] = log_level.upper()
    
    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """合并配置"""
        for key, value in new_config.items():
            if key in self.config and isinstance(self.config[key], dict) and isinstance(value, dict):
                # 递归合并字典
                self.config[key].update(value)
            else:
                # 直接覆盖
                self.config[key] = value
    
    def validate(self) -> None:
        """验证配置"""
        # 检查必要的API配置
        if not self.config["api"]["base_url"]:
            raise ValueError("API base_url 不能为空")
        
        if not self.config["api"]["endpoint"]:
            raise ValueError("API endpoint 不能为空")
        
        # 检查搜索配置
        if not self.config["search"]["channels"]:
            raise ValueError("搜索渠道 channels 不能为空")
        
        if not self.config["search"]["app_id"]:
            raise ValueError("应用ID app_id 不能为空")
        
        # 检查超时时间
        if self.config["api"]["timeout"] <= 0:
            raise ValueError("API timeout 必须大于0")
        
        # 检查重试次数
        if self.config["api"]["max_retries"] < 0:
            raise ValueError("API max_retries 不能为负数")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_api_key(self) -> str:
        """获取API Key（从环境变量）"""
        api_key = os.getenv("IWENCAI_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 IWENCAI_API_KEY")
        return api_key
    
    def get_api_url(self) -> str:
        """获取完整的API URL"""
        base_url = self.config["api"]["base_url"].rstrip('/')
        endpoint = self.config["api"]["endpoint"].lstrip('/')
        return f"{base_url}/{endpoint}"
    
    def setup_logging(self) -> None:
        """设置日志"""
        log_level = self.config["logging"]["level"]
        log_format = self.config["logging"]["format"]
        
        # 设置日志级别
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        
        logging.basicConfig(
            level=numeric_level,
            format=log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config(config_file: Optional[str] = None) -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


if __name__ == "__main__":
    # 测试配置模块
    config = get_config()
    print("API URL:", config.get_api_url())
    print("搜索渠道:", config.get("search.channels"))
    print("默认限制:", config.get("search.default_limit"))
    
    # 测试环境变量
    try:
        api_key = config.get_api_key()
        print("API Key:", "已设置" if api_key else "未设置")
    except ValueError as e:
        print(f"API Key错误: {e}")