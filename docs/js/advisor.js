/* Bộ tư vấn chiến lược theo quy tắc — bản JavaScript của quant_core/advisor.py (tab 🧭 Tư vấn).
   Điểm -100…+100 từ 5 nhóm yếu tố, chế độ thị trường (ADF + EMA 4h), playbook + kế hoạch lệnh,
   phân bổ vốn theo hồ sơ rủi ro. Không dùng dữ liệu tương lai. Không phải lời khuyên đầu tư. */
import { ADF_THRESHOLD, Z_ENTRY, addIndicators, donchian, ema, planPosition, logReturns } from './indicators.js';

const fin = Number.isFinite;
const H1 = 3600e3, H4 = 4 * H1;

export const WEIGHTS = { trend: 35, momentum: 20, value: 20, volatility: 10, sentiment: 15 };
export const FACTOR_LABELS = { trend: 'Xu hướng', momentum: 'Động lượng', value: 'Định giá (Z)',
                               volatility: 'Độ ổn định', sentiment: 'Tin tức' };

export const PROFILES = {
  than_trong: { label: 'Thận trọng', risk_pct: 0.75, max_leverage: 1, cash_min: 0.50, max_weight: 0.20, futures: false,
                desc: 'Ưu tiên giữ vốn. Rủi ro 0,75%/lệnh, chỉ Spot, ít nhất 50% tiền mặt.' },
  can_bang: { label: 'Cân bằng', risk_pct: 1.5, max_leverage: 2, cash_min: 0.30, max_weight: 0.30, futures: true,
              desc: 'Rủi ro 1,5%/lệnh (mặc định của bot), Futures tối đa x2, ít nhất 30% tiền mặt.' },
  mao_hiem: { label: 'Mạo hiểm', risk_pct: 2.5, max_leverage: 3, cash_min: 0.10, max_weight: 0.40, futures: true,
              desc: 'Rủi ro 2,5%/lệnh, Futures tối đa x3, ít nhất 10% tiền mặt. Biến động tài khoản lớn.' },
};

export const STRATEGY_OF = { mean_rev: 'QuantHybridStrategy', trend: 'QuantHybridStrategy',
  breakout: 'QuantBreakoutStrategy', dca: 'QuantSmartDCAStrategy', short: 'QuantHybridFuturesStrategy', wait: null };

/** Độ lệch chuẩn mẫu trượt, bỏ qua cửa sổ có NaN (giống pandas rolling(w).std()) */
function rollStd(a, w) {
  const out = new Array(a.length).fill(NaN);
  for (let i = w - 1; i < a.length; i++) {
    let s = 0, ok = true;
    for (let j = i - w + 1; j <= i; j++) { if (!fin(a[j])) { ok = false; break; } s += a[j]; }
    if (!ok) continue;
    const m = s / w;
    let v = 0;
    for (let j = i - w + 1; j <= i; j++) v += (a[j] - m) ** 2;
    out[i] = Math.sqrt(v / (w - 1));
  }
  return out;
}

/** rolling(w, min_periods).rank(pct=True): hạng (trung bình khi bằng nhau) của giá trị cuối trong cửa sổ ÷ số phần tử */
function rollRankPct(a, w, minPeriods) {
  const out = new Array(a.length).fill(NaN);
  for (let i = 0; i < a.length; i++) {
    if (!fin(a[i])) continue;
    let n = 0, less = 0, eq = 0;
    for (let j = Math.max(0, i - w + 1); j <= i; j++) {
      const v = a[j];
      if (!fin(v)) continue;
      n++;
      if (v < a[i]) less++; else if (v === a[i]) eq++;
    }
    if (n >= minPeriods) out[i] = (less + (eq + 1) / 2) / n;
  }
  return out;
}

/** Thêm toàn bộ chỉ báo tư vấn vào nến 1h ĐÃ ĐÓNG (giống advisor.enrich) */
export function enrich(candles, window = 50) {
  const rows = addIndicators(candles, { window });
  const close = candles.map(k => k.c);
  const [dcHigh, dcLow] = donchian(candles.map(k => k.h), candles.map(k => k.l), 48);
  const e200 = ema(close, 200);
  // EMA50 khung 4h dựng từ nến 1h, gắn vào nến 1h CUỐI của mỗi nến 4h -> chỉ dùng nến 4h đã đóng
  const groups = new Map();
  for (const k of candles) groups.set(Math.floor(k.t / H4) * H4, k.c);   // giữ giá đóng cửa cuối của mỗi nhóm 4h
  const starts = [...groups.keys()].sort((a, b) => a - b);
  const e4 = ema(starts.map(s => groups.get(s)), 50);
  const lr = logReturns(close);
  const vol24 = rollStd(lr, 24);
  const volPct = rollRankPct(vol24, 720, 48);
  let g = -1;
  return rows.map((r, i) => {
    while (g + 1 < starts.length && starts[g + 1] + H4 - H1 <= r.t) g++;
    return {
      ...r, dcHigh: dcHigh[i], dcLow: dcLow[i], ema200: e200[i],
      emaSlow4h: g >= 0 ? e4[g] : NaN,
      roc7d: i >= 168 ? (close[i] / close[i - 168] - 1) * 100 : NaN,
      volAnn: vol24[i] * Math.sqrt(24 * 365) * 100, volPct: volPct[i], logRet: lr[i],
    };
  });
}

