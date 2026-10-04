#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个股相对估值分析脚本

通过 Tushare Pro API 获取 PE/PB/PS 等估值指标，
计算历史分位数和行业横向对比，给出综合估值判断。
同时通过同花顺问财 API 获取实时估值数据，
应用估值模型方法论（DCF/DDM/PE-Band/PB-ROE/EV-EBITDA）进行多方法交叉验证。
供 stock_tools 调用。

用法:
  python scripts/analyze_stock_valuation.py --stock 000001.SZ --json
"""

import numpy as np  # KStock patch: 修复上游遗漏的 numpy 导入
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Optional


_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  同花顺问财数据接口
# ======================================================================

_HITHINK_MARKET_CLI = os.path.join(
    _project_root, 'server', 'skills', 'hithink-market-query', 'scripts', 'cli.py'
)
_HITHINK_BUSINESS_CLI = os.path.join(
    _project_root, 'server', 'skills', 'hithink-business-query', 'scripts', 'cli.py'
)


def _call_hithink_cli(cli_path: str, query: str, timeout: int = 30) -> dict:
    """调用同花顺问财 CLI 脚本获取数据"""
    if not os.path.exists(cli_path):
        return {'error': f'CLI 脚本不存在: {cli_path}'}
    try:
        result = subprocess.run(
            [sys.executable, cli_path, '--query', query, '--limit', '10'],
            capture_output=True, text=True, timeout=timeout,
            cwd=_project_root,
        )
        if result.returncode != 0:
            return {'error': f'CLI 调用失败: {result.stderr[:200]}'}
        output = json.loads(result.stdout)
        # 提取 datas 数组
        if isinstance(output, dict) and 'datas' in output:
            return {'datas': output['datas'], 'query': query}
        return output
    except subprocess.TimeoutExpired:
        return {'error': f'CLI 调用超时({timeout}s): {query}'}
    except json.JSONDecodeError:
        return {'error': f'CLI 返回非 JSON 数据'}
    except Exception as e:
        return {'error': f'CLI 调用异常: {str(e)}'}


def _query_hithink_valuation(stock_name: str) -> dict:
    """通过同花顺问财获取实时估值数据"""
    results = {}

    # 1. 估值指标（PE/PB/PS/ROE）
    r1 = _call_hithink_cli(_HITHINK_MARKET_CLI, f'{stock_name} PE PB PS ROE 市盈率 市净率')
    results['valuation_metrics'] = r1

    # 2. 同行业估值对比
    r2 = _call_hithink_cli(_HITHINK_MARKET_CLI, f'{stock_name} 同行业估值对比 PE PB')
    results['industry_comparison'] = r2

    # 3. 股息分红数据
    r3 = _call_hithink_cli(_HITHINK_MARKET_CLI, f'{stock_name} 股息率 分红')
    results['dividend_data'] = r3

    # 4. 主营业务构成（通过 business-query）
    r4 = _call_hithink_cli(_HITHINK_BUSINESS_CLI, f'{stock_name} 主营业务构成')
    results['business_composition'] = r4

    return results


# ======================================================================
#  估值模型方法论
# ======================================================================

def _compute_pe_band(pe_history: list, current_pe: float) -> dict:
    """计算 PE Band（市盈率分位带）"""
    if not pe_history or current_pe is None:
        return None
    valid = [v for v in pe_history if v and v > 0]
    if not valid:
        return None
    arr = np.array(valid)
    return {
        'p10': round(float(np.percentile(arr, 10)), 2),
        'p25': round(float(np.percentile(arr, 25)), 2),
        'p50': round(float(np.percentile(arr, 50)), 2),
        'p75': round(float(np.percentile(arr, 75)), 2),
        'p90': round(float(np.percentile(arr, 90)), 2),
        'current': round(current_pe, 2),
        'percentile': round(float(np.sum(arr >= current_pe) / len(arr) * 100), 1),
        'level': '低估' if current_pe <= np.percentile(arr, 20) else '高估' if current_pe >= np.percentile(arr, 80) else '合理',
    }


def _compute_pb_roe_analysis(pb: float, roe: float, industry: str) -> dict:
    """PB-ROE 矩阵分析"""
    if pb is None or roe is None:
        return None

    # 理论合理 PB = (ROE - g) / (Ke - g)，取 g=3%, Ke=10%
    ke = 0.10
    g = 0.03
    theoretical_pb = (roe / 100 - g) / (ke - g) if roe / 100 > g else 0

    # 判断 PB-ROE 象限
    if pb < theoretical_pb * 0.8 and roe > 10:
        quadrant = '低估区域（低PB高ROE）'
        signal = '买入信号'
    elif pb >= theoretical_pb * 0.8 and roe > 10:
        quadrant = '合理区域（高PB高ROE）'
        signal = '质量溢价'
    elif pb < theoretical_pb * 0.8 and roe <= 10:
        quadrant = '价值陷阱/反转候选（低PB低ROE）'
        signal = '需进一步验证'
    else:
        quadrant = '高估区域（高PB低ROE）'
        signal = '回避信号'

    return {
        'pb': round(pb, 2),
        'roe': round(roe, 2),
        'theoretical_pb': round(theoretical_pb, 2),
        'pb_ratio_to_theoretical': round(pb / theoretical_pb, 2) if theoretical_pb > 0 else None,
        'quadrant': quadrant,
        'signal': signal,
    }


def _detect_valuation_traps(stock_name: str, result: dict, hithink_data: dict) -> list:
    """检测估值陷阱"""
    traps = []
    current = result.get('current', {})
    hist = result.get('historical_percentile', {})
    ratings = result.get('ratings', {})
    industry = result.get('industry', '')

    # 1. 低PE周期股陷阱
    cyclical_industries = ['煤炭', '钢铁', '有色金属', '石油', '化工', '水泥', '造纸']
    if any(cyc in industry for cyc in cyclical_industries):
        pe = current.get('pe')
        pe_pct = hist.get('pe')
        if pe and pe_pct and pe_pct <= 30:
            traps.append({
                'type': '低PE周期股陷阱',
                'severity': 'high',
                'description': f'{industry}属周期性行业，当前PE={pe}处于历史{pe_pct}%分位（低位），可能是盈利最高峰而非低估',
                'suggestion': '周期股应使用PB或EV/EBITDA估值，避免使用PE',
            })

    # 2. 低PB价值毁灭陷阱
    pb = current.get('pb')
    if pb and pb < 1.0:
        traps.append({
            'type': '低PB价值毁灭陷阱',
            'severity': 'medium',
            'description': f'PB={pb}<1，可能是净资产减值风险或持续ROE低于资本成本',
            'suggestion': '检查ROE是否持续低于8%，商誉/净资产比是否>30%',
        })

    # 3. 商誉减值风险（从同花顺数据提取）
    biz_data = hithink_data.get('business_composition', {})
    if isinstance(biz_data, dict) and 'error' not in biz_data:
        datas = biz_data.get('datas', [])
        for item in datas:
            if isinstance(item, dict):
                goodwill_str = str(item.get('商誉', item.get(' goodwill', '')))
                net_assets_str = str(item.get('净资产', item.get('所有者权益合计', '')))
                try:
                    goodwill = float(re.sub(r'[^0-9.]', '', goodwill_str)) if goodwill_str and goodwill_str != 'None' else 0
                    net_assets = float(re.sub(r'[^0-9.]', '', net_assets_str)) if net_assets_str and net_assets_str != 'None' else 0
                    if net_assets > 0 and goodwill / net_assets > 0.3:
                        traps.append({
                            'type': '商誉减值风险',
                            'severity': 'high',
                            'description': f'商誉/净资产比={goodwill/net_assets:.0%}>30%，存在减值风险',
                            'suggestion': '关注并购标的业绩承诺完成情况',
                        })
                except (ValueError, ZeroDivisionError):
                    pass

    # 4. 应收账款/收入比上升
    traps.append({
        'type': '应收账款/收入比检测',
        'severity': 'info',
        'description': '需检查财报中应收账款/营业收入比例趋势（需财务数据支持）',
        'suggestion': '若应收账款增速持续>营收增速，说明收入质量下降',
    })

    # 5. 一次性收益虚增利润
    traps.append({
        'type': '一次性收益检测',
        'severity': 'info',
        'description': '需对比扣非净利润与净利润差距（需财务数据支持）',
        'suggestion': '若扣非净利<<净利润，说明利润质量不佳',
    })

    # 6. 估值方法匹配建议
    company_type = _classify_company_type(industry)
    method_advice = _get_valuation_method_advice(company_type)
    traps.append({
        'type': '估值方法建议',
        'severity': 'info',
        'company_type': company_type,
        'recommended_methods': method_advice,
        'description': f'{industry}行业建议使用{"、".join(method_advice)}进行估值',
    })

    return traps


def _classify_company_type(industry: str) -> str:
    """根据行业判断公司类型"""
    if any(k in industry for k in ['银行', '保险', '证券']):
        return '金融'
    elif any(k in industry for k in ['消费', '食品', '饮料', '家电', '公用']):
        return '成熟稳定'
    elif any(k in industry for k in ['科技', '电子', '计算机', '通信', '医药', '新能源']):
        return '高成长'
    elif any(k in industry for k in ['煤炭', '钢铁', '有色', '石油', '化工', '水泥']):
        return '周期性'
    elif any(k in industry for k in ['综合', '投资', '控股']):
        return '多元化集团'
    return '一般'


def _get_valuation_method_advice(company_type: str) -> list:
    """根据公司类型推荐估值方法"""
    advice_map = {
        '成熟稳定': ['DDM', 'PE-Band', 'DCF'],
        '高成长': ['DCF(高增长期)', 'PEG', 'PS'],
        '周期性': ['PB', 'EV/EBITDA'],
        '金融': ['PB', 'DDM'],
        '多元化集团': ['SOTP(分部估值法)'],
        '一般': ['DCF', 'PE-Band', 'PB-ROE'],
    }
    return advice_map.get(company_type, ['DCF', 'PE-Band'])


def _extract_roe_from_hithink(hithink_data: dict) -> Optional[float]:
    """从同花顺数据中提取 ROE 值"""
    metrics_data = hithink_data.get('valuation_metrics', {})
    if not isinstance(metrics_data, dict):
        return None
    datas = metrics_data.get('datas', [])
    if not datas:
        return None
    for item in datas:
        if not isinstance(item, dict):
            continue
        # 尝试多种字段名
        for key in ['ROE', 'ROE(%)', '净资产收益率', '加权净资产收益率']:
            val = item.get(key)
            if val is not None:
                try:
                    roe_val = float(str(val).replace('%', ''))
                    if roe_val > 0:
                        return roe_val
                except (ValueError, TypeError):
                    pass
    return None


def _extract_dividend_yield(div_data: dict) -> Optional[float]:
    """从同花顺数据中提取股息率"""
    if not isinstance(div_data, dict):
        return None
    datas = div_data.get('datas', [])
    if not datas:
        return None
    for item in datas:
        if not isinstance(item, dict):
            continue
        for key in ['股息率', '股息率(%)', '分红率', '分红比例']:
            val = item.get(key)
            if val is not None:
                try:
                    return float(str(val).replace('%', ''))
                except (ValueError, TypeError):
                    pass
    return None


def _generate_valuation_summary(result: dict) -> dict:
    """生成综合估值结论"""
    ratings = result.get('ratings', {})
    valuation_models = result.get('valuation_models', {})
    trap_detection = result.get('trap_detection', [])

    # 基础估值判断
    overall_rating = ratings.get('overall', '无法判断')

    # 高风险陷阱计数
    high_traps = [t for t in trap_detection if t.get('severity') == 'high']

    # 估值方法建议
    recommended = valuation_models.get('recommended_methods', [])
    company_type = valuation_models.get('company_type', '未知')

    # PB-ROE 信号
    pb_roe_signal = valuation_models.get('pb_roe', {}).get('signal', '')

    # 综合判断
    if overall_rating == '低估' and not high_traps:
        investment_rating = '买入'
        confidence = '高'
    elif overall_rating == '低估' and high_traps:
        investment_rating = '观望'
        confidence = '低（存在估值陷阱风险）'
    elif overall_rating == '合理':
        investment_rating = '持有'
        confidence = '中'
    elif overall_rating == '高估':
        investment_rating = '减仓'
        confidence = '高'
    else:
        investment_rating = '观望'
        confidence = '低'

    return {
        'overall_rating': overall_rating,
        'investment_rating': investment_rating,
        'confidence': confidence,
        'company_type': company_type,
        'recommended_valuation_methods': recommended,
        'trap_risk_count': len(high_traps),
        'pb_roe_signal': pb_roe_signal,
        'data_sources': ['Tushare Pro API（历史数据）', '同花顺问财（实时数据）'],
    }


# ======================================================================
#  Tushare 数据接口
# ======================================================================

def _get_tushare_api():
    from kk_common import get_finance_data_gateway
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, '.env'))
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN，请在 .env 中配置")
    return get_finance_data_gateway()


def _resolve_stock(ts_api, stock_input: str) -> tuple:
    code = stock_input.strip()
    if '.' in code and len(code.split('.')[0]) == 6:
        ts_code = code
        name = _get_stock_name(ts_api, ts_code)
        return ts_code, name

    try:
        df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,name,code')
        match = df[df['name'] == stock_input]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
        match = df[df['name'].str.contains(stock_input, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
        match = df[df['code'] == stock_input.zfill(6)]
        if not match.empty:
            return match.iloc[0]['ts_code'], match.iloc[0]['name']
    except Exception:
        pass
    raise ValueError(f"无法识别股票: {stock_input}")


def _get_stock_name(ts_api, ts_code: str) -> str:
    try:
        df = ts_api.stock_basic(ts_code=ts_code, fields='name')
        if not df.empty:
            return df.iloc[0]['name']
    except Exception:
        pass
    return ts_code


def _get_industry(ts_api, ts_code: str) -> str:
    try:
        df = ts_api.stock_basic(ts_code=ts_code, fields='industry')
        if not df.empty and 'industry' in df.columns:
            return df.iloc[0]['industry'] or '未知'
    except Exception:
        pass
    return '未知'


def _compute_percentile(values: list, current: float) -> float:
    if not values or current is None:
        return None
    valid = [v for v in values if v and v > 0]
    if not valid:
        return None
    return float(np.sum(np.array(valid) >= current) / len(valid) * 100)


def _rating(percentile: float, metric: str) -> str:
    if percentile is None:
        return '无法判断'
    if metric == 'pe':
        if percentile >= 80:
            return '高估'
        elif percentile <= 20:
            return '低估'
        return '合理'
    elif metric == 'pb':
        if percentile >= 80:
            return '高估'
        elif percentile <= 20:
            return '低估'
        return '合理'
    else:
        if percentile >= 75:
            return '偏高'
        elif percentile <= 25:
            return '偏低'
        return '正常'


# ======================================================================
#  核心分析逻辑
# ======================================================================

def analyze_stock_valuation(stock_input: str) -> dict:
    """
    分析个股相对估值水平。
    """
    ts_api = _get_tushare_api()
    ts_code, stock_name = _resolve_stock(ts_api, stock_input)
    industry = _get_industry(ts_api, ts_code)

    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

    df = ts_api.daily_basic(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields='ts_code,trade_date,close,pe,pe_ttm,pb,ps,ps_ttm,circ_mv'
    )
    time.sleep(0.3)

    if df is None or df.empty:
        return {'error': f'无法获取 {ts_code} 的估值数据'}

    df = df.sort_values('trade_date').reset_index(drop=True)
    latest = df.iloc[-1]
    trade_date = latest['trade_date']

    current_metrics = {
        'close': round(float(latest['close']), 2) if latest.get('close') else None,
        'pe': round(float(latest['pe']), 2) if latest.get('pe') and latest['pe'] > 0 else None,
        'pe_ttm': round(float(latest['pe_ttm']), 2) if latest.get('pe_ttm') and latest['pe_ttm'] > 0 else None,
        'pb': round(float(latest['pb']), 2) if latest.get('pb') and latest['pb'] > 0 else None,
        'ps': round(float(latest['ps']), 2) if latest.get('ps') and latest['ps'] > 0 else None,
        'ps_ttm': round(float(latest['ps_ttm']), 2) if latest.get('ps_ttm') and latest['ps_ttm'] > 0 else None,
        # daily_basic.circ_mv unit is 万元 (10k yuan) per Tushare official
        # doc. Convert to 亿元 by dividing 1e4 (NOT 1e8, which would be for 元).
        'circ_mv': round(float(latest['circ_mv']) / 1e4, 2) if latest.get('circ_mv') else None,
    }

    def hist_percentile(series, metric_key):
        if current_metrics.get(metric_key) is None:
            return None
        vals = series.dropna().tolist()
        cur = current_metrics[metric_key]
        return _compute_percentile(vals, cur)

    pe_pct = hist_percentile(df['pe'].where(df['pe'] > 0), 'pe')
    pb_pct = hist_percentile(df['pb'].where(df['pb'] > 0), 'pb')
    ps_pct = hist_percentile(df['ps'].where(df['ps'] > 0), 'ps')

    # 行业对比
    industry_stocks = []
    if industry and industry != '未知':
        try:
            comp_df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code')
            all_stocks = comp_df['ts_code'].tolist()
            sample = all_stocks[:200]
            for sym in sample:
                try:
                    d = ts_api.daily_basic(ts_code=sym, trade_date=trade_date,
                                           fields='ts_code,pe,pb,ps')
                    time.sleep(0.05)
                    if d is not None and not d.empty:
                        industry_stocks.append(d.iloc[0].to_dict())
                except Exception:
                    pass
        except Exception:
            pass

    def industry_percentile(industry_data, metric):
        if not industry_data or current_metrics.get(metric) is None:
            return None
        vals = [d.get(metric) for d in industry_data
                if d.get(metric) and d.get(metric) > 0]
        if not vals:
            return None
        cur = current_metrics[metric]
        return float(np.sum(np.array(vals) >= cur) / len(vals) * 100)

    def industry_stats(industry_data, metric):
        vals = [d.get(metric) for d in industry_data
                if d.get(metric) and d.get(metric) > 0]
        if not vals:
            return {'median': None, 'mean': None, 'min': None, 'max': None}
        arr = np.array(vals)
        return {
            'median': round(float(np.median(arr)), 2),
            'mean': round(float(np.mean(arr)), 2),
            'min': round(float(np.min(arr)), 2),
            'max': round(float(np.max(arr)), 2),
        }

    ind_pe_stats = industry_stats(industry_stocks, 'pe')
    ind_pb_stats = industry_stats(industry_stocks, 'pb')
    ind_ps_stats = industry_stats(industry_stocks, 'ps')

    ind_pe_pct = industry_percentile(industry_stocks, 'pe')
    ind_pb_pct = industry_percentile(industry_stocks, 'pb')
    ind_ps_pct = industry_percentile(industry_stocks, 'ps')

    pe_rating = _rating(pe_pct, 'pe') if pe_pct else None
    pb_rating = _rating(pb_pct, 'pb') if pb_pct else None
    ps_rating = _rating(ps_pct, 'ps') if ps_pct else None

    if pe_rating == '低估' and pb_rating in ('低估', '合理'):
        overall = '低估'
    elif pe_rating == '高估' and pb_rating in ('高估', '合理'):
        overall = '高估'
    else:
        overall = '合理'

    result = {
        'ts_code': ts_code,
        'stock_name': stock_name,
        'industry': industry,
        'trade_date': trade_date,
        'current': current_metrics,
        'historical_percentile': {
            'pe': round(pe_pct, 1) if pe_pct else None,
            'pb': round(pb_pct, 1) if pb_pct else None,
            'ps': round(ps_pct, 1) if ps_pct else None,
        },
        'industry_percentile': {
            'pe': round(ind_pe_pct, 1) if ind_pe_pct else None,
            'pb': round(ind_pb_pct, 1) if ind_pb_pct else None,
            'ps': round(ind_ps_pct, 1) if ind_ps_pct else None,
        },
        'industry_stats': {
            'pe': ind_pe_stats,
            'pb': ind_pb_stats,
            'ps': ind_ps_stats,
        },
        'ratings': {
            'pe': pe_rating,
            'pb': pb_rating,
            'ps': ps_rating,
            'overall': overall,
        },
        # 添加历史数据用于图表渲染
        'history': {
            'dates': df['trade_date'].dt.strftime('%Y-%m-%d').tolist() if hasattr(df['trade_date'], 'dt') else df['trade_date'].tolist(),
            'pe': df['pe'].where(df['pe'] > 0).ffill().tolist(),
            'pb': df['pb'].where(df['pb'] > 0).ffill().tolist(),
            'ps': df['ps'].where(df['ps'] > 0).ffill().tolist(),
        },
    }

    # 添加图表配置

    # ===== 同花顺实时估值数据增强 =====
    print(f"[估值分析] 正在获取同花顺实时估值数据: {stock_name}...", file=sys.stderr)
    hithink_data = _query_hithink_valuation(stock_name)
    result['hithink_data'] = hithink_data

    # ===== 估值模型方法论 =====
    valuation_models = {}

    # 1. PE-Band 分析
    pe_band = _compute_pe_band(
        result.get('history', {}).get('pe', []),
        current_metrics.get('pe'),
    )
    if pe_band:
        valuation_models['pe_band'] = pe_band

    # 2. PB-ROE 分析（尝试从同花顺数据提取 ROE）
    roe = _extract_roe_from_hithink(hithink_data)
    pb_roe = _compute_pb_roe_analysis(
        current_metrics.get('pb'),
        roe,
        industry,
    )
    if pb_roe:
        valuation_models['pb_roe'] = pb_roe

    # 3. 估值方法建议
    company_type = _classify_company_type(industry)
    valuation_models['company_type'] = company_type
    valuation_models['recommended_methods'] = _get_valuation_method_advice(company_type)

    # 4. 同行业估值对比（从同花顺数据）
    ind_comp = hithink_data.get('industry_comparison', {})
    if isinstance(ind_comp, dict) and 'datas' in ind_comp and ind_comp['datas']:
        valuation_models['hithink_industry_comparison'] = ind_comp['datas'][:5]

    # 5. 股息数据（用于 DDM 判断）
    div_data = hithink_data.get('dividend_data', {})
    if isinstance(div_data, dict) and 'datas' in div_data and div_data['datas']:
        valuation_models['dividend_info'] = div_data['datas'][:3]
        # 判断是否适合 DDM
        dividend_yield = _extract_dividend_yield(div_data)
        if dividend_yield and dividend_yield > 2.0:
            valuation_models['ddm_suitable'] = True
            valuation_models['ddm_reason'] = f'股息率{dividend_yield:.1f}%>2%，适合DDM估值'

    result['valuation_models'] = valuation_models

    # ===== 估值陷阱检测 =====
    trap_detection = _detect_valuation_traps(stock_name, result, hithink_data)
    result['trap_detection'] = trap_detection

    # ===== 综合估值结论 =====
    result['valuation_summary'] = _generate_valuation_summary(result)

    return result


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='个股相对估值分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    stock_input = args.stock

    try:
        result = analyze_stock_valuation(stock_input)
    except Exception as e:
        result = {'error': str(e)}

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    if 'error' in result:
        print(f"错误: {result['error']}")
        sys.exit(1)

    # 输出分析结果
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

if __name__ == '__main__':
    main()
