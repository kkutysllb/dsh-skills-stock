#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论K线处理器
参考Vespa314/chan.py的K线处理逻辑，实现标准的包含关系处理
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime

from ..models.kline import KLine, KLineList
from ..models.fenxing import FenXing, FenXingList
from ..models.enums import TimeLevel, FenXingType
from ..config.chan_config import ChanConfig, KlineConfig

logger = logging.getLogger(__name__)


class KlineProcessor:
    """
    K线处理器
    负责K线数据的清洗、验证和包含关系处理
    """
    
    def __init__(self, config: ChanConfig):
        """
        初始化K线处理器
        
        Args:
            config: 缠论配置
        """
        self.config = config
        self.kline_config = config.kline
        self.fenxing_config = config.fenxing
        
    def process_klines(self, klines: KLineList) -> Tuple[KLineList, FenXingList]:
        """
        处理K线数据
        包括数据验证、清洗、包含关系处理和分型识别
        
        Args:
            klines: 原始K线列表
            
        Returns:
            (处理后的K线列表, 分型列表)
        """
        if klines.is_empty():
            logger.warning("输入K线数据为空")
            return KLineList([], klines.level), FenXingList([], klines.level)
        
        level_name = klines.level.value if klines.level else 'unknown'
        logger.info(f"====== 开始处理{level_name}级别K线数据 ======")
        logger.info(f"原始K线数量: {len(klines)}根")
        logger.info(f"处理配置: 包含关系处理={self.kline_config.enable_include_process}, 数据清洗={self.kline_config.enable_data_clean}")
        
        # 记录处理开始时间
        import time
        start_time = time.time()
        
        # 1. 输入数据初步验证
        input_errors = self._validate_input_data(klines)
        if input_errors:
            logger.warning(f"输入数据存在{len(input_errors)}个问题: {input_errors[:3]}..." if len(input_errors) > 3 else f"输入数据问题: {input_errors}")
        
        # 2. 数据验证和清洗
        logger.info("--- 步骤1: 数据清洗和验证 ---")
        cleaned_klines = self._clean_and_validate(klines)
        if cleaned_klines.is_empty():
            logger.error("K线数据清洗后为空，处理终止")
            return cleaned_klines, FenXingList([], klines.level)
        
        logger.info(f"清洗结果: {len(klines)} -> {len(cleaned_klines)}根K线")
        
        # 3. 处理包含关系（缠论核心步骤）
        logger.info("--- 步骤2: 包含关系处理 ---")
        if self.kline_config.enable_include_process:
            processed_klines = self._process_include_relationship(cleaned_klines)
            
            # 验证包含关系处理结果
            validation_errors = self.validate_processed_klines(processed_klines)
            if validation_errors:
                logger.error(f"包含关系处理后验证失败: {validation_errors}")
        else:
            logger.info("跳过包含关系处理（配置已禁用）")
            processed_klines = cleaned_klines
        
        logger.info(f"包含关系处理结果: {len(cleaned_klines)} -> {len(processed_klines)}根K线")
        
        # 4. 分型识别（重要：必须基于合并包含关系后的K线进行分型识别）
        logger.info("--- 步骤3: 分型识别（基于合并后K线） ---")
        fenxings = FenXingList([], processed_klines.level)
        if self.fenxing_config and len(processed_klines) >= self.fenxing_config.min_window_size:
            # 关键：使用processed_klines（已合并包含关系）而非原始klines
            fenxings = self._identify_fenxings(processed_klines)
            logger.info(f"基于{len(processed_klines)}根合并后K线识别分型")
        else:
            logger.info(f"跳过分型识别: K线数量{len(processed_klines)} < 最小窗口{self.fenxing_config.min_window_size if self.fenxing_config else 'N/A'}")
        
        # 5. 缺口成笔处理（缠论标准）
        logger.info("--- 步骤4: 缺口成笔分析 ---")
        gap_fenxings = self._analyze_gaps_and_create_fenxings(processed_klines)
        if gap_fenxings:
            # 将缺口形成的分型合并到原有分型列表中
            all_fenxings = fenxings.fenxings + gap_fenxings
            # 按时间排序并去重
            all_fenxings.sort(key=lambda x: x.timestamp)
            fenxings = FenXingList(all_fenxings, processed_klines.level)
            logger.info(f"缺口分析: 发现{len(gap_fenxings)}个缺口成笔分型，总分型数: {len(fenxings)}")
        else:
            logger.info("缺口分析: 未发现符合成笔条件的缺口")
        
        # 5. 生成处理统计
        end_time = time.time()
        processing_time = end_time - start_time
        stats = self.get_processing_statistics(klines, processed_klines, fenxings)
        
        logger.info("--- 处理完成统计 ---")
        logger.info(f"总耗时: {processing_time:.3f}秒")
        logger.info(f"K线压缩率: {stats['reduction_ratio']:.1%} ({stats['original_count']} -> {stats['processed_count']})")
        logger.info(f"平均合并数: {stats['avg_merge_count']:.1f}根/K线")
        logger.info(f"识别分型: {stats['fenxing_count']}个 (比例: {stats['fenxing_ratio']:.1%})")
        logger.info(f"====== {level_name}级别K线处理完成 ======")
        
        return processed_klines, fenxings
    
    def _clean_and_validate(self, klines: KLineList) -> KLineList:
        """
        清洗和验证K线数据
        
        Args:
            klines: 原始K线列表
            
        Returns:
            清洗后的K线列表
        """
        if not self.kline_config.enable_data_clean:
            return klines
        
        cleaned = []
        removed_count = 0
        
        for i, kline in enumerate(klines):
            try:
                # 基础数据验证
                if not self._is_valid_kline(kline):
                    removed_count += 1
                    continue
                
                # 异常数据检查
                if i > 0 and self._is_abnormal_kline(klines[i-1], kline):
                    logger.warning(f"发现异常K线: {kline.timestamp}, 跳空比例过大")
                    if self.kline_config.max_gap_ratio < 0.5:  # 严格模式下移除异常数据
                        removed_count += 1
                        continue
                
                cleaned.append(kline)
                
            except Exception as e:
                logger.error(f"验证K线数据时出错: {e}, 跳过该K线")
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"数据清洗：移除{removed_count}根异常K线")
        
        return KLineList(cleaned, klines.level)
    
    def _is_valid_kline(self, kline: KLine) -> bool:
        """
        检查K线数据是否有效
        
        Args:
            kline: K线数据
            
        Returns:
            是否有效
        """
        try:
            # 基础数据完整性检查
            if any(x <= 0 for x in [kline.open, kline.high, kline.low, kline.close]):
                return False
            
            # OHLC逻辑检查
            if kline.high < max(kline.open, kline.close):
                return False
            if kline.low > min(kline.open, kline.close):
                return False
            
            # 成交量检查
            if kline.volume < self.kline_config.min_volume_threshold:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _is_abnormal_kline(self, prev_kline: KLine, current_kline: KLine) -> bool:
        """
        检查是否为异常K线（如跳空过大）
        
        Args:
            prev_kline: 前一根K线
            current_kline: 当前K线
            
        Returns:
            是否异常
        """
        # 计算跳空比例
        prev_close = prev_kline.close
        current_open = current_kline.open
        
        if prev_close > 0:
            gap_ratio = abs(current_open - prev_close) / prev_close
            return gap_ratio > self.kline_config.max_gap_ratio
        
        return False
    
    def _process_include_relationship(self, klines: KLineList) -> KLineList:
        """
        处理K线包含关系
        这是缠论的核心处理步骤之一
        采用循环处理确保所有包含关系都被完全处理
        
        Args:
            klines: 原始K线列表
            
        Returns:
            处理包含关系后的K线列表
        """
        if len(klines) <= 1:
            logger.debug("K线数量<=1，跳过包含关系处理")
            return klines
        
        logger.debug(f"开始处理包含关系，输入{len(klines)}根K线")
        
        processed = []
        merge_count = 0
        iteration_count = 0
        max_continuous_merges = 0
        current_continuous_merges = 0
        
        # 第一根K线直接添加
        processed.append(klines[0])
        logger.debug(f"添加第一根K线: {klines[0].timestamp} OHLC=({klines[0].open:.2f},{klines[0].high:.2f},{klines[0].low:.2f},{klines[0].close:.2f})")
        
        i = 1
        while i < len(klines):
            iteration_count += 1
            current_kline = klines[i]
            
            logger.debug(f"\n--- 处理第{i+1}根K线 (索引{i}) ---")
            logger.debug(f"当前K线: {current_kline.timestamp} OHLC=({current_kline.open:.2f},{current_kline.high:.2f},{current_kline.low:.2f},{current_kline.close:.2f})")
            
            # 从已处理的K线末尾开始，向前检查包含关系
            merged_with_existing = False
            merge_depth = 0
            
            # 检查当前K线与最后一根已处理K线的包含关系
            while len(processed) > 0:
                last_processed = processed[-1]
                
                # 检查是否存在包含关系
                relationship = self._check_include_relationship(last_processed, current_kline)
                
                logger.debug(f"检查包含关系: 已处理K线({last_processed.high:.2f},{last_processed.low:.2f}) vs 当前K线({current_kline.high:.2f},{current_kline.low:.2f}) = {relationship}")
                
                if relationship == "none":
                    # 无包含关系，跳出循环
                    logger.debug("无包含关系，添加到处理列表")
                    break
                else:
                    # 存在包含关系，需要合并
                    merge_count += 1
                    merge_depth += 1
                    current_continuous_merges += 1
                    max_continuous_merges = max(max_continuous_merges, current_continuous_merges)
                    
                    trend_direction = self._determine_trend_direction(processed)
                    logger.debug(f"确定趋势方向: {'向上' if trend_direction else '向下'}")
                    
                    merged_kline = self._merge_klines(last_processed, current_kline, 
                                                    relationship, trend_direction)
                    
                    logger.debug(f"合并结果: OHLC=({merged_kline.open:.2f},{merged_kline.high:.2f},{merged_kline.low:.2f},{merged_kline.close:.2f}) 原始数量={merged_kline.original_count}")
                    
                    # 移除最后一根K线，用合并后的K线替代当前K线
                    processed.pop()
                    current_kline = merged_kline
                    merged_with_existing = True
                    
                    # 继续检查合并后的K线是否与前一根还有包含关系
                    logger.debug(f"继续检查合并后K线是否与前面还有包含关系 (合并深度: {merge_depth})")
            
            if not merged_with_existing:
                current_continuous_merges = 0  # 重置连续合并计数
            
            # 将处理后的K线添加到结果中
            processed.append(current_kline)
            logger.debug(f"最终添加K线: OHLC=({current_kline.open:.2f},{current_kline.high:.2f},{current_kline.low:.2f},{current_kline.close:.2f}) 包含{current_kline.original_count}根原始K线")
            
            i += 1
        
        # 最后再做一轮完整性检查和处理
        logger.debug("\n--- 执行最终完整性检查 ---")
        processed = self._final_include_check(processed)
        
        result = KLineList(processed, klines.level)
        result._is_processed = True
        
        logger.info(f"包含关系处理统计: {len(klines)} -> {len(processed)}根K线")
        logger.info(f"合并操作: {merge_count}次, 迭代: {iteration_count}次")
        logger.info(f"最大连续合并: {max_continuous_merges}根K线")
        
        return result
    
    def _check_include_relationship(self, kline1: KLine, kline2: KLine) -> str:
        """
        检查两根K线的包含关系，包含边界情况处理
        
        缠论标准定义：如果K线A的高点>=K线B的高点且K线A的低点<=K线B的低点，则A包含B
        
        Args:
            kline1: 第一根K线
            kline2: 第二根K线
            
        Returns:
            包含关系类型: "none", "k1_contains_k2", "k2_contains_k1"
        """
        # 数据有效性检查
        if not self._is_valid_kline_for_include(kline1) or not self._is_valid_kline_for_include(kline2):
            logger.warning(f"K线数据无效，跳过包含关系检查: K1({kline1.high},{kline1.low}) K2({kline2.high},{kline2.low})")
            return "none"
        
        # 严格的包含关系判断（缠论标准）
        # K线1包含K线2：K1的高点>=K2的高点 且 K1的低点<=K2的低点
        k1_contains_k2 = (kline1.high >= kline2.high and kline1.low <= kline2.low)
        
        # K线2包含K线1：K2的高点>=K1的高点 且 K2的低点<=K1的低点
        k2_contains_k1 = (kline2.high >= kline1.high and kline2.low <= kline1.low)
        
        if k1_contains_k2 and not k2_contains_k1:
            logger.debug(f"K1包含K2: K1({kline1.high:.2f},{kline1.low:.2f}) 包含 K2({kline2.high:.2f},{kline2.low:.2f})")
            return "k1_contains_k2"
        elif k2_contains_k1 and not k1_contains_k2:
            logger.debug(f"K2包含K1: K2({kline2.high:.2f},{kline2.low:.2f}) 包含 K1({kline1.high:.2f},{kline1.low:.2f})")
            return "k2_contains_k1"
        elif k1_contains_k2 and k2_contains_k1:
            # 两根K线完全重合，选择成交量大的或时间较新的
            if kline1.volume != kline2.volume:
                result = "k1_contains_k2" if kline1.volume >= kline2.volume else "k2_contains_k1"
                logger.debug(f"K线完全重合，按成交量选择: V1={kline1.volume} V2={kline2.volume} -> {result}")
            else:
                # 成交量相同，选择时间较新的
                result = "k1_contains_k2" if kline1.timestamp >= kline2.timestamp else "k2_contains_k1"
                logger.debug(f"K线完全重合，按时间选择: T1={kline1.timestamp} T2={kline2.timestamp} -> {result}")
            return result
        else:
            return "none"
    
    def _is_valid_kline_for_include(self, kline: KLine) -> bool:
        """
        检查K线是否适合进行包含关系判断
        
        Args:
            kline: K线对象
            
        Returns:
            是否有效
        """
        if kline.high <= 0 or kline.low <= 0:
            return False
        
        if kline.high < kline.low:
            return False
        
        # 检查是否为异常的零幅度K线
        if abs(kline.high - kline.low) < 1e-8:
            logger.debug(f"发现零幅度K线: {kline.timestamp} H={kline.high} L={kline.low}")
            # 零幅度K线仍然可以参与包含关系判断
            return True
        
        return True
    
    def _determine_trend_direction(self, processed_klines: List[KLine]) -> bool:
        """
        按照缠论标准确定当前趋势方向
        
        缠论方向判断标准：
        - hi > hi-1 且 li > li-1：方向向上
        - hi < hi-1 且 li < li-1：方向向下
        - 其他情况（包含关系或横盘）：查找上一个非包含关系的K线确定方向
        
        Args:
            processed_klines: 已处理的K线列表
            
        Returns:
            True表示上升趋势，False表示下降趋势
        """
        if len(processed_klines) < 2:
            return True  # 默认为上升趋势
        
        current = processed_klines[-1]
        previous = processed_klines[-2]
        
        # 缠论标准方向判断
        if current.high > previous.high and current.low > previous.low:
            # hi > hi-1 且 li > li-1：明确向上
            logger.debug(f"明确向上: H{current.high:.2f}>{previous.high:.2f} 且 L{current.low:.2f}>{previous.low:.2f}")
            return True
        elif current.high < previous.high and current.low < previous.low:
            # hi < hi-1 且 li < li-1：明确向下
            logger.debug(f"明确向下: H{current.high:.2f}<{previous.high:.2f} 且 L{current.low:.2f}<{previous.low:.2f}")
            return False
        else:
            # 存在包含关系或横盘，需要查找上一个非包含关系的K线
            logger.debug(f"包含关系或横盘: H{current.high:.2f}vs{previous.high:.2f}, L{current.low:.2f}vs{previous.low:.2f}")
            return self._find_previous_trend_direction(processed_klines)
    
    def _find_previous_trend_direction(self, processed_klines: List[KLine]) -> bool:
        """
        当存在包含关系时，查找上一个非包含关系的K线来确定趋势方向
        
        Args:
            processed_klines: 已处理的K线列表
            
        Returns:
            True表示上升趋势，False表示下降趋势
        """
        if len(processed_klines) < 3:
            return True  # 默认向上
        
        current = processed_klines[-1]
        
        # 向前查找非包含关系的K线
        for i in range(len(processed_klines) - 2, 0, -1):
            reference = processed_klines[i - 1]
            
            # 检查是否为非包含关系
            if not self._has_include_relation_simple(reference, processed_klines[i]):
                # 找到非包含关系的K线，用它来判断方向
                if current.high > reference.high and current.low > reference.low:
                    logger.debug(f"参考K线判断向上: 当前({current.high:.2f},{current.low:.2f}) vs 参考({reference.high:.2f},{reference.low:.2f})")
                    return True
                elif current.high < reference.high and current.low < reference.low:
                    logger.debug(f"参考K线判断向下: 当前({current.high:.2f},{current.low:.2f}) vs 参考({reference.high:.2f},{reference.low:.2f})")
                    return False
                else:
                    # 继续向前查找
                    continue
        
        # 如果找不到合适的参考K线，使用简单判断
        previous = processed_klines[-2]
        result = current.high >= previous.high
        logger.debug(f"默认判断: H{current.high:.2f}>={previous.high:.2f} = {result}")
        return result
    
    def _has_include_relation_simple(self, kline1: KLine, kline2: KLine) -> bool:
        """
        简单的包含关系检查（用于趋势判断）
        
        Args:
            kline1: 第一根K线
            kline2: 第二根K线
            
        Returns:
            是否存在包含关系
        """
        return ((kline1.high >= kline2.high and kline1.low <= kline2.low) or
                (kline2.high >= kline1.high and kline2.low <= kline1.low))
    
    def _merge_klines(self, kline1: KLine, kline2: KLine, 
                     relationship: str, trend_up: bool) -> KLine:
        """
        按照缠论标准合并两根有包含关系的K线
        
        缠论标准合并规则：
        - 向上趋势：高点取两者最高，低点取两者较高者
        - 向下趋势：低点取两者最低，高点取两者较低者
        
        Args:
            kline1: 第一根K线
            kline2: 第二根K线  
            relationship: 包含关系类型
            trend_up: 趋势是否向上
            
        Returns:
            合并后的K线
        """
        # 确定时间戳和开收盘价
        # 在包含关系处理中，应该按照时间顺序来确定开收盘价
        if kline1.timestamp <= kline2.timestamp:
            # kline1在前，kline2在后
            timestamp = kline2.timestamp  # 合并后时间取较晚的
            open_price = kline1.open      # 开盘价取较早的
            close_price = kline2.close    # 收盘价取较晚的
        else:
            # kline2在前，kline1在后
            timestamp = kline1.timestamp  # 合并后时间取较晚的  
            open_price = kline2.open      # 开盘价取较早的
            close_price = kline1.close    # 收盘价取较晚的
        
        # 缠论标准高低点合并规则
        if trend_up:
            # 向上趋势：高点取最高，低点取较高者
            high = max(kline1.high, kline2.high)
            low = max(kline1.low, kline2.low)  # 关键修正：取较高者
            logger.debug(f"向上合并: high=max({kline1.high:.2f},{kline2.high:.2f})={high:.2f}, low=max({kline1.low:.2f},{kline2.low:.2f})={low:.2f}")
        else:
            # 向下趋势：低点取最低，高点取较低者
            high = min(kline1.high, kline2.high)  # 关键修正：取较低者
            low = min(kline1.low, kline2.low)
            logger.debug(f"向下合并: high=min({kline1.high:.2f},{kline2.high:.2f})={high:.2f}, low=min({kline1.low:.2f},{kline2.low:.2f})={low:.2f}")
        
        # 确保合并后的OHLC逻辑正确性
        # 开盘价和收盘价可能超出合并后的高低点范围，需要调整
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # 合并成交量和成交额
        volume = kline1.volume + kline2.volume
        amount = (kline1.amount or 0) + (kline2.amount or 0)
        
        # 合并其他属性
        turnover = None
        if kline1.turnover is not None and kline2.turnover is not None:
            turnover = kline1.turnover + kline2.turnover
        elif kline1.turnover is not None:
            turnover = kline1.turnover
        elif kline2.turnover is not None:
            turnover = kline2.turnover
        
        # 创建合并后的K线
        merged_kline = KLine(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=volume,
            amount=amount if amount > 0 else None,
            turnover=turnover,
            level=kline1.level,
            is_processed=True,
            original_count=kline1.original_count + kline2.original_count
        )
        
        # 合并技术指标（取平均值或最新值）
        merged_indicators = {}
        all_keys = set(kline1.indicators.keys()) | set(kline2.indicators.keys())
        for key in all_keys:
            val1 = kline1.indicators.get(key)
            val2 = kline2.indicators.get(key)
            
            if val1 is not None and val2 is not None:
                merged_indicators[key] = (val1 + val2) / 2  # 取平均值
            elif val1 is not None:
                merged_indicators[key] = val1
            elif val2 is not None:
                merged_indicators[key] = val2
        
        merged_kline.indicators = merged_indicators
        
        return merged_kline
    
    def _final_include_check(self, processed_klines: List[KLine]) -> List[KLine]:
        """
        最终的包含关系完整性检查和处理
        确保没有遗漏的包含关系
        
        Args:
            processed_klines: 已处理的K线列表
            
        Returns:
            最终处理完成的K线列表
        """
        if len(processed_klines) <= 1:
            return processed_klines
        
        max_iterations = 10  # 防止无限循环
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            found_include = False
            
            # 从头开始检查相邻K线的包含关系
            i = 0
            while i < len(processed_klines) - 1:
                current_kline = processed_klines[i]
                next_kline = processed_klines[i + 1]
                
                relationship = self._check_include_relationship(current_kline, next_kline)
                
                if relationship != "none":
                    # 发现包含关系，需要合并
                    found_include = True
                    
                    # 确定趋势方向（基于当前位置前后的K线）
                    trend_direction = True  # 默认上升
                    if i > 0:
                        prev_kline = processed_klines[i - 1]
                        trend_direction = current_kline.high >= prev_kline.high
                    
                    # 合并K线
                    merged_kline = self._merge_klines(current_kline, next_kline, 
                                                    relationship, trend_direction)
                    
                    # 替换当前K线，删除下一根K线
                    processed_klines[i] = merged_kline
                    processed_klines.pop(i + 1)
                    
                    # 不增加i，重新检查当前位置（因为合并后可能与前面的K线产生新的包含关系）
                    if i > 0:
                        i -= 1
                else:
                    i += 1
            
            # 如果这一轮没有发现包含关系，退出循环
            if not found_include:
                break
        
        if iteration >= max_iterations:
            logger.warning(f"包含关系处理达到最大迭代次数{max_iterations}，可能存在复杂的包含关系")
        
        return processed_klines
    
    def _identify_fenxings(self, klines: KLineList) -> FenXingList:
        """
        识别K线序列中的分型
        基于缠论标准的分型识别算法
        
        Args:
            klines: 已处理（合并包含关系）的K线序列
            
        Returns:
            分型列表
        """
        if len(klines) < self.fenxing_config.min_window_size:
            return FenXingList([], klines.level)
        
        fenxings = []
        
        # 使用滑动窗口识别分型
        for i in range(1, len(klines) - 1):  # 分型必须不在序列首尾
            fenxing = self._check_fenxing_at_position(klines, i)
            if fenxing is not None:
                fenxings.append(fenxing)
        
        result = FenXingList(fenxings, klines.level)
        
        # 后处理：优化连续同类型分型
        if self.fenxing_config.enable_optimization:
            result = result.optimize_consecutive_same_type()
        
        # 计算分型强度和置信度
        self._calculate_fenxing_metrics(result)
        
        # 用后续K线确认分型
        self._confirm_fenxings_with_subsequent_klines(result, klines)
        
        logger.info(f"分型识别完成：发现{len(result)}个分型")
        return result
    
    def _check_fenxing_at_position(self, klines: KLineList, center_index: int) -> Optional[FenXing]:
        """
        在指定位置检查是否存在分型
        
        Args:
            klines: K线序列
            center_index: 中心K线索引
            
        Returns:
            分型对象，如果不是分型则返回None
        """
        if center_index <= 0 or center_index >= len(klines) - 1:
            return None
        
        # 确定识别窗口
        left_size = min(self.fenxing_config.default_left_size, center_index)
        right_size = min(self.fenxing_config.default_right_size, len(klines) - center_index - 1)
        
        # 获取窗口内的K线
        center_kline = klines[center_index]
        left_klines = klines[center_index - left_size:center_index]
        right_klines = klines[center_index + 1:center_index + right_size + 1]
        
        # 检查分型模式
        fenxing_type = self._check_fenxing_pattern(center_kline, left_klines, right_klines)
        
        if fenxing_type is None:
            return None
        
        # 创建分型对象
        fenxing = FenXing(
            kline=center_kline,
            fenxing_type=fenxing_type,
            index=center_index,
            left_klines=left_klines,
            right_klines=right_klines
        )
        
        return fenxing
    
    def _check_fenxing_pattern(self, center_kline: KLine, 
                              left_klines: List[KLine], 
                              right_klines: List[KLine]) -> Optional[FenXingType]:
        """
        检查分型模式
        
        Args:
            center_kline: 中心K线
            left_klines: 左侧K线列表
            right_klines: 右侧K线列表
            
        Returns:
            分型类型，如果不是分型则返回None
        """
        if not left_klines or not right_klines:
            return None
        
        # 检查顶分型
        if self._is_top_fenxing(center_kline, left_klines, right_klines):
            return FenXingType.TOP
        
        # 检查底分型  
        if self._is_bottom_fenxing(center_kline, left_klines, right_klines):
            return FenXingType.BOTTOM
        
        return None
    
    def _is_top_fenxing(self, center_kline: KLine, 
                       left_klines: List[KLine], 
                       right_klines: List[KLine]) -> bool:
        """
        判断是否为顶分型
        缠论标准：中心K线的高点是三根K线中最高的，且低点也是三根K线中最高的
        
        Args:
            center_kline: 中心K线  
            left_klines: 左侧K线列表
            right_klines: 右侧K线列表
            
        Returns:
            是否为顶分型
        """
        center_high = center_kline.high
        center_low = center_kline.low
        
        # 检查所有邻近K线
        adjacent_klines = left_klines + right_klines
        
        # 条件1：中心K线高点必须是最高的
        for k in adjacent_klines:
            if self.fenxing_config.strict_mode:
                if k.high >= center_high:  # 严格模式：不允许相等
                    return False
            else:
                if k.high > center_high:   # 宽松模式：允许相等
                    return False
        
        # 条件2：中心K线低点也必须是最高的（关键的缠论条件）
        for k in adjacent_klines:
            if self.fenxing_config.strict_mode:
                if k.low >= center_low:    # 严格模式：不允许相等
                    return False
            else:
                if k.low > center_low:     # 宽松模式：允许相等
                    return False
        
        return True
    
    def _is_bottom_fenxing(self, center_kline: KLine,
                          left_klines: List[KLine],
                          right_klines: List[KLine]) -> bool:
        """
        判断是否为底分型
        缠论标准：中心K线的低点是三根K线中最低的，且高点也是三根K线中最低的
        
        Args:
            center_kline: 中心K线
            left_klines: 左侧K线列表  
            right_klines: 右侧K线列表
            
        Returns:
            是否为底分型
        """
        center_low = center_kline.low
        center_high = center_kline.high
        
        # 检查所有邻近K线
        adjacent_klines = left_klines + right_klines
        
        # 条件1：中心K线低点必须是最低的
        for k in adjacent_klines:
            if self.fenxing_config.strict_mode:
                if k.low <= center_low:    # 严格模式：不允许相等
                    return False
            else:
                if k.low < center_low:     # 宽松模式：允许相等
                    return False
        
        # 条件2：中心K线高点也必须是最低的（关键的缠论条件）
        for k in adjacent_klines:
            if self.fenxing_config.strict_mode:
                if k.high <= center_high:  # 严格模式：不允许相等
                    return False
            else:
                if k.high < center_high:   # 宽松模式：允许相等
                    return False
        
        return True
    
    def _calculate_fenxing_metrics(self, fenxings: FenXingList) -> None:
        """
        计算分型的强度、置信度等指标
        
        Args:
            fenxings: 分型列表
        """
        for fenxing in fenxings:
            # 计算分型强度
            fenxing.calculate_strength()
            
            # 计算成交量比例
            fenxing.calculate_volume_ratio()
    
    def _confirm_fenxings_with_subsequent_klines(self, fenxings: FenXingList, 
                                               klines: KLineList) -> None:
        """
        用后续K线确认分型
        
        Args:
            fenxings: 分型列表
            klines: 完整的K线序列
        """
        for fenxing in fenxings:
            confirm_count = 0
            start_index = fenxing.index + 1
            end_index = min(start_index + self.fenxing_config.confirm_window, len(klines))
            
            if start_index >= len(klines):
                continue
            
            # 检查后续K线是否确认分型
            for i in range(start_index, end_index):
                kline = klines[i]
                
                if fenxing.is_top:
                    # 顶分型：后续K线高点应该低于分型高点
                    if kline.high < fenxing.price:
                        confirm_count += 1
                    elif kline.high > fenxing.price:
                        # 如果有突破，减少确认度
                        confirm_count = max(0, confirm_count - 1)
                else:
                    # 底分型：后续K线低点应该高于分型低点
                    if kline.low > fenxing.price:
                        confirm_count += 1
                    elif kline.low < fenxing.price:
                        # 如果有突破，减少确认度
                        confirm_count = max(0, confirm_count - 1)
            
            # 更新确认状态
            fenxing.update_confirmation(confirm_count)
    
    def validate_processed_klines(self, klines: KLineList) -> List[str]:
        """
        验证处理后的K线数据
        
        Args:
            klines: 处理后的K线列表
            
        Returns:
            错误信息列表
        """
        errors = []
        
        if klines.is_empty():
            errors.append("处理后的K线数据为空")
            return errors
        
        # 检查时间顺序
        for i in range(1, len(klines)):
            if klines[i].timestamp <= klines[i-1].timestamp:
                errors.append(f"K线时间顺序错误: 索引{i}")
        
        # 检查包含关系是否已完全处理
        if self.kline_config.enable_include_process:
            for i in range(1, len(klines)):
                relationship = self._check_include_relationship(klines[i-1], klines[i])
                if relationship != "none":
                    errors.append(f"仍存在未处理的包含关系: 索引{i-1}, {i}")
        
        # 检查数据完整性
        for i, kline in enumerate(klines):
            try:
                if not self._is_valid_kline(kline):
                    errors.append(f"K线数据无效: 索引{i}")
            except Exception as e:
                errors.append(f"K线数据验证异常: 索引{i}, 错误: {e}")
        
        return errors
    
    def _validate_input_data(self, klines: KLineList) -> List[str]:
        """
        验证输入数据的质量和完整性
        
        Args:
            klines: 输入K线列表
            
        Returns:
            问题列表
        """
        issues = []
        
        if klines.is_empty():
            issues.append("K线数据为空")
            return issues
        
        # 检查时间顺序
        for i in range(1, len(klines)):
            if klines[i].timestamp <= klines[i-1].timestamp:
                issues.append(f"时间顺序错误: 索引{i-1}到{i}")
        
        # 检查数据完整性和合理性
        zero_volume_count = 0
        abnormal_price_count = 0
        
        for i, kline in enumerate(klines):
            # 检查成交量
            if kline.volume == 0:
                zero_volume_count += 1
            
            # 检查价格合理性
            if (kline.open <= 0 or kline.high <= 0 or 
                kline.low <= 0 or kline.close <= 0):
                abnormal_price_count += 1
                issues.append(f"索引{i}存在非正价格")
            
            # 检查OHLC逻辑
            if (kline.high < max(kline.open, kline.close) or
                kline.low > min(kline.open, kline.close)):
                issues.append(f"索引{i}OHLC逻辑错误")
        
        if zero_volume_count > 0:
            issues.append(f"{zero_volume_count}根K线成交量为0")
        
        # 检查数据连续性（时间间隔）- 增强跳空缺口识别
        if len(klines) > 1:
            time_gaps = []
            price_gaps = []
            normal_gaps = 0
            for i in range(1, len(klines)):
                time_gap = (klines[i].timestamp - klines[i-1].timestamp).total_seconds()
                time_gaps.append(time_gap)
                
                # 计算价格缺口（用于区分跳空和数据异常）
                prev_kline = klines[i-1]
                curr_kline = klines[i]
                
                # 判断是否存在价格跳空
                if curr_kline.low > prev_kline.high:  # 向上跳空
                    price_gap_pct = (curr_kline.low - prev_kline.high) / prev_kline.high * 100
                    price_gaps.append(('up', price_gap_pct, i))
                elif curr_kline.high < prev_kline.low:  # 向下跳空
                    price_gap_pct = (prev_kline.low - curr_kline.high) / prev_kline.low * 100
                    price_gaps.append(('down', price_gap_pct, i))
                else:
                    normal_gaps += 1
            
            # 检查异常时间间隔，但排除合理的跳空缺口和正常的市场休市
            if time_gaps:
                large_time_gaps = []
                
                for i, gap in enumerate(time_gaps):
                    # 定义正常的市场时间间隔（秒）
                    normal_intervals = {
                        1800,    # 30分钟
                        3600,    # 1小时
                        5400,    # 5分钟午休（11:30→13:00）
                        5700,    # 5分钟午休（11:30→13:05，时间戳语义差异）
                        6300,    # 15分钟午休（11:45→13:15）
                        7200,    # 2小时（午休）
                        9000,    # 60分钟午休（11:30→14:00）
                        66600,   # 18.5小时（隔夜）
                        239400,  # 66.5小时（周末：周五15:00到周一9:30）
                        325800,  # 90.5小时（3天长假）
                        499800,  # 138.8小时（4天假期）
                    }
                    
                    # 允许10%的时间误差
                    is_normal_interval = any(abs(gap - normal) / normal < 0.1 for normal in normal_intervals)
                    
                    if not is_normal_interval:
                        # 分钟级跨日/假期间隔：隔夜66600s加整天偏移（n天），
                        # 覆盖隔夜/周末/长假（如412200/757800/930600等变体）。
                        offset = (gap - 66600) / 86400.0
                        is_normal_interval = 0.0 <= offset <= 13.0 and abs(offset - round(offset)) < 0.01
                    
                    if not is_normal_interval:
                        # 日线及以上级别：间隔为整天（86400秒整数倍，1~62天）视为
                        # 正常休市（普通交易日/周末/节假日/长假期）。分钟级间隔
                        # （隔夜66600s、周末239400s等）均非整天数，不受此规则影响。
                        days = gap / 86400.0
                        is_normal_interval = 1.0 <= days <= 62.0 and abs(days - round(days)) < 0.01
                    
                    if not is_normal_interval and gap > 7200:  # 超过2小时且不是正常间隔
                        # 检查对应位置是否有价格跳空
                        has_price_gap = any(gap_info[2] == i+1 for gap_info in price_gaps)
                        if not has_price_gap:
                            # 只有时间异常但无价格跳空且非正常休市的才是真正的数据异常
                            large_time_gaps.append(gap)
                
                if large_time_gaps:
                    issues.append(f"存在{len(large_time_gaps)}个异常时间间隔（非跳空缺口）")
                
                # 记录跳空缺口信息（仅作信息记录，不作为问题）
                if price_gaps:
                    significant_gaps = [gap for gap in price_gaps if gap[1] > 2.0]  # 超过2%的跳空
                    if significant_gaps:
                        logger.info(f"检测到{len(significant_gaps)}个显著价格跳空: {[f'{gap[0]}{gap[1]:.1f}%' for gap in significant_gaps[:3]]}")
        
        
        return issues
    
    def validate_chan_theory_compliance(self, processed_klines: KLineList) -> List[str]:
        """
        验证处理后的K线是否符合缠论标准
        
        Args:
            processed_klines: 处理后的K线列表
            
        Returns:
            不合规问题列表
        """
        issues = []
        
        if processed_klines.is_empty():
            return ["处理后K线为空"]
        
        # 检查包含关系是否完全处理
        remaining_includes = 0
        for i in range(1, len(processed_klines)):
            relationship = self._check_include_relationship(processed_klines[i-1], processed_klines[i])
            if relationship != "none":
                remaining_includes += 1
                issues.append(f"索引{i-1}-{i}仍存在包含关系: {relationship}")
        
        if remaining_includes > 0:
            issues.append(f"总计{remaining_includes}对K线仍有包含关系")
        
        # 检查合并后K线的合理性
        for i, kline in enumerate(processed_klines):
            if kline.original_count > 1:
                # 检查合并后的价格是否合理
                if abs(kline.high - kline.low) < 1e-8:
                    issues.append(f"索引{i}合并后K线高低价相等")
                
                # 检查成交量是否合理
                if kline.volume <= 0:
                    issues.append(f"索引{i}合并后K线成交量异常")
        
        # 检查序列的趋势一致性
        trend_changes = 0
        for i in range(2, len(processed_klines)):
            prev_trend = (processed_klines[i-1].high > processed_klines[i-2].high and 
                         processed_klines[i-1].low > processed_klines[i-2].low)
            curr_trend = (processed_klines[i].high > processed_klines[i-1].high and 
                         processed_klines[i].low > processed_klines[i-1].low)
            
            if prev_trend != curr_trend:
                trend_changes += 1
        
        # 趋势变化太频繁可能表示处理有问题
        if trend_changes > len(processed_klines) * 0.8:
            issues.append(f"趋势变化过于频繁: {trend_changes}次变化")
        
        return issues
    
    def get_processing_statistics(self, original_klines: KLineList, 
                                processed_klines: KLineList,
                                fenxings: Optional[FenXingList] = None) -> dict:
        """
        获取详细的处理统计信息
        
        Args:
            original_klines: 原始K线
            processed_klines: 处理后K线
            fenxings: 分型列表（可选）
            
        Returns:
            统计信息字典
        """
        stats = {
            'original_count': len(original_klines),
            'processed_count': len(processed_klines),
            'reduction_count': len(original_klines) - len(processed_klines),
            'reduction_ratio': 0.0,
            'total_volume': 0,
            'avg_merge_count': 0.0,
            'max_merge_count': 0,
            'fenxing_count': 0,
            'fenxing_ratio': 0.0,
            'processing_quality': 'unknown'
        }
        
        if len(original_klines) > 0:
            stats['reduction_ratio'] = stats['reduction_count'] / len(original_klines)
        
        if not processed_klines.is_empty():
            stats['total_volume'] = sum(k.volume for k in processed_klines)
            merge_counts = [k.original_count for k in processed_klines]
            stats['avg_merge_count'] = sum(merge_counts) / len(merge_counts)
            stats['max_merge_count'] = max(merge_counts)
            
            # 计算价格范围统计
            price_ranges = [(k.high - k.low) for k in processed_klines]
            stats['avg_price_range'] = sum(price_ranges) / len(price_ranges)
            stats['max_price_range'] = max(price_ranges)
            stats['min_price_range'] = min(price_ranges)
        
        # 分型统计
        if fenxings:
            stats['fenxing_count'] = len(fenxings)
            if len(processed_klines) > 0:
                stats['fenxing_ratio'] = len(fenxings) / len(processed_klines)
            
            # 合并分型详细统计
            fenxing_stats = fenxings.get_statistics()
            stats.update({f'fenxing_{k}': v for k, v in fenxing_stats.items()})
            
            # 分型类型分布
            if len(fenxings) > 0:
                tops = sum(1 for f in fenxings if f.is_top)
                bottoms = len(fenxings) - tops
                stats['fenxing_top_ratio'] = tops / len(fenxings)
                stats['fenxing_bottom_ratio'] = bottoms / len(fenxings)
        
        # 处理质量评估
        quality_issues = self.validate_chan_theory_compliance(processed_klines)
        if not quality_issues:
            stats['processing_quality'] = 'excellent'
        elif len(quality_issues) <= 2:
            stats['processing_quality'] = 'good'
        elif len(quality_issues) <= 5:
            stats['processing_quality'] = 'fair'
        else:
            stats['processing_quality'] = 'poor'
        
        stats['quality_issues_count'] = len(quality_issues)
        
        return stats
    
    def _analyze_gaps_and_create_fenxings(self, klines: KLineList) -> List[FenXing]:
        """
        分析跳空缺口并创建相应的分型
        
        Args:
            klines: 处理后的K线列表
            
        Returns:
            缺口形成的分型列表
        """
        try:
            # 导入缺口处理器
            from .gap_processor import GapProcessor, analyze_gaps_in_klines
            
            # 判断是否为指数（简化判断：通过股票代码特征）
            # 这里可以根据实际需要改进判断逻辑
            is_index = False  # 默认为个股，实际应用中可以通过股票代码或其他信息判断
            
            # 分析缺口
            gaps, gap_stats = analyze_gaps_in_klines(klines, klines.level, is_index)
            
            if not gaps:
                return []
            
            # 记录缺口统计信息
            if gap_stats:
                logger.info(f"缺口统计: 总计{gap_stats.get('total_gaps', 0)}个, "
                           f"可成笔{gap_stats.get('can_form_bi_gaps', 0)}个, "
                           f"平均大小{gap_stats.get('avg_gap_size_percent', 0):.2f}%")
            
            # 创建缺口成笔的分型
            gap_processor = GapProcessor(klines.level)
            gap_fenxings = gap_processor.create_gap_bi_fenxings(gaps, klines)
            
            return gap_fenxings
            
        except Exception as e:
            logger.error(f"缺口分析失败: {e}")
            return []