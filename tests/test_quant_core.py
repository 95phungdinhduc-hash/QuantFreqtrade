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


def test_news_score_whole_words_only():
    # Trước đây khớp chuỗi con: "security" bị tính là "sec", "below" là "low", "bank" là "ban"
    assert score_text("Bitcoin's quantum security challenge") == 0
    assert score_text("ECB tokenized deposits, securities experiments") == 0
    assert score_text("Bank adoption keeps growing") == 1        # chỉ "adoption", không có "ban"
    assert score_text("ETF assets slip below $1 billion") == 1   # "etf" (+1), "below" không còn là "low"
    # Dạng biến thể vẫn được tính
    assert score_text("XRP falls 10% as bitcoin drops") == -2
    assert score_text("SEC lawsuit") == -2
    assert score_text("Solana surged, ETFs approved") == 3
    assert "Trung lập" in label_for(0)


def test_user_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "APP_DB", tmp_path / "app.db")
    assert settings.get_user_settings(500, 2.0) == (500, 2.0)
    settings.save_user_settings(1234.5, 1.0)
    assert settings.get_user_settings() == (1234.5, 1.0)


def test_alert_bot_follows_market_filter():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alert_bot"))
    from alert_bot import market_allows, regime_line

    down, up = {"up": False, "gap": -16.9}, {"up": True, "gap": 5.0}
    assert not market_allows(True, down) and market_allows(False, down)    # giảm: chặn Long, cho Short
    assert market_allows(True, up) and not market_allows(False, up)        # tăng: cho Long, chặn Short
    assert market_allows(True, None) and market_allows(False, None)        # thiếu dữ liệu: không chặn
    assert "dưới" in regime_line(down) and regime_line(None) == ""


def test_alert_instructions_contain_steps_qty_and_pct():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alert_bot"))
    from alert_bot import futures_instructions, spot_instructions

    plan = plan_position(1000, 1.5, 60000, 600, None, is_long=True, sl_std_mult=2.0, tp_std_mult=3.0)
    spot = spot_instructions("BTC/USDT", 60000, plan, True, 1000)
    assert "Market" in spot and "OCO" in spot and "BTC" in spot
    assert "-2.00%" in spot and "+3.00%" in spot                      # SL 2σ, TP 3σ với σ = 1% giá
    assert "vượt vốn" not in spot                                      # 750$ < vốn 1000$
    assert "vượt vốn" in spot_instructions("BTC/USDT", 60000, plan, True, 100)
    assert "đứng ngoài" in spot_instructions("BTC/USDT", 60000, plan, False, 1000)
    fut = futures_instructions("BTC/USDT", 60000, plan, plan, True, 3, 250.0, 0.75, "")
    assert "Isolated" in fut and "x3" in fut and "LONG" in fut


def _fake_db(path, trades):
    import sqlite3

    con = sqlite3.connect(path)
    con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, pair TEXT, is_short INTEGER, is_open INTEGER)")
    con.executemany("INSERT INTO trades (pair, is_short, is_open) VALUES (?, ?, ?)", trades)
    con.commit()
    con.close()


