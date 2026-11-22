"""
quant_core — Thư viện định lượng dùng chung, tách ra từ QuantTradingSystem.

Được dùng bởi:
  * user_data/strategies/*.py  (chiến lược Freqtrade)
  * dashboard/app.py           (Streamlit dashboard)
  * alert_bot/alert_bot.py     (Bot cảnh báo Telegram + AI)

Mọi hàm ở đây là hàm "thuần" (không gọi mạng, không ghi file) trừ
sentiment.py và ai_advisor.py, nên an toàn khi Freqtrade gọi trong backtest.
"""

from quant_core.indicators import (
    add_quant_indicators,
    adf_pvalue,
    ema,
    rolling_adf_pvalue,
    zscore,
)
from quant_core.risk import (
    PositionPlan,
    half_kelly,
    plan_position,
    value_at_risk,
)

__all__ = [
    "add_quant_indicators",
    "adf_pvalue",
    "ema",
    "rolling_adf_pvalue",
    "zscore",
    "PositionPlan",
    "half_kelly",
    "plan_position",
    "value_at_risk",
]
