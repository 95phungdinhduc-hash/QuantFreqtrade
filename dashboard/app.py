"""
Dashboard Streamlit — Lil_Duck Quant × Freqtrade.

Kế thừa 2_dashboard.py của QuantTradingSystem, nâng cấp:
  * Trang "Tổng quan": giá trực tiếp Binance, tín hiệu hệ thống từng coin, trạng thái bot, kết quả backtest
  * Đọc chung dữ liệu với Freqtrade (user_data/data/binance)
  * Screener nhận diện chế độ thị trường giống hệt chiến lược QuantHybridStrategy
  * Cài đặt Vốn/Rủi ro được bot Freqtrade dùng thật để tính khối lượng lệnh
  * Tab "Bot Freqtrade": theo dõi bot đang chạy qua REST API
  * Tab "Backtest": so sánh chiến lược, đường cong vốn, Kelly từ lệnh thật

Giao diện (màu, CSS, biểu đồ) nằm trong dashboard/ui.py.
Chạy:  ./run.sh dashboard   (http://localhost:8502)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ui  # noqa: E402
from quant_core import advisor, ai_advisor, market_context, settings  # noqa: E402
from quant_core.data import fetch_live_ohlcv, list_datasets, load_ohlcv  # noqa: E402
from quant_core.ft_client import FreqtradeClient  # noqa: E402
from quant_core.indicators import add_quant_indicators, adf_pvalue  # noqa: E402
from quant_core.risk import half_kelly, plan_position, value_at_risk  # noqa: E402

# Ngưỡng mặc định — giống QuantHybridStrategy
ADF_THRESHOLD = 0.20
Z_ENTRY = 2.0
TREND_GAP = 1.0

st.set_page_config(page_title="Lil_Duck Quant · Freqtrade", page_icon="🦆", layout="wide",
                   initial_sidebar_state="auto")  # auto: máy tính mở sẵn, điện thoại tự thu gọn
ui.inject_css()
ui.setup_plotly()
H = ui.html_block


# ==========================================================================================
# DỮ LIỆU
# ==========================================================================================
@st.cache_data(ttl=300, show_spinner="Đang tính chỉ báo...")
def load_with_indicators(pair: str, tf: str, window: int, mtime: float) -> pd.DataFrame:
    # Dashboard chỉ cần ~5000 nến gần nhất (1h ≈ 7 tháng). Backtest vẫn dùng toàn bộ dữ liệu.
    # Không cắt thì 2 năm nến 15m (70.000 nến) khiến ADF tính rất lâu.
    df = load_ohlcv(pair, tf).tail(5000).reset_index(drop=True)
    if df.empty:
        return df
    df = add_quant_indicators(df, window=window)
    df["return"] = df["close"].pct_change()
    return df.dropna(subset=["z_score"]).reset_index(drop=True)


def file_mtime(pair: str, tf: str) -> float:
    p = settings.FT_DATA_DIR / f"{pair.replace('/', '_')}-{tf}.feather"
    return p.stat().st_mtime if p.exists() else 0.0


def whitelist() -> list[str]:
    try:
        return json.loads((settings.USER_DATA / "config.json").read_text())["exchange"]["pair_whitelist"]
    except Exception:
        return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]


@st.cache_data(ttl=60, show_spinner=False)
def live_tickers(pairs: tuple[str, ...]) -> dict[str, dict]:
    """Giá trực tiếp + % thay đổi 24h từ Binance (cache 60 giây)."""
    try:
        import ccxt
        raw = ccxt.binance({"enableRateLimit": True, "timeout": 10000}).fetch_tickers(list(pairs))
    except Exception:
        return {}
    return {p: {"last": raw[p].get("last"), "pct": raw[p].get("percentage"),
                "high": raw[p].get("high"), "low": raw[p].get("low"), "qvol": raw[p].get("quoteVolume")}
            for p in pairs if p in raw}


@st.cache_data(ttl=300, show_spinner=False)
def market_frame(pair: str, window: int) -> tuple[pd.DataFrame, str]:
    """Nến 1h ĐÃ ĐÓNG + chỉ báo (giống bot). Ưu tiên Binance trực tiếp, mất mạng thì dùng dữ liệu đã tải."""
    try:
        df, src = fetch_live_ohlcv(pair, "1h", limit=400).iloc[:-1], "live"
    except Exception:
        df, src = load_ohlcv(pair, "1h"), "local"
    if df.empty:
        return df, src
    return add_quant_indicators(df.reset_index(drop=True), window=window), src


@st.cache_data(ttl=900, show_spinner=False)
def market_regime() -> dict | None:
    """Bộ lọc thị trường của bot: BTC đóng cửa ngày (nến đã đóng) so với SMA200 ngày."""
    try:
        d = fetch_live_ohlcv("BTC/USDT", "1d", limit=260).iloc[:-1]
    except Exception:
        d = load_ohlcv("BTC/USDT", "1d")
    if d is None or len(d) < 200:
        return None
    close, sma = float(d["close"].iloc[-1]), float(d["close"].rolling(200).mean().iloc[-1])
    return {"close": close, "sma": sma, "up": close > sma, "gap": (close / sma - 1) * 100,
            "date": d["date"].iloc[-1]}


def market_filter_enabled() -> bool:
    try:
        return bool(json.loads((settings.USER_DATA / "config.json").read_text())
                    .get("quant", {}).get("market_filter", True))
    except Exception:
        return True


@st.cache_data(ttl=20, show_spinner=False)
def bot_snapshot(url: str) -> dict | None:
    client = FreqtradeClient(url=url, timeout=3)
    if not client.ping():
        return None
    try:
        return {"cfg": client.show_config(), "profit": client.profit(), "open": client.status()}
    except Exception as e:
        auth = "401" in str(e) or "403" in str(e)
        return {"error": str(e), "auth": auth}


def latest_backtest(strategy: str = "QuantHybridStrategy") -> Path | None:
    """File backtest mới nhất có chiến lược `strategy` (mặc định Hybrid -> bỏ qua kết quả futures)."""
    bt_dir = settings.USER_DATA / "backtest_results"
    for meta in sorted(bt_dir.glob("*.meta.json"), reverse=True):
        try:
            if strategy in json.loads(meta.read_text()):
                return meta.with_name(meta.name.replace(".meta.json", ".zip"))
        except Exception:
            continue
    return None


@st.cache_data(ttl=600, show_spinner=False)
def backtest_summary(filename: str) -> dict:
    from freqtrade.data.btanalysis import load_backtest_stats

    stats = load_backtest_stats(settings.USER_DATA / "backtest_results", filename=filename)
    out = {"rows": [], "market": None, "start": None, "end": None}
    for name, s in stats.get("strategy", {}).items():
        trades = s.get("total_trades", 0) or 0
        out["rows"].append({"name": name, "profit": s.get("profit_total", 0) * 100,
                            "dd": (s.get("max_drawdown_account") or 0) * 100, "trades": trades,
                            "win": (s.get("wins", 0) / trades * 100) if trades else 0.0})
        out["market"] = s.get("market_change", 0) * 100
        out["start"], out["end"] = s.get("backtest_start"), s.get("backtest_end")
    return out


def run_download(pairs: list[str], timeframes: list[str], days: int) -> tuple[bool, str]:
    """Tải dữ liệu bằng chính Freqtrade (tự nối tiếp dữ liệu cũ)."""
    cmd = [str(ROOT / ".venv/bin/freqtrade"), "download-data", "-c", "user_data/config.json",
           "--days", str(days), "-p", *pairs, "-t", *timeframes]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=os.environ.copy())
    return res.returncode == 0, (res.stdout + res.stderr)[-3000:]


# ==========================================================================================
# LOGIC TÍN HIỆU (đồng bộ với QuantHybridStrategy)
# ==========================================================================================
def regime_signal(row: pd.Series) -> str:
    z, adf, gap = row["z_score"], row["adf_p"], row["ema_gap_pct"]
    if pd.notna(adf) and adf < ADF_THRESHOLD:
        if z <= -Z_ENTRY:
            return "🟢 MUA — Mean Reversion (đi ngang + quá bán)"
        if z >= Z_ENTRY:
            return "🔴 BÁN/SHORT — Mean Reversion (đi ngang + quá mua)"
        return "⚪ Đi ngang — chờ Z-Score chạm ±2"
    if gap > TREND_GAP:
        return "🚀 Xu hướng TĂNG — ưu tiên Long"
    if gap < -TREND_GAP:
        return "🔻 Xu hướng GIẢM — đứng ngoài Spot / Short Futures"
    return "⚪ Đứng ngoài — chưa rõ xu hướng"


def signal_of(r: pd.Series) -> dict:
    """Tín hiệu dạng thẻ cho trang Tổng quan."""
    z, adf, gap = float(r["z_score"]), float(r["adf_p"]), float(r["ema_gap_pct"])
    if np.isfinite(adf) and adf < ADF_THRESHOLD:
        base = dict(strat="Mean Reversion · thị trường đi ngang", mr=True)
        if z <= -Z_ENTRY:
            return {**base, "kind": "long", "label": "Long", "act": True, "is_long": True,
                    "why": f"Giá đang <b>quá bán</b> (Z = {z:+.2f}σ) trong vùng đi ngang (ADF {adf:.2f}) "
                           f"→ kỳ vọng hồi về trung bình."}
        if z >= Z_ENTRY:
            return {**base, "kind": "short", "label": "Short", "act": True, "is_long": False,
                    "why": f"Giá đang <b>quá mua</b> (Z = {z:+.2f}σ) trong vùng đi ngang "
                           f"→ Spot: cân nhắc chốt lời · Futures: Short."}
        return {**base, "kind": "wait", "label": "Chờ", "act": False, "progress": abs(z) / Z_ENTRY,
                "need": f"Z cần chạm ±{Z_ENTRY:.1f}σ", "now": f"hiện {z:+.2f}σ",
                "why": f"Thị trường <b>đi ngang</b> (ADF {adf:.2f}). Chờ giá lệch đủ xa khỏi trung bình."}
    base = dict(strat="Trend Following · thị trường có xu hướng", mr=False)
    if gap > TREND_GAP:
        return {**base, "kind": "long", "label": "Xu hướng tăng", "act": True, "is_long": True,
                "why": f"EMA20 cao hơn EMA50 <b>{gap:.2f}%</b> → đánh thuận xu hướng tăng."}
    if gap < -TREND_GAP:
        return {**base, "kind": "short", "label": "Xu hướng giảm", "act": True, "is_long": False,
                "why": f"EMA20 thấp hơn EMA50 <b>{abs(gap):.2f}%</b> → đứng ngoài Spot, Futures có thể Short."}
    return {**base, "kind": "wait", "label": "Đứng ngoài", "act": False, "progress": abs(gap) / TREND_GAP,
            "need": f"EMA lệch cần ±{TREND_GAP:.1f}%", "now": f"hiện {gap:+.2f}%",
            "why": f"Có xu hướng (ADF {adf:.2f}) nhưng EMA20/50 chưa tách ra đủ rõ."}


def signal_markers(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Điểm vào lệnh Mean Reversion trong quá khứ (xác nhận đảo chiều, giống chiến lược)."""
    ranging = df["adf_p"] < ADF_THRESHOLD
    z, zp = df["z_score"], df["z_score"].shift(1)
    return (ranging & (zp < -Z_ENTRY) & (z > zp)), (ranging & (zp > Z_ENTRY) & (z < zp))


