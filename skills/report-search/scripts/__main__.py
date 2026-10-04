#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能命令行入口点
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from research_report_search import main

if __name__ == "__main__":
    sys.exit(main())