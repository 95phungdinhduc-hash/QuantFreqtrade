/* Lil_Duck Quant — bản web của dashboard (dashboard/app.py), chạy hoàn toàn trên trình duyệt.
   Cùng 8 tab, cùng sidebar, cùng giao diện (theme.css + fx.js chép nguyên từ dashboard).
   Dữ liệu: giá/nến công khai của Binance (trực tiếp) + docs/data/snapshot.json do máy Mac xuất
   (tin tức, backtest). Không có bot, không có khoá API. Cài đặt chỉ lưu trên thiết bị này. */
import * as Q from './indicators.js';
import * as API from './api.js';
import * as A from './advisor.js';
import * as C from './charts.js';
import * as U from './ui.js';

const { esc, fmtPx, fmtPct, sg, num, trendCls, coinIcon, base, kv, badge, section, meter, dbar, emptyState, metric,
        caption, alert, cols, button, linkButton, chart, expander, dataframe, segmented, slider, selectbox,
        numberInput, textInput, multiselect, sparkline } = U;
const T = U.tip;
const fin = Number.isFinite;
const $ = (s, el = document) => el.querySelector(s);

/* ------------------------------------------------------------------ hằng số (giống dashboard) */
const ALL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT'];
const TFS = ['15m', '1h', '4h', '1d'];
const PER_DAY = { '15m': 96, '1h': 24, '4h': 6, '1d': 1 };
const GITHUB = 'https://github.com/95phungdinhduc-hash/QuantFreqtrade';
const TABS = ['home', 'advisor', 'analysis', 'screener', 'risk', 'news', 'bot', 'backtest'];
const LEGACY = { signals: 'home', chart: 'analysis', settings: 'risk' };   // link cũ của bản web trước
const SHORT_NAMES = { QuantZScoreStrategy: 'Z-Score gốc', QuantHybridStrategy: 'Hybrid', QuantBreakoutStrategy: 'Breakout',
                      QuantSmartDCAStrategy: 'Smart DCA', QuantHybridFuturesStrategy: 'Hybrid Futures' };

const TIPS = {
  price: 'Giá đóng cửa của nến cuối ĐÃ ĐÓNG (lấy trực tiếp từ Binance Spot).',
  chg24: '% thay đổi so với đúng 24 giờ trước. Xanh = tăng, đỏ = giảm.',
  z: 'Z-Score = (giá − trung bình 50 nến) ÷ độ lệch chuẩn σ. ≤ −2: rẻ bất thường (quá bán) · ≥ +2: đắt bất thường (quá mua) · từ −2 đến +2: bình thường, chưa có lợi thế.',
  adf: 'Kiểm định ADF trên 200 nến gần nhất (giống bot). p < 0,20: thị trường ĐI NGANG → đánh hồi quy Z-Score. p ≥ 0,20: CÓ XU HƯỚNG → đánh theo EMA.',
  adf_all: 'ADF trên toàn bộ dữ liệu đang xem — bức tranh dài hạn, chỉ để tham khảo. Bot dùng cột ADF 200.',
  ema_gap: 'EMA20 cao hơn EMA50 bao nhiêu %. > +1%: xu hướng tăng rõ · < −1%: xu hướng giảm rõ · từ −1% đến +1%: chưa rõ xu hướng.',
  kurt: "Độ 'béo đuôi' của lợi nhuận từng nến. > 3: hay có cú tăng/giảm đột ngột lớn bất thường → đặt cắt lỗ cẩn thận, tránh đòn bẩy cao.",
  vol24: 'Tổng giá trị giao dịch 24h (USDT). Càng lớn càng dễ mua bán, ít bị trượt giá.',
  signal: 'Tín hiệu hiện tại theo logic bot Hybrid: Long/Short (Mean Reversion), Xu hướng tăng/giảm (Trend), hoặc Chờ / Đứng ngoài. Chưa tính bộ lọc thị trường SMA200.',
  entry: 'Giá hiện tại — giá tham khảo nếu vào lệnh ngay.',
  sl: 'Cắt lỗ: chạm giá này thì chấp nhận sai và thoát. Đặt cách giá vào 2 độ lệch chuẩn (2σ), giống bot.',
  tp: 'Chốt lời. Mean Reversion: về giá trung bình (ít nhất 1,5σ). Trend: cách giá vào 3σ.',
  size: 'Số USDT nên vào lệnh = số tiền chấp nhận mất ÷ khoảng cách tới cắt lỗ. Cắt lỗ càng xa thì lệnh càng nhỏ, nên rủi ro luôn cố định.',
  risk_usd: 'Số tiền mất nếu giá chạm cắt lỗ = vốn × % rủi ro mỗi lệnh (đặt ở tab 🛡️).',
  rr: 'Tỷ lệ lời/lỗ. 1 : 1,5 = chấp nhận mất 1 đồng để có thể lời 1,5 đồng. Từ 1 : 1,5 trở lên là ổn.',
  near: 'Còn bao xa thì có tín hiệu. Đi ngang: |Z| ÷ 2. Có xu hướng: |EMA gap| ÷ 1%. Đạt 100% là có tín hiệu.',
  web_pill: 'Bản web công khai: tự tính mọi chỉ báo trên trình duyệt từ giá Binance. Bot dry-run chạy riêng trên Mac, không kết nối từ đây.',
  session: 'Phiên giao dịch theo giờ VN. Á 6h–14h: đi ngang · Âu 14h–19h: biến động vừa · Mỹ+Âu 19h–23h: sóng mạnh nhất · Mỹ 23h–6h: chạy theo xu hướng.',
  news: 'Tâm lý tin tức tổng = số tin tốt − số tin xấu (tab 📰). Điểm ≤ −4 thì bot ngừng mở lệnh Long.',
  mkt: 'Bộ lọc thị trường: BTC đóng cửa ngày so với trung bình 200 ngày. Dưới SMA200 → thị trường giảm → bot Spot không mở Long, Futures chỉ Short, alert bot chỉ báo Short.',
  h_pairs: 'Số coin đang theo dõi (đổi ở thanh bên → Dữ liệu → Cặp coin).',
  h_risk: '% vốn chấp nhận mất mỗi lệnh. Số tiền tính trên vốn khai ở tab 🛡️ (chỉ lưu trên thiết bị này).',
  h_strat: 'Hybrid, Breakout, Smart DCA, Futures + bản Z-Score gốc để so sánh. Chi tiết ở tab 🧭 → Thư viện.',
  h_dd: 'Sụt vốn tối đa của bot Hybrid trong lần backtest gần nhất: mức giảm lớn nhất từ đỉnh xuống đáy của tài khoản.',
  bt_profit: 'Lợi nhuận % trên vốn ban đầu trong cả giai đoạn backtest.',
  dd: 'Sụt vốn tối đa (Max Drawdown): mức giảm lớn nhất của tài khoản từ đỉnh xuống đáy. Quan trọng ngang lợi nhuận — DD càng nhỏ càng dễ chịu đựng.',
  trades: 'Tổng số lệnh trong giai đoạn.',
  hold: 'Lợi nhuận nếu chỉ mua rồi giữ các coin suốt giai đoạn — mốc để so sánh chiến lược.',
  mood: 'Trung bình điểm các coin. ≤ −40 rất tiêu cực · −40…−15 tiêu cực · −15…+15 trung lập · +15…+40 tích cực · ≥ +40 rất tích cực.',
  regimes: 'Đi ngang: ADF < 0,20. Tăng: giá trên EMA50 khung 4h VÀ EMA20 > EMA50. Giảm: ngược lại. Chưa rõ: hai điều kiện trái nhau.',
  best: 'Coin có điểm đánh giá cao nhất lúc này và gợi ý hành động cho nó.',
  score: 'Điểm −100…+100 = (35×Xu hướng + 20×Động lượng + 20×Định giá + 10×Ổn định + 15×Tin tức) ÷ 2. Dương = ủng hộ mua, âm = bất lợi.',
  f_trend: 'Xu hướng (35%): +1 nếu giá trên EMA50 khung 4h, +1 nếu EMA20 > EMA50 (ngược lại −1). Từ −2 đến +2.',
  f_momentum: 'Động lượng (20%): % thay đổi giá 7 ngày ÷ 5. Tăng 10%/tuần = +2, giảm 10%/tuần = −2.',
  f_value: 'Định giá (20%): −Z ÷ 1,25. Giá rẻ (Z âm) được điểm dương, giá đắt (Z dương) bị điểm âm.',
  f_volatility: 'Độ ổn định (10%): biến động 24h so với 30 ngày qua. Đang yên nhất tháng = +2, đang dữ dội nhất tháng = −2.',
  f_sentiment: 'Tin tức (15%): điểm tin ÷ 3. Điểm tin ≥ +6 = +2, ≤ −6 = −2.',
  zone: 'Vùng giá gợi ý đặt lệnh chờ — chưa nên vào ngay ở giá hiện tại.',
  evidence: 'Kết quả backtest gần nhất của bot tương ứng với gợi ý này — để biết trong quá khứ nó hiệu quả đến đâu.',
  kelly: 'Half-Kelly: % vốn tối ưu cho mỗi lệnh theo xác suất, tính từ tỷ lệ thắng và lời/lỗ trung bình của lệnh backtest thật (lấy một nửa cho an toàn). 0% = chiến lược không có lợi thế.',
  winrate: 'Tỷ lệ thắng = số lệnh có lãi ÷ tổng số lệnh. Tỷ lệ thắng thấp vẫn có thể lãi nếu lệnh lời lớn hơn nhiều lệnh lỗ.',
};
const RSI_TIP = 'Chế độ thị trường (theo ADF + EMA khung 4h) · RSI 14 nến: < 30 quá bán, > 70 quá mua · % thay đổi giá 7 ngày qua.';

