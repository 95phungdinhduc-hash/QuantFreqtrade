/* Lõi tính toán — bản JavaScript của quant_core (indicators.py, risk.py) và alert_bot.pick_signal.
   Chạy được cả trong trình duyệt lẫn Node (tests/web kiểm tra khớp số với bản Python).
   KHÔNG đặt tên file là quant.js: bộ lọc EasyPrivacy (uBlock, AdGuard…) chặn mọi URL "/quant.js" -> app trắng trang.
   Không nhìn trước tương lai: giá trị tại nến i chỉ dùng dữ liệu tới nến i. */

export const ADF_THRESHOLD = 0.20;           // ADF p < 0.20 -> đi ngang
export const Z_ENTRY = 2.0;                  // dashboard: tín hiệu Mean Reversion
export const TREND_GAP = 1.0;                // dashboard: EMA lệch >= 1% -> xu hướng rõ
export const MODERATE_Z = 2.0, STRONG_Z = 2.5;       // alert bot
export const MODERATE_GAP = 1.5, STRONG_GAP = 2.5;   // alert bot
export const TAKER_FEE = 0.0005;             // phí taker Binance Futures
export const DEFAULT_MIN_NOTIONAL = 21;      // dự phòng khi không đọc được từ sàn
export const MARKET_SMA = 200;               // bộ lọc thị trường: BTC so với SMA200 ngày

const fin = Number.isFinite;

/* ------------------------------------------------------------------ chỉ báo cơ bản */
export function rollingMean(a, w) {
  const out = new Array(a.length).fill(NaN);
  for (let i = w - 1; i < a.length; i++) {
    let s = 0;
    for (let j = i - w + 1; j <= i; j++) s += a[j];
    out[i] = s / w;
  }
  return out;
}

/** Độ lệch chuẩn mẫu (ddof=1) giống pandas rolling().std() */
export function rollingStd(a, w) {
  const out = new Array(a.length).fill(NaN);
  for (let i = w - 1; i < a.length; i++) {
    let s = 0;
    for (let j = i - w + 1; j <= i; j++) s += a[j];
    const m = s / w;
    let v = 0;
    for (let j = i - w + 1; j <= i; j++) v += (a[j] - m) ** 2;
    out[i] = Math.sqrt(v / (w - 1));
  }
  return out;
}

/** ewm(adjust=False): bỏ qua NaN ở đầu chuỗi, giống pandas */
export function ewm(a, alpha) {
  const out = new Array(a.length).fill(NaN);
  let prev = NaN;
  for (let i = 0; i < a.length; i++) {
    const v = a[i];
    if (!fin(v)) { out[i] = prev; continue; }
    prev = fin(prev) ? alpha * v + (1 - alpha) * prev : v;
    out[i] = prev;
  }
  return out;
}
export const ema = (a, span) => ewm(a, 2 / (span + 1));

export function atr(high, low, close, period = 14) {
  const tr = close.map((_, i) => i === 0 ? high[0] - low[0]
    : Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1])));
  return ewm(tr, 1 / period);
}

export function rsi(close, period = 14) {
  const gain = close.map((c, i) => i === 0 ? NaN : Math.max(c - close[i - 1], 0));
  const loss = close.map((c, i) => i === 0 ? NaN : Math.max(close[i - 1] - c, 0));
  const g = ewm(gain, 1 / period), l = ewm(loss, 1 / period);
  return g.map((gv, i) => !fin(l[i]) ? NaN : l[i] === 0 ? 100 : 100 - 100 / (1 + gv / l[i]));
}

export function sma(a, w) { return rollingMean(a, w); }

