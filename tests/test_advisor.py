"""Kiểm thử bộ tư vấn chiến lược (quant_core/advisor.py)."""

import numpy as np
import pandas as pd
import pytest

from quant_core import advisor
from quant_core.indicators import donchian, rsi


def _frame(close: np.ndarray) -> pd.DataFrame:
    n = len(close)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
        "open": close, "high": close * 1.003, "low": close * 0.997, "close": close,
        "volume": np.ones(n),
    })


@pytest.fixture
def uptrend():
    rng = np.random.default_rng(1)
    return _frame(100 * np.exp(np.cumsum(0.002 + rng.normal(0, 0.004, 900))))


@pytest.fixture
def downtrend():
    rng = np.random.default_rng(2)
    return _frame(100 * np.exp(np.cumsum(-0.002 + rng.normal(0, 0.004, 900))))


def test_rsi_bounds_and_donchian_no_lookahead(uptrend):
    r = rsi(uptrend["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    hi, lo = donchian(uptrend, 48)
    # Đỉnh kênh tại nến i chỉ dùng nến < i
    i = 500
    assert hi.iloc[i] == uptrend["high"].iloc[i - 48:i].max()
    assert lo.iloc[i] == uptrend["low"].iloc[i - 48:i].min()


def test_enrich_no_lookahead(uptrend):
    full = advisor.enrich(uptrend)
    cut = advisor.enrich(uptrend.iloc[:700])
    cols = ["ema_slow_4h", "rsi", "dc_high", "roc_7d", "z_score"]
    pd.testing.assert_frame_equal(full.loc[650:699, cols].reset_index(drop=True),
                                  cut.loc[650:699, cols].reset_index(drop=True))


def test_uptrend_scores_positive_downtrend_negative(uptrend, downtrend):
    up = advisor.assess("UP/USDT", advisor.enrich(uptrend))
    down = advisor.assess("DN/USDT", advisor.enrich(downtrend))
    assert up.score > 0 > down.score
    assert up.regime in ("up", "range")
    assert down.regime in ("down", "range")
    assert -100 <= down.score <= up.score <= 100
    assert up.reasons and down.reasons


def test_downtrend_never_suggests_spot_long_without_capitulation(downtrend):
    a = advisor.assess("DN/USDT", advisor.enrich(downtrend), allow_futures=False)
    if a.regime == "down":
        assert a.kind != "long"


def test_allocation_respects_profile(uptrend, downtrend):
    items = [advisor.assess("UP/USDT", advisor.enrich(uptrend)),
             advisor.assess("DN/USDT", advisor.enrich(downtrend))]
    for key, prof in advisor.PROFILES.items():
        alloc = advisor.allocate(items, key, 1000)
        assert alloc["Tỷ trọng"].sum() == pytest.approx(1.0)
        coins = alloc[alloc["Tài sản"] != "USDT (tiền mặt)"]
        assert (coins["Tỷ trọng"] <= prof["max_weight"] + 1e-9).all()
        assert alloc.iloc[-1]["Tỷ trọng"] >= prof["cash_min"] - 1e-9
        assert "DN/USDT" not in set(coins["Tài sản"]) or items[1].regime != "down"


def test_mood_labels():
    assert advisor.mood([-60, -50])[0] == "Rất tiêu cực"
    assert advisor.mood([0, 5])[0] == "Trung lập"
    assert advisor.mood([60, 50])[0] == "Rất tích cực"


def test_walk_forward_windows_cover_range():
    import sys
    from datetime import date
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from walk_forward import windows

    w = windows(date(2024, 11, 22), date(2026, 11, 22))
    assert w[0][0] == "20241201" and w[-1][1] == "20261122"
    assert all(a < b for a, b in w)
    assert all(w[i][1] == w[i + 1][0] for i in range(len(w) - 1))  # liền mạch, không chồng lấn
