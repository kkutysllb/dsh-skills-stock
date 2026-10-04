#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论配置管理
参考Vespa314/chan.py的配置设计思路，提供完整的缠论分析参数配置
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from decimal import Decimal


@dataclass
class KlineConfig:
    """K线处理配置"""
    # 包含关系处理
    enable_include_process: bool = True          # 是否启用包含关系处理
    include_gap_ratio: float = 0.001            # 包含关系判断的最小间隙比例
    
    # 数据清洗
    enable_data_clean: bool = True               # 是否启用数据清洗
    max_gap_ratio: float = 0.2                  # 最大跳空比例（超过则视为异常）
    min_volume_threshold: int = 1000             # 最小成交量阈值


@dataclass
class FenXingConfig:
    """分型识别配置"""
    # 基础参数
    min_window_size: int = 3                     # 最小分型识别窗口大小
    default_left_size: int = 2                  # 默认左侧K线数量
    default_right_size: int = 2                 # 默认右侧K线数量
    min_strength: float = 0.002                 # 分型最小强度阈值
    min_gap_bars: int = 1                       # 分型间最小间隔K线数
    
    # 识别模式
    strict_mode: bool = True                     # 严格模式：要求严格高低点
    enable_optimization: bool = True             # 启用连续同类型分型优化
    
    # 确认参数
    enable_volume_confirm: bool = False          # 是否启用成交量确认
    volume_ratio_threshold: float = 1.2         # 成交量确认比例阈值
    confirm_window: int = 3                     # 后续确认窗口大小
    
    # 过滤参数
    enable_noise_filter: bool = True             # 启用噪音过滤
    noise_threshold: float = 0.001              # 噪音阈值
    min_confidence: float = 0.5                 # 最小置信度阈值


@dataclass  
class BiConfig:
    """笔构建配置"""
    # 基础参数
    min_length: int = 3                          # 笔的最小长度(K线数)
    min_amplitude: float = 0.005                # 笔的最小幅度
    
    # 笔的有效性验证
    enable_direction_check: bool = True          # 启用方向一致性检查
    enable_strength_check: bool = True           # 启用强度检查
    min_strength_ratio: float = 0.618           # 最小强度比例(黄金分割)
    
    # 笔的优化
    enable_optimize: bool = True                 # 启用笔优化
    optimize_merge_threshold: float = 0.002     # 合并阈值


@dataclass
class SegConfig:
    """线段识别配置"""
    # 基础参数  
    min_bi_count: int = 3                        # 线段最少包含笔数
    break_threshold: float = 0.01               # 线段破坏阈值
    
    # 线段类型
    seg_algo: str = "classic"                    # 线段算法: classic/enhanced/dyhyh
    enable_gap_seg: bool = True                  # 启用跳空线段
    
    # 特征序列
    enable_feature_seq: bool = True              # 启用特征序列
    feature_threshold: float = 0.005             # 特征序列阈值


@dataclass
class ZhongShuConfig:
    """中枢识别配置"""
    # 基础参数
    min_overlap_ratio: float = 0.01             # 最小重叠比例
    min_duration: int = 3                        # 最小持续时间(K线数)
    
    # 中枢扩展
    enable_extend: bool = True                   # 启用中枢扩展
    extend_threshold: float = 0.02               # 扩展阈值
    max_extend_count: int = 9                    # 最大扩展次数
    
    # 中枢级别
    enable_level_calc: bool = True               # 启用级别计算
    level_threshold_ratio: float = 3.0          # 级别阈值比例


@dataclass
class MultiLevelConfig:
    """多级别分析配置"""
    # 级别设置
    levels: List[str] = field(default_factory=lambda: ["5min", "30min", "daily"])
    primary_level: str = "30min"                 # 主级别
    
    # 联立分析
    enable_resonance: bool = True                # 启用共振分析
    resonance_threshold: float = 0.7            # 共振阈值
    
    # 级别映射
    enable_level_mapping: bool = True            # 启用级别映射
    mapping_ratio_threshold: float = 3.0        # 映射比例阈值


@dataclass
class BuySellConfig:
    """买卖点配置"""
    # 买卖点类型
    enable_type1: bool = True                    # 启用一类买卖点
    enable_type2: bool = True                    # 启用二类买卖点  
    enable_type3: bool = True                    # 启用三类买卖点
    
    # 背驰判断
    divergence_method: str = "macd"              # 背驰判断方法: macd/volume/strength
    divergence_threshold: float = 0.1           # 背驰阈值
    
    # 确认机制
    enable_multi_confirm: bool = True            # 启用多重确认
    confirm_levels_count: int = 2                # 确认级别数量


@dataclass
class PerformanceConfig:
    """性能优化配置"""
    # 缓存设置
    enable_cache: bool = True                    # 启用缓存
    cache_size: int = 1000                       # 缓存大小
    cache_ttl: int = 3600                        # 缓存TTL(秒)
    
    # 并行计算
    enable_parallel: bool = False                # 启用并行计算
    max_workers: int = 4                         # 最大工作线程数
    
    # 内存管理
    enable_memory_limit: bool = True             # 启用内存限制
    max_memory_mb: int = 512                     # 最大内存使用量(MB)


