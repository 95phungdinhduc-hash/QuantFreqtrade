"""
Bot cảnh báo Telegram + Gemini AI — bản nâng cấp của QuantTradingSystem/4_alert_bot.py.

Thay đổi so với bản gốc:
  * Token/API key đọc từ .env (bản gốc ghi cứng trong code — rất nguy hiểm nếu lộ file)
  * Dùng chung chỉ báo với bot Freqtrade (quant_core) -> tín hiệu cảnh báo = tín hiệu bot
  * Thêm bộ lọc chế độ thị trường ADF (đi ngang -> Mean Reversion, xu hướng -> Trend)
  * Chống spam: cùng 1 tín hiệu chỉ gửi lại sau `cooldown` phút
  * Báo kèm trạng thái bot Freqtrade (nếu đang chạy): đang giữ lệnh cặp này hay không
  * SDK Gemini mới (google-genai). Không có key -> chạy thuần toán học

Chạy:  ./run.sh alert            (quét mỗi 5 phút)
       ./run.sh alert --once     (quét 1 lần rồi thoát — để thử)
       ./run.sh alert --legacy   (báo tín hiệu y hệt bản gốc: không lọc ADF, SL 1.2σ/1.5σ)
"""

from __future__ import annotations

import argparse
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
         legacy: bool = False, use_market_filter: bool = True) -> None:
    capital, risk_pct = settings.get_user_settings()
    regime = market_context.btc_regime() if use_market_filter else None
    mkt = ("" if regime is None else
           f" | Thị trường: BTC {'trên' if regime['up'] else 'dưới'} SMA200 ({regime['gap']:+.1f}%)")
    print(f"[{datetime.now():%H:%M:%S}] Quét thị trường | Vốn ${capital:,.2f} | Rủi ro {risk_pct}%"
          f"{' | chế độ GỐC (--legacy)' if legacy else ''}{mkt}")
    for sym in symbols:
        try:
            df = add_quant_indicators(fetch_live_ohlcv(sym, timeframe, limit=300, market_type="futures"),
                                      window=window)
            r = df.iloc[-1]
            price, z, gap, adf = r["close"], r["z_score"], r["ema_gap_pct"], r["adf_p"]
            min_not = min_notional(sym)
            print(f"  -> {sym}: ${price:,.2f} | Z={z:.2f}σ | EMA gap={gap:.2f}% | ADF={adf:.3f}"
                  f" | Min=${min_not:.1f}")

            sig = pick_signal(r, legacy)
            if sig is None:
                continue
            strategy, is_long, strong, sl_mult, tp_mult, use_mean, leverage = sig
            if not market_allows(is_long, regime):
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
            msg += "\n📦 *SPOT:* "
            msg += (f"mua `${plan.position_usd:,.2f}` — TP `${plan.take_profit:,.4f}` | "
                    f"SL `${plan.stop_loss:,.4f}`\n" if is_long else "không Short được, đứng ngoài.\n")
            msg += (f"⚡ *FUTURES:* x{leverage}, ký quỹ `${margin:,.2f}` "
                    f"(lệnh `${fplan.position_usd:,.2f}`)\n"
                    f"• Lỗ tối đa nếu chạm SL: `${fplan.risk_usd:,.2f}`{risk_note}\n"
                    f"• Phí sàn 2 chiều (ước tính): ~`${fee_2way:,.4f}`\n"
                    f"• TP `${plan.take_profit:,.4f}` | SL `${plan.stop_loss:,.4f}` | R:R 1:{plan.rr_ratio:.1f}")
            send_telegram(msg)
            _last_sent[key] = time.time()
        except Exception as e:
            print(f"  [!] Lỗi {sym}: {e}")


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
    ap.add_argument("--no-market-filter", action="store_true",
                    help="bỏ bộ lọc thị trường (BTC so với SMA200 ngày) — mặc định theo config.json")
    args = ap.parse_args()
    use_filter = market_context.market_filter_enabled() and not args.no_market_filter

    print("=== QUANT ALERT BOT (Mean Reversion + Trend + ADF + Gemini + Freqtrade) ===")
    print(f"AI: {'BẬT (' + settings.GEMINI_MODEL + ')' if ai_advisor.is_enabled() else 'TẮT'} | "
          f"Telegram: {'BẬT' if settings.TELEGRAM_BOT_TOKEN else 'TẮT'} | "
          f"Bộ lọc thị trường: {'BẬT' if use_filter else 'TẮT'}")
    while True:
        scan(args.pairs, args.timeframe, args.window, args.cooldown, legacy=args.legacy,
             use_market_filter=use_filter)
        if args.once:
            break
        print(f"✅ Xong vòng quét. Nghỉ {args.interval}s...\n")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
