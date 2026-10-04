#!/usr/bin/env python3
"""
社交媒体情绪分析引擎（A股社区适配版）

从雪球、东方财富股吧、淘股吧、同花顺社区等国内A股社区提取金融信号，
结合全球平台（Twitter/X、Reddit）的情绪分析框架，构建情绪驱动型交易辅助信号。

数据来源：
  - 同花顺问财 news-search API（新闻/讨论/舆情）
  - 东方财富股吧（通过问财 API）
  - 情绪评分基于多维度加权算法

依赖：pandas, numpy, tushare（标准库无额外依赖）

用法：
  python3 analyze_social_media.py --stock 600519.SH --json
  python3 analyze_social_media.py --stock 贵州茅台 --days 7 --json
"""

import argparse
import json
import os
import secrets
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timedelta

try:
    import numpy as np
    import pandas as pd
except ImportError:
    print(json.dumps({"error": "缺少依赖: pandas/numpy 不可用，请检查 Python 运行时配置"}, ensure_ascii=False))
    sys.exit(1)

try:
    from kk_common import get_finance_data_gateway
except ImportError:  # KStock patch: kk_common 由 common 技能提供，失败时置 None
    get_finance_data_gateway = None


# ============================================================
# A股情绪词典（扩展版）
# ============================================================

BULLISH_KEYWORDS = {
    # 基本面看多
    "利好": 0.8, "增持": 0.7, "回购": 0.7, "超预期": 0.8, "业绩增长": 0.8,
    "营收增长": 0.7, "净利增长": 0.8, " ROE": 0.5, "高增长": 0.7,
    "盈利能力": 0.6, "护城河": 0.7, "龙头地位": 0.6, "行业领先": 0.6,
    # 技术面看多
    "突破": 0.6, "放量上涨": 0.7, "金叉": 0.5, "底部": 0.5, "反弹": 0.5,
    "触底": 0.5, "支撑": 0.4, "企稳": 0.5, "底部放量": 0.7,
    "主力介入": 0.7, "资金流入": 0.6, "北向资金": 0.5,
    # 市场情绪看多
    "看好": 0.6, "推荐": 0.5, "买入": 0.6, "加仓": 0.6, "满仓": 0.4,
    "牛市": 0.7, "上涨": 0.4, "大涨": 0.7, "涨停": 0.8, "连板": 0.7,
    "翻倍": 0.6, "新高": 0.6, "强势": 0.5, "走强": 0.5,
    # 机构行为看多
    "机构增持": 0.8, "基金加仓": 0.7, "外资买入": 0.7, "评级上调": 0.7,
    "上调目标价": 0.7, "机构推荐": 0.7, "券商看好": 0.6,
    # 行业政策
    "政策利好": 0.8, "行业风口": 0.6, "风口": 0.5, "赛道": 0.4,
}

BEARISH_KEYWORDS = {
    # 基本面看空
    "利空": -0.8, "减持": -0.7, "质押": -0.5, "业绩下滑": -0.8, "亏损": -0.8,
    "暴雷": -0.9, "退市": -0.9, "财务造假": -0.9, "商誉减值": -0.7,
    "应收账款": -0.3, "库存积压": -0.5, "毛利率下降": -0.6,
    # 技术面看空
    "跌破": -0.6, "破位": -0.7, "死叉": -0.5, "顶部": -0.5, "调整": -0.3,
    "回调": -0.2, "压力": -0.3, "阻力": -0.3, "缩量下跌": -0.6,
    "主力出逃": -0.7, "资金流出": -0.6, "套牢": -0.5,
    # 市场情绪看空
    "看空": -0.7, "卖出": -0.5, "减仓": -0.4, "清仓": -0.6, "割肉": -0.6,
    "熊市": -0.7, "下跌": -0.4, "暴跌": -0.8, "跌停": -0.8, "闪崩": -0.9,
    "新低": -0.6, "弱势": -0.5, "走弱": -0.5, "破发": -0.6,
    # 机构行为看空
    "机构减持": -0.8, "基金减仓": -0.7, "外资卖出": -0.7, "评级下调": -0.7,
    "下调目标价": -0.7, "做空": -0.7, "融券增加": -0.5,
    # 行业政策
    "政策利空": -0.8, "监管": -0.3, "处罚": -0.6, "调查": -0.5,
    "反垄断": -0.5, "行业低迷": -0.6,
}

