#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的MACD背驰选股策略
基于MACD红绿柱面积对比的实用背驰判断方法
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..', '..'))

from chan_theory_v2.models.simple_backchi import SimpleBackchiAnalyzer
from chan_theory_v2.models.dynamics import MacdCalculator
from chan_theory_v2.models.kline import KLineList
from chan_theory_v2.models.enums import TimeLevel
from chan_theory_v2.core.trading_calendar import get_nearest_trading_date
try:
    from database.db_handler import get_db_handler
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

# Tushare API 数据获取
try:
    from kk_common import get_finance_data_gateway
    _TUSHARE_AVAILABLE = True
except ImportError:
    _TUSHARE_AVAILABLE = False

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """信号强度枚举"""
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


@dataclass
class StockSignal:
    """股票信号数据结构"""
    symbol: str
    name: str
    
    # 信号类型和强度
    signal_type: str = "观望"  # "买入", "卖出", "观望"
    backchi_type: Optional[str] = None  # "bottom", "top"
    reliability: float = 0.0
    description: str = ""
    
    # MACD技术指标
    has_macd_golden_cross: bool = False
    has_macd_death_cross: bool = False
    
    # 综合评分
    overall_score: float = 0.0
    signal_strength: SignalStrength = SignalStrength.WEAK
    recommendation: str = "观望"
    
    # 关键价位
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # 多信号融合评分详情
    signal_fusion: Optional[Dict] = None
    
    # 时间戳
    analysis_time: datetime = None
    
    def __post_init__(self):
        if self.analysis_time is None:
            self.analysis_time = datetime.now()


