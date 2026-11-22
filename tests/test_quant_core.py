"""Kiểm thử thư viện quant_core. Chạy: ./run.sh test"""

import numpy as np
import pandas as pd
import pytest

from quant_core import settings
from quant_core.indicators import add_quant_indicators, rolling_adf_pvalue, zscore
from quant_core.market_context import label_for, score_text
from quant_core.risk import half_kelly, plan_position, value_at_risk


@pytest.fixture
def ohlcv():
    rng = np.random.default_rng(42)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=600, freq="1h", tz="UTC"),
        "open": close * (1 + rng.normal(0, 0.001, 600)),
        "high": close * 1.005, "low": close * 0.995, "close": close,
        "volume": rng.uniform(1, 10, 600),
    })


def test_zscore_matches_legacy_formula(ohlcv):
    c = ohlcv["close"]
    legacy = (c - c.rolling(50).mean()) / c.rolling(50).std()  # công thức trong 3_backtest_engine.py
    pd.testing.assert_series_equal(zscore(c, 50), legacy)


def test_rolling_adf_has_no_lookahead(ohlcv):
    full = rolling_adf_pvalue(ohlcv["close"], window=200, step=12)
    partial = rolling_adf_pvalue(ohlcv["close"].iloc[:400], window=200, step=12)
    pd.testing.assert_series_equal(full.iloc[:400], partial)  # thêm dữ liệu tương lai không đổi quá khứ


def test_rolling_adf_time_anchored_is_start_independent(ohlcv):
    # Bot live nạp dữ liệu bắt đầu từ mốc khác backtest -> kết quả vẫn phải trùng
    full = rolling_adf_pvalue(ohlcv["close"], 200, 12, dates=ohlcv["date"])
    late = ohlcv.iloc[37:].reset_index(drop=True)
    part = rolling_adf_pvalue(late["close"], 200, 12, dates=late["date"])
    a = full.iloc[37:].reset_index(drop=True)
    k = part.first_valid_index()
    pd.testing.assert_series_equal(a.iloc[k:], part.iloc[k:], check_names=False)


@pytest.mark.parametrize("unit", ["ns", "us", "ms"])
def test_rolling_adf_works_with_any_datetime_unit(ohlcv, unit):
    short = ohlcv.tail(252).reset_index(drop=True)
    dates = short["date"].astype(f"datetime64[{unit}, UTC]")
    out = rolling_adf_pvalue(short["close"], 200, 12, dates=dates)
    assert out.notna().sum() >= 40  # ~ (252-200)/1 nến sau mốc đầu tiên


def test_add_quant_indicators_columns(ohlcv):
    df = add_quant_indicators(ohlcv)
    for col in ["z_score", "ema_fast", "ema_slow", "ema_gap_pct", "atr", "adf_p", "rolling_std"]:
        assert col in df
    assert df["adf_p"].dropna().between(0, 1).all()
    assert len(df) == len(ohlcv)


def test_plan_position_matches_dashboard_logic():
    # Vốn 1000, rủi ro 1.5%, giá 100, std 2, SL 1σ -> SL=98, khoảng cách 2% -> lệnh 750$
    p = plan_position(1000, 1.5, entry=100, std=2, mean=101, is_long=True, sl_std_mult=1.0)
    assert p.stop_loss == pytest.approx(98)
    assert p.take_profit == pytest.approx(103)  # max(mean, entry + 1.5σ)
    assert p.position_usd == pytest.approx(750)
    assert p.risk_usd == pytest.approx(15)
    assert p.rr_ratio == pytest.approx(1.5)


def test_plan_position_short_and_min_notional():
    p = plan_position(100, 1.0, entry=100, std=10, mean=90, is_long=False, min_notional=21)
    assert p.stop_loss > 100 and p.take_profit < 100
    assert p.position_usd == pytest.approx(21)  # bị ép lên min notional
    assert p.risk_usd == pytest.approx(21 * 0.10)


def test_var_and_kelly():
    r = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01, -0.01, 0.02, -0.03, 0.01, 0.02])
    var, cvar = value_at_risk(r)
    assert cvar <= var < 0
    assert half_kelly(r) > 0
    assert half_kelly(pd.Series([-0.01, -0.02])) == 0.0


def test_sentiment_scoring():
    assert score_text("Bitcoin ETF approve, price surge") > 0
    assert score_text("Exchange hack, market crash") < 0
    assert "Trung lập" in label_for(0)


def test_user_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "APP_DB", tmp_path / "app.db")
    assert settings.get_user_settings(500, 2.0) == (500, 2.0)
    settings.save_user_settings(1234.5, 1.0)
    assert settings.get_user_settings() == (1234.5, 1.0)