def test_portfolio_cap_across_bots(tmp_path):
    from quant_core.strategy_common import portfolio_allows, portfolio_dbs

    (tmp_path / "user_data").mkdir()
    _fake_db(tmp_path / "user_data/tradesv3.hybrid.dryrun.sqlite", [("BTC/USDT", 0, 1), ("ETH/USDT", 0, 0)])
    _fake_db(tmp_path / "user_data/tradesv3.dca.dryrun.sqlite", [("SOL/USDT", 0, 1)])
    _fake_db(tmp_path / "user_data/tradesv3.futures.dryrun.sqlite", [("BNB/USDT:USDT", 1, 1)])
    _fake_db(tmp_path / "user_data/tradesv3.sqlite", [("XRP/USDT", 0, 1)] * 9)  # DB live: không được tính
    dbs = portfolio_dbs(True, tmp_path)
    assert len(dbs) == 3
    cfg = {"dry_run": True, "quant": {"max_total_open": 3, "one_bot_per_pair": True}}
    assert portfolio_allows(cfg, "BNB/USDT", "long", dbs)            # Long #3 -> còn chỗ
    assert not portfolio_allows(cfg, "BTC/USDT:USDT", "long", dbs)   # BTC đã có bot giữ Long
    assert portfolio_allows(cfg, "BTC/USDT:USDT", "short", dbs)      # Short khác hướng -> được
    assert not portfolio_allows(cfg, "BNB/USDT:USDT", "short", dbs)  # BNB đã được Short
    cfg["quant"]["max_total_open"] = 2
    assert not portfolio_allows(cfg, "ADA/USDT", "long", dbs)        # đã 2 Long -> chạm trần
    assert portfolio_allows({"quant": {}}, "BTC/USDT", "long", dbs)  # không cấu hình -> không chặn


def test_correlated_cap(tmp_path):
    """Giống ngày 25/11: bot Futures đang Short SOL + ETH -> Short BTC (tương quan cao) phải bị chặn."""
    from quant_core.strategy_common import portfolio_allows, portfolio_dbs

    (tmp_path / "user_data").mkdir()
    _fake_db(tmp_path / "user_data/tradesv3.futures.dryrun.sqlite",
             [("SOL/USDT:USDT", 1, 1), ("ETH/USDT:USDT", 1, 1), ("BNB/USDT:USDT", 0, 1)])
    dbs = portfolio_dbs(True, tmp_path)
    cfg = {"dry_run": True, "quant": {"max_total_open": 4, "max_correlated_open": 2, "corr_threshold": 0.8}}
    high = lambda a, b: 0.88                                           # noqa: E731
    assert not portfolio_allows(cfg, "BTC/USDT:USDT", "short", dbs, corr_fn=high)   # lệnh Short thứ 3 cùng nhóm
    assert portfolio_allows(cfg, "BTC/USDT:USDT", "long", dbs, corr_fn=high)        # chỉ 1 Long đang mở
    low = lambda a, b: 0.3                                             # noqa: E731
    assert portfolio_allows(cfg, "DOGE/USDT:USDT", "short", dbs, corr_fn=low)       # coin ít tương quan -> được
    assert not portfolio_allows(cfg, "BTC/USDT:USDT", "short", dbs)                 # thiếu dữ liệu -> coi như tương quan
    cfg["quant"]["max_correlated_open"] = 0
    assert portfolio_allows(cfg, "BTC/USDT:USDT", "short", dbs, corr_fn=high)       # tắt luật -> như cũ


def test_make_corr_fn():
    import numpy as np
    import pandas as pd
    from quant_core.strategy_common import make_corr_fn

    rng = np.random.default_rng(0)
    dates = pd.date_range("2026-01-01", periods=800, freq="1h", tz="UTC")
    base = np.cumsum(rng.normal(0, 0.01, 800))
    data = {"BTC": base, "ETH": base + rng.normal(0, 0.002, 800), "XYZ": np.cumsum(rng.normal(0, 0.01, 800))}

    class DP:
        def get_pair_dataframe(self, pair, tf):
            coin = pair.split("/")[0]
            assert pair.endswith(":USDT") and tf == "1h"
            return pd.DataFrame({"date": dates, "close": 100 * np.exp(data[coin])}) if coin in data else pd.DataFrame()

    corr = make_corr_fn(DP(), {"stake_currency": "USDT", "trading_mode": "futures"}, "1h")
    assert corr("BTC", "ETH") > 0.8
    assert abs(corr("BTC", "XYZ")) < 0.3
    assert corr("BTC", "NOPE") is None


