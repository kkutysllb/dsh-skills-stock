#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KStock 本地行情数据磁盘缓存（Tushare 侧）。

动机：技能脚本每次任务都在线重拉同样的历史行情，重复消耗 Tushare 积分
并拖慢任务。历史 K 线/估值/资金流等时间序列一旦收盘即不可变，值得按
「接口 + 参数」落盘复用；跨任务、跨线程共享。

存储：CSV + meta.json（不引入 pyarrow 依赖，打包 runtime 只有 pandas）。
目录解析顺序：
  1. KSTOCK_MARKET_DATA_CACHE_DIR 显式指定（测试用）；
  2. /mnt/cache/market-data（QiLin 沙箱挂载视图；dsh 宿主上不存在，自动跳过）；
  3. <宿主 home>/dsh-skills-stock/cache/market-data（dsh 数据根；宿主 home
     按 $QILIN_HOME → $DSH_HOME → ~/.dsh 解析，与插件凭据/三库同根）。

开关：KSTOCK_MARKET_DATA_CACHE=0/false 关闭（默认开启）。该变量不含
scrub 关键字（KEY/TOKEN/SECRET/PASS），经沙箱 env 继承机制自动透传给
所有 bash 子进程，无需 secrets 白名单。

数据纪律：
  - 只缓存白名单接口（见 _RANGE_APIS / _SNAPSHOT_TTL）；
  - 空 DataFrame 一律不落盘（上游客户端把接口失败也吞成空 DF，落盘会
    污染缓存）；
  - 时间序列按日期增量合并，尾部 7 个自然日重叠刷新（覆盖盘中拉取的
    未收盘数据被次日修正的情况）；
  - 原子写（tempfile + os.replace），并发 last-write-wins。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

_ENV_DISABLE = "KSTOCK_MARKET_DATA_CACHE"
_ENV_DIR = "KSTOCK_MARKET_DATA_CACHE_DIR"

# 时间序列接口：api -> (日期列, 起始参数, 结束参数)。历史不可变，增量合并。
_RANGE_APIS: Dict[str, Tuple[str, str, str]] = {
    "daily": ("trade_date", "start_date", "end_date"),
    "weekly": ("trade_date", "start_date", "end_date"),
    "monthly": ("trade_date", "start_date", "end_date"),
    "pro_bar": ("trade_date", "start_date", "end_date"),
    "daily_basic": ("trade_date", "start_date", "end_date"),
    "index_daily": ("trade_date", "start_date", "end_date"),
    "index_dailybasic": ("trade_date", "start_date", "end_date"),
    "sw_daily": ("trade_date", "start_date", "end_date"),
    "moneyflow": ("trade_date", "start_date", "end_date"),
    "moneyflow_dc": ("trade_date", "start_date", "end_date"),
    "margin": ("trade_date", "start_date", "end_date"),
    "margin_detail": ("trade_date", "start_date", "end_date"),
    "fut_daily": ("trade_date", "start_date", "end_date"),
    "opt_daily": ("trade_date", "start_date", "end_date"),
    "fund_daily": ("trade_date", "start_date", "end_date"),
    "fund_nav": ("nav_date", "start_date", "end_date"),
    "hsgt_top10": ("trade_date", "start_date", "end_date"),
    "limit_list": ("trade_date", "start_date", "end_date"),
    "limit_list_d": ("trade_date", "start_date", "end_date"),
    "cyq_chips": ("trade_date", "start_date", "end_date"),
    # 分钟线：日期列是 trade_time（"2024-01-05 09:31:00"），起止参数同样带
    # 时间；比较按「去非数字」后字典序（前缀对齐 YYYYMMDD，8 位起点可与
    # 14 位 K 线时间正确比较）。重叠窗口缩短到 1 天（7 天 × 240 根/日太大）。
    "stk_mins": ("trade_time", "start_date", "end_date"),
}