/* ------------------------------------------------------------------ ADF (giống statsmodels adfuller, autolag AIC) */
/** OLS bằng phân rã QR Householder: trả về hệ số, sai số chuẩn và tổng bình phương phần dư */
function ols(X, y) {
  const n = X.length, k = X[0].length;
  const A = X.map(r => r.slice()), b = y.slice();
  for (let j = 0; j < k; j++) {
    let norm = 0;
    for (let i = j; i < n; i++) norm += A[i][j] ** 2;
    norm = Math.sqrt(norm);
    if (norm === 0) continue;
    const alpha = A[j][j] > 0 ? -norm : norm;
    const v = new Array(n).fill(0);
    v[j] = A[j][j] - alpha;
    for (let i = j + 1; i < n; i++) v[i] = A[i][j];
    let vv = 0;
    for (let i = j; i < n; i++) vv += v[i] ** 2;
    if (vv === 0) continue;
    for (let c = j; c < k; c++) {
      let s = 0;
      for (let i = j; i < n; i++) s += v[i] * A[i][c];
      s = (2 * s) / vv;
      for (let i = j; i < n; i++) A[i][c] -= s * v[i];
    }
    let s = 0;
    for (let i = j; i < n; i++) s += v[i] * b[i];
    s = (2 * s) / vv;
    for (let i = j; i < n; i++) b[i] -= s * v[i];
  }
  // R beta = (Q'y)[0:k]
  const beta = new Array(k).fill(0);
  for (let i = k - 1; i >= 0; i--) {
    let s = b[i];
    for (let c = i + 1; c < k; c++) s -= A[i][c] * beta[c];
    beta[i] = s / A[i][i];
  }
  let ssr = 0;
  for (let i = k; i < n; i++) ssr += b[i] ** 2;
  // (X'X)^-1 = R^-1 R^-T  -> phương sai hệ số j = s² · Σ_l (R^-1)[j][l]²
  const Rinv = Array.from({ length: k }, () => new Array(k).fill(0));
  for (let i = k - 1; i >= 0; i--) {
    Rinv[i][i] = 1 / A[i][i];
    for (let c = i + 1; c < k; c++) {
      let s = 0;
      for (let m = i + 1; m <= c; m++) s += A[i][m] * Rinv[m][c];
      Rinv[i][c] = -s / A[i][i];
    }
  }
  const s2 = ssr / (n - k);
  const se = beta.map((_, j) => { let s = 0; for (let l = j; l < k; l++) s += Rinv[j][l] ** 2; return Math.sqrt(s2 * s); });
  return { beta, se, ssr, n, k };
}

/** Hàm phân phối chuẩn (độ chính xác ~1e-7) */
export function normCdf(x) {
  const z = Math.abs(x) / Math.SQRT2, t = 1 / (1 + 0.5 * z);
  const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 +
    t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 +
    t * (-0.82215223 + t * 0.17087277)))))))));
  return x >= 0 ? 1 - r / 2 : r / 2;
}

/** MacKinnon (1994) p-value cho hồi quy có hằng số, N=1 — hằng số lấy từ statsmodels.tsa.adfvalues */
export function mackinnonP(t) {
  if (t > 2.74) return 1;
  if (t < -18.83) return 0;
  const c = t <= -1.61 ? [2.1659, 1.4412, 0.038269] : [1.7339, 0.93202, -0.12745, -0.010368];
  let p = 0;
  for (let i = c.length - 1; i >= 0; i--) p = p * t + c[i];
  return normCdf(p);
}