# ==========================================================================================
# SIDEBAR
# ==========================================================================================
datasets = list_datasets()

with st.sidebar:
    H("""<div class="side-brand"><div class="logo">🦆</div>
         <div><b>Lil_Duck Quant</b><small>Thống kê × Freqtrade</small></div></div>""")
    H('<div class="side-label">Thiết lập phân tích</div>')
    if datasets:
        labels = [f"{p} · {tf}" for p, tf in datasets]
        default_label = "BTC/USDT · 1h"
        choice = st.selectbox("Tài sản", labels,
                              index=labels.index(default_label) if default_label in labels else 0)
        pair, tf = datasets[labels.index(choice)]
    else:
        pair, tf = "BTC/USDT", "1h"
    window = st.slider("Chu kỳ Z-Score (nến)", 10, 200, 50)

    H('<div class="side-label">Dữ liệu (dùng chung với Freqtrade)</div>')
    with st.form("download_form", border=True):
        sym = st.multiselect("Cặp coin", ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
                                         "ADA/USDT"], default=["BTC/USDT"])
        tfs = st.multiselect("Khung thời gian", ["15m", "1h", "4h", "1d"], default=["1h", "4h"])
        days = st.number_input("Số ngày", 30, 1500, 365, step=30)
        if st.form_submit_button("⬇️  Tải / cập nhật từ Binance", type="primary", width="stretch") \
                and sym and tfs:
            with st.spinner("Freqtrade đang tải dữ liệu..."):
                ok, log = run_download(sym, tfs, int(days))
            (st.success if ok else st.error)("Đã tải xong" if ok else "Lỗi tải dữ liệu")
            if not ok:
                st.code(log)
            st.cache_data.clear()

    H('<div class="side-label">Lối tắt</div>')
    st.link_button("🖥️  Mở FreqUI (bot Spot)", "http://127.0.0.1:8080", width="stretch")
    st.link_button("⚡  Mở FreqUI (bot Futures)", "http://127.0.0.1:8081", width="stretch")
    st.caption("Bot cần đang chạy: `./run.sh dryrun` hoặc `./run.sh dryrun-futures`.")

if not datasets:
    ui.empty_state("📭", "Chưa có dữ liệu",
                   "Bấm <b>Tải / cập nhật từ Binance</b> ở thanh bên trái, hoặc chuyển dữ liệu cũ sang:",
                   "./run.sh import")
    st.stop()

df = load_with_indicators(pair, tf, window, file_mtime(pair, tf))
if df.empty:
    st.error("Dữ liệu trống.")
    st.stop()

capital, risk_pct = settings.get_user_settings()
t_home, t_adv, t_an, t_scr, t_risk, t_news, t_bot, t_bt = st.tabs([
    "🏠 Tổng quan", "🧭 Tư vấn", "📈 Phân tích", "🎯 Screener", "🛡️ Vốn & Rủi ro", "📰 Tin tức",
    "🤖 Bot Freqtrade", "📊 Backtest"])


# ==========================================================================================
# TAB 0 — TỔNG QUAN
# ==========================================================================================
def render_hero(pairs: list[str], snap: dict | None, bt: dict | None, sentiment: str) -> None:
    if snap and "cfg" in snap:
        cfg = snap["cfg"]
        bot_pill = (f'<span class="pill"><span class="dot on"></span>Bot đang chạy · '
                    f'{"DRY-RUN" if cfg.get("dry_run") else "LIVE"} · {ui.esc(str(cfg.get("trading_mode")))}</span>')
    elif snap:
        bot_pill = ('<span class="pill"><span class="dot warn"></span>'
                    + ("Bot chạy nhưng sai mật khẩu API" if snap.get("auth") else "Bot đang khởi động…")
                    + '</span>')
    else:
        bot_pill = '<span class="pill"><span class="dot off"></span>Bot chưa chạy</span>'
    session = market_context.trading_session()
    mr = market_regime() if market_filter_enabled() else None
    mkt_pill = "" if mr is None else (
        f'<span class="pill"><span class="dot {"on" if mr["up"] else "off"}"></span>'
        f'BTC {"trên" if mr["up"] else "dưới"} SMA200 ngày ({mr["gap"]:+.1f}%) · '
        f'{"bot được mở Long" if mr["up"] else "bot đứng ngoài lệnh Long"}</span>')
    hybrid = next((r for r in (bt or {}).get("rows", []) if r["name"] == "QuantHybridStrategy"), None)
    dd_stat = (f'<div class="v">{hybrid["dd"]:.1f}%</div><div class="s">sụt vốn tối đa khi backtest</div>'
               if hybrid else '<div class="v">—</div><div class="s">chạy ./run.sh backtest</div>')
    H(f"""
    <div class="hero">
      <div>
        <div class="eyebrow">● Hệ thống giao dịch định lượng · Freqtrade 2026</div>
        <h1>Giao dịch crypto bằng <span class="grad">thống kê</span>,<br>không bằng cảm xúc.</h1>
        <p class="lead">Hệ thống tự nhận diện thị trường đang <b>đi ngang</b> hay <b>có xu hướng</b> (kiểm định ADF),
        chọn đúng chiến lược — Mean Reversion hoặc Trend Following — rồi tính khối lượng lệnh theo
        <b>% rủi ro</b> bạn đặt. Mọi tín hiệu đều kiểm chứng được bằng backtest.</p>
        <div class="pills">{bot_pill}
          <span class="pill">🕒 {ui.esc(session)}</span>
          <span class="pill">📰 Tin tức: {ui.esc(sentiment)}</span>{mkt_pill}</div>
        <div class="cta">
          <a class="btn primary" href="#tin-hieu">Xem tín hiệu hôm nay ↓</a>
          <a class="btn ghost" href="http://127.0.0.1:8080" target="_blank">Mở bot FreqUI ↗</a>
        </div>
      </div>
      <div class="hero-stats">
        <div class="hstat"><div class="k">Theo dõi</div><div class="v">{len(pairs)} cặp</div>
          <div class="s">{ui.esc(" · ".join(p.split("/")[0] for p in pairs))}</div></div>
        <div class="hstat"><div class="k">Rủi ro mỗi lệnh</div><div class="v">{risk_pct:.1f}%</div>
          <div class="s">≈ ${capital * risk_pct / 100:,.2f} trên vốn ${capital:,.0f}</div></div>
        <div class="hstat"><div class="k">Chiến lược</div><div class="v">5 bot</div>
          <div class="s">Hồi quy · Xu hướng · Breakout · DCA · Futures</div></div>
        <div class="hstat"><div class="k">Kiểm soát rủi ro</div>{dd_stat}</div>
      </div>
    </div>""")


def render_tickers(pairs: list[str], frames: dict, tick: dict) -> None:
    cards = []
    for p in pairs:
        d, _ = frames[p]
        t = tick.get(p, {})
        if d.empty and not t:
            continue
        last = t.get("last") or (float(d["close"].iloc[-1]) if not d.empty else None)
        pct = t.get("pct")
        if pct is None and len(d) > 24:
            pct = (d["close"].iloc[-1] / d["close"].iloc[-25] - 1) * 100
        cls = ui.trend_cls(pct)
        color = ui.UP if cls == "up" else ui.DOWN if cls == "down" else ui.TEXT2
        spark = ui.sparkline(d["close"].tail(72).tolist(), color) if not d.empty else ""
        z = float(d["z_score"].iloc[-1]) if not d.empty else float("nan")
        sig = signal_of(d.iloc[-1]) if not d.empty else {"kind": "wait", "label": "—"}
        vol = t.get("qvol")
        cards.append(f"""
        <div class="card">
          <div class="card-head"><div class="sym">{ui.coin_icon(p)}<div>{ui.esc(p.split('/')[0])}
            <small>{ui.esc(p)}</small></div></div>{ui.badge(sig['label'], sig['kind'])}</div>
          <div class="px">{ui.fmt_px(last)}</div>
          <span class="chg {cls}">{ui.fmt_pct(pct)} 24h</span>
          {spark}
          <div class="meta"><span>Z-Score <b>{z:+.2f}σ</b></span>
            <span>Vol 24h <b>{f'${vol / 1e6:,.0f}M' if vol else '—'}</b></span></div>
        </div>""")
    H(f'<div class="grid">{"".join(cards)}</div>')


