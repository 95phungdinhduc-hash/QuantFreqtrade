"""
Giao diện dashboard: bảng màu, CSS, template Plotly và các khối HTML dùng chung.

Mọi màu nằm ở 1 chỗ (đầu file) -> muốn đổi giao diện chỉ cần sửa ở đây.
Màu chuỗi dữ liệu (SERIES) lấy theo thứ tự cố định từ bảng màu đã kiểm định
cho người mù màu (dark mode), không tự sinh màu ngẫu nhiên.
"""

from __future__ import annotations

import html
import itertools
from pathlib import Path

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

_HERE = Path(__file__).resolve().parent
CSS = (_HERE / "theme.css").read_text(encoding="utf-8")   # theme "Aurora Glass"
FX_JS = (_HERE / "fx.js").read_text(encoding="utf-8")     # hiệu ứng chuyển động

COIN_COLORS = {"BTC": "#f7931a", "ETH": "#8c9eff", "SOL": "#14f195", "BNB": "#f3ba2f",
               "XRP": "#9aa4b2", "ADA": "#4b7bec", "DOGE": "#c2a633"}


# ---------------------------------------------------------------- cài đặt -----------
def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    # JS chạy ngay trong trang (không iframe); fx.js tự chặn chạy lặp khi Streamlit vẽ lại.
    st.html(f'<div id="qfx-boot"></div><script>{FX_JS}</script>', unsafe_allow_javascript=True)


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
            f'width="100%" height="{height}" aria-hidden="true" style="filter:drop-shadow(0 4px 10px {color}55)">'
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


def tip(text: str, down: bool = False, right: bool = False) -> str:
    """Biểu tượng "?" — rê chuột (hoặc chạm trên điện thoại) để hiện giải thích."""
    cls = "tip" + (" down" if down else "") + (" right" if right else "")
    return f'<span class="{cls}" tabindex="0" data-tip="{esc(text, quote=True)}">?</span>'


def kv(label: str, value: str, cls: str = "", help: str | None = None) -> str:
    t = tip(help) if help else ""
    return f'<div class="kv"><span>{esc(label)}{t}</span><span class="{cls}">{value}</span></div>'


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
