"""
Truy cập dữ liệu dùng chung cho dashboard / alert bot.

Nguồn dữ liệu duy nhất là thư mục dữ liệu của Freqtrade (user_data/data/binance/*.feather)
=> dashboard, alert bot và Freqtrade luôn nhìn CÙNG một bộ dữ liệu, không lệch nhau.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from quant_core.settings import FT_DATA_DIR

OHLCV = ["date", "open", "high", "low", "close", "volume"]


def list_datasets(datadir: Path = FT_DATA_DIR) -> list[tuple[str, str]]:
    """[('BTC/USDT', '1h'), ...] cho dữ liệu spot."""
    out = []
    for f in sorted(datadir.glob("*.feather")):
        stem = f.stem  # BTC_USDT-1h  (futures: BTC_USDT_USDT-1h-futures)
        parts = stem.split("-")
        if len(parts) != 2:
            continue
        sym, tf = parts
        base_quote = sym.split("_")
        if len(base_quote) != 2:
            continue
        out.append((f"{base_quote[0]}/{base_quote[1]}", tf))
    return out


def dataset_path(pair: str, timeframe: str, datadir: Path = FT_DATA_DIR) -> Path:
    return datadir / f"{pair.replace('/', '_')}-{timeframe}.feather"


def load_ohlcv(pair: str, timeframe: str, datadir: Path = FT_DATA_DIR) -> pd.DataFrame:
    path = dataset_path(pair, timeframe, datadir)
    if not path.exists():
        return pd.DataFrame(columns=OHLCV)
    df = pd.read_feather(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df[OHLCV].sort_values("date").reset_index(drop=True)


def fetch_live_ohlcv(pair: str, timeframe: str = "1h", limit: int = 300,
                     market_type: str = "spot") -> pd.DataFrame:
    """Lấy nến trực tiếp từ Binance qua CCXT (dùng cho alert bot)."""
    import ccxt

    ex = ccxt.binance({"enableRateLimit": True, "timeout": 15000,
                       "options": {"defaultType": "future" if market_type == "futures" else "spot"}})
    raw = ex.fetch_ohlcv(pair, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df[OHLCV]
