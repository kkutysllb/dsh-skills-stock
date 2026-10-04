#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能安装配置
"""

import os
import sys
from setuptools import setup, find_packages

# 读取版本信息
with open(os.path.join(os.path.dirname(__file__), 'requirements.txt'), 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# 读取README
with open(os.path.join(os.path.dirname(__file__), '..', 'README.md'), 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="research-report-search",
    version="1.0.0",
    description="研报搜索技能 - 搜索和分析财经研究报告",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="研报搜索技能开发团队",
    author_email="",
    url="",
    packages=find_packages(),
    py_modules=[
        'config',
        'api_client',
        'data_processor',
        'cli',
        'research_report_search'
    ],
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'research-report-search=research_report_search:main',
            'rrs=research_report_search:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Office/Business :: Financial :: Investment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    keywords='research report, financial analysis, investment, stock, finance',
    python_requires='>=3.7',
    project_urls={
        'Documentation': 'https://github.com/example/research-report-search',
        'Source': 'https://github.com/example/research-report-search',
        'Tracker': 'https://github.com/example/research-report-search/issues',
    },
)


def install_config():
    """安装配置文件"""
    import shutil
    from pathlib import Path
    
    # 源配置文件路径
    source_config = Path(__file__).parent / 'config.example.json'
    
    # 目标配置文件路径（用户目录）
    home_dir = Path.home()
    config_dir = home_dir / '.research_report_search'
    config_dir.mkdir(exist_ok=True)
    
    target_config = config_dir / 'config.json'
    
    # 如果配置文件不存在，复制示例配置
    if not target_config.exists() and source_config.exists():
        shutil.copy2(source_config, target_config)
        print(f"已创建配置文件: {target_config}")
        print("请编辑该文件以配置您的API设置。")
    else:
        print(f"配置文件已存在: {target_config}")


def check_dependencies():
    """检查依赖"""
    import subprocess
    import importlib
    
    print("检查依赖...")
    
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        sys.exit(1)
    
    # 检查必要依赖
    required_packages = ['requests', 'pandas', 'numpy']
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} 未安装")
            print(f"    请运行: pip install {package}")
    
    print("\n依赖检查完成。")


if __name__ == "__main__":
    # 安装时执行额外操作
    if len(sys.argv) > 1 and sys.argv[1] == 'install':
        print("研报搜索技能安装程序")
        print("=" * 80)
        
        # 检查依赖
        check_dependencies()
        
        # 安装配置文件
        install_config()
        
        print("\n安装完成!")
        print("\n使用说明:")
        print("1. 设置API密钥环境变量:")
        print("   export IWENCAI_API_KEY=\"your_api_key_here\"")
        print("\n2. 基本使用:")
        print("   research-report-search -q \"人工智能行业研究报告\"")
        print("\n3. 获取帮助:")
        print("   research-report-search -h")
        
    else:
        # 正常setup.py执行
        pass