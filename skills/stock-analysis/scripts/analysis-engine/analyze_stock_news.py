#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司相关新闻资讯分析脚本

通过同花顺问财 news-search API 检索与指定公司相关的新闻，
包括公司名称匹配和公司所属行业的相关新闻。

数据来源：同花顺问财（财经资讯搜索）

用法:
  python scripts/analysis-engine/analyze_stock_news.py --stock 000001.SZ --json
  python scripts/analysis-engine/analyze_stock_news.py --stock 茅台 --json
  python scripts/analysis-engine/analyze_stock_news.py --stock 600519 --json
"""

import argparse
import json
import os
import secrets
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_skill_root = os.path.dirname(os.path.dirname(_script_dir))
_project_root = os.path.dirname(_skill_root)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ======================================================================
#  Tushare 数据接口（仅用于股票代码解析）
# ======================================================================

def _get_tushare_api():
    from kk_common import get_finance_data_gateway
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, '.env'))
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN，请在 .env 中配置")
    return get_finance_data_gateway()


def _resolve_stock_code(ts_api, stock_input: str) -> str:
    """将用户输入的股票代码/名称解析为 ts_code 格式"""
    code = stock_input.strip()

    if '.' in code and len(code.split('.')[0]) == 6:
        return code

    if code.isdigit() and len(code) == 6:
        suffix = '.SH' if code.startswith(('6', '9')) else '.SZ'
        return code + suffix

    try:
        df = ts_api.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        match = df[df['name'] == code]
        if not match.empty:
            return match.iloc[0]['ts_code']
        match = df[df['name'].str.contains(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
        match = df[df['ts_code'].str.startswith(code, na=False)]
        if not match.empty:
            return match.iloc[0]['ts_code']
    except Exception:
        pass
    raise ValueError(f"无法识别股票: {stock_input}")


# ======================================================================
#  同花顺问财新闻搜索接口
# ======================================================================

def _search_news_iwencai(query: str, max_retries: int = 2) -> dict:
    """调用同花顺问财财经资讯搜索接口"""
    import urllib.request
    import urllib.error

    api_key = os.getenv('IWENCAI_API_KEY')
    if not api_key:
        raise ValueError("未找到 IWENCAI_API_KEY，请设置环境变量")

    url = "https://openapi.iwencai.com/v1/comprehensive/search"
    trace_id = secrets.token_hex(32)
    payload = json.dumps({
        "channels": ["news"],
        "app_id": "AIME_SKILL",
        "query": query,
    }).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": "normal",
        "X-Claw-Skill-Id": "news-search",
        "X-Claw-Skill-Version": "1.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": trace_id,
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def _parse_articles(response: dict) -> list:
    """从问财 API 响应中提取文章列表"""
    if not response or 'error' in response:
        return []
    articles = response.get('data', [])
    if not isinstance(articles, list):
        return []
    return articles


def _format_article(article: dict) -> dict:
    """统一格式化文章信息"""
    content = article.get('content', '') or article.get('summary', '') or ''
    return {
        "title": article.get('title', ''),
        "source": article.get('source', '同花顺问财'),
        "publish_date": article.get('publish_date', ''),
        "url": article.get('url', ''),
        "summary": content[:200] + '...' if len(content) > 200 else content,
    }


# ======================================================================
#  核心分析逻辑
# ======================================================================

def analyze_stock_news(stock_input: str, days: int = 7) -> dict:
    """通过问财 news-search API 获取公司新闻和行业新闻"""
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_project_root, '.env'))

    ts_api = _get_tushare_api()
    ts_code = _resolve_stock_code(ts_api, stock_input)

    # 获取公司名称和行业
    basic_df = ts_api.stock_basic(
        ts_code=ts_code,
        fields='ts_code,name,industry'
    )
    if basic_df.empty:
        return {"error": f"未找到股票 {ts_code} 的基本信息"}

    stock_name = basic_df.iloc[0]['name']
    industry = basic_df.iloc[0].get('industry', '')

    # ── 通过问财 news-search API 搜索公司相关新闻 ──
    company_news = []
    try:
        response = _search_news_iwencai(stock_name)
        articles = _parse_articles(response)
        company_news = [_format_article(a) for a in articles[:20]]
    except Exception as e:
        print(f"  ⚠️ 搜索公司新闻失败: {e}", file=sys.stderr)

    # ── 通过问财 news-search API 搜索行业相关新闻 ──
    industry_news = []
    if industry:
        try:
            response = _search_news_iwencai(f"{industry}行业")
            articles = _parse_articles(response)
            industry_news = [
                _format_article(a) for a in articles[:15]
                if stock_name not in (a.get('title', '') or '')
            ]
        except Exception as e:
            print(f"  ⚠️ 搜索行业新闻失败: {e}", file=sys.stderr)

    return {
        "stock_code": ts_code,
        "stock_name": stock_name,
        "industry": industry,
        "company_news_count": len(company_news),
        "company_news": company_news,
        "industry_news_count": len(industry_news),
        "industry_news": industry_news,
        "data_source": "同花顺问财 news-search API",
    }


# ======================================================================
#  主入口
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='公司相关新闻资讯分析')
    parser.add_argument('--stock', '-s', required=True, help='股票代码或名称')
    parser.add_argument('--days', '-d', type=int, default=7,
                        help='查询最近多少天的新闻（默认7天，最大30天）')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    args = parser.parse_args()

    try:
        result = analyze_stock_news(args.stock, args.days)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        # 格式化文本输出
        print(f"\n{'='*60}")
        print(f"  {result.get('stock_name', '')}（{result.get('stock_code', '')}）新闻资讯")
        print(f"  所属行业: {result.get('industry', '—')}")
        print(f"  查询范围: {result.get('query_period', '')}")
        print(f"{'='*60}")

        company_news = result.get('company_news', [])
        print(f"\n  【公司相关新闻】（共 {len(company_news)} 条）")
        print(f"{'─'*60}")
        if company_news:
            for i, news in enumerate(company_news[:10], 1):
                print(f"  {i}. {news.get('title', '')}")
                print(f"     来源: {news.get('source', '—')}  日期: {news.get('publish_date', '—')}")
                summary = news.get('summary', '')
                if summary:
                    print(f"     {summary[:100]}{'...' if len(summary) > 100 else ''}")
        else:
            print("  暂无公司相关新闻")

        industry_news = result.get('industry_news', [])
        print(f"\n  【行业相关新闻】（共 {len(industry_news)} 条）")
        print(f"{'─'*60}")
        if industry_news:
            for i, news in enumerate(industry_news[:10], 1):
                print(f"  {i}. {news.get('title', '')}")
                print(f"     来源: {news.get('source', '—')}  日期: {news.get('publish_date', '—')}")
        else:
            print("  暂无行业相关新闻")

        print(f"\n{'='*60}")
        print(f"  数据来源: 同花顺问财 news-search API")


if __name__ == '__main__':
    main()
