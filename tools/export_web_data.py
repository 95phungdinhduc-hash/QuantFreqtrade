"""
Xuất dữ liệu cho web app (docs/) — những thứ trình duyệt KHÔNG tự lấy được:
  * Tin tức CoinDesk/CoinTelegraph đã chấm điểm (2 trang này chặn trình duyệt đọc trực tiếp - CORS)
  * Kết quả backtest gần nhất, đường cong vốn, Half-Kelly, walk-forward
  * Vài thông số cấu hình bot (danh sách coin, đòn bẩy tối đa, bộ lọc thị trường)
Đồng thời chép theme.css + fx.js của dashboard sang docs/ để web và dashboard luôn cùng giao diện.

CHỈ xuất số liệu công khai: không có khoá API, mật khẩu, địa chỉ IP hay số dư ví bot.

Chạy:  ./run.sh web-data        (hoặc .venv/bin/python tools/export_web_data.py)
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant_core import market_context, settings  # noqa: E402
from quant_core.risk import half_kelly  # noqa: E402

BT_DIR = settings.USER_DATA / "backtest_results"
OUT = ROOT / "docs" / "data" / "snapshot.json"
STRATS = ["QuantHybridFuturesStrategy", "QuantHybridStrategy", "QuantBreakoutStrategy",
          "QuantSmartDCAStrategy", "QuantZScoreStrategy"]


def latest_backtest(strategy: str) -> Path | None:
    for meta in sorted(BT_DIR.glob("*.meta.json"), reverse=True):
        try:
            if strategy in json.loads(meta.read_text()):
                return meta.with_name(meta.name.replace(".meta.json", ".zip"))
        except Exception:
            continue
    return None


def num(v, nd: int = 4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if np.isfinite(v) else None


def summary(filename: str) -> dict:
    from freqtrade.data.btanalysis import load_backtest_stats

    stats = load_backtest_stats(BT_DIR, filename=filename)
    out = {"rows": [], "market": None, "start": None, "end": None}
    for name, s in stats.get("strategy", {}).items():
        trades = s.get("total_trades", 0) or 0
        out["rows"].append({"name": name, "profit": num(s.get("profit_total", 0) * 100, 2),
                            "dd": num((s.get("max_drawdown_account") or 0) * 100, 2), "trades": trades,
                            "win": num((s.get("wins", 0) / trades * 100) if trades else 0.0, 1)})
        out["market"] = num(s.get("market_change", 0) * 100, 2)
        out["start"], out["end"] = str(s.get("backtest_start", ""))[:10], str(s.get("backtest_end", ""))[:10]
    return out


def backtest_detail(filename: str) -> dict:
    """Bảng so sánh + đường cong vốn (rút gọn) + Half-Kelly + lý do thoát, giống tab 📊 Backtest."""
    from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats

    stats = load_backtest_stats(BT_DIR, filename=filename)
    comp = []
    for r in stats.get("strategy_comparison", []):
        comp.append({"key": r.get("key"), "trades": r.get("trades"), "profit_pct": num(r.get("profit_total_pct"), 2),
                     "profit_abs": num(r.get("profit_total_abs"), 2), "wins": r.get("wins"), "losses": r.get("losses"),
                     "dd_pct": num((r.get("max_drawdown_account") or 0) * 100, 2), "hold": r.get("duration_avg")})
    strategies = []
    for strat, s in stats.get("strategy", {}).items():
        trades = load_backtest_data(BT_DIR, strategy=strat, filename=filename)
        if trades.empty:
            continue
        trades = trades.sort_values("close_date")
        equity = s["starting_balance"] + trades["profit_abs"].cumsum()
        step = max(1, len(trades) // 400)                       # tối đa ~400 điểm / đường
        idx = list(range(0, len(trades), step))
        if idx[-1] != len(trades) - 1:
            idx.append(len(trades) - 1)
        curve = [[int(trades["close_date"].iloc[i].timestamp() * 1000), num(equity.iloc[i], 2)] for i in idx]
        exits = [{"key": e.get("key"), "trades": e.get("trades"), "profit_pct": num(e.get("profit_total_pct"), 2),
                  "wins": e.get("wins"), "losses": e.get("losses")} for e in s.get("exit_reason_summary", [])]
        last = trades.tail(30)[["pair", "enter_tag", "exit_reason", "open_date", "close_date", "profit_ratio",
                                "profit_abs"]]
        strategies.append({
            "name": strat, "start_balance": s["starting_balance"], "n": len(trades),
            "kelly": num(half_kelly(trades["profit_ratio"]), 2), "equity": curve, "exits": exits,
            "last_trades": [{"pair": r.pair, "tag": r.enter_tag, "exit": r.exit_reason,
                             "open": r.open_date.strftime("%Y-%m-%d %H:%M"),
                             "close": r.close_date.strftime("%Y-%m-%d %H:%M"),
                             "pct": num(r.profit_ratio * 100, 2), "abs": num(r.profit_abs, 2)}
                            for r in last.itertuples()],
        })
    market = next(iter(stats["strategy"].values()), {}).get("market_change", 0) * 100
    return {"file": filename, "comparison": comp, "strategies": strategies, "market": num(market, 2)}


def main() -> None:
    cfg = json.loads((settings.USER_DATA / "config.json").read_text())
    try:
        fcfg = json.loads((settings.USER_DATA / "config.futures.json").read_text())
    except Exception:
        fcfg = {}
    out: dict = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {"pairs": cfg.get("exchange", {}).get("pair_whitelist", []),
                   "market_filter": bool(cfg.get("quant", {}).get("market_filter", True)),
                   "futures_max_leverage": fcfg.get("quant", {}).get("max_leverage", 2)},
    }

    news = market_context.fetch_news()
    out["news"] = [{k: n[k] for k in ("source", "title", "link", "published", "score")} for n in news]
    out["news_score"] = market_context.news_sentiment_score(news) if news else None
    print(f"Tin tức: {len(news)} bài, điểm {out['news_score']}")

    evidence = {}
    for strat in STRATS:
        f = latest_backtest(strat)
        if f is None:
            continue
        summ = summary(f.name)
        for r in summ["rows"]:
            if r["name"] == strat:
                evidence[strat] = {**r, "market": summ["market"]}
    out["evidence"] = evidence
    hybrid_file = latest_backtest("QuantHybridStrategy")
    if hybrid_file:
        out["backtest_summary"] = summary(hybrid_file.name)
        out["backtest"] = backtest_detail(hybrid_file.name)
        print(f"Backtest: {hybrid_file.name} ({len(out['backtest']['strategies'])} chiến lược)")

    wf = {}
    for key, name in (("filter", "walk_forward.json"), ("nofilter", "walk_forward_nofilter.json")):
        p = settings.USER_DATA / name
        if p.exists():
            wf[key] = json.loads(p.read_text())
    out["walk_forward"] = wf

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Đã ghi {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")

    # web dùng CHUNG giao diện với dashboard
    shutil.copyfile(ROOT / "dashboard" / "theme.css", ROOT / "docs" / "css" / "theme.css")
    shutil.copyfile(ROOT / "dashboard" / "fx.js", ROOT / "docs" / "js" / "fx.js")
    print("Đã chép dashboard/theme.css + fx.js sang docs/")


if __name__ == "__main__":
    main()
