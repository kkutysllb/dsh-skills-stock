#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
研报搜索技能主程序
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli import main

if __name__ == "__main__":
    sys.exit(main())