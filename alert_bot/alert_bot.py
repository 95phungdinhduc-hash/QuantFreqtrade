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
  * Trả lời khi bạn nhắn: /tomtat /btc /eth /sol /bnb /coin XRP /lenh /trangthai /help

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


def send_telegram(message: str, tag: str = "🔔 BÁO ĐỘNG", log_full: bool = True) -> None:
    now_vn = datetime.now(market_context.VN_TZ).strftime("%H:%M:%S - %d/%m/%Y")
    full = f"{message}\n\n🕒 *Thời gian gửi:* `{now_vn}`"
    print(f"\n[{tag}]\n{full}\n" if log_full else f"  [{tag}] {message.splitlines()[0][:80]}")
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


def analyze(sym: str, timeframe: str, window: int, legacy: bool, regime: dict | None,
            capital: float, risk_pct: float) -> tuple[dict, dict | None]:
    """
    Tính chỉ báo 1 coin. Trả về (row cho tin tóm tắt, chi tiết tín hiệu hoặc None).
    KHÔNG gửi gì — scan() và lệnh /btc... cùng dùng hàm này.
    """
    for attempt in range(3):                   # mạng chập chờn (vd vừa mở máy) -> thử lại, sai tên coin thì thôi
        try:
            raw = fetch_live_ohlcv(sym, timeframe, limit=300, market_type="futures")
            break
        except Exception as e:
            if attempt == 2 or type(e).__name__ in ("BadSymbol", "BadRequest"):
                raise
            time.sleep(3 * (attempt + 1))
    df = add_quant_indicators(raw, window=window)
    r = df.iloc[-1]
    price, z, gap, adf = r["close"], r["z_score"], r["ema_gap_pct"], r["adf_p"]
    back = 1440 // TF_MINUTES.get(timeframe, 60)
    chg = float(price / df["close"].iloc[-1 - back] - 1) * 100 if len(df) > back else None
    row = {"sym": sym, "price": float(price), "z": float(z), "gap": float(gap), "adf": float(adf),
           "chg24": chg, "status": "none", "legacy": legacy, "min_notional": min_notional(sym)}
    sig = pick_signal(r, legacy)
    if sig is None:
        return row, None
    strategy, is_long, strong, sl_mult, tp_mult, use_mean, leverage = sig
    row.update(side="LONG" if is_long else "SHORT", strategy=strategy)
    if not market_allows(is_long, regime):
        row["status"] = "blocked"
        return row, None
    row["status"] = "signal"
    mean = r["rolling_mean"] if use_mean else None
    # Spot: quy mô lý tưởng theo % rủi ro. Futures: bị sàn ép lên tối thiểu Min Notional.
    plan = plan_position(capital, risk_pct, price, r["rolling_std"], mean,
                         is_long=is_long, sl_std_mult=sl_mult, tp_std_mult=tp_mult)
    fplan = plan_position(capital, risk_pct, price, r["rolling_std"], mean,
                          is_long=is_long, sl_std_mult=sl_mult, tp_std_mult=tp_mult,
                          min_notional=row["min_notional"])
    return row, {"r": r, "strategy": strategy, "is_long": is_long, "strong": strong, "leverage": leverage,
                 "plan": plan, "fplan": fplan, "capital": capital}


def signal_message(sym: str, timeframe: str, row: dict, d: dict, regime: dict | None,
                   ai: str | None, ft_ctx: str = "") -> str:
    """Tin tín hiệu đầy đủ (chỉ số + cách vào lệnh Spot/Futures)."""
    price, plan, fplan, is_long, leverage = row["price"], d["plan"], d["fplan"], d["is_long"], d["leverage"]
    session = market_context.trading_session()
    sentiment = market_context.label_for(market_context.news_sentiment_score())
    ai = ai or "ℹ️ Chạy thuần toán học (tín hiệu trung bình hoặc AI không khả dụng)."
    side = "🟢 LONG" if is_long else "🔴 SHORT"
    margin = fplan.position_usd / leverage
    fee_2way = fplan.position_usd * TAKER_FEE * 2
    risk_note = ""
    if fplan.position_usd > plan.position_usd:
        risk_note = (f" (⚠️ Sàn ép lệnh Min ${row['min_notional']:.1f} -> "
                     f"rủi ro thực: ${fplan.risk_usd:.2f})")
    msg = (f"🤖 *QUANT × FREQTRADE: {sym}*\n\n"
           f"🧠 *AI:*\n{ai}\n\n"
           f"📊 *Chỉ số ({timeframe}):*\n"
           f"• Chiến lược: *{d['strategy']}* ({'mạnh' if d['strong'] else 'trung bình'})\n"
           f"• Hướng: *{side}*\n"
           f"• Giá: `${price:,.4f}` | Z: `{row['z']:.2f}σ` | EMA gap: `{row['gap']:.2f}%` | ADF: `{row['adf']:.3f}`\n"
           f"• Phiên: {session} | Tin tức: {sentiment}\n"
           f"{regime_line(regime)}")
    if ft_ctx:
        msg += f"• {ft_ctx.lstrip('- ')}\n"
    msg += "\n" + spot_instructions(sym, price, plan, is_long, d["capital"])
    msg += "\n" + futures_instructions(sym, price, plan, fplan, is_long, leverage, margin, fee_2way, risk_note)
    return msg