class SimpleBackchiStockSelector:
    """简化的MACD背驰选股器（支持多信号融合评分）
    
    优先使用 Tushare Pro API 获取数据，无本地数据库依赖。
    """
    
    def __init__(self, use_signal_scorer: bool = True):
        """初始化选股器
        
        Args:
            use_signal_scorer: 是否启用多信号融合评分（默认启用）
        """
        # 初始化 Tushare API
        if not _TUSHARE_AVAILABLE:
            raise RuntimeError("tushare 不可用，请检查 Python 运行时配置")
        from dotenv import load_dotenv
        load_dotenv()
        token = os.environ.get('TUSHARE_TOKEN', '')
        if not token:
            raise ValueError('TUSHARE_TOKEN 环境变量未设置')
        self.pro = get_finance_data_gateway()
        self._stock_basic_cache = None
        self.use_signal_scorer = use_signal_scorer
        
        # 选股参数配置 - 与DynamicsAnalyzer保持一致
        self.config = {
            'days_30min': 30,      # 30分钟分析天数
            'min_backchi_strength': 0.3,  # 最小背驰强度 (与DynamicsAnalyzer的min_reliability一致)
            'require_macd_golden_cross': True,  # 买入要求MACD金叉
            'max_stocks_per_batch': 0,     # 0表示处理全市场所有股票
            'min_price': 2.0,      # 最低股价过滤
            'max_price': 1000.0,   # 最高股价过滤
            'min_volume_ratio': 0.5,  # 最小成交量比率
            # 背驰分析参数 - 与DynamicsAnalyzer保持完全一致
            'min_area_ratio': 1.1,           # 绿柱面积比阈值
            'max_area_shrink_ratio': 0.9,    # 红柱面积缩小比例
            'confirm_days': 3,               # 金叉确认天数
            'death_cross_confirm_days': 2,   # 死叉确认天数
            # 多信号融合评分参数
            'signal_score_weight': 0.4,   # 信号融合评分在综合评分中的权重（0~1）
            'backchi_score_weight': 0.6,  # 原有背驰评分在综合评分中的权重
        }
        
        # 延迟初始化信号评分器
        self._signal_scorer = None
        
        logger.info("🎯 简化MACD背驰选股器初始化完成（多信号融合: %s）",
                     "启用" if use_signal_scorer else "禁用")
    
    @property
    def signal_scorer(self):
        """延迟加载信号评分器"""
        if self._signal_scorer is None and self.use_signal_scorer:
            try:
                from chan_theory_v2.core.signal_scorer import SignalScorer
                self._signal_scorer = SignalScorer()
                logger.info("✅ 信号评分融合引擎加载完成")
            except Exception as e:
                logger.warning(f"⚠️ 信号评分引擎加载失败，将使用纯背驰评分: {e}")
                self.use_signal_scorer = False
        return self._signal_scorer
    
    def _get_stock_basic(self):
        """缓存获取股票基础信息（Tushare API）"""
        import pandas as pd
        if self._stock_basic_cache is None:
            try:
                self._stock_basic_cache = self.pro.stock_basic(
                    exchange='', list_status='L', fields='ts_code,name'
                )
            except Exception:
                self._stock_basic_cache = pd.DataFrame(columns=['ts_code', 'name'])
        return self._stock_basic_cache
    
    def get_stock_pool(self) -> List[Dict[str, str]]:
        """获取股票池（全市场筛选，通过 Tushare API）"""
        try:
            import pandas as pd
            df = self._get_stock_basic()
            if df.empty:
                return []
            
            # 基础筛选条件：排除ST股票、退市股票、B股等
            import re
            mask = ~df['name'].str.contains('ST|退市|暂停|B$|N|C', regex=True, na=False)
            df = df[mask].reset_index(drop=True)
            
            all_stocks = [{'symbol': row['ts_code'], 'name': row['name']} for _, row in df.iterrows()]
            
            logger.info(f"📊 股票池：{len(all_stocks)} 只股票")
            return all_stocks
            
        except Exception as e:
            logger.error(f"❌ 获取股票池失败: {e}")
            return []
    
    def analyze_stock_backchi(self, symbol: str) -> Optional[StockSignal]:
        """分析单个股票的背驰情况（含多信号融合评分）"""
        try:
            # 获取30分钟K线数据
            data = self._fetch_stock_data(symbol, TimeLevel.MIN_30, self.config['days_30min'])
            if not data or len(data) < 30:
                logger.debug(f"📊 {symbol} 数据不足: {len(data) if data else 0}条")
                return None
            
            # 转换数据格式
            klines = KLineList.from_dict_data(data, TimeLevel.MIN_30)
            
            # 计算MACD
            close_prices = [kline.close for kline in klines]
            macd_calculator = MacdCalculator()
            macd_data = macd_calculator.calculate(close_prices)
            
            if len(macd_data) < 20:
                logger.debug(f"📊 {symbol} MACD数据不足: {len(macd_data)}条")
                return None
            
            # 执行简化背驰分析（传入配置参数）
            analyzer_config = {
                'min_area_ratio': self.config.get('min_area_ratio', 1.1),
                'max_area_shrink_ratio': self.config.get('max_area_shrink_ratio', 0.9),
                'confirm_days': self.config.get('confirm_days', 3),
                'death_cross_confirm_days': self.config.get('death_cross_confirm_days', 2),
            }
            analyzer = SimpleBackchiAnalyzer(analyzer_config)
            backchi_type, reliability, description = analyzer.analyze_backchi(klines, macd_data)
            
            # 检查MACD金叉/死叉
            has_golden_cross, has_death_cross = self._check_macd_crosses(macd_data)
            
            # 判断信号类型
            signal_type = "观望"
            if backchi_type == "bottom" and reliability >= self.config['min_backchi_strength']:
                if not self.config['require_macd_golden_cross'] or has_golden_cross:
                    signal_type = "买入"
            elif backchi_type == "top" and reliability >= self.config['min_backchi_strength']:
                signal_type = "卖出"
            
            # 只有买入或卖出信号才创建记录
            if signal_type == "观望":
                return None
            
            # 获取股票名称
            stock_name = self._get_stock_name(symbol)
            
            # 创建信号对象
            signal = StockSignal(
                symbol=symbol,
                name=stock_name,
                signal_type=signal_type,
                backchi_type=backchi_type,
                reliability=reliability,
                description=description,
                has_macd_golden_cross=has_golden_cross,
                has_macd_death_cross=has_death_cross
            )
            
            # ── 计算评分（支持多信号融合） ──
            backchi_score = self._calculate_signal_score(signal)  # 原有背驰评分
            
            # 尝试获取多信号融合评分
            signal_fusion_score = None
            signal_fusion_result = None
            if self.use_signal_scorer and self.signal_scorer and len(klines) >= 50:
                try:
                    signal_fusion_result = self._calc_signal_fusion_score(symbol, klines)
                    if signal_fusion_result:
                        signal_fusion_score = signal_fusion_result.final_score
                except Exception as e:
                    logger.debug(f"📊 {symbol} 信号融合评分失败: {e}")
            
            # 融合评分：加权合并背驰评分和信号融合评分
            if signal_fusion_score is not None:
                sw = self.config.get('signal_score_weight', 0.4)
                bw = self.config.get('backchi_score_weight', 0.6)
                # 背驰评分 0~100，信号融合评分 0~100
                signal.overall_score = round(backchi_score * bw + signal_fusion_score * sw, 2)
                # 记录信号融合详情
                signal.signal_fusion = signal_fusion_result.to_dict() if signal_fusion_result else None
            else:
                signal.overall_score = backchi_score
                signal.signal_fusion = None
            
            signal.signal_strength = self._determine_signal_strength(signal.overall_score)
            signal.recommendation = self._generate_recommendation(signal)
            
            # 计算关键价位
            self._calculate_key_prices(signal, klines)
            
            fusion_info = f" + 信号融合{signal_fusion_score:.1f}" if signal_fusion_score else ""
            logger.info(f"✅ {symbol} {signal_type}信号评分: {signal.overall_score:.1f}(背驰{backchi_score:.1f}{fusion_info}), 强度: {signal.signal_strength.value}")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ 分析股票 {symbol} 失败: {e}")
            return None
    
    def _calc_signal_fusion_score(self, symbol: str, klines: KLineList):
        """基于信号函数库生成融合评分
        
        使用K线数据生成信号库的信号，然后通过SignalScorer融合评分。
        由于选股场景不依赖完整的缠论分析结果，这里使用信号函数库
        直接对K线数据生成信号。
        
        Args:
            symbol: 股票代码
            klines: K线数据
            
        Returns:
            SignalScoreResult 或 None
        """
        try:
            from chan_theory_v2.core.signal_scorer import SignalScorer
            from chan_theory_v2.signals import tas, bar, vol, jcc, pos, sta
            
            freq = "30分钟"
            signals = {}
            bars_raw = list(klines)
            
            # ── tas 技术指标信号 ──
            if len(bars_raw) >= 50:
                try:
                    signals['tas_macd_cross'] = tas.tas_macd_cross(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_double_ma'] = tas.tas_double_ma(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_ma_system'] = tas.tas_ma_system(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_dif_zero'] = tas.tas_dif_zero(freq, bars_raw)
                except Exception:
                    pass
            if len(bars_raw) >= 30:
                try:
                    signals['tas_boll_status'] = tas.tas_boll_status(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_kdj_cross'] = tas.tas_kdj_cross(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_rsi_status'] = tas.tas_rsi_status(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['tas_volume_price'] = tas.tas_volume_price(freq, bars_raw)
                except Exception:
                    pass
            
            # ── vol 成交量信号 ──
            if len(bars_raw) >= 20:
                try:
                    signals['vol_ratio'] = vol.vol_ratio_signal(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['vol_single_ma'] = vol.vol_single_ma(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['vol_break'] = vol.vol_break(freq, bars_raw)
                except Exception:
                    pass
            
            # ── bar K线基础信号 ──
            if len(bars_raw) >= 10:
                try:
                    signals['bar_zdf'] = bar.bar_zdf(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['bar_big_solid'] = bar.bar_big_solid(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['bar_section_momentum'] = bar.bar_section_momentum(freq, bars_raw)
                except Exception:
                    pass
            
            # ── pos 位置信号 ──
            if len(bars_raw) >= 20:
                try:
                    signals['pos_above_ma'] = pos.pos_above_ma(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['pos_boll_position'] = pos.pos_boll_position(freq, bars_raw)
                except Exception:
                    pass
            
            # ── jcc K线组合形态信号 ──
            if len(bars_raw) >= 5:
                try:
                    signals['jcc_hammer'] = jcc.jcc_hammer(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['jcc_engulfing'] = jcc.jcc_engulfing(freq, bars_raw)
                except Exception:
                    pass
            
            # ── sta 统计信号 ──
            if len(bars_raw) >= 30:
                try:
                    signals['sta_mean_revert'] = sta.sta_mean_revert(freq, bars_raw)
                except Exception:
                    pass
                try:
                    signals['sta_percentile'] = sta.sta_percentile(freq, bars_raw)
                except Exception:
                    pass
            
            if not signals:
                return None
            
            # 融合评分
            return self.signal_scorer.score_all_signals(signals)
            
        except Exception as e:
            logger.debug(f"📊 {symbol} 信号融合评分计算异常: {e}")
            return None
    
    def _check_macd_crosses(self, macd_data) -> Tuple[bool, bool]:
        """检查MACD金叉和死叉"""
        has_golden_cross = False
        has_death_cross = False
        
        if len(macd_data) >= 3:
            recent_macd = macd_data[-3:]
            for i in range(1, len(recent_macd)):
                prev_macd = recent_macd[i-1]
                curr_macd = recent_macd[i]
                
                # 检查金叉
                if (prev_macd.dif <= prev_macd.dea and 
                    curr_macd.dif > curr_macd.dea and
                    curr_macd.macd >= 0):
                    has_golden_cross = True
                
                # 检查死叉
                if (prev_macd.dif >= prev_macd.dea and 
                    curr_macd.dif < curr_macd.dea and
                    curr_macd.macd <= 0):
                    has_death_cross = True
        
        return has_golden_cross, has_death_cross
    
    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称（通过 Tushare API）"""
        try:
            df = self._get_stock_basic()
            match = df[df['ts_code'] == symbol]
            if not match.empty:
                return match.iloc[0]['name']
        except Exception:
            pass
        return symbol
    
    def _calculate_signal_score(self, signal: StockSignal) -> float:
        """
        计算信号综合评分 - 改进版
        使用多维度精细化评分，提高区分度
        """
        score = 0.0
        
        # 1. 背驰基础可靠度 (30分)
        score += signal.reliability * 30
        
        # 2. 背驰强度细分评分 (25分) - 基于面积比
        area_ratio_score = self._calculate_area_ratio_score(signal.description)
        score += area_ratio_score
        
        # 3. 价格背离度评分 (20分) - 基于价差百分比  
        price_divergence_score = self._calculate_price_divergence_score(signal.description)
        score += price_divergence_score
        
        # 4. MACD技术指标质量 (15分)
        macd_quality_score = self._calculate_macd_quality_score(signal)
        score += macd_quality_score
        
        # 5. 风险回报比评分 (10分)
        risk_reward_score = self._calculate_risk_reward_score(signal)
        score += risk_reward_score
        
        # 添加小数位精度，避免完全相同的分数
        precision_adjustment = hash(signal.symbol) % 100 / 10000  # 0-0.0099的微调
        score += precision_adjustment
        
        return min(score, 100.0)
    
    def _calculate_area_ratio_score(self, description: str) -> float:
        """
        基于MACD面积比计算评分
        面积比越大，背驰越显著，得分越高
        """
        try:
            # 从描述中提取面积比 "面积比7.74"
            import re
            match = re.search(r'面积比([\d.]+)', description)
            if not match:
                return 12.5  # 默认中等分数
            
            area_ratio = float(match.group(1))
            
            # 面积比评分规则：
            # 5-10: 基础分 10-15分
            # 10-20: 优秀分 15-20分  
            # 20-50: 极佳分 20-25分
            # >50: 满分 25分
            if area_ratio >= 50:
                return 25.0
            elif area_ratio >= 20:
                return 20.0 + (area_ratio - 20) / 30 * 5  # 20-25分
            elif area_ratio >= 10:
                return 15.0 + (area_ratio - 10) / 10 * 5  # 15-20分
            elif area_ratio >= 5:
                return 10.0 + (area_ratio - 5) / 5 * 5    # 10-15分
            else:
                return 5.0 + area_ratio                    # 5-10分
                
        except:
            return 12.5  # 解析失败时给默认分
    
    def _calculate_price_divergence_score(self, description: str) -> float:
        """
        基于价格背离度计算评分
        价差越大，背驰越明显，得分越高
        """
        try:
            # 从描述中提取价差 "价差1.2%"
            import re
            match = re.search(r'价差([\d.]+)%', description)
            if not match:
                return 10.0  # 默认中等分数
            
            price_diff_pct = float(match.group(1))
            
            # 价差评分规则：
            # 0-0.5%: 5-10分 (背离较小)
            # 0.5-1.0%: 10-15分 (背离中等)
            # 1.0-2.0%: 15-20分 (背离显著)
            # >2.0%: 满分 20分 (背离极强)
            if price_diff_pct >= 2.0:
                return 20.0
            elif price_diff_pct >= 1.0:
                return 15.0 + (price_diff_pct - 1.0) * 5  # 15-20分
            elif price_diff_pct >= 0.5:
                return 10.0 + (price_diff_pct - 0.5) * 10 # 10-15分
            else:
                return 5.0 + price_diff_pct * 10          # 5-10分
                
        except:
            return 10.0  # 解析失败时给默认分
    
    def _calculate_macd_quality_score(self, signal: StockSignal) -> float:
        """
        计算MACD技术指标质量评分
        """
        score = 0.0
        
        # 基础金叉/死叉确认 (10分)
        if signal.signal_type == "买入" and signal.has_macd_golden_cross:
            score += 10.0
        elif signal.signal_type == "卖出" and signal.has_macd_death_cross:
            score += 10.0
        else:
            score += 5.0  # 没有技术确认的信号降分
        
        # 信号明确性 (5分)
        if signal.signal_type in ["买入", "卖出"]:
            score += 5.0
        
        return score
    
    def _calculate_risk_reward_score(self, signal: StockSignal) -> float:
        """
        计算风险回报比评分
        """
        if not signal.entry_price or not signal.stop_loss or not signal.take_profit:
            return 5.0  # 默认分数
        
        try:
            # 计算风险回报比
            risk = abs(signal.entry_price - signal.stop_loss)
            reward = abs(signal.take_profit - signal.entry_price)
            
            if risk <= 0:
                return 5.0
            
            risk_reward_ratio = reward / risk
            
            # 风险回报比评分：
            # <1.5: 2-5分 (风险过高)
            # 1.5-2.0: 5-7分 (一般)
            # 2.0-3.0: 7-9分 (良好) 
            # >3.0: 9-10分 (优秀)
            if risk_reward_ratio >= 3.0:
                return 10.0
            elif risk_reward_ratio >= 2.0:
                return 7.0 + (risk_reward_ratio - 2.0) * 2  # 7-9分
            elif risk_reward_ratio >= 1.5:
                return 5.0 + (risk_reward_ratio - 1.5) * 4  # 5-7分
            else:
                return 2.0 + risk_reward_ratio * 2           # 2-5分
                
        except:
            return 5.0
    
    def _determine_signal_strength(self, score: float) -> SignalStrength:
        """确定信号强度"""
        if score >= 80:
            return SignalStrength.STRONG
        elif score >= 60:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK
    
    def _generate_recommendation(self, signal: StockSignal) -> str:
        """生成投资建议"""
        if signal.signal_type == "买入":
            if signal.signal_strength == SignalStrength.STRONG:
                return "强烈推荐买入"
            elif signal.signal_strength == SignalStrength.MEDIUM:
                return "建议买入"
            else:
                return "谨慎买入"
        elif signal.signal_type == "卖出":
            if signal.signal_strength == SignalStrength.STRONG:
                return "强烈推荐卖出"
            elif signal.signal_strength == SignalStrength.MEDIUM:
                return "建议卖出"
            else:
                return "谨慎卖出"
        else:
            return "观望"
    
    def _calculate_key_prices(self, signal: StockSignal, klines: KLineList):
        """计算关键价位"""
        if len(klines) == 0:
            return
        
        current_price = klines[-1].close
        signal.entry_price = current_price
        
        if signal.signal_type == "买入":
            # 止损价：入场价的95%
            signal.stop_loss = current_price * 0.95
            # 止盈价：根据背驰强度确定
            profit_ratio = 1 + signal.reliability * 0.15
            signal.take_profit = current_price * profit_ratio
            
        elif signal.signal_type == "卖出":
            # 止损价：入场价的105%
            signal.stop_loss = current_price * 1.05
            # 止盈价：根据背驰强度确定
            profit_ratio = 1 - signal.reliability * 0.15
            signal.take_profit = current_price * profit_ratio
    
    def run_stock_selection(self, max_results: int = 50) -> List[StockSignal]:
        """执行选股（基于简化MACD背驰算法）"""
        logger.info("🎯 开始执行简化MACD背驰选股")
        
        stock_pool = self.get_stock_pool()
        if not stock_pool:
            logger.warning("⚠️ 股票池为空")
            return []
        
        signals = []
        processed_count = 0
        
        # 如果max_stocks_per_batch为0，则处理所有股票，否则按配置限制
        stock_limit = len(stock_pool) if self.config['max_stocks_per_batch'] == 0 else self.config['max_stocks_per_batch']
        
        for stock in stock_pool[:stock_limit]:
            try:
                symbol = stock['symbol']
                name = stock['name']
                
                logger.debug(f"📊 分析股票: {symbol} - {name}")
                
                # 分析背驰信号
                signal = self.analyze_stock_backchi(symbol)
                
                if signal:
                    signals.append(signal)
                
                processed_count += 1
                
                # 每100只股票报告一次进度
                if processed_count % 100 == 0:
                    logger.info(f"📈 已处理 {processed_count}/{stock_limit} 只股票，发现 {len(signals)} 个信号")
                
            except Exception as e:
                logger.error(f"❌ 处理股票 {stock['symbol']} 失败: {e}")
                continue
        
        # 按评分排序
        signals.sort(key=lambda x: x.overall_score, reverse=True)
        
        # 返回前N个结果
        results = signals[:max_results]
        
        logger.info(f"🎯 选股完成: 处理了 {processed_count} 只股票，筛选出 {len(results)} 个信号")
        
        return results
    
    def _fetch_stock_data(self, symbol: str, time_level: TimeLevel, days: int):
        """获取股票数据（通过 Tushare API）"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            if time_level == TimeLevel.DAILY:
                freq = 'daily'
            elif time_level == TimeLevel.MIN_30:
                freq = '30min'
            elif time_level == TimeLevel.MIN_60:
                freq = '60min'
            elif time_level == TimeLevel.MIN_5:
                freq = '5min'
            else:
                freq = 'daily'
            
            df = get_finance_data_gateway().pro_bar(
                ts_code=symbol, asset='E',
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                freq=freq
            )
            
            if df is None or df.empty:
                logger.debug(f"📊 {symbol} 无{time_level.value}数据")
                return None
            
            # 转换为缠论引擎需要的格式
            data = []
            if time_level == TimeLevel.DAILY:
                df = df.sort_values('trade_date').reset_index(drop=True)
                for _, row in df.iterrows():
                    try:
                        data.append({
                            'timestamp': datetime.strptime(str(row['trade_date']), '%Y%m%d'),
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row.get('vol', row.get('amount', 0)))
                        })
                    except Exception:
                        continue
            else:
                df = df.sort_values('trade_time').reset_index(drop=True)
                for _, row in df.iterrows():
                    try:
                        val = row['trade_time']
                        if isinstance(val, str):
                            ts_obj = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                        else:
                            ts_obj = val.to_pydatetime()
                        data.append({
                            'timestamp': ts_obj,
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row.get('vol', row.get('amount', 0)))
                        })
                    except Exception:
                        continue
            
            logger.debug(f"📊 {symbol} 获取到 {len(data)} 条{time_level.value}数据")
            return data
            
        except Exception as e:
            logger.error(f"❌ 获取股票数据失败 {symbol}: {e}")
            return None


# 向后兼容的类名
BackchiStockSelector = SimpleBackchiStockSelector


if __name__ == "__main__":
    # 测试选股器
    selector = SimpleBackchiStockSelector()
    results = selector.run_stock_selection(max_results=10)
    
    print("\n🎯 选股结果:")
    for i, signal in enumerate(results, 1):
        print(f"{i}. {signal.symbol} - {signal.name}")
        print(f"   信号: {signal.signal_type}, 评分: {signal.overall_score:.1f}, 强度: {signal.signal_strength.value}")
        print(f"   建议: {signal.recommendation}")
        print(f"   描述: {signal.description}")
        if signal.entry_price:
            print(f"   入场价: {signal.entry_price:.2f}, 止损: {signal.stop_loss:.2f}, 止盈: {signal.take_profit:.2f}")
        print()