"""
Giao diện dashboard: bảng màu, CSS, template Plotly và các khối HTML dùng chung.

Mọi màu nằm ở 1 chỗ (đầu file) -> muốn đổi giao diện chỉ cần sửa ở đây.
Màu chuỗi dữ liệu (SERIES) lấy theo thứ tự cố định từ bảng màu đã kiểm định
cho người mù màu (dark mode), không tự sinh màu ngẫu nhiên.
"""

from __future__ import annotations

import html
import itertools

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------- màu --------------
BG = "#0b0e14"
SURFACE = "#121722"
SURFACE2 = "#1a2130"
BORDER = "rgba(255,255,255,0.08)"
TEXT = "#e8eaf0"
TEXT2 = "#a3abbd"
MUTED = "#6b7385"
GRID = "rgba(255,255,255,0.06)"
AXIS = "rgba(255,255,255,0.16)"

UP = "#1fbf75"      # tăng / Long / tốt
DOWN = "#ef5d5d"    # giảm / Short / xấu
WARN = "#fab219"

BLUE, ORANGE, AQUA, YELLOW = "#3987e5", "#d95926", "#199e70", "#c98500"
MAGENTA, GREEN, VIOLET, RED = "#d55181", "#0ca30c", "#9085e9", "#e66767"
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]

FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

:root{
  --bg:#0b0e14; --surface:#121722; --surface2:#1a2130; --border:rgba(255,255,255,0.08);
  --border-strong:rgba(255,255,255,0.14); --text:#e8eaf0; --text2:#a3abbd; --muted:#6b7385;
  --up:#1fbf75; --down:#ef5d5d; --warn:#fab219; --accent:#3987e5; --accent-soft:#6da7ec;
  --mono:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}