const STRATEGY_LIBRARY = [
  ['QuantHybridStrategy', '🔄 Hybrid (Mean Reversion + Trend)', 'Spot · Long',
   'Thị trường đi ngang: mua khi Z-Score &lt; −2 và đã quay đầu, bán khi về trung bình. Có xu hướng: mua khi EMA20 tách khỏi EMA50.',
   'Cắt lỗ 2σ, hoà vốn khi lời 1,5σ. Ít lệnh, chọn lọc.', './run.sh dryrun'],
  ['QuantBreakoutStrategy', '🚀 Breakout — mua theo đà', 'Spot · Long',
   'Thị trường có xu hướng tăng (ADF cao, EMA50 4h dốc lên): mua khi giá phá đỉnh 48 giờ kèm khối lượng lớn.',
   'Cắt lỗ 2,5×ATR rồi kéo theo đỉnh (3×ATR); thoát khi thủng đáy 24 giờ. Tỷ lệ thắng thấp, lệnh lời lớn.', './run.sh dryrun-breakout'],
  ['QuantSmartDCAStrategy', '🧺 Smart DCA — tích luỹ từng phần', 'Spot · Long · đầu tư',
   'Thị trường hoảng loạn (Z &lt; −2, RSI &lt; 30): mua 1 phần; giảm thêm 4% / 8% thì mua thêm 1 / 1,5 phần.',
   'Chốt khi lời 4% trên giá vốn. Cắt lỗ −12% trên giá vốn; tổng tiền 1 coin giới hạn theo % rủi ro.', './run.sh dryrun-dca'],
  ['QuantHybridFuturesStrategy', '⚡ Hybrid Futures — Long &amp; Short', null,
   'Như Hybrid nhưng thêm lệnh Short khi quá mua / xu hướng giảm.',
   'Đòn bẩy nhân cả lời lẫn lỗ. Chỉ dành cho hồ sơ Cân bằng / Mạo hiểm.', './run.sh dryrun-futures'],
  ['QuantZScoreStrategy', '📐 Z-Score gốc', 'Spot · Long · tham chiếu',
   'Bản chép nguyên logic dự án cũ: mua Z &lt; −2, bán Z ≥ 0, không lọc chế độ thị trường.',
   'Giữ lại để so sánh — không khuyến khích chạy thật.', './run.sh backtest'],
];
const CONTROL = [['🔄 Bot Hybrid (Spot)', 8080, 'Tiền ảo · chạy im lặng'], ['🚀 Bot Breakout', 8082, 'Mua theo đà'],
                 ['🧺 Bot Smart DCA', 8083, 'Tích luỹ từng phần'], ['⚡ Bot Futures', 8081, 'Long + Short, đòn bẩy'],
                 ['🔔 Alert bot', null, 'Gửi tín hiệu có SL/TP lên Telegram']];

/* ------------------------------------------------------------------ cài đặt (chỉ lưu trên máy này) */
const DEF = { capital: 1000, riskPct: 1.5, pairs: ALL_PAIRS.slice(0, 4), tfs: ['1h', '4h'], days: 60, asset: 'BTC/USDT|1h',
              window: 50, profile: 'can_bang', span: '30', dir: 'long', slMult: 2, wf: 'filter', dashUrl: '' };
let S = (() => {
  try {
    const s = { ...DEF, ...JSON.parse(localStorage.getItem('qf.settings') || '{}') };
    s.pairs = (s.pairs || []).filter(p => ALL_PAIRS.includes(p));
    if (!s.pairs.length) s.pairs = DEF.pairs.slice();
    if (!Array.isArray(s.tfs) || !s.tfs.length) s.tfs = DEF.tfs.slice();
    return s;
  } catch { return { ...DEF }; }
})();
const save = () => { try { localStorage.setItem('qf.settings', JSON.stringify(S)); } catch { /* chế độ riêng tư */ } };
const F = { pairs: S.pairs.slice(), tfs: S.tfs.slice(), days: S.days };   // form "Dữ liệu" ở thanh bên: chỉ áp dụng khi bấm nút

/* ------------------------------------------------------------------ dữ liệu: cache + tải lười */
const cache = new Map(), inflight = new Map(), errors = new Map();
let gen = 0;                                   // tăng khi bấm "Tải / cập nhật" -> bỏ cache cũ
function need(key, fn, ttl) {
  const c = cache.get(key);
  const fresh = c && c.gen === gen && Date.now() - c.at < ttl;
  if (!fresh && !inflight.has(key)) {
    const g = gen;
    inflight.set(key, fn().then(v => { cache.set(key, { v, at: Date.now(), gen: g }); errors.delete(key); })
      .catch(e => errors.set(key, e.message || String(e)))
      .finally(() => { inflight.delete(key); queueRender(); }));
  }
  return c?.v;
}
const memoStore = new Map();
function memo(key, src, fn) {
  const m = memoStore.get(key);
  if (m && m.src === src) return m.v;
  const v = fn();
  memoStore.set(key, { src, v });
  return v;
}
const loading = () => inflight.size > 0;

