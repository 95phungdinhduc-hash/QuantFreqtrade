# pragma pylint: disable=missing-docstring, invalid-name, unused-argument
"""
QuantHybridStrategy — Chiến lược NÂNG CẤP kết hợp toàn bộ logic của QuantTradingSystem:

  1. Nhận diện chế độ thị trường bằng ADF p-value trượt (từ dashboard tab 1/2)
       - ADF < adf_threshold  => thị trường đi ngang  => đánh MEAN REVERSION theo Z-Score
       - ngược lại            => thị trường có xu hướng => đánh TREND FOLLOWING theo EMA20/50
  2. Lọc xu hướng khung lớn 4h (EMA50 4h) cho lệnh Trend.
  3. Cắt lỗ động theo độ lệch chuẩn tại lúc vào lệnh (giống 4_alert_bot.py: 1.2σ / 1.5σ),
     tự dời về hoà vốn khi giá chạy được 1σ.
  4. Khối lượng lệnh theo "rủi ro cố định % vốn" (tab 3 Quản lý vốn) thay vì chia đều.
  5. Chốt lời Mean Reversion khi Z-Score hồi về z_exit, Trend khi EMA cắt xuống.
  6. Bảo vệ tài khoản (Protections): nghỉ sau lệnh, dừng khi thua liên tiếp / sụt vốn sâu.
  7. (Chỉ dry-run/live) Chặn lệnh mới khi tin tức RSS quá tiêu cực.

Phiên bản Futures (có Short + đòn bẩy): QuantHybridFuturesStrategy ở cuối file.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # để import quant_core

import logging

from pandas import DataFrame, Series

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    informative,
    stoploss_from_absolute,
)

from quant_core.indicators import add_quant_indicators, ema
from quant_core.strategy_common import (add_market_regime, market_informative_pairs, market_long_ok,
                                          market_short_ok)

logger = logging.getLogger(__name__)


class QuantHybridStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # ROI chỉ là "lưới an toàn" chốt lời khi giá bay quá xa; thoát chính nằm ở custom_exit
    minimal_roi = {"0": 0.25}
    stoploss = -0.10  # cắt lỗ cứng tối đa; custom_stoploss luôn chặt hơn
    use_custom_stoploss = True
    trailing_stop = False

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    startup_candle_count = 250

    # ---- Tham số cố định (ảnh hưởng tới chỉ báo) ----
    z_window = 50
    adf_window = 200
    adf_step = 12

    # ---- Tham số tối ưu được bằng hyperopt ----
    adf_threshold = DecimalParameter(0.05, 0.40, default=0.20, decimals=2, space="buy")
    z_entry = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")
    trend_gap = DecimalParameter(0.3, 3.0, default=1.0, decimals=1, space="buy")
    trend_max_z = DecimalParameter(1.0, 3.0, default=2.0, decimals=1, space="buy")
    use_trend = BooleanParameter(default=True, space="buy")
    mr_htf_filter = BooleanParameter(default=True, space="buy")

    z_exit = DecimalParameter(-0.5, 1.0, default=0.0, decimals=1, space="sell")
    mr_max_hours = IntParameter(12, 96, default=48, space="sell")

    sl_std_mean_rev = DecimalParameter(1.0, 3.5, default=2.0, decimals=1, space="protection")
    sl_std_trend = DecimalParameter(1.0, 4.0, default=2.0, decimals=1, space="protection")
    breakeven_std = DecimalParameter(0.5, 3.0, default=1.5, decimals=1, space="protection")

    # % vốn chấp nhận mất mỗi lệnh (giống "Mức chấp nhận mất tối đa" trong dashboard).
    # Ghi đè trong config.json: "quant": {"risk_pct": 1.5, "sync_risk_from_dashboard": true}
    default_risk_pct = 1.5
    news_block_score = -4  # tổng điểm tin tức <= mức này thì ngừng mở lệnh mới

    plot_config = {
        "main_plot": {
            "rolling_mean": {"color": "orange"},
            "ema_fast": {"color": "#00F0FF"},
            "ema_slow": {"color": "#F0B90B"},
        },
        "subplots": {
            "Z-Score": {"z_score": {"color": "#B266FF"}},
            "ADF p": {"adf_p": {"color": "gray"}},
        },
    }

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 168,
                "trade_limit": 5,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.15,
            },
        ]

    # ------------------------------------------------------------------ chỉ báo
    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_slow"] = ema(dataframe["close"], 50)
        return dataframe

    def informative_pairs(self):
        return market_informative_pairs(self.config)  # BTC khung ngày cho bộ lọc thị trường

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = add_quant_indicators(
            dataframe,
            window=self.z_window,
            adf_window=self.adf_window,
            adf_step=self.adf_step,
        )
        return add_market_regime(self.dp, df, self.config, self.timeframe)

    # ------------------------------------------------------------------ tín hiệu vào lệnh
    def _mean_rev_long(self, df: DataFrame):
        # Nâng cấp so với bản gốc: KHÔNG bắt dao rơi. Chờ nến trước quá bán (Z < -z_entry)
        # rồi Z bắt đầu quay đầu đi lên + nến xanh => xác nhận lực mua quay lại.
        return (
            (df["adf_p"] < self.adf_threshold.value)
            & (df["z_score"].shift(1) < -self.z_entry.value)
            & (df["z_score"] > df["z_score"].shift(1))
            & (df["close"] > df["open"])
            & self._htf_ok(df, long=True)  # khung 4h không ngược chiều
            & (df["volume"] > 0)
        )

    def _htf_ok(self, df: DataFrame, long: bool):
        """Bộ lọc khung 4h cho Mean Reversion (tắt được bằng mr_htf_filter)."""
        if not self.mr_htf_filter.value:
            return Series(True, index=df.index)
        return df["close"] > df["ema_slow_4h"] if long else df["close"] < df["ema_slow_4h"]

    def _trend_long(self, df: DataFrame):
        return (
            (df["adf_p"] >= self.adf_threshold.value)
            & (df["ema_gap_pct"] > self.trend_gap.value)
            & (df["ema_gap_pct"].shift(1) <= self.trend_gap.value)  # vừa mở rộng qua ngưỡng
            & (df["close"] > df["ema_slow_4h"])  # khung 4h cũng đang tăng
            & (df["z_score"] < self.trend_max_z.value)  # không đu đỉnh
            & (df["volume"] > 0)
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ok = market_long_ok(dataframe, self.config)  # BTC dưới SMA200 ngày -> không mở Long mới
        dataframe.loc[self._mean_rev_long(dataframe) & ok, ["enter_long", "enter_tag"]] = (1, "mean_rev")
        if self.use_trend.value:
            dataframe.loc[self._trend_long(dataframe) & ok, ["enter_long", "enter_tag"]] = (1, "trend")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Thoát được xử lý trong custom_exit vì phụ thuộc vào loại lệnh (enter_tag)
        return dataframe

    # ------------------------------------------------------------------ helpers
    def _last_candle(self, pair: str):
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        return df.iloc[-1]

    def _entry_candle(self, pair: str, trade: Trade):
        """Nến phát tín hiệu (nến ngay trước thời điểm khớp lệnh)."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None
        before = df.loc[df["date"] < trade.open_date_utc]
        return before.iloc[-1] if not before.empty else df.iloc[-1]

    def _sl_mult(self, tag: str | None) -> float:
        return self.sl_std_trend.value if tag == "trend" else self.sl_std_mean_rev.value

    def _risk_pct(self) -> float:
        qcfg = self.config.get("quant", {})
        risk = float(qcfg.get("risk_pct", self.default_risk_pct))
        if qcfg.get("sync_risk_from_dashboard") and self.dp.runmode.value in ("live", "dry_run"):
            from quant_core.settings import get_user_settings

            _, risk = get_user_settings(default_risk=risk)
        return max(0.1, min(risk, 10.0))

    # ------------------------------------------------------------------ quản lý vốn
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        candle = self._last_candle(pair)
        if candle is None or not candle["rolling_std"] > 0:
            return proposed_stake
        stop_dist = self._sl_mult(entry_tag) * candle["rolling_std"] / current_rate
        stop_dist = min(max(stop_dist, 0.005), abs(self.stoploss))
        capital = self.wallets.get_total_stake_amount() if self.wallets else proposed_stake
        risk_usd = capital * self._risk_pct() / 100
        stake = risk_usd / stop_dist / max(leverage, 1.0)  # stake = ký quỹ; notional = stake*leverage
        if min_stake:
            stake = max(stake, min_stake)  # "lách" min notional giống bản gốc
        return min(stake, max_stake)

    # ------------------------------------------------------------------ cắt lỗ động
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> float | None:
        sl_price = trade.get_custom_data("sl_price")
        std = trade.get_custom_data("entry_std")
        if sl_price is None or std is None:
            candle = self._entry_candle(pair, trade)
            if candle is None or not candle["rolling_std"] > 0:
                return None
            std = float(candle["rolling_std"])
            dist = self._sl_mult(trade.enter_tag) * std
            sl_price = trade.open_rate + dist if trade.is_short else trade.open_rate - dist
            trade.set_custom_data("sl_price", sl_price)
            trade.set_custom_data("entry_std", std)

        # Dời cắt lỗ về hoà vốn (+phí) khi giá đã chạy đúng hướng >= breakeven_std * σ
        move = (trade.open_rate - current_rate) if trade.is_short else (current_rate - trade.open_rate)
        if move >= self.breakeven_std.value * std:
            fee_pad = trade.open_rate * (trade.fee_open + trade.fee_close)
            be = trade.open_rate - fee_pad if trade.is_short else trade.open_rate + fee_pad
            sl_price = min(sl_price, be) if trade.is_short else max(sl_price, be)

        return stoploss_from_absolute(sl_price, current_rate, is_short=trade.is_short,
                                      leverage=trade.leverage)

    # ------------------------------------------------------------------ thoát lệnh
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str | bool | None:
        c = self._last_candle(pair)
        if c is None:
            return None
        sign = -1 if trade.is_short else 1
        if trade.enter_tag in ("mean_rev", "mean_rev_short"):
            if sign * c["z_score"] >= self.z_exit.value:
                return "z_revert"
            if current_time - trade.open_date_utc > timedelta(hours=self.mr_max_hours.value):
                return "mr_timeout"
        elif trade.enter_tag in ("trend", "trend_short"):
            if sign * (c["ema_fast"] - c["ema_slow"]) < 0:
                return "ema_cross"
        return None

    # ------------------------------------------------------------------ bộ lọc tin tức (live)
    _news_cache: tuple[datetime, int] | None = None

    def bot_start(self, **kwargs) -> None:
        from quant_core.logfilter import install_log_dedup

        install_log_dedup()                        # gộp cảnh báo lặp lại khi mất mạng (log khỏi phình)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str | None,
                            side: str, **kwargs) -> bool:
        if self.dp.runmode.value not in ("live", "dry_run"):
            return True
        from quant_core.strategy_common import make_corr_fn, portfolio_allows

        corr = make_corr_fn(self.dp, self.config, self.timeframe)
        if not portfolio_allows(self.config, pair, side, corr_fn=corr):  # trần rủi ro chung giữa các bot
            return False
        if not self.config.get("quant", {}).get("news_filter", True):
            return True
        now = datetime.now(timezone.utc)
        if self._news_cache is None or now - self._news_cache[0] > timedelta(minutes=15):
            try:
                from quant_core.market_context import news_sentiment_score

                self._news_cache = (now, news_sentiment_score())
            except Exception as e:
                logger.warning("Không lấy được tin tức: %s", e)
                self._news_cache = (now, 0)
        score = self._news_cache[1]
        if side == "long" and score <= self.news_block_score:
            logger.info("Chặn lệnh LONG %s vì tin tức quá tiêu cực (score=%s)", pair, score)
            return False
        if side == "short" and score >= -self.news_block_score:
            logger.info("Chặn lệnh SHORT %s vì tin tức quá tích cực (score=%s)", pair, score)
            return False
        return True


