"""
Chỉ báo định lượng — port từ QuantTradingSystem (2_dashboard.py, 3_backtest_engine.py, 4_alert_bot.py).

Quy ước: KHÔNG được nhìn trước tương lai (no look-ahead). Mọi giá trị tại nến i
chỉ dùng dữ liệu từ nến <= i, nên an toàn cho backtest của Freqtrade.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd


def zscore(close: pd.Series, window: int = 50) -> pd.Series:
    """Z-Score = (giá - trung bình trượt) / độ lệch chuẩn trượt. Giống hệt bản gốc."""
    mean = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    return (close - mean) / std.replace(0, np.nan)


def ema(close: pd.Series, span: int) -> pd.Series:
    """EMA giống 4_alert_bot.py (adjust=False)."""
    return close.ewm(span=span, adjust=False).mean()


def adf_pvalue(values: np.ndarray | pd.Series) -> float:
    """p-value của kiểm định ADF (Augmented Dickey-Fuller). < 0.05 => chuỗi dừng (đi ngang)."""
    from statsmodels.tsa.stattools import adfuller

    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 20 or np.allclose(arr, arr[0]):
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(adfuller(arr, autolag="AIC", result_object=False)[1])


def rolling_adf_pvalue(close: pd.Series, window: int = 200, step: int = 12,
                       dates: pd.Series | None = None) -> pd.Series:
    """
    ADF p-value trượt, tính mỗi `step` nến trên `window` nến gần nhất rồi forward-fill.

    Bản dashboard gốc chạy ADF trên TOÀN BỘ lịch sử (có look-ahead nếu dùng trong backtest).
    Bản này chỉ dùng quá khứ nên dùng được làm bộ lọc "chế độ thị trường" trong chiến lược.

    Nếu truyền `dates`, các mốc tính được NEO THEO THỜI GIAN (không theo vị trí dòng) để
    bot live (nạp ~1000 nến gần nhất) và backtest (nạp toàn bộ lịch sử) cho ra cùng kết quả.
    """
    values = close.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    step = max(1, step)
    if dates is not None and n > 1:
        d = pd.to_datetime(pd.Series(dates), utc=True)
        # Không dùng astype(int64): pandas 3 có thể lưu theo µs/ms/ns -> đổi qua Timedelta cho chắc
        secs = ((d - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1)).to_numpy(dtype="int64")
        candle = int(np.median(np.diff(secs))) or 1
        idx = np.flatnonzero((secs // candle) % step == 0)
        idx = idx[idx >= window - 1]
    else:
        idx = range(window - 1, n, step)
    for i in idx:
        out[i] = adf_pvalue(values[i - window + 1 : i + 1])
    return pd.Series(out, index=close.index).ffill()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (dùng cho cắt lỗ động)."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI kiểu Wilder. < 30 quá bán, > 70 quá mua."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0).where(loss.notna())


def donchian(df: pd.DataFrame, period: int = 48) -> tuple[pd.Series, pd.Series]:
    """
    Kênh Donchian của `period` nến TRƯỚC nến hiện tại (đã shift 1 -> không look-ahead).
    Trả về (đỉnh cao nhất, đáy thấp nhất).
    """
    return (df["high"].rolling(period).max().shift(1), df["low"].rolling(period).min().shift(1))


def add_quant_indicators(
    df: pd.DataFrame,
    window: int = 50,
    ema_fast: int = 20,
    ema_slow: int = 50,
    adf_window: int = 200,
    adf_step: int = 12,
    with_adf: bool = True,
) -> pd.DataFrame:
    """
    Thêm toàn bộ cột chỉ báo dùng chung vào DataFrame OHLCV (cột open/high/low/close/volume).

    Cột tạo ra: rolling_mean, rolling_std, z_score, ema_fast, ema_slow, ema_gap_pct,
                atr, log_return, adf_p (nếu with_adf).
    """
    df = df.copy()
    close = df["close"]
    df["rolling_mean"] = close.rolling(window=window).mean()
    df["rolling_std"] = close.rolling(window=window).std()
    df["z_score"] = (close - df["rolling_mean"]) / df["rolling_std"].replace(0, np.nan)
    df["ema_fast"] = ema(close, ema_fast)
    df["ema_slow"] = ema(close, ema_slow)
    df["ema_gap_pct"] = (df["ema_fast"] - df["ema_slow"]) / df["ema_slow"] * 100
    df["atr"] = atr(df)
    df["log_return"] = np.log(close / close.shift(1))
    if with_adf:
        df["adf_p"] = rolling_adf_pvalue(close, window=adf_window, step=adf_step,
                                         dates=df["date"] if "date" in df else None)
    return df
