#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论信号评分融合引擎

将157个信号函数的 OrderedDict 输出统一转化为 -100~100 的数值评分，
并按7类信号加权融合为综合评分，用于选股和个股分析。

评分体系设计：
1. 信号值→评分映射：每个信号函数的 v1_v2_v3 组合映射为标准化分数
2. 类别权重：7类信号按信息量和可靠性分配权重
3. 融合算法：加权平均 + 多信号一致性奖励
4. 雷达图数据：输出各类信号得分，用于前端可视化
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


# ─── 信号值→评分映射表 ──────────────────────────────────────────────
# 格式：{信号函数名: {v1值或v1_v2组合: 评分}}
# 评分范围：-100（强烈看空）到 +100（强烈看多），0为中性

SIGNAL_SCORE_MAP = {
    # ═══ cxt - 缠论形态信号 ═══
    "cxt_bi_base": {
        "向上": 30, "向下": -30,
        "向上_转折": 50, "向下_转折": -50,
        "向上_中继": 15, "向下_中继": -15,
    },
    "cxt_fx_power": {
        "强底": 60, "弱底": 25, "中底": 40,
        "强顶": -60, "弱顶": -25, "中顶": -40,
    },
    "cxt_bi_end": {
        "结束": 40, "延续": 0,
        "结束_MACD确认": 70, "结束_MACD未确认": 30,
    },
    "cxt_bi_status": {
        "向上": 25, "向下": -25,
    },
    "cxt_bi_trend": {
        "上涨": 50, "下跌": -50, "震荡": 0,
    },
    "cxt_bi_zdf": {
        "大涨": 70, "小涨": 30, "横盘": 0, "小跌": -30, "大跌": -70,
    },
    "cxt_bi_stop": {
        "向上": 20, "向下": -20,
    },
    "cxt_three_bi": {
        "向上": 30, "向下": -30, "收敛": 10, "扩张": -10,
    },
    "cxt_five_bi": {
        "向上": 40, "向下": -40, "收敛": 15, "扩张": -15,
    },
    "cxt_seven_bi": {
        "向上": 45, "向下": -45, "收敛": 20, "扩张": -20,
    },
    "cxt_nine_bi": {
        "向上": 50, "向下": -50,
    },
    "cxt_eleven_bi": {
        "向上": 50, "向下": -50,
    },
    "cxt_thirteen_bi": {
        "向上": 50, "向下": -50,
    },
    "cxt_first_buy": {
        "一类买": 80, "一类买_确认": 90, "一类买_未确认": 55,
    },
    "cxt_first_sell": {
        "一类卖": -80, "一类卖_确认": -90, "一类卖_未确认": -55,
    },
    "cxt_second_bs": {
        "二类买": 65, "二类卖": -65,
        "二类买_确认": 75, "二类卖_确认": -75,
    },
    "cxt_third_buy": {
        "三类买": 60, "三类买_确认": 70,
    },
    "cxt_third_bs": {
        "三类买": 55, "三类卖": -55,
    },
    "cxt_zs_breakout": {
        "向上突破": 70, "向下突破": -70, "在中枢内": 0,
    },
    "cxt_zs_status": {
        "形成中": 10, "稳定": 0, "扩展": 15, "收缩": -10,
    },
    "cxt_zs_overlap": {
        "重叠增加": 5, "重叠减少": -5, "无重叠": 0,
    },
    "cxt_zs_gongzhen": {
        "共振": 50, "无共振": 0,
    },
    "cxt_double_zs": {
        "多头": 45, "空头": -45, "无": 0,
    },
    "cxt_range_oscillation": {
        "盘整": 0, "突破": 50, "收敛": 10,
    },
    "cxt_decision": {
        "买入": 70, "卖出": -70, "观望": 0, "持有": 10,
    },
    "cxt_bs_signal": {
        "买入": 60, "卖出": -60, "观望": 0,
    },
    "cxt_ubi_end": {
        "结束": 30, "延续": 0,
    },
    "cxt_seg_status": {
        "向上": 35, "向下": -35, "震荡": 0,
    },
    "cxt_seg_direction": {
        "向上": 35, "向下": -35,
    },
    "cxt_trend_type_signal": {
        "上涨走势": 60, "下跌走势": -60, "盘整走势": 0,
    },
    "cxt_backchi_signal": {
        "底背驰": 75, "顶背驰": -75, "无背驰": 0,
        "底背驰_强": 90, "顶背驰_强": -90,
    },
    "cxt_zs_level": {
        "高级别": 40, "低级别": 15, "无级别": 0,
    },
    "cxt_bi_macd_diverge": {
        "底背离": 65, "顶背离": -65, "无背离": 0,
    },
    "cxt_seg_zs": {
        "多头": 40, "空头": -40, "无": 0,
    },
    "cxt_multi_level_bs": {
        "买入": 80, "卖出": -80, "观望": 0,
    },

    # ═══ tas - 技术指标信号 ═══
    "tas_macd_cross": {
        "金叉": 60, "死叉": -60,
    },
    "tas_macd_bc": {
        "底背驰": 70, "顶背驰": -70, "无背驰": 0,
    },
    "tas_macd_dist": {
        "零轴上方": 25, "零轴下方": -25, "零轴附近": 0,
    },
    "tas_ma_system": {
        "多头排列": 55, "空头排列": -55, "交叉排列": 0,
    },
    "tas_ma_cohere": {
        "粘合": 15, "分散": 0,
        "粘合_多头": 40, "粘合_空头": -40,
    },
    "tas_double_ma": {
        "金叉": 50, "死叉": -50, "多头": 25, "空头": -25,
    },
    "tas_cross_status": {
        "金叉": 45, "死叉": -45, "多头": 20, "空头": -20,
    },
    "tas_atr": {
        "高波动": 0, "低波动": 0, "正常": 0,
    },
    "tas_boll_status": {
        "上轨附近": -20, "中轨上方": 20, "中轨附近": 0,
        "中轨下方": -15, "下轨附近": 25,
    },
    "tas_kdj_cross": {
        "金叉": 45, "死叉": -45, "超买": -30, "超卖": 30,
    },
    "tas_rsi_status": {
        "超买": -35, "超卖": 35, "中性": 0, "偏强": 15, "偏弱": -15,
    },
    "tas_cci_status": {
        "超买": -25, "超卖": 25, "中性": 0,
    },
    "tas_sar_status": {
        "多头": 30, "空头": -30, "反转": 40,
    },
    "tas_dif_zero": {
        "远高于零轴": 40, "高于零轴": 25, "低于零轴": -25, "远低于零轴": -40,
    },
    "tas_slope": {
        "上升": 30, "下降": -30, "平缓": 0,
    },
    "tas_accelerate": {
        "加速上升": 45, "加速下降": -45, "减速": 0,
    },
    "tas_low_trend": {
        "上升趋势": 40, "下降趋势": -40, "无趋势": 0,
    },
    "tas_angle": {
        "陡峭上升": 50, "平缓上升": 25, "平缓下降": -25, "陡峭下降": -50,
    },
    "tas_dma_bs": {
        "买入": 50, "卖出": -50, "观望": 0,
    },
    "tas_rumi": {
        "多头": 30, "空头": -30, "中性": 0,
    },
    "tas_macd_bs1": {
        "买入": 55, "卖出": -55, "观望": 0,
    },
    "tas_volume_price": {
        "价涨量增": 40, "价跌量缩": 10, "价涨量缩": -15, "价跌量增": -35, "量价中性": 0,
    },
    "tas_bias_status": {
        "正乖离大": -30, "正乖离小": 10, "负乖离大": 30, "负乖离小": -10, "中性": 0,
    },
    "tas_emv_status": {
        "多头": 25, "空头": -25, "中性": 0,
    },
    "tas_obv_status": {
        "上升": 25, "下降": -25, "平缓": 0,
    },
    "tas_wr_status": {
        "超买": -30, "超卖": 30, "中性": 0,
    },
    "tas_dmi_status": {
        "多头趋势": 40, "空头趋势": -40, "无趋势": 0,
    },
    "tas_trix_signal": {
        "金叉": 40, "死叉": -40, "多头": 20, "空头": -20,
    },
    "tas_roc_signal": {
        "上升": 25, "下降": -25, "中性": 0,
    },
    "tas_mtm_signal": {
        "上升": 25, "下降": -25, "中性": 0,
    },
    "tas_psy_status": {
        "超买": -20, "超卖": 20, "中性": 0,
    },
    "tas_vr_status": {
        "多头": 25, "空头": -25, "中性": 0,
    },
    "tas_wad_status": {
        "多头": 25, "空头": -25, "中性": 0,
    },
    "tas_adx_status": {
        "强趋势": 30, "弱趋势": -10, "中性": 0,
    },
    "tas_tsi_signal": {
        "多头": 30, "空头": -30, "中性": 0,
    },

    # ═══ bar - K线基础信号 ═══
    "bar_single_trend": {
        "上涨": 30, "下跌": -30, "十字": 0,
    },
    "bar_triple_accelerate": {
        "加速上升": 55, "加速下降": -55, "减速": 0,
    },
    "bar_accelerate": {
        "加速": 35, "减速": -20, "匀速": 0,
    },
    "bar_reversal": {
        "看多反转": 55, "看空反转": -55, "无反转": 0,
    },
    "bar_fake_break": {
        "假突破": -40, "真突破": 50, "无突破": 0,
    },
    "bar_channel": {
        "上轨附近": -20, "中轨附近": 0, "下轨附近": 20,
    },
    "bar_zdf": {
        "涨停": 80, "大涨": 50, "小涨": 20, "横盘": 0, "小跌": -20, "大跌": -50, "跌停": -80,
    },
    "bar_vol_grow": {
        "放量增长": 35, "缩量萎缩": -20, "正常": 0,
    },
    "bar_mean_amount": {
        "高于均值": 20, "低于均值": -15, "持平": 0,
    },
    "bar_section_momentum": {
        "强多头": 50, "弱多头": 20, "中性": 0, "弱空头": -20, "强空头": -50,
    },
    "bar_zt_count": {
        "涨停": 60, "无涨停": 0,
    },
    "bar_big_solid": {
        "大阳线": 50, "大阴线": -50, "小实体": 0,
    },
    "bar_shuang_fei": {
        "多头": 40, "空头": -40, "中性": 0,
    },
    "bar_limit_down": {
        "跌停": -60, "无跌停": 0,
    },
    "bar_bpm": {
        "多头": 30, "空头": -30, "中性": 0,
    },
    "bar_r_breaker": {
        "买入": 45, "卖出": -45, "观望": 0,
    },
    "bar_dual_thrust": {
        "突破上轨": 45, "突破下轨": -45, "区间内": 0,
    },
    "bar_tnr": {
        "多头": 30, "空头": -30, "中性": 0,
    },
    "bar_amount_acc": {
        "放量累积": 30, "缩量累积": -20, "正常": 0,
    },
    "bar_operate_span": {
        "可操作": 30, "不可操作": -20, "中性": 0,
    },

    # ═══ vol - 成交量信号 ═══
    "vol_single_ma": {
        "巨量": 45, "放量": 25, "正常": 0, "缩量": -15, "地量": -25,
    },
    "vol_double_ma": {
        "金叉": 40, "死叉": -40, "多头": 20, "空头": -20,
    },
    "vol_ti_suo": {
        "提量": 30, "缩量": -20, "正常": 0,
    },
    "vol_gao_di": {
        "高量柱": 25, "低量柱": -15, "正常": 0,
    },
    "vol_window": {
        "放量窗口": 35, "缩量窗口": -25, "正常": 0,
    },
    "vol_window_v2": {
        "放量窗口": 35, "缩量窗口": -25, "正常": 0,
    },
    "vol_break": {
        "放量突破": 60, "缩量突破": 20, "放量下跌": -50, "缩量下跌": -15, "无突破": 0,
    },
    "vol_shrink": {
        "缩量": -15, "放量": 25, "正常": 0,
    },
    "vol_ratio_signal": {
        "巨量": 50, "大量": 30, "正常": 0, "小量": -15, "地量": -25,
    },
    "vol_price_divergence": {
        "量价背离": -35, "量价配合": 25, "中性": 0,
    },
    "vol_vwap": {
        "高于VWAP": 20, "低于VWAP": -20, "持平": 0,
    },
    "vol_pvt_signal": {
        "多头": 25, "空头": -25, "中性": 0,
    },
    "vol_mfi_signal": {
        "超买": -25, "超卖": 25, "中性": 0,
    },
    "vol_volatility_ratio": {
        "高波动": 0, "低波动": 0, "正常": 0,
    },
    "vol_adi_signal": {
        "多头": 25, "空头": -25, "中性": 0,
    },

    # ═══ jcc - K线组合形态信号 ═══
    "jcc_san_xing_xian": {
        "三星看多": 45, "三星看空": -45,
    },
    "jcc_ten_mo": {
        "蜻蜓十字": 30, "墓碑十字": -30, "长腿十字": 0,
    },
    "jcc_wu_yun_gai_ding": {
        "乌云盖顶": -55,
    },
    "jcc_ci_tou": {
        "刺透": 55,
    },
    "jcc_san_fa": {
        "上升三法": 50, "下降三法": -50,
    },
    "jcc_xing_xian": {
        "晨星": 55, "暮星": -55,
    },
    "jcc_fen_shou_xian": {
        "看空分手": -40, "看多分手": 40,
    },
    "jcc_zhu_huo_xian": {
        "看多抓获": 45, "看空抓获": -45,
    },
    "jcc_yun_xian": {
        "看空孕线": -35, "看多孕线": 35,
    },
    "jcc_ping_tou": {
        "看多": 25, "看空": -25,
    },
    "jcc_two_crow": {
        "两只乌鸦": -45,
    },
    "jcc_three_crow": {
        "三只乌鸦": -55,
    },
    "jcc_szx": {
        "十字星": 0, "长腿十字": 0,
    },
    "jcc_san_szx": {
        "三星十字": 0,
    },
    "jcc_fan_ji_xian": {
        "看多反击": 45, "看空反击": -45,
    },
    "jcc_shan_chun": {
        "看多": 35, "看空": -35,
    },
    "jcc_gap_yin_yang": {
        "看多": 40, "看空": -40,
    },
    "jcc_ta_xing": {
        "塔形顶": -50, "塔形底": 50,
    },
    "jcc_zhuo_yao_dai_xian": {
        "看多": 40, "看空": -40,
    },
    "jcc_hammer": {
        "锤子线": 45, "上吊线": -40,
    },
    "jcc_engulfing": {
        "看多吞没": 55, "看空吞没": -55,
    },
    "jcc_harami_cross": {
        "看多": 35, "看空": -35,
    },
    "jcc_three_white": {
        "三白兵": 55,
    },
    "jcc_three_black": {
        "三黑鸦": -55,
    },
    "jcc_kicking": {
        "看多跳空": 50, "看空跳空": -50,
    },

    # ═══ pos - 位置信号 ═══
    "pos_above_ma": {
        "均线上方": 25, "均线下方": -25, "均线附近": 0,
    },
    "pos_ma_cross": {
        "金叉": 40, "死叉": -40, "上方": 20, "下方": -20,
    },
    "pos_support_resistance": {
        "支撑位附近": 30, "阻力位附近": -30, "中间": 0,
    },
    "pos_high_low": {
        "前高附近": -25, "前低附近": 25, "中间": 0,
    },
    "pos_gap_fill": {
        "回补": 20, "未回补": 0,
    },
    "pos_trend_line": {
        "上方": 25, "下方": -25, "触及": 15,
    },
    "pos_fibonacci": {
        "支撑位": 25, "阻力位": -25, "中性": 0,
    },
    "pos_pivot": {
        "支撑位": 25, "阻力位": -25, "中性": 0,
    },
    "pos_channel_position": {
        "上轨附近": -20, "中轨附近": 0, "下轨附近": 20,
    },
    "pos_price_zone": {
        "高位": -25, "低位": 25, "中位": 0,
    },
    "pos_ma_band": {
        "上轨附近": -20, "中轨附近": 0, "下轨附近": 20,
    },
    "pos_round_number": {
        "整数关口支撑": 20, "整数关口阻力": -20, "无": 0,
    },
    "pos_volume_profile": {
        "高量区支撑": 20, "高量区阻力": -20, "中性": 0,
    },
    "pos_boll_position": {
        "上轨附近": -20, "中轨附近": 0, "下轨附近": 20,
    },
    "pos_kelt_position": {
        "上轨附近": -20, "中轨附近": 0, "下轨附近": 20,
    },

    # ═══ sta - 统计信号 ═══
    "sta_mean_revert": {
        "超买": -30, "超卖": 30, "中性": 0,
    },
    "sta_volatility": {
        "高波动": 0, "低波动": 0, "正常": 0,
    },
    "sta_vol_ratio": {
        "扩张": 0, "收缩": 0, "正常": 0,
    },
    "sta_autocorr": {
        "正相关": 15, "负相关": -15, "无相关": 0,
    },
    "sta_skewness": {
        "正偏": 10, "负偏": -10, "对称": 0,
    },
    "sta_kurtosis": {
        "尖峰": 5, "扁平": -5, "正常": 0,
    },
    "sta_hurst": {
        "趋势持续": 20, "均值回归": -15, "随机游走": 0,
    },
    "sta_z_score": {
        "正偏离": -20, "负偏离": 20, "正常": 0,
    },
    "sta_percentile": {
        "高位": -25, "低位": 25, "中位": 0,
    },
    "sta_regime": {
        "牛市": 40, "熊市": -40, "震荡": 0,
    },
    "sta_consecutive": {
        "连续上涨": 25, "连续下跌": -25, "无": 0,
    },
    "sta_momentum_roc": {
        "上升": 25, "下降": -25, "中性": 0,
    },
}


