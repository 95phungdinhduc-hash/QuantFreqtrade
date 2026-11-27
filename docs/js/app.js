/* Lil_Duck Quant — web app. Mọi tính toán chạy ngay trên máy bạn từ dữ liệu công khai của Binance.
   Không có bot, không có khoá API, không gửi dữ liệu đi đâu. Cài đặt chỉ lưu trên thiết bị này. */
import * as Q from './quant.js';
import * as API from './api.js';
import { initFx, countUp, snapshot, flashChanges, reduce } from './fx.js';

const ALL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT'];
const COIN_COLORS = { BTC: '#f7931a', ETH: '#8c9eff', SOL: '#14f195', BNB: '#f3ba2f', XRP: '#9aa4b2', ADA: '#4b7bec', DOGE: '#c2a633' };
const DEFAULTS = { capital: 1000, riskPct: 1.5, maxLeverage: 5, pairs: ALL_PAIRS.slice(0, 4), marketFilter: true,
                   autoRefresh: true, dashUrl: '' };
const VIEWS = ['home', 'signals', 'chart', 'settings'];
const REFRESH_MS = 60_000;

/* ------------------------------------------------------------------ tiện ích */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fin = Number.isFinite;
const num = (v, d) => v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const pxDigits = v => Math.abs(v) >= 10 ? 2 : Math.abs(v) >= 1 ? 3 : 5;
const fmtPx = v => fin(v) ? '$' + num(v, pxDigits(v)) : '—';
const fmtUsd = v => fin(v) ? '$' + num(v, 2) : '—';
const fmtPct = (v, d = 2, sign = true) => fin(v) ? (sign && v > 0 ? '+' : '') + v.toFixed(d) + '%' : '—';
const fmtQty = q => q >= 100 ? num(q, 1) : q >= 1 ? q.toFixed(3) : q.toFixed(5);
const qtyRaw = q => q >= 100 ? q.toFixed(1) : q >= 1 ? q.toFixed(3) : q.toFixed(5);   // để copy: không có dấu phẩy
const movePct = (target, price) => fmtPct((target / price - 1) * 100);
const trend = v => !fin(v) || Math.abs(v) < 1e-9 ? 'flat' : v > 0 ? 'up' : 'down';
const base = p => p.split('/')[0];
const timeVN = t => new Date(t).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
const coin = p => `<span class="coin" style="background:${COIN_COLORS[base(p)] || '#6da7ec'}">${esc(base(p).slice(0, 4))}</span>`;
const copyable = (v, text) => `<code class="copy" data-copy="${esc(String(v))}">${esc(text)}</code>`;

