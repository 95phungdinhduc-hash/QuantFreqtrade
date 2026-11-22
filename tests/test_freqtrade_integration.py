"""
Kiểm thử tích hợp: chạy Freqtrade backtest thật trên dữ liệu đã import.
Bỏ qua nếu chưa có dữ liệu (chạy ./run.sh import trước).
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FT = ROOT / ".venv" / "bin" / "freqtrade"
HAS_DATA = (ROOT / "user_data/data/binance/BTC_USDT-1h.feather").exists()


def _env():
    from quant_core import settings  # noqa: F401  (nạp .env vào os.environ)
    return os.environ.copy()


@pytest.mark.skipif(not HAS_DATA, reason="chưa có dữ liệu")
@pytest.mark.parametrize("strategy,config", [
    ("QuantZScoreStrategy", "user_data/config.json"),
    ("QuantHybridStrategy", "user_data/config.json"),
    ("QuantBreakoutStrategy", "user_data/config.json"),
    ("QuantSmartDCAStrategy", "user_data/config.json"),
])
def test_backtest_runs(strategy, config):
    res = subprocess.run(
        [str(FT), "backtesting", "-c", config, "-s", strategy, "-p", "BTC/USDT",
         "--timerange", "20260801-20261101", "--export", "none", "--cache", "none"],
        cwd=ROOT, capture_output=True, text=True, env=_env(), timeout=300)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    assert "STRATEGY SUMMARY" in res.stdout


def test_strategies_are_discoverable():
    res = subprocess.run([str(FT), "list-strategies", "-c", "user_data/config.json", "-1"],
                         cwd=ROOT, capture_output=True, text=True, env=_env(), timeout=120)
    assert res.returncode == 0, res.stderr[-2000:]
    for name in ["QuantZScoreStrategy", "QuantHybridStrategy", "QuantHybridFuturesStrategy",
                 "QuantBreakoutStrategy", "QuantSmartDCAStrategy"]:
        assert name in res.stdout
