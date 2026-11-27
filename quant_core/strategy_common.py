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
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ trần rủi ro chung giữa các bot
# Mỗi bot có database riêng nên tự nó không biết bot khác đang giữ gì. Trước khi mở lệnh mới, đọc
# (chỉ đọc) database của TẤT CẢ bot cùng chế độ (dry-run hoặc live) để:
#   * "max_total_open": tổng số lệnh CÙNG HƯỚNG (Long hoặc Short) của mọi bot không vượt mức này
#   * "one_bot_per_pair": một coin chỉ được 1 bot giữ theo cùng hướng (tránh nhân đôi cùng 1 cược)
# BTC/ETH/SOL/BNB thường lên xuống cùng nhau -> nhiều lệnh Long cùng lúc ~ 1 cược lớn vào "crypto tăng".
def portfolio_dbs(dry_run: bool, root: Path = ROOT) -> list[Path]:
    files = sorted({*root.glob("tradesv3*.sqlite"), *(root / "user_data").glob("tradesv3*.sqlite")})
    return [f for f in files if ("dryrun" in f.name) == bool(dry_run)]


def open_positions(dbs: list[Path]) -> list[tuple[str, bool, str]]:
    """[(coin gốc, is_short, tên database)] của mọi lệnh đang mở."""
    out: list[tuple[str, bool, str]] = []
    for f in dbs:
        try:
            con = sqlite3.connect(f"file:{f}?mode=ro", uri=True, timeout=2)
            try:
                rows = con.execute("SELECT pair, is_short FROM trades WHERE is_open = 1").fetchall()
            finally:
                con.close()
        except Exception as e:  # database đang khởi tạo / khoá -> bỏ qua, không chặn bot
            logger.debug("Không đọc được %s: %s", f.name, e)
            continue
        out += [(str(pair).split("/")[0], bool(short), f.name) for pair, short in rows]
    return out


def make_corr_fn(dp, config: dict, timeframe: str, lookback: int = 720):
    """
    Hàm corr(coin_a, coin_b) = tương quan lợi nhuận log của `lookback` nến gần nhất (khớp theo thời gian),
    lấy từ dữ liệu bot đang có (dp). Không có dữ liệu -> None.
    """
    import numpy as np
    import pandas as pd

    stake = config.get("stake_currency", "USDT")
    suffix = f":{stake}" if config.get("trading_mode") == "futures" else ""
    cache: dict[str, pd.Series | None] = {}

    def returns(coin: str):
        if coin not in cache:
            try:
                df = dp.get_pair_dataframe(f"{coin}/{stake}{suffix}", timeframe)
                cache[coin] = None if df is None or df.empty else \
                    np.log(df.set_index("date")["close"]).diff().tail(lookback)
            except Exception:
                cache[coin] = None
        return cache[coin]

    def corr(a: str, b: str):
        ra, rb = returns(a), returns(b)
        if ra is None or rb is None:
            return None
        c = pd.concat([ra, rb], axis=1, join="inner").dropna()
        return float(c.iloc[:, 0].corr(c.iloc[:, 1])) if len(c) >= 48 else None

    return corr


def portfolio_allows(config: dict, pair: str, side: str, dbs: list[Path] | None = None,
                     corr_fn=None) -> bool:
    """
    Thêm "max_correlated_open" (0 = tắt): tối đa N lệnh CÙNG HƯỚNG trên các coin tương quan cao
    (≥ "corr_threshold", mặc định 0.8). BTC/ETH/SOL/BNB thường tương quan 0.8–0.9 -> 3 lệnh Short cùng lúc
    thực chất là 1 cược x3 rủi ro. Không tính được tương quan (thiếu dữ liệu) -> coi như tương quan (an toàn).
    """
    q = config.get("quant", {})
    max_total = int(q.get("max_total_open", 0) or 0)
    one_per_pair = bool(q.get("one_bot_per_pair", False))
    max_corr = int(q.get("max_correlated_open", 0) or 0)
    threshold = float(q.get("corr_threshold", 0.8))
    if not max_total and not one_per_pair and not max_corr:
        return True
    want_short = side == "short"
    coin = pair.split("/")[0]
    same_dir = [p for p in open_positions(dbs if dbs is not None else portfolio_dbs(config.get("dry_run", True)))
                if p[1] == want_short]
    word = "SHORT" if want_short else "LONG"
    if max_total and len(same_dir) >= max_total:
        logger.info("Chặn lệnh %s %s: các bot đã giữ %d lệnh %s (trần chung max_total_open = %d)",
                    word, pair, len(same_dir), word, max_total)
        return False
    if one_per_pair and any(c == coin for c, _, _ in same_dir):
        holder = next(db for c, _, db in same_dir if c == coin)
        logger.info("Chặn lệnh %s %s: %s đã được giữ %s ở %s (one_bot_per_pair)", word, pair, coin, word, holder)
        return False
    if max_corr:
        linked = []
        for c, _, _ in same_dir:
            if c == coin:
                continue
            r = corr_fn(coin, c) if corr_fn else None
            if r is None or r >= threshold:
                linked.append(f"{c} {'?' if r is None else f'{r:.2f}'}")
        if len(linked) >= max_corr:
            logger.info("Chặn lệnh %s %s: đã có %d lệnh %s trên coin tương quan cao (%s) — max_correlated_open = %d",
                        word, pair, len(linked), word, ", ".join(linked), max_corr)
            return False
    return True


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

    def bot_start(self, **kwargs) -> None:
        from quant_core.logfilter import install_log_dedup

        install_log_dedup()                        # gộp cảnh báo lặp lại khi mất mạng (log khỏi phình)

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
        if self.dp.runmode.value in ("live", "dry_run") and not portfolio_allows(
                self.config, pair, side, corr_fn=make_corr_fn(self.dp, self.config, self.timeframe)):
            return False
        return self._news_allows(pair, side)