def scan(symbols: list[str], timeframe: str, window: int, cooldown_min: int,
         legacy: bool = False, use_market_filter: bool = True) -> tuple[dict | None, list[dict]]:
    """Quét 1 vòng, gửi tín hiệu mới. Trả về (thị trường chung, [trạng thái từng coin]) cho tin tóm tắt."""
    capital, risk_pct = settings.get_user_settings()
    regime = market_context.btc_regime() if use_market_filter else None
    mkt = ("" if regime is None else
           f" | Thị trường: BTC {'trên' if regime['up'] else 'dưới'} SMA200 ({regime['gap']:+.1f}%)")
    print(f"[{datetime.now():%H:%M:%S}] Quét thị trường | Vốn ${capital:,.2f} | Rủi ro {risk_pct}%"
          f"{' | chế độ GỐC (--legacy)' if legacy else ''}{mkt}")
    rows: list[dict] = []
    for sym in symbols:
        try:
            row, d = analyze(sym, timeframe, window, legacy, regime, capital, risk_pct)
        except Exception as e:
            rows.append({"sym": sym, "status": "error"})
            print(f"  [!] Lỗi {sym}: {e}")
            continue
        rows.append(row)
        print(f"  -> {sym}: ${row['price']:,.2f} | Z={row['z']:.2f}σ | EMA gap={row['gap']:.2f}% | "
              f"ADF={row['adf']:.3f} | Min=${row['min_notional']:.1f}")
        if row["status"] == "blocked":
            print(f"     (tín hiệu {row['side']} bị bộ lọc thị trường chặn, giống các bot)")
        if d is None:
            continue
        try:
            row["status"] = "sent"
            key = f"{sym}|{d['strategy']}|{d['is_long']}"
            if time.time() - _last_sent.get(key, 0) < cooldown_min * 60:
                print("     (đã báo gần đây, bỏ qua)")
                continue
            ft_ctx = freqtrade_context(sym)
            ai = None
            if d["strong"] and ai_advisor.is_enabled():
                print(f"  🧠 Tín hiệu mạnh {sym}, gọi Gemini...")
                session = market_context.trading_session()
                sentiment = market_context.label_for(market_context.news_sentiment_score())
                ai = ai_advisor.analyze(sym, timeframe, row["price"], row["z"], d["r"]["ema_fast"],
                                        d["r"]["ema_slow"], row["adf"], session, sentiment, ft_ctx)
            send_telegram(signal_message(sym, timeframe, row, d, regime, ai, ft_ctx))
            _last_sent[key] = time.time()
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
    if row["status"] in ("sent", "signal"):
        note = "đã gửi riêng" if row["status"] == "sent" else f"gõ /{base.lower()} để xem cách vào lệnh"
        return f"🔔 {head}\n    Đang có tín hiệu *{row['side']}* ({row['strategy']}) — {note}"
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
                  now: float | None = None, title: str = "☀️ *TÓM TẮT BUỔI SÁNG") -> str:
    now = time.time() if now is None else now
    lines = [f"{title} — {len(rows)} coin ({timeframe})*", ""]
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


