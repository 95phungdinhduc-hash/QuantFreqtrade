"""
Bối cảnh thị trường: phiên giao dịch + tâm lý tin tức RSS.
Port từ 2_dashboard.py (fetch_crypto_news) và 4_alert_bot.py (get_trading_session, get_news_sentiment).

Các hàm này GỌI MẠNG -> không dùng trong backtest, chỉ dùng ở dashboard / alert bot
(hoặc trong chiến lược khi chạy live, có cache).
"""

from __future__ import annotations

from datetime import datetime

import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
}
BULLISH_WORDS = ["surge", "jump", "bull", "high", "gain", "approve", "etf", "buy", "rally",
                 "soar", "upgrade", "adoption", "record"]
BEARISH_WORDS = ["drop", "crash", "bear", "low", "hack", "ban", "sec", "lawsuit", "fall",
                 "plunge", "dump", "fear", "inflation", "cpi"]


def trading_session(now: datetime | None = None) -> str:
    hour = (now or datetime.now(VN_TZ)).astimezone(VN_TZ).hour
    if 6 <= hour < 14:
        return "🇯🇵 Phiên Á (Sideway, biên độ hẹp)"
    if 14 <= hour < 19:
        return "🇬🇧 Phiên Âu (Biến động trung bình)"
    if 19 <= hour < 23:
        return "🇺🇸 Phiên Mỹ + Âu (Thanh khoản cực lớn, sóng mạnh)"
    return "🇺🇸 Phiên Mỹ (Chạy theo xu hướng)"


def score_text(text: str) -> int:
    """>0 tích cực, <0 tiêu cực, 0 trung lập."""
    t = text.lower()
    return sum(w in t for w in BULLISH_WORDS) - sum(w in t for w in BEARISH_WORDS)


def label_for(score: int) -> str:
    if score > 0:
        return "🟢 Tích cực (Bullish)"
    if score < 0:
        return "🔴 Tiêu cực (Bearish)"
    return "⚪ Trung lập (Neutral)"


def fetch_news(per_feed: int = 8, timeout: int = 10) -> list[dict]:
    """Kéo tin RSS và chấm điểm từng bài."""
    import socket

    import feedparser

    items: list[dict] = []
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        for source, url in FEEDS.items():
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries[:per_feed]:
                    summary = entry.get("summary", "")[:200]
                    s = score_text(entry.title + " " + summary)
                    items.append({
                        "source": source,
                        "title": entry.title,
                        "link": entry.get("link", ""),
                        "published": entry.get("published", "Mới cập nhật"),
                        "score": s,
                        "sentiment": label_for(s),
                    })
            except Exception:
                continue
    finally:
        socket.setdefaulttimeout(old_timeout)
    return items


def news_sentiment_score(items: list[dict] | None = None) -> int:
    """Tổng điểm tâm lý toàn thị trường (số tin tốt - số tin xấu)."""
    items = fetch_news() if items is None else items
    return sum(1 if i["score"] > 0 else -1 if i["score"] < 0 else 0 for i in items)


# ------------------------------------------------------------------ bộ lọc thị trường chung
# Cùng quy tắc với các bot Freqtrade (quant_core/strategy_common.py):
# BTC đóng cửa ngày (nến ĐÃ ĐÓNG) dưới SMA200 ngày => thị trường giảm => không Long, chỉ Short.
MARKET_SMA = 200


def market_filter_enabled() -> bool:
    """Đọc "quant.market_filter" trong user_data/config.json (mặc định bật)."""
    import json

    from quant_core.settings import USER_DATA

    try:
        cfg = json.loads((USER_DATA / "config.json").read_text())
        return bool(cfg.get("quant", {}).get("market_filter", True))
    except Exception:
        return True


def btc_regime() -> dict | None:
    """
    {"up": bool, "close", "sma", "gap" (% so với SMA), "date"} hoặc None nếu thiếu dữ liệu.
    Ưu tiên nến ngày trực tiếp từ Binance, mất mạng thì dùng dữ liệu đã tải.
    """
    from quant_core.data import fetch_live_ohlcv, load_ohlcv

    try:
        d = fetch_live_ohlcv("BTC/USDT", "1d", limit=MARKET_SMA + 60).iloc[:-1]  # bỏ nến đang chạy
    except Exception:
        d = load_ohlcv("BTC/USDT", "1d")
    if d is None or len(d) < MARKET_SMA:
        return None
    close = float(d["close"].iloc[-1])
    sma = float(d["close"].rolling(MARKET_SMA).mean().iloc[-1])
    return {"up": close > sma, "close": close, "sma": sma, "gap": (close / sma - 1) * 100,
            "date": d["date"].iloc[-1]}
