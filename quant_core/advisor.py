"""
Bộ tư vấn chiến lược theo quy tắc (rule-based) — tổng hợp MỌI phân tích của hệ thống thành:
  1. Điểm đánh giá từng coin (-100 … +100) từ 5 nhóm yếu tố: xu hướng, động lượng,
     định giá thống kê (Z-Score), biến động, tin tức.
  2. Chế độ thị trường (ADF + EMA khung 4h) và "playbook" chiến lược phù hợp,
     kèm vùng giá vào, cắt lỗ, chốt lời, khối lượng theo % rủi ro.
  3. Phân bổ danh mục theo hồ sơ rủi ro (thận trọng / cân bằng / mạo hiểm):
     tỷ trọng ∝ điểm / biến động, có trần mỗi coin và tỷ lệ tiền mặt tối thiểu.

Đây là CÔNG CỤ PHÂN TÍCH: mọi kết luận đều suy ra từ số liệu và quy tắc cố định bên dưới,
không phải lời khuyên đầu tư cá nhân. Không dùng dữ liệu tương lai.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quant_core.indicators import add_quant_indicators, donchian, ema, rsi
from quant_core.risk import PositionPlan, plan_position

ADF_THRESHOLD = 0.20
Z_ENTRY = 2.0

# Trọng số 5 nhóm yếu tố (tổng 100). Mỗi yếu tố chấm từ -2 đến +2.
WEIGHTS = {"trend": 35, "momentum": 20, "value": 20, "volatility": 10, "sentiment": 15}
FACTOR_LABELS = {"trend": "Xu hướng", "momentum": "Động lượng", "value": "Định giá (Z)",
                 "volatility": "Độ ổn định", "sentiment": "Tin tức"}

PROFILES = {
    "than_trong": {"label": "Thận trọng", "risk_pct": 0.75, "max_leverage": 1, "cash_min": 0.50,
                   "max_weight": 0.20, "futures": False,
                   "desc": "Ưu tiên giữ vốn. Rủi ro 0,75%/lệnh, chỉ Spot, ít nhất 50% tiền mặt."},
    "can_bang": {"label": "Cân bằng", "risk_pct": 1.5, "max_leverage": 2, "cash_min": 0.30,
                 "max_weight": 0.30, "futures": True,
                 "desc": "Rủi ro 1,5%/lệnh (mặc định của bot), Futures tối đa x2, ít nhất 30% tiền mặt."},
    "mao_hiem": {"label": "Mạo hiểm", "risk_pct": 2.5, "max_leverage": 3, "cash_min": 0.10,
                 "max_weight": 0.40, "futures": True,
                 "desc": "Rủi ro 2,5%/lệnh, Futures tối đa x3, ít nhất 10% tiền mặt. Biến động tài khoản lớn."},
}

# Playbook -> chiến lược Freqtrade tương ứng để kiểm chứng bằng backtest
STRATEGY_OF = {
    "mean_rev": "QuantHybridStrategy", "trend": "QuantHybridStrategy",
    "breakout": "QuantBreakoutStrategy", "dca": "QuantSmartDCAStrategy",
    "short": "QuantHybridFuturesStrategy", "wait": None,
}


@dataclass
class Assessment:
    pair: str
    price: float
    date: pd.Timestamp
    regime: str                     # "range" | "up" | "down" | "unclear"
    regime_label: str
    factors: dict[str, float]       # điểm -2..+2 từng yếu tố
    score: float                    # -100..+100
    stance: str                     # nhãn hành động ngắn
    kind: str                       # "long" | "short" | "wait" (để tô màu)
    playbook: str                   # khoá trong STRATEGY_OF
    playbook_label: str
    reasons: list[str] = field(default_factory=list)
    zone: str = ""                  # vùng giá gợi ý (lệnh chờ)
    plan: PositionPlan | None = None
    metrics: dict[str, float] = field(default_factory=dict)


# ------------------------------------------------------------------ chỉ báo
def enrich(df: pd.DataFrame, window: int = 50) -> pd.DataFrame:
    """Thêm toàn bộ chỉ báo cần cho tư vấn vào nến 1h (cột date/open/high/low/close/volume)."""
    d = add_quant_indicators(df.reset_index(drop=True), window=window)
    d["rsi"] = rsi(d["close"])
    d["dc_high"], d["dc_low"] = donchian(d, 48)
    d["ema200"] = ema(d["close"], 200)
    # EMA50 khung 4h dựng lại từ nến 1h, gắn vào nến 1h CUỐI của mỗi nến 4h (giống cách
    # Freqtrade ghép @informative("4h")) -> chỉ dùng nến 4h đã đóng, không look-ahead
    h4 = d.set_index("date")["close"].resample("4h", label="left", closed="left").last().dropna()
    ema4 = ema(h4, 50)
    ema4.index = ema4.index + pd.Timedelta(hours=4) - pd.Timedelta(hours=1)
    d["ema_slow_4h"] = ema4.reindex(d["date"], method="ffill").to_numpy()
    d["roc_7d"] = d["close"].pct_change(168) * 100
    vol24 = d["log_return"].rolling(24).std()
    d["vol_ann"] = vol24 * np.sqrt(24 * 365) * 100
    d["vol_pct"] = vol24.rolling(720, min_periods=48).rank(pct=True)  # vị trí biến động trong ~30 ngày
    return d


# ------------------------------------------------------------------ chấm điểm
def _clip(x: float, lo: float = -2.0, hi: float = 2.0) -> float:
    return float(np.clip(x, lo, hi)) if np.isfinite(x) else 0.0


def score_factors(r: pd.Series, news_score: float = 0.0) -> dict[str, float]:
    trend = (1 if r["close"] > r["ema_slow_4h"] else -1) + (1 if r["ema_fast"] > r["ema_slow"] else -1) \
        if pd.notna(r["ema_slow_4h"]) else (1 if r["ema_fast"] > r["ema_slow"] else -1)
    return {
        "trend": _clip(trend),
        "momentum": _clip(r["roc_7d"] / 5.0),            # +10%/tuần => +2
        "value": _clip(-r["z_score"] / 1.25),             # rẻ (Z âm) => điểm dương
        "volatility": _clip((0.5 - r["vol_pct"]) * 4) if pd.notna(r["vol_pct"]) else 0.0,
        "sentiment": _clip(news_score / 3.0),
    }


def total_score(factors: dict[str, float]) -> float:
    return sum(WEIGHTS[k] * v for k, v in factors.items()) / 2.0


def regime_of(r: pd.Series) -> tuple[str, str]:
    if pd.notna(r["adf_p"]) and r["adf_p"] < ADF_THRESHOLD:
        return "range", "Đi ngang"
    above4h = pd.notna(r["ema_slow_4h"]) and r["close"] > r["ema_slow_4h"]
    if above4h and r["ema_gap_pct"] > 0:
        return "up", "Xu hướng tăng"
    if (not above4h) and r["ema_gap_pct"] < 0:
        return "down", "Xu hướng giảm"
    return "unclear", "Chưa rõ xu hướng"


# ------------------------------------------------------------------ tư vấn 1 coin
def assess(pair: str, d: pd.DataFrame, news_score: float = 0.0, capital: float = 1000.0,
           risk_pct: float = 1.5, allow_futures: bool = True, price: float | None = None) -> Assessment:
    """Đánh giá 1 coin từ DataFrame đã qua `enrich` (dùng nến cuối cùng ĐÃ ĐÓNG)."""
    r = d.iloc[-1]
    px = float(price or r["close"])
    std, mean = float(r["rolling_std"]), float(r["rolling_mean"])
    factors = score_factors(r, news_score)
    score = total_score(factors)
    regime, regime_label = regime_of(r)
    z, adf, gap, rs = float(r["z_score"]), float(r["adf_p"]), float(r["ema_gap_pct"]), float(r["rsi"])
    reasons: list[str] = []
    zone, plan = "", None
    fmt = (lambda v: f"{v:,.2f}") if px >= 10 else (lambda v: f"{v:,.4f}")

    if regime == "range":
        reasons.append(f"ADF = {adf:.2f} < {ADF_THRESHOLD} → giá dao động quanh trung bình, phù hợp đánh hồi quy.")
        if z <= -Z_ENTRY:
            stance, kind, pb, pbl = "Mua (hồi quy)", "long", "mean_rev", "Mean Reversion — mua vùng quá bán"
            reasons.append(f"Z-Score {z:+.2f}σ: giá thấp bất thường so với trung bình {fmt(mean)}.")
            plan = plan_position(capital, risk_pct, px, std, mean, is_long=True, sl_std_mult=2.0)
        elif z >= Z_ENTRY:
            stance, kind = "Chốt lời / Short", "short"
            pb, pbl = ("short", "Mean Reversion — Short vùng quá mua (Futures)") if allow_futures \
                else ("wait", "Chốt lời Spot, không mua mới")
            reasons.append(f"Z-Score {z:+.2f}σ: giá cao bất thường, dễ quay về {fmt(mean)}.")
            if allow_futures:
                plan = plan_position(capital, risk_pct, px, std, mean, is_long=False, sl_std_mult=2.0)
        else:
            stance, kind, pb, pbl = "Chờ vùng giá đẹp", "wait", "mean_rev", "Mean Reversion — đặt lệnh chờ"
            zone = f"Mua quanh {fmt(mean - 2 * std)} (−2σ) · Bán quanh {fmt(mean + 2 * std)} (+2σ)"
            reasons.append(f"Z-Score {z:+.2f}σ còn trong vùng bình thường — chưa có lợi thế thống kê.")
    elif regime == "up":
        reasons.append(f"Giá trên EMA50 khung 4h và EMA20 > EMA50 ({gap:+.2f}%) → xu hướng tăng.")
        breakout = pd.notna(r["dc_high"]) and r["close"] > r["dc_high"]
        if breakout:
            stance, kind, pb, pbl = "Mua theo đà", "long", "breakout", "Breakout — phá đỉnh 48 giờ"
            reasons.append(f"Giá vừa vượt đỉnh 48 giờ ({fmt(float(r['dc_high']))}) — lực mua mạnh.")
            plan = plan_position(capital, risk_pct, px, float(r["atr"]) / 2, None, is_long=True,
                                 sl_std_mult=5.0, tp_std_mult=10.0)  # SL 2.5×ATR, TP 5×ATR
        elif z < 0.5:
            stance, kind, pb, pbl = "Mua khi điều chỉnh", "long", "trend", "Trend Following — mua nhịp điều chỉnh"
            reasons.append(f"Giá đang điều chỉnh về gần trung bình (Z {z:+.2f}σ) trong xu hướng tăng.")
            plan = plan_position(capital, risk_pct, px, std, None, is_long=True, sl_std_mult=2.0,
                                 tp_std_mult=3.0)
        else:
            stance, kind, pb, pbl = "Chờ điều chỉnh", "wait", "trend", "Trend Following — chờ giá về EMA20"
            zone = f"Chờ mua quanh EMA20 ≈ {fmt(float(r['ema_fast']))}"
            reasons.append(f"Giá đã cao (Z {z:+.2f}σ, RSI {rs:.0f}) — mua lúc này dễ đu đỉnh.")
    elif regime == "down":
        reasons.append(f"Giá dưới EMA50 khung 4h và EMA20 < EMA50 ({gap:+.2f}%) → xu hướng giảm.")
        if z <= -Z_ENTRY and rs < 30:
            stance, kind, pb, pbl = "Tích luỹ từng phần", "wait", "dca", "Smart DCA — chia nhỏ vốn, chỉ dài hạn"
            reasons.append(f"Quá bán sâu (Z {z:+.2f}σ, RSI {rs:.0f}) nhưng xu hướng vẫn giảm: "
                           "chỉ mua phần nhỏ, chia nhiều lần.")
        elif allow_futures and z > -1:
            stance, kind, pb, pbl = "Short khi hồi", "short", "short", "Trend Following — Short (Futures)"
            zone = f"Chờ Short khi giá hồi về EMA20 ≈ {fmt(float(r['ema_fast']))}"
            reasons.append("Spot: đứng ngoài. Futures: chờ nhịp hồi lên để Short thuận xu hướng.")
            plan = plan_position(capital, risk_pct, px, std, None, is_long=False, sl_std_mult=2.0,
                                 tp_std_mult=3.0)
        else:
            stance, kind, pb, pbl = "Đứng ngoài", "wait", "wait", "Đứng ngoài — không bắt dao rơi"
            reasons.append("Không mua ngược xu hướng giảm khi chưa có tín hiệu đảo chiều.")
    else:
        stance, kind, pb, pbl = "Đứng ngoài", "wait", "wait", "Đứng ngoài — chờ tín hiệu rõ"
        reasons.append(f"ADF {adf:.2f} và EMA ({gap:+.2f}%) chưa cho thấy xu hướng hay vùng đi ngang rõ ràng.")

    best = max(factors, key=lambda k: WEIGHTS[k] * factors[k])
    worst = min(factors, key=lambda k: WEIGHTS[k] * factors[k])
    if factors[best] > 0:
        reasons.append(f"Điểm mạnh: {FACTOR_LABELS[best].lower()}.")
    if factors[worst] < 0:
        reasons.append(f"Điểm yếu: {FACTOR_LABELS[worst].lower()}.")

    return Assessment(
        pair=pair, price=px, date=r["date"], regime=regime, regime_label=regime_label,
        factors=factors, score=score, stance=stance, kind=kind, playbook=pb, playbook_label=pbl,
        reasons=reasons, zone=zone, plan=plan,
        metrics={"z": z, "adf": adf, "gap": gap, "rsi": rs, "roc_7d": float(r["roc_7d"]),
                 "vol_ann": float(r["vol_ann"]), "atr_pct": float(r["atr"]) / px * 100},
    )


# ------------------------------------------------------------------ danh mục
def mood(scores: list[float]) -> tuple[str, str]:
    """Nhiệt kế thị trường từ điểm trung bình."""
    s = float(np.mean(scores)) if scores else 0.0
    if s <= -40:
        return "Rất tiêu cực", "short"
    if s <= -15:
        return "Tiêu cực", "short"
    if s < 15:
        return "Trung lập", "wait"
    if s < 40:
        return "Tích cực", "long"
    return "Rất tích cực", "long"


def allocate(assessments: list[Assessment], profile_key: str, capital: float) -> pd.DataFrame:
    """
    Phân bổ vốn đề xuất cho phần SPOT:
      * chỉ coin có điểm > 0 và không ở xu hướng giảm
      * tỷ trọng thô ∝ điểm / biến động năm  (coin càng biến động càng ít tiền)
      * mỗi coin tối đa max_weight, tổng đầu tư tối đa (1 - cash_min) × (điểm TB / 100 * 2, ≤ 1)
      * phần còn lại giữ USDT
    """
    prof = PROFILES[profile_key]
    picks = [a for a in assessments if a.score > 0 and a.regime != "down"]
    rows = []
    if picks:
        raw = np.array([a.score / max(a.metrics["vol_ann"], 1.0) for a in picks])
        w = raw / raw.sum()
        conviction = min(1.0, float(np.mean([a.score for a in picks])) / 50.0)
        invest = (1 - prof["cash_min"]) * conviction
        w = np.minimum(w * invest, prof["max_weight"])
        for a, wi in zip(picks, w):
            rows.append({"Tài sản": a.pair, "Tỷ trọng": float(wi), "USDT": float(wi) * capital,
                         "Điểm": a.score, "Lý do": a.stance})
    cash = 1 - sum(r["Tỷ trọng"] for r in rows)
    rows.append({"Tài sản": "USDT (tiền mặt)", "Tỷ trọng": cash, "USDT": cash * capital,
                 "Điểm": None, "Lý do": "Dự phòng rủi ro & chờ cơ hội"})
    return pd.DataFrame(rows)


def correlated_pairs(returns: dict[str, pd.Series], threshold: float = 0.85) -> list[tuple[str, str, float]]:
    if len(returns) < 2:
        return []
    c = pd.DataFrame(returns).corr()
    out = []
    cols = list(c.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if c.loc[a, b] >= threshold:
                out.append((a, b, float(c.loc[a, b])))
    return out