# ------------------------------------------------------------------ trả lời lệnh trên Telegram
# Bot vừa TỰ GỬI (tín hiệu + tóm tắt sáng) vừa TRẢ LỜI khi bạn nhắn. Chỉ trả lời đúng chat của bạn
# (TELEGRAM_CHAT_ID trong .env) — người lạ nhắn vào bot sẽ bị bỏ qua. Trả lời theo lệnh KHÔNG gọi Gemini
# (tiết kiệm hạn mức) và KHÔNG tính là "đã báo" (không ảnh hưởng tín hiệu tự gửi).
COMMANDS = [
    ("tomtat", "Tóm tắt 4 coin ngay bây giờ"),
    ("btc", "Phân tích BTC (có cách vào lệnh nếu đang có tín hiệu)"),
    ("eth", "Phân tích ETH"),
    ("sol", "Phân tích SOL"),
    ("bnb", "Phân tích BNB"),
    ("coin", "Phân tích coin khác, ví dụ: /coin XRP"),
    ("lenh", "Lệnh đang mở của 4 bot tiền ảo"),
    ("trangthai", "Alert bot và các bot có đang chạy không"),
    ("help", "Danh sách lệnh"),
]
BOT_NAMES = {"hybrid": "Hybrid", "breakout": "Breakout", "dca": "Smart DCA", "futures": "Futures"}
STATUS: dict = {"started": time.time(), "last_scan": None, "regime": None}


def help_text(pairs: list[str]) -> str:
    coins = " ".join(f"/{p.split('/')[0].lower()}" for p in pairs)
    return ("🤖 *Lệnh của alert bot*\n\n"
            "/tomtat — tóm tắt 4 coin ngay bây giờ\n"
            f"{coins} — phân tích 1 coin (có cách vào lệnh nếu đang có tín hiệu)\n"
            "/coin XRP — phân tích coin khác\n"
            "/lenh — lệnh đang mở của 4 bot tiền ảo\n"
            "/trangthai — các bot có đang chạy không\n\n"
            "Bot vẫn tự gửi tín hiệu khi có và tin tóm tắt mỗi sáng 8:00. "
            "Có thể gõ không dấu gạch: `btc`, `tomtat`.")


def coin_reply(sym: str, cfg: dict) -> str:
    capital, risk_pct = settings.get_user_settings()
    regime = market_context.btc_regime() if cfg["use_filter"] else None
    try:
        row, d = analyze(sym, cfg["timeframe"], cfg["window"], cfg["legacy"], regime, capital, risk_pct)
    except Exception as e:
        if type(e).__name__ in ("BadSymbol", "BadRequest") or "does not have market symbol" in str(e):
            return f"⚠️ Không lấy được dữ liệu {sym}: Binance Futures không có coin này. Kiểm tra lại tên coin."
        return f"⚠️ Không lấy được dữ liệu {sym} ({type(e).__name__} — mạng/Binance chập chờn). Thử lại sau ít phút."
    if d is not None:
        return signal_message(sym, cfg["timeframe"], row, d, regime,
                              "ℹ️ Trả lời theo lệnh: chạy thuần toán học (không gọi AI).", freqtrade_context(sym))
    out = [f"🔎 *{sym} ({cfg['timeframe']})*", "", coin_line(row, regime), "",
           f"• Z `{row['z']:+.2f}σ` · EMA gap `{row['gap']:+.2f}%` · ADF `{row['adf']:.3f}`"
           f" ({'đi ngang' if row['adf'] < ADF_THRESHOLD else 'có xu hướng'})"]
    if regime is not None:
        out.append(regime_line(regime).rstrip())
    out.append("\nChưa có tín hiệu → đứng ngoài, không cần làm gì.")
    return "\n".join(out)


def summary_reply(cfg: dict) -> str:
    capital, risk_pct = settings.get_user_settings()
    regime = market_context.btc_regime() if cfg["use_filter"] else None
    rows = []
    for sym in cfg["pairs"]:
        try:
            rows.append(analyze(sym, cfg["timeframe"], cfg["window"], cfg["legacy"], regime, capital, risk_pct)[0])
        except Exception:
            rows.append({"sym": sym, "status": "error"})
    return build_summary(rows, regime, cfg["timeframe"], load_state().get("sent", []), title="📋 *TÓM TẮT")


def _pid_alive(name: str) -> bool:
    import os
    try:
        os.kill(int((ROOT / "logs" / f"{name}.pid").read_text().strip()), 0)
        return True
    except Exception:
        return False


