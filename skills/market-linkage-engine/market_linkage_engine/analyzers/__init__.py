"""分析器子包：8 大维度各自的 fetch + analyze 逻辑。"""
from .main_capital import MainCapitalAnalyzer
from .northbound import NorthboundAnalyzer
from .margin import MarginAnalyzer
from .futures_basis import FuturesBasisAnalyzer
from .options_vol import OptionsVolatilityAnalyzer
from .broad_etf_share import BroadETFShareAnalyzer
from .shibor import ShiborAnalyzer
from .dragon_tiger import DragonTigerAnalyzer

__all__ = [
    "MainCapitalAnalyzer",
    "NorthboundAnalyzer",
    "MarginAnalyzer",
    "FuturesBasisAnalyzer",
    "OptionsVolatilityAnalyzer",
    "BroadETFShareAnalyzer",
    "ShiborAnalyzer",
    "DragonTigerAnalyzer",
]
