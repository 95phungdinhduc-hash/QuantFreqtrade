/* Biểu đồ Plotly — cùng phiên bản (plotly.js 4.1.1) và cùng template "quant" với dashboard (ui.setup_plotly).
   Thư viện ~1.4 MB nên chỉ tải khi mở tab có biểu đồ; service worker lưu lại cho lần sau. */
import { ADF_THRESHOLD, Z_ENTRY, signalMarkers } from './indicators.js';
import { BG, TEXT, TEXT2, MUTED, GRID, AXIS, SURFACE2, UP, DOWN, WARN, BLUE, ORANGE, AQUA, VIOLET, RED, SERIES, fmtPx } from './ui.js';

const SRC = 'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@4.1.1/plotly.min.js';
const FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif";
let loading;
export function loadPlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  return loading ||= new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = SRC; s.async = true;
    s.onload = () => ok(window.Plotly);
    s.onerror = () => { loading = null; fail(new Error('Không tải được thư viện biểu đồ')); };
    document.head.append(s);
  });
}

const axis = { gridcolor: GRID, zerolinecolor: AXIS, linecolor: AXIS, tickcolor: AXIS, showline: false, zeroline: true, zerolinewidth: 2,
               automargin: true, ticks: '',   // giống template plotly_dark của Python
               tickfont: { color: MUTED, size: 11 }, title: { font: { color: TEXT2, size: 12 }, standoff: 15 } };
const BASE = {
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: FONT, color: TEXT2, size: 12 }, colorway: SERIES,
  hoverlabel: { bgcolor: SURFACE2, bordercolor: AXIS, font: { family: FONT, color: TEXT, size: 12 } },
  legend: { orientation: 'h', yanchor: 'bottom', y: 1.01, xanchor: 'left', x: 0, bgcolor: 'rgba(0,0,0,0)', font: { color: TEXT2, size: 12 } },
  title: { font: { color: TEXT, size: 15, family: FONT }, x: 0.01 },
  margin: { l: 8, r: 8, t: 36, b: 8 }, xaxis: { ...axis }, yaxis: { ...axis }, dragmode: 'pan',
};
const CONFIG = { displaylogo: false, responsive: true, scrollZoom: false,
                 modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'] };
const merge = (a, b) => { const o = { ...a }; for (const [k, v] of Object.entries(b))
  o[k] = v && typeof v === 'object' && !Array.isArray(v) && a[k] && typeof a[k] === 'object' ? merge(a[k], v) : v; return o; };

/** Vẽ (hoặc cập nhật tại chỗ) vào div id */
export async function plot(id, data, layout) {
  const el = document.getElementById(id);
  if (!el) return;
  const P = await loadPlotly();
  const mobile = innerWidth < 640;
  const lay = merge(structuredClone(BASE), structuredClone(layout));   // bản sao mới: Plotly ghi ngược range/type vào layout
  if (mobile) lay.margin = { ...lay.margin, l: 4, r: 4 };
  el.style.minHeight = '';
  await P.react(el, data, lay, { ...CONFIG, displayModeBar: !mobile && 'hover' });
}

const dt = rows => rows.map(r => new Date(r.t));
const hrect = (y0, y1, color, opacity, yref) => ({ type: 'rect', xref: 'paper', x0: 0, x1: 1, yref, y0, y1, fillcolor: color, opacity, line: { width: 0 }, layer: 'below' });
const hline = (y, color, yref, dash = 'solid', width = 1) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, yref, y0: y, y1: y, line: { color, width, dash } });

