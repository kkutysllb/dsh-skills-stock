"""
多腿组合盈亏计算引擎

提供：
- 多腿期权组合的到期盈亏曲线计算
- Black-Scholes 理论价值曲线
- 盈亏平衡点数值求解
- 最大盈亏计算
- 波动率情景分析
"""

import numpy as np
from dataclasses import dataclass
from typing import Literal, Optional

try:
    # 包内导入（推荐）
    from .bs_model import bs_price
except ImportError:
    # 脚本直接执行（sys.path 含本目录）兼容
    from bs_model import bs_price

try:
    from scipy.optimize import brentq
except ImportError:
    brentq = None


@dataclass
class OptionLeg:
    """单腿期权定义。

    Attributes:
        option_type: "call" 或 "put"
        K: 行权价
        direction: +1 (Long) / -1 (Short)
        quantity: 合约数量，默认 1
        premium: 单腿权利金成本（始终 >= 0，表示每腿付出的绝对金额）。
                 买入时为现金流出，卖出时为现金流入，方向由 direction 决定，
                 此处只记录绝对值，避免与 direction 产生符号歧义。
        T: 到期时间（年）
        sigma: 定价波动率
    """
    option_type: Literal["call", "put"]
    K: float
    direction: Literal[1, -1] = 1
    quantity: float = 1.0
    premium: float = 0.0
    T: float = 0.25
    sigma: float = 0.20

    def __post_init__(self) -> None:
        """参数校验，避免静默错误。"""
        if self.direction not in (1, -1):
            raise ValueError(
                f"direction must be +1 (Long) or -1 (Short), got {self.direction}"
            )
        if self.quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {self.quantity}")
        if self.premium < 0:
            raise ValueError(
                f"premium must be the absolute cost (>= 0), got {self.premium}"
            )
        if self.T < 0:
            raise ValueError(f"T must be >= 0, got {self.T}")
        if self.sigma <= 0:
            raise ValueError(f"sigma must be > 0, got {self.sigma}")


def compute_expiry_payoff(
    legs: list,
    S_range: np.ndarray,
) -> np.ndarray:
    """计算到期盈亏曲线。

    Args:
        legs: 期权腿列表
        S_range: 标的价格数组

    买入腿付出权利金（现金流出），卖出腿收取权利金（现金流入）。
    premium 约定为绝对值（>=0），方向由 direction 决定：
        direction * quantity * premium 的语义：
            long  (+1): +|premium| 表示付出金额
            short (-1): -|premium| 表示收取金额（取负后表示反向现金流）
        故 net_premium = Σ(direction * quantity * premium) 为「净付出」金额。
    到期实际盈亏 = 内在价值合计 - 净付出。
    """
    total_payoff = np.zeros(len(S_range))
    net_premium = sum(leg.direction * leg.quantity * leg.premium for leg in legs)

    for leg in legs:
        if leg.option_type == "call":
            intrinsic = np.maximum(S_range - leg.K, 0)
        else:
            intrinsic = np.maximum(leg.K - S_range, 0)
        total_payoff += leg.direction * leg.quantity * intrinsic

    return total_payoff - net_premium


def compute_theo_value(
    legs: list,
    S_range: np.ndarray,
    r: float = 0.03,
    q: float = 0.0,
) -> np.ndarray:
    """计算当前 BS 理论价值曲线。

    Args:
        legs: 期权腿列表（每腿携带 T 和 sigma）
        S_range: 标的价格数组
        r: 无风险利率
        q: 连续股息率

    Returns:
        理论盈亏数组
    """
    total_value = np.zeros(len(S_range))
    net_premium = sum(leg.direction * leg.quantity * leg.premium for leg in legs)

    for leg in legs:
        prices = np.array([
            bs_price(S, leg.K, leg.T, r, leg.sigma, leg.option_type, q)
            for S in S_range
        ])
        total_value += leg.direction * leg.quantity * prices

    return total_value - net_premium


def find_breakeven_points(
    S_range: np.ndarray,
    payoff: np.ndarray,
) -> list:
    """数值求解盈亏平衡点。

    既捕获严格变号区间，也显式处理 payoff == 0 的采样点。

    Returns:
        盈亏平衡点列表（去重、升序）
    """
    beps: set = set()

    # 显式判零：任意采样点 payoff 恰为 0 即为平衡点
    exact_zeros = S_range[payoff == 0]
    for s in exact_zeros:
        beps.add(round(float(s), 2))

    # 逐区间查找变号
    for i in range(len(S_range) - 1):
        p0, p1 = payoff[i], payoff[i + 1]
        # 严格变号才进入求解（一端为 0 已被上面捕获）
        if p0 * p1 >= 0:
            continue

        if brentq is None:
            # scipy 不可用时用线性插值近似
            ratio = abs(p0) / (abs(p0) + abs(p1))
            beps.append(round(float(S_range[i] + ratio * (S_range[i + 1] - S_range[i])), 2))
        else:
            try:
                # brentq 的函数句柄改为局部线性插值，避免每次在全数组上做 np.interp
                s_lo, s_hi = float(S_range[i]), float(S_range[i + 1])
                denom = s_hi - s_lo
                if denom <= 0:
                    continue

                def _local_lin(s: float, a=p0, b=p1, lo=s_lo, d=denom) -> float:
                    t = (s - lo) / d
                    return a + (b - a) * t

                bep = brentq(_local_lin, s_lo, s_hi, xtol=0.01)
                beps.add(round(float(bep), 2))
            except ValueError:
                continue

    return sorted(beps)