/** p-value kiểm định ADF. < 0.05 => chuỗi dừng (đi ngang) */
export function adfPvalue(values) {
  const x = values.filter(fin);
  const n = x.length;
  if (n < 20 || x.every(v => Math.abs(v - x[0]) <= 1e-8 + 1e-5 * Math.abs(x[0]))) return NaN;
  let maxlag = Math.ceil(12 * Math.pow(n / 100, 0.25));
  maxlag = Math.min(Math.floor(n / 2) - 2, maxlag);
  if (maxlag < 0) return NaN;
  const dx = x.slice(1).map((v, i) => v - x[i]);           // dx[i] = x[i+1] - x[i]

  const design = (lags, start) => {                         // hàng i = start..n-2
    const X = [], y = [];
    for (let i = start; i <= n - 2; i++) {
      const row = [1, x[i]];
      for (let j = 1; j <= lags; j++) row.push(dx[i - j]);
      X.push(row);
      y.push(dx[i]);
    }
    return { X, y };
  };
  // chọn số lag theo AIC trên cùng số quan sát (giống _autolag)
  let best = 0, bestAic = Infinity;
  for (let L = 0; L <= maxlag; L++) {
    const { X, y } = design(L, maxlag);
    const r = ols(X, y);
    const llf = -r.n / 2 * (Math.log(2 * Math.PI) + Math.log(r.ssr / r.n) + 1);
    const aic = -2 * llf + 2 * r.k;
    if (aic < bestAic) { bestAic = aic; best = L; }
  }
  const { X, y } = design(best, best);
  const r = ols(X, y);
  return mackinnonP(r.beta[1] / r.se[1]);
}

/** ADF trượt: tính mỗi `step` nến trên `window` nến gần nhất, neo theo thời gian (giống rolling_adf_pvalue) */
export function rollingAdf(close, times, window = 200, step = 12) {
  const n = close.length, out = new Array(n).fill(NaN);
  if (n < 2) return out;
  const secs = times.map(t => Math.floor(t / 1000));
  const diffs = secs.slice(1).map((s, i) => s - secs[i]).sort((a, b) => a - b);
  const mid = diffs.length >> 1;
  const candle = Math.trunc(diffs.length % 2 ? diffs[mid] : (diffs[mid - 1] + diffs[mid]) / 2) || 1;
  let last = NaN;
  for (let i = 0; i < n; i++) {
    if (i >= window - 1 && Math.floor(secs[i] / candle) % step === 0) last = adfPvalue(close.slice(i - window + 1, i + 1));
    out[i] = last;
  }
  return out;
}

/** Toàn bộ chỉ báo dùng chung (giống add_quant_indicators). candles: [{t,o,h,l,c,v}] */
export function addIndicators(candles, { window = 50, emaFast = 20, emaSlow = 50, adfWindow = 200, adfStep = 12 } = {}) {
  const close = candles.map(k => k.c), high = candles.map(k => k.h), low = candles.map(k => k.l);
  const mean = rollingMean(close, window), std = rollingStd(close, window);
  const ef = ema(close, emaFast), es = ema(close, emaSlow);
  const at = atr(high, low, close), rs = rsi(close);
  const adf = rollingAdf(close, candles.map(k => k.t), adfWindow, adfStep);
  return candles.map((k, i) => ({
    ...k,
    mean: mean[i], std: std[i],
    z: std[i] > 0 ? (k.c - mean[i]) / std[i] : NaN,
    emaFast: ef[i], emaSlow: es[i], gap: (ef[i] - es[i]) / es[i] * 100,
    atr: at[i], rsi: rs[i], adf: adf[i],
  }));
}

/* ------------------------------------------------------------------ quản lý vốn (risk.plan_position) */
export function planPosition({ capital, riskPct, entry, std, mean = null, isLong = true,
                               slMult = 1.0, tpMult = 1.5, minNotional = 0 }) {
  let sl, tp;
  if (isLong) {
    sl = entry - slMult * std; tp = entry + tpMult * std;
    if (mean != null) tp = Math.max(mean, tp);
  } else {
    sl = entry + slMult * std; tp = entry - tpMult * std;
    if (mean != null) tp = Math.min(mean, tp);
  }
  const riskUsd = capital * riskPct / 100;
  const stopDist = entry > 0 ? Math.abs(entry - sl) / entry : 0;
  let position = stopDist > 0 ? riskUsd / stopDist : 0;
  position = Math.max(position, minNotional);
  const rr = Math.abs(entry - sl) > 0 ? Math.abs(tp - entry) / Math.abs(entry - sl) : 0;
  return {
    entry, stopLoss: sl, takeProfit: tp, riskUsd: position * stopDist, positionUsd: position,
    coinAmount: entry > 0 ? position / entry : 0, stopDistPct: stopDist, rr,
    leverageNeeded: capital > 0 ? Math.max(1, Math.round(position / capital * 10) / 10) : 1,
  };
}