def render_signals(pairs: list[str], frames: dict, tick: dict) -> None:
    cards = []
    for p in pairs:
        d, _ = frames[p]
        if d.empty:
            continue
        r = d.iloc[-1]
        s = signal_of(r)
        price = tick.get(p, {}).get("last") or float(r["close"])
        body = [f'<p class="why">{s["why"]}</p>']
        if s["act"]:
            plan = plan_position(capital, risk_pct, price, float(r["rolling_std"]),
                                 float(r["rolling_mean"]) if s["mr"] else None, is_long=s["is_long"],
                                 sl_std_mult=2.0, tp_std_mult=1.5 if s["mr"] else 3.0)
            body += [ui.kv("Giá vào tham khảo", ui.fmt_px(price)),
                     ui.kv("Cắt lỗ (2σ)", ui.fmt_px(plan.stop_loss), "down"),
                     ui.kv("Chốt lời", ui.fmt_px(plan.take_profit), "up"),
                     ui.kv("Quy mô lệnh", f"${plan.position_usd:,.2f}"),
                     ui.kv("Rủi ro nếu chạm SL", f"-${plan.risk_usd:,.2f}", "down"),
                     ui.kv("Tỷ lệ lời/lỗ", f"1 : {plan.rr_ratio:.1f}")]
        else:
            body.append(ui.meter(s["progress"], s["need"], s["now"]))
            body.append(f'<div class="meta" style="margin-top:10px"><span>Mức gần tín hiệu</span>'
                        f'<b>{min(s["progress"], 1) * 100:.0f}%</b></div>')
        glow = {"long": "glow-long", "short": "glow-short"}.get(s["kind"], "")
        cards.append(f"""
        <div class="card {glow}">
          <div class="card-head"><div class="sym">{ui.coin_icon(p)}<div>{ui.esc(p)}
            <small>Nến 1h đã đóng · {r['date']:%H:%M %d/%m} UTC</small></div></div>
            {ui.badge(s['label'], s['kind'])}</div>
          <div class="strat">{ui.esc(s['strat'])}</div>
          {''.join(body)}
        </div>""")
    H(f'<div class="grid wide">{"".join(cards)}</div>')


def render_performance(snap: dict | None, bt: dict | None) -> None:
    c1, c2 = st.columns([1, 1.25], gap="medium")
    with c1:
        if snap and "profit" in snap:
            prof, cfg = snap["profit"], snap["cfg"]
            pct = prof.get("profit_all_percent", 0) or 0
            H(f"""<div class="card" style="height:100%">
              <div class="card-head"><b style="color:var(--text)">🤖 Bot đang chạy</b>
                {ui.badge('Dry-run' if cfg.get('dry_run') else 'Live', 'info' if cfg.get('dry_run') else 'warn')}</div>
              <div class="strat">{ui.esc(str(cfg.get('strategy')))} · {ui.esc(str(cfg.get('trading_mode')))}</div>
              <div class="big {ui.trend_cls(pct)}">{ui.fmt_pct(pct)}</div>
              <div class="strat">Tổng lãi/lỗ (gồm lệnh đang mở) · {prof.get('profit_all_coin', 0):,.2f} USDT</div>
              {ui.kv('Số lệnh đã đóng', str(prof.get('closed_trade_count', prof.get('trade_count', 0))))}
              {ui.kv('Thắng / Thua', f"{prof.get('winning_trades', 0)} / {prof.get('losing_trades', 0)}")}
              {ui.kv('Lệnh đang mở', str(len(snap.get('open', []))))}
            </div>""")
        else:
            ui.empty_state("🤖", "Bot chưa chạy",
                           "Chạy bot bằng tiền ảo (dry-run) để xem lãi/lỗ thật theo thời gian ở đây. "
                           "Không mất tiền thật.", "./run.sh dryrun")
    with c2:
        if not bt or not bt["rows"]:
            ui.empty_state("📊", "Chưa có kết quả backtest",
                           "Chạy backtest để so sánh chiến lược gốc và bản nâng cấp.", "./run.sh backtest")
            return
        rows = sorted(bt["rows"], key=lambda r: -r["profit"])
        names = {"QuantHybridStrategy": "Hybrid <small>nâng cấp</small>",
                 "QuantZScoreStrategy": "Z-Score <small>bản gốc</small>",
                 "QuantBreakoutStrategy": "Breakout <small>mới</small>",
                 "QuantSmartDCAStrategy": "Smart DCA <small>mới</small>"}

        def pcolor(v: float) -> str:
            return "up" if v > 0 else "down"

        cells = ['<div class="h">Chiến lược</div><div class="h n">Lợi nhuận</div>'
                 '<div class="h n">Sụt vốn</div><div class="h n hide-sm">Lệnh</div>']
        for r in rows:
            cells.append(f'<div class="name">{names.get(r["name"], ui.esc(r["name"]))}</div>'
                         f'<div class="n" style="color:var(--{pcolor(r["profit"])})">{ui.fmt_pct(r["profit"])}</div>'
                         f'<div class="n">{r["dd"]:.1f}%</div><div class="n hide-sm">{r["trades"]}</div>')
        if bt["market"] is not None:
            cells.append(f'<div class="name">Mua &amp; giữ <small>thị trường</small></div>'
                         f'<div class="n" style="color:var(--{pcolor(bt["market"])})">{ui.fmt_pct(bt["market"])}</div>'
                         f'<div class="n">—</div><div class="n hide-sm">—</div>')
        period = f"{str(bt['start'])[:10]} → {str(bt['end'])[:10]}" if bt["start"] else ""
        H(f"""<div class="card" style="height:100%">
          <div class="card-head"><b style="color:var(--text)">📊 Backtest gần nhất</b>
            <span class="strat" style="margin:0">{ui.esc(period)}</span></div>
          <div class="cmp" style="margin-top:10px">{''.join(cells)}</div>
          <div class="strat" style="margin:14px 0 0">Kết quả thật, không chỉnh sửa. Lỗ ít hơn thị trường
          chưa có nghĩa là có lãi — hãy chạy dry-run vài tuần trước khi dùng tiền thật.</div>
        </div>""")


with t_home:
    pairs = whitelist()
    news_items = st.cache_data(ttl=300, show_spinner=False)(market_context.fetch_news)()
    sentiment = market_context.label_for(market_context.news_sentiment_score(news_items)) \
        if news_items else "không có dữ liệu"
    snap = bot_snapshot(settings.FT_API_URL)
    bt_file = latest_backtest()
    bt = backtest_summary(bt_file.name) if bt_file else None

    render_hero(pairs, snap, bt, sentiment)

    with st.spinner("Đang lấy giá trực tiếp từ Binance..."):
        tick = live_tickers(tuple(pairs))
        frames = {p: market_frame(p, window) for p in pairs}
    src_live = all(src == "live" for _, src in frames.values())
    now = datetime.now(market_context.VN_TZ)
    ui.section("Thị trường", "Giá trực tiếp từ Binance Spot, biểu đồ 72 giờ gần nhất.",
               aside=f"{'🟢 Trực tiếp' if tick else '🟠 Dữ liệu đã tải (mất kết nối)'} · cập nhật {now:%H:%M:%S}")
    render_tickers(pairs, frames, tick)

    ui.section("Tín hiệu hệ thống", "Cùng logic với bot <b>QuantHybridStrategy</b>, tính trên nến 1h đã đóng. "
               f"Khối lượng lệnh tính theo vốn ${capital:,.0f} và rủi ro {risk_pct:.1f}%/lệnh (sửa ở tab 🛡️).",
               aside="" if src_live else "⚠️ Dùng dữ liệu đã tải", anchor="tin-hieu")
    render_signals(pairs, frames, tick)

    ui.section("Hiệu suất", "Bot đang chạy và kết quả kiểm chứng trên dữ liệu quá khứ.")
    render_performance(snap, bt)

    ui.section("Hệ thống hoạt động thế nào", "4 bước, từ dữ liệu thô đến lệnh có kiểm soát rủi ro.")
    H("""<div class="steps">
      <div class="step"><div class="num">01</div><b>Nhận diện thị trường</b>
        <span>Kiểm định ADF trên 200 nến gần nhất: p &lt; 0.20 là <i>đi ngang</i>, ngược lại là <i>có xu hướng</i>.</span></div>
      <div class="step"><div class="num">02</div><b>Chọn đúng chiến lược</b>
        <span>Đi ngang → mua khi Z-Score &lt; −2 và đã quay đầu. Có xu hướng → theo EMA20/50, lọc thêm khung 4h.</span></div>
      <div class="step"><div class="num">03</div><b>Tính lệnh theo rủi ro</b>
        <span>Cắt lỗ cách 2σ, khối lượng = số tiền chấp nhận mất ÷ khoảng cách cắt lỗ. Hòa vốn khi lời 1.5σ.</span></div>
      <div class="step"><div class="num">04</div><b>Tự bảo vệ</b>
        <span>Tạm dừng sau chuỗi cắt lỗ, dừng khi sụt vốn &gt; 15%, chặn mua khi tin tức quá tiêu cực.</span></div>
    </div>""")

    H("""<div class="disclaimer"><b>⚠️ Lưu ý rủi ro.</b> Đây là công cụ phân tích và tự động hóa, không phải lời khuyên
      đầu tư. Giao dịch crypto — đặc biệt Futures có đòn bẩy — có thể mất toàn bộ vốn. Kết quả quá khứ không đảm bảo
      tương lai. Luôn chạy <code>./run.sh dryrun</code> (tiền ảo) đủ lâu trước khi dùng tiền thật.</div>
      <div class="foot">Lil_Duck Quant × Freqtrade · dữ liệu Binance · làm mới trang để cập nhật</div>""")


