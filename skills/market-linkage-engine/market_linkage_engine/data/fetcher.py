"""
市场联动分析引擎 — 数据获取层 (LinkageFetcher)

统一封装 8 大分析维度所需的全部原始数据获取：
  - Tushare Pro API（结构化历史数据，T+1）
  - 同花顺问财 OpenAPI（实时/盘中数据补充）

设计原则：
  1. 所有 fetch_* 方法返回干净的 pandas.DataFrame（已排序、去重、列名规整）
  2. 失败返回空 DataFrame，不抛异常（上层可优雅降级）
  3. 自动限速由底层 kk_common.TushareClient 完成
"""
from __future__ import annotations

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import pandas as pd

# ---------------------------------------------------------------------
# 接入 common（提供 TushareClient + IwencaiClient）
# 通过 sys.path 注入同级 common 包，兼容多种安装方式。
# 目录结构：public/<skill>/<pkg>/data/fetcher.py → 向上 3 级到 public/，
# 再取同级 common/src（此前多算一级指向 skills/common/src，注入从未生效）。
# ---------------------------------------------------------------------
_KK_COMMON_SRC = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "common", "src")
)
if os.path.isdir(_KK_COMMON_SRC) and _KK_COMMON_SRC not in sys.path:
    sys.path.insert(0, _KK_COMMON_SRC)

try:
    from kk_common import get_tushare_client, IwencaiClient  # type: ignore
    _HAS_KK_COMMON = True
except Exception as e:  # pragma: no cover - 环境异常兜底
    _HAS_KK_COMMON = False
    logging.getLogger(__name__).warning(
        "common 未安装，将仅支持离线/测试模式。原因: %s", e
    )

logger = logging.getLogger("market_linkage_engine.fetcher")


