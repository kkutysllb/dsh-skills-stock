"""
市场联动分析引擎 (Market Linkage Analysis Engine)

独立的、可复用的 A 股市场联动分析引擎，覆盖 8 大维度：
  1. 主力资金流向
  2. 北向资金流向
  3. 两融趋势
  4. 股指期货基差分析
  5. 7 大期权 ETF 波动率分析
  6. 9 大宽基 ETF 份额变化分析
  7. Shibor 利率走势分析
  8. 龙虎榜分析

数据源：Tushare Pro API + 同花顺问财 OpenAPI。

用法:
    from market_linkage_engine import LinkageEngine
    engine = LinkageEngine()
    daily = engine.run_daily()      # 日度联动分析
    weekly = engine.run_weekly()    # 周度联动分析
"""
from .engine import LinkageEngine
from .data.fetcher import LinkageFetcher

__version__ = "1.0.0"
__all__ = ["LinkageEngine", "LinkageFetcher"]