# ==========================================================================================
# TAB TƯ VẤN — tổng hợp mọi phân tích thành chiến lược & phân bổ vốn (rule-based)
# ==========================================================================================
@st.cache_data(ttl=300, show_spinner=False)
def advisor_frame(pair: str) -> tuple[pd.DataFrame, str]:
    """~1000 nến 1h ĐÃ ĐÓNG + toàn bộ chỉ báo tư vấn. Mất mạng thì dùng dữ liệu đã tải."""
    try:
        df, src = fetch_live_ohlcv(pair, "1h", limit=1000).iloc[:-1], "live"
    except Exception:
        df, src = load_ohlcv(pair, "1h").tail(1000), "local"
    if df.empty:
        return df, src
    return advisor.enrich(df), src


def strategy_evidence() -> dict[str, dict]:
    """Kết quả backtest gần nhất của từng chiến lược (Spot + Futures) để làm 'bằng chứng'."""
    out: dict[str, dict] = {}
    for strat in ["QuantHybridFuturesStrategy", "QuantHybridStrategy", "QuantBreakoutStrategy",
                  "QuantSmartDCAStrategy", "QuantZScoreStrategy"]:
        f = latest_backtest(strat)
        if f is None:
            continue
        summ = backtest_summary(f.name)
        for r in summ["rows"]:
            if r["name"] == strat:
                out[strat] = {**r, "market": summ["market"]}
    return out


STRATEGY_LIBRARY = [
    ("QuantHybridStrategy", "🔄 Hybrid (Mean Reversion + Trend)", "Spot · Long",
     "Thị trường đi ngang: mua khi Z-Score &lt; −2 và đã quay đầu, bán khi về trung bình. "
     "Có xu hướng: mua khi EMA20 tách khỏi EMA50.",
     "Cắt lỗ 2σ, hoà vốn khi lời 1,5σ. Ít lệnh, chọn lọc.", "./run.sh dryrun"),
    ("QuantBreakoutStrategy", "🚀 Breakout — mua theo đà", "Spot · Long",
     "Thị trường có xu hướng tăng (ADF cao, EMA50 4h dốc lên): mua khi giá phá đỉnh 48 giờ kèm khối lượng lớn.",
     "Cắt lỗ 2,5×ATR rồi kéo theo đỉnh (3×ATR); thoát khi thủng đáy 24 giờ. Tỷ lệ thắng thấp, lệnh lời lớn.",
     "./run.sh dryrun-breakout"),
    ("QuantSmartDCAStrategy", "🧺 Smart DCA — tích luỹ từng phần", "Spot · Long · đầu tư",
     "Thị trường hoảng loạn (Z &lt; −2, RSI &lt; 30): mua 1 phần; giảm thêm 4% / 8% thì mua thêm 1 / 1,5 phần.",
     "Chốt khi lời 4% trên giá vốn. Cắt lỗ −12% trên giá vốn; tổng tiền 1 coin giới hạn theo % rủi ro.",
     "./run.sh dryrun-dca"),
    ("QuantHybridFuturesStrategy", "⚡ Hybrid Futures — Long &amp; Short", "Futures · x2–x5",
     "Như Hybrid nhưng thêm lệnh Short khi quá mua / xu hướng giảm.",
     "Đòn bẩy nhân cả lời lẫn lỗ. Chỉ dành cho hồ sơ Cân bằng / Mạo hiểm.", "./run.sh dryrun-futures"),
    ("QuantZScoreStrategy", "📐 Z-Score gốc", "Spot · Long · tham chiếu",
     "Bản chép nguyên logic dự án cũ: mua Z &lt; −2, bán Z ≥ 0, không lọc chế độ thị trường.",
     "Giữ lại để so sánh — không khuyến khích chạy thật.", "./run.sh backtest"),
]