let gid = 0;
function sparkline(values, color, w = 240, h = 46) {
  const v = values.filter(fin);
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), rng = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${((h - 3) - (x - lo) / rng * (h - 6)).toFixed(1)}`).join(' ');
  const id = `sp${gid++}`;
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true" style="filter:drop-shadow(0 4px 10px ${color}55)">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".32"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <polygon points="0,${h} ${pts} ${w},${h}" fill="url(#${id})"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}
function meter(frac, left, right) {
  const pct = Math.max(0, Math.min(1, fin(frac) ? frac : 0)) * 100;
  return `<div class="meter"><div class="bar"><i style="width:${pct.toFixed(0)}%"></i></div>
    <div class="lbl"><span>${esc(left)}</span><span>${esc(right)}</span></div></div>`;
}
let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('on'), 2000);
}

/* ------------------------------------------------------------------ cài đặt (chỉ lưu trên máy này) */
function loadSettings() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem('qf.settings') || '{}') }; } catch { return { ...DEFAULTS }; }
}
let S = loadSettings();
function saveSettings(patch) {
  S = { ...S, ...patch };
  try { localStorage.setItem('qf.settings', JSON.stringify(S)); } catch { /* chế độ riêng tư */ }
}

/* ------------------------------------------------------------------ dữ liệu */
const st = { tick: {}, candles: {}, rows: {}, regime: null, days: null, fng: null, minNot: null, updated: 0,
             loading: false, error: '', offline: false };

function restoreCache() {
  try {
    const c = JSON.parse(localStorage.getItem('qf.cache') || 'null');
    if (!c) return;
    Object.assign(st, { tick: c.tick || {}, candles: c.candles || {}, fng: c.fng, updated: c.updated, days: c.days });
    computeAll();
  } catch { /* bỏ qua */ }
}
function saveCache() {
  try {
    localStorage.setItem('qf.cache', JSON.stringify({ tick: st.tick, candles: st.candles, fng: st.fng, updated: st.updated, days: st.days }));
  } catch { /* đầy bộ nhớ */ }
}
function computeAll() {
  st.rows = {};
  for (const [p, c] of Object.entries(st.candles)) if (c?.length) st.rows[p] = Q.addIndicators(c, { window: 50 });
  st.regime = st.days ? Q.btcRegime(st.days) : null;
}

async function refresh({ manual = false } = {}) {
  if (st.loading) return;
  st.loading = true; setStatus();
  const wasEmpty = !Object.keys(st.rows).length;
  const pairs = S.pairs;
  const jobs = [API.tickers(pairs), API.spotKlines('BTC/USDT', '1d', 260), API.fearGreed(),
                ...pairs.map(p => API.futuresKlines(p, '1h', 300))];
  const res = await Promise.allSettled(jobs);
  const ok = res.filter(r => r.status === 'fulfilled').length;
  if (res[0].status === 'fulfilled') st.tick = res[0].value;
  if (res[1].status === 'fulfilled') st.days = res[1].value.slice(0, -1);          // bỏ nến ngày đang chạy
  if (res[2].status === 'fulfilled') st.fng = res[2].value;
  pairs.forEach((p, i) => { const r = res[3 + i]; if (r.status === 'fulfilled') st.candles[p] = r.value; });
  for (const p of Object.keys(st.candles)) if (!pairs.includes(p)) delete st.candles[p];
  computeAll();
  st.offline = ok === 0;
  st.error = ok === 0 ? 'Không kết nối được Binance' : ok < res.length ? 'Một phần dữ liệu chưa tải được' : '';
  if (ok > 0) st.updated = Date.now();
  if (activeSignals().length && !st.minNot) st.minNot = await API.minNotionals().catch(() => null);
  saveCache();
  st.loading = false;
  render({ quiet: !wasEmpty });
  if (manual) toast(st.error || 'Đã cập nhật');
}

/* ------------------------------------------------------------------ tín hiệu */
function signalFor(p) {
  const rows = st.rows[p];
  if (!rows?.length) return null;
  const r = rows.at(-1);
  const sig = Q.pickSignal(r);
  const allowed = sig && (!S.marketFilter || Q.marketAllows(sig.isLong, st.regime));
  return { p, r, sig, allowed };
}
const activeSignals = () => S.pairs.map(signalFor).filter(x => x?.sig && x.allowed);

function whyText(r, sig) {
  if (sig.strategy === 'Mean Reversion')
    return sig.isLong
      ? `Giá đang <b>quá bán</b> (Z = ${r.z.toFixed(2)}σ) trong vùng đi ngang (ADF ${r.adf.toFixed(2)}) → kỳ vọng hồi về trung bình.`
      : `Giá đang <b>quá mua</b> (Z = +${r.z.toFixed(2)}σ) trong vùng đi ngang (ADF ${r.adf.toFixed(2)}) → kỳ vọng quay về trung bình.`;
  return sig.isLong
    ? `EMA20 cao hơn EMA50 <b>${r.gap.toFixed(2)}%</b>, thị trường có xu hướng (ADF ${r.adf.toFixed(2)}) → đánh thuận xu hướng <b>tăng</b>.`
    : `EMA20 thấp hơn EMA50 <b>${Math.abs(r.gap).toFixed(2)}%</b>, thị trường có xu hướng (ADF ${r.adf.toFixed(2)}) → đánh thuận xu hướng <b>giảm</b>.`;
}

function signalCard({ p, r, sig, demo = false }) {
  const minNot = API.minNotionalOf(st.minNot, p) ?? Q.DEFAULT_MIN_NOTIONAL;
  const P = Q.buildPlan(r, sig, { capital: S.capital, riskPct: S.riskPct, minNotional: minNot, maxLeverage: S.maxLeverage });
  const price = r.c, b = esc(base(p));
  const tp = P.plan.takeProfit, sl = P.plan.stopLoss;
  const tpsl = `<li>Chốt lời (TP): ${copyable(tp.toFixed(pxDigits(tp)), fmtPx(tp))} <span class="tag-tp">(${movePct(tp, price)})</span></li>
                <li>Cắt lỗ (SL): ${copyable(sl.toFixed(pxDigits(sl)), fmtPx(sl))} <span class="tag-sl">(${movePct(sl, price)})</span></li>`;
  const spot = P.spot
    ? `<div class="steps"><h4>📦 Spot — cách vào lệnh</h4><ol>
         <li>Mua <b>Market</b> ${copyable(qtyRaw(P.spot.qty), `${fmtQty(P.spot.qty)} ${b}`)} (≈ ${fmtUsd(P.spot.usd)})</li>
         <li>Ngay sau khi khớp, đặt lệnh <b>OCO</b> bán toàn bộ:<ul>${tpsl}</ul></li></ol>
         ${P.spot.capped ? `<div class="note">⚠️ Khối lượng lý tưởng vượt vốn → mua tối đa ${fmtUsd(S.capital)} (lỗ tối đa còn ${fmtUsd(P.spot.maxLoss)})</div>` : ''}</div>`
    : `<div class="steps"><h4>📦 Spot</h4><div class="note">Không Short được trên Spot → <b>đứng ngoài</b>. Nếu đang giữ ${b}: cân nhắc chốt lời một phần quanh ${fmtPx(price)}.</div></div>`;
  const fut = `<div class="steps"><h4>⚡ Futures — cách vào lệnh</h4><ol>
      <li>Chọn ký quỹ <b>Isolated</b>, đòn bẩy <b>x${P.leverage}</b></li>
      <li>Mở <b>${sig.isLong ? 'LONG (Mua)' : 'SHORT (Bán)'}</b> Market ${copyable(qtyRaw(P.fplan.positionUsd / price), `${fmtQty(P.fplan.positionUsd / price)} ${b}`)}
          (lệnh ≈ ${fmtUsd(P.fplan.positionUsd)}, ký quỹ ≈ ${fmtUsd(P.margin)})</li>
      <li>Đặt TP/SL cho vị thế:<ul>${tpsl}</ul></li></ol>
      <div class="note">Lỗ tối đa nếu chạm SL: <b class="down">${fmtUsd(P.fplan.riskUsd)}</b>${P.forcedMin ? ` (⚠️ sàn bắt lệnh tối thiểu $${minNot} → rủi ro thực cao hơn mức ${S.riskPct}%)` : ''}
      · Phí 2 chiều ~${fmtUsd(P.fee2way)} · Lời/lỗ 1:${P.plan.rr.toFixed(1)}</div></div>`;
  const kind = sig.isLong ? 'long' : 'short';
  return `<article class="card sig-${kind}">
    <div class="card-head"><div class="sym">${coin(p)}<div>${esc(p)}<small>Nến 1h Futures · ${timeVN(r.t)} (đang chạy)</small></div></div>
      <span class="badge ${demo ? 'warn' : kind}">${demo ? 'Mẫu · ' : ''}${sig.isLong ? 'Long' : 'Short'}${sig.strong ? ' · mạnh' : ''}</span></div>
    <div class="strat">${sig.strategy === 'Mean Reversion' ? '🔄 Mean Reversion · thị trường đi ngang' : '🚀 Trend Following · thị trường có xu hướng'}</div>
    <p class="why">${whyText(r, sig)}</p>
    <div class="kv"><span>Giá tham chiếu</span><span${demo ? '' : ` data-key="sp-${b}"`}>${fmtPx(price)}</span></div>
    <div class="kv"><span>Z-Score · EMA lệch · ADF</span><span>${r.z.toFixed(2)}σ · ${fmtPct(r.gap)} · ${r.adf.toFixed(3)}</span></div>
    ${spot}${fut}</article>`;
}

function waitCard({ p, r, sig }) {
  const s = Q.regimeState(r);
  const ranging = fin(r.adf) && r.adf < Q.ADF_THRESHOLD;
  let body;
  if (sig) {
    body = `<p class="why">Có tín hiệu <b>${sig.isLong ? 'LONG' : 'SHORT'}</b> (${sig.strategy}) nhưng <b>bộ lọc thị trường chặn</b>:
      BTC đang ${st.regime?.up ? 'trên' : 'dưới'} SMA200 ngày nên hệ thống chỉ báo ${st.regime?.up ? 'Long' : 'Short'} — giống các bot.</p>`;
  } else if (ranging) {
    body = `<p class="why">Thị trường <b>đi ngang</b> (ADF ${r.adf.toFixed(2)}). Chờ giá lệch đủ xa khỏi trung bình.</p>
      ${meter(Math.abs(r.z) / Q.MODERATE_Z, `Z cần chạm ±${Q.MODERATE_Z.toFixed(1)}σ`, `hiện ${r.z >= 0 ? '+' : ''}${r.z.toFixed(2)}σ`)}`;
  } else {
    body = `<p class="why">Thị trường <b>có xu hướng</b> (ADF ${fin(r.adf) ? r.adf.toFixed(2) : '—'}) nhưng EMA20/50 chưa tách đủ rõ.</p>
      ${meter(Math.abs(r.gap) / Q.MODERATE_GAP, `EMA lệch cần ±${Q.MODERATE_GAP.toFixed(1)}%`, `hiện ${fmtPct(r.gap)}`)}`;
  }
  return `<article class="card${sig ? ' muted' : ''}">
    <div class="card-head"><div class="sym">${coin(p)}<div>${esc(p)}<small>${fmtPx(r.c)} · ${timeVN(r.t)}</small></div></div>
      <span class="badge ${sig ? 'warn' : ''}">${sig ? 'Bị lọc' : s.mr ? 'Đi ngang · chờ' : 'Đứng ngoài'}</span></div>
    ${body}</article>`;
}

/** Thẻ mẫu: lấy giá thật của coin đầu tiên, giả lập Z = -2.6σ trong vùng đi ngang để bạn tập đọc */
function demoBlock(all) {
  const x = all[0];
  if (!x) return '';
  const r = { ...x.r, z: -2.6, adf: 0.08, gap: 0.2, mean: x.r.c + 2.6 * x.r.std };
  const sig = Q.pickSignal(r);
  const open = document.querySelector('#v-signals details.demo')?.open ? ' open' : '';
  return `<details class="demo"${open}><summary>👀 Xem thử một tín hiệu mẫu (không phải tín hiệu thật)</summary>
    <div class="grid wide" style="margin-top:12px">${signalCard({ p: x.p, r, sig, demo: true })}</div></details>`;
}

/* ------------------------------------------------------------------ màn Tổng quan */
function fngColor(v) { return v < 25 ? '#ef5d5d' : v < 45 ? '#d95926' : v < 55 ? '#a7afc3' : v < 75 ? '#7cb3f0' : '#1fbf75'; }
const FNG_VI = { 'Extreme Fear': 'Cực kỳ sợ hãi', Fear: 'Sợ hãi', Neutral: 'Trung lập', Greed: 'Tham lam', 'Extreme Greed': 'Cực kỳ tham lam' };

function renderHome() {
  const reg = st.regime, n = activeSignals().length;
  const pairs = S.pairs.filter(p => st.rows[p]?.length);
  const regTxt = !reg ? 'Chưa lấy được dữ liệu BTC ngày.'
    : !S.marketFilter ? `BTC ${reg.up ? 'trên' : 'dưới'} SMA200 ngày (${fmtPct(reg.gap, 1)}). Bộ lọc thị trường <b>đang tắt</b>: báo cả Long lẫn Short.`
    : reg.up ? `BTC <b>trên</b> SMA200 ngày (${fmtPct(reg.gap, 1)}) → hệ thống chỉ báo <b>Long</b>, Spot và Futures.`
    : `BTC <b>dưới</b> SMA200 ngày (${fmtPct(reg.gap, 1)}) → chỉ báo <b>Short Futures</b>, Spot đứng ngoài.`;
  const f = st.fng?.[0];
  const tapeItems = pairs.map(p => {
    const t = st.tick[p] || {}, last = t.last ?? st.rows[p].at(-1).c;
    return `<span class="tape-item">${coin(p)}<b>${esc(base(p))}</b><span class="p">${fmtPx(last)}</span><span class="chg ${trend(t.pct)}">${fmtPct(t.pct)}</span></span>`;
  });
  const reps = tapeItems.length ? Math.max(1, Math.ceil(10 / tapeItems.length)) : 0;
  const tapeOne = Array(reps).fill(tapeItems.join('')).join('');

  const cards = pairs.map(p => {
    const rows = st.rows[p], r = rows.at(-1), t = st.tick[p] || {};
    const last = t.last ?? r.c, pct = t.pct;
    const color = trend(pct) === 'up' ? '#1fbf75' : trend(pct) === 'down' ? '#ef5d5d' : '#a7afc3';
    const s = Q.regimeState(r);
    return `<article class="card lift">
      <div class="card-head"><div class="sym">${coin(p)}<div>${esc(base(p))}<small>${esc(p)}</small></div></div>
        <span class="badge ${s.kind}">${esc(s.label)}</span></div>
      <div class="px" data-key="px-${esc(base(p))}">${fmtPx(last)}</div>
      <span class="chg ${trend(pct)}">${fmtPct(pct)} 24h</span>
      ${sparkline(rows.slice(-72).map(k => k.c), color)}
      <div class="meta"><span>Z <b>${fin(r.z) ? (r.z >= 0 ? '+' : '') + r.z.toFixed(2) + 'σ' : '—'}</b></span>
        <span>EMA <b>${fmtPct(r.gap)}</b></span><span>RSI <b>${fin(r.rsi) ? r.rsi.toFixed(0) : '—'}</b></span></div>
    </article>`;
  }).join('');

  const fngCard = f ? (() => {
    const c = fngColor(f.value), frac = f.value / 100;
    const hist = (st.fng || []).slice().reverse().map(x => `<i style="height:${Math.max(8, x.value)}%;background:${fngColor(x.value)}"></i>`).join('');
    return `<article class="card"><div class="card-head"><b>😨 Sợ hãi & Tham lam</b><span class="badge info">8 ngày</span></div>
      <div class="fng"><svg viewBox="0 0 112 66" aria-hidden="true">
          <path d="M8 60 A48 48 0 0 1 104 60" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="10" stroke-linecap="round"/>
          <path class="arc-v" d="M8 60 A48 48 0 0 1 104 60" fill="none" stroke="${c}" stroke-width="10" stroke-linecap="round" pathLength="1"
            stroke-dashoffset="${(1 - frac).toFixed(3)}" style="filter:drop-shadow(0 0 8px ${c}88)"/></svg>
        <div><div class="fng-val" style="color:${c}" data-count>${f.value}</div><div class="fng-lbl">${esc(FNG_VI[f.label] || f.label)}</div></div></div>
      <div class="hist">${hist}</div>
      <div class="meta" style="margin-top:6px"><span>0 = hoảng loạn</span><span>100 = hưng phấn</span></div></article>`;
  })() : '';
  const regCard = reg ? `<article class="card"><div class="card-head"><b>🧭 Bộ lọc thị trường</b>
        <span class="badge ${reg.up ? 'long' : 'short'}">${reg.up ? 'Thị trường tăng' : 'Thị trường giảm'}</span></div>
      <div class="kv"><span>BTC đóng cửa ngày</span><span>${fmtPx(reg.close)}</span></div>
      <div class="kv"><span>SMA200 ngày</span><span>${fmtPx(reg.sma)}</span></div>
      <div class="kv"><span>Cách SMA200</span><span class="${trend(reg.gap)}" data-count>${fmtPct(reg.gap, 1)}</span></div>
      <div class="kv"><span>Hệ thống cho phép</span><span>${!S.marketFilter ? 'Long + Short (lọc tắt)' : reg.up ? 'Chỉ Long' : 'Chỉ Short (Futures)'}</span></div></article>` : '';

  $('#v-home').innerHTML = `
    <section class="hero"><i class="orb o1"></i><i class="orb o2"></i>
      <div class="eyebrow"><span class="dot${st.offline ? ' off' : ''}"></span>Phân tích định lượng · Binance trực tiếp</div>
      <h1>Giao dịch crypto bằng <span class="grad">thống kê</span>,<br>không bằng cảm xúc.</h1>
      <p>${regTxt}</p>
      <div class="stats">
        <div class="stat"><div class="k">Tín hiệu lúc này</div><div class="v ${n ? 'up' : ''}" data-count>${n}</div><div class="s">${n ? 'xem tab ⚡ Tín hiệu' : 'chưa có kèo đạt chuẩn'}</div></div>
        <div class="stat"><div class="k">Rủi ro mỗi lệnh</div><div class="v" data-count>${S.riskPct.toFixed(1)}%</div><div class="s">≈ ${fmtUsd(S.capital * S.riskPct / 100)} / vốn ${fmtUsd(S.capital)}</div></div>
        <div class="stat"><div class="k">BTC vs SMA200</div><div class="v ${reg ? trend(reg.gap) : ''}" data-count>${reg ? fmtPct(reg.gap, 1) : '—'}</div><div class="s">${reg ? (reg.up ? 'xu hướng dài hạn tăng' : 'xu hướng dài hạn giảm') : ''}</div></div>
        <div class="stat"><div class="k">Sợ hãi/Tham lam</div><div class="v" style="color:${f ? fngColor(f.value) : ''}" data-count>${f ? f.value : '—'}</div><div class="s">${f ? esc(FNG_VI[f.label] || f.label) : ''}</div></div>
      </div>
      ${tapeItems.length ? `<div class="tape" style="--dur:${tapeItems.length * reps * 4.5}s"><div class="tape-track">${tapeOne}${tapeOne}</div></div>` : ''}
    </section>
    <div class="sec"><div><h2>Thị trường</h2><p>Biểu đồ 72 giờ · Z-Score, EMA và RSI trên nến 1h Futures.</p></div>
      <span class="aside">${st.updated ? 'cập nhật ' + timeVN(st.updated) : ''}</span></div>
    ${cards ? `<div class="grid">${cards}</div>` : skeleton(4)}
    <div class="sec"><div><h2>Bối cảnh</h2><p>Hai thứ quyết định hệ thống được phép báo Long hay Short.</p></div></div>
    <div class="grid two">${regCard}${fngCard}</div>
    ${disclaimer()}`;
}

function renderSignals() {
  const all = S.pairs.map(signalFor).filter(Boolean);
  const active = all.filter(x => x.sig && x.allowed);
  const rest = all.filter(x => !(x.sig && x.allowed));
  const reg = st.regime;
  $('#v-signals').innerHTML = `
    <div class="sec"><div><h2>⚡ Tín hiệu vào lệnh</h2><p>Cùng quy tắc với alert bot Telegram: nến 1h Futures, cắt lỗ 2σ, khối lượng theo ${S.riskPct}% rủi ro trên vốn ${fmtUsd(S.capital)}.</p></div>
      <span class="aside">${st.updated ? timeVN(st.updated) : ''}</span></div>
    ${S.marketFilter && reg ? `<div class="filter-note">🧭 <b>Bộ lọc thị trường:</b> BTC ${reg.up ? 'trên' : 'dưới'} SMA200 ngày (${fmtPct(reg.gap, 1)})
      → chỉ báo <b>${reg.up ? 'Long' : 'Short'}</b>${reg.up ? '' : ' (Futures), Spot đứng ngoài'}. Tắt bộ lọc ở tab 💼 Vốn nếu muốn thấy cả hai chiều.</div>` : ''}
    ${active.length ? `<div class="sec"><div><h2>Đang có tín hiệu</h2><p>Chạm vào số được gạch chân để copy, dán thẳng vào app sàn.</p></div></div>
      <div class="grid wide">${active.map(signalCard).join('')}</div>` : all.length ? `<div class="sec"><div><h2>Chưa có tín hiệu</h2>
      <p>Không có coin nào đạt điều kiện. Đứng ngoài cũng là một quyết định — đừng ép lệnh.</p></div></div>${demoBlock(all)}` : skeleton(2)}
    ${rest.length ? `<div class="sec"><div><h2>Đang theo dõi</h2><p>Thanh tiến độ cho biết còn cách điều kiện vào lệnh bao xa.</p></div></div>
      <div class="grid">${rest.map(x => waitCard(x)).join('')}</div>` : ''}
    ${disclaimer()}`;
}

/* ------------------------------------------------------------------ màn Biểu đồ */
const chartState = { pair: null, tf: '1h', cache: new Map(), charts: null };
const TF = ['15m', '1h', '4h', '1d'];

function renderChartShell() {
  if (!S.pairs.includes(chartState.pair)) chartState.pair = S.pairs[0];
  if (chartState.charts) { chartState.charts.main.remove(); chartState.charts.zc.remove(); chartState.charts = null; }
  $('#v-chart').innerHTML = `
    <div class="sec"><div><h2>📈 Biểu đồ phân tích</h2><p>Nến Futures · đường trung bình ± 2σ (vùng Z-Score) · EMA20/50 · Z-Score bên dưới.</p></div></div>
    <div class="toolbar">
      <div class="seg" id="c-pair">${S.pairs.map(p => `<button data-v="${esc(p)}" aria-pressed="${p === chartState.pair}">${esc(base(p))}</button>`).join('')}</div>
      <div class="seg" id="c-tf">${TF.map(t => `<button data-v="${t}" aria-pressed="${t === chartState.tf}">${t}</button>`).join('')}</div>
    </div>
    <article class="card">
      <div id="c-main" class="chart-box"></div>
      <div id="c-z" class="chart-box small"></div>
      <div class="legend">
        <span><i style="background:#7cb3f0"></i>Trung bình 50 nến</span>
        <span style="color:rgba(124,179,240,.7)"><i class="dash"></i>± 2σ</span>
        <span><i style="background:#9085e9"></i>EMA20</span><span><i style="background:#d95926"></i>EMA50</span>
        <span><i style="background:#3987e5"></i>Z-Score</span>
      </div>
      <div class="kpis" id="c-kpis"></div>
    </article>
    <p class="foot">Biểu đồ: <a href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noopener">TradingView Lightweight Charts™</a></p>`;
  $('#c-pair').onclick = e => { const b = e.target.closest('button'); if (b) { chartState.pair = b.dataset.v; renderChartShell(); loadChart(); } };
  $('#c-tf').onclick = e => { const b = e.target.closest('button'); if (b) { chartState.tf = b.dataset.v; renderChartShell(); loadChart(); } };
}