def open_trades() -> list[dict]:
    """Lệnh đang mở (tiền ảo) của các bot, đọc thẳng database (chỉ đọc)."""
    import sqlite3

    from quant_core.strategy_common import portfolio_dbs

    out = []
    for f in portfolio_dbs(True):
        bot = next((v for k, v in BOT_NAMES.items() if f".{k}." in f.name), f.name)
        try:
            con = sqlite3.connect(f"file:{f}?mode=ro", uri=True, timeout=2)
            try:
                rows = con.execute("SELECT pair, is_short, open_rate, open_date, stake_amount, leverage "
                                   "FROM trades WHERE is_open = 1 ORDER BY open_date").fetchall()
            finally:
                con.close()
        except Exception:
            continue
        out += [{"bot": bot, "pair": p, "short": bool(sh), "open": float(o), "date": str(dt)[:16],
                 "stake": float(st or 0), "lev": float(lv or 1)} for p, sh, o, dt, st, lv in rows]
    return out


def trades_reply() -> str:
    trades = open_trades()
    if not trades:
        return ("📭 *Không có lệnh nào đang mở* (4 bot tiền ảo).\n"
                "Bot chỉ vào lệnh khi đủ điều kiện — thị trường giảm thì bot Spot đứng ngoài là bình thường.")
    lines = [f"📂 *Lệnh đang mở — {len(trades)} lệnh (tiền ảo)*", ""]
    for t in trades:
        futures = ":" in t["pair"]
        side = "🔴 SHORT" if t["short"] else "🟢 LONG"
        try:
            cur = float(fetch_live_ohlcv(t["pair"].split(":")[0], "1m", limit=2,
                                         market_type="futures" if futures else "spot")["close"].iloc[-1])
            pnl = (cur / t["open"] - 1) * (-1 if t["short"] else 1) * t["lev"] * 100
            now = f" → `{fmt_price(cur)}` · {'🟢' if pnl >= 0 else '🔴'} `{pnl:+.2f}%`"
        except Exception:
            now = ""
        lev = f" x{t['lev']:g}" if futures else ""
        lines.append(f"• *{t['bot']}* {t['pair'].split(':')[0]} {side}{lev}\n"
                     f"    Vào `{fmt_price(t['open'])}`{now} · {t['stake']:.2f} USDT · từ {t['date']} UTC")
    return "\n".join(lines)


def status_reply(cfg: dict) -> str:
    now = time.time()
    vn = lambda ts: datetime.fromtimestamp(ts, market_context.VN_TZ).strftime("%H:%M %d/%m")  # noqa: E731
    last = STATUS.get("last_scan")
    lines = ["🩺 *Trạng thái*", "",
             f"• Alert bot: 🟢 chạy từ {vn(STATUS['started'])}" +
             (f", quét gần nhất {vn(last)} ({(now - last) / 60:.0f} phút trước)" if last else ", đang quét lần đầu")]
    if STATUS.get("regime") is not None:
        lines.append(regime_line(STATUS["regime"]).rstrip())
    state = load_state()
    today = datetime.now(market_context.VN_TZ).strftime("%Y-%m-%d")
    if cfg["summary_hour"] >= 0:
        lines.append(f"• Tóm tắt sáng {cfg['summary_hour']}:00: "
                     f"{'đã gửi hôm nay' if state.get('summary_date') == today else 'hôm nay chưa gửi'}")
    n24 = sum(1 for x in state.get("sent", []) if now - x[0] < 24 * 3600)
    lines.append(f"• Tín hiệu đã gửi 24 giờ qua: {n24}")
    counts: dict[str, int] = {}
    for t in open_trades():
        counts[t["bot"]] = counts.get(t["bot"], 0) + 1
    lines.append("\n*Bot tiền ảo (dry-run):*")
    for key, name in BOT_NAMES.items():
        lines.append(f"• {name}: {'🟢 đang chạy' if _pid_alive(key) else '⚪ tắt'} · {counts.get(name, 0)} lệnh mở")
    lines.append(f"• Dashboard: {'🟢 đang chạy' if _pid_alive('dashboard') else '⚪ tắt'}")
    return "\n".join(lines)


def handle_command(text: str, cfg: dict) -> str | None:
    """Tin nhắn của bạn -> câu trả lời (None = bỏ qua)."""
    words = text.strip().split()
    if not words:
        return None
    cmd = words[0].lstrip("/").split("@")[0].lower()
    arg = words[1] if len(words) > 1 else ""
    cmd = {"start": "help", "lenhs": "lenh", "tóm": "tomtat", "status": "trangthai"}.get(cmd, cmd)
    coins = {p.split("/")[0].lower(): p for p in cfg["pairs"]}
    if cmd == "help":
        return help_text(cfg["pairs"])
    if cmd == "tomtat":
        return summary_reply(cfg)
    if cmd == "lenh":
        return trades_reply()
    if cmd == "trangthai":
        return status_reply(cfg)
    if cmd in coins:
        return coin_reply(coins[cmd], cfg)
    if cmd == "coin":
        base = "".join(ch for ch in arg.upper() if ch.isalnum()).removesuffix("USDT")
        return coin_reply(f"{base}/USDT", cfg) if base else "Gõ kèm tên coin, ví dụ: `/coin XRP`"
    return "Mình chưa hiểu lệnh này.\n\n" + help_text(cfg["pairs"])