class LinkageFetcher:
    """统一数据获取器，对接 Tushare + 同花顺问财。

    Parameters
    ----------
    use_iwencai : bool
        是否启用问财实时补充数据（默认 False，仅用 Tushare）。
    iwencai_skill_name : str
        问财上报的 skill_name。
    """

    def __init__(
        self,
        use_iwencai: bool = False,
        iwencai_skill_name: str = "market-linkage-engine",
    ):
        self.use_iwencai = use_iwencai
        self.iwencai_skill_name = iwencai_skill_name

        if not _HAS_KK_COMMON:
            raise RuntimeError(
                "未找到 common 公共库，请先安装：\n"
                "  pip install -e ../common\n"
                "或确保 ../common/src 在 PYTHONPATH 中。"
            )

        self.ts = get_tushare_client()
        # 原始 pro 对象，用于调用 common 尚未封装的接口（shibor/opt_daily/hsgt_top10）
        self.pro = getattr(self.ts, "pro", None)
        self._iwencai: Optional[Any] = None

    # ------------------------------------------------------------------
    #  通用工具
    # ------------------------------------------------------------------
    @staticmethod
    def _date_range(days: int, end: Optional[str] = None) -> tuple[str, str]:
        end_dt = datetime.strptime(end, "%Y%m%d") if end else datetime.now()
        start_dt = end_dt - timedelta(days=days)
        return start_dt.strftime("%Y%m%d"), end_dt.strftime("%Y%m%d")

    @staticmethod
    def _clean(df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:
        if df is None or len(df) == 0:
            return pd.DataFrame()
        df = df.copy()
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.sort_values(date_col).drop_duplicates().reset_index(drop=True)
        return df

    def _raw(self, api: str, **kwargs) -> pd.DataFrame:
        """直接调用 tushare pro 原始接口（带空值兜底）。"""
        if self.pro is None:
            return pd.DataFrame()
        try:
            fn = getattr(self.pro, api)
            df = fn(**kwargs)
            return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
        except Exception as e:
            logger.warning("pro.%s 调用失败: %s", api, e)
            return pd.DataFrame()

    # ==================================================================
    #  1. 主力资金（个股 + 板块）
    # ==================================================================
    def fetch_main_capital_stocks(self, trade_date: str, top_n: int = 200) -> pd.DataFrame:
        """个股主力资金流向 moneyflow（按 trade_date，返回全市场）。

        注意：不能只取流入 topN——否则"净流出榜"会变成流入较少者。
        全量返回（约 5000+ 行），由分析器自行取流入/流出两端。
        """
        df = self.ts.moneyflow(trade_date=trade_date)
        if len(df) == 0:
            return pd.DataFrame()
        sort_col = "net_amount" if "net_amount" in df.columns else \
            ("net_mf_amount" if "net_mf_amount" in df.columns else df.columns[-1])
        return df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    def fetch_main_capital_sector(self, trade_date: str) -> pd.DataFrame:
        """板块主力资金流向 moneyflow_dc（行业板块）。"""
        df = self.ts.moneyflow_dc(trade_date=trade_date)
        if len(df) == 0:
            return pd.DataFrame()
        sort_col = "net_amount" if "net_amount" in df.columns else df.columns[-1]
        return df.sort_values(sort_col, ascending=False).reset_index(drop=True)

    def fetch_main_capital_industry_ths(self, trade_date: str) -> pd.DataFrame:
        """同花顺行业资金流向 moneyflow_ind_ths。"""
        df = self.ts.moneyflow_ind_ths(trade_date=trade_date)
        return df.reset_index(drop=True) if len(df) else df

    # ==================================================================
    #  2. 北向资金
    # ==================================================================
    def fetch_northbound(self, days: int = 30, end: Optional[str] = None) -> pd.DataFrame:
        """沪深港通每日资金流向（使用 moneyflow_hsgt 接口，支持日期范围）。"""
        start, end = self._date_range(days, end)
        try:
            df = self.ts.moneyflow_hsgt(start_date=start, end_date=end)
        except Exception:
            # Fallback to hsgt interface for older tokens
            try:
                df = self.ts.hsgt(start_date=start, end_date=end)
            except Exception:
                return pd.DataFrame()
        return self._clean(df)

    def fetch_northbound_top10(self, trade_date: str, market: str = "north") -> pd.DataFrame:
        """十大成交股 hsgt_top10（north=北向, south=南向）。"""
        df = self.ts.hsgt_top10(trade_date=trade_date)
        return df.reset_index(drop=True) if len(df) else df

    # ==================================================================
    #  3. 两融
    # ==================================================================
    def fetch_margin_daily(self, days: int = 60, end: Optional[str] = None) -> pd.DataFrame:
        """全市场两融日数据 margin。"""
        start, end = self._date_range(days, end)
        df = self.ts.margin(start_date=start, end_date=end)
        return self._clean(df)

    def fetch_margin_detail(self, trade_date: str, top_n: int = 50) -> pd.DataFrame:
        """个股融资融券明细 margin_detail。"""
        df = self.ts.margin_detail(trade_date=trade_date)
        if len(df) == 0:
            return pd.DataFrame()
        sort_col = "rzye" if "rzye" in df.columns else df.columns[-1]
        df = df.sort_values(sort_col, ascending=False).head(top_n)
        return df.reset_index(drop=True)

    # ==================================================================
    #  4. 股指期货基差
    # ==================================================================
    def fetch_futures_daily(
        self, ts_code: str, days: int = 30, end: Optional[str] = None
    ) -> pd.DataFrame:
        """股指期货日行情 fut_daily。"""
        start, end = self._date_range(days, end)
        df = self.ts.fut_daily(ts_code=ts_code, start_date=start, end_date=end)
        return self._clean(df)

    def fetch_index_daily(
        self, ts_code: str, days: int = 30, end: Optional[str] = None
    ) -> pd.DataFrame:
        """指数日线 index_daily。"""
        start, end = self._date_range(days, end)
        df = self.ts.index_daily(ts_code=ts_code, start_date=start, end_date=end)
        return self._clean(df)

    def fetch_futures_holding(self, symbol: str, trade_date: Optional[str] = None,
                              days: int = 7) -> pd.DataFrame:
        """期货会员持仓排名 fut_holding。"""
        start, end = self._date_range(days)
        df = self.ts.fut_holding(symbol=symbol, trade_date=trade_date,
                                 start_date=start, end_date=end)
        return df.reset_index(drop=True) if len(df) else df

    # ==================================================================
    #  5. 期权波动率
    # ==================================================================
    def fetch_option_basic(self, exchange: str) -> pd.DataFrame:
        """期权合约基础信息 opt_basic（含 call_put / exercise_price / maturity_date）。"""
        try:
            df = self.ts.opt_basic(exchange=exchange)
        except Exception:
            return pd.DataFrame()
        return df.reset_index(drop=True) if len(df) else df

    def fetch_option_daily(
        self, ts_code: Optional[str] = None, trade_date: Optional[str] = None,
        days: int = 30, end: Optional[str] = None, exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """期权日线 opt_daily（含隐含波动率）。

        通过 common 封装的 opt_daily 调用。
        """
        if trade_date is None:
            start, end = self._date_range(days, end)
        else:
            start = end = trade_date
        kwargs = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if trade_date:
            kwargs["trade_date"] = trade_date
        else:
            kwargs["start_date"] = start
            kwargs["end_date"] = end
        if exchange:
            kwargs["exchange"] = exchange
        df = self.ts.opt_daily(
            ts_code=kwargs.get("ts_code"),
            trade_date=kwargs.get("trade_date"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            exchange=kwargs.get("exchange"),
        )
        return self._clean(df)

    # ==================================================================
    #  6. 宽基 ETF 份额
    # ==================================================================
    def fetch_fund_daily(
        self, ts_code: str, days: int = 90, end: Optional[str] = None
    ) -> pd.DataFrame:
        """场内 ETF 日线 fund_daily。"""
        start, end = self._date_range(days, end)
        df = self.ts.fund_daily(ts_code=ts_code, start_date=start, end_date=end)
        return self._clean(df)

    def fetch_fund_share(
        self, ts_code: str, days: int = 90, end: Optional[str] = None
    ) -> pd.DataFrame:
        """基金每日份额 fund_share。"""
        start, end = self._date_range(days, end)
        df = self.ts.fund_share(ts_code=ts_code, start_date=start, end_date=end)
        return self._clean(df)

    # ==================================================================
    #  7. Shibor 利率
    # ==================================================================
    def fetch_shibor(self, days: int = 180, end: Optional[str] = None) -> pd.DataFrame:
        """Shibor 银行间拆放利率 shibor。"""
        start, end = self._date_range(days, end)
        df = self.ts.shibor(start_date=start, end_date=end)
        return self._clean(df, date_col="date")

    def fetch_shibor_lpr(self, days: int = 720, end: Optional[str] = None) -> pd.DataFrame:
        """LPR 贷款基础利率 shibor_lpr。"""
        start, end = self._date_range(days, end)
        df = self.ts.shibor_lpr(start_date=start, end_date=end)
        return self._clean(df, date_col="date")

    # ==================================================================
    #  8. 龙虎榜
    # ==================================================================
    def fetch_dragon_tiger_list(self, trade_date: str) -> pd.DataFrame:
        """龙虎榜每日明细 top_list。"""
        df = self.ts.top_list(trade_date=trade_date)
        return df.reset_index(drop=True) if len(df) else df

    def fetch_dragon_tiger_inst(self, trade_date: str) -> pd.DataFrame:
        """龙虎榜机构成交明细 top_inst。"""
        df = self.ts.top_inst(trade_date=trade_date)
        return df.reset_index(drop=True) if len(df) else df

    # ==================================================================
    #  问财（同花顺）实时数据补充
    # ==================================================================
    def iwencai_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """通过问财 OpenAPI 执行自然语言查询，返回结构化字典。

        典型查询：
          - "今日主力资金净流入前10的板块"
          - "北向资金今日净买入个股"
          - "今日涨停的股票"
          - "ETF最新份额变化"
        """
        if not self.use_iwencai:
            raise RuntimeError("use_iwencai=False，请初始化时启用问财。")
        if self._iwencai is None:
            self._iwencai = IwencaiClient(skill_name=self.iwencai_skill_name)
        return self._iwencai.query(query, limit=limit)
