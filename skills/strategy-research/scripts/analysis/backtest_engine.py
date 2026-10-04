"""

功能:
  - 从 SignalEngine 输出的信号评估回测表现
  - 支持单标的和组合策略
  - 计算核心指标: 总收益/年化/夏普/最大回撤/胜率/交易次数
  - 持仓记录: 每日持仓快照（标的/方向/数量/成本/市值/浮盈）
  - 调仓记录: 信号变化时的买卖明细（调仓前后持仓对比）
  - A股交易规则: T+1、涨跌停（收盘触板不成交）、停牌/零成交量的信号顺延、
    整手(100股)交易、佣金最低5元、卖出印花税、过户费、滑点
"""

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _board_limit_ratio(code: str) -> float:
    """按代码板块推断涨跌停幅度。

    创业板(300/301)与科创板(688/689) 20%，北交所(4/8/92 开头) 30%，其余 10%。
    ST 股票 5% 无法从代码判断，用 limit_ratio_overrides 显式指定。
    """
    pure = str(code).split(".")[0]
    if pure.startswith(("300", "301", "688", "689")):
        return 0.20
    if pure.startswith(("4", "8", "92")):
        return 0.30
    return 0.10


def _limit_prices(prev_close: float, code: str, overrides: Dict[str, float]) -> Tuple[float, float]:
    """按前收盘计算涨停/跌停价（交易所规则：前收盘×(1±幅度)四舍五入到分）。"""
    ratio = overrides.get(code) or _board_limit_ratio(code)
    limit_up = round(prev_close * (1 + ratio), 2)
    limit_down = round(prev_close * (1 - ratio), 2)
    return limit_up, limit_down