# ─── 信号类别权重配置 ──────────────────────────────────────────────

SIGNAL_CATEGORY_WEIGHTS = {
    "cxt": 0.30,   # 缠论形态信号 - 核心信号，权重最高
    "tas": 0.25,   # 技术指标信号 - 辅助确认，权重次高
    "vol": 0.15,   # 成交量信号 - 量价配合确认
    "bar": 0.10,   # K线基础信号 - 短期信号
    "pos": 0.10,   # 位置信号 - 位置判断
    "jcc": 0.05,   # K线组合形态 - 辅助确认
    "sta": 0.05,   # 统计信号 - 辅助判断
}

# 信号函数名 → 类别前缀的映射
SIGNAL_CATEGORY_MAP = {}
for _cat in ["cxt", "tas", "bar", "vol", "jcc", "pos", "sta"]:
    SIGNAL_CATEGORY_MAP[_cat] = _cat


@dataclass
class SignalScoreResult:
    """信号评分结果"""
    # 各类别原始平均分（-100~100）
    category_scores: Dict[str, float] = field(default_factory=dict)
    # 各类别有效信号数量
    category_counts: Dict[str, int] = field(default_factory=dict)
    # 各类别加权得分
    category_weighted: Dict[str, float] = field(default_factory=dict)
    # 综合评分（-100~100）
    total_score: float = 0.0
    # 一致性奖励系数（0~0.2），多信号方向一致时获得额外加分
    consistency_bonus: float = 0.0
    # 最终评分（含一致性奖励，0~100，50为中性）
    final_score: float = 50.0
    # 信号方向：bullish / bearish / neutral
    direction: str = "neutral"
    # 信号强度：strong / medium / weak
    strength: str = "weak"
    # 各信号详情
    signal_details: List[Dict[str, Any]] = field(default_factory=list)
    # 雷达图数据
    radar_data: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category_scores": self.category_scores,
            "category_counts": self.category_counts,
            "category_weighted": self.category_weighted,
            "total_score": round(self.total_score, 2),
            "consistency_bonus": round(self.consistency_bonus, 4),
            "final_score": round(self.final_score, 2),
            "direction": self.direction,
            "strength": self.strength,
            "radar_data": self.radar_data,
            "signal_details": self.signal_details[:20],  # 只输出前20个
        }


