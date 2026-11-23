"""
Kiểm tra "đã đủ điều kiện dùng tiền thật chưa?" — chấm từng tiêu chí ✅ / ❌ / ⚠️.

Chạy:  ./run.sh readiness

Đây là danh sách kiểm tra KỸ THUẬT do hệ thống tự đặt ra, không phải lời khuyên đầu tư.
Đạt hết vẫn có thể lỗ; chưa đạt thì chắc chắn chưa nên dùng tiền thật.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

UD = ROOT / "user_data"
LEGACY_ALERT = Path.home() / "QuantTradingSystem" / "4_alert_bot.py"  # chỉ ĐỌC để so token cũ

# Ngưỡng
MIN_TRADES = 30          # lệnh đã đóng mỗi bot dry-run
MIN_DAYS = 60            # số ngày chạy dry-run
STABLE_SHARE = 0.75      # walk-forward: có lãi ở >= 75% số giai đoạn
MAX_DOWNTIME_MIN = 60    # tổng thời gian máy ngủ / mất mạng trong 14 ngày
MAX_RISK_PCT = 2.0
SAFE_LEVERAGE = 2        # backtest 2 năm: x2 lỗ ít hơn x5 (-9,4% so với -13,8%)
MAX_LEVERAGE = 5         # trên mức này là chưa đạt

BOTS = {"Hybrid": "tradesv3.hybrid.dryrun.sqlite", "Breakout": "tradesv3.breakout.dryrun.sqlite",
        "Smart DCA": "tradesv3.dca.dryrun.sqlite", "Futures": "tradesv3.futures.dryrun.sqlite"}

results: list[tuple[str, str, str, str]] = []  # (nhóm, trạng thái, tiêu chí, chi tiết)


def add(group: str, ok: bool | None, name: str, detail: str = "") -> None:
    results.append((group, "✅" if ok else "⚠️" if ok is None else "❌", name, detail))


def load(name: str) -> dict:
    return json.loads((UD / name).read_text())


# ------------------------------------------------------------------ 1. bằng chứng chiến lược
def check_strategy() -> None:
    g = "1. Bằng chứng chiến lược"
    wf_file = UD / "walk_forward.json"
    if not wf_file.exists():
        add(g, False, "Kiểm chứng walk-forward", "chưa có — chạy ./run.sh validate")
    else:
        wf = json.loads(wf_file.read_text())
        good = [n.replace("Quant", "").replace("Strategy", "")
                for n, sm in wf.get("summary", {}).items()
                if sm["profitable"] >= STABLE_SHARE * sm["n"] and sm["sum_profit_pct"] > 0]
        add(g, bool(good), f"Có chiến lược ổn định (lãi ≥ {STABLE_SHARE:.0%} giai đoạn, tổng > 0)",
            ", ".join(good) if good else "chưa chiến lược nào đạt")

    for bot, db in BOTS.items():
        f = UD / db
        if not f.exists():
            add(g, False, f"Dry-run {bot}", "chưa có database")
            continue
        con = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        try:
            first, n, profit = con.execute(
                "SELECT MIN(open_date), COUNT(*), COALESCE(SUM(close_profit_abs), 0) "
                "FROM trades WHERE is_open = 0").fetchone()
        finally:
            con.close()
        days = (datetime.now() - datetime.fromisoformat(str(first)[:19])).days if first else 0
        ok = n >= MIN_TRADES and days >= MIN_DAYS and profit > 0
        add(g, ok, f"Dry-run {bot}: ≥ {MIN_TRADES} lệnh, ≥ {MIN_DAYS} ngày, có lãi",
            f"{n} lệnh · {days} ngày · {profit:+.2f} USDT")


# ------------------------------------------------------------------ 2. an toàn vận hành
def check_operations() -> None:
    g = "2. An toàn vận hành"
    spot, fut = load("config.json"), load("config.futures.json")
    for label, cfg in (("Spot", spot), ("Futures", fut)):
        ot = cfg.get("order_types", {})
        add(g, bool(ot.get("stoploss_on_exchange")), f"Cắt lỗ đặt trên sàn ({label})",
            "stoploss_on_exchange = true" if ot.get("stoploss_on_exchange") else "chưa bật")

    cap = spot.get("quant", {}).get("capital", {})
    split = cap.get("split", {})
    total_share = sum(split.values())
    add(g, bool(split) and total_share <= 1.0 + 1e-9, "Chia vốn riêng cho từng bot Spot",
        f"{' · '.join(f'{k} {v:.0%}' for k, v in split.items())} (tổng {total_share:.0%} của "
        f"{cap.get('total_usdt', 0):,.0f} USDT)" if split else "chưa cấu hình quant.capital")

    q = spot.get("quant", {})
    mto = int(q.get("max_total_open", 0) or 0)
    add(g, 0 < mto <= 6 and bool(q.get("one_bot_per_pair")), "Trần rủi ro chung giữa các bot",
        f"tối đa {mto} lệnh cùng hướng · 1 coin chỉ 1 bot giữ: {bool(q.get('one_bot_per_pair'))}")

    lev = float(fut.get("quant", {}).get("max_leverage", 2))
    if lev <= SAFE_LEVERAGE:
        add(g, True, f"Đòn bẩy Futures ≤ x{MAX_LEVERAGE}", f"max_leverage = x{lev:g}")
    elif lev <= MAX_LEVERAGE:
        add(g, None, f"Đòn bẩy Futures ≤ x{MAX_LEVERAGE}",
            f"max_leverage = x{lev:g} (bạn chọn) — backtest 2 năm x{SAFE_LEVERAGE} lỗ ít hơn; "
            "cân nhắc hạ khi dùng tiền thật")
    else:
        add(g, False, f"Đòn bẩy Futures ≤ x{MAX_LEVERAGE}", f"max_leverage = x{lev:g} — quá cao")

    try:
        from quant_core.settings import get_user_settings

        _, risk = get_user_settings()
        add(g, risk <= MAX_RISK_PCT, f"Rủi ro mỗi lệnh ≤ {MAX_RISK_PCT}%", f"đang đặt {risk}%")
    except Exception as e:
        add(g, None, "Rủi ro mỗi lệnh", f"không đọc được: {e}")

    # máy ngủ / mất mạng trong 14 ngày (watchdog ghi lại)
    log = ROOT / "logs" / "watchdog.log"
    since = datetime.now() - timedelta(days=14)
    down = events = 0
    if log.exists():
        for line in log.read_text(errors="ignore").splitlines():
            m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) .*(💤|📡).*\(~(\d+) phút\)", line)
            if m and datetime.fromisoformat(m.group(1)) >= since:
                down += int(m.group(3))
                events += 1
    add(g, down <= MAX_DOWNTIME_MIN, f"Máy chạy liên tục (ngủ/mất mạng ≤ {MAX_DOWNTIME_MIN} phút / 14 ngày)",
        f"{events} lần · tổng ~{down} phút" + (" — cân nhắc VPS hoặc không gập nắp" if down > MAX_DOWNTIME_MIN else ""))

    loaded = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    add(g, "com.quantfreqtrade.watchdog" in loaded, "Watchdog tự động đang bật",
        "có" if "com.quantfreqtrade.watchdog" in loaded else "chạy ./run.sh autostart on")


# ------------------------------------------------------------------ 3. bảo mật
def env_values() -> dict[str, str]:
    out = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def check_security() -> None:
    g = "3. Bảo mật"
    f = ROOT / ".env"
    mode = stat.S_IMODE(f.stat().st_mode) if f.exists() else None
    add(g, mode == 0o600, "File .env chỉ chủ máy đọc được (600)", oct(mode) if mode is not None else "không có .env")

    env = env_values()
    if LEGACY_ALERT.exists():
        old = LEGACY_ALERT.read_text(errors="ignore")
        for key, label in (("TELEGRAM_BOT_TOKEN", "Token Telegram"), ("GEMINI_API_KEY", "Khoá Gemini")):
            val = env.get(key, "")
            leaked = bool(val) and val in old
            add(g, not leaked, f"{label} đã đổi (không còn là bản bị lộ trong code cũ)",
                "vẫn là bản cũ — đổi theo hướng dẫn trong LENH.md" if leaked else "ok")
    else:
        add(g, None, "Token cũ", "không tìm thấy code cũ để so")

    has_key = bool(env.get("FREQTRADE__EXCHANGE__KEY"))
    add(g, None, "Khoá API sàn: TẮT quyền rút tiền, chỉ cho IP máy chạy bot, dùng tài khoản con",
        "đã có khoá — tự kiểm tra trên Binance" if has_key else "chưa có khoá (đúng, vì đang dry-run)")


def main() -> None:
    os.chdir(ROOT)
    check_strategy()
    check_operations()
    check_security()
    group = None
    for g, st, name, detail in results:
        if g != group:
            print(f"\n{g}")
            group = g
        print(f"  {st} {name}" + (f"\n       → {detail}" if detail else ""))
    fails = sum(st == "❌" for _, st, _, _ in results)
    passed = sum(st == "✅" for _, st, _, _ in results)
    print(f"\nĐạt {passed}/{len(results)} tiêu chí · {fails} chưa đạt · "
          f"{sum(st == '⚠️' for _, st, _, _ in results)} cần tự kiểm tra")
    if fails:
        print("👉 CHƯA SẴN SÀNG cho tiền thật — tiếp tục dry-run và xử lý các mục ❌.")
    else:
        print("👉 Đạt các tiêu chí kỹ thuật. Nếu thử tiền thật: 1 bot Spot, số tiền nhỏ chấp nhận mất, "
              "kiểm tra các mục ⚠️ trước.")
    print("(Danh sách kiểm tra kỹ thuật — không phải lời khuyên đầu tư.)")


if __name__ == "__main__":
    main()