/** Giá + dải ±2σ + EMA + điểm tín hiệu / Z-Score / ADF — giống dashboard price_figure */
export function priceFigure(rows) {
  const x = dt(rows);
  const up = rows.map(r => r.mean + 2 * r.std), lo = rows.map(r => r.mean - 2 * r.std);
  const band = 'rgba(57,135,229,0.45)';
  const [buy, sell] = signalMarkers(rows);
  const zabs = Math.max(...rows.map(r => Math.abs(r.z)).filter(Number.isFinite), 0);
  const zmax = Math.max(3.5, zabs + 0.3);
  const data = [
    { x, y: up, name: '+2σ', type: 'scatter', mode: 'lines', line: { color: band, width: 1 }, hovertemplate: '+2σ %{y:,.4f}<extra></extra>' },
    { x, y: lo, name: '−2σ', type: 'scatter', mode: 'lines', line: { color: band, width: 1 }, fill: 'tonexty', fillcolor: 'rgba(57,135,229,0.06)', hovertemplate: '−2σ %{y:,.4f}<extra></extra>' },
    { x, open: rows.map(r => r.o), high: rows.map(r => r.h), low: rows.map(r => r.l), close: rows.map(r => r.c), name: 'Giá', type: 'candlestick',
      increasing: { line: { color: UP, width: 1 }, fillcolor: UP }, decreasing: { line: { color: DOWN, width: 1 }, fillcolor: DOWN } },
    { x, y: rows.map(r => r.mean), name: 'Trung bình', type: 'scatter', mode: 'lines', line: { color: TEXT2, width: 1, dash: 'dash' }, hovertemplate: 'TB %{y:,.4f}<extra></extra>' },
    { x, y: rows.map(r => r.emaFast), name: 'EMA20', type: 'scatter', mode: 'lines', line: { color: BLUE, width: 2 }, hovertemplate: 'EMA20 %{y:,.4f}<extra></extra>' },
    { x, y: rows.map(r => r.emaSlow), name: 'EMA50', type: 'scatter', mode: 'lines', line: { color: ORANGE, width: 2 }, hovertemplate: 'EMA50 %{y:,.4f}<extra></extra>' },
    { x: buy.map(i => x[i]), y: buy.map(i => rows[i].l * 0.996), name: 'Tín hiệu Long', type: 'scatter', mode: 'markers',
      marker: { symbol: 'triangle-up', size: 12, color: UP, line: { color: BG, width: 2 } }, hovertemplate: '▲ Long %{x|%d/%m %H:%M}<extra></extra>' },
    { x: sell.map(i => x[i]), y: sell.map(i => rows[i].h * 1.004), name: 'Tín hiệu Short', type: 'scatter', mode: 'markers',
      marker: { symbol: 'triangle-down', size: 12, color: DOWN, line: { color: BG, width: 2 } }, hovertemplate: '▼ Short %{x|%d/%m %H:%M}<extra></extra>' },
    { x, y: rows.map(r => r.z), name: 'Z-Score', type: 'scatter', mode: 'lines', line: { color: VIOLET, width: 2 }, xaxis: 'x2', yaxis: 'y2', showlegend: false, hovertemplate: 'Z %{y:.2f}σ<extra></extra>' },
    { x, y: rows.map(r => r.adf), name: 'ADF p', type: 'scatter', mode: 'lines', line: { color: AQUA, width: 2 }, xaxis: 'x3', yaxis: 'y3', showlegend: false, hovertemplate: 'ADF p %{y:.3f}<extra></extra>' },
  ];
  const spikes = { showspikes: true, spikemode: 'across', spikethickness: 1, spikedash: 'dot', spikecolor: MUTED };
  const h = innerWidth < 640 ? 640 : 820;
  const layout = {
    height: h, hovermode: 'x unified', margin: { l: 8, r: 8, t: 40, b: 8 },
    xaxis: { ...axis, ...spikes, domain: [0, 1], anchor: 'y', matches: 'x3', showticklabels: false, rangeslider: { visible: false } },
    xaxis2: { ...axis, ...spikes, domain: [0, 1], anchor: 'y2', matches: 'x3', showticklabels: false },
    xaxis3: { ...axis, ...spikes, domain: [0, 1], anchor: 'y3' },
    yaxis: { ...axis, domain: [0.405, 1], side: 'right', title: { text: 'Giá', font: { color: TEXT2, size: 12 } } },
    yaxis2: { ...axis, domain: [0.19, 0.38], side: 'right', range: [-zmax, zmax], title: { text: 'Z-Score', font: { color: TEXT2, size: 12 } } },
    yaxis3: { ...axis, domain: [0, 0.165], side: 'right', range: [0, 1], title: { text: 'ADF p', font: { color: TEXT2, size: 12 } } },
    shapes: [hrect(Z_ENTRY, zmax, DOWN, 0.08, 'y2'), hrect(-zmax, -Z_ENTRY, UP, 0.08, 'y2'), hline(0, AXIS, 'y2'),
             hrect(0, ADF_THRESHOLD, BLUE, 0.08, 'y3'), hline(ADF_THRESHOLD, WARN, 'y3', 'dot')],
  };
  return [data, layout];
}

/** Kịch bản lệnh trên 120 nến gần nhất — giống plan_figure */
export function planFigure(rows, plan, isLong) {
  const tail = rows.slice(-120);
  const tl = tail.at(-1).t, step = tl - tail.at(-2).t;
  const x0 = new Date(tail[0].t), x1 = new Date(tl + step * 14), xl = new Date(tl);
  const lines = [[plan.takeProfit, UP, 'Chốt lời'], [plan.entry, TEXT, 'Vào lệnh'], [plan.stopLoss, DOWN, 'Cắt lỗ']];
  return [[{ x: dt(tail), y: tail.map(r => r.c), name: 'Giá', type: 'scatter', mode: 'lines', line: { color: BLUE, width: 2 },
             hovertemplate: '%{x|%d/%m %H:%M} · %{y:,.4f}<extra></extra>' }], {
    height: 380, showlegend: false, xaxis: { range: [x0, x1] },
    title: { text: `Kịch bản ${isLong ? 'Long' : 'Short'} trên 120 nến gần nhất` },
    shapes: [
      { type: 'rect', xref: 'x', yref: 'y', x0: xl, x1, y0: plan.entry, y1: plan.takeProfit, fillcolor: UP, opacity: 0.14, line: { width: 0 } },
      { type: 'rect', xref: 'x', yref: 'y', x0: xl, x1, y0: plan.entry, y1: plan.stopLoss, fillcolor: DOWN, opacity: 0.14, line: { width: 0 } },
      ...lines.map(([y, c, n]) => ({ type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: y, y1: y, line: { color: c, width: 1.5, dash: n === 'Vào lệnh' ? 'dot' : 'solid' } })),
    ],
    annotations: lines.map(([y, c, n]) => ({ xref: 'paper', x: 0, yref: 'y', y, text: `${n}  ${fmtPx(y)}`, showarrow: false,
                                              xanchor: 'left', yanchor: 'bottom', font: { color: c, size: 12 } })),
  }];
}

