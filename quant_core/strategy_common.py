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
