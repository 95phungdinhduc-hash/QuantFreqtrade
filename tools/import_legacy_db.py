"""
Chuyển dữ liệu nến từ quant_data.db (QuantTradingSystem cũ) sang định dạng Freqtrade (.feather).

  * Mở DB cũ ở chế độ CHỈ ĐỌC (mode=ro) -> không bao giờ sửa/xoá dữ liệu của dự án cũ.
  * Gộp với dữ liệu Freqtrade đã có (nếu đã chạy download-data), ưu tiên nến mới nhất.

Cách dùng:
    python tools/import_legacy_db.py
    python tools/import_legacy_db.py --db /duong/dan/quant_data.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freqtrade.data.converter import clean_ohlcv_dataframe  # noqa: E402
from freqtrade.data.history.datahandlers import get_datahandler  # noqa: E402
from freqtrade.enums import CandleType  # noqa: E402

DEFAULT_DB = ROOT.parent / "QuantTradingSystem" / "quant_data.db"
COLS = ["date", "open", "high", "low", "close", "volume"]


def parse_table(name: str) -> tuple[str, str] | None:
    """'BTC_USDT_1h' -> ('BTC/USDT', '1h')"""
    parts = name.split("_")
    if len(parts) != 3:
        return None
    return f"{parts[0]}/{parts[1]}", parts[2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB, help="Đường dẫn tới quant_data.db cũ")
    ap.add_argument("--datadir", type=Path, default=ROOT / "user_data" / "data" / "binance")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"[!] Không tìm thấy {args.db}")

    args.datadir.mkdir(parents=True, exist_ok=True)
    dh = get_datahandler(args.datadir, "feather")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)  # CHỈ ĐỌC
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    imported = 0
    for table in sorted(tables):
        parsed = parse_table(table)
        if not parsed:
            continue  # bỏ qua user_settings, ...
        pair, tf = parsed
        raw = pd.read_sql(f'SELECT timestamp, open, high, low, close, volume FROM "{table}"', conn)
        if raw.empty:
            continue
        raw["date"] = pd.to_datetime(raw["timestamp"].astype("int64"), unit="ms", utc=True)
        new = raw[COLS].astype({c: "float64" for c in COLS[1:]})

        old = dh.ohlcv_load(pair, tf, CandleType.SPOT, fill_missing=False, warn_no_data=False)
        merged = pd.concat([old[COLS], new]) if not old.empty else new
        merged = merged.drop_duplicates(subset="date", keep="last").sort_values("date")
        merged = clean_ohlcv_dataframe(merged, tf, pair, fill_missing=False, drop_incomplete=False)
        dh.ohlcv_store(pair, tf, merged.reset_index(drop=True), CandleType.SPOT)
        imported += 1
        print(f"[+] {pair:10s} {tf:4s} {len(merged):6d} nến  "
              f"({merged['date'].iloc[0]:%Y-%m-%d} -> {merged['date'].iloc[-1]:%Y-%m-%d})")
    conn.close()
    print(f"\n=== Đã chuyển {imported} bảng vào {args.datadir} ===")


if __name__ == "__main__":
    main()