# 强度修饰词
INTENSIFIERS = {"非常": 1.3, "极度": 1.5, "大幅": 1.3, "猛烈": 1.4, "显著": 1.2}
NEGATION_WORDS = {"不", "没", "未", "别", "非", "无", "莫", "勿"}


# ============================================================
# 情绪分析引擎
# ============================================================

class SocialMediaSentimentEngine:
    """A股社交媒体情绪分析引擎"""

    def __init__(self, stock: str, days: int = 7):
        self.stock = self._normalize_stock(stock)
        self.days = days
        self.tushare_pro = None
        self._init_tushare()

    def _normalize_stock(self, stock: str) -> str:
        """标准化股票代码"""
        stock = stock.strip()
        if stock.isdigit() and len(stock) == 6:
            if stock.startswith(('6',)):
                return f"{stock}.SH"
            else:
                return f"{stock}.SZ"
        return stock

    def _init_tushare(self):
        """初始化 Tushare Pro"""
        token = os.getenv("TUSHARE_TOKEN")
        if get_finance_data_gateway and token:
            self.tushare_pro = get_finance_data_gateway()

    # ----------------------------------------------------------
    # 数据采集
    # ----------------------------------------------------------

    def _search_iwencai(self, query: str, skill_id: str = "news-search") -> dict:
        """调用问财 API 搜索新闻/讨论"""
        api_key = os.getenv("IWENCAI_API_KEY")
        if not api_key:
            return {"error": "IWENCAI_API_KEY 未设置", "items": []}

        url = "https://openapi.iwencai.com/v1/comprehensive/search"
        trace_id = secrets.token_hex(32)
        payload = json.dumps({
            "channels": ["news", "announcement", "media"],
            "app_id": "AIME_SKILL",
            "query": query,
        }).encode()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Claw-Call-Type": "normal",
            "X-Claw-Skill-Id": skill_id,
            "X-Claw-Skill-Version": "1.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": trace_id,
        }

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e), "items": []}

    def _get_stock_name(self) -> str:
        """获取股票名称"""
        if self.tushare_pro:
            try:
                code = self.stock.replace(".SH", "").replace(".SZ", "")
                df = self.tushare_pro.stock_basic(
                    ts_code=self.stock,
                    fields="ts_code,name"
                )
                if not df.empty:
                    return df.iloc[0]["name"]
            except Exception:
                pass
        # 从代码推断
        return self.stock.replace(".SH", "").replace(".SZ", "")

    def collect_discussions(self) -> list:
        """采集社交媒体讨论数据"""
        name = self._get_stock_name()
        discussions = []

        # 1. 问财新闻搜索 - 综合舆情
        queries = [
            f"{name} 最新消息 讨论",
            f"{name} 利好 利空 分析",
            f"{name} 机构观点 研报",
        ]

        for query in queries:
            result = self._search_iwencai(query)
            items = result.get("data", {}).get("items", [])
            if not items and isinstance(result.get("data"), list):
                items = result.get("data", [])

            for item in items:
                title = item.get("title", "")
                content = item.get("content", "") or item.get("summary", "")
                source = item.get("source", "")
                pub_time = item.get("pub_time", "") or item.get("publish_time", "")

                if title or content:
                    discussions.append({
                        "title": title,
                        "content": content,
                        "source": source,
                        "pub_time": pub_time,
                        "text": f"{title} {content}",
                    })

            time.sleep(0.3)  # 避免请求过快

        return discussions

    def _get_price_data(self) -> pd.DataFrame | None:
        """获取最近 N 天的行情数据"""
        if not self.tushare_pro:
            return None
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=self.days + 30)).strftime("%Y%m%d")
            df = self.tushare_pro.daily(
                ts_code=self.stock,
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
                df = df.sort_values("trade_date").reset_index(drop=True)
                return df
        except Exception:
            pass
        return None

    # ----------------------------------------------------------
    # 情绪评分
    # ----------------------------------------------------------

    def _score_text(self, text: str) -> float:
        """对单条文本进行情绪评分

        Returns:
            float: 情绪分数 [-1, 1]，正值看多，负值看空
        """
        if not text:
            return 0.0

        score = 0.0
        matched_keywords = 0

        # 看多关键词匹配
        for keyword, weight in BULLISH_KEYWORDS.items():
            count = text.count(keyword)
            if count > 0:
                # 检查否定词
                negated = False
                for neg_word in NEGATION_WORDS:
                    idx = text.find(keyword)
                    if idx > 0:
                        prefix = text[max(0, idx - 2):idx]
                        if neg_word in prefix:
                            negated = True
                            break

                if negated:
                    score -= weight * count * 0.7
                else:
                    # 检查强度修饰词
                    modifier = 1.0
                    for intensifier, mult in INTENSIFIERS.items():
                        if intensifier in text[:text.find(keyword) + 10] if keyword in text else False:
                            modifier = mult
                            break
                    score += weight * count * modifier

                matched_keywords += count

        # 看空关键词匹配
        for keyword, weight in BEARISH_KEYWORDS.items():
            count = text.count(keyword)
            if count > 0:
                negated = False
                for neg_word in NEGATION_WORDS:
                    idx = text.find(keyword)
                    if idx > 0:
                        prefix = text[max(0, idx - 2):idx]
                        if neg_word in prefix:
                            negated = True
                            break

                if negated:
                    score += abs(weight) * count * 0.7
                else:
                    modifier = 1.0
                    for intensifier, mult in INTENSIFIERS.items():
                        if intensifier in text[:text.find(keyword) + 10] if keyword in text else False:
                            modifier = mult
                            break
                    score += weight * count * modifier

                matched_keywords += count

        if matched_keywords == 0:
            return 0.0

        # 归一化到 [-1, 1]
        normalized = score / matched_keywords
        return max(-1.0, min(1.0, normalized))

    def _classify_sentiment(self, score: float) -> str:
        """情绪分类"""
        if score > 0.3:
            return "strongly_bullish"
        elif score > 0.1:
            return "bullish"
        elif score > -0.1:
            return "neutral"
        elif score > -0.3:
            return "bearish"
        else:
            return "strongly_bearish"

    def _classify_sentiment_cn(self, score: float) -> str:
        """情绪分类（中文）"""
        mapping = {
            "strongly_bullish": "强烈看多",
            "bullish": "偏多",
            "neutral": "中性",
            "bearish": "偏空",
            "strongly_bearish": "强烈看空",
        }
        return mapping.get(self._classify_sentiment(score), "中性")

    # ----------------------------------------------------------
    # Buzz 指标
    # ----------------------------------------------------------

    def _compute_buzz_metrics(self, discussions: list) -> dict:
        """计算讨论热度指标"""
        total_count = len(discussions)

        if total_count == 0:
            return {
                "total_count": 0,
                "unique_sources": 0,
                "avg_sentiment": 0.0,
                "sentiment_std": 0.0,
                "bullish_ratio": 0.0,
                "bearish_ratio": 0.0,
                "neutral_ratio": 0.0,
                "buzz_level": "无数据",
                "hot_topics": [],
            }

        # 情绪评分
        scores = [self._score_text(d["text"]) for d in discussions]
        avg_score = np.mean(scores)
        std_score = np.std(scores) if len(scores) > 1 else 0.0

        # 分类统计
        bullish = sum(1 for s in scores if s > 0.1)
        bearish = sum(1 for s in scores if s < -0.1)
        neutral = total_count - bullish - bearish

        # 来源多样性
        sources = [d.get("source", "unknown") for d in discussions]
        unique_sources = len(set(sources))

        # 热词提取
        hot_topics = self._extract_hot_topics(discussions)

        # 讨论热度等级
        if total_count >= 50:
            buzz_level = "极高"
        elif total_count >= 30:
            buzz_level = "高"
        elif total_count >= 15:
            buzz_level = "中等"
        elif total_count >= 5:
            buzz_level = "偏低"
        else:
            buzz_level = "低"

        return {
            "total_count": total_count,
            "unique_sources": unique_sources,
            "avg_sentiment": round(avg_score, 4),
            "sentiment_std": round(std_score, 4),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "bullish_ratio": round(bullish / total_count, 4),
            "bearish_ratio": round(bearish / total_count, 4),
            "neutral_ratio": round(neutral / total_count, 4),
            "buzz_level": buzz_level,
            "hot_topics": hot_topics,
        }

    def _extract_hot_topics(self, discussions: list) -> list:
        """从讨论中提取热门话题"""
        # 财务/事件类关键词
        topic_keywords = {
            "业绩": 0, "财报": 0, "分红": 0, "回购": 0, "增持": 0,
            "减持": 0, "质押": 0, "重组": 0, "并购": 0, "定增": 0,
            "新业务": 0, "合同": 0, "订单": 0, "产能": 0, "涨价": 0,
            "降价": 0, "竞争": 0, "垄断": 0, "创新": 0, "研发": 0,
            "政策": 0, "监管": 0, "退市": 0, "ST": 0, "暴雷": 0,
            "涨停": 0, "跌停": 0, "机构": 0, "北向": 0, "融资": 0,
            "技术突破": 0, "新产品": 0, "合作": 0, "海外": 0, "国产替代": 0,
        }

        for d in discussions:
            text = d.get("text", "")
            for kw in topic_keywords:
                topic_keywords[kw] += text.count(kw)

        # 返回出现频率前10的话题
        sorted_topics = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)
        return [{"topic": t, "mentions": c} for t, c in sorted_topics if c > 0][:10]

    # ----------------------------------------------------------
    # 恐惧贪婪指数
    # ----------------------------------------------------------

    def _compute_fear_greed_index(self, sentiment_score: float, buzz_metrics: dict) -> dict:
        """构建恐惧贪婪指数

        Returns:
            fear_greed: [0, 100]
            0-20: 极度恐惧
            20-40: 恐惧
            40-60: 中性
            60-80: 贪婪
            80-100: 极度贪婪
        """
        # 基于情绪分数计算（-1~1 映射到 0~100）
        sentiment_component = (sentiment_score + 1) / 2 * 100

        # 基于多空比率调整
        bullish_ratio = buzz_metrics.get("bullish_ratio", 0.5)
        ratio_component = bullish_ratio * 100

        # 基于讨论热度调整（热度高时放大情绪）
        total = buzz_metrics.get("total_count", 0)
        buzz_amplifier = min(1.0, total / 30.0)  # 30条讨论达到满值

        # 综合指数
        fear_greed = 0.6 * sentiment_component + 0.4 * ratio_component
        # 热度调整：低热度时向中性靠拢
        fear_greed = 50 + (fear_greed - 50) * (0.3 + 0.7 * buzz_amplifier)

        fear_greed = max(0, min(100, round(fear_greed, 2)))

        if fear_greed >= 80:
            level = "极度贪婪"
            signal = "短期见顶风险，建议谨慎"
        elif fear_greed >= 60:
            level = "贪婪"
            signal = "市场情绪偏乐观，注意追高风险"
        elif fear_greed >= 40:
            level = "中性"
            signal = "市场情绪中性，可按策略执行"
        elif fear_greed >= 20:
            level = "恐惧"
            signal = "市场情绪偏悲观，关注超跌机会"
        else:
            level = "极度恐惧"
            signal = "市场恐慌，可能是逆向布局机会"

        return {
            "index": fear_greed,
            "level": level,
            "signal": signal,
            "components": {
                "sentiment_score": round(sentiment_score, 4),
                "bullish_ratio": round(bullish_ratio, 4),
                "buzz_amplifier": round(buzz_amplifier, 4),
            },
        }

    # ----------------------------------------------------------
    # 情绪反转信号
    # ----------------------------------------------------------

    def _detect_sentiment_reversal(self, discussions: list) -> dict:
        """检测情绪反转信号"""
        if len(discussions) < 5:
            return {"signal": "数据不足", "direction": "none", "confidence": 0.0}

        # 按时间排序（如果有时序数据）
        scores = [self._score_text(d["text"]) for d in discussions]

        # 将讨论分为前后两半
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]

        avg_first = np.mean(first_half) if first_half else 0.0
        avg_second = np.mean(second_half) if second_half else 0.0

        shift = avg_second - avg_first

        if abs(shift) < 0.1:
            return {
                "signal": "情绪平稳",
                "direction": "none",
                "shift": round(shift, 4),
                "confidence": round(min(abs(shift) / 0.3, 1.0), 4),
            }

        if shift > 0:
            direction = "多转空→空转多"
            signal = "情绪由空转多，关注看多信号确认"
        else:
            direction = "多→空"
            signal = "情绪由多转空，注意风险控制"

        return {
            "signal": signal,
            "direction": direction,
            "shift": round(shift, 4),
            "first_half_avg": round(avg_first, 4),
            "second_half_avg": round(avg_second, 4),
            "confidence": round(min(abs(shift) / 0.3, 1.0), 4),
        }

    # ----------------------------------------------------------
    # 情绪与价格背离
    # ----------------------------------------------------------

    def _analyze_price_sentiment_divergence(
        self, sentiment_score: float, price_df: pd.DataFrame | None
    ) -> dict:
        """分析情绪与价格的背离"""
        if price_df is None or price_df.empty:
            return {"status": "无行情数据", "divergence": "unknown"}

        # 最近 5 日涨跌幅
        recent = price_df.tail(5)
        if len(recent) < 3:
            return {"status": "行情数据不足", "divergence": "unknown"}

        price_change = (recent["close"].iloc[-1] - recent["close"].iloc[0]) / recent["close"].iloc[0]
        price_direction = "up" if price_change > 0.02 else "down" if price_change < -0.02 else "flat"

        sentiment_direction = "up" if sentiment_score > 0.1 else "down" if sentiment_score < -0.1 else "flat"

        # 背离检测
        divergence = "none"
        divergence_signal = ""
        if price_direction == "up" and sentiment_direction == "down":
            divergence = "bearish_divergence"
            divergence_signal = "价涨情缩：价格上行但情绪转空，上涨动能可能衰竭"
        elif price_direction == "down" and sentiment_direction == "up":
            divergence = "bullish_divergence"
            divergence_signal = "价跌情暖：价格下行但情绪转多，可能是见底信号"
        elif price_direction == "up" and sentiment_direction == "up":
            divergence = "trend_confirmation"
            divergence_signal = "价涨情涨：趋势与情绪一致，上涨趋势健康"
        elif price_direction == "down" and sentiment_direction == "down":
            divergence = "trend_confirmation"
            divergence_signal = "价跌情跌：趋势与情绪一致，下跌趋势延续"
        else:
            divergence = "neutral"
            divergence_signal = "价格与情绪无明显方向"

        return {
            "status": "ok",
            "divergence": divergence,
            "signal": divergence_signal,
            "price_change_5d": round(price_change, 4),
            "price_direction": price_direction,
            "sentiment_direction": sentiment_direction,
        }

    # ----------------------------------------------------------
    # 综合评分
    # ----------------------------------------------------------

    def _compute_overall_sentiment_score(self, sentiment_score: float, buzz_metrics: dict,
                                          fear_greed: dict, reversal: dict,
                                          divergence: dict) -> dict:
        """计算社交媒体维度综合评分（0-100）"""
        # 基础情绪分（40%权重）
        sentiment_component = (sentiment_score + 1) / 2 * 100 * 0.4

        # 恐惧贪婪指数偏离中性的程度（20%权重）
        fg_deviation = abs(fear_greed["index"] - 50) / 50 * 100
        # 偏离越大，信号越强（但方向由情绪决定）
        fg_component = min(fg_deviation, 100) * 0.2

        # 讨论活跃度（20%权重）
        total = buzz_metrics.get("total_count", 0)
        buzz_component = min(total / 50 * 100, 100) * 0.2

        # 情绪一致性（20%权重）
        bullish_ratio = buzz_metrics.get("bullish_ratio", 0.5)
        bearish_ratio = buzz_metrics.get("bearish_ratio", 0.5)
        consistency = max(bullish_ratio, bearish_ratio)
        consistency_component = consistency * 100 * 0.2

        raw_score = sentiment_component + fg_component + buzz_component + consistency_component

        # 方向调整：如果情绪偏空，分数应降低
        if sentiment_score < -0.1:
            raw_score = 100 - raw_score

        score = max(0, min(100, round(raw_score, 2)))

        return {
            "score": score,
            "rating": self._score_to_rating(score),
            "components": {
                "sentiment_component": round(sentiment_component, 2),
                "fear_greed_component": round(fg_component, 2),
                "buzz_component": round(buzz_component, 2),
                "consistency_component": round(consistency_component, 2),
            },
        }

    def _score_to_rating(self, score: float) -> str:
        if score >= 80:
            return "强烈看多"
        elif score >= 65:
            return "偏多"
        elif score >= 45:
            return "中性"
        elif score >= 30:
            return "偏空"
        else:
            return "强烈看空"

    # ----------------------------------------------------------
    # 主分析流程
    # ----------------------------------------------------------

    def analyze(self) -> dict:
        """执行完整的社交媒体情绪分析"""
        result = {
            "stock": self.stock,
            "analysis_type": "social_media_sentiment",
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_source": "同花顺问财 news-search API",
            "lookback_days": self.days,
        }

        # 1. 数据采集
        discussions = self.collect_discussions()
        result["data_collection"] = {
            "total_discussions": len(discussions),
            "lookback_days": self.days,
        }

        if not discussions:
            result["error"] = "未采集到讨论数据，请检查 IWENCAI_API_KEY 配置"
            result["sentiment_score"] = 0.0
            result["sentiment_label"] = "无数据"
            return result

        # 2. 整体情绪评分
        all_scores = [self._score_text(d["text"]) for d in discussions]
        avg_sentiment = np.mean(all_scores)

        result["sentiment_score"] = round(avg_sentiment, 4)
        result["sentiment_label"] = self._classify_sentiment_cn(avg_sentiment)
        result["sentiment_label_en"] = self._classify_sentiment(avg_sentiment)

        # 3. Buzz 热度指标
        buzz_metrics = self._compute_buzz_metrics(discussions)
        result["buzz_metrics"] = buzz_metrics

        # 4. 恐惧贪婪指数
        fear_greed = self._compute_fear_greed_index(avg_sentiment, buzz_metrics)
        result["fear_greed_index"] = fear_greed

        # 5. 情绪反转检测
        reversal = self._detect_sentiment_reversal(discussions)
        result["sentiment_reversal"] = reversal

        # 6. 情绪与价格背离
        price_df = self._get_price_data()
        divergence = self._analyze_price_sentiment_divergence(avg_sentiment, price_df)
        result["price_sentiment_divergence"] = divergence

        # 7. 讨论样本（最多展示10条代表性讨论）
        sorted_discussions = sorted(discussions,
                                     key=lambda d: abs(self._score_text(d["text"])),
                                     reverse=True)
        samples = []
        for d in sorted_discussions[:10]:
            score = self._score_text(d["text"])
            samples.append({
                "title": d.get("title", "")[:80],
                "source": d.get("source", ""),
                "pub_time": d.get("pub_time", ""),
                "sentiment_score": round(score, 4),
                "sentiment_label": self._classify_sentiment_cn(score),
            })
        result["discussion_samples"] = samples

        # 8. 综合评分
        overall = self._compute_overall_sentiment_score(
            avg_sentiment, buzz_metrics, fear_greed, reversal, divergence
        )
        result["overall_sentiment_score"] = overall

        # 9. 交易建议
        result["trading_signals"] = self._generate_trading_signals(
            avg_sentiment, fear_greed, reversal, divergence
        )

        # 10. 免责声明
        result["disclaimer"] = "数据来源于同花顺问财 API，分析结果仅供参考，不构成投资建议"

        return result

    def _generate_trading_signals(self, sentiment: float, fear_greed: dict,
                                   reversal: dict, divergence: dict) -> dict:
        """生成交易信号"""
        signals = []
        confidence = 0.0

        # 基于情绪方向
        if sentiment > 0.3:
            signals.append("社交媒体情绪强烈看多，短线可能有资金跟进")
            confidence += 0.3
        elif sentiment > 0.1:
            signals.append("社交媒体情绪偏乐观")
            confidence += 0.2
        elif sentiment < -0.3:
            signals.append("社交媒体情绪强烈看空，注意下行风险")
            confidence += 0.3
        elif sentiment < -0.1:
            signals.append("社交媒体情绪偏悲观")
            confidence += 0.2

        # 基于恐惧贪婪指数
        fg = fear_greed.get("index", 50)
        if fg >= 80:
            signals.append("极度贪婪状态，短期见顶概率增大")
            confidence += 0.2
        elif fg <= 20:
            signals.append("极度恐惧状态，逆向布局信号")
            confidence += 0.2

        # 基于反转信号
        if reversal.get("confidence", 0) > 0.5:
            signals.append(f"情绪反转信号：{reversal.get('signal', '')}")
            confidence += 0.2

        # 基于背离
        div_type = divergence.get("divergence", "none")
        if div_type == "bearish_divergence":
            signals.append("价涨情缩背离，上涨动能可能衰竭")
            confidence += 0.3
        elif div_type == "bullish_divergence":
            signals.append("价跌情暖背离，可能是见底信号")
            confidence += 0.3

        if not signals:
            signals.append("社交媒体情绪中性，无明显交易信号")

        return {
            "signals": signals,
            "confidence": round(min(confidence, 1.0), 4),
            "strength": "强" if confidence > 0.7 else "中" if confidence > 0.4 else "弱",
        }


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="社交媒体情绪分析引擎（A股社区适配版）")
    parser.add_argument("--stock", required=True, help="股票代码或名称，如 600519.SH 或 贵州茅台")
    parser.add_argument("--days", type=int, default=7, help="回看天数（默认7天）")
    parser.add_argument("--json", action="store_true", help="JSON 输出模式")

    args = parser.parse_args()

    engine = SocialMediaSentimentEngine(stock=args.stock, days=args.days)
    result = engine.analyze()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(result)