function makeCharts() {
  const LC = window.LightweightCharts;
  if (!LC) return null;
  const tz = -new Date().getTimezoneOffset() * 60;
  const base = {
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#a7afc3', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
    grid: { vertLines: { color: 'rgba(150,170,220,.06)' }, horzLines: { color: 'rgba(150,170,220,.06)' } },
    rightPriceScale: { borderColor: 'rgba(150,170,220,.16)', minimumWidth: 74 },   // 2 biểu đồ thẳng cột với nhau
    timeScale: { borderColor: 'rgba(150,170,220,.16)', timeVisible: true, secondsVisible: false },
    crosshair: { mode: LC.CrosshairMode.Normal, vertLine: { color: 'rgba(124,179,240,.4)', labelBackgroundColor: '#1e273a' },
                 horzLine: { color: 'rgba(124,179,240,.4)', labelBackgroundColor: '#1e273a' } },
    handleScale: { axisPressedMouseMove: false },
  };
  const main = LC.createChart($('#c-main'), { ...base, timeScale: { ...base.timeScale, visible: false } });
  const zc = LC.createChart($('#c-z'), { ...base, layout: { ...base.layout, attributionLogo: false } });
  const line = (chart, color, extra = {}) => chart.addLineSeries({ color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
                                                                  crosshairMarkerVisible: false, ...extra });
  const s = {
    tz, main, zc,
    candles: main.addCandlestickSeries({ upColor: '#1fbf75', downColor: '#ef5d5d', borderVisible: false, wickUpColor: '#1fbf75', wickDownColor: '#ef5d5d' }),
    upper: line(main, 'rgba(124,179,240,.55)', { lineWidth: 1, lineStyle: LC.LineStyle.Dashed }),
    lower: line(main, 'rgba(124,179,240,.55)', { lineWidth: 1, lineStyle: LC.LineStyle.Dashed }),
    mean: line(main, '#7cb3f0'),
    e20: line(main, '#9085e9', { lineWidth: 1.5 }),
    e50: line(main, '#d95926', { lineWidth: 1.5 }),
    z: line(zc, '#3987e5', { lastValueVisible: true, crosshairMarkerVisible: true }),
  };
  for (const [v, c, t] of [[2, 'rgba(239,93,93,.7)', '+2σ'], [-2, 'rgba(31,191,117,.7)', '−2σ'], [0, 'rgba(150,170,220,.3)', '']])
    s.z.createPriceLine({ price: v, color: c, lineWidth: 1, lineStyle: LC.LineStyle.Dashed, axisLabelVisible: !!t, title: t });
  let syncing = false;
  const sync = (from, to) => from.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (syncing || !r) return; syncing = true; to.timeScale().setVisibleLogicalRange(r); syncing = false;
  });
  sync(main, zc); sync(zc, main);
  return s;
}

