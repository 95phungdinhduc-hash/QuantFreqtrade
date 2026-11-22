# pragma pylint: disable=missing-docstring, invalid-name, unused-argument
"""
QuantSmartDCAStrategy — "Tích luỹ thông minh" (Spot, chỉ Long), phong cách ĐẦU TƯ hơn là lướt sóng.

Ý tưởng: thay vì dồn hết tiền vào 1 lần, chia vốn thành 3 phần và chỉ mua khi thị trường hoảng loạn:
  1. Vào lần 1 (1 phần): Z-Score vừa xuống dưới -2 VÀ RSI < 30 (quá bán sâu) VÀ nến xanh xác nhận
     lực mua quay lại; giá không rơi quá xa EMA50 khung 4h (tránh coin đang sụp đổ hoàn toàn).
  2. Mua thêm lần 2 (1 phần) nếu giá giảm thêm 4% so với giá vốn trung bình.
  3. Mua thêm lần 3 (1,5 phần) nếu giảm thêm 8% so với giá vốn trung bình.
  4. Bán toàn bộ khi lời 4% trên giá vốn trung bình, hoặc khi Z-Score hồi lên +1 mà đang có lời.
  5. Cắt lỗ cứng -12% trên giá vốn trung bình.
  6. TỔNG số tiền tối đa cho 1 coin được tính sao cho nếu chạm cắt lỗ thì chỉ mất đúng risk_pct% vốn.

Rủi ro: DCA mua thêm khi giá giảm — trong thị trường giảm kéo dài có thể chạm cắt lỗ với khối lượng lớn.
Chạy backtest:  ./run.sh backtest-all
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import quant_core

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy, informative

from quant_core.indicators import add_quant_indicators, ema, rsi
from quant_core.strategy_common import (QuantRiskMixin, add_market_regime, market_informative_pairs,
                                          market_long_ok)

# Tỷ lệ mỗi lần mua: lần 1 = 1 phần, lần 2 = 1 phần, lần 3 = 1,5 phần
DCA_UNITS = (1.0, 1.0, 1.5)


class QuantSmartDCAStrategy(QuantRiskMixin, IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    minimal_roi = {"0": 100}           # chốt lời trong custom_exit
    stoploss = -0.12                   # trên giá vốn trung bình
    process_only_new_candles = True
    startup_candle_count = 250

    position_adjustment_enable = True
    max_entry_position_adjustment = len(DCA_UNITS) - 1

    z_entry = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")
    rsi_entry = IntParameter(20, 40, default=30, space="buy")
    max_below_4h = DecimalParameter(0.05, 0.25, default=0.12, decimals=2, space="buy")
    add_drop_1 = DecimalParameter(0.02, 0.08, default=0.04, decimals=2, space="buy")
    add_drop_2 = DecimalParameter(0.05, 0.12, default=0.08, decimals=2, space="buy")
    take_profit = DecimalParameter(0.02, 0.08, default=0.04, decimals=2, space="sell")
    z_exit = DecimalParameter(0.0, 2.0, default=1.0, decimals=1, space="sell")

    plot_config = {
        "main_plot": {"rolling_mean": {"color": "orange"}, "ema_slow_4h": {"color": "#d95926"}},
        "subplots": {"Z-Score": {"z_score": {"color": "#9085e9"}}, "RSI": {"rsi": {"color": "#3987e5"}}},
    }

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_slow"] = ema(dataframe["close"], 50)
        return dataframe

    def informative_pairs(self):
        return market_informative_pairs(self.config)  # BTC khung ngày cho bộ lọc thị trường

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = add_quant_indicators(dataframe, with_adf=False)
        df["rsi"] = rsi(df["close"])
        return add_market_regime(self.dp, df, self.config, self.timeframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe
        cond = (
            (df["z_score"].shift(1) < -self.z_entry.value)
            & (df["rsi"].shift(1) < self.rsi_entry.value)
            & (df["z_score"] > df["z_score"].shift(1))       # bắt đầu quay đầu
            & (df["close"] > df["open"])                     # nến xanh xác nhận
            & (df["close"] > df["ema_slow_4h"] * (1 - self.max_below_4h.value))
            & (df["volume"] > 0)
        )
        cond &= market_long_ok(df, self.config)  # BTC dưới SMA200 ngày -> đứng ngoài
        df.loc[cond, ["enter_long", "enter_tag"]] = (1, "dca")
        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ------------------------------------------------------------------ vốn
    def _budget(self, proposed_stake: float, max_stake: float) -> float:
        """Tổng tiền tối đa cho 1 coin: chạm cắt lỗ -12% thì mất đúng risk_pct% vốn."""
        capital = self.wallets.get_total_stake_amount() if self.wallets else proposed_stake
        return min(capital * self._risk_pct() / 100 / abs(self.stoploss), max_stake * len(DCA_UNITS))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        stake = self._budget(proposed_stake, max_stake) * DCA_UNITS[0] / sum(DCA_UNITS)
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def adjust_trade_position(self, trade: Trade, current_time: datetime, current_rate: float,
                              current_profit: float, min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> float | tuple[float | None, str | None] | None:
        if trade.has_open_orders:
            return None
        n = trade.nr_of_successful_entries
        if n >= len(DCA_UNITS):
            return None
        need = -self.add_drop_1.value if n == 1 else -self.add_drop_2.value
        if current_profit > need:
            return None
        first = trade.select_filled_orders(trade.entry_side)[0].stake_amount_filled
        stake = first * DCA_UNITS[n] / DCA_UNITS[0]
        if min_stake and stake < min_stake:
            return None
        return min(stake, max_stake), f"dca_add_{n}"

    # ------------------------------------------------------------------ thoát
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str | None:
        if current_profit >= self.take_profit.value:
            return "dca_take_profit"
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is not None and not df.empty and current_profit > 0.005 \
                and df.iloc[-1]["z_score"] >= self.z_exit.value:
            return "z_revert"
        return None