# 日期时间型时间序列（日期列/参数带 HH:MM 部分，比较走去非数字归一）。
_DATETIME_RANGE_APIS = frozenset({"stk_mins"})
# 增量尾部重叠窗口（自然日），按接口覆盖；默认 7 天。
_RANGE_OVERLAP_DAYS: Dict[str, int] = {"stk_mins": 1}

# 快照接口：api -> TTL 秒。参考类 7 天；按日发布且盘后不可变的榜单 36 小时；
# 其余（无起止参数的时间序列请求）统一 8 小时兜底。
_SNAPSHOT_TTL: Dict[str, float] = {
    "stock_basic": 7 * 86400,
    "fund_basic": 7 * 86400,
    "fut_basic": 7 * 86400,
    "opt_basic": 7 * 86400,
    "trade_cal": 7 * 86400,
    "namechange": 86400,
    "top_list": 36 * 3600,
    "top_inst": 36 * 3600,
}
_FALLBACK_SNAPSHOT_TTL = 8 * 3600
# 增量拉取时与已缓存尾部的重叠窗口（自然日），覆盖盘中未收盘数据修正。
_TAIL_OVERLAP_DAYS = 7


def _env_flag_disabled() -> bool:
    return os.getenv(_ENV_DISABLE, "").strip().lower() in ("0", "false", "no", "off")


def cache_dir() -> Optional[str]:
    """解析缓存目录；不可用返回 None（缓存整体旁路）。"""
    explicit = os.getenv(_ENV_DIR, "").strip()
    if explicit:
        return explicit
    for candidate in ("/mnt/cache/market-data",):
        if os.path.isdir(candidate):
            return candidate
    # dsh-skills-stock 数据根：跟随宿主 home（$QILIN_HOME → $DSH_HOME →
    # ~/.dsh），缓存落在 <数据根>/cache/market-data，首次写入自动建目录。
    root = os.getenv("QILIN_HOME", "").strip() or os.getenv("DSH_HOME", "").strip() \
        or os.path.join(os.path.expanduser("~"), ".dsh")
    return os.path.join(root, "dsh-skills-stock", "cache", "market-data")


def handles(endpoint: str) -> bool:
    """该接口是否被缓存覆盖（白名单 + 开关 + 目录可用）。"""
    if _env_flag_disabled():
        return False
    if endpoint not in _RANGE_APIS and endpoint not in _SNAPSHOT_TTL:
        return False
    return cache_dir() is not None


def _param_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _cache_key(endpoint: str, params: Dict[str, Any], exclude: Tuple[str, ...] = ()) -> str:
    material = json.dumps(
        {k: _param_str(v) for k, v in sorted(params.items()) if k not in exclude},
        ensure_ascii=False, sort_keys=True,
    )
    digest = hashlib.sha1(f"{endpoint}\n{material}".encode("utf-8")).hexdigest()
    return os.path.join(cache_dir() or "", endpoint, digest)  # type: ignore[arg-type]