/* ------------------------------------------------------------------ tín hiệu */
/** Giống alert_bot.pick_signal (legacy=False). null = không có tín hiệu */
export function pickSignal(r) {
  const ranging = r.adf < ADF_THRESHOLD;   // NaN -> false, giống Python
  if (ranging && Math.abs(r.z) >= MODERATE_Z)
    return { strategy: 'Mean Reversion', isLong: r.z < 0, strong: Math.abs(r.z) >= STRONG_Z,
             slMult: 2.0, tpMult: 1.5, useMean: true, leverage: Math.abs(r.z) >= 3 ? 5 : 2 };
  if (!ranging && Math.abs(r.gap) >= MODERATE_GAP)
    return { strategy: 'Trend Following', isLong: r.gap > 0, strong: Math.abs(r.gap) >= STRONG_GAP,
             slMult: 2.0, tpMult: 3.0, useMean: false, leverage: 3 };
  return null;
}

/** Bộ lọc thị trường giống các bot: BTC trên SMA200 ngày -> chỉ Long, dưới -> chỉ Short */
export const marketAllows = (isLong, regime) => regime == null || regime.up === isLong;

export function btcRegime(dailyCandles) {
  if (!dailyCandles || dailyCandles.length < MARKET_SMA) return null;
  const close = dailyCandles.map(k => k.c);
  const s = sma(close, MARKET_SMA);
  const c = close.at(-1), m = s.at(-1);
  return { up: c > m, close: c, sma: m, gap: (c / m - 1) * 100, t: dailyCandles.at(-1).t };
}

/** Tình trạng dạng thẻ cho màn Tổng quan (giống dashboard signal_of) */
export function regimeState(r) {
  if (fin(r.adf) && r.adf < ADF_THRESHOLD) {
    if (r.z <= -Z_ENTRY) return { kind: 'long', label: 'Quá bán', mr: true };
    if (r.z >= Z_ENTRY) return { kind: 'short', label: 'Quá mua', mr: true };
    return { kind: 'wait', label: 'Đi ngang', mr: true, progress: Math.abs(r.z) / Z_ENTRY };
  }
  if (r.gap > TREND_GAP) return { kind: 'long', label: 'Xu hướng tăng', mr: false };
  if (r.gap < -TREND_GAP) return { kind: 'short', label: 'Xu hướng giảm', mr: false };
  return { kind: 'wait', label: 'Chưa rõ', mr: false, progress: Math.abs(r.gap) / TREND_GAP };
}

/** Kế hoạch đầy đủ cho 1 coin: Spot + Futures, giống tin nhắn alert bot */
export function buildPlan(r, sig, { capital, riskPct, minNotional = DEFAULT_MIN_NOTIONAL, maxLeverage = 5 }) {
  const mean = sig.useMean ? r.mean : null;
  const base = { capital, riskPct, entry: r.c, std: r.std, mean, isLong: sig.isLong, slMult: sig.slMult, tpMult: sig.tpMult };
  const plan = planPosition(base);
  const fplan = planPosition({ ...base, minNotional });
  const leverage = Math.min(sig.leverage, maxLeverage);
  let spotUsd = plan.positionUsd, spotCapped = false;
  if (spotUsd > capital) { spotUsd = capital; spotCapped = true; }
  return {
    plan, fplan, leverage,
    spot: sig.isLong ? { usd: spotUsd, qty: spotUsd / r.c, capped: spotCapped,
                         maxLoss: spotCapped ? capital * plan.stopDistPct : plan.riskUsd } : null,
    margin: fplan.positionUsd / leverage,
    fee2way: fplan.positionUsd * TAKER_FEE * 2,
    forcedMin: fplan.positionUsd > plan.positionUsd,
  };
}