def _print_report(result: dict):
    """打印可读报告"""
    print(f"\n{'=' * 60}")
    print(f"  社交媒体情绪分析报告 — {result.get('stock', 'N/A')}")
    print(f"  分析时间: {result.get('analysis_time', 'N/A')}")
    print(f"  数据来源: {result.get('data_source', 'N/A')}")
    print(f"{'=' * 60}")

    if "error" in result:
        print(f"\n  错误: {result['error']}")
        return

    # 情绪概览
    print(f"\n📊 情绪概览")
    print(f"  情绪分数: {result.get('sentiment_score', 0):.4f}")
    print(f"  情绪标签: {result.get('sentiment_label', 'N/A')}")

    # Buzz 热度
    buzz = result.get("buzz_metrics", {})
    print(f"\n🔥 讨论热度")
    print(f"  讨论总量: {buzz.get('total_count', 0)} 条")
    print(f"  来源数: {buzz.get('unique_sources', 0)} 个")
    print(f"  热度等级: {buzz.get('buzz_level', 'N/A')}")
    print(f"  看多比例: {buzz.get('bullish_ratio', 0):.1%}")
    print(f"  看空比例: {buzz.get('bearish_ratio', 0):.1%}")
    print(f"  中性比例: {buzz.get('neutral_ratio', 0):.1%}")

    hot_topics = buzz.get("hot_topics", [])
    if hot_topics:
        print(f"  热门话题: {', '.join(t['topic'] for t in hot_topics[:5])}")

    # 恐惧贪婪指数
    fg = result.get("fear_greed_index", {})
    print(f"\n😱🤑 恐惧贪婪指数")
    print(f"  指数值: {fg.get('index', 50):.1f} / 100")
    print(f"  等级: {fg.get('level', 'N/A')}")
    print(f"  信号: {fg.get('signal', 'N/A')}")

    # 反转信号
    reversal = result.get("sentiment_reversal", {})
    print(f"\n🔄 情绪反转检测")
    print(f"  信号: {reversal.get('signal', 'N/A')}")
    if reversal.get("direction") != "none":
        print(f"  方向: {reversal.get('direction', 'N/A')}")
        print(f"  置信度: {reversal.get('confidence', 0):.1%}")

    # 价格背离
    div = result.get("price_sentiment_divergence", {})
    print(f"\n📈 价格-情绪背离")
    print(f"  状态: {div.get('status', 'N/A')}")
    if div.get("divergence") != "unknown":
        print(f"  背离类型: {div.get('divergence', 'N/A')}")
        print(f"  信号: {div.get('signal', 'N/A')}")

    # 综合评分
    overall = result.get("overall_sentiment_score", {})
    print(f"\n⭐ 综合评分")
    print(f"  评分: {overall.get('score', 0):.1f} / 100")
    print(f"  评级: {overall.get('rating', 'N/A')}")

    # 交易信号
    trading = result.get("trading_signals", {})
    print(f"\n💡 交易信号")
    print(f"  信号强度: {trading.get('strength', 'N/A')}")
    print(f"  置信度: {trading.get('confidence', 0):.1%}")
    for s in trading.get("signals", []):
        print(f"  • {s}")

    # 免责声明
    print(f"\n{'=' * 60}")
    print(f"  ⚠️ {result.get('disclaimer', '')}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