class SignalScorer:
    """
    信号评分融合引擎

    核心逻辑：
    1. 将信号函数输出的 OrderedDict 统一转化为评分
    2. 按类别加权融合
    3. 多信号一致性奖励
    4. 输出综合评分和雷达图数据
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: 自定义类别权重，为None时使用默认权重
        """
        self.weights = weights or SIGNAL_CATEGORY_WEIGHTS.copy()
        self.score_map = SIGNAL_SCORE_MAP.copy()

    def score_single_signal(self, signal_name: str,
                            signal_value: OrderedDict) -> float:
        """
        将单个信号函数的输出转化为评分

        Args:
            signal_name: 信号函数名（如 "cxt_first_buy"）
            signal_value: 信号函数返回的 OrderedDict

        Returns:
            评分（-100~100），无法识别时返回0
        """
        if not signal_value:
            return 0.0

        # 提取信号的值部分（v1_v2_v3）
        value_str = list(signal_value.values())[0] if signal_value else ""
        if not value_str:
            return 0.0

        # 获取该信号函数的评分映射
        signal_map = self.score_map.get(signal_name, {})
        if not signal_map:
            return 0.0

        # 尝试精确匹配：v1_v2_v3 → v1_v2 → v1
        parts = value_str.split("_")
        for i in range(len(parts), 0, -1):
            candidate = "_".join(parts[:i])
            if candidate in signal_map:
                return float(signal_map[candidate])

        # 尝试模糊匹配：包含关键词
        for key, score in signal_map.items():
            if key in value_str or value_str in key:
                return float(score)

        return 0.0

    def score_all_signals(self, signals: Dict[str, OrderedDict]) -> SignalScoreResult:
        """
        对所有信号进行评分融合

        Args:
            signals: {信号名: OrderedDict} 格式的信号字典，
                     通常由 EnhancedChanAnalyzer.generate_signal_library() 生成

        Returns:
            SignalScoreResult 评分结果
        """
        result = SignalScoreResult()

        # 1. 逐信号评分
        category_raw: Dict[str, List[float]] = {}
        for cat in self.weights:
            category_raw[cat] = []

        for signal_name, signal_value in signals.items():
            score = self.score_single_signal(signal_name, signal_value)

            # 确定信号类别
            cat = self._get_category(signal_name)
            if cat in category_raw:
                category_raw[cat].append(score)

            # 记录详情
            value_str = list(signal_value.values())[0] if signal_value else ""
            result.signal_details.append({
                "name": signal_name,
                "value": value_str,
                "score": round(score, 2),
                "category": cat,
            })

        # 2. 各类别平均分
        for cat, scores in category_raw.items():
            if scores:
                result.category_scores[cat] = round(sum(scores) / len(scores), 2)
                result.category_counts[cat] = len(scores)
            else:
                result.category_scores[cat] = 0.0
                result.category_counts[cat] = 0

        # 3. 加权融合
        total_weight = 0.0
        weighted_sum = 0.0
        for cat, weight in self.weights.items():
            if result.category_counts.get(cat, 0) > 0:
                weighted = result.category_scores[cat] * weight
                result.category_weighted[cat] = round(weighted, 2)
                weighted_sum += weighted
                total_weight += weight

        if total_weight > 0:
            result.total_score = weighted_sum / total_weight * (sum(self.weights.values()) / total_weight)
        else:
            result.total_score = 0.0

        # 4. 一致性奖励：多数信号方向一致时加分
        result.consistency_bonus = self._calc_consistency_bonus(category_raw)

        # 5. 最终评分：total_score归一化到0~100，50为中性
        # total_score 范围 -100~100，映射到 0~100
        raw_final = 50 + result.total_score * 0.5 * (1 + result.consistency_bonus)
        result.final_score = max(0, min(100, raw_final))

        # 6. 方向和强度
        if result.final_score >= 70:
            result.direction = "bullish"
            result.strength = "strong"
        elif result.final_score >= 58:
            result.direction = "bullish"
            result.strength = "medium"
        elif result.final_score >= 52:
            result.direction = "bullish"
            result.strength = "weak"
        elif result.final_score <= 30:
            result.direction = "bearish"
            result.strength = "strong"
        elif result.final_score <= 42:
            result.direction = "bearish"
            result.strength = "medium"
        elif result.final_score <= 48:
            result.direction = "bearish"
            result.strength = "weak"
        else:
            result.direction = "neutral"
            result.strength = "weak"

        # 7. 雷达图数据（各类别得分映射到0~100）
        for cat in self.weights:
            if cat in result.category_scores:
                result.radar_data[cat] = round(50 + result.category_scores[cat] * 0.5, 1)
            else:
                result.radar_data[cat] = 50.0

        return result

    def _get_category(self, signal_name: str) -> str:
        """根据信号函数名确定类别"""
        for prefix in ["cxt", "tas", "bar", "vol", "jcc", "pos", "sta"]:
            if signal_name.startswith(prefix):
                return prefix
        return "cxt"  # 默认归入缠论形态

    def _calc_consistency_bonus(self, category_raw: Dict[str, List[float]]) -> float:
        """
        计算一致性奖励

        当多个类别的信号方向一致时，给予额外加分（0~0.2）
        """
        positive_cats = 0
        negative_cats = 0
        total_cats = 0

        for cat, scores in category_raw.items():
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            total_cats += 1
            if avg > 10:
                positive_cats += 1
            elif avg < -10:
                negative_cats += 1

        if total_cats == 0:
            return 0.0

        # 一致性比例
        max_direction = max(positive_cats, negative_cats)
        if max_direction >= 3:
            return 0.2
        elif max_direction >= 2:
            return 0.1
        else:
            return 0.0

    def score_from_chan_result(self, result: Any,
                               time_level: Any = None) -> SignalScoreResult:
        """
        直接从缠论分析结果生成信号评分

        便捷方法：自动调用 EnhancedChanAnalyzer 生成信号库，然后评分

        Args:
            result: ChanAnalysisResult 对象
            time_level: 时间级别

        Returns:
            SignalScoreResult 评分结果
        """
        from chan_theory_v2.core.chan_enhanced import EnhancedChanAnalyzer
        from chan_theory_v2.models.enums import TimeLevel

        if time_level is None:
            time_level = TimeLevel.DAILY

        analyzer = EnhancedChanAnalyzer()
        signals = analyzer.generate_signal_library(time_level, result)
        return self.score_all_signals(signals)


def get_signal_scorer() -> SignalScorer:
    """获取全局信号评分器实例"""
    return SignalScorer()
