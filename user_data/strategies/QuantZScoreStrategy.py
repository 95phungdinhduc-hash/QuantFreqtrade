# pragma pylint: disable=missing-docstring, invalid-name
"""
QuantZScoreStrategy — Bản port 1:1 chiến lược trong QuantTradingSystem/3_backtest_engine.py
sang Freqtrade, dùng làm "chiến lược gốc" (baseline) để so sánh.

  * Mua khi Z-Score < z_entry (mặc định -2.0)
  * Bán khi Z-Score >= z_exit (mặc định 0.0)
  * Chu kỳ 50 nến, khung 1h, chỉ Long (Spot)

Khác biệt duy nhất so với bản gốc: có thêm cắt lỗ cứng -15% để bảo vệ tài khoản
(bản gốc không có cắt lỗ). Chạy:
    freqtrade backtesting -c user_data/config.json -s QuantZScoreStrategy
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import quant_core

from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IStrategy

from quant_core.indicators import zscore


class QuantZScoreStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}  # tắt ROI — chỉ thoát theo tín hiệu Z-Score như bản gốc
    stoploss = -0.15
    trailing_stop = False

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 60

    window = 50
    z_entry = DecimalParameter(-3.0, -1.0, default=-2.0, decimals=1, space="buy")
    z_exit = DecimalParameter(-1.0, 1.0, default=0.0, decimals=1, space="sell")

    plot_config = {
        "main_plot": {"rolling_mean": {"color": "orange"}},
        "subplots": {"Z-Score": {"z_score": {"color": "#B266FF"}}},
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rolling_mean"] = dataframe["close"].rolling(self.window).mean()
        dataframe["z_score"] = zscore(dataframe["close"], self.window)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["z_score"] < self.z_entry.value) & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "zscore")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["z_score"] >= self.z_exit.value, ["exit_long", "exit_tag"]] = (
            1,
            "z_revert",
        )
        return dataframe
