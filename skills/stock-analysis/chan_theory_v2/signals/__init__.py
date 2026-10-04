#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论信号函数库

借鉴 czsc 的信号体系设计，建立完整的缠论信号函数库。
信号格式统一为 k1_k2_k3_v1_v2_v3，参考 czsc.Signal 规范。

信号分类：
- cxt: 缠论形态信号（笔、分型、中枢、买卖点）- 35个信号
- tas: 技术指标信号（MA、MACD、BOLL、ATR、KDJ等）- 35个信号
- bar: K线基础信号（单K、三K、加速、反转等）- 20个信号
- vol: 成交量信号（量比、缩放、高量柱、窗口能量等）- 15个信号
- jcc: K线组合形态信号（三星、十字、三法、山川等）- 25个信号
- pos: 位置信号（支撑阻力、价格位置、趋势线等）- 15个信号
- sta: 统计信号（均值回归、波动率、自相关等）- 12个信号

总计：157个信号函数

使用方式：
    from chan_theory_v2.signals import cxt_bi_base, tas_macd_cross
    signal = cxt_bi_base(freq='15分钟', bi_list=..., bars_ubi=...)
"""

from .cxt import *
from .tas import *
from .bar import *
from .vol import *
from .jcc import *
from .pos import *
from .sta import *

__all__ = [
    # cxt - 缠论形态信号 (35)
    'cxt_bi_base',
    'cxt_fx_power',
    'cxt_bi_end',
    'cxt_bi_status',
    'cxt_bi_trend',
    'cxt_bi_zdf',
    'cxt_bi_stop',
    'cxt_three_bi',
    'cxt_five_bi',
    'cxt_seven_bi',
    'cxt_nine_bi',
    'cxt_eleven_bi',
    'cxt_first_buy',
    'cxt_first_sell',
    'cxt_second_bs',
    'cxt_third_buy',
    'cxt_third_bs',
    'cxt_zs_breakout',
    'cxt_zs_status',
    'cxt_zs_overlap',
    'cxt_zs_gongzhen',
    'cxt_double_zs',
    'cxt_range_oscillation',
    'cxt_decision',
    'cxt_bs_signal',
    'cxt_ubi_end',
    'cxt_seg_status',
    'cxt_seg_direction',
    'cxt_trend_type_signal',
    'cxt_backchi_signal',
    'cxt_thirteen_bi',
    'cxt_zs_level',
    'cxt_bi_macd_diverge',
    'cxt_seg_zs',
    'cxt_multi_level_bs',

    # tas - 技术指标信号 (35)
    'tas_macd_cross',
    'tas_macd_bc',
    'tas_macd_dist',
    'tas_ma_system',
    'tas_ma_cohere',
    'tas_double_ma',
    'tas_cross_status',
    'tas_atr',
    'tas_boll_status',
    'tas_kdj_cross',
    'tas_rsi_status',
    'tas_cci_status',
    'tas_sar_status',
    'tas_dif_zero',
    'tas_slope',
    'tas_accelerate',
    'tas_low_trend',
    'tas_angle',
    'tas_dma_bs',
    'tas_rumi',
    'tas_macd_bs1',
    'tas_volume_price',
    'tas_bias_status',
    'tas_emv_status',
    'tas_obv_status',
    'tas_wr_status',
    'tas_dmi_status',
    'tas_trix_signal',
    'tas_roc_signal',
    'tas_mtm_signal',
    'tas_psy_status',
    'tas_vr_status',
    'tas_wad_status',
    'tas_adx_status',
    'tas_tsi_signal',

    # bar - K线基础信号 (20)
    'bar_single_trend',
    'bar_triple_accelerate',
    'bar_accelerate',
    'bar_reversal',
    'bar_fake_break',
    'bar_channel',
    'bar_zdf',
    'bar_vol_grow',
    'bar_mean_amount',
    'bar_section_momentum',
    'bar_zt_count',
    'bar_big_solid',
    'bar_shuang_fei',
    'bar_limit_down',
    'bar_bpm',
    'bar_r_breaker',
    'bar_dual_thrust',
    'bar_tnr',
    'bar_amount_acc',
    'bar_operate_span',

    # vol - 成交量信号 (15)
    'vol_single_ma',
    'vol_double_ma',
    'vol_ti_suo',
    'vol_gao_di',
    'vol_window',
    'vol_window_v2',
    'vol_break',
    'vol_shrink',
    'vol_ratio_signal',
    'vol_price_divergence',
    'vol_vwap',
    'vol_pvt_signal',
    'vol_mfi_signal',
    'vol_volatility_ratio',
    'vol_adi_signal',

    # jcc - K线组合形态信号 (25)
    'jcc_san_xing_xian',
    'jcc_ten_mo',
    'jcc_wu_yun_gai_ding',
    'jcc_ci_tou',
    'jcc_san_fa',
    'jcc_xing_xian',
    'jcc_fen_shou_xian',
    'jcc_zhu_huo_xian',
    'jcc_yun_xian',
    'jcc_ping_tou',
    'jcc_two_crow',
    'jcc_three_crow',
    'jcc_szx',
    'jcc_san_szx',
    'jcc_fan_ji_xian',
    'jcc_shan_chun',
    'jcc_gap_yin_yang',
    'jcc_ta_xing',
    'jcc_zhuo_yao_dai_xian',
    'jcc_hammer',
    'jcc_engulfing',
    'jcc_harami_cross',
    'jcc_three_white',
    'jcc_three_black',
    'jcc_kicking',

    # pos - 位置信号 (15)
    'pos_above_ma',
    'pos_ma_cross',
    'pos_support_resistance',
    'pos_high_low',
    'pos_gap_fill',
    'pos_trend_line',
    'pos_fibonacci',
    'pos_pivot',
    'pos_channel_position',
    'pos_price_zone',
    'pos_ma_band',
    'pos_round_number',
    'pos_volume_profile',
    'pos_boll_position',
    'pos_kelt_position',

    # sta - 统计信号 (12)
    'sta_mean_revert',
    'sta_volatility',
    'sta_vol_ratio',
    'sta_autocorr',
    'sta_skewness',
    'sta_kurtosis',
    'sta_hurst',
    'sta_z_score',
    'sta_percentile',
    'sta_regime',
    'sta_consecutive',
    'sta_momentum_roc',
]