def _extract_intervals(
    S_range: np.ndarray,
    mask: np.ndarray,
) -> list:
    """从布尔掩码中提取连续区间列表。

    Args:
        S_range: 标的价格数组（单调递增）
        mask: 布尔掩码，标记满足条件的采样点

    Returns:
        [(lo, hi), ...] 区间列表；空掩码返回空列表。
        区间端点已 round 到 2 位小数。
    """
    if not np.any(mask):
        return []

    # 找到掩码变化的边界
    padded = np.concatenate([[False], mask, [False]])
    diffs = np.diff(padded.astype(int))
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    intervals = []
    for s, e in zip(starts, ends):
        # 区间取该连续段的首末采样点
        lo = float(S_range[s])
        hi = float(S_range[e - 1])
        intervals.append((round(lo, 2), round(hi, 2)))
    return intervals


def _format_extreme(value: float, is_unlimited: bool, is_profit: bool) -> object:
    """格式化最大盈利/亏损，避免类型不一致。"""
    if is_unlimited:
        return "Unlimited"
    return round(value, 2)


def compute_max_profit_loss(
    payoff: np.ndarray,
    S_range: np.ndarray,
    legs: Optional[list] = None,
    rtol: float = 1e-9,
) -> dict:
    """计算最大盈利和最大亏损。

    通过解析腿的方向判断盈亏是否「无限」，避免依赖采样阈值。
    采样范围内的 max/min 仍作为「有限情形下的数值上限」返回。

    Args:
        payoff: 盈亏数组
        S_range: 对应标的价格数组
        legs: 期权腿列表，用于解析方向判断是否无限盈利/亏损；
              若为 None 则退化为基于采样范围的数值判断。
        rtol: 端点是否单调的相对容差，用于辅助无限性判定

    Returns:
        {
            "max_profit": float | "Unlimited",
            "max_loss": float | "Unlimited",
            "profit_range": [(lo, hi), ...] | None,   # 不连续区间列表
            "loss_range": [(lo, hi), ...] | None,
        }
    """
    max_p = float(np.max(payoff))
    min_p = float(np.min(payoff))

    # 不连续区间提取
    profit_intervals = _extract_intervals(S_range, payoff > 0)
    loss_intervals = _extract_intervals(S_range, payoff < 0)

    # 基于腿方向解析「无限」属性
    # 用净头寸（按方向加权的数量）判断，避免组合被误判为无限
    # 净 long call 头寸 > 0 → S→∞ 时盈利无限
    # 净 short call 头寸 > 0 → S→∞ 时亏损无限
    # 净 short put 头寸 > 0 → S→0 时亏损无限（但通常有 K 兜底，视为有限）
    net_call_long = net_put_long = 0.0
    net_call_short = net_put_short = 0.0
    if legs is not None:
        for leg in legs:
            signed_qty = leg.direction * leg.quantity
            if leg.option_type == "call":
                if signed_qty > 0:
                    net_call_long += signed_qty
                else:
                    net_call_short += -signed_qty
            else:  # put
                if signed_qty > 0:
                    net_put_long += signed_qty
                else:
                    net_put_short += -signed_qty

    net_call = net_call_long - net_call_short  # 净 call 头寸（正=净多）
    # 盈利无限：净 call 多头存在（S→∞ 时线性增长）
    profit_unlimited = net_call > 0
    # 亏损无限：净 call 空头存在（S→∞ 时线性亏损）
    loss_unlimited = net_call < 0

    # 若未提供 legs，退化为基于端点单调性的判定
    if legs is None:
        # 右端点 payoff >= 左端点 payoff 视为可能无限盈利
        profit_unlimited = payoff[-1] >= payoff[0] and payoff[-1] >= max_p - abs(max_p) * rtol
        loss_unlimited = payoff[-1] <= payoff[0] and payoff[0] <= min_p + abs(min_p) * rtol

    return {
        "max_profit": _format_extreme(max_p, profit_unlimited, is_profit=True),
        "max_loss": _format_extreme(min_p, loss_unlimited, is_profit=False),
        "profit_range": profit_intervals if profit_intervals else None,
        "loss_range": loss_intervals if loss_intervals else None,
    }