const clip = (x, lo = -2, hi = 2) => fin(x) ? Math.min(hi, Math.max(lo, x)) : 0;

export function scoreFactors(r, newsScore = 0) {
  const trend = fin(r.emaSlow4h)
    ? (r.c > r.emaSlow4h ? 1 : -1) + (r.emaFast > r.emaSlow ? 1 : -1)
    : (r.emaFast > r.emaSlow ? 1 : -1);
  return {
    trend: clip(trend),
    momentum: clip(r.roc7d / 5),
    value: clip(-r.z / 1.25),
    volatility: fin(r.volPct) ? clip((0.5 - r.volPct) * 4) : 0,
    sentiment: clip(newsScore / 3),
  };
}
export const totalScore = f => Object.entries(f).reduce((s, [k, v]) => s + WEIGHTS[k] * v, 0) / 2;

export function regimeOf(r) {
  if (fin(r.adf) && r.adf < ADF_THRESHOLD) return ['range', 'Đi ngang'];
  const above4h = fin(r.emaSlow4h) && r.c > r.emaSlow4h;
  if (above4h && r.gap > 0) return ['up', 'Xu hướng tăng'];
  if (!above4h && r.gap < 0) return ['down', 'Xu hướng giảm'];
  return ['unclear', 'Chưa rõ xu hướng'];
}

const num = (v, d) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const sg = (v, d = 2) => (v >= 0 ? '+' : '') + v.toFixed(d);