@dataclass
class ChanConfig:
    """
    缠论完整配置类
    参考Vespa314/chan.py的配置架构设计
    """
    # 子配置模块
    kline: KlineConfig = field(default_factory=KlineConfig)
    fenxing: FenXingConfig = field(default_factory=FenXingConfig)
    bi: BiConfig = field(default_factory=BiConfig)  
    seg: SegConfig = field(default_factory=SegConfig)
    zhongshu: ZhongShuConfig = field(default_factory=ZhongShuConfig)
    multi_level: MultiLevelConfig = field(default_factory=MultiLevelConfig)  
    buy_sell: BuySellConfig = field(default_factory=BuySellConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # 全局配置
    symbol: str = ""                             # 股票代码
    debug_mode: bool = False                     # 调试模式
    log_level: str = "INFO"                      # 日志级别
    
    @classmethod
    def create_default(cls) -> 'ChanConfig':
        """创建默认配置"""
        return cls()
    
    @classmethod  
    def create_conservative(cls) -> 'ChanConfig':
        """创建保守配置 - 更严格的参数，减少假信号"""
        config = cls()
        
        # 更严格的分型要求
        config.fenxing.min_strength = 0.005
        config.fenxing.strict_mode = True
        config.fenxing.enable_volume_confirm = True
        config.fenxing.min_confidence = 0.8
        
        # 更严格的笔要求
        config.bi.min_length = 5
        config.bi.min_amplitude = 0.01
        config.bi.min_strength_ratio = 0.8
        
        # 更严格的线段要求
        config.seg.min_bi_count = 5
        config.seg.break_threshold = 0.02
        
        # 更严格的买卖点要求
        config.buy_sell.enable_multi_confirm = True
        config.buy_sell.confirm_levels_count = 3
        config.buy_sell.divergence_threshold = 0.15
        
        return config
    
    @classmethod
    def create_aggressive(cls) -> 'ChanConfig':
        """创建激进配置 - 更敏感的参数，捕获更多机会"""
        config = cls()
        
        # 更敏感的分型要求
        config.fenxing.min_strength = 0.001
        config.fenxing.strict_mode = False
        config.fenxing.min_gap_bars = 0
        config.fenxing.min_confidence = 0.3
        
        # 更敏感的笔要求  
        config.bi.min_length = 1
        config.bi.min_amplitude = 0.002
        config.bi.min_strength_ratio = 0.5
        
        # 更敏感的线段要求
        config.seg.min_bi_count = 2  
        config.seg.break_threshold = 0.005
        
        # 更敏感的买卖点要求
        config.buy_sell.enable_multi_confirm = False
        config.buy_sell.divergence_threshold = 0.05
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChanConfig':
        """从字典创建配置"""
        # 简化实现，实际项目中可能需要更复杂的反序列化逻辑
        return cls(**data)
    
    def validate(self) -> List[str]:
        """验证配置的有效性"""
        errors = []
        
        # 验证分型配置
        if self.fenxing.min_window_size < 3:
            errors.append("分型最小窗口大小必须大于等于3")
        if self.fenxing.min_strength < 0:
            errors.append("分型最小强度不能为负数")
        if self.fenxing.min_confidence < 0 or self.fenxing.min_confidence > 1:
            errors.append("分型最小置信度必须在[0,1]区间")
            
        # 验证笔配置
        if self.bi.min_length < 1:
            errors.append("笔最小长度必须大于0")
        if self.bi.min_amplitude < 0:
            errors.append("笔最小幅度不能为负数")
            
        # 验证线段配置
        if self.seg.min_bi_count < 2:
            errors.append("线段最少笔数必须大于1")
            
        # 验证中枢配置
        if self.zhongshu.min_overlap_ratio <= 0 or self.zhongshu.min_overlap_ratio >= 1:
            errors.append("中枢最小重叠比例必须在(0,1)区间")
            
        # 验证多级别配置
        if len(self.multi_level.levels) < 1:
            errors.append("至少需要一个分析级别")
        if self.multi_level.primary_level not in self.multi_level.levels:
            errors.append("主级别必须在级别列表中")
            
        return errors
    
    def __str__(self) -> str:
        """配置摘要"""
        return f"""缠论配置摘要:
        分型: 窗口≥{self.fenxing.min_window_size}, 强度≥{self.fenxing.min_strength}, 置信度≥{self.fenxing.min_confidence}
        笔: 长度≥{self.bi.min_length}, 幅度≥{self.bi.min_amplitude}  
        线段: 笔数≥{self.seg.min_bi_count}, 破坏阈值{self.seg.break_threshold}
        中枢: 重叠≥{self.zhongshu.min_overlap_ratio}, 扩展≤{self.zhongshu.max_extend_count}次
        级别: {', '.join(self.multi_level.levels)} (主:{self.multi_level.primary_level})
        """