def _read_cache(key_dir: str) -> Optional[Tuple[pd.DataFrame, Dict[str, Any]]]:
    try:
        with open(os.path.join(key_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        # dtype 名原样回放（"object"/"int64"/"float64"）；pandas3 下 str 内建
        # 会映射成 StringDtype，与 tushare 返回的 object 不一致。
        dtypes = meta.get("dtypes", {})
        df = pd.read_csv(os.path.join(key_dir, "data.csv"), dtype=dtypes)
        return df, meta
    except Exception:
        return None


def _atomic_write(path: str, content: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _store_df(key_dir: str, endpoint: str, df: pd.DataFrame, meta_extra: Dict[str, Any]) -> None:
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    meta = {
        "endpoint": endpoint,
        "fetched_at": time.time(),
        "rows": int(len(df)),
        "dtypes": dtypes,
        **meta_extra,
    }
    _atomic_write(
        os.path.join(key_dir, "meta.json"),
        json.dumps(meta, ensure_ascii=False).encode("utf-8"),
    )
    _atomic_write(
        os.path.join(key_dir, "data.csv"),
        df.to_csv(index=False).encode("utf-8"),
    )


def _normalize_date(value: Any, datetime_mode: bool = False) -> Optional[str]:
    """统一边界值为可比较的数字串；无效返回 None。

    日期模式：YYYYMMDD / YYYY-MM-DD → 8 位。
    日期时间模式（分钟线）：剥离全部非数字，接受 8（仅日期）/ 12 / 14 位；
    与 14 位的 trade_time 值做字典序比较时前缀对齐，语义正确。
    """
    digits = "".join(ch for ch in _param_str(value).strip() if ch.isdigit())
    if not digits:
        return None
    if datetime_mode:
        return digits if len(digits) in (8, 12, 14) else None
    return digits if len(digits) == 8 else None


def wrap_request(
    endpoint: str,
    params: Dict[str, Any],
    fetch: Callable[[Dict[str, Any]], pd.DataFrame],
) -> pd.DataFrame:
    """缓存包装：命中直接返回；未命中收缩增量窗口后 fetch 并合并落盘。

    fetch 参数是「执行实际网络请求」的回调（gateway 适配器），本函数
    负责命中判定、增量窗口收缩、合并去重与落盘。
    """
    if not handles(endpoint):
        return fetch(params)

    range_spec = _RANGE_APIS.get(endpoint)
    dt_mode = endpoint in _DATETIME_RANGE_APIS
    start = _normalize_date(params.get(range_spec[1]), dt_mode) if range_spec else None
    end = _normalize_date(params.get(range_spec[2]), dt_mode) if range_spec else None
    # 无起止参数的时间序列请求按快照 TTL 兜底（如单日 trade_date 查询）。
    if range_spec is not None and (start is None or end is None):
        range_spec = None

    if range_spec is not None:
        date_col, start_param, end_param = range_spec
        key_dir = _cache_key(endpoint, params, exclude=(start_param, end_param))
        # 比较基准：日期列与边界统一「去非数字」后字典序（日线 8 位，
        # 分钟线 14 位 trade_time；8 位起点与 14 位值前缀对齐可正确比较）。
        cached = _read_cache(key_dir)
        if cached is not None:
            cached_df, meta = cached
            if date_col in cached_df.columns and not cached_df.empty:
                col_digits = cached_df[date_col].astype(str).str.replace(r"\D", "", regex=True)
                lo = str(col_digits.min())
                hi = str(col_digits.max())
                # fetched_start：产生/扩展本缓存那次拉取的起始边界（归一化）。
                # 请求 start 早于首根数据（如 09:00 vs 09:31 首根分钟线）不代表
                # 缺数据——只要 start 不早于 fetched_start，09:31 之前本就无数据。
                fetch_floor = str(meta.get("fetched_start") or lo)
                # probe_end：已向上游探测过「无更多数据」的终点（如收盘后
                # end 超过最后一根 K 线）。探测后 6 小时内同范围请求纯命中，
                # 避免重复请求每次都打一次 API。
                probe_end = str(meta.get("probe_end") or "")
                probe_fresh = time.time() - float(meta.get("fetched_at", 0)) < 6 * 3600
                if start >= fetch_floor and (end <= hi or (probe_fresh and probe_end and end <= probe_end)):
                    mask = (col_digits >= start) & (col_digits <= end)
                    return cached_df.loc[mask].reset_index(drop=True)
                if start >= fetch_floor and end > hi:
                    # 尾部缺口：仅增量拉取 [hi 日期-重叠窗口, end]，合并去重。
                    overlap_days = _RANGE_OVERLAP_DAYS.get(endpoint, _TAIL_OVERLAP_DAYS)
                    overlap_start = (
                        datetime.strptime(hi[:8], "%Y%m%d") - timedelta(days=overlap_days)
                    ).strftime("%Y%m%d")
                    fetch_start = max(start, overlap_start)
                    if dt_mode:
                        # 分钟线接口起止参数要求 "YYYY-MM-DD HH:MM:SS" 形态，
                        # 8 位纯数字会被上游拒绝；从当日 00:00 起拉全量分钟。
                        fetch_start = (
                            f"{fetch_start[:4]}-{fetch_start[4:6]}-{fetch_start[6:8]} 00:00:00"
                        )
                    fetch_params = dict(params)
                    fetch_params[start_param] = fetch_start
                    fetched = fetch(fetch_params)
                    if fetched is None or fetched.empty or date_col not in fetched.columns:
                        # 增量失败（如积分不足）：退回缓存可见部分，不落盘。
                        mask = col_digits >= start
                        return cached_df.loc[mask].reset_index(drop=True)
                    fetched_digits = fetched[date_col].astype(str).str.replace(r"\D", "", regex=True)
                    if fetched_digits.empty or str(fetched_digits.max()) <= hi:
                        # 上游确无更多数据：记录 probe_end，短时间内同范围请求纯命中。
                        _store_df(
                            key_dir, endpoint, cached_df,
                            {
                                "date_min": str(cached_df[date_col].min()),
                                "date_max": str(cached_df[date_col].max()),
                                "fetched_start": fetch_floor,
                                "probe_end": end,
                            },
                        )
                        mask = col_digits >= start
                        return cached_df.loc[mask].reset_index(drop=True)
                    merged = pd.concat([cached_df, fetched], ignore_index=True)
                    merged = merged.drop_duplicates(subset=[date_col], keep="last")
                    merged = merged.sort_values(date_col).reset_index(drop=True)
                    merged_digits = merged[date_col].astype(str).str.replace(r"\D", "", regex=True)
                    meta_extra = {
                        "date_min": str(merged[date_col].min()),
                        "date_max": str(merged[date_col].max()),
                        "fetched_start": fetch_floor,
                    }
                    if str(merged_digits.max()) < end:
                        # 已拉到 end 仍无更多数据（end 超过最后一根 K 线）：
                        # 记录 probe_end，后续同范围请求纯命中。
                        meta_extra["probe_end"] = end
                    _store_df(key_dir, endpoint, merged, meta_extra)
                    mask = (merged_digits >= start) & (merged_digits <= end)
                    return merged.loc[mask].reset_index(drop=True)
        # 完整拉取（无缓存 / 请求起点早于已探测边界，需向更早历史扩展）
        fetched = fetch(params)
        if fetched is None or fetched.empty:
            return fetched if isinstance(fetched, pd.DataFrame) else pd.DataFrame()
        if date_col not in fetched.columns:
            return fetched
        merged = fetched
        fetched_start_out = start
        if cached is not None and date_col in cached[0].columns and not cached[0].empty:
            merged = pd.concat([cached[0], fetched], ignore_index=True)
            merged = merged.drop_duplicates(subset=[date_col], keep="last")
            merged = merged.sort_values(date_col).reset_index(drop=True)
            prev_floor = str((cached[1] or {}).get("fetched_start") or "")
            if prev_floor:
                fetched_start_out = min(prev_floor, start)
        merged_digits = merged[date_col].astype(str).str.replace(r"\D", "", regex=True)
        meta_extra = {
            "date_min": str(merged[date_col].min()),
            "date_max": str(merged[date_col].max()),
            "fetched_start": fetched_start_out,
        }
        if str(merged_digits.max()) < end:
            meta_extra["probe_end"] = end
        _store_df(key_dir, endpoint, merged, meta_extra)
        return merged

    # 快照 TTL
    ttl = _SNAPSHOT_TTL.get(endpoint, _FALLBACK_SNAPSHOT_TTL)
    key_dir = _cache_key(endpoint, params)
    cached = _read_cache(key_dir)
    if cached is not None:
        cached_df, meta = cached
        if time.time() - float(meta.get("fetched_at", 0)) <= ttl:
            return cached_df
    fetched = fetch(params)
    if fetched is None or fetched.empty:
        return fetched if isinstance(fetched, pd.DataFrame) else pd.DataFrame()
    _store_df(key_dir, endpoint, fetched, {})
    return fetched
