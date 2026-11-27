"""
Tạo dữ liệu mẫu để kiểm tra web app (docs/js/indicators.js) cho ra ĐÚNG số giống bản Python.

Chạy:  .venv/bin/python tools/make_web_fixture.py     -> ghi tests/web/fixture.json
Sau đó: node --test tests/web

Dữ liệu cố định (sinh ngẫu nhiên có seed) -> chạy lại vẫn ra cùng file, không cần mạng.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alert_bot.alert_bot import pick_signal  # noqa: E402
from quant_core.indicators import add_quant_indicators, adf_pvalue, rsi  # noqa: E402
from quant_core.risk import plan_position  # noqa: E402
from statsmodels.tsa.adfvalues import mackinnonp  # noqa: E402


def series(seed: int, n: int, kind: str) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    if kind == "trend":
        close = 60000 * np.exp(np.cumsum(rng.normal(0.0015, 0.008, n)))
    elif kind == "range":   # dao động quanh trung bình -> ADF nhỏ
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.85 * x[i - 1] + rng.normal(0, 0.006)
        close = 3000 * np.exp(x)
    else:
        close = 150 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    start = pd.Timestamp("2026-10-01", tz="UTC")
    dates = pd.date_range(start, periods=n, freq="1h")
    return pd.DataFrame({
        "date": dates,
        "open": close * (1 + rng.normal(0, 0.001, n)),
        "high": close * (1 + np.abs(rng.normal(0, 0.004, n))),
        "low": close * (1 - np.abs(rng.normal(0, 0.004, n))),
        "close": close,
        "volume": rng.uniform(1, 10, n),
    })


def f(v) -> float | None:
    v = float(v)
    return v if np.isfinite(v) else None


def main() -> None:
    out = {"datasets": [], "mackinnon": [], "adf": [], "plans": [], "signals": []}
    for seed, kind in ((1, "trend"), (2, "range"), (3, "walk")):
        df = series(seed, 300, kind)
        ind = add_quant_indicators(df, window=50)
        ind["rsi"] = rsi(df["close"])
        rows = []
        for _, r in ind.iterrows():
            rows.append({k: f(r[c]) for k, c in (("mean", "rolling_mean"), ("std", "rolling_std"), ("z", "z_score"),
                                                  ("emaFast", "ema_fast"), ("emaSlow", "ema_slow"),
                                                  ("gap", "ema_gap_pct"), ("atr", "atr"), ("rsi", "rsi"),
                                                  ("adf", "adf_p"))})
        sig = pick_signal(ind.iloc[-1], legacy=False)
        out["datasets"].append({
            "kind": kind,
            "candles": [{"t": int(d.timestamp() * 1000), "o": o, "h": h, "l": lo, "c": c, "v": v}
                        for d, o, h, lo, c, v in df[["date", "open", "high", "low", "close", "volume"]].itertuples(index=False)],
            "rows": rows,
            "signal": None if sig is None else dict(zip(
                ["strategy", "isLong", "strong", "slMult", "tpMult", "useMean", "leverage"],
                [sig[0], bool(sig[1]), bool(sig[2]), sig[3], sig[4], sig[5], sig[6]])),
        })

    for t in (-25.0, -5.2, -3.4, -2.86, -1.61, -1.2, 0.0, 1.5, 3.0):
        out["mackinnon"].append({"t": t, "p": float(mackinnonp(t, regression="c", N=1))})

    rng = np.random.default_rng(7)
    for n in (60, 120, 200):
        walk = 100 + np.cumsum(rng.normal(0, 1, n))
        ar = np.zeros(n)
        for i in range(1, n):
            ar[i] = 0.5 * ar[i - 1] + rng.normal()
        out["adf"] += [{"values": walk.tolist(), "p": adf_pvalue(walk)},
                       {"values": (50 + ar).tolist(), "p": adf_pvalue(50 + ar)}]

    for kw in (dict(capital=1000, risk_pct=1.5, entry=60000, std=900, mean=61000, is_long=True,
                    sl_std_mult=2.0, tp_std_mult=1.5),
               dict(capital=1000, risk_pct=1.5, entry=3000, std=40, mean=None, is_long=False,
                    sl_std_mult=2.0, tp_std_mult=3.0),
               dict(capital=50, risk_pct=2.0, entry=150, std=3, mean=None, is_long=True,
                    sl_std_mult=2.0, tp_std_mult=3.0, min_notional=21)):
        p = plan_position(**kw)
        out["plans"].append({"args": kw, "out": {"stopLoss": p.stop_loss, "takeProfit": p.take_profit,
                                                 "riskUsd": p.risk_usd, "positionUsd": p.position_usd,
                                                 "coinAmount": p.coin_amount, "stopDistPct": p.stop_distance_pct,
                                                 "rr": p.rr_ratio}})

    for z, gap, adf in ((-2.7, 0.3, 0.05), (2.1, -0.2, 0.1), (3.2, 0.0, 0.01), (0.5, 1.8, 0.6),
                        (0.2, -2.9, 0.4), (1.9, 1.2, 0.3), (-2.5, 0.0, float("nan"))):
        sig = pick_signal(pd.Series({"z_score": z, "ema_gap_pct": gap, "adf_p": adf}), legacy=False)
        out["signals"].append({"row": {"z": z, "gap": gap, "adf": f(adf)},
                               "out": None if sig is None else [sig[0], bool(sig[1]), bool(sig[2]), sig[3],
                                                                 sig[4], sig[5], sig[6]]})

    # --- tab 🧭 Tư vấn (advisor.py) + kurtosis / VaR của tab Phân tích, Vốn & Rủi ro
    from quant_core import advisor
    from quant_core.risk import value_at_risk

    out["advisor"] = []
    items = []
    for seed, kind, news in ((11, "trend", 2), (12, "range", -5), (13, "down", 0), (14, "walk", 7)):
        rng = np.random.default_rng(seed)
        n = 999
        if kind == "down":
            close = 3000 * np.exp(np.cumsum(rng.normal(-0.0012, 0.007, n)))
        else:
            close = series(seed, n, kind)["close"].to_numpy()
        df = pd.DataFrame({"date": pd.date_range(pd.Timestamp("2026-09-01", tz="UTC"), periods=n, freq="1h"),
                           "open": close * (1 + rng.normal(0, 0.001, n)),
                           "high": close * (1 + np.abs(rng.normal(0, 0.004, n))),
                           "low": close * (1 - np.abs(rng.normal(0, 0.004, n))), "close": close,
                           "volume": rng.uniform(1, 10, n)})
        d = advisor.enrich(df)
        for prof, fut in (("can_bang", True), ("than_trong", False)):
            a = advisor.assess(f"{kind.upper()}/USDT", d, news, 1000.0, advisor.PROFILES[prof]["risk_pct"], fut)
            if prof == "can_bang":
                items.append(a)
            p = a.plan
            out["advisor"].append({
                "kind": kind, "news": news, "profile": prof, "futures": fut,
                "candles": [{"t": int(t.timestamp() * 1000), "o": o, "h": h, "l": lo, "c": c, "v": v}
                            for t, o, h, lo, c, v in df[["date", "open", "high", "low", "close", "volume"]].itertuples(index=False)]
                if prof == "can_bang" else None,
                "tail": [{k: f(r[c]) for k, c in (("emaSlow4h", "ema_slow_4h"), ("roc7d", "roc_7d"), ("volAnn", "vol_ann"),
                                                   ("volPct", "vol_pct"), ("dcHigh", "dc_high"), ("ema200", "ema200"))}
                         for _, r in d.tail(60).iterrows()],
                "out": {"regime": a.regime, "stance": a.stance, "kind": a.kind, "playbook": a.playbook, "score": a.score,
                        "factors": a.factors, "zone": a.zone, "reasons": a.reasons,
                        "plan": None if p is None else {"stopLoss": p.stop_loss, "takeProfit": p.take_profit,
                                                        "positionUsd": p.position_usd, "riskUsd": p.risk_usd}},
                "kurtosis": f(d["log_return"].kurtosis()),
                "var": list(value_at_risk(d["close"].pct_change())),
            })
    alloc = advisor.allocate(items, "mao_hiem", 1000.0)
    out["allocate"] = [{"asset": r["Tài sản"], "weight": r["Tỷ trọng"], "usdt": r["USDT"]} for _, r in alloc.iterrows()]
    out["mood"] = list(advisor.mood([a.score for a in items]))

    dst = ROOT / "tests" / "web" / "fixture.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False))
    print(f"Đã ghi {dst.relative_to(ROOT)} ({dst.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