/** Ma trận tương quan — giống tab Screener */
export function corrFigure(names, m) {
  return [[{ type: 'heatmap', z: m, x: names, y: names, zmin: -1, zmax: 1, xgap: 3, ygap: 3,
             text: m.map(r => r.map(v => Number.isFinite(v) ? v.toFixed(2) : '')), texttemplate: '%{text}',
             textfont: { color: TEXT, size: 13 }, colorscale: [[0, BLUE], [0.5, '#2a2f3a'], [1, RED]],
             hovertemplate: '%{y} × %{x}: %{z:.2f}<extra></extra>', colorbar: { thickness: 10, tickfont: { color: MUTED } } }],
          { height: 420, yaxis: { autorange: 'reversed' } }];
}

/** Phân bổ vốn — thanh ngang */
export function allocFigure(alloc) {
  const colors = alloc.map((_, i) => i === alloc.length - 1 ? MUTED : SERIES[i % SERIES.length]);
  return [[{ type: 'bar', orientation: 'h', x: alloc.map(a => a.weight * 100), y: alloc.map(a => a.asset), marker: { color: colors },
             text: alloc.map(a => `${(a.weight * 100).toFixed(0)}% · $${Math.round(a.usdt).toLocaleString('en-US')}`),
             textposition: 'outside', textfont: { color: TEXT }, cliponaxis: false, hovertemplate: '%{y}: %{x:.1f}%<extra></extra>' }],
          { height: 80 + 52 * alloc.length, showlegend: false, bargap: 0.35, margin: { l: 8, r: 40, t: 10, b: 8 },
            xaxis: { range: [0, 140], ticksuffix: '%', showgrid: true, tickvals: [0, 25, 50, 75, 100] },
            yaxis: { autorange: 'reversed', automargin: true } }];
}

/** Walk-forward: lãi/lỗ từng giai đoạn — heatmap đỏ/xanh */
export function wfFigure(labels, ylab, z) {
  const lim = Math.max(5, ...z.flat().map(Math.abs));
  return [[{ type: 'heatmap', z, x: labels, y: ylab, zmin: -lim, zmax: lim, xgap: 4, ygap: 4,
             colorscale: [[0, DOWN], [0.5, '#2a2f3a'], [1, UP]], showscale: false,
             text: z.map(r => r.map(v => (v >= 0 ? '+' : '') + v.toFixed(1) + '%')), texttemplate: '%{text}',
             textfont: { color: TEXT, size: 14 }, hovertemplate: '%{y} · %{x}: %{text}<extra></extra>' }],
          { height: 90 + 52 * ylab.length, yaxis: { autorange: 'reversed', automargin: true }, xaxis: { side: 'top' },
            margin: { l: 8, r: 8, t: 30, b: 8 } }];
}

/** Đường cong vốn backtest */
export function equityFigure(strategies) {
  const data = strategies.map((s, i) => ({
    type: 'scatter', mode: 'lines', name: s.name, x: s.equity.map(p => new Date(p[0])), y: s.equity.map(p => p[1]),
    line: { color: SERIES[i % SERIES.length], width: 2, shape: 'hv' },
    hovertemplate: `${s.name}<br>%{x|%d/%m/%Y} · %{y:,.2f} USDT<extra></extra>` }));
  const sb = strategies[0]?.start_balance;
  return [data, {
    title: { text: 'Đường cong vốn (USDT)' }, height: 460, hovermode: 'x unified',
    shapes: sb ? [hline(sb, AXIS, 'y', 'dot')] : [],
    annotations: [
      ...(sb ? [{ xref: 'paper', x: 1, yref: 'y', y: sb, text: 'Vốn ban đầu', showarrow: false, xanchor: 'right', yanchor: 'bottom', font: { color: MUTED, size: 11 } }] : []),
      ...strategies.map(s => { const p = s.equity.at(-1); return { x: new Date(p[0]), y: p[1], text: Math.round(p[1]).toLocaleString('en-US'),
        showarrow: false, xanchor: 'left', xshift: 6, font: { color: TEXT, size: 12 } }; }),
    ],
  }];
}