def render_advisor() -> None:
    ui.section("🧭 Tư vấn chiến lược",
               "Hệ thống gom <b>mọi phân tích</b> (ADF, Z-Score, EMA 1h &amp; 4h, động lượng 7 ngày, biến động, "
               "tin tức, kết quả backtest) thành điểm đánh giá, chiến lược phù hợp và phân bổ vốn theo hồ sơ rủi ro.")
    H('<div class="disclaimer" style="margin-top:0"><b>Đây là phân tích tự động theo quy tắc, không phải lời khuyên '
      'đầu tư cá nhân.</b> Mọi kết luận suy ra từ số liệu bên dưới và có thể sai. Bạn tự chịu trách nhiệm với quyết '
      'định của mình — hãy thử bằng dry-run trước.</div>')

    cp, cb = st.columns([2, 1], vertical_alignment="bottom")
    with cp:
        pkey = st.segmented_control("Hồ sơ rủi ro của bạn", list(advisor.PROFILES),
                                    format_func=lambda k: advisor.PROFILES[k]["label"],
                                    default="can_bang", key="profile") or "can_bang"
    prof = advisor.PROFILES[pkey]
    with cb:
        if st.button(f"Áp dụng rủi ro {prof['risk_pct']}%/lệnh cho bot", width="stretch",
                     disabled=abs(prof["risk_pct"] - risk_pct) < 1e-9):
            settings.save_user_settings(capital, prof["risk_pct"])
            st.toast(f"Đã lưu: bot dùng rủi ro {prof['risk_pct']}%/lệnh cho lệnh tiếp theo.", icon="✅")
            st.rerun()
    st.caption(f"{prof['desc']} · Vốn tính toán: ${capital:,.0f} (sửa ở tab 🛡️).")

    pairs = whitelist()
    news = st.cache_data(ttl=300, show_spinner=False)(market_context.fetch_news)()
    news_score = market_context.news_sentiment_score(news) if news else 0
    with st.spinner("Đang phân tích ~1000 nến mỗi coin..."):
        tick = live_tickers(tuple(pairs))
        frames = {p: advisor_frame(p) for p in pairs}
    items = [advisor.assess(p, d, news_score, capital, prof["risk_pct"], prof["futures"],
                            price=tick.get(p, {}).get("last"))
             for p, (d, _) in frames.items() if not d.empty]
    if not items:
        ui.empty_state("📡", "Không có dữ liệu", "Kiểm tra mạng hoặc tải dữ liệu ở thanh bên.")
        return
    evidence = strategy_evidence()

    # ---- bộ lọc thị trường của bot
    mr = market_regime()
    if mr is not None:
        on = market_filter_enabled()
        state = ("🟢 Thị trường chung đang TĂNG (BTC trên SMA200 ngày) → các bot được phép mở lệnh Long."
                 if mr["up"] else
                 "🔴 Thị trường chung đang GIẢM (BTC dưới SMA200 ngày) → các bot Spot <b>đứng ngoài</b>, "
                 "không mở lệnh Long mới; bot Futures chỉ được Short.")
        H(f"""<div class="zone" style="margin-top:14px;font-weight:500;color:var(--text)">
          <b>Bộ lọc thị trường {'(đang BẬT)' if on else '(đang TẮT)'}:</b> {state}<br>
          <span style="color:var(--text2)">BTC đóng cửa ngày {mr['date']:%d/%m}: {ui.fmt_px(mr['close'])} ·
          SMA200 ngày: {ui.fmt_px(mr['sma'])} · cách {mr['gap']:+.1f}%</span></div>""")

    # ---- nhiệt kế thị trường
    label, kind = advisor.mood([a.score for a in items])
    avg = float(np.mean([a.score for a in items]))
    counts = {k: sum(a.regime == k for a in items) for k in ("range", "up", "down", "unclear")}
    best = max(items, key=lambda a: a.score)
    H(f"""<div class="mood" style="margin-top:14px">
      <div class="card"><div class="strat" style="margin:0">Nhiệt kế thị trường</div>
        <div class="score {ui.trend_cls(avg)}">{avg:+.0f} <small>/ 100</small></div>
        {ui.dbar(avg, 100)}{ui.badge(label, kind)}</div>
      <div class="card"><div class="strat" style="margin:0">Chế độ thị trường</div>
        {ui.kv('Đi ngang', str(counts['range']))}{ui.kv('Xu hướng tăng', str(counts['up']), 'up')}
        {ui.kv('Xu hướng giảm', str(counts['down']), 'down')}{ui.kv('Chưa rõ', str(counts['unclear']))}</div>
      <div class="card"><div class="strat" style="margin:0">Điểm cao nhất</div>
        <div class="sym" style="margin:6px 0">{ui.coin_icon(best.pair)}{ui.esc(best.pair)}</div>
        <div class="score {ui.trend_cls(best.score)}">{best.score:+.0f}</div>
        <div class="strat" style="margin:6px 0 0">{ui.esc(best.stance)}</div></div>
      <div class="card"><div class="strat" style="margin:0">Tin tức</div>
        <div class="score {ui.trend_cls(news_score)}">{news_score:+d}</div>
        <div class="strat" style="margin:8px 0 0">{ui.esc(market_context.label_for(news_score))}</div>
        <div class="evidence">Bot chặn lệnh Long khi ≤ −4</div></div>
    </div>""")

    # ---- thẻ tư vấn từng coin
    ui.section("Đánh giá & chiến lược từng coin",
               "Điểm = 35% xu hướng + 20% động lượng + 20% định giá (Z) + 10% độ ổn định (biến động thấp) + 15% tin tức. "
               "Xanh = ủng hộ mua, đỏ = bất lợi.")
    cards = []
    for a in sorted(items, key=lambda x: -x.score):
        frows = "".join(f"<span>{advisor.FACTOR_LABELS[k]}</span>{ui.dbar(v, 2)}<b>{v:+.1f}</b>"
                        for k, v in a.factors.items())
        reasons = "".join(f"<li>{ui.esc(x)}</li>" for x in a.reasons)
        zone = f'<div class="zone">🎯 {ui.esc(a.zone)}</div>' if a.zone else ""
        plan = ""
        if a.plan is not None:
            p = a.plan
            plan = (ui.kv("Giá vào tham khảo", ui.fmt_px(p.entry))
                    + ui.kv("Cắt lỗ", ui.fmt_px(p.stop_loss), "down")
                    + ui.kv("Chốt lời", ui.fmt_px(p.take_profit), "up")
                    + ui.kv("Khối lượng", f"${p.position_usd:,.0f}")
                    + ui.kv("Mất tối đa nếu sai", f"-${p.risk_usd:,.2f}", "down")
                    + ui.kv("Lời / lỗ", f"1 : {p.rr_ratio:.1f}"))
        strat = advisor.STRATEGY_OF.get(a.playbook)
        ev = evidence.get(strat) if strat else None
        ev_html = (f'<div class="evidence">Kiểm chứng: bot <b>{strat}</b> backtest '
                   f'<b style="color:var(--{"up" if ev["profit"] > 0 else "down"})">{ev["profit"]:+.2f}%</b>, '
                   f'sụt vốn {ev["dd"]:.1f}%, {ev["trades"]} lệnh (thị trường {ev["market"]:+.1f}%)</div>'
                   if ev else "")
        m = a.metrics
        cards.append(f"""<div class="card {'glow-long' if a.kind == 'long' else 'glow-short' if a.kind == 'short' else ''}">
          <div class="card-head"><div class="sym">{ui.coin_icon(a.pair)}<div>{ui.esc(a.pair)}
            <small>{ui.esc(a.regime_label)} · RSI {m['rsi']:.0f} · 7 ngày {m['roc_7d']:+.1f}%</small></div></div>
            <div style="text-align:right"><div class="score {ui.trend_cls(a.score)}">{a.score:+.0f}</div></div></div>
          {ui.dbar(a.score, 100)}
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px">{ui.badge(a.stance, a.kind)}
            {ui.badge(a.regime_label, 'info')}</div>
          <div class="strat">{ui.esc(a.playbook_label)}</div>
          <div class="factors">{frows}</div>
          <ul class="reasons">{reasons}</ul>{zone}{plan}{ev_html}
        </div>""")
    H(f'<div class="grid wide">{"".join(cards)}</div>')

    # ---- phân bổ danh mục
    ui.section(f"Phân bổ vốn đề xuất · hồ sơ {prof['label']}",
               "Chỉ chọn coin có điểm dương và không ở xu hướng giảm. Tỷ trọng tỷ lệ với điểm ÷ biến động "
               f"(coin càng biến động càng ít tiền), tối đa {prof['max_weight']:.0%}/coin, "
               f"tiền mặt tối thiểu {prof['cash_min']:.0%}.")
    alloc = advisor.allocate(items, pkey, capital)
    ca, cb2 = st.columns([1.3, 1], gap="large")
    with ca:
        colors = [ui.SERIES[i % len(ui.SERIES)] for i in range(len(alloc) - 1)] + [ui.MUTED]
        fig = go.Figure(go.Bar(
            x=alloc["Tỷ trọng"] * 100, y=alloc["Tài sản"], orientation="h", marker_color=colors,
            text=[f"{w:.0%} · ${u:,.0f}" for w, u in zip(alloc["Tỷ trọng"], alloc["USDT"])],
            textposition="outside", textfont=dict(color=ui.TEXT), cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig.update_layout(height=80 + 52 * len(alloc), showlegend=False, bargap=0.35,
                          xaxis=dict(range=[0, 140], ticksuffix="%", showgrid=True, tickvals=[0, 25, 50, 75, 100]),
                          yaxis=dict(autorange="reversed"), margin=dict(l=8, r=40, t=10, b=8))
        ui.chart(fig, key="alloc")
    with cb2:
        st.dataframe(alloc, hide_index=True, width="stretch", column_config={
            "Tỷ trọng": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "USDT": st.column_config.NumberColumn(format="$%.0f"),
            "Điểm": st.column_config.NumberColumn(format="%+.0f")})
        rets = {p: d.set_index("date")["log_return"].tail(720) for p, (d, _) in frames.items() if not d.empty}
        corr_pairs = advisor.correlated_pairs(rets)
        if corr_pairs:
            lst = " · ".join(f"{a_.split('/')[0]}–{b_.split('/')[0]} {c_:.2f}" for a_, b_, c_ in corr_pairs)
            st.warning(f"**Các coin đang đi cùng nhau** (tương quan ≥ 0.85): {lst}. Giữ nhiều coin tương quan cao "
                       "gần như nhân rủi ro lên — đa dạng hoá thật sự cần tài sản ít tương quan.", icon="🔗")
        if len(alloc) == 1:
            st.info("Hiện không có coin nào đủ điểm — hệ thống đề xuất giữ 100% tiền mặt.", icon="🛡️")

    # ---- AI diễn giải
    ui.section("🤖 Nhờ AI diễn giải", "Gemini đọc bảng số liệu ở trên và tóm tắt bằng lời dễ hiểu (không tự bịa số).")
    if not ai_advisor.is_enabled():
        st.info("Chưa có GEMINI_API_KEY trong .env — phần này tạm tắt.")
    elif st.button("Tóm tắt bằng Gemini", key="ai_brief"):
        summary = "\n".join(
            f"{a.pair}: điểm {a.score:+.0f}, {a.regime_label}, đề xuất '{a.stance}' ({a.playbook_label}), "
            f"Z {a.metrics['z']:+.2f}, RSI {a.metrics['rsi']:.0f}, 7 ngày {a.metrics['roc_7d']:+.1f}%, "
            f"biến động năm {a.metrics['vol_ann']:.0f}%" for a in items)
        summary += f"\nTin tức: {news_score:+d}. Phân bổ: " + ", ".join(
            f"{r['Tài sản']} {r['Tỷ trọng']:.0%}" for _, r in alloc.iterrows())
        summary += "\nBacktest: " + ", ".join(f"{k} {v['profit']:+.2f}% (DD {v['dd']:.1f}%)"
                                             for k, v in evidence.items())
        with st.spinner("Gemini đang đọc số liệu..."):
            st.session_state["ai_brief_text"] = ai_advisor.portfolio_brief(summary, prof["label"]) \
                or "AI tạm thời không trả lời (hết hạn mức hoặc lỗi mạng)."
    if st.session_state.get("ai_brief_text"):
        H(f'<div class="ai-box">{ui.esc(st.session_state["ai_brief_text"])}</div>')

    # ---- thư viện chiến lược
    ui.section("📚 Thư viện chiến lược", "5 bot Freqtrade có sẵn — dùng bot nào tuỳ chế độ thị trường và hồ sơ rủi ro. "
               "Số liệu là kết quả backtest gần nhất (chạy lại bằng <code>./run.sh backtest-all</code>).")
    lib = []
    for key, title, tag, when, risk, cmd in STRATEGY_LIBRARY:
        ev = evidence.get(key)
        res = (ui.kv("Lợi nhuận backtest", ui.fmt_pct(ev["profit"]), "up" if ev["profit"] > 0 else "down")
               + ui.kv("Sụt vốn tối đa", f"{ev['dd']:.1f}%") + ui.kv("Số lệnh · tỷ lệ thắng",
                                                                       f"{ev['trades']} · {ev['win']:.0f}%")
               if ev else ui.kv("Backtest", "chưa có — chạy ./run.sh backtest-all"))
        lib.append(f"""<div class="card"><h4>{title}</h4>{ui.badge(tag, 'info')}
          <div class="when"><b>Khi nào dùng:</b> {when}<br><b>Quản trị rủi ro:</b> {risk}</div>
          {res}<div style="margin-top:12px"><span class="cmd">{ui.esc(cmd)}</span></div></div>""")
    H(f'<div class="lib">{"".join(lib)}</div>')


with t_adv:
    render_advisor()


# ==========================================================================================
# TAB 1 — PHÂN TÍCH KỸ THUẬT & THỐNG KÊ
# ==========================================================================================
def price_figure(d: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.62, 0.2, 0.18])
    x = d["date"]
    upper = d["rolling_mean"] + 2 * d["rolling_std"]
    lower = d["rolling_mean"] - 2 * d["rolling_std"]
    band = "rgba(57,135,229,0.45)"
    fig.add_trace(go.Scatter(x=x, y=upper, name="+2σ", line=dict(color=band, width=1),
                             hovertemplate="+2σ %{y:,.4f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=lower, name="−2σ", line=dict(color=band, width=1), fill="tonexty",
                             fillcolor="rgba(57,135,229,0.06)", hovertemplate="−2σ %{y:,.4f}<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Candlestick(x=x, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                 name="Giá", increasing=dict(line=dict(color=ui.UP, width=1), fillcolor=ui.UP),
                                 decreasing=dict(line=dict(color=ui.DOWN, width=1), fillcolor=ui.DOWN)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["rolling_mean"], name="Trung bình", line=dict(color=ui.TEXT2, width=1,
                             dash="dash"), hovertemplate="TB %{y:,.4f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["ema_fast"], name="EMA20", line=dict(color=ui.BLUE, width=2),
                             hovertemplate="EMA20 %{y:,.4f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["ema_slow"], name="EMA50", line=dict(color=ui.ORANGE, width=2),
                             hovertemplate="EMA50 %{y:,.4f}<extra></extra>"), row=1, col=1)
    buy, sell = signal_markers(d)
    fig.add_trace(go.Scatter(x=x[buy], y=d["low"][buy] * 0.996, mode="markers", name="Tín hiệu Long",
                             marker=dict(symbol="triangle-up", size=12, color=ui.UP,
                                         line=dict(color=ui.BG, width=2)),
                             hovertemplate="▲ Long %{x|%d/%m %H:%M}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x[sell], y=d["high"][sell] * 1.004, mode="markers", name="Tín hiệu Short",
                             marker=dict(symbol="triangle-down", size=12, color=ui.DOWN,
                                         line=dict(color=ui.BG, width=2)),
                             hovertemplate="▼ Short %{x|%d/%m %H:%M}<extra></extra>"), row=1, col=1)

    zmax = max(3.5, float(np.nanmax(d["z_score"].abs())) + 0.3)
    fig.add_hrect(y0=Z_ENTRY, y1=zmax, fillcolor=ui.DOWN, opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hrect(y0=-zmax, y1=-Z_ENTRY, fillcolor=ui.UP, opacity=0.08, line_width=0, row=2, col=1)
    fig.add_hline(y=0, line=dict(color=ui.AXIS, width=1), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["z_score"], name="Z-Score", line=dict(color=ui.VIOLET, width=2),
                             hovertemplate="Z %{y:.2f}σ<extra></extra>", showlegend=False), row=2, col=1)

    fig.add_hrect(y0=0, y1=ADF_THRESHOLD, fillcolor=ui.BLUE, opacity=0.08, line_width=0, row=3, col=1)
    fig.add_hline(y=ADF_THRESHOLD, line=dict(color=ui.WARN, width=1, dash="dot"), row=3, col=1)
    fig.add_trace(go.Scatter(x=x, y=d["adf_p"], name="ADF p", line=dict(color=ui.AQUA, width=2),
                             hovertemplate="ADF p %{y:.3f}<extra></extra>", showlegend=False), row=3, col=1)

    fig.update_yaxes(title_text="Giá", row=1, col=1, side="right")
    fig.update_yaxes(title_text="Z-Score", row=2, col=1, side="right", range=[-zmax, zmax])
    fig.update_yaxes(title_text="ADF p", row=3, col=1, side="right", range=[0, 1])
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, spikedash="dot", spikecolor=ui.MUTED)
    fig.update_layout(height=820, hovermode="x unified", xaxis_rangeslider_visible=False,
                      margin=dict(l=8, r=8, t=40, b=8))
    return fig