const snap = () => need('snap', API.snapshot, 30 * 60e3);
const regime = () => need('regime', async () => {
  const d = await API.spotKlines('BTC/USDT', '1d', Q.MARKET_SMA + 60);
  return Q.btcRegime(d.filter(k => k.t + 864e5 <= Date.now()));          // bỏ nến ngày đang chạy
}, 15 * 60e3);
const ticks = pairs => need('tick:' + pairs.join(), () => API.tickers(pairs), 60e3);
const h1Candles = p => need('h1:' + p, () => API.spotHistory(p, '1h', 999), 5 * 60e3);
/** Nến 1h + chỉ báo theo chu kỳ ở thanh bên (Tổng quan) */
function homeRows(p) {
  const c = h1Candles(p);
  return c && memo(`home:${p}:${S.window}`, c, () => Q.addIndicators(c, { window: S.window }));
}
/** Nến 1h + chỉ báo tư vấn (Tư vấn, luôn chu kỳ 50 giống advisor.enrich) */
function advRows(p) {
  const c = h1Candles(p);
  return c && memo(`adv:${p}`, c, () => A.enrich(c, 50));
}
const candlesFor = tf => Math.max(500, Math.min(5000, S.days * PER_DAY[tf]));
/** Bộ dữ liệu pair × khung (Phân tích, Screener, Vốn & Rủi ro): bỏ các nến chưa đủ chu kỳ Z giống dropna */
function setRows(p, tf) {
  const c = need(`set:${p}|${tf}`, () => API.spotHistory(p, tf, candlesFor(tf)), 5 * 60e3);
  return c && memo(`set:${p}|${tf}:${S.window}`, c, () => {
    const rows = Q.addIndicators(c, { window: S.window });
    const lr = Q.logReturns(c.map(k => k.c)), ret = Q.pctChange(c.map(k => k.c));
    rows.forEach((r, i) => { r.logRet = lr[i]; r.ret = ret[i]; });
    return rows.filter(r => fin(r.z));
  });
}
const datasets = () => S.pairs.flatMap(p => S.tfs.map(tf => [p, tf]));
function assetPair() {
  const ok = datasets().map(([p, tf]) => `${p}|${tf}`);
  if (!ok.includes(S.asset)) S.asset = ok.includes('BTC/USDT|1h') ? 'BTC/USDT|1h' : ok[0];
  return S.asset.split('|');
}
/** Tin tức: tự lấy trực tiếp mỗi 5 phút (giống dashboard); lỗi mạng thì dùng tin do Mac xuất trong snapshot */
function news() {
  const live = need('news', () => API.liveNews(), 5 * 60e3);
  if (live?.length) return { items: live, score: API.newsSentiment(live), at: cache.get('news')?.at, live: true };
  const s = snap();
  if (s?.news?.length) return { items: s.news, score: s.news_score ?? API.newsSentiment(s.news), at: Date.parse(s.generated), live: false };
  return null;
}
const newsScore = () => news()?.score ?? 0;
const newsWhen = n => n?.at ? (n.live ? `cập nhật ${U.vnTime(n.at)}` : `tin do Mac xuất lúc ${U.vnDate(n.at)}`) : '';
const labelFor = s => s > 0 ? '🟢 Tích cực (Bullish)' : s < 0 ? '🔴 Tiêu cực (Bearish)' : '⚪ Trung lập (Neutral)';
function session() {
  const h = +new Date().toLocaleString('en-US', { hour: 'numeric', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' }) % 24;
  if (h >= 6 && h < 14) return '🇯🇵 Phiên Á (Sideway, biên độ hẹp)';
  if (h >= 14 && h < 19) return '🇬🇧 Phiên Âu (Biến động trung bình)';
  if (h >= 19 && h < 23) return '🇺🇸 Phiên Mỹ + Âu (Thanh khoản cực lớn, sóng mạnh)';
  return '🇺🇸 Phiên Mỹ (Chạy theo xu hướng)';
}
const snapAge = s => s?.generated ? U.vnDate(s.generated) : '';
const marketFilterOn = () => snap()?.config?.market_filter ?? true;

/* ------------------------------------------------------------------ vá DOM tại chỗ (giữ hiệu ứng, cho fx.js nháy giá khi đổi) */
const KEEP = new Set(['data-qin', 'data-qsc', 'data-flash', 'style']);
function morph(el, html) {
  const t = document.createElement('template');
  t.innerHTML = html;
  patchChildren(el, t.content);
}
function patchChildren(a, b) {
  const an = [...a.childNodes], bn = [...b.childNodes];
  bn.forEach((y, i) => {
    const x = an[i];
    if (!x) a.appendChild(y);
    else if (x.nodeType === y.nodeType && x.nodeName === y.nodeName && (x.nodeType !== 1 || x.id === y.id)) patchNode(x, y);
    else a.replaceChild(y, x);
  });
  for (let i = bn.length; i < an.length; i++) an[i].remove();
}
function patchNode(x, y) {
  if (x.nodeType !== 1) { if (x.nodeValue !== y.nodeValue) x.nodeValue = y.nodeValue; return; }
  if (x.hasAttribute('data-keep')) return;                          // biểu đồ Plotly: tự cập nhật bằng Plotly.react
  for (const { name, value } of [...y.attributes]) {
    if (name === 'open' && x.tagName === 'DETAILS') continue;       // giữ trạng thái mở/đóng người dùng chọn
    if (x.getAttribute(name) !== value) x.setAttribute(name, value);
  }
  for (const { name } of [...x.attributes])
    if (!y.hasAttribute(name) && !KEEP.has(name) && !(name === 'open' && x.tagName === 'DETAILS')) x.removeAttribute(name);
  patchChildren(x, y);
  if (x.tagName === 'INPUT' && x !== document.activeElement && x.type !== 'range') x.value = y.getAttribute('value') ?? '';
  if (x.tagName === 'INPUT' && x.type === 'range' && x !== document.activeElement) x.value = y.getAttribute('value');
  if (x.tagName === 'SELECT') { const o = y.querySelector('option[selected]'); x.value = o ? o.value : (x.options[0]?.value ?? ''); }
}

/* ------------------------------------------------------------------ vẽ */
let current = 'home', queued = false;
const plotSig = new Map();
function queueRender() {
  if (queued) return;
  queued = true;
  setTimeout(() => { queued = false; render(); }, 24);   // không dùng requestAnimationFrame: tab ẩn sẽ không bao giờ vẽ lại
}
const RENDER = { home: renderHome, advisor: renderAdvisor, analysis: renderAnalysis, screener: renderScreener,
                 risk: renderRisk, news: renderNews, bot: renderBot, backtest: renderBacktest };
function render() {
  morph($('#side'), renderSide());
  const post = [];
  let html;
  try { html = RENDER[current](post); }
  catch (e) { console.error(e); html = alert('error', `Lỗi hiển thị: ${esc(e.message)}`, '⚠️'); }
  morph($(`#p-${current}`), html);
  for (const [id, sig, fig, rev] of post) {
    if (plotSig.get(id) === sig && document.getElementById(id)?.querySelector('.plot-container')) continue;
    plotSig.set(id, sig);
    const [data, layout] = fig();
    C.plot(id, data, { ...layout, uirevision: rev ?? id }).catch(e => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<div class="loading" style="justify-content:center">⚠️ ${esc(e.message)}</div>`;
      plotSig.delete(id);
    });
  }
}

/* ------------------------------------------------------------------ THANH BÊN */
function renderSide() {
  const opts = datasets().map(([p, tf]) => ({ v: `${p}|${tf}`, l: `${p} · ${tf}` }));
  assetPair();
  return `<div class="side-brand"><div class="logo"><span>🦆</span></div><div><b>Lil_Duck Quant</b><small>Thống kê × Freqtrade</small></div></div>
    <div class="side-label">Thiết lập phân tích</div>
    ${selectbox('asset', opts, S.asset, 'Tài sản', 'Coin và khung nến dùng cho tab 📈 Phân tích, 🛡️ Vốn & Rủi ro và ma trận tương quan ở 🎯 Screener. Danh sách theo phần Dữ liệu bên dưới.')}
    ${slider('window', 10, 200, 1, S.window, 'Chu kỳ Z-Score (nến)', 'Số nến để tính trung bình và độ lệch chuẩn cho Z-Score. Bot luôn dùng 50 — đổi số này chỉ để xem thử, không thay đổi bot.')}
    <div class="side-label">Dữ liệu (trực tiếp từ Binance)</div>
    <div data-testid="stForm">
      ${multiselect('pairs', ALL_PAIRS, F.pairs, 'Cặp coin', 'Coin theo dõi ở 🏠 Tổng quan, 🧭 Tư vấn và 🎯 Screener.')}
      ${multiselect('tfs', TFS, F.tfs, 'Khung thời gian', 'Độ dài mỗi nến. Bot dùng 1h (chính), 4h và 1d (lọc), 15m (backtest chi tiết).')}
      ${numberInput('f_days', 30, 365, 30, F.days, 'Số ngày', 'Lấy bao nhiêu ngày nến gần nhất (tối đa 5000 nến mỗi bộ, ít nhất 500 nến để đủ tính ADF).')}
      ${button('load', '⬇️ &nbsp;Tải / cập nhật từ Binance', { primary: true })}
    </div>
    <div class="side-label">Lối tắt</div>
    ${S.dashUrl ? linkButton(S.dashUrl, '🖥️ &nbsp;Mở dashboard trên Mac') : ''}
    ${textInput('dashUrl', S.dashUrl, 'Link dashboard trên Mac', 'Địa chỉ dashboard đầy đủ (có bot, backtest, AI) qua Tailscale, ví dụ http://100.x.x.x:8502. Chỉ lưu trên thiết bị này, không gửi đi đâu.', 'http://100.x.x.x:8502')}
    ${linkButton(GITHUB, '⭐ &nbsp;Mã nguồn trên GitHub')}
    ${caption('Bản web chạy hoàn toàn trên trình duyệt: không có bot, không có khoá API. Bot dry-run chạy trên Mac: <code>./run.sh start</code>.')}`;
}

/* ------------------------------------------------------------------ TAB 0 — TỔNG QUAN */
function renderHome(post) {
  const pairs = S.pairs, s = snap(), mr = marketFilterOn() ? regime() : null;
  const tick = ticks(pairs) || {};
  const frames = Object.fromEntries(pairs.map(p => [p, homeRows(p)]));
  const nw = news(), ns = nw?.score;
  const hybrid = s?.backtest_summary?.rows?.find(r => r.name === 'QuantHybridStrategy');
  const dash = S.dashUrl ? `<a class="btn ghost" href="${esc(S.dashUrl)}" target="_blank" rel="noopener">Mở dashboard trên Mac ↗</a>`
                         : `<a class="btn ghost" href="#" data-act="focus-dash">Mở dashboard trên Mac ↗</a>`;
  const out = [`
  <div class="hero">
    <div class="hero-bg"><i class="orb o1"></i><i class="orb o2"></i><i class="orb o3"></i></div>
    <div>
      <div class="eyebrow"><span class="live-dot"></span>Hệ thống giao dịch định lượng · Freqtrade 2026</div>
      <h1>Giao dịch crypto bằng <span class="grad">thống kê</span>,<br>không bằng cảm xúc.</h1>
      <p class="lead">Hệ thống tự nhận diện thị trường đang <b>đi ngang</b> hay <b>có xu hướng</b> (kiểm định ADF),
      chọn đúng chiến lược — Mean Reversion hoặc Trend Following — rồi tính khối lượng lệnh theo
      <b>% rủi ro</b> bạn đặt. Mọi tín hiệu đều kiểm chứng được bằng backtest.</p>
      <div class="pills"><span class="pill"><span class="dot ${Object.keys(tick).length ? 'on' : 'warn'}"></span>Bản web · dữ liệu trực tiếp Binance${T(TIPS.web_pill, { down: true })}</span>
        <span class="pill">🕒 ${esc(session())}${T(TIPS.session, { down: true })}</span>
        <span class="pill">📰 Tin tức: ${ns == null ? 'không có dữ liệu' : esc(labelFor(ns))}${T(TIPS.news + (nw ? ` (${newsWhen(nw)})` : ''), { down: true })}</span>
        ${mr ? `<span class="pill"><span class="dot ${mr.up ? 'on' : 'off'}"></span>BTC ${mr.up ? 'trên' : 'dưới'} SMA200 ngày (${sg(mr.gap, 1)}%) · ${mr.up ? 'bot được mở Long' : 'bot đứng ngoài lệnh Long'}${T(TIPS.mkt, { down: true })}</span>` : ''}</div>
      <div class="cta"><a class="btn primary" href="#tin-hieu" data-act="to-signals">Xem tín hiệu hôm nay ↓</a>${dash}</div>
    </div>
    <div class="hero-stats">
      <div class="hstat"><div class="k">Theo dõi${T(TIPS.h_pairs, { down: true })}</div><div class="v">${pairs.length} cặp</div>
        <div class="s">${esc(pairs.map(base).join(' · '))}</div></div>
      <div class="hstat"><div class="k">Rủi ro mỗi lệnh${T(TIPS.h_risk, { down: true, right: true })}</div><div class="v">${S.riskPct.toFixed(1)}%</div>
        <div class="s">≈ $${num(S.capital * S.riskPct / 100)} trên vốn $${num(S.capital, 0)}</div></div>
      <div class="hstat"><div class="k">Chiến lược${T(TIPS.h_strat, { down: true })}</div><div class="v">5 bot</div>
        <div class="s">Hồi quy · Xu hướng · Breakout · DCA · Futures</div></div>
      <div class="hstat"><div class="k">Kiểm soát rủi ro${T(TIPS.h_dd, { down: true, right: true })}</div>${hybrid
        ? `<div class="v">${hybrid.dd.toFixed(1)}%</div><div class="s">sụt vốn tối đa khi backtest</div>`
        : '<div class="v">—</div><div class="s">chạy ./run.sh backtest</div>'}</div>
    </div>
  </div>`];

  const ready = pairs.filter(p => frames[p]);
  if (!ready.length) {
    out.push(errors.size && !loading() ? alert('error', 'Không kết nối được Binance. Kiểm tra mạng rồi bấm "Tải / cập nhật" ở thanh bên.', '📡')
                                       : '<div class="loading">Đang lấy giá trực tiếp từ Binance...</div>');
    return out.join('');
  }
  const tickAt = cache.get('tick:' + pairs.join())?.at;
  out.push(section('Thị trường', 'Giá trực tiếp từ Binance Spot, biểu đồ 72 giờ gần nhất.',
    `${Object.keys(tick).length ? '🟢 Trực tiếp' : '🟠 Mất kết nối'} · cập nhật ${tickAt ? U.vnTime(tickAt, true) : '—'}`));
  out.push(tape(ready, frames, tick), tickers(ready, frames, tick));
  out.push(section('Tín hiệu hệ thống', 'Cùng logic với bot <b>QuantHybridStrategy</b>, tính trên nến 1h đã đóng. '
    + `Khối lượng lệnh tính theo vốn $${num(S.capital, 0)} và rủi ro ${S.riskPct.toFixed(1)}%/lệnh (sửa ở tab 🛡️).`, '', 'tin-hieu'));
  out.push(signals(ready, frames, tick, mr));
  out.push(section('Hiệu suất', 'Bot đang chạy và kết quả kiểm chứng trên dữ liệu quá khứ.'));
  out.push(cols([1, 1.25], [
    emptyState('🤖', 'Bot chạy trên máy Mac', 'Lãi/lỗ của 4 bot dry-run (tiền ảo) chỉ xem ở dashboard riêng trên Mac — bản web công khai không kết nối tới bot.', './run.sh dashboard'),
    backtestCard(s),
  ], { cls: 'a-stretch' }));
  out.push(section('Hệ thống hoạt động thế nào', '4 bước, từ dữ liệu thô đến lệnh có kiểm soát rủi ro.'));
  out.push(`<div class="steps">
    <div class="step"><div class="num">01</div><b>Nhận diện thị trường</b><span>Kiểm định ADF trên 200 nến gần nhất: p &lt; 0.20 là <i>đi ngang</i>, ngược lại là <i>có xu hướng</i>.</span></div>
    <div class="step"><div class="num">02</div><b>Chọn đúng chiến lược</b><span>Đi ngang → mua khi Z-Score &lt; −2 và đã quay đầu. Có xu hướng → theo EMA20/50, lọc thêm khung 4h.</span></div>
    <div class="step"><div class="num">03</div><b>Tính lệnh theo rủi ro</b><span>Cắt lỗ cách 2σ, khối lượng = số tiền chấp nhận mất ÷ khoảng cách cắt lỗ. Hòa vốn khi lời 1.5σ.</span></div>
    <div class="step"><div class="num">04</div><b>Tự bảo vệ</b><span>Tạm dừng sau chuỗi cắt lỗ, dừng khi sụt vốn &gt; 15%, chặn mua khi tin tức quá tiêu cực.</span></div>
  </div>`);
  out.push(`<div class="disclaimer"><b>⚠️ Lưu ý rủi ro.</b> Đây là công cụ phân tích, không phải lời khuyên đầu tư. Giao dịch crypto — đặc biệt Futures có đòn bẩy — có thể mất toàn bộ vốn. Kết quả quá khứ không đảm bảo tương lai. Luôn chạy <code>./run.sh dryrun</code> (tiền ảo) đủ lâu trước khi dùng tiền thật.</div>
    <div class="foot">Lil_Duck Quant × Freqtrade · bản web · dữ liệu Binance · tự cập nhật mỗi 60 giây</div>`);
  return out.join('');
}

function lastPx(p, rows, tick) { return tick[p]?.last || rows?.at(-1)?.c; }
function chg24(p, rows, tick) {
  const pct = tick[p]?.pct;
  return fin(pct) ? pct : rows && rows.length > 24 ? (rows.at(-1).c / rows.at(-25).c - 1) * 100 : NaN;
}
function tape(pairs, frames, tick) {
  const items = pairs.map(p => {
    const pct = chg24(p, frames[p], tick);
    return `<span class="tape-item">${coinIcon(p)}<b>${esc(base(p))}</b><span class="p">${fmtPx(lastPx(p, frames[p], tick))}</span><span class="c ${trendCls(pct)}">${fmtPct(pct)}</span></span>`;
  });
  const reps = Math.max(1, Math.ceil(10 / items.length));
  const one = Array(reps).fill(items.join('')).join('');
  return `<div class="tape" style="--dur:${Math.round(items.length * reps * 4.5)}s"><div class="tape-track">${one}${one}</div></div>`;
}
function tickers(pairs, frames, tick) {
  return `<div class="grid">${pairs.map(p => {
    const d = frames[p], r = d.at(-1), pct = chg24(p, d, tick), cls = trendCls(pct);
    const color = cls === 'up' ? U.UP : cls === 'down' ? U.DOWN : U.TEXT2;
    const sig = Q.signalOf(r), vol = tick[p]?.qvol;
    return `<div class="card"><div class="card-head"><div class="sym">${coinIcon(p)}<div>${esc(base(p))}<small>${esc(p)}</small></div></div>${badge(sig.label, sig.kind)}</div>
      <div class="px">${fmtPx(lastPx(p, d, tick))}</div>
      <span class="chg ${cls}">${fmtPct(pct)} 24h</span>${T(TIPS.chg24)}
      ${sparkline(d.slice(-72).map(x => x.c), color)}
      <div class="meta"><span>Z-Score${T(TIPS.z)} <b>${sg(r.z)}σ</b></span><span>Vol 24h${T(TIPS.vol24, { right: true })} <b>${vol ? '$' + num(vol / 1e6, 0) + 'M' : '—'}</b></span></div></div>`;
  }).join('')}</div>`;
}
function signals(pairs, frames, tick, mr) {
  const fut = snap()?.config?.futures_max_leverage ?? 5;
  const minTab = need('minnot', API.minNotionals, 864e5);
  return `<div class="grid wide">${pairs.map(p => {
    const r = frames[p].at(-1), s = Q.signalOf(r), price = lastPx(p, frames[p], tick);
    const body = [`<p class="why">${s.why}</p>`];
    if (s.act) {
      const plan = Q.planPosition({ capital: S.capital, riskPct: S.riskPct, entry: price, std: r.std, mean: s.mr ? r.mean : null,
                                    isLong: s.isLong, slMult: 2.0, tpMult: s.mr ? 1.5 : 3.0 });
      body.push(kv('Giá vào tham khảo', fmtPx(price), '', TIPS.entry), kv('Cắt lỗ (2σ)', fmtPx(plan.stopLoss), 'down', TIPS.sl),
                kv('Chốt lời', fmtPx(plan.takeProfit), 'up', TIPS.tp), kv('Quy mô lệnh', '$' + num(plan.positionUsd), '', TIPS.size),
                kv('Rủi ro nếu chạm SL', '-$' + num(plan.riskUsd), 'down', TIPS.risk_usd), kv('Tỷ lệ lời/lỗ', `1 : ${plan.rr.toFixed(1)}`, '', TIPS.rr));
      body.push(howTo(p, r, s, plan, price, mr, fut, API.minNotionalOf(minTab, p) ?? Q.DEFAULT_MIN_NOTIONAL));
    } else {
      body.push(meter(s.progress, s.need, s.now),
        `<div class="meta" style="margin-top:10px"><span>Mức gần tín hiệu${T(TIPS.near)}</span><b>${(Math.min(s.progress, 1) * 100).toFixed(0)}%</b></div>`);
    }
    const glow = { long: 'glow-long', short: 'glow-short' }[s.kind] || '';
    return `<div class="card ${glow}"><div class="card-head"><div class="sym">${coinIcon(p)}<div>${esc(p)}<small>Nến 1h đã đóng · ${U.utc(r.t)} UTC</small></div></div>${badge(s.label, s.kind)}</div>
      <div class="strat">${esc(s.strat)}${T(TIPS.signal)}</div>${body.join('')}</div>`;
  }).join('')}</div>`;
}
const cp = (v, text = v) => `<code class="copy" data-copy="${esc(v)}">${esc(text)}</code>`;
const raw = (v, ref) => v.toFixed(Math.abs(ref) >= 10 ? 2 : Math.abs(ref) >= 1 ? 3 : 5);
const qtyRaw = q => q >= 100 ? q.toFixed(1) : q >= 1 ? q.toFixed(3) : q.toFixed(5);
/** Cách đặt lệnh tay trên Binance (Spot + Futures) — giống tin nhắn alert bot */
function howTo(p, r, s, plan, price, mr, maxLev, minNot) {
  const b = base(p), sym = p.replace('/', '');
  const lev = Math.min(s.mr ? (Math.abs(r.z) >= 3 ? 5 : 2) : 3, maxLev);
  const futUsd = Math.max(plan.positionUsd, minNot), futQty = futUsd / price;
  const spotUsd = Math.min(plan.positionUsd, S.capital), spotQty = spotUsd / price;
  const sl = raw(plan.stopLoss, price), tp = raw(plan.takeProfit, price);
  const blocked = mr && mr.up !== s.isLong;
  return `<details class="how"><summary>📋 Cách đặt lệnh trên Binance (chạm số để copy)</summary>
    ${blocked ? `<p class="note">⚠️ Bộ lọc thị trường: BTC đang ${mr.up ? 'trên' : 'dưới'} SMA200 ngày → các bot đứng ngoài hướng ${s.isLong ? 'Long' : 'Short'} này.</p>` : ''}
    ${s.isLong ? `<h5>Spot (không đòn bẩy)</h5><ol class="steps-order">
      <li>Binance → <b>Giao dịch → Spot</b> → cặp <b>${esc(b)}/USDT</b>.</li>
      <li>Mua <b>Market</b> ${cp(qtyRaw(spotQty))} ${esc(b)} (≈ $${num(spotUsd)}).${spotUsd < plan.positionUsd ? ' Vốn không đủ quy mô đề xuất → mua tối đa bằng vốn.' : ''}</li>
      <li>Đặt lệnh bán <b>OCO</b>: chốt lời (Limit) ${cp(tp)} · giá kích hoạt cắt lỗ (Stop) ${cp(sl)}.</li></ol>`
      : '<p class="note">Spot không bán khống được → chỉ đặt lệnh Short trên Futures.</p>'}
    <h5>Futures USDⓈ-M</h5><ol class="steps-order">
      <li>Futures → <b>${esc(sym)}</b> Perpetual → chế độ <b>Isolated</b>, đòn bẩy <b>${lev}x</b>.</li>
      <li>Mở <b>${s.isLong ? 'Long' : 'Short'}</b> Market ${cp(qtyRaw(futQty))} ${esc(b)} (giá trị ≈ $${num(futUsd)}, ký quỹ ≈ $${num(futUsd / lev)}).</li>
      <li>Bật <b>TP/SL</b>: TP ${cp(tp)} · SL ${cp(sl)} (theo Mark Price).</li></ol>
    ${futUsd > plan.positionUsd ? `<p class="note">Sàn yêu cầu lệnh Futures tối thiểu $${num(minNot, 0)} → lỗ tối đa thực tế ≈ $${num(futUsd * plan.stopDistPct)}.</p>` : ''}
  </details>`;
}
function backtestCard(s) {
  const bt = s?.backtest_summary;
  if (!bt?.rows?.length) return emptyState('📊', 'Chưa có kết quả backtest', 'Chạy backtest trên Mac rồi xuất dữ liệu cho web.', './run.sh web-data');
  const names = { QuantHybridStrategy: 'Hybrid <small>nâng cấp</small>', QuantZScoreStrategy: 'Z-Score <small>bản gốc</small>',
                  QuantBreakoutStrategy: 'Breakout <small>mới</small>', QuantSmartDCAStrategy: 'Smart DCA <small>mới</small>' };
  const pc = v => v > 0 ? 'up' : 'down';
  const cells = [`<div class="h">Chiến lược</div><div class="h n">Lợi nhuận${T(TIPS.bt_profit)}</div><div class="h n">Sụt vốn${T(TIPS.dd)}</div><div class="h n hide-sm">Lệnh${T(TIPS.trades, { right: true })}</div>`];
  for (const r of [...bt.rows].sort((a, b) => b.profit - a.profit))
    cells.push(`<div class="name">${names[r.name] || esc(r.name)}</div><div class="n" style="color:var(--${pc(r.profit)})">${fmtPct(r.profit)}</div><div class="n">${r.dd.toFixed(1)}%</div><div class="n hide-sm">${r.trades}</div>`);
  if (bt.market != null)
    cells.push(`<div class="name">Mua &amp; giữ <small>thị trường</small>${T(TIPS.hold)}</div><div class="n" style="color:var(--${pc(bt.market)})">${fmtPct(bt.market)}</div><div class="n">—</div><div class="n hide-sm">—</div>`);
  return `<div class="card" style="height:100%"><div class="card-head"><b style="color:var(--text)">📊 Backtest gần nhất</b><span class="strat" style="margin:0">${esc(bt.start)} → ${esc(bt.end)}</span></div>
    <div class="cmp" style="margin-top:10px">${cells.join('')}</div>
    <div class="strat" style="margin:14px 0 0">Kết quả thật, không chỉnh sửa. Lỗ ít hơn thị trường chưa có nghĩa là có lãi — hãy chạy dry-run vài tuần trước khi dùng tiền thật.</div></div>`;
}

/* ------------------------------------------------------------------ TAB TƯ VẤN */
function renderAdvisor(post) {
  const prof = A.PROFILES[S.profile] || A.PROFILES.can_bang;
  const out = [section('🧭 Tư vấn chiến lược', 'Hệ thống gom <b>mọi phân tích</b> (ADF, Z-Score, EMA 1h &amp; 4h, động lượng 7 ngày, biến động, tin tức, kết quả backtest) thành điểm đánh giá, chiến lược phù hợp và phân bổ vốn theo hồ sơ rủi ro.'),
    '<div class="disclaimer" style="margin-top:0"><b>Đây là phân tích tự động theo quy tắc, không phải lời khuyên đầu tư cá nhân.</b> Mọi kết luận suy ra từ số liệu bên dưới và có thể sai. Bạn tự chịu trách nhiệm với quyết định của mình — hãy thử bằng dry-run trước.</div>',
    cols([2, 1], [
      segmented('profile', Object.entries(A.PROFILES).map(([v, p]) => ({ v, l: p.label })), S.profile, 'Hồ sơ rủi ro của bạn',
        'Thận trọng: rủi ro 0,75%/lệnh, chỉ Spot, ≥ 50% tiền mặt. Cân bằng: 1,5%/lệnh, Futures ≤ x2, ≥ 30% tiền mặt. Mạo hiểm: 2,5%/lệnh, Futures ≤ x3, ≥ 10% tiền mặt.'),
      button('apply-risk', `Áp dụng rủi ro ${prof.risk_pct}%/lệnh`, { disabled: Math.abs(prof.risk_pct - S.riskPct) < 1e-9 }),
    ], { align: 'bottom' }),
    caption(`${esc(prof.desc)} · Vốn tính toán: $${num(S.capital, 0)} (sửa ở tab 🛡️).`)];

  const s = snap(), ns = newsScore(), tick = ticks(S.pairs) || {};
  const frames = Object.fromEntries(S.pairs.map(p => [p, advRows(p)]));
  const items = S.pairs.filter(p => frames[p]?.length).map(p =>
    A.assess(p, frames[p], { newsScore: ns, capital: S.capital, riskPct: prof.risk_pct, allowFutures: prof.futures, price: tick[p]?.last }));
  if (items.length < S.pairs.length && loading()) { out.push('<div class="loading">Đang phân tích ~1000 nến mỗi coin...</div>'); return out.join(''); }
  if (!items.length) { out.push(emptyState('📡', 'Không có dữ liệu', 'Kiểm tra mạng hoặc bấm "Tải / cập nhật" ở thanh bên.')); return out.join(''); }
  const evidence = s?.evidence || {};

  const mr = regime();
  if (mr) {
    const on = marketFilterOn();
    const state = mr.up ? '🟢 Thị trường chung đang TĂNG (BTC trên SMA200 ngày) → các bot được phép mở lệnh Long.'
      : '🔴 Thị trường chung đang GIẢM (BTC dưới SMA200 ngày) → các bot Spot <b>đứng ngoài</b>, không mở lệnh Long mới; bot Futures chỉ được Short.';
    const d = new Date(mr.t);
    out.push(`<div class="zone" style="margin-top:14px;font-weight:500;color:var(--text)"><b>Bộ lọc thị trường ${on ? '(đang BẬT)' : '(đang TẮT)'}</b>${T(TIPS.mkt, { down: true })}<b>:</b> ${state}<br>
      <span style="color:var(--text2)">BTC đóng cửa ngày ${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}: ${fmtPx(mr.close)} · SMA200 ngày: ${fmtPx(mr.sma)} · cách ${sg(mr.gap, 1)}%</span></div>`);
  }

  const scores = items.map(a => a.score), avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  const [label, kind] = A.mood(scores);
  const cnt = k => items.filter(a => a.regime === k).length;
  const best = items.reduce((a, b) => b.score > a.score ? b : a);
  out.push(`<div class="mood" style="margin-top:14px">
    <div class="card"><div class="strat" style="margin:0">Nhiệt kế thị trường${T(TIPS.mood, { down: true })}</div>
      <div class="score ${trendCls(avg)}">${sg(avg, 0)} <small>/ 100</small></div>${dbar(avg, 100)}${badge(label, kind)}</div>
    <div class="card"><div class="strat" style="margin:0">Chế độ thị trường${T(TIPS.regimes, { down: true })}</div>
      ${kv('Đi ngang', String(cnt('range')))}${kv('Xu hướng tăng', String(cnt('up')), 'up')}${kv('Xu hướng giảm', String(cnt('down')), 'down')}${kv('Chưa rõ', String(cnt('unclear')))}</div>
    <div class="card"><div class="strat" style="margin:0">Điểm cao nhất${T(TIPS.best, { down: true })}</div>
      <div class="sym" style="margin:6px 0">${coinIcon(best.pair)}${esc(best.pair)}</div>
      <div class="score ${trendCls(best.score)}">${sg(best.score, 0)}</div><div class="strat" style="margin:6px 0 0">${esc(best.stance)}</div></div>
    <div class="card"><div class="strat" style="margin:0">Tin tức${T(TIPS.news, { down: true, right: true })}</div>
      <div class="score ${trendCls(ns)}">${sg(ns, 0)}</div><div class="strat" style="margin:8px 0 0">${esc(labelFor(ns))}</div>
      <div class="evidence">Bot chặn lệnh Long khi ≤ −4 · ${newsWhen(news())}</div></div>
  </div>`);

  out.push(section('Đánh giá &amp; chiến lược từng coin', 'Điểm = 35% xu hướng + 20% động lượng + 20% định giá (Z) + 10% độ ổn định (biến động thấp) + 15% tin tức. Xanh = ủng hộ mua, đỏ = bất lợi.'));
  out.push(`<div class="grid wide">${[...items].sort((a, b) => b.score - a.score).map(a => {
    const frows = Object.entries(a.factors).map(([k, v]) => `<span>${A.FACTOR_LABELS[k]}${T(TIPS['f_' + k])}</span>${dbar(v, 2)}<b>${sg(v, 1)}</b>`).join('');
    const p = a.plan, strat = A.STRATEGY_OF[a.playbook], ev = strat ? evidence[strat] : null, m = a.metrics;
    return `<div class="card ${a.kind === 'long' ? 'glow-long' : a.kind === 'short' ? 'glow-short' : ''}">
      <div class="card-head"><div class="sym">${coinIcon(a.pair)}<div>${esc(a.pair)}<small>${esc(a.regimeLabel)} · RSI ${m.rsi.toFixed(0)} · 7 ngày ${fmtPct(m.roc7d, 1)}${T(RSI_TIP)}</small></div></div>
        <div style="text-align:right"><div class="score ${trendCls(a.score)}">${sg(a.score, 0)}${T(TIPS.score, { right: true })}</div></div></div>
      ${dbar(a.score, 100)}
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin:10px 0 4px">${badge(a.stance, a.kind)} ${badge(a.regimeLabel, 'info')}</div>
      <div class="strat">${esc(a.playbookLabel)}</div>
      <div class="factors">${frows}</div>
      <ul class="reasons">${a.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
      ${a.zone ? `<div class="zone">🎯 ${esc(a.zone)}${T(TIPS.zone)}</div>` : ''}
      ${p ? kv('Giá vào tham khảo', fmtPx(p.entry), '', TIPS.entry) + kv('Cắt lỗ', fmtPx(p.stopLoss), 'down', TIPS.sl) + kv('Chốt lời', fmtPx(p.takeProfit), 'up', TIPS.tp)
          + kv('Khối lượng', '$' + num(p.positionUsd, 0), '', TIPS.size) + kv('Mất tối đa nếu sai', '-$' + num(p.riskUsd), 'down', TIPS.risk_usd)
          + kv('Lời / lỗ', `1 : ${p.rr.toFixed(1)}`, '', TIPS.rr) : ''}
      ${ev ? `<div class="evidence">Kiểm chứng: bot <b>${strat}</b> backtest <b style="color:var(--${ev.profit > 0 ? 'up' : 'down'})">${fmtPct(ev.profit)}</b>, sụt vốn ${ev.dd.toFixed(1)}%, ${ev.trades} lệnh (thị trường ${fmtPct(ev.market, 1)})${T(TIPS.evidence)}</div>` : ''}
    </div>`;
  }).join('')}</div>`);

  out.push(section(`Phân bổ vốn đề xuất · hồ sơ ${prof.label}`, `Chỉ chọn coin có điểm dương và không ở xu hướng giảm. Tỷ trọng tỷ lệ với điểm ÷ biến động (coin càng biến động càng ít tiền), tối đa ${(prof.max_weight * 100).toFixed(0)}%/coin, tiền mặt tối thiểu ${(prof.cash_min * 100).toFixed(0)}%.`));
  const alloc = A.allocate(items, S.profile, S.capital);
  const corrs = correlatedPairs(frames);
  out.push(cols([1.3, 1], [chart('c-alloc', 80 + 52 * alloc.length),
    dataframe([
      { key: 'asset', label: 'Tài sản', help: 'Coin được chọn (điểm > 0, không ở xu hướng giảm) + tiền mặt.' },
      { key: 'weight', label: 'Tỷ trọng', progress: true, fmt: v => (v * 100).toFixed(0) + '%', help: '% vốn đề xuất. Tỷ lệ với điểm ÷ biến động năm, có trần mỗi coin theo hồ sơ.' },
      { key: 'usdt', label: 'USDT', num: true, fmt: v => '$' + num(v, 0), help: 'Số tiền tương ứng trên vốn khai ở tab 🛡️.' },
      { key: 'score', label: 'Điểm', num: true, fmt: v => sg(v, 0), help: TIPS.score },
      { key: 'why', label: 'Lý do', help: 'Gợi ý hành động cho coin này (xem thẻ coin ở trên).' }], alloc)
    + (corrs.length ? alert('warning', `<b>Các coin đang đi cùng nhau</b> (tương quan ≥ 0.85): ${corrs.map(([a, b, c]) => `${base(a)}–${base(b)} ${c.toFixed(2)}`).join(' · ')}. Giữ nhiều coin tương quan cao gần như nhân rủi ro lên — đa dạng hoá thật sự cần tài sản ít tương quan.`, '🔗') : '')
    + (alloc.length === 1 ? alert('info', 'Hiện không có coin nào đủ điểm — hệ thống đề xuất giữ 100% tiền mặt.', '🛡️') : '')], { gap: 'large' }));
  post.push(['c-alloc', JSON.stringify(alloc.map(a => [a.asset, a.weight.toFixed(4)])), () => C.allocFigure(alloc)]);

  out.push(section('🤖 Nhờ AI diễn giải', 'Gemini đọc bảng số liệu ở trên và tóm tắt bằng lời dễ hiểu (không tự bịa số).'));
  out.push(alert('info', 'Phần này chỉ có ở dashboard trên Mac (cần khoá Gemini riêng — không đưa khoá lên trang web công khai).', 'ℹ️'));

  out.push(section('📚 Thư viện chiến lược', '5 bot Freqtrade có sẵn — dùng bot nào tuỳ chế độ thị trường và hồ sơ rủi ro. Số liệu là kết quả backtest gần nhất (chạy lại bằng <code>./run.sh backtest-all</code>).'));
  const lev = s?.config?.futures_max_leverage ?? 2;
  out.push(`<div class="lib">${STRATEGY_LIBRARY.map(([key, title, tag, when, risk, cmd]) => {
    const ev = evidence[key];
    const res = ev ? kv('Lợi nhuận backtest', fmtPct(ev.profit), ev.profit > 0 ? 'up' : 'down', TIPS.bt_profit) + kv('Sụt vốn tối đa', `${ev.dd.toFixed(1)}%`, '', TIPS.dd)
                     + kv('Số lệnh · tỷ lệ thắng', `${ev.trades} · ${ev.win.toFixed(0)}%`, '', TIPS.winrate)
                   : kv('Backtest', 'chưa có — chạy ./run.sh backtest-all');
    return `<div class="card"><h4>${title}</h4>${badge(tag || `Futures · tối đa x${lev}`, 'info')}
      <div class="when"><b>Khi nào dùng:</b> ${when}<br><b>Quản trị rủi ro:</b> ${risk}</div>${res}<div style="margin-top:12px"><span class="cmd">${esc(cmd)}</span></div></div>`;
  }).join('')}</div>`);
  return out.join('');
}
/** Cặp coin tương quan ≥ 0.85 (lợi nhuận log 720 nến gần nhất, khớp theo thời gian) */
function correlatedPairs(frames, threshold = 0.85) {
  const series = Object.entries(frames).filter(([, r]) => r?.length).map(([p, r]) => [p, new Map(r.slice(-720).map(x => [x.t, x.logRet]))]);
  const out = [];
  for (let i = 0; i < series.length; i++) for (let j = i + 1; j < series.length; j++) {
    const [a, ma] = series[i], [b, mb] = series[j], xa = [], xb = [];
    for (const [t, v] of ma) if (mb.has(t)) { xa.push(v); xb.push(mb.get(t)); }
    const c = Q.corr(xa, xb);
    if (c >= threshold) out.push([a, b, c]);
  }
  return out;
}

/* ------------------------------------------------------------------ TAB PHÂN TÍCH */
function renderAnalysis(post) {
  const [pair, tf] = assetPair();
  const df = setRows(pair, tf);
  if (!df?.length) return errors.has(`set:${pair}|${tf}`) && !loading()
    ? alert('error', `Không tải được dữ liệu ${esc(pair)} · ${esc(tf)} từ Binance.`, '📡') : '<div class="loading">Đang tải nến và tính chỉ báo...</div>';
  const last = df.at(-1), sig = Q.signalOf(last);
  const kurt = Q.kurtosis(df.map(r => r.logRet));
  const out = [`<div class="sec"><div><h3>${coinIcon(pair)} &nbsp;${esc(pair)} <span style="color:var(--muted);font-weight:600">· ${esc(tf)}</span> &nbsp;${badge(sig.label, sig.kind)}</h3>
    <p>${sig.why}</p></div><span class="aside">Nến cuối: ${U.utc(last.t, true)} UTC · ${df.length.toLocaleString('en-US')} nến đã đóng từ Binance</span></div>`];
  out.push(`<div class="mgrid odd" style="--n:5">${[
    metric('Giá', fmtPx(last.c), '', { help: TIPS.price }),
    metric('Z-Score', `${sg(last.z)}σ`, last.z > 2 ? 'Quá mua' : last.z < -2 ? 'Quá bán' : 'Trung tính', { help: TIPS.z }),
    metric('ADF 200 nến', fin(last.adf) ? last.adf.toFixed(3) : '—', last.adf < Q.ADF_THRESHOLD ? 'Đi ngang' : 'Có xu hướng', { help: TIPS.adf }),
    metric('EMA20 / EMA50', `${sg(last.gap)}%`, last.gap > Q.TREND_GAP ? 'Tăng rõ' : last.gap < -Q.TREND_GAP ? 'Giảm rõ' : 'Chưa rõ', { help: TIPS.ema_gap }),
    metric('Kurtosis', fin(kurt) ? kurt.toFixed(2) : '—', kurt > 3 ? 'Đuôi béo — dễ có cú sốc' : 'Ổn định', { help: TIPS.kurt }),
  ].join('')}</div>`);
  const spans = [{ v: '7', l: '7 ngày' }, { v: '30', l: '30 ngày' }, { v: '90', l: '90 ngày' }, { v: 'all', l: 'Tất cả' }];
  out.push(segmented('span', spans, S.span));
  const view = S.span === 'all' ? df : df.filter(r => r.t >= last.t - +S.span * 864e5);
  out.push(chart('c-price', innerWidth < 640 ? 640 : 820));
  out.push(caption('▲▼ = điểm Mean Reversion trong quá khứ (đi ngang + Z vượt ±2 rồi quay đầu). Vùng xanh ở ô ADF = thị trường đi ngang. Kéo để xem, chạm đúp để thu phóng lại.'));
  post.push(['c-price', `${pair}|${tf}|${S.window}|${S.span}|${last.t}|${view.length}`, () => C.priceFigure(view), `${pair}|${tf}|${S.span}`]);
  return out.join('');
}

/* ------------------------------------------------------------------ TAB SCREENER */
function renderScreener(post) {
  const [, atf] = assetPair();
  const out = [section('🎯 Screener theo chế độ thị trường', 'ADF &lt; 0.20 ⇒ đi ngang ⇒ đánh hồi quy Z-Score. Ngược lại ⇒ đánh theo xu hướng EMA. Cùng logic với bot Freqtrade.')];
  const sets = datasets(), rows = [], returns = {};
  for (const [p, tf] of sets) {
    const d = setRows(p, tf);
    if (!d?.length) continue;
    const r = d.at(-1);
    rows.push({ asset: p, tf, price: r.c, spark: d.slice(-60).map(x => x.c), z: r.z, adf: r.adf,
                adfAll: memo(`adfall:${p}|${tf}`, d, () => Q.adfPvalue(d.map(x => x.c))), gap: r.gap, target: r.mean, rec: Q.regimeSignal(r) });
    if (tf === atf) returns[p] = d;
  }
  if (rows.length < sets.length && loading()) out.push(`<div class="loading">Đang tải ${rows.length}/${sets.length} bộ dữ liệu...</div>`);
  if (rows.length) {
    out.push(dataframe([
      { key: 'asset', label: 'Tài sản', help: 'Cặp coin.' }, { key: 'tf', label: 'Khung', help: 'Độ dài mỗi nến: 15m, 1h, 4h, 1d.' },
      { key: 'price', label: 'Giá', num: true, fmt: v => '$' + v.toFixed(4), help: 'Giá đóng cửa của nến cuối đã đóng.' },
      { key: 'spark', label: 'Diễn biến (60 nến)', spark: true, help: 'Biểu đồ giá 60 nến gần nhất.' },
      { key: 'z', label: 'Z-Score', num: true, fmt: v => `${sg(v)} σ`, help: TIPS.z },
      { key: 'adf', label: 'ADF 200', num: true, fmt: v => v.toFixed(3), help: TIPS.adf },
      { key: 'adfAll', label: 'ADF toàn bộ', num: true, fmt: v => v.toFixed(3), help: TIPS.adf_all },
      { key: 'gap', label: 'EMA gap %', num: true, fmt: v => `${sg(v)}%`, help: TIPS.ema_gap },
      { key: 'target', label: 'Mục tiêu (TB)', num: true, fmt: v => '$' + v.toFixed(4), help: 'Giá trung bình — nơi Mean Reversion kỳ vọng giá quay về (mục tiêu chốt lời).' },
      { key: 'rec', label: 'Khuyến nghị', help: '🟢 MUA / 🔴 BÁN-SHORT: Mean Reversion (đi ngang + Z vượt ±2). 🚀 / 🔻: xu hướng EMA. ⚪: chờ hoặc đứng ngoài. Cùng logic bot Hybrid.' },
    ], rows.sort((a, b) => a.z - b.z)));
  }
  out.push(section(`🔗 Ma trận tương quan · khung ${esc(atf)}`, 'Tương quan &gt; 0.80 ⇒ chỉ nên giữ 1 trong 2 đồng để tránh nhân đôi rủi ro.'
    + T('Mức độ 2 coin lên xuống cùng nhau, từ −1 đến +1. Gần +1 (đỏ): đi cùng nhau · gần 0 (xám): độc lập, tốt cho đa dạng hoá · âm (xanh): đi ngược nhau. Đường chéo luôn = 1.')));
  const names = Object.keys(returns).sort();
  if (names.length >= 2) {
    const maps = names.map(p => new Map(returns[p].map(x => [x.t, x.logRet])));
    const m = names.map((_, i) => names.map((__, j) => {
      if (i === j) return 1;
      const xa = [], xb = [];
      for (const [t, v] of maps[i]) if (maps[j].has(t)) { xa.push(v); xb.push(maps[j].get(t)); }
      return Q.corr(xa, xb);
    }));
    out.push(chart('c-corr', 420));
    post.push(['c-corr', JSON.stringify(m.map(r => r.map(v => v.toFixed(3)))) + names, () => C.corrFigure(names, m)]);
  } else out.push(caption('Cần ít nhất 2 coin có cùng khung với "Tài sản" ở thanh bên.'));
  return out.join('');
}

/* ------------------------------------------------------------------ TAB VỐN & RỦI RO */
function renderRisk(post) {
  const [pair, tf] = assetPair();
  const out = [section(`🛡️ Máy tính đi vốn · ${esc(pair)}`, 'Đặt số tiền chấp nhận mất mỗi lệnh — hệ thống tự tính khối lượng, cắt lỗ và chốt lời. (Bản web chỉ để tính — không đổi cài đặt bot.)')];
  const left = numberInput('capital', 10, 1e9, 100, S.capital, 'Tổng vốn (USDT)', 'Vốn dùng để TÍNH TOÁN (quy mô lệnh, số tiền mất nếu sai). Chỉ lưu trên thiết bị này.', 2)
    + slider('riskPct', 0.5, 5, 0.5, S.riskPct, 'Rủi ro tối đa mỗi lệnh (%)', '% vốn chấp nhận mất nếu một lệnh chạm cắt lỗ. Người mới nên 0,5–1,5%.', 2)
    + segmented('dir', [{ v: 'long', l: '🟢 Long' }, { v: 'short', l: '🔴 Short' }], S.dir, 'Hướng', 'Long = mua, lời khi giá lên. Short = bán khống, lời khi giá xuống (chỉ làm được trên Futures).')
    + slider('slMult', 0.5, 3.5, 0.5, S.slMult, 'Cắt lỗ cách bao nhiêu σ', 'Khoảng cách từ giá vào tới cắt lỗ, tính bằng độ lệch chuẩn σ. Xa hơn = ít bị quét nhưng lệnh nhỏ hơn. Bot Hybrid mặc định 2σ.', 2);
  const df = setRows(pair, tf);
  if (!df?.length) { out.push(cols([1, 2], [left, '<div class="loading">Đang tải nến...</div>'], { gap: 'large' })); return out.join(''); }
  const last = df.at(-1), isLong = S.dir === 'long';
  const plan = Q.planPosition({ capital: S.capital, riskPct: S.riskPct, entry: last.c, std: last.std, mean: last.mean, isLong, slMult: S.slMult });
  const [v95, cv95] = Q.valueAtRisk(df.map(r => r.ret));
  const right = `<div class="mgrid" style="--n:3">
      ${metric('Rủi ro tối đa', '-$' + num(plan.riskUsd), `${S.riskPct}% vốn`, { help: TIPS.risk_usd })}
      ${metric('Quy mô lệnh', '$' + num(plan.positionUsd, 0), `${plan.coinAmount.toFixed(4)} coin`, { help: TIPS.size })}
      ${metric('Đòn bẩy cần', `${plan.leverageNeeded}x`, 'Cẩn thận nếu > 5x', { help: 'Quy mô lệnh ÷ vốn. 1x: Spot làm được. > 1x: cần Futures hoặc vào lệnh nhỏ hơn. > 5x: rất nguy hiểm, dễ bị thanh lý.' })}
      ${metric('Cắt lỗ', fmtPx(plan.stopLoss), `Cách ${(plan.stopDistPct * 100).toFixed(2)}%`, { help: TIPS.sl })}
      ${metric('Chốt lời', fmtPx(plan.takeProfit), `R:R = 1:${plan.rr.toFixed(1)}`, { help: TIPS.tp + ' ' + TIPS.rr })}
      ${metric('VaR 95% / nến', `${(v95 * 100).toFixed(2)}%`, `CVaR ${(cv95 * 100).toFixed(2)}%`, { help: "VaR 95%: trong 95% số nến, mức lỗ KHÔNG vượt quá con số này. CVaR: trung bình lỗ trong 5% số nến tệ nhất — 'ngày xấu' thật sự trông như thế nào." })}
    </div>`;
  out.push(cols([1, 2], [left, right], { gap: 'large' }));
  out.push(chart('c-plan', 380));
  out.push(caption('Half-Kelly tính từ lệnh backtest thật nằm ở tab 📊 Backtest.'));
  post.push(['c-plan', `${pair}|${tf}|${last.t}|${plan.stopLoss}|${plan.takeProfit}`, () => C.planFigure(df, plan, isLong), `${pair}|${tf}`]);
  return out.join('');
}

/* ------------------------------------------------------------------ TAB TIN TỨC */
function renderNews() {
  const n = news();
  if (!n) return loading() ? '<div class="loading">Đang lấy tin mới nhất...</div>'
    : emptyState('📡', 'Không kết nối được nguồn tin', 'Kiểm tra mạng rồi tải lại trang.');
  const items = n.items, score = n.score;
  const when = t => { const d = Date.parse(t); return Number.isFinite(d) ? U.vnDate(d) : t; };
  return section('📰 Tin tức &amp; tâm lý thị trường', 'Tin mới nhất từ CoinDesk và CoinTelegraph, chấm điểm tăng/giảm theo từ khoá.', 'Bot chặn lệnh Long khi điểm tổng ≤ −4')
    + `<div class="mgrid" style="--n:3">${metric('Tin tích cực', String(items.filter(x => x.score > 0).length), '', { help: 'Số tin có nhiều từ khoá tích cực hơn tiêu cực (surge, rally, ETF, approve, record…).' })}
      ${metric('Tin tiêu cực', String(items.filter(x => x.score < 0).length), '', { help: 'Số tin có nhiều từ khoá tiêu cực hơn (crash, hack, ban, SEC, lawsuit, dump, fear…).' })}
      ${metric('Điểm tổng', sg(score, 0), labelFor(score), { help: 'Số tin tích cực − số tin tiêu cực. Điểm ≤ −4 thì bot ngừng mở lệnh Long mới. Chấm theo từ khoá nên chỉ là nhiệt kế thô.' })}</div>`
    + `<div class="grid wide" style="margin-top:14px">${items.map(x => {
      const kind = x.score > 0 ? 'long' : x.score < 0 ? 'short' : 'wait';
      return `<a class="card news" href="${esc(x.link)}" target="_blank" rel="noopener"><div class="card-head"><span class="src">${esc(x.source)}</span>${badge(labelFor(x.score), kind)}</div>
        <span class="t">${esc(x.title)}</span><span class="time">🕒 ${esc(when(x.published))}</span></a>`;
    }).join('')}</div>`
    + caption(n.live ? `🟢 Tự cập nhật mỗi 5 phút · ${newsWhen(n)} (giờ Việt Nam).`
                     : `🟠 Chưa đọc được tin trực tiếp — đang dùng ${newsWhen(n)}. Trang tự thử lại sau 5 phút.`);
}

/* ------------------------------------------------------------------ TAB BOT */
function renderBot() {
  return section('🎛️ Bật / tắt bot', 'Bot chạy <b>nền trên máy Mac</b> — mọi bot đều là <b>dry-run (tiền ảo)</b>. Bản web công khai không điều khiển được bot, để không ai khác bật/tắt được bot của bạn.')
    + `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr))">${CONTROL.map(([lbl, port, desc]) =>
      `<div class="card"><b style="color:var(--text)">${lbl}</b><div class="strat" style="margin:2px 0 8px">${desc}${port ? ` · cổng ${port}` : ''}</div>
        <span class="pill"><span class="dot warn"></span>Chỉ xem trên Mac</span></div>`).join('')}</div>`
    + caption('4 bot luôn chạy TIỀN ẢO và im lặng (không nhắn Telegram) — chỉ để đo chiến lược. Telegram chỉ nhận tín hiệu của alert bot để bạn tự đặt lệnh. Bot tắt bất thường tự bật lại sau tối đa 5 phút.')
    + section('🤖 Bot Freqtrade đang chạy', 'Lãi/lỗ, lệnh đang mở và lệnh đã đóng của từng bot.')
    + emptyState('🔒', 'Bot không công khai trên web', 'Mở dashboard riêng trên Mac (hoặc trên điện thoại qua Tailscale) để xem lãi/lỗ và bật/tắt bot. Trên Mac chạy:', './run.sh dashboard')
    + (S.dashUrl ? `<div style="max-width:340px;margin:16px auto 0">${linkButton(S.dashUrl, '🖥️ &nbsp;Mở dashboard trên Mac')}</div>`
                 : caption('Mẹo: dán link dashboard (Tailscale) vào ô <b>Link dashboard trên Mac</b> ở thanh bên để mở nhanh từ đây.'));
}

/* ------------------------------------------------------------------ TAB BACKTEST */
function renderBacktest(post) {
  const s = snap();
  if (!s) return loading() ? '<div class="loading">Đang tải kết quả...</div>' : emptyState('🧪', 'Chưa có kết quả', 'Trên Mac chạy backtest rồi xuất dữ liệu cho bản web:', './run.sh web-data');
  const out = [section('🧪 Kiểm chứng theo giai đoạn (walk-forward)', 'Cùng một bộ tham số chạy riêng trên <b>từng 6 tháng</b>. Chiến lược đáng tin phải ổn định qua nhiều kiểu thị trường, không chỉ đẹp ở một giai đoạn may mắn.', 'Chạy lại: <code>./run.sh validate</code>')];
  const wfs = s.walk_forward || {};
  const avail = [['filter', 'Có bộ lọc thị trường'], ['nofilter', 'Không lọc (để so sánh)']].filter(([k]) => wfs[k]);
  if (!avail.length) out.push(emptyState('🧪', 'Chưa có kết quả kiểm chứng', 'Cần ~2 năm dữ liệu rồi chạy:', './run.sh validate'));
  else {
    if (!wfs[S.wf]) S.wf = avail[0][0];
    if (avail.length > 1) out.push(segmented('wf', avail.map(([v, l]) => ({ v, l })), S.wf));
    const wf = wfs[S.wf];
    const labels = wf.windows.map(w => w.label), names = Object.keys(wf.strategies);
    const z = [...names.map(n => wf.strategies[n].map(r => r.profit_pct)), wf.windows.map(w => w.market_pct)];
    const ylab = [...names.map(n => SHORT_NAMES[n] || n), 'Mua & giữ (thị trường)'];
    out.push(chart('c-wf', 90 + 52 * ylab.length));
    post.push(['c-wf', S.wf + (wf.generated || ''), () => C.wfFigure(labels, ylab, z)]);
    out.push(`<div class="grid" style="margin-top:12px">${names.map(n => {
      const sm = wf.summary[n];
      const kind = sm.profitable >= sm.n * 0.75 ? 'long' : sm.profitable >= sm.n / 2 ? 'wait' : 'short';
      const verdict = { long: 'Ổn định', wait: 'Chưa ổn định', short: 'Không ổn định' }[kind];
      return `<div class="card"><div class="card-head"><b style="color:var(--text)">${SHORT_NAMES[n] || esc(n)}</b><span>${badge(verdict, kind)}${T('Ổn định: có lãi ở ≥ 75% số giai đoạn · Chưa ổn định: ≥ 50% · Không ổn định: < 50%.', { right: true })}</span></div>
        ${kv('Giai đoạn có lãi', `${sm.profitable} / ${sm.n}`, sm.profitable > sm.n / 2 ? 'up' : 'down', 'Số giai đoạn 6 tháng có lãi / tổng số giai đoạn. Ổn định = ≥ 75%.')}
        ${kv('Thắng thị trường', `${sm.beat_market} / ${sm.n}`, '', 'Số giai đoạn lời nhiều hơn (hoặc lỗ ít hơn) so với mua rồi giữ.')}
        ${kv('Tổng lãi/lỗ các giai đoạn', fmtPct(sm.sum_profit_pct), sm.sum_profit_pct > 0 ? 'up' : 'down', 'Cộng % lãi/lỗ của các giai đoạn (mỗi giai đoạn bắt đầu lại từ vốn ban đầu).')}
        ${kv('Sụt vốn tệ nhất', `${sm.worst_dd_pct.toFixed(1)}%`, '', TIPS.dd)}</div>`;
    }).join('')}</div>`);
    out.push(caption(`Cập nhật: ${esc((wf.generated || '').replace('T', ' '))} · Ô xanh = có lãi, ô đỏ = lỗ trong giai đoạn đó. Ổn định = có lãi ở ≥ 75% số giai đoạn.`));
  }

  out.push(section('📊 Kết quả Backtest Freqtrade', 'So sánh chiến lược trên cùng dữ liệu quá khứ.'));
  const bt = s.backtest;
  if (!bt) { out.push(emptyState('📊', 'Chưa có kết quả', 'Chạy backtest trên Mac rồi xuất dữ liệu:', './run.sh web-data')); return out.join(''); }
  out.push(caption(`File: <code>${esc(bt.file)}</code> · xuất lúc ${snapAge(s)}`));
  out.push(dataframe([
    { key: 'key', label: 'Chiến lược', help: 'Tên chiến lược Freqtrade.' }, { key: 'trades', label: 'Số lệnh', num: true, help: TIPS.trades },
    { key: 'profit_pct', label: 'Lợi nhuận %', num: true, fmt: v => `${sg(v)}%`, cls: v => v > 0 ? 'up' : 'down', help: TIPS.bt_profit },
    { key: 'profit_abs', label: 'Lợi nhuận USDT', num: true, fmt: v => sg(v), help: 'Lợi nhuận tính bằng USDT.' },
    { key: 'wins', label: 'Thắng', num: true, help: 'Số lệnh có lãi.' }, { key: 'losses', label: 'Thua', num: true, help: 'Số lệnh bị lỗ.' },
    { key: 'dd_pct', label: 'Sụt vốn tối đa', num: true, fmt: v => `${v.toFixed(2)}%`, help: TIPS.dd },
    { key: 'hold', label: 'Giữ lệnh TB', help: 'Thời gian giữ một lệnh trung bình.' }], bt.comparison || []));
  out.push(chart('c-eq', 460));
  post.push(['c-eq', bt.file, () => C.equityFigure(bt.strategies)]);
  out.push(caption(`Half-Kelly: ${TIPS.kelly} · Thị trường thay đổi trong giai đoạn: ${fmtPct(bt.market)}`));
  for (const st of bt.strategies)
    out.push(expander(`Chi tiết ${esc(st.name)} — ${st.n} lệnh · Half-Kelly = ${st.kelly.toFixed(1)}% vốn`,
      dataframe([{ key: 'key', label: 'Lý do thoát' }, { key: 'trades', label: 'Số lệnh', num: true },
                 { key: 'profit_pct', label: 'Lợi nhuận %', num: true, fmt: v => `${sg(v)}%`, cls: v => v > 0 ? 'up' : 'down' },
                 { key: 'wins', label: 'Thắng', num: true }, { key: 'losses', label: 'Thua', num: true }], st.exits)
      + caption('30 lệnh gần nhất:')
      + dataframe([{ key: 'pair', label: 'pair' }, { key: 'tag', label: 'enter_tag' }, { key: 'exit', label: 'exit_reason' },
                   { key: 'open', label: 'open_date' }, { key: 'close', label: 'close_date' },
                   { key: 'pct', label: 'profit %', num: true, fmt: v => `${sg(v)}%`, cls: v => v > 0 ? 'up' : 'down' },
                   { key: 'abs', label: 'profit_abs', num: true, fmt: v => sg(v) }], [...st.last_trades].reverse(), { maxHeight: 420 })));
  return out.join('');
}

/* ------------------------------------------------------------------ chuyển tab */
function setTab(name, { scroll = true } = {}) {
  if (!TABS.includes(name)) name = 'home';
  const prevTab = $(`[role=tab][data-tab="${current}"]`), nextTab = $(`[role=tab][data-tab="${name}"]`);
  current = name;
  document.querySelectorAll('[role=tab]').forEach(t => {
    const on = t === nextTab;
    t.setAttribute('aria-selected', on);
    if (on) t.setAttribute('data-selected', 'true'); else t.removeAttribute('data-selected');
  });
  // viên thuốc trượt từ tab cũ sang tab mới (giống react-aria của Streamlit)
  let ind = $('.react-aria-SelectionIndicator');
  if (!ind) { ind = document.createElement('span'); ind.className = 'react-aria-SelectionIndicator'; }
  const from = prevTab?.getBoundingClientRect(), to = nextTab.getBoundingClientRect();
  nextTab.prepend(ind);
  if (from && prevTab !== nextTab && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    ind.style.transition = 'none';
    ind.style.translate = `${from.left - to.left}px 0`;
    ind.style.width = `${from.width}px`;
    void ind.offsetWidth;
    ind.style.transition = '';
    ind.style.translate = '0 0';
    ind.style.width = '';
  }
  TABS.forEach(t => { $(`#p-${t}`).hidden = t !== name; });
  const hash = name === 'home' ? location.pathname + location.search : `#${name}`;
  if ((location.hash.slice(1) || 'home') !== name) history.replaceState(null, '', hash);
  nextTab.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  if (scroll && scrollY > 0) scrollTo({ top: 0 });
  render();
}

