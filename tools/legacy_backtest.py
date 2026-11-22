"""
Backtest kiểu cũ (vector hoá) — port từ QuantTradingSystem/3_backtest_engine.py,
nhưng đọc dữ liệu Freqtrade (.feather). Dùng để ĐỐI CHIẾU với kết quả của Freqtrade:
nếu hai bên chênh nhau nhiều -> có lỗi logic ở đâu đó.

Sửa 2 lỗi nhỏ của bản gốc:
  * Sharpe tự quy đổi theo khung thời gian (bản gốc luôn dùng hệ số của khung 1h)
  * Phí tính trên cả 2 chiều mua/bán giống Freqtrade

    python tools/legacy_backtest.py --pairs BTC/USDT ETH/USDT --timeframe 1h
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant_core.data import load_ohlcv  # noqa: E402
from quant_core.indicators import zscore  # noqa: E402

CANDLES_PER_YEAR = {"15m": 4 * 24 * 365, "1h": 24 * 365, "4h": 6 * 365, "1d": 365}


def run(pair: str, timeframe: str, window: int, z_entry: float, z_exit: float, fee: float) -> dict:
    df = load_ohlcv(pair, timeframe)
    if df.empty:
        raise SystemExit(f"Không có dữ liệu {pair} {timeframe}. Chạy ./run.sh import hoặc download")
    df["return"] = df["close"].pct_change()
    df["z"] = zscore(df["close"], window)
    df = df.dropna().reset_index(drop=True)

    pos, positions = 0, []
    for z in df["z"]:
        if pos == 0 and z < z_entry:
            pos = 1
        elif pos == 1 and z >= z_exit:
            pos = 0
        positions.append(pos)
    df["position"] = pd.Series(positions).shift(1).fillna(0)
    df["trades"] = df["position"].diff().abs().fillna(0)
    df["strat"] = df["position"] * df["return"] - df["trades"] * fee
    equity = (1 + df["strat"]).cumprod()
    dd = (equity - equity.cummax()) / equity.cummax()
    ann = np.sqrt(CANDLES_PER_YEAR.get(timeframe, 24 * 365))
    return {
        "Cặp": pair,
        "Số lệnh": int(df["trades"].sum() // 2),
        "Lợi nhuận bot %": round((equity.iloc[-1] - 1) * 100, 2),
        "Mua & giữ %": round(((1 + df["return"]).prod() - 1) * 100, 2),
        "Sharpe": round(df["strat"].mean() / df["strat"].std() * ann, 2) if df["strat"].std() > 0 else 0,
        "Max DD %": round(dd.min() * 100, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", default=["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"])
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--window", type=int, default=50)
    ap.add_argument("--z-entry", type=float, default=-2.0)
    ap.add_argument("--z-exit", type=float, default=0.0)
    ap.add_argument("--fee", type=float, default=0.001)
    a = ap.parse_args()
    res = pd.DataFrame([run(p, a.timeframe, a.window, a.z_entry, a.z_exit, a.fee) for p in a.pairs])
    print(f"\nBACKTEST KIỂU CŨ — Z-Score {a.window} nến, mua Z<{a.z_entry}, bán Z>={a.z_exit}, "
          f"phí {a.fee * 100:.2f}%/chiều, khung {a.timeframe}")
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