with t_an:
    last = df.iloc[-1]
    sig = signal_of(last)
    H(f"""<div class="sec"><div><h3>{ui.coin_icon(pair)} &nbsp;{ui.esc(pair)} <span style="color:var(--muted);
      font-weight:600">· {ui.esc(tf)}</span> &nbsp;{ui.badge(sig['label'], sig['kind'])}</h3>
      <p>{sig['why']}</p></div><span class="aside">Nến cuối: {last['date']:%H:%M %d/%m/%Y} UTC ·
      dữ liệu đã tải (cập nhật ở thanh bên)</span></div>""")
    kurt = df["log_return"].kurtosis()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Giá", ui.fmt_px(float(last["close"])))
    c2.metric("Z-Score", f"{last['z_score']:+.2f}σ",
              "Quá mua" if last["z_score"] > 2 else "Quá bán" if last["z_score"] < -2 else "Trung tính",
              delta_color="off")
    c3.metric("ADF 200 nến", f"{last['adf_p']:.3f}",
              "Đi ngang" if last["adf_p"] < ADF_THRESHOLD else "Có xu hướng", delta_color="off",
              help="ADF trượt 200 nến gần nhất (giống bot). < 0.20 = đi ngang.")
    c4.metric("EMA20 / EMA50", f"{last['ema_gap_pct']:+.2f}%", delta_color="off")
    c5.metric("Kurtosis", f"{kurt:.2f}", "Đuôi béo — dễ có cú sốc" if kurt > 3 else "Ổn định",
              delta_color="off")

    spans = {"7 ngày": 7, "30 ngày": 30, "90 ngày": 90, "Tất cả": None}
    span = st.segmented_control("Khoảng hiển thị", list(spans), default="30 ngày", key="span",
                                label_visibility="collapsed") or "30 ngày"
    view = df if spans[span] is None else df[df["date"] >= df["date"].iloc[-1] - pd.Timedelta(days=spans[span])]
    ui.chart(price_figure(view), key="price_chart")
    st.caption("▲▼ = điểm Mean Reversion trong quá khứ (đi ngang + Z vượt ±2 rồi quay đầu). "
               "Vùng xanh ở ô ADF = thị trường đi ngang.")


# ==========================================================================================
# TAB 2 — SCREENER
# ==========================================================================================
with t_scr:
    ui.section("🎯 Screener theo chế độ thị trường",
               "ADF &lt; 0.20 ⇒ đi ngang ⇒ đánh hồi quy Z-Score. Ngược lại ⇒ đánh theo xu hướng EMA. "
               "Cùng logic với bot Freqtrade.")
    rows, returns = [], {}
    for p, t in datasets:
        d = load_with_indicators(p, t, window, file_mtime(p, t))
        if d.empty:
            continue
        r = d.iloc[-1]
        rows.append({
            "Tài sản": p, "Khung": t, "Giá": float(r["close"]),
            "Diễn biến": d["close"].tail(60).tolist(),
            "Z-Score": round(float(r["z_score"]), 2),
            "ADF 200": round(float(r["adf_p"]), 3) if pd.notna(r["adf_p"]) else None,
            "ADF toàn bộ": round(adf_pvalue(d["close"]), 3),
            "EMA gap %": round(float(r["ema_gap_pct"]), 2), "Mục tiêu (TB)": float(r["rolling_mean"]),
            "Khuyến nghị": regime_signal(r),
        })
        if t == tf:
            returns[p] = d.set_index("date")["log_return"]
    st.dataframe(
        pd.DataFrame(rows).sort_values("Z-Score"), hide_index=True, width="stretch",
        column_config={
            "Giá": st.column_config.NumberColumn(format="$%.4f"),
            "Mục tiêu (TB)": st.column_config.NumberColumn(format="$%.4f"),
            "Diễn biến": st.column_config.LineChartColumn("Diễn biến (60 nến)", width="small"),
            "Z-Score": st.column_config.NumberColumn(format="%+.2f σ"),
            "EMA gap %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Khuyến nghị": st.column_config.TextColumn(width="large"),
        })

    ui.section(f"🔗 Ma trận tương quan · khung {ui.esc(tf)}",
               "Tương quan &gt; 0.80 ⇒ chỉ nên giữ 1 trong 2 đồng để tránh nhân đôi rủi ro.")
    if len(returns) >= 2:
        corr = pd.DataFrame(returns).corr()
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1, text=corr.round(2).values,
            texttemplate="%{text}", textfont=dict(color=ui.TEXT, size=13), xgap=3, ygap=3,
            colorscale=[[0, ui.BLUE], [0.5, "#2a2f3a"], [1, ui.RED]],
            hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>", colorbar=dict(thickness=10)))
        fig.update_layout(height=420, yaxis=dict(autorange="reversed"))
        ui.chart(fig, key="corr")


# ==========================================================================================
# TAB 3 — VỐN & RỦI RO
# ==========================================================================================
def plan_figure(d: pd.DataFrame, plan, is_long: bool) -> go.Figure:
    tail = d.tail(120)
    t_last = tail["date"].iloc[-1]
    x0, x1 = tail["date"].iloc[0], t_last + (t_last - tail["date"].iloc[-2]) * 14
    fig = go.Figure()
    fig.add_shape(type="rect", x0=t_last, x1=x1, y0=plan.entry, y1=plan.take_profit,
                  fillcolor=ui.UP, opacity=0.14, line_width=0)
    fig.add_shape(type="rect", x0=t_last, x1=x1, y0=plan.entry, y1=plan.stop_loss,
                  fillcolor=ui.DOWN, opacity=0.14, line_width=0)
    fig.add_trace(go.Scatter(x=tail["date"], y=tail["close"], name="Giá", line=dict(color=ui.BLUE, width=2),
                             hovertemplate="%{x|%d/%m %H:%M} · %{y:,.4f}<extra></extra>"))
    for y, color, name in [(plan.take_profit, ui.UP, "Chốt lời"), (plan.entry, ui.TEXT, "Vào lệnh"),
                           (plan.stop_loss, ui.DOWN, "Cắt lỗ")]:
        fig.add_hline(y=y, line=dict(color=color, width=1.5, dash="dot" if name == "Vào lệnh" else "solid"),
                      annotation_text=f"{name}  {ui.fmt_px(y)}", annotation_position="top left",
                      annotation_font=dict(color=color, size=12))
    fig.update_layout(height=380, showlegend=False, xaxis=dict(range=[x0, x1]),
                      title=f"Kịch bản {'Long' if is_long else 'Short'} trên 120 nến gần nhất")
    return fig