def tg_api(method: str, http_timeout: float = 15, **params) -> dict:
    r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
                      json=params, timeout=http_timeout)
    if r.status_code == 409:
        raise RuntimeError("409")
    r.raise_for_status()
    return r.json()


def listen_commands(cfg: dict, max_age: int = 600) -> None:
    """Chạy nền: đọc tin nhắn mới (long polling) và trả lời. Tin cũ hơn `max_age` giây bị bỏ qua."""
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return
    try:
        tg_api("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
    except Exception as e:
        print(f"  [!] Không cài được menu lệnh Telegram: {e}")
    offset, warned = None, 0.0
    while True:
        try:
            res = tg_api("getUpdates", http_timeout=40, offset=offset, timeout=30, allowed_updates=["message"])
        except Exception as e:
            if time.time() - warned > 1800:      # mất mạng / token đang bị chương trình khác đọc -> báo 30 phút/lần
                hint = (" (token đang bị chương trình khác đọc tin — vd bot Hybrid bật Telegram)"
                        if str(e) == "409" else "")
                print(f"  [!] Không đọc được tin nhắn Telegram: {e}{hint}")
                warned = time.time()
            time.sleep(15)
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if str((m.get("chat") or {}).get("id")) != str(settings.TELEGRAM_CHAT_ID):
                continue                         # người lạ -> bỏ qua
            if time.time() - m.get("date", 0) > max_age or not m.get("text"):
                continue
            print(f"[{datetime.now():%H:%M:%S}] 💬 Lệnh: {m['text'][:40]}")
            try:
                tg_api("sendChatAction", chat_id=settings.TELEGRAM_CHAT_ID, action="typing")
                reply = handle_command(m["text"], cfg)
            except Exception as e:
                reply = f"⚠️ Lỗi khi xử lý lệnh: {type(e).__name__}"
            if reply:
                send_telegram(reply, tag="💬 TRẢ LỜI", log_full=False)


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
    ap.add_argument("--no-commands", action="store_true", help="không nghe/trả lời tin nhắn Telegram")
    ap.add_argument("--no-market-filter", action="store_true",
                    help="bỏ bộ lọc thị trường (BTC so với SMA200 ngày) — mặc định theo config.json")
    args = ap.parse_args()
    use_filter = market_context.market_filter_enabled() and not args.no_market_filter

    print("=== QUANT ALERT BOT (Mean Reversion + Trend + ADF + Gemini + Freqtrade) ===")
    print(f"AI: {'BẬT (' + settings.GEMINI_MODEL + ')' if ai_advisor.is_enabled() else 'TẮT'} | "
          f"Telegram: {'BẬT' if settings.TELEGRAM_BOT_TOKEN else 'TẮT'} | "
          f"Bộ lọc thị trường: {'BẬT' if use_filter else 'TẮT'}")
    cfg = {"pairs": args.pairs, "timeframe": args.timeframe, "window": args.window, "legacy": args.legacy,
           "use_filter": use_filter, "summary_hour": args.summary_hour}
    if not (args.once or args.summary_now or args.no_commands):
        import threading
        threading.Thread(target=listen_commands, args=(cfg,), daemon=True).start()
        print("💬 Đang nghe lệnh Telegram: /help /tomtat /btc /eth /sol /bnb /coin /lenh /trangthai")
    while True:
        regime, rows = scan(args.pairs, args.timeframe, args.window, args.cooldown, legacy=args.legacy,
                            use_market_filter=use_filter)
        if args.summary_now:
            maybe_send_summary(rows, regime, args.timeframe, args.summary_hour, force=True)
            break
        if args.once:
            break
        STATUS.update(last_scan=time.time(), regime=regime)
        maybe_send_summary(rows, regime, args.timeframe, args.summary_hour)
        print(f"✅ Xong vòng quét. Nghỉ {args.interval}s...\n")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