def test_log_dedup_filter():
    import logging
    from quant_core.logfilter import DedupFilter

    t = [0.0]
    f = DedupFilter(window=600, clock=lambda: t[0])
    rec = lambda msg, lvl=logging.WARNING: logging.LogRecord("freqtrade.exchange", lvl, "", 0, msg, (), None)  # noqa: E731
    assert f.filter(rec("Could not fetch BTC/USDT 1h, retry 1"))          # lần đầu: ghi
    for i in range(500):                                                   # mất mạng: lặp lại -> gộp
        assert not f.filter(rec(f"Could not fetch BTC/USDT 1h, retry {i}"))
    assert f.filter(rec("Could not fetch ETH/USDT 1h, retry 1"))          # tin khác: vẫn ghi
    assert f.filter(rec("Bot heartbeat 1", logging.INFO))                 # INFO: không đụng tới
    assert f.filter(rec("Bot heartbeat 1", logging.INFO))
    t[0] = 601
    r = rec("Could not fetch BTC/USDT 1h, retry 9")
    assert f.filter(r) and "lặp lại 500 lần" in r.getMessage()            # hết cửa sổ: ghi kèm tổng kết


def test_alert_morning_summary(tmp_path, monkeypatch):
    import sys
    from datetime import datetime
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alert_bot"))
    import alert_bot as ab

    down = {"up": False, "gap": -15.8}
    rows = [
        {"sym": "BTC/USDT", "status": "none", "price": 59916.6, "z": -0.89, "gap": 0.41, "adf": 0.08, "chg24": -1.2},
        {"sym": "ETH/USDT", "status": "sent", "price": 1743.6, "z": 2.21, "gap": 0.66, "adf": 0.17, "chg24": 2.0,
         "side": "SHORT", "strategy": "🔄 MEAN REVERSION"},
        {"sym": "SOL/USDT", "status": "blocked", "price": 71.6, "z": 0.3, "gap": 1.9, "adf": 0.4, "chg24": 0.5,
         "side": "LONG", "strategy": "🚀 TREND FOLLOWING"},
        {"sym": "BNB/USDT", "status": "none", "price": 552.5, "z": 1.0, "gap": -1.3, "adf": 0.3, "chg24": None},
        {"sym": "XRP/USDT", "status": "error"},
    ]
    now = 1_000_000.0
    sent = [[now - 3600, "ETH/USDT", "SHORT"], [now - 7200, "ETH/USDT", "SHORT"], [now - 30 * 3600, "SOL/USDT", "SHORT"]]
    msg = ab.build_summary(rows, down, "1h", sent, now=now)
    lines = msg.splitlines()
    btc = next(i for i, l in enumerate(lines) if "*BTC*" in l)
    assert lines[btc].startswith("⚪") and "(-1.2% 24h)" in lines[btc]
    assert "Đi ngang" in lines[btc + 1] and "Z ≥ +2" in lines[btc + 1] and "SHORT" in lines[btc + 1]  # thị trường giảm -> chờ Short
    assert any(l.startswith("🔔 *ETH*") for l in lines) and "bị bộ lọc" in msg
    bnb = next(i for i, l in enumerate(lines) if "*BNB*" in l)
    assert lines[bnb].startswith("🟡") and "24h" not in lines[bnb]          # gap -1.3% ≥ 75% của 1.5% -> gần tới
    assert "Có xu hướng" in lines[bnb + 1] and "gap ≤ −1.5%" in lines[bnb + 1]
    assert "XRP* — không lấy được" in msg
    assert "BTC 0 · ETH 2 · SOL 0 · BNB 0" in msg                           # SOL 30 giờ trước không tính

    # chỉ gửi 1 lần/ngày, từ 8:00 tới trước 12:00; tắt bằng -1
    st = {"summary_date": "2026-11-27"}
    assert ab.summary_due(datetime(2026, 11, 28, 8, 5), st, 8)
    assert not ab.summary_due(datetime(2026, 11, 27, 9, 0), st, 8)
    assert not ab.summary_due(datetime(2026, 11, 28, 7, 59), st, 8)
    assert not ab.summary_due(datetime(2026, 11, 28, 12, 0), st, 8)
    assert not ab.summary_due(datetime(2026, 11, 28, 8, 5), st, -1)

    monkeypatch.setattr(ab, "STATE_FILE", tmp_path / "state.json")
    out = []
    monkeypatch.setattr(ab, "send_telegram", out.append)
    ab.record_signal("ETH/USDT", "SHORT")
    assert ab.maybe_send_summary(rows, down, "1h", 8, force=True) and "ETH 1" in out[0]
    assert ab.load_state()["summary_date"] == datetime.now(ab.market_context.VN_TZ).strftime("%Y-%m-%d")