with t_risk:
    ui.section(f"🛡️ Máy tính đi vốn · {ui.esc(pair)}",
               "Đặt số tiền chấp nhận mất mỗi lệnh — hệ thống tự tính khối lượng, cắt lỗ và chốt lời. "
               "Bot Freqtrade dùng chung mức rủi ro này.")
    ci, cr = st.columns([1, 2], gap="large")
    with ci:
        cap_in = st.number_input("Tổng vốn (USDT)", min_value=10.0, value=capital, step=100.0)
        risk_in = st.slider("Rủi ro tối đa mỗi lệnh (%)", 0.5, 5.0, float(risk_pct), 0.5)
        if (cap_in, risk_in) != (capital, risk_pct):
            settings.save_user_settings(cap_in, risk_in)
            st.toast("Đã lưu — bot Freqtrade sẽ dùng mức rủi ro này cho lệnh tiếp theo.", icon="✅")
        direction = st.segmented_control("Hướng", ["🟢 Long", "🔴 Short"], default="🟢 Long") or "🟢 Long"
        sl_mult = st.slider("Cắt lỗ cách bao nhiêu σ", 0.5, 3.5, 2.0, 0.5,
                            help="Bot QuantHybridStrategy mặc định 2.0σ.")
    with cr:
        is_long = "Long" in direction
        plan = plan_position(cap_in, risk_in, float(last["close"]), float(last["rolling_std"]),
                             float(last["rolling_mean"]), is_long=is_long, sl_std_mult=sl_mult)
        a, b, c = st.columns(3)
        a.metric("Rủi ro tối đa", f"-${plan.risk_usd:,.2f}", f"{risk_in}% vốn", delta_color="off")
        b.metric("Quy mô lệnh", f"${plan.position_usd:,.0f}", f"{plan.coin_amount:.4f} coin", delta_color="off")
        c.metric("Đòn bẩy cần", f"{plan.leverage_needed}x", "Cẩn thận nếu > 5x", delta_color="off")
        a, b, c = st.columns(3)
        a.metric("Cắt lỗ", ui.fmt_px(plan.stop_loss), f"Cách {plan.stop_distance_pct * 100:.2f}%",
                 delta_color="off")
        b.metric("Chốt lời", ui.fmt_px(plan.take_profit), f"R:R = 1:{plan.rr_ratio:.1f}", delta_color="off")
        var95, cvar95 = value_at_risk(df["return"])
        c.metric("VaR 95% / nến", f"{var95 * 100:.2f}%", f"CVaR {cvar95 * 100:.2f}%", delta_color="off")
    ui.chart(plan_figure(df, plan, is_long), key="plan")
    st.caption("Half-Kelly tính từ lệnh backtest thật nằm ở tab 📊 Backtest.")


# ==========================================================================================
# TAB 4 — TIN TỨC
# ==========================================================================================
with t_news:
    news = st.cache_data(ttl=300, show_spinner=False)(market_context.fetch_news)()
    if not news:
        ui.empty_state("📡", "Không kết nối được nguồn tin", "Kiểm tra mạng rồi tải lại trang.")
    else:
        score = market_context.news_sentiment_score(news)
        ui.section("📰 Tin tức & tâm lý thị trường",
                   "Tin mới nhất từ CoinDesk và CoinTelegraph, chấm điểm tăng/giảm theo từ khoá.",
                   aside="Bot chặn lệnh Long khi điểm tổng ≤ −4")
        m1, m2, m3 = st.columns(3)
        m1.metric("Tin tích cực", sum(n["score"] > 0 for n in news))
        m2.metric("Tin tiêu cực", sum(n["score"] < 0 for n in news))
        m3.metric("Điểm tổng", f"{score:+d}", market_context.label_for(score), delta_color="off")
        cards = []
        for n in news:
            kind = "long" if n["score"] > 0 else "short" if n["score"] < 0 else "wait"
            cards.append(f"""<a class="card news" href="{ui.esc(n['link'])}" target="_blank">
              <div class="card-head"><span class="src">{ui.esc(n['source'])}</span>
              {ui.badge(n['sentiment'], kind)}</div>
              <span class="t">{ui.esc(n['title'])}</span><span class="time">🕒 {ui.esc(str(n['published']))}</span></a>""")
        H(f'<div class="grid wide" style="margin-top:14px">{"".join(cards)}</div>')


# ==========================================================================================
# TAB 5 — BOT FREQTRADE (LIVE)
# ==========================================================================================
CONTROL = [  # (tên dịch vụ trong ./run.sh start, nhãn, cổng, mô tả)
    ("hybrid", "🔄 Bot Hybrid (Spot)", 8080, "Bot chính · nhận lệnh Telegram"),
    ("breakout", "🚀 Bot Breakout", 8082, "Mua theo đà"),
    ("dca", "🧺 Bot Smart DCA", 8083, "Tích luỹ từng phần"),
    ("futures", "⚡ Bot Futures", 8081, "Long + Short, đòn bẩy"),
    ("alert", "🔔 Alert bot", None, "Chỉ gửi cảnh báo Telegram"),
]


def service_state(name: str, port: int | None) -> str:
    """'nen' = chạy nền (do ./run.sh start bật), 'terminal' = chạy trong Terminal, 'tat' = tắt."""
    import socket

    pidf = ROOT / "logs" / f"{name}.pid"
    try:
        os.kill(int(pidf.read_text().strip()), 0)
        return "nen"
    except Exception:
        pass
    if port:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return "terminal"
    if name == "alert" and subprocess.run(["pgrep", "-f", "alert_bot/alert_bot.py"],
                                          capture_output=True).returncode == 0:
        return "terminal"
    return "tat"


def run_service(action: str, name: str) -> str:
    res = subprocess.run([str(ROOT / "run.sh"), action, name], cwd=ROOT, capture_output=True, text=True,
                         timeout=90, env=os.environ.copy())
    return (res.stdout + res.stderr).strip()


@st.fragment
def control_panel():
    ui.section("🎛️ Bật / tắt bot", "Bot bật ở đây chạy <b>nền</b> — đóng trình duyệt hay Terminal bot vẫn chạy. "
               "Mọi bot đều là <b>dry-run (tiền ảo)</b>.")
    cols = st.columns(len(CONTROL))
    for col, (name, label, port, desc) in zip(cols, CONTROL):
        state = service_state(name, port)
        with col, st.container(border=True):
            dot = {"nen": "on", "terminal": "on", "tat": "off"}[state]
            text = {"nen": "Đang chạy (nền)", "terminal": "Đang chạy (Terminal)", "tat": "Đang tắt"}[state]
            H(f'<b style="color:var(--text)">{label}</b><div class="strat" style="margin:2px 0 8px">{desc}'
              f'{f" · cổng {port}" if port else ""}</div>'
              f'<span class="pill"><span class="dot {dot}"></span>{text}</span>')
            if state == "tat":
                if st.button("▶ Bật", key=f"on_{name}", width="stretch", type="primary"):
                    with st.spinner("Đang bật..."):
                        st.toast(run_service("start", name).splitlines()[0], icon="▶️")
                    st.rerun()
            elif state == "nen":
                if st.button("■ Tắt", key=f"off_{name}", width="stretch"):
                    with st.spinner("Đang tắt (tối đa 20 giây)..."):
                        st.toast(run_service("stop", name).splitlines()[0], icon="⏹️")
                    st.rerun()
            else:
                st.caption("Bật bằng tay trong Terminal → tắt bằng `Ctrl + C` ở Terminal đó.")
    st.caption("Cả 4 bot nhắn Telegram khi vào/thoát lệnh; chỉ bot Hybrid nhận lệnh /status, /profit. "
               "Với autostart, bot bị tắt bất thường sẽ tự bật lại sau tối đa 5 phút.")


with t_bot:
    control_panel()
    ui.section("🤖 Bot Freqtrade đang chạy", "Tự làm mới mỗi 30 giây.")
    bots = {"Hybrid Spot · 8080": ("http://127.0.0.1:8080", "./run.sh dryrun"),
            "Futures · 8081": ("http://127.0.0.1:8081", "./run.sh dryrun-futures"),
            "Breakout · 8082": ("http://127.0.0.1:8082", "./run.sh dryrun-breakout"),
            "Smart DCA · 8083": ("http://127.0.0.1:8083", "./run.sh dryrun-dca")}
    api_choice = st.segmented_control("Bot", [*bots, "Tuỳ chỉnh"], default="Hybrid Spot · 8080",
                                      key="api_choice") or "Hybrid Spot · 8080"
    if api_choice == "Tuỳ chỉnh":
        api_url, start_cmd = st.text_input("Địa chỉ API", settings.FT_API_URL), "./run.sh dryrun"
    else:
        api_url, start_cmd = bots[api_choice]

    @st.fragment(run_every=30)
    def bot_panel():
        client = FreqtradeClient(url=api_url)
        if not client.ping():
            ui.empty_state("🛌", "Bot chưa chạy",
                           "Mở Terminal trong thư mục QuantFreqtrade, gõ lệnh dưới đây rồi quay lại trang này.",
                           start_cmd)
            return
        try:
            cfg, prof, open_trades = client.show_config(), client.profit(), client.status()
        except Exception as e:
            st.error(f"Không đọc được API (sai mật khẩu trong .env?): {e}")
            return
        mode = "🧪 DRY-RUN (tiền ảo)" if cfg.get("dry_run") else "💰 LIVE (TIỀN THẬT)"
        st.caption(f"{mode} · {cfg.get('strategy')} · {cfg.get('trading_mode')} · "
                   f"cập nhật {datetime.now():%H:%M:%S}")
        a, b, c, d = st.columns(4)
        a.metric("Lợi nhuận đã chốt", f"{prof.get('profit_closed_coin', 0):,.2f} USDT",
                 f"{prof.get('profit_closed_percent', 0):.2f}%")
        b.metric("Tổng (gồm lệnh mở)", f"{prof.get('profit_all_coin', 0):,.2f} USDT",
                 f"{prof.get('profit_all_percent', 0):.2f}%")
        c.metric("Số lệnh", prof.get("trade_count", 0), f"Thắng {prof.get('winning_trades', 0)} / "
                                                         f"Thua {prof.get('losing_trades', 0)}", delta_color="off")
        d.metric("Lệnh đang mở", len(open_trades))
        pct_col = {"profit_pct": st.column_config.NumberColumn("Lãi/lỗ %", format="%+.2f%%")}
        if open_trades:
            ui.section("Lệnh đang mở")
            cols = [c for c in ["pair", "is_short", "enter_tag", "open_date", "open_rate", "current_rate",
                                "stake_amount", "leverage", "profit_pct", "stop_loss_abs"]
                    if c in open_trades[0]]
            st.dataframe(pd.DataFrame(open_trades)[cols], hide_index=True, width="stretch",
                         column_config=pct_col)
        closed = client.trades(limit=50)
        if closed:
            cdf = pd.DataFrame(closed)
            cdf = cdf[~cdf["is_open"]] if "is_open" in cdf else cdf
            if not cdf.empty:
                ui.section("Lệnh đã đóng gần nhất")
                cols = [c for c in ["pair", "enter_tag", "exit_reason", "open_date", "close_date",
                                    "profit_pct", "profit_abs"] if c in cdf]
                st.dataframe(cdf[cols], hide_index=True, width="stretch", column_config=pct_col)

    bot_panel()


