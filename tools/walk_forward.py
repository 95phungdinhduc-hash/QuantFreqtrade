"""
Kiểm chứng theo giai đoạn (walk-forward) — chạy cùng một bộ tham số trên TỪNG giai đoạn 6 tháng.

Mục đích: một chiến lược tốt phải ổn định qua nhiều kiểu thị trường (tăng, giảm, đi ngang),
không phải chỉ đẹp ở một khoảng thời gian may mắn. Tham số KHÔNG được tối ưu lại giữa các giai
đoạn -> mỗi giai đoạn là một bài kiểm tra "chưa từng thấy" đối với chiến lược.

Chạy:  ./run.sh validate            (khoảng 10–20 phút)
Kết quả: user_data/walk_forward.json  (dashboard tab 📊 Backtest đọc file này)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "user_data" / "walk_forward.json"
WF_DIR = ROOT / "user_data" / "backtest_results" / "walkforward"

SPOT = ["QuantZScoreStrategy", "QuantHybridStrategy", "QuantBreakoutStrategy", "QuantSmartDCAStrategy"]
FUTURES = ["QuantHybridFuturesStrategy"]


def data_start(pair_file: Path) -> date:
    import pandas as pd

    return pd.read_feather(pair_file, columns=["date"])["date"].min().date()


def windows(start: date, end: date, months: int = 6) -> list[tuple[str, str]]:
    """Chia [start, end] thành các khối `months` tháng (khối cuối có thể ngắn hơn)."""
    out, cur = [], date(start.year, start.month, 1)
    if cur < start:  # bỏ tháng lẻ đầu tiên (cần dữ liệu khởi động cho chỉ báo)
        cur = date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
    while cur < end:
        m = cur.month - 1 + months
        nxt = date(cur.year + m // 12, m % 12 + 1, 1)
        out.append((cur.strftime("%Y%m%d"), min(nxt, end).strftime("%Y%m%d")))
        cur = nxt
    return out


def run_bt(config: str, strategies: list[str], timerange: str, outdir: Path) -> dict:
    from freqtrade.data.btanalysis import load_backtest_stats

    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [str(ROOT / "run.sh"), "ft", "backtesting", "-c", config, "--strategy-list", *strategies,
           "--timerange", timerange, "--export", "trades", "--backtest-directory", str(outdir),
           "--cache", "none"]
    if "futures" not in config:
        cmd += ["--timeframe-detail", "15m"]  # giống ./run.sh backtest-all
    env = {**os.environ, "FREQTRADE__TELEGRAM__ENABLED": "false"}
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(res.stdout[-1500:], res.stderr[-1500:])
        raise SystemExit(f"Backtest lỗi ở giai đoạn {timerange}")
    stats = load_backtest_stats(outdir)
    rows = {}
    for name, s in stats["strategy"].items():
        n = s.get("total_trades", 0) or 0
        rows[name] = {
            "profit_pct": round(s.get("profit_total", 0) * 100, 2),
            "max_dd_pct": round((s.get("max_drawdown_account") or 0) * 100, 2),
            "trades": n,
            "winrate": round(s.get("wins", 0) / n * 100, 1) if n else 0.0,
            "market_pct": round(s.get("market_change", 0) * 100, 2),
        }
    return rows


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT), help="file JSON kết quả")
    out = Path(ap.parse_args().out)
    mf = os.environ.get("FREQTRADE__QUANT__MARKET_FILTER", "true").lower() not in ("false", "0")
    print(f"Bộ lọc thị trường (BTC < SMA200 ngày thì đứng ngoài): {'BẬT' if mf else 'TẮT'}")
    first = data_start(ROOT / "user_data/data/binance/BTC_USDT-1h.feather")
    end = date.today()
    wins = windows(first, end)
    if len(wins) < 2:
        raise SystemExit("Chưa đủ dữ liệu — chạy ./run.sh download 730 --prepend trước.")
    print(f"Kiểm chứng {len(wins)} giai đoạn từ {wins[0][0]} đến {wins[-1][1]}\n")

    result = {"generated": datetime.now().isoformat(timespec="seconds"), "market_filter": mf,
              "windows": [], "strategies": {}}
    for i, (a, b) in enumerate(wins, 1):
        tr = f"{a}-{b}"
        print(f"[{i}/{len(wins)}] {a[:4]}-{a[4:6]} → {b[:4]}-{b[4:6]} ...", flush=True)
        rows = run_bt("user_data/config.json", SPOT, tr, WF_DIR / f"{tr}_spot")
        rows.update(run_bt("user_data/config.futures.json", FUTURES, tr, WF_DIR / f"{tr}_futures"))
        market = next(iter(rows.values()))["market_pct"]
        result["windows"].append({"timerange": tr, "label": f"{a[4:6]}/{a[:4]}–{b[4:6]}/{b[:4]}",
                                  "market_pct": market})
        for name, r in rows.items():
            result["strategies"].setdefault(name, []).append(r)
        line = " | ".join(f"{n.replace('Quant', '').replace('Strategy', '')} {r['profit_pct']:+.1f}%"
                          for n, r in rows.items())
        print(f"     thị trường {market:+.1f}% | {line}")

    print("\nTỔNG KẾT (số giai đoạn có lãi / thắng thị trường):")
    for name, rs in result["strategies"].items():
        prof = sum(r["profit_pct"] > 0 for r in rs)
        beat = sum(r["profit_pct"] > w["market_pct"] for r, w in zip(rs, result["windows"]))
        total = sum(r["profit_pct"] for r in rs)
        worst = max(r["max_dd_pct"] for r in rs)
        result.setdefault("summary", {})[name] = {"profitable": prof, "beat_market": beat, "n": len(rs),
                                                  "sum_profit_pct": round(total, 2), "worst_dd_pct": worst}
        print(f"  {name:28s} lãi {prof}/{len(rs)} · thắng thị trường {beat}/{len(rs)} · "
              f"tổng {total:+.1f}% · sụt vốn tệ nhất {worst:.1f}%")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nĐã lưu {out} — xem trên dashboard tab 📊 Backtest.")


if __name__ == "__main__":
    main()
