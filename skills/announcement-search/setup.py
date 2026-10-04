#!/usr/bin/env python3
"""
announcement-search 根目录 setup.py

此文件将安装代理到 scripts/setup.py，确保 pip install -e . 在根目录即可工作。
"""
import os
import sys
from setuptools import setup

# 代理到 scripts/setup.py
scripts_dir = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.insert(0, scripts_dir)

# 读 requirements
req_file = os.path.join(scripts_dir, 'requirements.txt')
install_requires = []
if os.path.exists(req_file):
    with open(req_file, 'r', encoding='utf-8') as f:
        install_requires = [
            line.strip() for line in f
            if line.strip() and not line.startswith('#')
        ]

# 读 README
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
long_desc = ''
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_desc = f.read()

setup(
    name='announcement-search',
    version='1.0.0',
    description='金融公告搜索工具 - 搜索A股、港股、基金、ETF等金融标的公告',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    author='公告搜索技能开发团队',
    license='MIT',
    py_modules=['config', 'utils', 'announcement_search'],
    package_dir={'': 'scripts'},
    scripts=[os.path.join('scripts', '__main__.py')],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'announcement-search=__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Office/Business :: Financial :: Investment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    keywords='finance, announcement, search, stock, fund, etf',
    python_requires='>=3.8',
    include_package_data=True,
    zip_safe=False,
)

if __name__ == '__main__':
    print('公告搜索工具安装成功')
    print('使用方式: announcement-search --help')