def run_backtest(
    data_map: Dict[str, pd.DataFrame],
    signals: Dict[str, pd.Series],
    initial_cash: float = 1_000_000,
    commission: float = 0.001,
    record_positions: bool = True,
    enforce_a_share_rules: bool = True,
    stamp_duty: float = 0.0005,
    transfer_fee: float = 0.00001,
    min_commission: float = 5.0,
    slippage: float = 0.0,
    limit_ratio_overrides: Optional[Dict[str, float]] = None,
) -> Dict:
    """
    回测引擎：根据信号计算策略表现。

    Args:
        data_map: code -> DataFrame (columns: open, high, low, close, volume)
        signals: code -> signal Series (value in [-1.0, 1.0])
        initial_cash: 初始资金
        commission: 单边佣金率（万2.5 传 0.00025）
        record_positions: 是否记录每日持仓快照
        enforce_a_share_rules: 是否执行 A 股交易规则
            （T+1、涨跌停、停牌顺延、整手、最低佣金、印花税、过户费）。
            False 时回到简化语义（仅单边佣金率，可负持仓不设限）。
        资金分配：开仓按「当日非零信号数」等分可用权益（|sig| 缩放强度），
            top-K 稀疏组合满仓；全部同向的密集信号与旧 len(codes) 语义一致。
        stamp_duty: 印花税率，仅卖出收取（2023-08-28 起为 0.0005）
        transfer_fee: 过户费率，双边收取（0.00001 = 万0.1）
        min_commission: 单笔最低佣金（元，A股常见为 5 元；0 表示不启用下限）
        slippage: 滑点比例（0.001 = 买入价上浮 0.1%、卖出价下浮 0.1%）
        limit_ratio_overrides: 个股涨跌停幅度覆盖（如 ST 股 {"XXX.XX": 0.05}）

    Returns:
        dict with metrics, equity curve, trade log, position snapshots, rebalance records
    """
    codes = [c for c in signals if c in data_map]
    if not codes:
        return {"error": "无有效标的"}

    # 合并日期索引
    all_dates = sorted(set().union(*(data_map[c].index for c in codes)))
    if not all_dates:
        return {"error": "无交易日期"}

    equity = [initial_cash]
    equity_dates = [all_dates[0]]
    trades = []
    rebalance_records = []  # 调仓记录
    position_snapshots = []  # 每日持仓快照
    positions = {c: 0.0 for c in codes}
    cost_basis = {c: 0.0 for c in codes}  # 持仓成本价
    prev_signals = {c: 0.0 for c in codes}
    total_commission = 0.0
    # A股规则状态：last_closes 用于涨跌停基准价；last_buy_date 用于 T+1 判定。
    # 主循环从第二个交易日开始，首日收盘需预载，否则第二日无涨跌停基准。
    last_closes: Dict[str, float] = {}
    last_buy_date: Dict[str, object] = {}
    limit_overrides: Dict[str, float] = limit_ratio_overrides or {}
    for c in codes:
        if not data_map[c].empty:
            first_close = data_map[c].iloc[0].get("close", np.nan)
            if pd.notna(first_close):
                last_closes[c] = float(first_close)

    def _trade_cost(notional: float, is_sell: bool) -> float:
        """按规则计算单笔交易成本；简化模式下仅单边佣金率。"""
        if not enforce_a_share_rules:
            return abs(notional * commission)
        if notional <= 0:
            return 0.0
        cost = notional * commission
        if min_commission > 0:
            cost = max(cost, min_commission)
        cost += notional * transfer_fee
        if is_sell:
            cost += notional * stamp_duty
        return cost

    for i, dt in enumerate(all_dates[1:], 1):
        daily_pnl = 0.0
        daily_rebalance_actions = []  # 当日调仓动作
        # 当日活跃信号数：开仓资金按活跃标的等分（修复 top-K 稀疏组合
        # 只用 |sig|/全宇宙 比例资金的问题——500 只池选 10 只旧公式只投
        # 2% 资金）。全部同向的密集信号下 active==len(codes)，与旧语义一致。
        active_count = 0
        for code in codes:
            sig_now = 0.0
            if code in signals and dt in signals[code].index:
                sig_now = float(signals[code].loc[dt])
            if sig_now != 0:
                active_count += 1

        for code in codes:
            if dt not in data_map[code].index:
                continue
            row = data_map[code].loc[dt]
            close = row.get("close", np.nan)
            if pd.isna(close):
                continue

            sig = 0.0
            if code in signals and dt in signals[code].index:
                sig = float(signals[code].loc[dt])

            # 限制信号范围
            sig = max(-1.0, min(1.0, sig))

            # 滑点执行价：买入上浮、卖出下浮（简化模式下即收盘价）
            buy_price = close * (1 + slippage) if enforce_a_share_rules else close
            sell_price = close * (1 - slippage) if enforce_a_share_rules else close

            # 检测信号变化 → 交易
            prev_sig = prev_signals.get(code, 0.0)
            if sig != prev_sig and i > 0:
                rebalance = {
                    "date": str(dt.date()),
                    "code": code,
                    "signal_before": round(prev_sig, 4),
                    "signal_after": round(sig, 4),
                }

                # ── A股可交易性检查：被阻的调仓整体顺延到下一交易日 ──
                blocked = None
                if enforce_a_share_rules:
                    vol = row.get("volume", np.nan)
                    if pd.notna(vol) and float(vol) <= 0:
                        blocked = "suspended_zero_volume"
                    else:
                        ref_close = last_closes.get(code)
                        if ref_close:
                            limit_up, limit_down = _limit_prices(ref_close, code, limit_overrides)
                            at_limit_up = close >= limit_up - 1e-6
                            at_limit_down = close <= limit_down + 1e-6
                            needs_buy = sig > 0 or positions[code] < 0  # 开多或平空
                            needs_sell = sig < 0 or positions[code] > 0  # 开空或平多
                            if needs_buy and at_limit_up:
                                blocked = "limit_up"
                            elif needs_sell and at_limit_down:
                                blocked = "limit_down"
                            elif positions[code] > 0 and last_buy_date.get(code) == dt:
                                blocked = "t_plus_1"

                if blocked is not None:
                    # 不成交、不更新 prev_signals：信号在下一交易日重试。
                    rebalance["blocked"] = blocked
                    rebalance_records.append(rebalance)
                else:
                    # 平旧仓位
                    if positions[code] != 0:
                        old_qty = positions[code]
                        old_cost = cost_basis[code]
                        px = sell_price if old_qty > 0 else buy_price
                        close_pnl = old_qty * (px - old_cost)
                        cost = _trade_cost(abs(old_qty) * px, is_sell=old_qty > 0)
                        daily_pnl += close_pnl - cost
                        total_commission += cost
                        trades.append({
                            "date": str(dt.date()),
                            "code": code,
                            "action": "close" if old_qty > 0 else "cover",
                            "price": round(px, 4),
                            "quantity": round(abs(old_qty), 4),
                            "cost_price": round(old_cost, 4),
                            "realized_pnl": round(close_pnl - cost, 2),
                        })
                        rebalance["action_close"] = {
                            "direction": "long" if old_qty > 0 else "short",
                            "quantity": round(abs(old_qty), 4),
                            "price": round(px, 4),
                            "realized_pnl": round(close_pnl - cost, 2),
                        }
                        if old_qty > 0:
                            last_buy_date.pop(code, None)

                    # 开新仓位
                    open_blocked = False
                    if sig != 0:
                        alloc = equity[-1] * abs(sig) / max(1, active_count)
                        px = buy_price if sig > 0 else sell_price
                        raw_qty = alloc / px
                        qty_abs = None
                        if enforce_a_share_rules:
                            lots = int(raw_qty // 100)
                            # 整手交易：不足一手不成交（开仓顺延到下一交易日重试）
                            qty_abs = lots * 100.0 if lots >= 1 else None
                        else:
                            qty_abs = raw_qty
                        if qty_abs is None:
                            open_blocked = True
                            rebalance["blocked"] = "insufficient_for_one_lot"
                        else:
                            qty = qty_abs if sig > 0 else -qty_abs
                            cost = _trade_cost(qty_abs * px, is_sell=sig < 0)
                            daily_pnl -= cost
                            total_commission += cost
                            positions[code] = qty
                            cost_basis[code] = px
                            if qty > 0:
                                last_buy_date[code] = dt
                            trades.append({
                                "date": str(dt.date()),
                                "code": code,
                                "action": "buy" if sig > 0 else "sell",
                                "price": round(px, 4),
                                "quantity": round(qty_abs, 4),
                                "cost_price": round(px, 4),
                                "realized_pnl": 0.0,
                            })
                            rebalance["action_open"] = {
                                "direction": "long" if sig > 0 else "short",
                                "quantity": round(qty_abs, 4),
                                "price": round(px, 4),
                                "signal_strength": round(abs(sig), 4),
                            }
                    else:
                        positions[code] = 0.0
                        cost_basis[code] = 0.0
                    if not open_blocked:
                        prev_signals[code] = sig
                    rebalance_records.append(rebalance)

            # 持仓盈亏（用该标的上一有效收盘：停牌缺口期间损益正确累计）
            if positions[code] != 0 and (i > 0):
                prev_close = last_closes.get(code)
                if prev_close is not None:
                    daily_pnl += positions[code] * (close - prev_close)

            if pd.notna(close):
                last_closes[code] = float(close)

        equity.append(equity[-1] + daily_pnl)
        equity_dates.append(dt)

        # 记录每日持仓快照
        if record_positions:
            snapshot = {"date": str(dt.date())}
            holding_total = 0.0
            for code in codes:
                if dt not in data_map[code].index:
                    continue
                price = data_map[code].loc[dt].get("close", 0)
                qty = positions[code]
                if qty == 0:
                    continue
                mv = qty * price
                holding_total += mv
                unrealized = qty * (price - cost_basis[code])
                snapshot[code] = {
                    "direction": "long" if qty > 0 else "short",
                    "quantity": round(abs(qty), 4),
                    "cost_price": round(cost_basis[code], 4),
                    "market_price": round(price, 4),
                    "market_value": round(mv, 2),
                    "unrealized_pnl": round(unrealized, 2),
                    "unrealized_pnl_pct": round(unrealized / (abs(qty) * cost_basis[code]) * 100, 2) if cost_basis[code] > 0 else 0,
                }
            cash = equity[-1] - holding_total
            snapshot["_summary"] = {
                "equity": round(equity[-1], 2),
                "cash": round(cash, 2),
                "holding_value": round(holding_total, 2),
                "position_utilization": round(holding_total / equity[-1] * 100, 2) if equity[-1] > 0 else 0,
                "holding_count": sum(1 for c in codes if positions[c] != 0),
            }
            position_snapshots.append(snapshot)

    # 计算指标
    equity_series = pd.Series(equity, index=equity_dates)
    metrics = _compute_metrics(equity_series, initial_cash, len(trades))
    metrics["total_commission"] = round(total_commission, 2)

    a_share_rules_summary = {
        "enabled": enforce_a_share_rules,
        "commission_rate": commission,
        "min_commission": min_commission if enforce_a_share_rules else None,
        "stamp_duty_sell": stamp_duty if enforce_a_share_rules else None,
        "transfer_fee": transfer_fee if enforce_a_share_rules else None,
        "slippage": slippage if enforce_a_share_rules else None,
        "lot_size": 100 if enforce_a_share_rules else None,
        "t_plus_1": enforce_a_share_rules,
        "blocked_rebalances": sum(1 for r in rebalance_records if r.get("blocked")),
    }

    return {
        "metrics": metrics,
        "a_share_rules": a_share_rules_summary,
        "equity_dates": [str(d.date()) if hasattr(d, "date") else str(d) for d in equity_dates],
        "equity_values": [round(v, 2) for v in equity],
        "trade_count": len(trades),
        "trades": trades,
        "rebalance_records": rebalance_records,
        "rebalance_count": len(rebalance_records),
        "position_snapshots": position_snapshots,
    }


def _compute_metrics(equity: pd.Series, initial_cash: float, trade_count: int) -> Dict:
    """计算回测指标"""
    total_return = (equity.iloc[-1] / initial_cash - 1) * 100

    # 日收益率
    returns = equity.pct_change().dropna()
    if len(returns) == 0:
        return {"total_return_pct": 0, "annual_return_pct": 0, "sharpe": 0,
                "max_drawdown_pct": 0, "win_rate": 0, "trade_count": trade_count}

    # 年化
    n_days = len(returns)
    annual_factor = 252
    annual_return = (1 + total_return / 100) ** (annual_factor / max(n_days, 1)) - 1

    # 夏普
    sharpe = returns.mean() / returns.std() * np.sqrt(annual_factor) if returns.std() > 0 else 0

    # 最大回撤
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_dd = drawdown.min() * 100

    # 胜率（按日）
    win_days = (returns > 0).sum()
    win_rate = win_days / len(returns) * 100

    return {
        "total_return_pct": round(total_return, 2),
        "annual_return_pct": round(annual_return * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "trade_count": trade_count,
        "n_days": n_days,
    }


def evaluate_strategy(metrics: Dict) -> Dict:
    """根据评审标准评估策略"""
    score = 60  # 基础分
    issues = []
    action_items = []

    if metrics.get("trade_count", 0) == 0:
        score -= 30
        issues.append("零交易：信号逻辑可能有 bug，条件可能太严格")
        action_items.append("放宽信号条件，降低阈值或缩短计算窗口")

    if metrics.get("total_return_pct", 0) < -20:
        score -= 10
        issues.append(f"严重亏损: {metrics['total_return_pct']}%")

    if metrics.get("max_drawdown_pct", 0) < -30:
        score -= 5
        issues.append(f"最大回撤较大: {metrics['max_drawdown_pct']}%")
        action_items.append("添加止损逻辑：当亏损超过 5% 时强制平仓")

    if metrics.get("sharpe_ratio", 0) < 0.5:
        issues.append(f"夏普比率偏低: {metrics['sharpe_ratio']}")
        action_items.append("添加趋势过滤：仅在均线多头排列时做多")

    passed = score >= 60
    return {
        "passed": passed,
        "score": score,
        "issues": issues,
        "action_items": action_items,
    }