class QuantHybridFuturesStrategy(QuantHybridStrategy):
    """
    Phiên bản Futures: thêm lệnh Short đối xứng + đòn bẩy theo độ mạnh tín hiệu
    (giống 4_alert_bot.py: |Z|>=3 -> x5, mean reversion -> x2, trend -> x3),
    nhưng không vượt "quant.max_leverage" trong config (mặc định x2).
    Dùng với user_data/config.futures.json
    """

    can_short = True
    max_leverage = 5.0

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        df = dataframe
        mr_short = (
            (df["adf_p"] < self.adf_threshold.value)
            & (df["z_score"].shift(1) > self.z_entry.value)
            & (df["z_score"] < df["z_score"].shift(1))
            & (df["close"] < df["open"])
            & self._htf_ok(df, long=False)
            & (df["volume"] > 0)
        )
        trend_short = (
            (df["adf_p"] >= self.adf_threshold.value)
            & (df["ema_gap_pct"] < -self.trend_gap.value)
            & (df["ema_gap_pct"].shift(1) >= -self.trend_gap.value)
            & (df["close"] < df["ema_slow_4h"])
            & (df["z_score"] > -self.trend_max_z.value)
            & (df["volume"] > 0)
        )
        ok_short = market_short_ok(df, self.config)  # chỉ Short khi thị trường chung đang giảm
        dataframe.loc[mr_short & ok_short, ["enter_short", "enter_tag"]] = (1, "mean_rev_short")
        if self.use_trend.value:
            dataframe.loc[trend_short & ok_short, ["enter_short", "enter_tag"]] = (1, "trend_short")
        return dataframe

    def _sl_mult(self, tag: str | None) -> float:
        return self.sl_std_trend.value if tag and tag.startswith("trend") else self.sl_std_mean_rev.value

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str | None,
                 side: str, **kwargs) -> float:
        if entry_tag and entry_tag.startswith("trend"):
            lev = 3.0
        else:
            c = self._last_candle(pair)
            lev = 5.0 if c is not None and abs(c["z_score"]) >= 3.0 else 2.0
        # Trần chung trong config ("quant.max_leverage", mặc định x2 = hồ sơ Cân bằng ở tab 🧭).
        # Khối lượng lệnh tính theo % rủi ro nên lỗ khi chạm cắt lỗ KHÔNG đổi; đòn bẩy thấp hơn chỉ
        # dùng nhiều ký quỹ hơn và đẩy giá thanh lý ra xa hơn (an toàn hơn khi trượt giá / mất kết nối).
        cap = float(self.config.get("quant", {}).get("max_leverage", 2.0))
        return max(1.0, min(lev, cap, self.max_leverage, max_leverage))
