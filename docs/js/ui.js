/* Khối giao diện dùng chung — bản JavaScript của dashboard/ui.py.
   Sinh ĐÚNG cấu trúc HTML + class mà dashboard Streamlit tạo ra (card, sec, kv, badge, stMetric…)
   để dùng lại nguyên theme.css + fx.js của dashboard -> web và dashboard trông giống hệt nhau. */

export const UP = '#1fbf75', DOWN = '#ef5d5d', WARN = '#fab219', TEXT = '#e8eaf0', TEXT2 = '#a3abbd', MUTED = '#6b7385';
export const BG = '#0b0e14', SURFACE2 = '#1a2130', GRID = 'rgba(255,255,255,0.06)', AXIS = 'rgba(255,255,255,0.16)';
export const BLUE = '#3987e5', ORANGE = '#d95926', AQUA = '#199e70', YELLOW = '#c98500';
export const MAGENTA = '#d55181', GREEN = '#0ca30c', VIOLET = '#9085e9', RED = '#e66767';
export const SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED];
export const COIN_COLORS = { BTC: '#f7931a', ETH: '#8c9eff', SOL: '#14f195', BNB: '#f3ba2f', XRP: '#9aa4b2', ADA: '#4b7bec', DOGE: '#c2a633' };

const fin = Number.isFinite;
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const num = (v, d = 2) => fin(v) ? v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';
export const fmtPx = v => fin(v) ? '$' + num(v, Math.abs(v) >= 10 ? 2 : Math.abs(v) >= 1 ? 3 : 5) : '—';
export const fmtUsd = (v, d = 2) => fin(v) ? (v < 0 ? '-$' : '$') + num(Math.abs(v), d) : '—';
export const fmtPct = (v, d = 2, sign = true) => fin(v) ? (sign && v >= 0 ? '+' : '') + v.toFixed(d) + '%' : '—';
export const sg = (v, d = 2) => fin(v) ? (v >= 0 ? '+' : '') + v.toFixed(d) : '—';
export const trendCls = v => !fin(v) || Math.abs(v) < 1e-9 ? 'flat' : v > 0 ? 'up' : 'down';
export const base = p => p.split('/')[0];
export const coinIcon = p => `<span class="coin" style="background:${COIN_COLORS[base(p)] || '#6da7ec'}">${esc(base(p).slice(0, 3))}</span>`;
const pad = n => String(n).padStart(2, '0');
/** Giờ UTC dạng "HH:MM dd/mm" (giống dashboard, nến ghi giờ UTC) */
export const utc = (t, year = false) => { const d = new Date(t);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} ${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}${year ? '/' + d.getUTCFullYear() : ''}`; };
/** Giờ Việt Nam */
export const vnTime = (t, sec = false) => new Date(t).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', ...(sec ? { second: '2-digit' } : {}), hour12: false, timeZone: 'Asia/Ho_Chi_Minh' });
export const vnDate = t => new Date(t).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' });

let gid = 0;
export function sparkline(values, color, w = 240, h = 46) {
  const v = values.filter(fin);
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), rng = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${((h - 3) - (x - lo) / rng * (h - 6)).toFixed(1)}`).join(' ');
  const id = `sp${gid++}`;
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%" height="${h}" aria-hidden="true" style="filter:drop-shadow(0 4px 10px ${color}55)"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="0.32"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><polygon points="0,${h} ${pts} ${w},${h}" fill="url(#${id})"/><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}

export const section = (title, sub = '', aside = '', anchor = '') =>
  `<div class="sec"${anchor ? ` id="${esc(anchor)}"` : ''}><div><h3>${title}</h3>${sub ? `<p>${sub}</p>` : ''}</div>${aside ? `<span class="aside">${aside}</span>` : ''}</div>`;
export const badge = (text, kind = 'wait') => `<span class="badge ${kind}">${esc(text)}</span>`;
export const tip = (text, { down = false, right = false } = {}) =>
  `<span class="tip${down ? ' down' : ''}${right ? ' right' : ''}" tabindex="0" data-tip="${esc(text)}">?</span>`;
export const kv = (label, value, cls = '', help = '') =>
  `<div class="kv"><span>${esc(label)}${help ? tip(help) : ''}</span><span class="${cls}">${value}</span></div>`;
export function meter(frac, left, right) {
  const pct = Math.max(0, Math.min(1, fin(frac) ? frac : 0)) * 100;
  return `<div class="meter"><div class="bar"><i style="width:${pct.toFixed(0)}%"></i></div><div class="lbl"><span>${esc(left)}</span><span>${esc(right)}</span></div></div>`;
}
export function dbar(value, vmax) {
  const v = fin(value) ? value : 0, w = Math.min(Math.abs(v) / vmax, 1) * 50;
  return `<div class="dbar"><i class="${v >= 0 ? 'pos' : 'neg'}" style="width:${w.toFixed(1)}%"></i></div>`;
}
export const emptyState = (icon, title, body, command = '') =>
  `<div class="empty"><div class="ico">${icon}</div><b>${title}</b><p>${body}</p>${command ? `<span class="cmd">${esc(command)}</span>` : ''}</div>`;

/* ------------------------------------------------------------------ widget kiểu Streamlit */
const label = (text, help, opts = {}) => text
  ? `<div data-testid="stWidgetLabel"><p>${text}</p>${help ? tip(help, { down: true, right: !opts.left }) : ''}</div>` : '';

/** st.metric: nhãn, giá trị, phần chênh (deltaColor 'off' = xám, 'normal' = xanh/đỏ theo dấu) */
export function metric(lbl, value, delta = '', { help = '', deltaColor = 'off', up = null } = {}) {
  const cls = deltaColor === 'off' ? 'off' : up === null ? (String(delta).trim().startsWith('-') ? 'down' : 'up') : up ? 'up' : 'down';
  return `<div data-testid="stMetric"><div data-testid="stMetricLabel"><p>${esc(lbl)}</p>${help ? tip(help, { down: true }) : ''}</div>`
    + `<div data-testid="stMetricValue"><div>${esc(value)}</div></div>`
    + (delta !== '' && delta != null ? `<div data-testid="stMetricDelta" class="${cls}">${esc(delta)}</div>` : '') + '</div>';
}
export const caption = html => `<div data-testid="stCaptionContainer">${html}</div>`;
export const alert = (kind, html, icon = '') =>
  `<div data-testid="stAlert" class="${kind}">${icon ? `<span class="ai">${icon}</span>` : ''}<div>${html}</div></div>`;
export const cols = (fracs, parts, { gap = 'medium', align = 'start', cls = '' } = {}) =>
  `<div class="st-cols ${gap} a-${align} ${cls}" style="grid-template-columns:${fracs.map(f => `minmax(0,${f}fr)`).join(' ')}">${parts.map(p => `<div class="st-col">${p}</div>`).join('')}</div>`;
export const button = (act, text, { primary = false, stretch = true, disabled = false, val = '' } = {}) =>
  `<div class="stButton${stretch ? ' stretch' : ''}"><button data-act="${act}"${val !== '' ? ` data-val="${esc(val)}"` : ''} kind="${primary ? 'primary' : 'secondary'}"${disabled ? ' disabled' : ''}>${text}</button></div>`;
export const linkButton = (href, text, { stretch = true } = {}) =>
  `<div class="stLinkButton${stretch ? ' stretch' : ''}"><a href="${esc(href)}" target="_blank" rel="noopener">${text}</a></div>`;
export const chart = (id, h = 400) => `<div data-testid="stPlotlyChart" data-keep id="${id}" style="min-height:${h}px"></div>`;
export const expander = (title, html, open = false) =>
  `<div data-testid="stExpander"><details${open ? ' open' : ''}><summary>${title}</summary><div class="exp-body">${html}</div></details></div>`;

export function selectbox(key, options, value, lbl, help = '') {
  return `<div class="st-w">${label(lbl, help)}<div class="st-select"><select data-set="${key}">${options.map(o =>
    `<option value="${esc(o.v)}"${o.v === value ? ' selected' : ''}>${esc(o.l)}</option>`).join('')}</select></div></div>`;
}
export function slider(key, min, max, step, value, lbl, help = '', dec = null) {
  const d = dec ?? (String(step).split('.')[1]?.length || 0);
  const p = (value - min) / (max - min) * 100;
  return `<div class="st-w">${label(lbl, help)}<div class="st-slider" style="--p:${p}%;--pn:${p / 100}"><span class="sv">${Number(value).toFixed(d)}</span>`
    + `<input type="range" role="slider" data-set="${key}" data-dec="${d}" min="${min}" max="${max}" step="${step}" value="${value}">`
    + `<div class="ends"><span>${Number(min).toFixed(d)}</span><span>${Number(max).toFixed(d)}</span></div></div></div>`;
}
export function numberInput(key, min, max, step, value, lbl, help = '', dec = 0) {
  return `<div class="st-w">${label(lbl, help)}<div class="st-number"><input type="number" inputmode="decimal" data-set="${key}" min="${min}" max="${max}" step="${step}" value="${Number(value).toFixed(dec)}">`
    + `<button type="button" data-step="-1" aria-label="Giảm">−</button><button type="button" data-step="1" aria-label="Tăng">+</button></div></div>`;
}
export function textInput(key, value, lbl, help = '', placeholder = '') {
  return `<div class="st-w">${label(lbl, help)}<div class="st-text"><input type="text" data-set="${key}" value="${esc(value)}" placeholder="${esc(placeholder)}" autocomplete="off" spellcheck="false"></div></div>`;
}
export function multiselect(key, options, values, lbl, help = '') {
  const rest = options.filter(o => !values.includes(o));
  return `<div class="st-w">${label(lbl, help)}<div class="st-multi">${values.map(v =>
    `<span data-baseweb="tag">${esc(v)}<button type="button" data-ms="${key}" data-del="${esc(v)}" aria-label="Bỏ ${esc(v)}">×</button></span>`).join('')}`
    + `<select data-ms="${key}" aria-label="Thêm"><option value="">${rest.length ? '' : '—'}</option>${rest.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('')}</select></div></div>`;
}
export function segmented(key, options, value, lbl = '', help = '') {
  return `<div class="st-w">${label(lbl, help)}<div class="st-seg" role="radiogroup">${options.map(o =>
    `<button type="button" role="radio" data-seg="${key}" data-val="${esc(o.v)}" aria-checked="${o.v === value}">${esc(o.l)}</button>`).join('')}</div></div>`;
}

/** st.dataframe: cột {key, label, help, fmt(v,row) -> text, cls(v,row), num, spark, progress, width} */
export function dataframe(columns, rows, { maxHeight = 0 } = {}) {
  const head = columns.map(c => `<th class="${c.num ? 'n' : ''}"${c.width ? ` style="min-width:${c.width}px"` : ''}>${esc(c.label)}${c.help ? tip(c.help, { down: true, right: c.num }) : ''}</th>`).join('');
  const body = rows.map(r => `<tr>${columns.map(c => {
    const v = r[c.key];
    if (c.spark) return `<td class="sp">${sparkline(v || [], (v?.at(-1) ?? 0) >= (v?.[0] ?? 0) ? UP : DOWN, 120, 26)}</td>`;
    if (c.progress) return `<td class="pg"><span class="pbar"><i style="width:${Math.max(0, Math.min(1, v)) * 100}%"></i></span><span>${c.fmt ? c.fmt(v, r) : v}</span></td>`;
    const text = v == null || (typeof v === 'number' && !fin(v)) ? '<span class="na">None</span>' : esc(c.fmt ? c.fmt(v, r) : v);
    const cl = c.cls ? c.cls(v, r) : '';
    return `<td class="${c.num ? 'n' : ''} ${cl}">${text}</td>`;
  }).join('')}</tr>`).join('');
  return `<div data-testid="stDataFrame"${maxHeight ? ` style="max-height:${maxHeight}px"` : ''}><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