async function loadChart() {
  const { pair, tf } = chartState;
  const key = `${pair}|${tf}`;
  const cached = chartState.cache.get(key);
  let rows = tf === '1h' && st.rows[pair] ? st.rows[pair] : cached && Date.now() - cached.t < REFRESH_MS ? cached.rows : null;
  if (!rows) {
    try {
      rows = Q.addIndicators(await API.futuresKlines(pair, tf, 400), { window: 50 });
      chartState.cache.set(key, { rows, t: Date.now() });
    } catch {
      $('#c-main').innerHTML = '<div class="empty" style="padding:40px;text-align:center;color:var(--text2)">Không tải được dữ liệu — kiểm tra mạng.</div>';
      return;
    }
  }
  if (chartState.pair !== pair || chartState.tf !== tf) return;
  const c = chartState.charts || (chartState.charts = makeCharts());
  if (!c) { $('#c-main').innerHTML = '<p style="padding:40px;text-align:center;color:var(--text2)">Thư viện biểu đồ chưa tải được (cần mạng lần đầu).</p>'; return; }
  const T = k => Math.floor(k.t / 1000) + c.tz;
  // giữ đủ số nến (nến chưa có giá trị = khoảng trắng) để 2 biểu đồ cuộn khớp nhau
  const line = f => rows.map(k => fin(f(k)) ? { time: T(k), value: f(k) } : { time: T(k) });
  const d = pxDigits(rows.at(-1).c);
  c.candles.applyOptions({ priceFormat: { type: 'price', precision: d, minMove: 10 ** -d } });
  c.candles.setData(rows.map(k => ({ time: T(k), open: k.o, high: k.h, low: k.l, close: k.c })));
  c.mean.setData(line(k => k.mean));
  c.upper.setData(line(k => k.mean + 2 * k.std));
  c.lower.setData(line(k => k.mean - 2 * k.std));
  c.e20.setData(line(k => k.emaFast));
  c.e50.setData(line(k => k.emaSlow));
  c.z.setData(line(k => k.z));
  c.main.timeScale().setVisibleLogicalRange({ from: rows.length - 120, to: rows.length + 3 });
  const r = rows.at(-1), ranging = fin(r.adf) && r.adf < Q.ADF_THRESHOLD;
  const kpi = (k, v, cls = '', s = '') => `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
  $('#c-kpis').innerHTML = kpi('Giá', fmtPx(r.c)) +
    kpi('Z-Score', `${r.z >= 0 ? '+' : ''}${r.z.toFixed(2)}σ`, Math.abs(r.z) >= 2 ? (r.z > 0 ? 'down' : 'up') : '', Math.abs(r.z) >= 2 ? (r.z > 0 ? 'quá mua' : 'quá bán') : 'bình thường') +
    kpi('ADF p', fin(r.adf) ? r.adf.toFixed(3) : '—', '', ranging ? 'đi ngang' : 'có xu hướng') +
    kpi('EMA20/50', fmtPct(r.gap), trend(r.gap), Math.abs(r.gap) >= Q.MODERATE_GAP ? 'tách rõ' : 'chưa rõ') +
    kpi('RSI 14', fin(r.rsi) ? r.rsi.toFixed(0) : '—', '', r.rsi > 70 ? 'quá mua' : r.rsi < 30 ? 'quá bán' : '') +
    kpi('ATR', fmtPct(r.atr / r.c * 100, 2, false), '', 'biên độ 1 nến');
}

/* ------------------------------------------------------------------ màn Vốn & cài đặt */
const calc = { pair: null, side: 'long', entry: '', sl: '' };

function renderSettings() {
  if (!S.pairs.includes(calc.pair)) calc.pair = S.pairs[0];
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  $('#v-settings').innerHTML = `
    <div class="sec"><div><h2>💼 Vốn & rủi ro</h2><p>Chỉ lưu trên thiết bị này. Dùng để tính khối lượng trong tab ⚡ Tín hiệu.</p></div></div>
    <div class="grid two">
      <article class="card">
        <div class="row2">
          <div class="field"><label for="s-cap">Vốn (USDT)</label><input class="input" id="s-cap" type="number" inputmode="decimal" min="10" step="10" value="${S.capital}"></div>
          <div class="field"><label for="s-risk">Rủi ro mỗi lệnh (%)</label><input class="input" id="s-risk" type="number" inputmode="decimal" min="0.1" max="10" step="0.1" value="${S.riskPct}"></div>
        </div>
        <div class="field"><label for="s-lev">Đòn bẩy Futures tối đa</label>
          <div class="seg" id="s-lev">${[1, 2, 3, 5].map(v => `<button data-v="${v}" aria-pressed="${S.maxLeverage === v}">x${v}</button>`).join('')}</div>
          <small>Tín hiệu đề xuất x2–x5; app không bao giờ vượt mức bạn chọn. Khối lượng vẫn tính theo % rủi ro nên đòn bẩy thấp chỉ tốn thêm ký quỹ.</small></div>
        <div class="kv"><span>Mỗi lệnh chấp nhận mất</span><span class="down" id="s-riskusd">${fmtUsd(S.capital * S.riskPct / 100)}</span></div>
        ${S.riskPct > 2 ? '<div class="filter-note" style="margin-top:10px">⚠️ Trên <b>2%</b> mỗi lệnh là mạo hiểm: 10 lệnh thua liên tiếp sẽ mất hơn 18% vốn.</div>' : ''}
      </article>
      <article class="card">
        <div class="card-head"><b>🧮 Tự tính khối lượng</b><span class="badge info">${S.riskPct}% rủi ro</span></div>
        <div class="toolbar"><div class="seg" id="k-pair">${S.pairs.map(p => `<button data-v="${esc(p)}" aria-pressed="${p === calc.pair}">${esc(base(p))}</button>`).join('')}</div>
          <div class="seg" id="k-side"><button data-v="long" aria-pressed="${calc.side === 'long'}">Long</button><button data-v="short" aria-pressed="${calc.side === 'short'}">Short</button></div></div>
        <div class="row2">
          <div class="field"><label for="k-entry">Giá vào</label><input class="input" id="k-entry" type="number" inputmode="decimal" step="any" placeholder="${livePrice(calc.pair) ?? ''}" value="${esc(calc.entry)}"></div>
          <div class="field"><label for="k-sl">Giá cắt lỗ</label><input class="input" id="k-sl" type="number" inputmode="decimal" step="any" placeholder="${suggestSl()}" value="${esc(calc.sl)}"></div>
        </div>
        <div id="k-out" class="result"></div>
      </article>
    </div>
    <div class="sec"><div><h2>⚙️ Cài đặt</h2></div></div>
    <div class="grid two">
      <article class="card">
        <div class="field"><label>Coin theo dõi</label><div class="chips" id="s-pairs">${ALL_PAIRS.map(p => `<span class="chip" role="button" tabindex="0" data-v="${esc(p)}" aria-pressed="${S.pairs.includes(p)}">${coin(p)}${esc(base(p))}</span>`).join('')}</div></div>
        <label class="switch"><span>Bộ lọc thị trường<small>BTC dưới SMA200 ngày → chỉ báo Short, trên → chỉ Long (giống các bot)</small></span><input type="checkbox" id="s-filter" ${S.marketFilter ? 'checked' : ''}></label>
        <label class="switch"><span>Tự làm mới mỗi phút<small>Chỉ khi app đang mở trên màn hình</small></span><input type="checkbox" id="s-auto" ${S.autoRefresh ? 'checked' : ''}></label>
      </article>
      <article class="card">
        <div class="card-head"><b>🔒 Dashboard đầy đủ (bot ảo, backtest)</b></div>
        <p class="why" style="color:var(--text2);font-size:13.5px">Dashboard Streamlit chạy trên Mac của bạn, chỉ mở được qua <b>Tailscale</b>. Dán link vào đây (chỉ lưu trên máy này, không đưa lên GitHub).</p>
        <div class="field"><input class="input" id="s-dash" type="url" placeholder="http://100.x.x.x:8502" value="${esc(S.dashUrl)}" style="font-family:var(--font)"></div>
        ${S.dashUrl ? `<a class="btn primary" href="${esc(S.dashUrl)}" target="_blank" rel="noopener">Mở dashboard ↗</a>` : ''}
      </article>
      <article class="card">
        <div class="card-head"><b>📱 Cài lên điện thoại</b>${standalone ? '<span class="badge long">Đã cài</span>' : ''}</div>
        <div class="steps" style="margin-top:0"><ol>
          <li>iPhone: mở trang này bằng <b>Safari</b> → nút <b>Chia sẻ</b> → <b>Thêm vào Màn hình chính</b>.</li>
          <li>Android: Chrome → menu ⋮ → <b>Cài đặt ứng dụng</b>.</li>
          <li>Mở từ icon 🦆 như một app bình thường, toàn màn hình, xem được dữ liệu lần cuối khi mất mạng.</li></ol></div>
      </article>
    </div>
    ${disclaimer()}
    <p class="foot">Dữ liệu: Binance (công khai) · Chỉ số Sợ hãi & Tham lam: alternative.me · Mã nguồn:
      <a href="https://github.com/95phungdinhduc-hash/QuantFreqtrade" target="_blank" rel="noopener">GitHub</a></p>`;
  bindSettings();
  calcOut();
}

const livePrice = p => st.tick[p]?.last ?? st.rows[p]?.at(-1)?.c ?? null;
function suggestSl() {
  const r = st.rows[calc.pair]?.at(-1), e = +calc.entry || livePrice(calc.pair);
  if (!r || !e) return '';
  const sl = calc.side === 'long' ? e - 2 * r.std : e + 2 * r.std;
  return sl.toFixed(pxDigits(sl));
}
function calcOut() {
  const out = $('#k-out');
  if (!out) return;
  const entry = +calc.entry || livePrice(calc.pair), sl = +calc.sl || +suggestSl();
  if (!entry || !sl) { out.innerHTML = ''; return; }
  const wrong = calc.side === 'long' ? sl >= entry : sl <= entry;
  if (wrong) { out.innerHTML = `<div class="filter-note">Giá cắt lỗ phải <b>${calc.side === 'long' ? 'thấp hơn' : 'cao hơn'}</b> giá vào.</div>`; return; }
  const risk = S.capital * S.riskPct / 100, dist = Math.abs(entry - sl) / entry, pos = risk / dist;
  const tp2 = calc.side === 'long' ? entry + 2 * Math.abs(entry - sl) : entry - 2 * Math.abs(entry - sl);
  out.innerHTML = `<div class="big">${fmtQty(pos / entry)} <span style="font-size:15px;color:var(--text2)">${esc(base(calc.pair))}</span></div>
    <div class="kv"><span>Giá trị lệnh</span><span>${fmtUsd(pos)}</span></div>
    <div class="kv"><span>Khoảng cách cắt lỗ</span><span class="down">${(dist * 100).toFixed(2)}%</span></div>
    <div class="kv"><span>Lỗ nếu chạm SL</span><span class="down">−${fmtUsd(risk)}</span></div>
    <div class="kv"><span>Chốt lời gợi ý (lời/lỗ 1:2)</span><span class="up">${fmtPx(tp2)}</span></div>
    <div class="kv"><span>Cần đòn bẩy</span><span>${pos > S.capital ? 'x' + Math.ceil(pos / S.capital) + ' (Futures)' : 'không — Spot được'}</span></div>
    ${!calc.sl ? '<div class="meta" style="margin-top:6px"><span>Đang dùng SL gợi ý: cách giá 2σ như bot.</span></div>' : ''}`;
}
function bindSettings() {
  const numIn = (id, key, min, max) => $(id).addEventListener('change', e => {
    const v = Math.min(max, Math.max(min, +e.target.value || DEFAULTS[key]));
    saveSettings({ [key]: v }); render({ quiet: true });
  });
  numIn('#s-cap', 'capital', 10, 1e9);
  numIn('#s-risk', 'riskPct', 0.1, 10);
  $('#s-lev').onclick = e => { const b = e.target.closest('button'); if (b) { saveSettings({ maxLeverage: +b.dataset.v }); render({ quiet: true }); } };
  $('#s-pairs').onclick = e => {
    const c = e.target.closest('.chip'); if (!c) return;
    const p = c.dataset.v, on = S.pairs.includes(p);
    if (on && S.pairs.length === 1) return toast('Cần theo dõi ít nhất 1 coin');
    saveSettings({ pairs: on ? S.pairs.filter(x => x !== p) : ALL_PAIRS.filter(x => x === p || S.pairs.includes(x)) });
    render({ quiet: true }); renderChartShell(); refresh();
  };
  $('#s-filter').onchange = e => { saveSettings({ marketFilter: e.target.checked }); render({ quiet: true }); };
  $('#s-auto').onchange = e => { saveSettings({ autoRefresh: e.target.checked }); schedule(); };
  $('#s-dash').onchange = e => {
    const v = e.target.value.trim();
    if (v && !/^https?:\/\//i.test(v)) return toast('Link phải bắt đầu bằng http:// hoặc https://');
    saveSettings({ dashUrl: v }); render({ quiet: true });
  };
  $('#k-pair').onclick = e => { const b = e.target.closest('button'); if (b) { calc.pair = b.dataset.v; calc.entry = ''; calc.sl = ''; renderSettings(); } };
  $('#k-side').onclick = e => { const b = e.target.closest('button'); if (b) { calc.side = b.dataset.v; calc.sl = ''; renderSettings(); } };
  $('#k-entry').oninput = e => { calc.entry = e.target.value; $('#k-sl').placeholder = suggestSl(); calcOut(); };
  $('#k-sl').oninput = e => { calc.sl = e.target.value; calcOut(); };
}

/* ------------------------------------------------------------------ khung chung */
const skeleton = n => `<div class="grid">${Array.from({ length: n }, () => '<div class="skel"></div>').join('')}</div>`;
const disclaimer = () => `<div class="disclaimer"><b>⚠️ Không phải lời khuyên đầu tư.</b> Đây là công cụ phân tích theo quy tắc cố định
  (Z-Score, EMA, kiểm định ADF). Giao dịch crypto — đặc biệt Futures có đòn bẩy — có thể mất toàn bộ vốn; kết quả quá khứ không đảm bảo
  tương lai. Luôn đặt cắt lỗ ngay khi vào lệnh và chỉ dùng số tiền bạn chấp nhận mất.</div>`;

function setStatus() {
  const el = $('#status');
  const ago = st.updated ? Math.round((Date.now() - st.updated) / 60000) : null;
  const cls = st.loading ? 'wait' : st.offline || ago == null || ago > 10 ? 'off' : '';
  el.innerHTML = `<span class="dot ${cls}"></span><span>${st.loading ? 'Đang cập nhật…' : st.updated
    ? (st.offline ? 'Mất mạng · ' : '') + timeVN(st.updated) : 'Chưa có dữ liệu'}</span>`;
  $('#refresh').classList.toggle('spin', st.loading);
  const n = activeSignals().length, badge = $('#sig-badge');
  badge.hidden = !n; badge.textContent = n;
}

let current = 'home';
function render({ quiet = false } = {}) {
  const app = $('.app');
  const before = snapshot(app);
  app.classList.toggle('quiet', quiet);
  renderHome(); renderSignals();
  const typing = $('#v-settings').contains(document.activeElement) && document.activeElement.matches('input');
  if (!typing && (current === 'settings' || !quiet)) renderSettings();
  if (current === 'chart' && chartState.charts && quiet) loadChart();
  setStatus();
  if (quiet) flashChanges(app, before); else countUp($(`#v-${current}`));
  st.rendered = true;
}