html, body, .stApp, .stMarkdown, button, input, textarea, select{
  font-family: Inter, system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.stApp{
  background:
    radial-gradient(1100px 520px at 8% -8%, rgba(57,135,229,0.13), transparent 60%),
    radial-gradient(900px 480px at 100% -4%, rgba(31,191,117,0.09), transparent 60%),
    var(--bg);
}
header[data-testid="stHeader"]{ background: transparent; }
#MainMenu, footer, [data-testid="stDecoration"]{ visibility: hidden; height: 0; }
.block-container{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1440px; }
h1, h2, h3{ letter-spacing: -0.02em; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{ background: #0d1119; border-right: 1px solid var(--border); }
section[data-testid="stSidebar"] .block-container{ padding-top: 1rem; }
.side-brand{ display:flex; align-items:center; gap:10px; margin: 0 0 14px; }
.side-brand .logo{ width:36px; height:36px; border-radius:10px; display:grid; place-items:center;
  background: linear-gradient(135deg, #3987e5, #1fbf75); font-size:20px; }
.side-brand b{ font-size:16px; color:var(--text); display:block; line-height:1.1; }
.side-brand small{ color:var(--muted); font-size:12px; }
.side-label{ color:var(--muted); font-size:11px; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; margin: 18px 0 6px; }

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"]{ gap:4px; background: var(--surface); padding:6px; border-radius:14px;
  border:1px solid var(--border); overflow-x:auto; }
.stTabs [data-baseweb="tab"]{ height:42px; border-radius:10px; padding:0 18px; color:var(--text2);
  font-weight:600; white-space:nowrap; }
.stTabs [data-baseweb="tab"]:hover{ color: var(--text); background: rgba(255,255,255,0.03); }
.stTabs [aria-selected="true"]{ background: var(--surface2) !important; color: var(--text) !important;
  box-shadow: inset 0 0 0 1px var(--border-strong); }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{ display:none; }
.stTabs [data-baseweb="tab-panel"]{ padding-top: 18px; }

/* ---------- widget mặc định ---------- */
div[data-testid="stMetric"]{ background: var(--surface); border:1px solid var(--border); border-radius:14px;
  padding: 14px 16px; }
div[data-testid="stMetricLabel"] p{ color:var(--text2); font-size:12px; font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; }
div[data-testid="stMetricValue"]{ font-family: var(--mono); font-weight:600; font-size: 1.32rem; }
div[data-testid="stMetricValue"] > div{ overflow: visible; text-overflow: clip; }
div[data-testid="stMetricDelta"]{ font-size: 12px; }
div[data-testid="stMetricDelta"] svg{ display:none; }  /* bỏ mũi tên ↑ gây hiểu nhầm ở nhãn mô tả */
div[data-testid="stPlotlyChart"]{ background: var(--surface); border:1px solid var(--border);
  border-radius:16px; padding: 10px 8px 4px; }
div[data-testid="stDataFrame"]{ border:1px solid var(--border); border-radius:14px; overflow:hidden; }
div[data-testid="stExpander"] details{ background: var(--surface); border:1px solid var(--border);
  border-radius:14px; }
div[data-testid="stForm"]{ border:1px solid var(--border); border-radius:14px; background: rgba(255,255,255,0.015); }
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a, .stDownloadButton > button{
  border-radius:10px; font-weight:600; }
div[data-testid="stAlert"]{ border-radius:12px; }
code{ font-family: var(--mono); }

/* ---------- hero ---------- */
.hero{ position:relative; display:grid; grid-template-columns: 1.35fr 1fr; gap: 28px; align-items:center;
  padding: 34px 34px; border-radius: 22px; border:1px solid var(--border);
  background:
    radial-gradient(600px 300px at 0% 0%, rgba(57,135,229,0.20), transparent 70%),
    radial-gradient(500px 300px at 100% 100%, rgba(31,191,117,0.14), transparent 70%),
    linear-gradient(180deg, #131a27, #0f141e);
  overflow:hidden; margin-bottom: 18px; }
.hero:after{ content:""; position:absolute; inset:0; pointer-events:none;
  background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px);
  background-size: 36px 36px; mask-image: linear-gradient(90deg, transparent, #000 35%, #000 65%, transparent); }
.hero > *{ position:relative; z-index:1; }
.eyebrow{ display:inline-flex; gap:8px; align-items:center; color: var(--accent-soft); font-size:12px;
  font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin-bottom: 14px; }
.hero h1{ font-size: clamp(30px, 3.4vw, 46px); line-height:1.08; font-weight:800; margin: 0 0 14px;
  color: var(--text); padding:0; }
.grad{ background: linear-gradient(90deg, #6da7ec 0%, #1fbf75 100%); -webkit-background-clip:text;
  background-clip:text; color: transparent; }
.hero p.lead{ color: var(--text2); font-size: 16px; line-height:1.6; max-width: 620px; margin: 0 0 18px; }
.pills{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom: 20px; }
.pill{ display:inline-flex; align-items:center; gap:7px; padding:5px 11px; border-radius:999px;
  font-size:12.5px; font-weight:600; color: var(--text2); border:1px solid var(--border);
  background: rgba(255,255,255,0.03); }
.dot{ width:8px; height:8px; border-radius:50%; background: var(--muted); display:inline-block; }
.dot.on{ background: var(--up); animation: pulse 2s infinite; }
.dot.off{ background: var(--down); }
.dot.warn{ background: var(--warn); }
@keyframes pulse{ 0%{ box-shadow:0 0 0 0 rgba(31,191,117,.55);} 70%{ box-shadow:0 0 0 7px rgba(31,191,117,0);}
  100%{ box-shadow:0 0 0 0 rgba(31,191,117,0);} }
.cta{ display:flex; flex-wrap:wrap; gap:10px; }
.btn{ display:inline-flex; align-items:center; gap:8px; padding: 11px 18px; border-radius: 12px;
  font-weight:700; font-size:14px; text-decoration:none !important; transition: transform .15s, box-shadow .15s; }
.btn.primary{ background: linear-gradient(135deg, #3987e5, #2a6fd0); color:#fff !important;
  box-shadow: 0 8px 24px rgba(57,135,229,0.35); }
.btn.ghost{ color: var(--text) !important; border:1px solid var(--border-strong); background: rgba(255,255,255,0.03); }
.btn:hover{ transform: translateY(-1px); }
.hero-stats{ display:grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hstat{ background: rgba(11,14,20,0.55); border:1px solid var(--border); border-radius:16px; padding: 16px 18px;
  backdrop-filter: blur(6px); }
.hstat .k{ color: var(--muted); font-size:11.5px; font-weight:700; letter-spacing:.07em; text-transform:uppercase; }
.hstat .v{ font-family: var(--mono); font-size: 26px; font-weight:700; color: var(--text); margin-top: 6px; }
.hstat .s{ color: var(--text2); font-size: 12.5px; margin-top: 2px; }

/* ---------- section ---------- */
.sec{ margin: 30px 0 14px; display:flex; align-items:flex-end; justify-content:space-between; gap: 12px; flex-wrap:wrap; }
.sec h3{ font-size: 21px; font-weight: 750; margin:0; padding:0; color: var(--text); }
.sec p{ color: var(--text2); font-size: 14px; margin: 4px 0 0; }
.sec .aside{ color: var(--muted); font-size: 12.5px; }

/* ---------- grid + card ---------- */
.grid{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); }
.grid.wide{ grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.card{ background: var(--surface); border:1px solid var(--border); border-radius:18px; padding: 18px;
  transition: border-color .2s, transform .2s; }
.card:hover{ border-color: rgba(57,135,229,0.38); transform: translateY(-1px); }
.card.glow-long{ box-shadow: inset 0 1px 0 rgba(31,191,117,0.35); border-color: rgba(31,191,117,0.30); }
.card.glow-short{ box-shadow: inset 0 1px 0 rgba(239,93,93,0.35); border-color: rgba(239,93,93,0.28); }
.card-head{ display:flex; align-items:center; justify-content:space-between; gap: 8px; margin-bottom: 8px; }
.sym{ display:flex; align-items:center; gap:10px; font-weight:750; font-size:16px; color: var(--text); }
.coin{ width:30px; height:30px; border-radius:50%; display:inline-grid; place-items:center; font-size:11px;
  font-weight:800; color:#0b0e14; vertical-align: middle; flex: 0 0 auto; letter-spacing:0; }
.sec h3 .coin{ margin-top:-4px; }
.sym small{ display:block; color: var(--muted); font-weight:600; font-size:11.5px; }
.px{ font-family: var(--mono); font-size: 24px; font-weight:700; color: var(--text); margin: 4px 0 2px; }
.chg{ font-family: var(--mono); font-weight:700; font-size: 13px; }
.chg.up{ color: var(--up); } .chg.down{ color: var(--down); } .chg.flat{ color: var(--text2); }
.spark{ display:block; margin: 10px 0 8px; }
.meta{ display:flex; justify-content:space-between; color: var(--text2); font-size:12.5px; gap: 8px; }
.meta b{ font-family: var(--mono); color: var(--text); font-weight:600; }

.badge{ display:inline-flex; align-items:center; gap:5px; padding:4px 9px; border-radius:7px; font-size:11px;
  font-weight:800; letter-spacing:.06em; text-transform:uppercase; white-space:nowrap; }
.badge.long{ background: rgba(31,191,117,.14); color: var(--up); }
.badge.short{ background: rgba(239,93,93,.14); color: var(--down); }
.badge.wait{ background: rgba(255,255,255,.06); color: var(--text2); }
.badge.info{ background: rgba(57,135,229,.16); color: var(--accent-soft); }
.badge.warn{ background: rgba(250,178,25,.14); color: var(--warn); }

.strat{ color: var(--text2); font-size: 12.5px; font-weight:600; margin: 2px 0 10px; }
.why{ color: var(--text); font-size: 14px; line-height: 1.55; margin: 0 0 12px; }
.kv{ display:flex; justify-content:space-between; gap:10px; font-size:13px; padding: 7px 0;
  border-top: 1px dashed var(--border); }
.kv span:first-child{ color: var(--text2); }
.kv span:last-child{ font-family: var(--mono); color: var(--text); font-weight:600; }
.kv .up{ color: var(--up) !important; } .kv .down{ color: var(--down) !important; }
.meter{ margin-top: 6px; }
.meter .bar{ height: 6px; border-radius: 99px; background: rgba(255,255,255,0.07); overflow:hidden; }
.meter .bar i{ display:block; height:100%; border-radius:99px; background: linear-gradient(90deg, #3987e5, #1fbf75); }
.meter .lbl{ display:flex; justify-content:space-between; color: var(--muted); font-size: 11.5px; margin-top: 6px; }

.big{ font-family: var(--mono); font-size: 30px; font-weight:700; color: var(--text); }
.big.up{ color: var(--up); } .big.down{ color: var(--down); }
.cmp{ display:grid; grid-template-columns: 1.4fr 1fr 1fr 0.7fr; gap: 6px 10px; font-size: 13.5px; align-items:center; }
.cmp .h{ color: var(--muted); font-size: 11px; font-weight:700; letter-spacing:.07em; text-transform:uppercase; }
.cmp .n{ font-family: var(--mono); font-weight:600; text-align:right; }
.cmp .best{ color: var(--up); }
.cmp .name{ color: var(--text); font-weight: 600; }
.cmp .name small{ color: var(--muted); font-weight:500; }

.steps{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.step{ background: var(--surface); border:1px solid var(--border); border-radius:18px; padding: 20px; }
.step .num{ width:34px; height:34px; border-radius:10px; display:grid; place-items:center; font-weight:800;
  background: rgba(57,135,229,.14); color: var(--accent-soft); margin-bottom: 12px; font-family: var(--mono); }
.step b{ display:block; color: var(--text); font-size: 15.5px; margin-bottom: 6px; }
.step span{ color: var(--text2); font-size: 13.5px; line-height: 1.55; }

.empty{ text-align:center; padding: 34px 20px; background: var(--surface); border:1px dashed var(--border-strong);
  border-radius: 18px; }
.empty .ico{ font-size: 34px; }
.empty b{ display:block; color: var(--text); font-size: 17px; margin: 8px 0 6px; }
.empty p{ color: var(--text2); font-size: 14px; margin: 0 auto 12px; max-width: 520px; }
.cmd{ display:inline-block; font-family: var(--mono); background: #0b0e14; border:1px solid var(--border-strong);
  color: var(--accent-soft); padding: 8px 14px; border-radius: 10px; font-size: 13.5px; }

.news{ display:block; text-decoration:none !important; }
.news .src{ color: var(--accent-soft); font-weight:700; font-size: 12px; }
.news .t{ color: var(--text); font-weight: 650; font-size: 15px; line-height: 1.45; margin: 8px 0; display:block; }
.news .time{ color: var(--muted); font-size: 12px; }

.disclaimer{ margin-top: 34px; padding: 16px 18px; border-radius: 14px; border:1px solid rgba(250,178,25,0.25);
  background: rgba(250,178,25,0.06); color: var(--text2); font-size: 13px; line-height: 1.6; }
.disclaimer b{ color: var(--warn); }
.foot{ color: var(--muted); font-size: 12px; text-align:center; margin-top: 18px; }

/* ---------- tư vấn ---------- */
.score{ font-family: var(--mono); font-weight:800; font-size: 28px; line-height:1; }
.score.up{ color: var(--up); } .score.down{ color: var(--down); } .score.flat{ color: var(--text2); }
.score small{ font-size: 12px; color: var(--muted); font-weight:600; }
.dbar{ position:relative; height:8px; border-radius:99px; background: rgba(255,255,255,0.07); margin: 8px 0 4px; }
.dbar:before{ content:""; position:absolute; left:50%; top:-3px; bottom:-3px; width:1px; background: var(--border-strong); }
.dbar i{ position:absolute; top:0; bottom:0; border-radius:99px; }
.dbar i.pos{ left:50%; background: var(--up); } .dbar i.neg{ right:50%; background: var(--down); }
.factors{ display:grid; grid-template-columns: 92px 1fr 34px; gap: 4px 10px; align-items:center;
  font-size: 12px; color: var(--text2); margin: 10px 0 12px; }
.factors .dbar{ height:6px; margin:0; }
.factors b{ font-family: var(--mono); color: var(--text); font-weight:600; text-align:right; font-size:11.5px; }
.reasons{ margin: 0 0 10px; padding-left: 18px; color: var(--text); font-size: 13.5px; line-height:1.55; }
.reasons li{ margin-bottom: 3px; }
.zone{ background: rgba(57,135,229,0.10); border:1px solid rgba(57,135,229,0.25); color: var(--accent-soft);
  border-radius: 10px; padding: 8px 12px; font-size: 13px; margin: 0 0 10px; font-weight:600; }
.evidence{ color: var(--muted); font-size: 12px; margin-top: 10px; }
.evidence b{ font-family: var(--mono); }
.mood{ display:grid; grid-template-columns: 1.1fr 1fr 1fr 1fr; gap: 14px; }
.lib{ display:grid; gap:14px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.lib .card h4{ margin: 0 0 4px; font-size: 16px; color: var(--text); padding:0; }
.lib .card code{ font-size: 12px; }
.lib .when{ color: var(--text2); font-size: 13px; line-height:1.55; margin: 6px 0 10px; }
.ai-box{ background: linear-gradient(135deg, rgba(57,135,229,0.10), rgba(31,191,117,0.08));
  border:1px solid rgba(57,135,229,0.3); border-radius: 16px; padding: 16px 18px; color: var(--text);
  font-size: 14px; line-height: 1.65; white-space: pre-wrap; }

@media (max-width: 900px){
  .mood{ grid-template-columns: 1fr 1fr; }
  .hero{ grid-template-columns: 1fr; padding: 24px 20px; }
  .cmp{ grid-template-columns: 1.2fr 1fr 1fr; }
  .cmp .hide-sm{ display:none; }
}
"""

COIN_COLORS = {"BTC": "#f7931a", "ETH": "#8c9eff", "SOL": "#14f195", "BNB": "#f3ba2f",
               "XRP": "#9aa4b2", "ADA": "#4b7bec", "DOGE": "#c2a633"}


# ---------------------------------------------------------------- cài đặt -----------
def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def setup_plotly() -> None:
    axis = dict(gridcolor=GRID, zerolinecolor=AXIS, linecolor=AXIS, tickcolor=AXIS,
                tickfont=dict(color=MUTED, size=11), title=dict(font=dict(color=TEXT2, size=12)))
    pio.templates["quant"] = go.layout.Template(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=TEXT2, size=12), colorway=SERIES,
        xaxis=axis, yaxis=axis,
        hoverlabel=dict(bgcolor=SURFACE2, bordercolor=AXIS, font=dict(family=FONT, color=TEXT, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT2, size=12)),
        title=dict(font=dict(color=TEXT, size=15, family=FONT), x=0.01),
        margin=dict(l=8, r=8, t=36, b=8),
    ))
    pio.templates.default = "plotly_dark+quant"


def chart(fig: go.Figure, height: int | None = None, key: str | None = None) -> None:
    """Vẽ Plotly với theme riêng (theme=None để Streamlit không ghi đè màu)."""
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, theme=None, key=key,
                    config={"displaylogo": False,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]})


# ---------------------------------------------------------------- HTML helpers -------
esc = html.escape


def html_block(s: str) -> None:
    """Render HTML. Gộp thành 1 dòng để Markdown không biến dòng thụt lề thành code block."""
    st.markdown(" ".join(line.strip() for line in s.splitlines() if line.strip()),
                unsafe_allow_html=True)


def fmt_px(v: float | None) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    d = 2 if a >= 10 else 3 if a >= 1 else 5
    return f"${v:,.{d}f}"


def fmt_pct(v: float | None, digits: int = 2, sign: bool = True) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v:+.{digits}f}%" if sign else f"{v:.{digits}f}%"


def trend_cls(v: float | None) -> str:
    if v is None or not np.isfinite(v) or abs(v) < 1e-9:
        return "flat"
    return "up" if v > 0 else "down"


def coin_icon(pair: str) -> str:
    base = pair.split("/")[0]
    color = COIN_COLORS.get(base, "#6da7ec")
    return f'<span class="coin" style="background:{color}">{esc(base[:3])}</span>'


_ids = itertools.count()


def sparkline(values, color: str, width: int = 240, height: int = 46) -> str:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) < 2:
        return ""
    lo, hi = float(v.min()), float(v.max())
    rng = (hi - lo) or 1.0
    xs = np.linspace(0, width, len(v))
    ys = (height - 3) - (v - lo) / rng * (height - 6)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    gid = f"sp{next(_ids)}"
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
            f'width="100%" height="{height}" aria-hidden="true">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity="0.32"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="0,{height} {pts} {width},{height}" fill="url(#{gid})"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


def section(title: str, sub: str | None = None, aside: str | None = None, anchor: str | None = None) -> None:
    a = f' id="{esc(anchor)}"' if anchor else ""
    html_block(f"""<div class="sec"{a}><div><h3>{title}</h3>{f'<p>{sub}</p>' if sub else ''}</div>
                {f'<span class="aside">{aside}</span>' if aside else ''}</div>""")


def badge(text: str, kind: str = "wait") -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def kv(label: str, value: str, cls: str = "") -> str:
    return f'<div class="kv"><span>{esc(label)}</span><span class="{cls}">{value}</span></div>'


def meter(frac: float, left: str, right: str) -> str:
    pct = max(0.0, min(1.0, float(frac) if np.isfinite(frac) else 0.0)) * 100
    return (f'<div class="meter"><div class="bar"><i style="width:{pct:.0f}%"></i></div>'
            f'<div class="lbl"><span>{esc(left)}</span><span>{esc(right)}</span></div></div>')


def dbar(value: float, vmax: float) -> str:
    """Thanh phân kỳ quanh 0: xanh sang phải nếu dương, đỏ sang trái nếu âm."""
    v = float(value) if np.isfinite(value) else 0.0
    w = min(abs(v) / vmax, 1.0) * 50
    return f'<div class="dbar"><i class="{"pos" if v >= 0 else "neg"}" style="width:{w:.1f}%"></i></div>'


def empty_state(icon: str, title: str, body: str, command: str | None = None) -> None:
    cmd = f'<span class="cmd">{esc(command)}</span>' if command else ""
    html_block(f'<div class="empty"><div class="ico">{icon}</div><b>{title}</b><p>{body}</p>{cmd}</div>')