# ==========================================================================================
# TAB 6 — KẾT QUẢ BACKTEST
# ==========================================================================================
SHORT_NAMES = {"QuantZScoreStrategy": "Z-Score gốc", "QuantHybridStrategy": "Hybrid",
               "QuantBreakoutStrategy": "Breakout", "QuantSmartDCAStrategy": "Smart DCA",
               "QuantHybridFuturesStrategy": "Hybrid Futures"}


def render_walk_forward() -> None:
    ui.section("🧪 Kiểm chứng theo giai đoạn (walk-forward)",
               "Cùng một bộ tham số chạy riêng trên <b>từng 6 tháng</b>. Chiến lược đáng tin phải ổn định qua "
               "nhiều kiểu thị trường, không chỉ đẹp ở một giai đoạn may mắn.",
               aside="Chạy lại: <code>./run.sh validate</code>")
    files = {"Có bộ lọc thị trường": settings.USER_DATA / "walk_forward.json",
             "Không lọc (để so sánh)": settings.USER_DATA / "walk_forward_nofilter.json"}
    avail = [k for k, f in files.items() if f.exists()]
    choice = st.segmented_control("Phiên bản", avail, default=avail[0] if avail else None,
                                  key="wf_choice", label_visibility="collapsed") if len(avail) > 1 else None
    wf_file = files[choice or (avail[0] if avail else "Có bộ lọc thị trường")]
    if not wf_file.exists():
        ui.empty_state("🧪", "Chưa có kết quả kiểm chứng",
                       "Cần ~2 năm dữ liệu (<code>./run.sh download 730 --prepend</code>) rồi chạy:", "./run.sh validate")
        return
    wf = json.loads(wf_file.read_text())
    labels = [w["label"] for w in wf["windows"]]
    names = list(wf["strategies"])
    z = [[r["profit_pct"] for r in wf["strategies"][n]] for n in names] + [[w["market_pct"] for w in wf["windows"]]]
    ylab = [SHORT_NAMES.get(n, n) for n in names] + ["Mua & giữ (thị trường)"]
    lim = max(5.0, max(abs(v) for row in z for v in row))
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=ylab, zmin=-lim, zmax=lim, xgap=4, ygap=4,
        colorscale=[[0, ui.DOWN], [0.5, "#2a2f3a"], [1, ui.UP]], showscale=False,
        text=[[f"{v:+.1f}%" for v in row] for row in z], texttemplate="%{text}",
        textfont=dict(color=ui.TEXT, size=14), hovertemplate="%{y} · %{x}: %{text}<extra></extra>"))
    fig.update_layout(height=90 + 52 * len(ylab), yaxis=dict(autorange="reversed"),
                      xaxis=dict(side="top"), margin=dict(l=8, r=8, t=30, b=8))
    ui.chart(fig, key="wf_heat")
    cards = []
    for n in names:
        sm = wf["summary"][n]
        kind = "long" if sm["profitable"] >= sm["n"] * 0.75 else "wait" if sm["profitable"] >= sm["n"] / 2 else "short"
        verdict = {"long": "Ổn định", "wait": "Chưa ổn định", "short": "Không ổn định"}[kind]
        cards.append(f"""<div class="card"><div class="card-head"><b style="color:var(--text)">{SHORT_NAMES.get(n, n)}</b>
          {ui.badge(verdict, kind)}</div>
          {ui.kv('Giai đoạn có lãi', f"{sm['profitable']} / {sm['n']}", 'up' if sm['profitable'] > sm['n'] / 2 else 'down')}
          {ui.kv('Thắng thị trường', f"{sm['beat_market']} / {sm['n']}")}
          {ui.kv('Tổng lãi/lỗ các giai đoạn', ui.fmt_pct(sm['sum_profit_pct']), 'up' if sm['sum_profit_pct'] > 0 else 'down')}
          {ui.kv('Sụt vốn tệ nhất', f"{sm['worst_dd_pct']:.1f}%")}</div>""")
    H(f'<div class="grid" style="margin-top:12px">{"".join(cards)}</div>')
    st.caption(f"Cập nhật: {wf['generated'].replace('T', ' ')} · Ô xanh = có lãi, ô đỏ = lỗ trong giai đoạn đó. "
               "Ổn định = có lãi ở ≥ 75% số giai đoạn.")


with t_bt:
    render_walk_forward()
    ui.section("📊 Kết quả Backtest Freqtrade", "So sánh chiến lược trên cùng dữ liệu quá khứ.")
    bt_dir = settings.USER_DATA / "backtest_results"
    files = sorted(bt_dir.glob("backtest-result-*.zip"), reverse=True)
    if not files:
        ui.empty_state("📊", "Chưa có kết quả", "Chạy backtest trong Terminal rồi tải lại trang.", "./run.sh backtest")
    else:
        from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats

        names = [f.name for f in files]
        default_bt = latest_backtest()
        pick = st.selectbox("File kết quả", names,
                            index=names.index(default_bt.name) if default_bt and default_bt.name in names else 0,
                            help="Mặc định mở lần backtest gần nhất có so sánh Z-Score (gốc) vs Hybrid (nâng cấp).")
        stats = load_backtest_stats(bt_dir, filename=pick)
        comp = pd.DataFrame(stats.get("strategy_comparison", []))
        if not comp.empty:
            show = comp[["key", "trades", "profit_total_pct", "profit_total_abs", "wins", "losses",
                         "max_drawdown_account", "duration_avg"]].rename(columns={
                "key": "Chiến lược", "trades": "Số lệnh", "profit_total_pct": "Lợi nhuận %",
                "profit_total_abs": "Lợi nhuận USDT", "wins": "Thắng", "losses": "Thua",
                "max_drawdown_account": "Sụt vốn tối đa", "duration_avg": "Giữ lệnh TB"})
            show["Sụt vốn tối đa"] = show["Sụt vốn tối đa"] * 100
            st.dataframe(show, hide_index=True, width="stretch", column_config={
                "Lợi nhuận %": st.column_config.NumberColumn(format="%+.2f%%"),
                "Lợi nhuận USDT": st.column_config.NumberColumn(format="%+.2f"),
                "Sụt vốn tối đa": st.column_config.NumberColumn(format="%.2f%%")})

        fig = go.Figure()
        start_bal = None
        details = []
        for i, (strat, s) in enumerate(stats["strategy"].items()):
            trades = load_backtest_data(bt_dir, strategy=strat, filename=pick)
            if trades.empty:
                continue
            trades = trades.sort_values("close_date")
            start_bal = s["starting_balance"]
            equity = start_bal + trades["profit_abs"].cumsum()
            color = ui.SERIES[i % len(ui.SERIES)]
            fig.add_trace(go.Scatter(x=trades["close_date"], y=equity, name=strat, mode="lines",
                                     line=dict(color=color, width=2, shape="hv"),
                                     hovertemplate=f"{strat}<br>%{{x|%d/%m/%Y}} · %{{y:,.2f}} USDT<extra></extra>"))
            fig.add_annotation(x=trades["close_date"].iloc[-1], y=equity.iloc[-1], text=f"{equity.iloc[-1]:,.0f}",
                               showarrow=False, xanchor="left", xshift=6, font=dict(color=ui.TEXT, size=12))
            details.append((strat, s, trades))
        if start_bal is not None:
            fig.add_hline(y=start_bal, line=dict(color=ui.AXIS, width=1, dash="dot"),
                          annotation_text="Vốn ban đầu", annotation_font=dict(color=ui.MUTED, size=11))
        fig.update_layout(title="Đường cong vốn (USDT)", height=460, hovermode="x unified")
        ui.chart(fig, key="equity")
        st.caption(f"Thị trường thay đổi trong giai đoạn: "
                   f"{next(iter(stats['strategy'].values()))['market_change'] * 100:+.2f}%")
        for strat, s, trades in details:
            with st.expander(f"Chi tiết {strat} — {len(trades)} lệnh · Half-Kelly = "
                             f"{half_kelly(trades['profit_ratio']):.1f}% vốn"):
                st.dataframe(pd.DataFrame(s["exit_reason_summary"])[["key", "trades", "profit_total_pct",
                                                                    "wins", "losses"]], hide_index=True)
                st.dataframe(trades[["pair", "enter_tag", "exit_reason", "open_date", "close_date",
                                     "profit_ratio", "profit_abs"]], hide_index=True, width="stretch")
