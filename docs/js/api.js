/* Lấy dữ liệu công khai từ Binance + chỉ số Sợ hãi/Tham lam. Không cần khoá API, không gửi dữ liệu cá nhân. */

const SPOT = 'https://data-api.binance.vision/api/v3';   // bản công khai chỉ đọc của Binance Spot
const INTERVAL_MS = { "15m": 9e5, "1h": 36e5, "4h": 144e5, "1d": 864e5 };
const FUT = 'https://fapi.binance.com/fapi/v1';

const sym = pair => pair.replace('/', '');

async function getJSON(url, timeout = 12000) {
  const ctl = new AbortController();
  const id = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctl.signal, cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(id);
  }
}

const toCandles = raw => raw.map(k => ({ t: k[0], o: +k[1], h: +k[2], l: +k[3], c: +k[4], v: +k[5] }));

/** Nến Futures USDT-M (giống alert bot: nến cuối là nến đang chạy) */
export const futuresKlines = (pair, interval = '1h', limit = 300) =>
  getJSON(`${FUT}/klines?symbol=${sym(pair)}&interval=${interval}&limit=${limit}`).then(toCandles);

export const spotKlines = (pair, interval = '1d', limit = 260) =>
  getJSON(`${SPOT}/klines?symbol=${sym(pair)}&interval=${interval}&limit=${limit}`).then(toCandles);

/** Giá + % 24h trên Spot */
export async function tickers(pairs) {
  const q = encodeURIComponent(JSON.stringify(pairs.map(sym)));
  const raw = await getJSON(`${SPOT}/ticker/24hr?symbols=${q}`);
  const out = {};
  for (const t of raw) {
    const p = pairs.find(x => sym(x) === t.symbol);
    if (p) out[p] = { last: +t.lastPrice, pct: +t.priceChangePercent, high: +t.highPrice, low: +t.lowPrice, qvol: +t.quoteVolume };
  }
  return out;
}

export async function fearGreed() {
  const d = await getJSON('https://api.alternative.me/fng/?limit=8');
  return d.data.map(x => ({ value: +x.value, label: x.value_classification, t: +x.timestamp * 1000 }));
}

/** Giá trị lệnh tối thiểu Futures (file của sàn ~1MB -> lưu lại 1 ngày) */
export async function minNotionals() {
  const KEY = 'qf.minNotional';
  try {
    const c = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (c && Date.now() - c.t < 864e5) return c.v;
  } catch { /* bỏ qua */ }
  const d = await getJSON(`${FUT}/exchangeInfo`, 20000);
  const v = {};
  for (const s of d.symbols) {
    if (!s.symbol.endsWith('USDT')) continue;
    const f = s.filters.find(x => x.filterType === 'MIN_NOTIONAL');
    if (f) v[s.symbol] = +(f.notional ?? f.minNotional);
  }
  try { localStorage.setItem(KEY, JSON.stringify({ t: Date.now(), v })); } catch { /* đầy bộ nhớ */ }
  return v;
}
export const minNotionalOf = (table, pair) => table?.[sym(pair)];

/** Nến Spot ĐÃ ĐÓNG, lấy nhiều trang (Binance trả tối đa 1000 nến/lần). total: số nến muốn có */
export async function spotHistory(pair, interval, total) {
  const step = INTERVAL_MS[interval] || 36e5;
  let out = [], end = Date.now();
  while (out.length < total + 1) {
    const need = Math.min(1000, total + 1 - out.length);
    const raw = await getJSON(`${SPOT}/klines?symbol=${sym(pair)}&interval=${interval}&limit=${need}&endTime=${end}`);
    const c = toCandles(raw);
    if (!c.length) break;
    out = c.concat(out);
    if (c.length < need) break;
    end = c[0].t - 1;
  }
  const now = Date.now();
  return out.filter(k => k.t + step <= now).slice(-total);   // bỏ nến đang chạy
}

/** Dữ liệu do máy Mac xuất (tin tức, backtest, walk-forward) — docs/data/snapshot.json */
export async function snapshot() {
  const r = await fetch('data/snapshot.json', { cache: 'no-cache' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* ------------------------------------------------------------------ tin tức (giống quant_core/market_context.py) */
// CoinDesk/CoinTelegraph không cho trình duyệt đọc RSS trực tiếp (CORS) -> đọc qua rss2json.com (chỉ gửi địa chỉ RSS công khai)
const FEEDS = { CoinDesk: 'https://www.coindesk.com/arc/outboundfeeds/rss/', CoinTelegraph: 'https://cointelegraph.com/rss' };
const BULLISH = ['surge', 'jump', 'bull', 'high', 'gain', 'approve', 'etf', 'buy', 'rally', 'soar', 'upgrade', 'adoption', 'record'];
const BEARISH = ['drop', 'crash', 'bear', 'low', 'hack', 'ban', 'sec', 'lawsuit', 'fall', 'plunge', 'dump', 'fear', 'inflation', 'cpi'];
// khớp TỪ NGUYÊN VẸN (+ đuôi s/es/d/ed/ing): "security" không bị đếm là "sec", "below" không là "low"
const wordRe = words => new RegExp(`\\b(?:${[...words].sort((a, b) => b.length - a.length).join('|')})(?:s|es|d|ed|ing)?\\b`, 'g');
const BULL_RE = wordRe(BULLISH), BEAR_RE = wordRe(BEARISH);

/** >0 tích cực, <0 tiêu cực (số từ khoá tăng − số từ khoá giảm) — giống market_context.score_text */
export function scoreText(text) {
  const t = text.toLowerCase();
  return (t.match(BULL_RE) || []).length - (t.match(BEAR_RE) || []).length;
}
/** Tổng điểm thị trường = số tin tốt − số tin xấu — giống news_sentiment_score */
export const newsSentiment = items => items.reduce((s, i) => s + Math.sign(i.score), 0);

/** 8 tin mới nhất mỗi nguồn, đã chấm điểm (tiêu đề + 200 ký tự tóm tắt, giống bot) */
export async function liveNews(perFeed = 8) {
  const res = await Promise.allSettled(Object.entries(FEEDS).map(async ([source, url]) => {
    const d = await getJSON(`https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(url)}`, 15000);
    if (d.status !== 'ok') throw new Error(d.message || 'rss2json lỗi');
    return d.items.slice(0, perFeed).map(e => ({
      source, title: e.title, link: e.link,
      published: e.pubDate ? new Date(e.pubDate.replace(' ', 'T') + 'Z').toISOString() : '',
      score: scoreText(`${e.title} ${(e.description || '').slice(0, 200)}`),
    }));
  }));
  const items = res.flatMap(r => r.status === 'fulfilled' ? r.value : []);
  if (!items.length) throw new Error('Không lấy được tin');
  return items;
}