/** Đánh giá 1 coin từ hàng đã qua enrich (dùng nến cuối ĐÃ ĐÓNG) — giống advisor.assess */
export function assess(pair, rows, { newsScore = 0, capital = 1000, riskPct = 1.5, allowFutures = true, price = null } = {}) {
  const r = rows.at(-1);
  const px = price || r.c;
  const std = r.std, mean = r.mean;
  const factors = scoreFactors(r, newsScore);
  const score = totalScore(factors);
  const [regime, regimeLabel] = regimeOf(r);
  const z = r.z, adf = r.adf, gap = r.gap, rs = r.rsi;
  const reasons = [];
  let zone = '', plan = null, stance, kind, pb, pbl;
  const fmt = v => num(v, px >= 10 ? 2 : 4);
  const P = o => planPosition({ capital, riskPct, entry: px, std, ...o });

  if (regime === 'range') {
    reasons.push(`ADF = ${adf.toFixed(2)} < ${ADF_THRESHOLD} → giá dao động quanh trung bình, phù hợp đánh hồi quy.`);
    if (z <= -Z_ENTRY) {
      [stance, kind, pb, pbl] = ['Mua (hồi quy)', 'long', 'mean_rev', 'Mean Reversion — mua vùng quá bán'];
      reasons.push(`Z-Score ${sg(z)}σ: giá thấp bất thường so với trung bình ${fmt(mean)}.`);
      plan = P({ mean, isLong: true, slMult: 2.0 });
    } else if (z >= Z_ENTRY) {
      [stance, kind] = ['Chốt lời / Short', 'short'];
      [pb, pbl] = allowFutures ? ['short', 'Mean Reversion — Short vùng quá mua (Futures)'] : ['wait', 'Chốt lời Spot, không mua mới'];
      reasons.push(`Z-Score ${sg(z)}σ: giá cao bất thường, dễ quay về ${fmt(mean)}.`);
      if (allowFutures) plan = P({ mean, isLong: false, slMult: 2.0 });
    } else {
      [stance, kind, pb, pbl] = ['Chờ vùng giá đẹp', 'wait', 'mean_rev', 'Mean Reversion — đặt lệnh chờ'];
      zone = `Mua quanh ${fmt(mean - 2 * std)} (−2σ) · Bán quanh ${fmt(mean + 2 * std)} (+2σ)`;
      reasons.push(`Z-Score ${sg(z)}σ còn trong vùng bình thường — chưa có lợi thế thống kê.`);
    }
  } else if (regime === 'up') {
    reasons.push(`Giá trên EMA50 khung 4h và EMA20 > EMA50 (${sg(gap)}%) → xu hướng tăng.`);
    if (fin(r.dcHigh) && r.c > r.dcHigh) {
      [stance, kind, pb, pbl] = ['Mua theo đà', 'long', 'breakout', 'Breakout — phá đỉnh 48 giờ'];
      reasons.push(`Giá vừa vượt đỉnh 48 giờ (${fmt(r.dcHigh)}) — lực mua mạnh.`);
      plan = planPosition({ capital, riskPct, entry: px, std: r.atr / 2, mean: null, isLong: true, slMult: 5.0, tpMult: 10.0 });
    } else if (z < 0.5) {
      [stance, kind, pb, pbl] = ['Mua khi điều chỉnh', 'long', 'trend', 'Trend Following — mua nhịp điều chỉnh'];
      reasons.push(`Giá đang điều chỉnh về gần trung bình (Z ${sg(z)}σ) trong xu hướng tăng.`);
      plan = P({ mean: null, isLong: true, slMult: 2.0, tpMult: 3.0 });
    } else {
      [stance, kind, pb, pbl] = ['Chờ điều chỉnh', 'wait', 'trend', 'Trend Following — chờ giá về EMA20'];
      zone = `Chờ mua quanh EMA20 ≈ ${fmt(r.emaFast)}`;
      reasons.push(`Giá đã cao (Z ${sg(z)}σ, RSI ${rs.toFixed(0)}) — mua lúc này dễ đu đỉnh.`);
    }
  } else if (regime === 'down') {
    reasons.push(`Giá dưới EMA50 khung 4h và EMA20 < EMA50 (${sg(gap)}%) → xu hướng giảm.`);
    if (z <= -Z_ENTRY && rs < 30) {
      [stance, kind, pb, pbl] = ['Tích luỹ từng phần', 'wait', 'dca', 'Smart DCA — chia nhỏ vốn, chỉ dài hạn'];
      reasons.push(`Quá bán sâu (Z ${sg(z)}σ, RSI ${rs.toFixed(0)}) nhưng xu hướng vẫn giảm: chỉ mua phần nhỏ, chia nhiều lần.`);
    } else if (allowFutures && z > -1) {
      [stance, kind, pb, pbl] = ['Short khi hồi', 'short', 'short', 'Trend Following — Short (Futures)'];
      zone = `Chờ Short khi giá hồi về EMA20 ≈ ${fmt(r.emaFast)}`;
      reasons.push('Spot: đứng ngoài. Futures: chờ nhịp hồi lên để Short thuận xu hướng.');
      plan = P({ mean: null, isLong: false, slMult: 2.0, tpMult: 3.0 });
    } else {
      [stance, kind, pb, pbl] = ['Đứng ngoài', 'wait', 'wait', 'Đứng ngoài — không bắt dao rơi'];
      reasons.push('Không mua ngược xu hướng giảm khi chưa có tín hiệu đảo chiều.');
    }
  } else {
    [stance, kind, pb, pbl] = ['Đứng ngoài', 'wait', 'wait', 'Đứng ngoài — chờ tín hiệu rõ'];
    reasons.push(`ADF ${fin(adf) ? adf.toFixed(2) : '—'} và EMA (${sg(gap)}%) chưa cho thấy xu hướng hay vùng đi ngang rõ ràng.`);
  }

  const keys = Object.keys(factors);
  const best = keys.reduce((a, b) => WEIGHTS[b] * factors[b] > WEIGHTS[a] * factors[a] ? b : a);
  const worst = keys.reduce((a, b) => WEIGHTS[b] * factors[b] < WEIGHTS[a] * factors[a] ? b : a);
  if (factors[best] > 0) reasons.push(`Điểm mạnh: ${FACTOR_LABELS[best].toLowerCase()}.`);
  if (factors[worst] < 0) reasons.push(`Điểm yếu: ${FACTOR_LABELS[worst].toLowerCase()}.`);

  return { pair, price: px, t: r.t, regime, regimeLabel, factors, score, stance, kind, playbook: pb, playbookLabel: pbl,
           reasons, zone, plan,
           metrics: { z, adf, gap, rsi: rs, roc7d: r.roc7d, volAnn: r.volAnn, atrPct: r.atr / px * 100 } };
}

export function mood(scores) {
  const s = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  if (s <= -40) return ['Rất tiêu cực', 'short'];
  if (s <= -15) return ['Tiêu cực', 'short'];
  if (s < 15) return ['Trung lập', 'wait'];
  if (s < 40) return ['Tích cực', 'long'];
  return ['Rất tích cực', 'long'];
}

/** Phân bổ vốn Spot đề xuất — giống advisor.allocate */
export function allocate(items, profileKey, capital) {
  const prof = PROFILES[profileKey];
  const picks = items.filter(a => a.score > 0 && a.regime !== 'down');
  const rows = [];
  if (picks.length) {
    const raw = picks.map(a => a.score / Math.max(a.metrics.volAnn, 1));
    const sum = raw.reduce((a, b) => a + b, 0);
    const conviction = Math.min(1, picks.reduce((s, a) => s + a.score, 0) / picks.length / 50);
    const invest = (1 - prof.cash_min) * conviction;
    picks.forEach((a, i) => {
      const w = Math.min(raw[i] / sum * invest, prof.max_weight);
      rows.push({ asset: a.pair, weight: w, usdt: w * capital, score: a.score, why: a.stance });
    });
  }
  const cash = 1 - rows.reduce((s, r) => s + r.weight, 0);
  rows.push({ asset: 'USDT (tiền mặt)', weight: cash, usdt: cash * capital, score: null, why: 'Dự phòng rủi ro & chờ cơ hội' });
  return rows;
}
