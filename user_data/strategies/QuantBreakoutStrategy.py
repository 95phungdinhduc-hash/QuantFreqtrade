# pragma pylint: disable=missing-docstring, invalid-name, unused-argument
"""
QuantBreakoutStrategy — "Mua theo đà" khi giá PHÁ ĐỈNH trong thị trường có xu hướng (Spot, chỉ Long).

Ý tưởng (bổ sung cho QuantHybridStrategy — Hybrid mạnh ở thị trường đi ngang, Breakout ở thị trường
có xu hướng mạnh):
  1. Chế độ thị trường: ADF >= ngưỡng (có xu hướng), giá trên EMA50 khung 4h và EMA50 4h đang dốc lên.
  2. Vào lệnh: giá đóng cửa vượt đỉnh cao nhất 48 giờ trước đó (kênh Donchian) + khối lượng lớn hơn
     trung bình (xác nhận lực mua thật) + Z-Score chưa quá cao (không đu đỉnh quá xa trung bình).
  3. Cắt lỗ ban đầu 2.5 × ATR, sau đó KÉO THEO (trailing) cách đỉnh cao nhất 3 × ATR — để lời chạy.
  4. Thoát khi giá thủng đáy 24 giờ (kênh Donchian dưới) — xu hướng ngắn hạn đã gãy.
  5. Khối lượng theo % rủi ro (giống Hybrid), bộ lọc tin tức, bộ bảo vệ tài khoản.

Chạy backtest:  ./run.sh backtest-all   (so sánh với các chiến lược khác)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import quant_core

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IStrategy, informative, stoploss_from_absolute

from quant_core.indicators import add_quant_indicators, donchian, ema
from quant_core.strategy_common import QuantRiskMixin


class QuantBreakoutStrategy(QuantRiskMixin, IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    minimal_roi = {"0": 100}      # không chốt lời cố định — để trailing stop & kênh Donchian quyết định
    stoploss = -0.10              # trần an toàn; custom_stoploss luôn chặt hơn
    use_custom_stoploss = True
    process_only_new_candles = True
    startup_candle_count = 250

    # Chu kỳ kênh (cố định — nằm trong populate_indicators)
    dc_entry_period = 48
    dc_exit_period = 24

    # Tham số hyperopt được
    adf_threshold = DecimalParameter(0.05, 0.40, default=0.20, decimals=2, space="buy")
    vol_mult = DecimalParameter(1.0, 2.5, default=1.2, decimals=1, space="buy")
    max_z = DecimalParameter(1.5, 4.0, default=3.0, decimals=1, space="buy")
    atr_init = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="protection")
    atr_trail = DecimalParameter(2.0, 5.0, default=3.0, decimals=1, space="protection")

    plot_config = {
        "main_plot": {"dc_high": {"color": "#1fbf75"}, "dc_low_exit": {"color": "#ef5d5d"},
                      "ema_slow_4h": {"color": "#d95926"}},
        "subplots": {"Khối lượng / TB": {"vol_ratio": {"color": "#3987e5"}},
                     "ADF p": {"adf_p": {"color": "gray"}}},
    }

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_slow"] = ema(dataframe["close"], 50)
        dataframe["ema_rising"] = (dataframe["ema_slow"] > dataframe["ema_slow"].shift(6)).astype(int)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = add_quant_indicators(dataframe)
        df["dc_high"], _ = donchian(df, self.dc_entry_period)
        _, df["dc_low_exit"] = donchian(df, self.dc_exit_period)
        df["vol_ratio"] = df["volume"] / df["volume"].rolling(48).mean().shift(1)
        return df

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe
        cond = (
            (df["adf_p"] >= self.adf_threshold.value)          # thị trường có xu hướng
            & (df["close"] > df["dc_high"])                    # phá đỉnh 48 giờ
            & (df["close"].shift(1) <= df["dc_high"].shift(1))  # vừa mới phá (không mua đuổi)
            & (df["close"] > df["ema_slow_4h"])                # khung 4h đồng thuận
            & (df["ema_rising_4h"] == 1)
            & (df["vol_ratio"] > self.vol_mult.value)          # khối lượng xác nhận
            & (df["z_score"] < self.max_z.value)               # chưa quá xa trung bình
            & (df["volume"] > 0)
        )
        df.loc[cond, ["enter_long", "enter_tag"]] = (1, "breakout")
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe  # thoát trong custom_exit / custom_stoploss

    # ------------------------------------------------------------------ helpers
    def _candle(self, pair: str, before=None):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        if before is not None:
            sub = df.loc[df["date"] < before]
            return sub.iloc[-1] if not sub.empty else df.iloc[-1]
        return df.iloc[-1]

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        c = self._candle(pair)
        if c is None or not c["atr"] > 0:
            return proposed_stake
        stop_dist = min(self.atr_init.value * c["atr"] / current_rate, abs(self.stoploss))
        return self._risk_stake(stop_dist, proposed_stake, min_stake, max_stake, leverage)

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        atr = trade.get_custom_data("entry_atr")
        if atr is None:
            c = self._candle(pair, before=trade.open_date_utc)
            if c is None or not c["atr"] > 0:
                return None
            atr = float(c["atr"])
            trade.set_custom_data("entry_atr", atr)
        initial = trade.open_rate - self.atr_init.value * atr
        trailing = (trade.max_rate or trade.open_rate) - self.atr_trail.value * atr
        return stoploss_from_absolute(max(initial, trailing), current_rate, is_short=False,
                                      leverage=trade.leverage)

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str | None:
        c = self._candle(pair)
        if c is not None and c["close"] < c["dc_low_exit"]:
            return "channel_exit"
        return None
