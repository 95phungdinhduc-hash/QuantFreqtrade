"""
Bot cảnh báo Telegram + Gemini AI — bản nâng cấp của QuantTradingSystem/4_alert_bot.py.

Thay đổi so với bản gốc:
  * Token/API key đọc từ .env (bản gốc ghi cứng trong code — rất nguy hiểm nếu lộ file)
  * Dùng chung chỉ báo với bot Freqtrade (quant_core) -> tín hiệu cảnh báo = tín hiệu bot
  * Thêm bộ lọc chế độ thị trường ADF (đi ngang -> Mean Reversion, xu hướng -> Trend)
  * Chống spam: cùng 1 tín hiệu chỉ gửi lại sau `cooldown` phút
  * Báo kèm trạng thái bot Freqtrade (nếu đang chạy): đang giữ lệnh cặp này hay không
  * SDK Gemini mới (google-genai). Không có key -> chạy thuần toán học
  * Mỗi sáng 8:00 (giờ VN) gửi 1 tin tóm tắt CẢ 4 coin, kể cả khi không có tín hiệu

Chạy:  ./run.sh alert            (quét mỗi 5 phút)
       ./run.sh alert --once     (quét 1 lần rồi thoát — để thử)
       ./run.sh alert --summary-now   (gửi tin tóm tắt ngay để xem thử)
       ./run.sh alert --legacy   (báo tín hiệu y hệt bản gốc: không lọc ADF, SL 1.2σ/1.5σ)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quant_core import ai_advisor, market_context, settings  # noqa: E402
from quant_core.data import fetch_live_ohlcv  # noqa: E402
from quant_core.ft_client import FreqtradeClient  # noqa: E402
from quant_core.indicators import add_quant_indicators  # noqa: E402
from quant_core.risk import plan_position  # noqa: E402

ADF_THRESHOLD = 0.20
MODERATE_Z, STRONG_Z = 2.0, 2.5
MODERATE_GAP, STRONG_GAP = 1.5, 2.5

TAKER_FEE = 0.0005          # phí taker Binance Futures (giống bản gốc)
DEFAULT_MIN_NOTIONAL = 21.0  # dự phòng khi không đọc được từ sàn (giống bản gốc)

_last_sent: dict[str, float] = {}
_exchange = None


def min_notional(sym: str) -> float:
    """Giá trị lệnh tối thiểu của Binance Futures cho cặp `sym` (logic từ bản gốc)."""
    global _exchange
    try:
        if _exchange is None:
            import ccxt
            _exchange = ccxt.binance({"enableRateLimit": True, "timeout": 15000,
                                      "options": {"defaultType": "future"}})
            _exchange.load_markets()
        market = _exchange.market(sym)
        val = (market.get("limits", {}).get("cost") or {}).get("min")
        if val is None:
            for f in market.get("info", {}).get("filters", []):
                if f.get("filterType") == "MIN_NOTIONAL":
                    val = float(f.get("notional") or f.get("minNotional"))
                    break
        return float(val) if val else DEFAULT_MIN_NOTIONAL
    except Exception:
        return DEFAULT_MIN_NOTIONAL


def send_telegram(message: str) -> None:
    now_vn = datetime.now(market_context.VN_TZ).strftime("%H:%M:%S - %d/%m/%Y")
    full = f"{message}\n\n🕒 *Thời gian gửi:* `{now_vn}`"
    print(f"\n[🔔 BÁO ĐỘNG]\n{full}\n")
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        print("  (chưa cấu hình TELEGRAM_BOT_TOKEN trong .env -> chỉ in ra màn hình)")
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                          json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": full,
                                "parse_mode": "Markdown"}, timeout=10)
        if r.status_code != 200:  # Markdown lỗi -> gửi lại dạng thường
            requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                          json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": full}, timeout=10)
    except Exception as e:
        print(f"  [!] Gửi Telegram lỗi: {e}")


def freqtrade_context(sym: str) -> str:
    client = FreqtradeClient(timeout=3)
    if not client.ping():
        return ""
    try:
        for t in client.status():
            if t["pair"].split(":")[0] == sym:
                return (f"- Bot Freqtrade ĐANG GIỮ lệnh {sym} ({t.get('enter_tag')}), "
                        f"lãi/lỗ {t.get('profit_pct', 0):.2f}%")
        return f"- Bot Freqtrade đang chạy, chưa có lệnh {sym}"
    except Exception:
        return ""


def pick_signal(r, legacy: bool):
    """
    Trả về (chiến lược, is_long, strong, sl_mult, tp_mult, dùng_mean_làm_TP, đòn bẩy) hoặc None.

    legacy=False: bản nâng cấp — ADF chọn chế độ thị trường, SL 2σ (khớp QuantHybridStrategy).
    legacy=True : y hệt 4_alert_bot.py gốc — không lọc ADF, SL 1.2σ (MR) / 1.5σ (Trend).
    """
    z, gap, adf = r["z_score"], r["ema_gap_pct"], r["adf_p"]
    if legacy:
        moderate = abs(z) >= MODERATE_Z or abs(gap) >= MODERATE_GAP
        if not moderate:
            return None
        strong = abs(z) >= STRONG_Z or abs(gap) >= STRONG_GAP
        if abs(z) >= STRONG_Z:
            return ("🔄 MEAN REVERSION", z < 0, strong, 1.2, 0.0, True, 5 if abs(z) >= 3 else 2)
        return ("🚀 TREND FOLLOWING", r["ema_fast"] > r["ema_slow"], strong, 1.5, 2.5, False, 3)

    ranging = adf < ADF_THRESHOLD
    if ranging and abs(z) >= MODERATE_Z:
        return ("🔄 MEAN REVERSION", z < 0, abs(z) >= STRONG_Z, 2.0, 1.5, True, 5 if abs(z) >= 3 else 2)
    if not ranging and abs(gap) >= MODERATE_GAP:
        return ("🚀 TREND FOLLOWING", gap > 0, abs(gap) >= STRONG_GAP, 2.0, 3.0, False, 3)
    return None


# ------------------------------------------------------------------ hướng dẫn vào lệnh
def fmt_price(v: float) -> str:
    return f"${v:,.2f}" if v >= 10 else f"${v:,.4f}"


def fmt_qty(q: float) -> str:
    return f"{q:,.1f}" if q >= 100 else f"{q:,.3f}" if q >= 1 else f"{q:.5f}"


def move_pct(target: float, price: float) -> str:
    return f"{(target / price - 1) * 100:+.2f}%"


def spot_instructions(sym: str, price: float, plan, is_long: bool, capital: float) -> str:
    """Các bước vào lệnh Spot trên Binance (giống bản cũ: Market + OCO), kèm số coin và % SL/TP."""
    base = sym.split("/")[0]
    if not is_long:
        return ("📦 *SPOT:* không Short được → đứng ngoài.\n"
                f"   Nếu đang giữ {base}: cân nhắc chốt lời một phần quanh `{fmt_price(price)}`.\n")
    usd = plan.position_usd
    note = ""
    if usd > capital:  # khối lượng theo % rủi ro vượt quá vốn -> giới hạn bằng vốn
        stop = abs(price - plan.stop_loss) / price
        usd = capital
        note = (f"   ⚠️ Khối lượng lý tưởng vượt vốn → mua tối đa `${capital:,.0f}` "
                f"(lỗ tối đa còn `${capital * stop:,.2f}`)\n")
    return (f"📦 *SPOT — cách vào lệnh:*\n"
            f"1. Mua *Market* `{fmt_qty(usd / price)} {base}` (≈ `${usd:,.2f}`)\n"
            f"2. Ngay sau khi khớp, đặt lệnh *OCO* bán toàn bộ:\n"
            f"   • Chốt lời (TP): `{fmt_price(plan.take_profit)}` ({move_pct(plan.take_profit, price)})\n"
            f"   • Cắt lỗ (SL): `{fmt_price(plan.stop_loss)}` ({move_pct(plan.stop_loss, price)})\n"
            f"{note}")


def futures_instructions(sym: str, price: float, plan, fplan, is_long: bool, leverage: int,
                         margin: float, fee_2way: float, risk_note: str) -> str:
    """Các bước vào lệnh Futures (Isolated + đòn bẩy + TP/SL), kèm số coin, ký quỹ, lỗ tối đa, phí."""
    base = sym.split("/")[0]
    side = "LONG (Mua)" if is_long else "SHORT (Bán)"
    return (f"⚡ *FUTURES — cách vào lệnh:*\n"
            f"1. Chọn ký quỹ *Isolated*, đòn bẩy *x{leverage}*\n"
            f"2. Mở *{side}* Market `{fmt_qty(fplan.position_usd / price)} {base}` "
            f"(lệnh ≈ `${fplan.position_usd:,.2f}`, ký quỹ ≈ `${margin:,.2f}`)\n"
            f"3. Đặt TP/SL cho vị thế:\n"
            f"   • Chốt lời (TP): `{fmt_price(plan.take_profit)}` ({move_pct(plan.take_profit, price)})\n"
            f"   • Cắt lỗ (SL): `{fmt_price(plan.stop_loss)}` ({move_pct(plan.stop_loss, price)})\n"
            f"• Lỗ tối đa nếu chạm SL: `${fplan.risk_usd:,.2f}`{risk_note}\n"
            f"• Phí sàn 2 chiều (ước tính): ~`${fee_2way:,.4f}` · Tỷ lệ lời/lỗ 1:{plan.rr_ratio:.1f}\n")


def market_allows(is_long: bool, regime: dict | None) -> bool:
    """Giống các bot: thị trường giảm (BTC < SMA200 ngày) -> chỉ Short; thị trường tăng -> chỉ Long."""
    if regime is None:  # thiếu dữ liệu -> không chặn
        return True
    return regime["up"] == is_long


def regime_line(regime: dict | None) -> str:
    if regime is None:
        return ""
    if regime["up"]:
        return f"• Thị trường chung: BTC *trên* SMA200 ngày ({regime['gap']:+.1f}%) → chỉ báo Long\n"
    return f"• Thị trường chung: BTC *dưới* SMA200 ngày ({regime['gap']:+.1f}%) → chỉ báo Short (Futures)\n"


def scan(symbols: list[str], timeframe: str, window: int, cooldown_min: int,
         legacy: bool = False, use_market_filter: bool = True) -> tuple[dict | None, list[dict]]:
    """Quét 1 vòng. Trả về (thị trường chung, [trạng thái từng coin]) cho tin tóm tắt buổi sáng."""
    capital, risk_pct = settings.get_user_settings()
    regime = market_context.btc_regime() if use_market_filter else None
    mkt = ("" if regime is None else
           f" | Thị trường: BTC {'trên' if regime['up'] else 'dưới'} SMA200 ({regime['gap']:+.1f}%)")
    print(f"[{datetime.now():%H:%M:%S}] Quét thị trường | Vốn ${capital:,.2f} | Rủi ro {risk_pct}%"
          f"{' | chế độ GỐC (--legacy)' if legacy else ''}{mkt}")
    rows: list[dict] = []
    for sym in symbols:
        row = {"sym": sym, "status": "error"}
        rows.append(row)
        try:
            df = add_quant_indicators(fetch_live_ohlcv(sym, timeframe, limit=300, market_type="futures"),
                                      window=window)
            r = df.iloc[-1]
            price, z, gap, adf = r["close"], r["z_score"], r["ema_gap_pct"], r["adf_p"]
            min_not = min_notional(sym)
            print(f"  -> {sym}: ${price:,.2f} | Z={z:.2f}σ | EMA gap={gap:.2f}% | ADF={adf:.3f}"
                  f" | Min=${min_not:.1f}")
            back = 1440 // TF_MINUTES.get(timeframe, 60)
            chg = float(price / df["close"].iloc[-1 - back] - 1) * 100 if len(df) > back else None
            row.update(price=float(price), z=float(z), gap=float(gap), adf=float(adf), chg24=chg,
                       status="none", legacy=legacy)

            sig = pick_signal(r, legacy)
            if sig is None:
                continue
            strategy, is_long, strong, sl_mult, tp_mult, use_mean, leverage = sig
            row.update(side="LONG" if is_long else "SHORT", strategy=strategy)
            if not market_allows(is_long, regime):
                row["status"] = "blocked"
                print(f"     (tín hiệu {'LONG' if is_long else 'SHORT'} bị bộ lọc thị trường chặn, giống các bot)")
                continue
            mean = r["rolling_mean"] if use_mean else None
            # Spot: quy mô lý tưởng theo % rủi ro. Futures: bị sàn ép lên tối thiểu Min Notional.
            plan = plan_position(capital, risk_pct, price, r["rolling_std"], mean,
                                 is_long=is_long, sl_std_mult=sl_mult, tp_std_mult=tp_mult)
            fplan = plan_position(capital, risk_pct, price, r["rolling_std"], mean,
                                  is_long=is_long, sl_std_mult=sl_mult, tp_std_mult=tp_mult,
                                  min_notional=min_not)

            key = f"{sym}|{strategy}|{is_long}"
            if time.time() - _last_sent.get(key, 0) < cooldown_min * 60:
                row["status"] = "sent"
                print("     (đã báo gần đây, bỏ qua)")
                continue

            session = market_context.trading_session()
            sentiment = market_context.label_for(market_context.news_sentiment_score())
            ft_ctx = freqtrade_context(sym)
            ai = None
            if strong and ai_advisor.is_enabled():
                print(f"  🧠 Tín hiệu mạnh {sym}, gọi Gemini...")
                ai = ai_advisor.analyze(sym, timeframe, price, z, r["ema_fast"], r["ema_slow"],
                                        adf, session, sentiment, ft_ctx)
            ai = ai or "ℹ️ Chạy thuần toán học (tín hiệu trung bình hoặc AI không khả dụng)."

            side = "🟢 LONG" if is_long else "🔴 SHORT"
            margin = fplan.position_usd / leverage
            fee_2way = fplan.position_usd * TAKER_FEE * 2
            risk_note = ""
            if fplan.position_usd > plan.position_usd:
                risk_note = (f" (⚠️ Sàn ép lệnh Min ${min_not:.1f} -> "
                             f"rủi ro thực: ${fplan.risk_usd:.2f})")
            msg = (f"🤖 *QUANT × FREQTRADE: {sym}*\n\n"
                   f"🧠 *AI:*\n{ai}\n\n"
                   f"📊 *Chỉ số ({timeframe}):*\n"
                   f"• Chiến lược: *{strategy}* ({'mạnh' if strong else 'trung bình'})\n"
                   f"• Hướng: *{side}*\n"
                   f"• Giá: `${price:,.4f}` | Z: `{z:.2f}σ` | EMA gap: `{gap:.2f}%` | ADF: `{adf:.3f}`\n"
                   f"• Phiên: {session} | Tin tức: {sentiment}\n"
                   f"{regime_line(regime)}")
            if ft_ctx:
                msg += f"• {ft_ctx.lstrip('- ')}\n"
            msg += "\n" + spot_instructions(sym, price, plan, is_long, capital)
            msg += "\n" + futures_instructions(sym, price, plan, fplan, is_long, leverage, margin,
                                               fee_2way, risk_note)
            send_telegram(msg)
            _last_sent[key] = time.time()
            row["status"] = "sent"
            record_signal(sym, row["side"])
        except Exception as e:
            print(f"  [!] Lỗi {sym}: {e}")
    return regime, rows


# ------------------------------------------------------------------ tin tóm tắt buổi sáng
# Mỗi sáng (mặc định 8:00 giờ VN) gửi 1 tin tóm tắt CẢ 4 coin, kể cả khi không có tín hiệu: giá,
# % thay đổi 24h, coin đang đi ngang hay có xu hướng, còn cách điều kiện báo tín hiệu bao xa.
# Máy ngủ lúc 8:00 -> gửi ở lần quét đầu tiên sau đó (trước 12:00). Mỗi ngày chỉ gửi 1 lần (nhớ trong file).
STATE_FILE = ROOT / "logs" / "alert_state.json"
SUMMARY_LATEST_HOUR = 12
TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "1d": 1440}


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False))
    except Exception as e:
        print(f"  [!] Không ghi được {STATE_FILE.name}: {e}")


def record_signal(sym: str, side: str, now: float | None = None) -> None:
    """Ghi lại tín hiệu đã gửi (giữ 48 giờ) để tin tóm tắt đếm được '24 giờ qua đã báo mấy lần'."""
    now = time.time() if now is None else now
    state = load_state()
    state["sent"] = [x for x in state.get("sent", []) if now - x[0] < 48 * 3600] + [[now, sym, side]]
    save_state(state)


def summary_due(now_vn: datetime, state: dict, hour: int) -> bool:
    return hour >= 0 and hour <= now_vn.hour < max(hour + 1, SUMMARY_LATEST_HOUR) \
        and state.get("summary_date") != now_vn.strftime("%Y-%m-%d")


def coin_line(row: dict, regime: dict | None) -> str:
    """1 coin: giá, % 24h và còn cách điều kiện báo tín hiệu bao xa (nói bằng lời)."""
    base = row["sym"].split("/")[0]
    if row.get("status") == "error" or "z" not in row:
        return f"⚪ *{base}* — không lấy được dữ liệu lần quét này"
    chg = "" if row.get("chg24") is None else f" ({row['chg24']:+.1f}% 24h)"
    head = f"*{base}* `{fmt_price(row['price'])}`{chg}"
    z, gap, adf = row["z"], row["gap"], row["adf"]
    only = None if regime is None else ("LONG" if regime["up"] else "SHORT")
    if row["status"] == "sent":
        return f"🔔 {head}\n    Đang có tín hiệu *{row['side']}* ({row['strategy']}) — đã gửi riêng"
    if row["status"] == "blocked":
        return (f"⛔ {head}\n    Có tín hiệu {row['side']} nhưng bị bộ lọc thị trường chặn "
                f"(đang chỉ báo {only})")
    if row.get("legacy"):
        return f"⚪ {head}\n    Chưa có tín hiệu · Z `{z:+.2f}σ` · EMA gap `{gap:+.2f}%`"
    if adf < ADF_THRESHOLD:            # đi ngang -> chờ giá lệch xa trung bình (Mean Reversion)
        want = {"LONG": (f"Z ≤ −{MODERATE_Z:g}", -z), "SHORT": (f"Z ≥ +{MODERATE_Z:g}", z)}
        need, val = want[only] if only else (f"|Z| ≥ {MODERATE_Z:g}", abs(z))
        mode, now_txt = "Đi ngang", f"Z `{z:+.2f}σ`"
        lim = MODERATE_Z
    else:                               # có xu hướng -> chờ 2 đường EMA tách xa (Trend Following)
        want = {"LONG": (f"gap ≥ +{MODERATE_GAP:g}%", gap), "SHORT": (f"gap ≤ −{MODERATE_GAP:g}%", -gap)}
        need, val = want[only] if only else (f"|gap| ≥ {MODERATE_GAP:g}%", abs(gap))
        mode, now_txt = "Có xu hướng", f"EMA gap `{gap:+.2f}%`"
        lim = MODERATE_GAP
    icon = "🟡" if val >= 0.75 * lim else "⚪"
    near = "gần tới" if icon == "🟡" else "còn xa"
    side = f" để báo {only}" if only else ""
    return f"{icon} {head}\n    {mode} · {now_txt} → {near} (cần {need}{side})"


def build_summary(rows: list[dict], regime: dict | None, timeframe: str, sent: list,
                  now: float | None = None) -> str:
    now = time.time() if now is None else now
    lines = [f"☀️ *TÓM TẮT BUỔI SÁNG — {len(rows)} coin ({timeframe})*", ""]
    if regime is not None:
        lines.append(regime_line(regime).rstrip() + "\n")
    lines += [coin_line(r, regime) for r in rows]
    recent: dict[str, int] = {}
    for ts, sym, _ in sent:
        if now - ts < 24 * 3600:
            recent[sym.split("/")[0]] = recent.get(sym.split("/")[0], 0) + 1
    counts = " · ".join(f"{r['sym'].split('/')[0]} {recent.get(r['sym'].split('/')[0], 0)}" for r in rows)
    lines += ["", f"📨 Tín hiệu đã gửi 24 giờ qua: {counts}",
              "ℹ️ ⚪ còn xa · 🟡 gần tới · 🔔 có tín hiệu · ⛔ bị bộ lọc chặn. "
              "Không có tín hiệu = đứng ngoài, không cần làm gì."]
    return "\n".join(lines)


def maybe_send_summary(rows: list[dict], regime: dict | None, timeframe: str, hour: int,
                       force: bool = False) -> bool:
    state = load_state()
    now_vn = datetime.now(market_context.VN_TZ)
    if not force and not summary_due(now_vn, state, hour):
        return False
    send_telegram(build_summary(rows, regime, timeframe, state.get("sent", [])))
    state["summary_date"] = now_vn.strftime("%Y-%m-%d")
    save_state(state)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", default=["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"])
    ap.add_argument("--timeframe", default="1h")
    ap.add_argument("--window", type=int, default=50)
    ap.add_argument("--interval", type=int, default=300, help="giây giữa 2 lần quét")
    ap.add_argument("--cooldown", type=int, default=60, help="phút chờ trước khi báo lại cùng tín hiệu")
    ap.add_argument("--once", action="store_true", help="quét 1 lần rồi thoát")
    ap.add_argument("--legacy", action="store_true",
                    help="báo tín hiệu y hệt 4_alert_bot.py gốc (không lọc ADF)")
    ap.add_argument("--summary-hour", type=int, default=8,
                    help="giờ VN gửi tin tóm tắt 4 coin mỗi sáng (-1 = tắt)")
    ap.add_argument("--summary-now", action="store_true", help="quét 1 lần, gửi tin tóm tắt ngay rồi thoát")
    ap.add_argument("--no-market-filter", action="store_true",
                    help="bỏ bộ lọc thị trường (BTC so với SMA200 ngày) — mặc định theo config.json")
    args = ap.parse_args()
    use_filter = market_context.market_filter_enabled() and not args.no_market_filter

    print("=== QUANT ALERT BOT (Mean Reversion + Trend + ADF + Gemini + Freqtrade) ===")
    print(f"AI: {'BẬT (' + settings.GEMINI_MODEL + ')' if ai_advisor.is_enabled() else 'TẮT'} | "
          f"Telegram: {'BẬT' if settings.TELEGRAM_BOT_TOKEN else 'TẮT'} | "
          f"Bộ lọc thị trường: {'BẬT' if use_filter else 'TẮT'}")
    while True:
        regime, rows = scan(args.pairs, args.timeframe, args.window, args.cooldown, legacy=args.legacy,
                            use_market_filter=use_filter)
        if args.summary_now:
            maybe_send_summary(rows, regime, args.timeframe, args.summary_hour, force=True)
            break
        if args.once:
            break
        maybe_send_summary(rows, regime, args.timeframe, args.summary_hour)
        print(f"✅ Xong vòng quét. Nghỉ {args.interval}s...\n")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