def test_alert_telegram_commands(monkeypatch):
    import sys
    import time as _time
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alert_bot"))
    import alert_bot as ab

    cfg = {"pairs": ["BTC/USDT", "ETH/USDT"], "timeframe": "1h", "window": 50, "legacy": False,
           "use_filter": True, "summary_hour": 8}
    seen = []

    def fake_analyze(sym, *a):
        seen.append(sym)
        if sym == "BAD/USDT":
            raise ValueError("binance does not have market symbol BAD/USDT")
        return {"sym": sym, "price": 100.0, "z": 0.5, "gap": 0.2, "adf": 0.1, "chg24": 1.0, "status": "none"}, None

    monkeypatch.setattr(ab, "analyze", fake_analyze)
    monkeypatch.setattr(ab.market_context, "btc_regime", lambda: {"up": False, "gap": -15.0})
    monkeypatch.setattr(ab.settings, "get_user_settings", lambda *a, **k: (1000.0, 1.5))
    monkeypatch.setattr(ab, "load_state", lambda: {})

    assert "/tomtat" in ab.handle_command("/start", cfg) and "/btc /eth" in ab.handle_command("/help", cfg)
    assert "TÓM TẮT" in ab.handle_command("/tomtat@QuantBot", cfg) and seen == ["BTC/USDT", "ETH/USDT"]
    assert "*ETH/USDT (1h)*" in ab.handle_command("eth", cfg)                 # gõ không có dấu /
    assert "*XRP/USDT" in ab.handle_command("/coin xrpusdt", cfg)
    assert "Không lấy được dữ liệu BAD/USDT" in ab.handle_command("/coin bad", cfg)
    assert "ví dụ" in ab.handle_command("/coin", cfg)
    assert "chưa hiểu" in ab.handle_command("/abc", cfg) and ab.handle_command("   ", cfg) is None

    # chỉ trả lời đúng chat của bạn, bỏ tin cũ; trả lời theo lệnh không gửi kèm "BÁO ĐỘNG"
    monkeypatch.setattr(ab.settings, "TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setattr(ab.settings, "TELEGRAM_CHAT_ID", "42")
    now = _time.time()
    updates = [{"update_id": 1, "message": {"chat": {"id": 42}, "date": now, "text": "/help"}},
               {"update_id": 2, "message": {"chat": {"id": 99}, "date": now, "text": "/help"}},      # người lạ
               {"update_id": 3, "message": {"chat": {"id": 42}, "date": now - 3600, "text": "/help"}}]  # tin cũ
    calls = []

    class Stop(Exception):
        pass

    def fake_api(method, **p):
        calls.append((method, p.get("offset")))
        if method == "getUpdates":
            if p.get("offset"):
                raise Stop
            return {"result": updates}
        return {}

    replies = []
    monkeypatch.setattr(ab, "tg_api", fake_api)
    monkeypatch.setattr(ab, "send_telegram", lambda m, **k: replies.append((m, k)))
    monkeypatch.setattr(ab.time, "sleep", lambda s: (_ for _ in ()).throw(Stop()))
    try:
        ab.listen_commands(cfg)
    except Stop:
        pass
    assert calls[0][0] == "setMyCommands" and ("getUpdates", 4) in calls
    assert len(replies) == 1 and "Lệnh của alert bot" in replies[0][0] and replies[0][1]["tag"] == "💬 TRẢ LỜI"