function show(view, { push = true } = {}) {
  if (!VIEWS.includes(view)) view = 'home';
  current = view;
  $('.app').classList.remove('quiet');
  VIEWS.forEach((v, i) => {
    $(`#v-${v}`).classList.toggle('on', v === view);
    const t = $(`#t-${v}`);
    t.setAttribute('aria-selected', v === view);
    if (v === view) $('.tab-ind').style.transform = `translateX(${i * 100}%)`;
  });
  if (view === 'chart') { if (!$('#c-main')) renderChartShell(); loadChart(); }
  if (view === 'settings') renderSettings();
  countUp($(`#v-${view}`));
  if (push && location.hash !== `#${view}`) history.replaceState(null, '', view === 'home' ? location.pathname : `#${view}`);
  scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
}

let timer;
function schedule() {
  clearInterval(timer);
  if (S.autoRefresh) timer = setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
}

/* ------------------------------------------------------------------ khởi động */
function boot() {
  initFx();
  VIEWS.forEach(v => { $(`#t-${v}`).onclick = () => show(v); });
  $('#refresh').onclick = () => refresh({ manual: true });
  document.addEventListener('click', e => {
    const c = e.target.closest('[data-copy]');
    if (!c) return;
    navigator.clipboard?.writeText(c.dataset.copy).then(() => toast(`Đã copy ${c.dataset.copy}`), () => toast('Không copy được'));
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && Date.now() - st.updated > 30_000) refresh();
  });
  addEventListener('online', () => refresh());
  addEventListener('hashchange', () => { const v = location.hash.slice(1) || 'home'; if (v !== current) show(v, { push: false }); });
  restoreCache();
  render();
  show(location.hash.slice(1) || 'home', { push: false });
  refresh();
  schedule();
  setInterval(setStatus, 30_000);
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
}
boot();
