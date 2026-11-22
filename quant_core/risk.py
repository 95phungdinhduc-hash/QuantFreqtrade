"""
Quản lý vốn & rủi ro — port từ tab 3 của 2_dashboard.py và phần sizing của 4_alert_bot.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PositionPlan:
    entry: float
    stop_loss: float
    take_profit: float
    risk_usd: float          # số tiền chấp nhận mất nếu chạm SL
    position_usd: float      # quy mô lệnh (notional)
    coin_amount: float
    stop_distance_pct: float  # khoảng cách tới SL (0.02 = 2%)
    rr_ratio: float           # tỷ lệ lợi nhuận / rủi ro
    leverage_needed: float    # đòn bẩy cần nếu position > vốn


def plan_position(
    capital: float,
    risk_pct: float,
    entry: float,
    std: float,
    mean: float | None = None,
    is_long: bool = True,
    sl_std_mult: float = 1.0,
    tp_std_mult: float = 1.5,
    min_notional: float = 0.0,
) -> PositionPlan:
    """
    Tính kế hoạch vào lệnh theo quy tắc "rủi ro cố định % vốn".

    risk_pct: % vốn chấp nhận mất (1.5 = 1.5%).
    SL = entry -/+ sl_std_mult * std ; TP = max/min(mean, entry +/- tp_std_mult * std)
    """
    if is_long:
        sl = entry - sl_std_mult * std
        tp = entry + tp_std_mult * std
        if mean is not None:
            tp = max(mean, tp)
    else:
        sl = entry + sl_std_mult * std
        tp = entry - tp_std_mult * std
        if mean is not None:
            tp = min(mean, tp)

    risk_usd = capital * risk_pct / 100
    stop_dist = abs(entry - sl) / entry if entry > 0 else 0.0
    position = risk_usd / stop_dist if stop_dist > 0 else 0.0
    position = max(position, min_notional)
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0.0
    return PositionPlan(
        entry=entry,
        stop_loss=sl,
        take_profit=tp,
        risk_usd=position * stop_dist,
        position_usd=position,
        coin_amount=position / entry if entry > 0 else 0.0,
        stop_distance_pct=stop_dist,
        rr_ratio=rr,
        leverage_needed=max(1.0, round(position / capital, 1)) if capital > 0 else 1.0,
    )


def value_at_risk(returns: pd.Series, level: float = 0.95) -> tuple[float, float]:
    """Trả về (VaR, CVaR) lịch sử. Giá trị âm, ví dụ -0.012 = -1.2% mỗi nến."""
    r = pd.Series(returns).dropna()
    if r.empty:
        return float("nan"), float("nan")
    var = float(np.percentile(r, (1 - level) * 100))
    tail = r[r <= var]
    return var, float(tail.mean()) if not tail.empty else var


def half_kelly(trade_returns: pd.Series) -> float:
    """
    Half-Kelly (% vốn nên dùng cho 1 lệnh) tính trên LỢI NHUẬN TỪNG LỆNH.

    Nâng cấp so với bản gốc: bản gốc tính Kelly trên lợi nhuận từng nến của giá,
    không phản ánh chiến lược. Ở đây truyền vào profit_ratio từ backtest Freqtrade
    để có con số có ý nghĩa.
    """
    r = pd.Series(trade_returns).dropna()
    wins, losses = r[r > 0], r[r < 0]
    if r.empty or wins.empty or losses.empty:
        return 0.0
    p = len(wins) / len(r)
    b = wins.mean() / abs(losses.mean())
    kelly = p - (1 - p) / b
    return max(0.0, kelly / 2 * 100)