def volatility_scenario_analysis(
    legs: list,
    S_range: np.ndarray,
    r: float = 0.03,
    q: float = 0.0,
    sigma_multipliers: Optional[list] = None,
    S_current: Optional[float] = None,
    n_points: int = 500,
) -> dict:
    """波动率情景分析。

    Args:
        sigma_multipliers: 波动率乘数列表，默认 [0.5, 0.75, 1.0, 1.25, 1.5]
        S_current: 当前标的价格；用于评估「当前价位理论盈亏」。
                   若为 None，则退化为采样中点（不推荐）。
        n_points: S_range 的采样点数，用于 theo_curve 采样步长对齐

    Returns:
        各情景的理论价值曲线。每个情景的 key 使用「乘数」而非具体 σ，
        避免多腿组合下用单腿 σ 做标签导致歧义。
    """
    if sigma_multipliers is None:
        sigma_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5]

    # 使用哪个价格作为「当前价」基准
    S_ref = S_current if S_current is not None else float(S_range[len(S_range) // 2])

    # theo_curve 采样步长与 analyze_payoff 保持一致
    step = max(1, n_points // 100)

    scenarios = {}
    for mult in sigma_multipliers:
        scenario_legs = []
        for leg in legs:
            scenario_legs.append(OptionLeg(
                option_type=leg.option_type,
                K=leg.K,
                direction=leg.direction,
                quantity=leg.quantity,
                premium=leg.premium,
                T=leg.T,
                sigma=leg.sigma * mult,
            ))
        theo = compute_theo_value(scenario_legs, S_range, r, q)

        # key 使用乘数（跨腿统一基准），value 内仍提供各腿的 σ 信息
        leg_sigmas = [round(leg.sigma * mult, 4) for leg in legs]
        scenarios[f"x{mult}"] = {
            "multiplier": mult,
            "leg_sigmas": leg_sigmas,
            "pnl_at_current": round(float(np.interp(S_ref, S_range, theo)), 2),
            "theo_curve": [round(float(v), 2) for v in theo[::step]],
        }

    return scenarios


def analyze_payoff(
    legs: list,
    S_current: float,
    r: float = 0.03,
    q: float = 0.0,
    n_points: int = 500,
) -> dict:
    """完整的盈亏分析入口。

    Returns:
        包含所有分析结果的字典
    """
    K_values = [leg.K for leg in legs]
    K_min, K_max = min(K_values), max(K_values)

    # 扩展端点，保证 S_current 落入区间，并避免单 K 时区间过窄/过宽
    lo_candidates = [K_min * 0.70]
    hi_candidates = [K_max * 1.30]
    if S_current is not None:
        lo_candidates.append(S_current * 0.70)
        hi_candidates.append(S_current * 1.30)
    S_lo = min(lo_candidates)
    S_hi = max(hi_candidates)
    if S_hi <= S_lo:
        S_hi = S_lo * 1.01
    S_range = np.linspace(S_lo, S_hi, n_points)

    # 到期盈亏
    expiry_pnl = compute_expiry_payoff(legs, S_range)

    # 理论价值
    theo_pnl = compute_theo_value(legs, S_range, r, q)

    # 盈亏平衡点
    beps = find_breakeven_points(S_range, expiry_pnl)

    # 最大盈亏（传入 legs 以解析方向性 Unlimited 判定）
    max_pl = compute_max_profit_loss(expiry_pnl, S_range, legs=legs)

    # 当前标的理论盈亏
    current_theo_pnl = float(np.interp(S_current, S_range, theo_pnl))
    current_expiry_pnl = float(np.interp(S_current, S_range, expiry_pnl))

    # 波动率情景（透传 S_current 和 n_points）
    vol_scenarios = volatility_scenario_analysis(
        legs, S_range, r, q,
        S_current=S_current,
        n_points=n_points,
    )

    # 采样曲线用于输出（避免数据量过大）
    step = max(1, n_points // 100)
    sampled_S = [round(float(s), 2) for s in S_range[::step]]
    sampled_expiry = [round(float(v), 2) for v in expiry_pnl[::step]]
    sampled_theo = [round(float(v), 2) for v in theo_pnl[::step]]

    return {
        "legs": [
            {
                "type": leg.option_type,
                "direction": "long" if leg.direction == 1 else "short",
                "strike": leg.K,
                "quantity": leg.quantity,
                "premium": leg.premium,
                "T": leg.T,
                "sigma": leg.sigma,
            }
            for leg in legs
        ],
        "params": {
            "S_current": S_current,
            "r": r,
            "q": q,
            "S_range": [round(S_lo, 2), round(S_hi, 2)],
        },
        "expiry_payoff_sampled": {
            "S": sampled_S,
            "pnl": sampled_expiry,
        },
        "theo_value_sampled": {
            "S": sampled_S,
            "pnl": sampled_theo,
        },
        "breakeven_points": beps,
        "max_profit": max_pl["max_profit"],
        "max_loss": max_pl["max_loss"],
        "profit_range": max_pl["profit_range"],
        "loss_range": max_pl["loss_range"],
        "current_theo_pnl": round(current_theo_pnl, 2),
        "current_expiry_pnl": round(current_expiry_pnl, 2),
        "volatility_scenarios": vol_scenarios,
    }
