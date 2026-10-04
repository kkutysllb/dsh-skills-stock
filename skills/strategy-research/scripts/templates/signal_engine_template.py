"""
SignalEngine 基类模板 — 所有策略必须遵循此合约

用法:
  1. 复制此文件为 signal_engine.py
  2. 实现 generate() 方法
  3. 信号值范围 [-1.0, 1.0]：1.0=满仓做多, 0.0=空仓, -1.0=满仓做空
  4. 组合策略：N只入选各 1/N 权重，未入选 = 0
"""

from typing import Dict
import pandas as pd


class SignalEngine:
    """
    策略信号引擎。

    Args:
        data_map: code -> DataFrame (columns: open, high, low, close, volume)
                 如果 config.json 指定了 extra_fields，还会包含 pe, pb, roe 等列。

    Returns:
        code -> signal Series, 值范围 [-1.0, 1.0]
        1.0 = 满仓做多, 0.5 = 半仓, 0.0 = 空仓, -1.0 = 满仓做空
        组合策略: 入选股票各 1/N 权重 (如 top10 -> 各 0.1), 未入选 = 0
    """

    def generate(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """
        生成交易信号。

        必须实现此方法。
        """
        raise NotImplementedError("子类必须实现 generate() 方法")


# ===== 硬性约束 =====
# 1. signal Series 的 index 必须与输入 DataFrame 的 index 完全对齐
# 2. 包含所有必要的 import (numpy, pandas 等)
# 3. 不要硬编码日期或股票代码
# 4. 不要包含 if __name__ == "__main__" 块
# 5. 纯 pandas/numpy 实现，不依赖外部信号库
# 6. 输出纯 Python 代码，不要 Markdown 围栏
