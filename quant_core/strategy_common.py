"""
Phần dùng chung cho các chiến lược Freqtrade MỚI (Breakout, Smart DCA):
  * Mức rủi ro % vốn (đọc config "quant" hoặc đồng bộ từ dashboard khi chạy dry-run/live)
  * Tính khối lượng lệnh theo rủi ro cố định
  * Bộ lọc tin tức RSS trước khi vào lệnh (chỉ dry-run/live)
  * Bộ bảo vệ tài khoản (Protections)

Giống hệt logic trong QuantHybridStrategy, tách ra để không phải chép lại.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ bộ lọc thị trường chung
# "Thị trường giảm thì đứng ngoài": BTC đóng cửa ngày dưới SMA200 ngày => thị trường crypto đang
# trong xu hướng giảm dài hạn => không mở lệnh LONG mới (Futures: chỉ cho SHORT khi thị trường giảm).
# Bật/tắt trong config: "quant": {"market_filter": true}  (hoặc FREQTRADE__QUANT__MARKET_FILTER=false)
MARKET_TF = "1d"
MARKET_SMA = 200


def market_pair(config: dict) -> str:
    stake = config.get("stake_currency", "USDT")
    return f"BTC/{stake}:{stake}" if config.get("trading_mode") == "futures" else f"BTC/{stake}"


def market_filter_on(config: dict) -> bool:
    return bool(config.get("quant", {}).get("market_filter", True))


def market_informative_pairs(config: dict) -> list[tuple[str, str]]:
    return [(market_pair(config), MARKET_TF)] if market_filter_on(config) else []


def add_market_regime(dp, dataframe, config: dict, timeframe: str):
    """
    Thêm cột `market_up` (1 = BTC trên SMA200 ngày, 0 = dưới) vào DataFrame của mọi cặp.
    Dùng nến NGÀY ĐÃ ĐÓNG (merge_informative_pair dịch thời gian) -> không look-ahead.
    Thiếu dữ liệu (chưa đủ 200 ngày) -> 1 (không chặn).
    """
    from freqtrade.strategy import merge_informative_pair

    dataframe["market_up"] = 1.0
    if not market_filter_on(config) or dp is None:
        return dataframe
    inf = dp.get_pair_dataframe(market_pair(config), MARKET_TF)
    if inf is None or inf.empty:
        return dataframe
    inf = inf[["date", "close"]].copy()
    sma = inf["close"].rolling(MARKET_SMA).mean()
    inf["mkt"] = (inf["close"] > sma).astype(float).where(sma.notna())
    merged = merge_informative_pair(dataframe.drop(columns=["market_up"]), inf[["date", "mkt"]],
                                    timeframe, MARKET_TF, ffill=True)
    merged["market_up"] = merged[f"mkt_{MARKET_TF}"].fillna(1.0)
    return merged.drop(columns=[f"mkt_{MARKET_TF}", f"date_{MARKET_TF}"], errors="ignore")


def market_long_ok(dataframe, config: dict):
    import pandas as pd

    if not market_filter_on(config):
        return pd.Series(True, index=dataframe.index)
    return dataframe["market_up"] >= 0.5


def market_short_ok(dataframe, config: dict):
    import pandas as pd

    if not market_filter_on(config):
        return pd.Series(True, index=dataframe.index)
    return dataframe["market_up"] < 0.5


class QuantRiskMixin:
    default_risk_pct = 1.5
    news_block_score = -4
    _news_cache: tuple[datetime, int] | None = None

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {"method": "StoplossGuard", "lookback_period_candles": 24, "trade_limit": 3,
             "stop_duration_candles": 12, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 168, "trade_limit": 5,
             "stop_duration_candles": 24, "max_allowed_drawdown": 0.15},
        ]

    def _risk_pct(self) -> float:
        qcfg = self.config.get("quant", {})
        risk = float(qcfg.get("risk_pct", self.default_risk_pct))
        if qcfg.get("sync_risk_from_dashboard") and self.dp.runmode.value in ("live", "dry_run"):
            from quant_core.settings import get_user_settings

            _, risk = get_user_settings(default_risk=risk)
        return max(0.1, min(risk, 10.0))

    def _risk_stake(self, stop_dist: float, proposed_stake: float, min_stake: float | None,
                    max_stake: float, leverage: float = 1.0) -> float:
        """Khối lượng (ký quỹ) để nếu chạm cắt lỗ cách `stop_dist` (0.03 = 3%) thì mất đúng risk_pct% vốn."""
        stop_dist = max(stop_dist, 0.005)
        capital = self.wallets.get_total_stake_amount() if self.wallets else proposed_stake
        stake = capital * self._risk_pct() / 100 / stop_dist / max(leverage, 1.0)
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def _news_allows(self, pair: str, side: str) -> bool:
        if self.dp.runmode.value not in ("live", "dry_run"):
            return True
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
        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str | None,
                            side: str, **kwargs) -> bool:
        return self._news_allows(pair, side)