/* ------------------------------------------------------------------ sự kiện */
let toastTimer;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('on'), 2200);
}
function sideOpen(on) {
  document.body.classList.toggle('side-on', on);
  $('#sideOpen').setAttribute('aria-expanded', on);
}
function setVal(key, v) {
  if (key === 'f_days') { F.days = v; queueRender(); return; }
  S[key] = v; save();
  if (key === 'window') memoStore.clear();
  queueRender();
}
function clampNum(input) {
  const min = +input.min, max = +input.max;
  let v = parseFloat(String(input.value).replace(',', '.'));
  if (!fin(v)) v = min;
  return Math.min(max, Math.max(min, v));
}

document.addEventListener('click', e => {
  const tab = e.target.closest('[role=tab][data-tab]');
  if (tab) return setTab(tab.dataset.tab);
  const seg = e.target.closest('[data-seg]');
  if (seg) return setVal(seg.dataset.seg, seg.dataset.val);
  const del = e.target.closest('[data-ms][data-del]');
  if (del) { const k = del.dataset.ms; F[k] = F[k].filter(x => x !== del.dataset.del); return queueRender(); }
  const step = e.target.closest('.st-number [data-step]');
  if (step) {
    const inp = step.parentElement.querySelector('input');
    const v = Math.min(+inp.max, Math.max(+inp.min, clampNum(inp) + +step.dataset.step * +inp.step));
    inp.value = v;
    return setVal(inp.dataset.set, v);
  }
  const copy = e.target.closest('[data-copy]');
  if (copy) {
    navigator.clipboard?.writeText(copy.dataset.copy).then(() => toast(`Đã copy ${copy.dataset.copy}`), () => toast('Không copy được'));
    return;
  }
  const act = e.target.closest('[data-act]');
  if (!act) return;
  const a = act.dataset.act;
  if (a === 'load') {
    if (!F.pairs.length || !F.tfs.length) return toast('Chọn ít nhất 1 coin và 1 khung thời gian');
    S.pairs = ALL_PAIRS.filter(p => F.pairs.includes(p)); S.tfs = TFS.filter(t => F.tfs.includes(t)); S.days = F.days;
    save(); gen++; memoStore.clear(); plotSig.clear();
    toast('Đang tải dữ liệu mới từ Binance...');
    if (innerWidth <= 820) sideOpen(false);
    queueRender();
  } else if (a === 'apply-risk') {
    const p = A.PROFILES[S.profile];
    setVal('riskPct', p.risk_pct);
    toast(`Đã lưu: máy tính dùng rủi ro ${p.risk_pct}%/lệnh.`);
  } else if (a === 'to-signals') {
    e.preventDefault();
    document.getElementById('tin-hieu')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else if (a === 'focus-dash') {
    e.preventDefault();
    sideOpen(true);
    const inp = $('[data-set="dashUrl"]');
    inp?.scrollIntoView({ block: 'center' }); inp?.focus();
    toast('Dán link dashboard trên Mac (Tailscale) vào ô này');
  }
});
document.addEventListener('change', e => {
  const el = e.target;
  if (el.matches('select[data-ms]')) { if (el.value) F[el.dataset.ms].push(el.value); el.value = ''; return queueRender(); }
  if (!el.dataset.set) return;
  if (el.type === 'range' || el.type === 'number') return setVal(el.dataset.set, el.type === 'range' ? +el.value : clampNum(el));
  if (el.type === 'text') {
    let v = el.value.trim();
    if (v && !/^https?:\/\//i.test(v)) v = 'http://' + v;
    return setVal(el.dataset.set, v);
  }
  setVal(el.dataset.set, el.value);
});
document.addEventListener('input', e => {
  const el = e.target;
  if (el.type !== 'range') return;
  const box = el.closest('.st-slider'), p = (el.value - el.min) / (el.max - el.min);
  box.style.setProperty('--p', `${p * 100}%`); box.style.setProperty('--pn', p);
  box.querySelector('.sv').textContent = Number(el.value).toFixed(+el.dataset.dec);
});
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.matches('.st-number input, .st-text input')) e.target.blur();
  if (e.key === 'Escape') sideOpen(false);
  const tab = e.target.closest?.('[role=tab]');
  if (tab && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
    const i = TABS.indexOf(tab.dataset.tab) + (e.key === 'ArrowRight' ? 1 : -1);
    const next = TABS[(i + TABS.length) % TABS.length];
    setTab(next); $(`[role=tab][data-tab="${next}"]`).focus();
  }
});
$('#sideOpen').onclick = () => sideOpen(true);
$('#sideClose').onclick = () => sideOpen(false);
$('#sideScrim').onclick = () => sideOpen(false);
addEventListener('hashchange', () => { const h = location.hash.slice(1); const t = LEGACY[h] || h || 'home'; if (t !== current) setTab(t); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) queueRender(); });
addEventListener('online', () => queueRender());
setInterval(() => { if (!document.hidden) queueRender(); }, 60e3);

/* ------------------------------------------------------------------ khởi động */
const h = location.hash.slice(1);
setTab(LEGACY[h] || h || 'home', { scroll: false });
if (h === 'signals') setTimeout(() => document.getElementById('tin-hieu')?.scrollIntoView({ block: 'start' }), 1200);
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
