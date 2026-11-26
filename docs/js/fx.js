/* Hiệu ứng: đèn soi theo ngón tay/chuột, gợn sóng khi chạm, số đếm lên, nháy xanh/đỏ khi giá đổi,
   mạng hạt nền (chỉ máy tính). Tắt hết khi người dùng bật "Giảm chuyển động". */
export const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const fine = matchMedia('(pointer: fine)').matches;

export function initFx() {
  // đèn soi + viền sáng theo vị trí con trỏ
  let hover = null, px = 0, py = 0, queued = false;
  const frame = () => {
    queued = false;
    if (!hover) return;
    const r = hover.getBoundingClientRect();
    hover.style.setProperty('--mx', `${px - r.left}px`);
    hover.style.setProperty('--my', `${py - r.top}px`);
  };
  document.addEventListener('pointermove', e => {
    px = e.clientX; py = e.clientY;
    hover = e.target.closest?.('.card') || null;
    if (!queued) { queued = true; requestAnimationFrame(frame); }
  }, { passive: true });

  // gợn sóng khi bấm
  document.addEventListener('pointerdown', e => {
    const b = e.target.closest?.('.btn, .icon-btn, .chip');
    if (!b || reduce) return;
    const r = b.getBoundingClientRect();
    b.style.setProperty('--rx', `${e.clientX - r.left}px`);
    b.style.setProperty('--ry', `${e.clientY - r.top}px`);
    b.removeAttribute('data-rip'); void b.offsetWidth; b.setAttribute('data-rip', '');
  }, { passive: true });

  if (!reduce && fine && innerWidth >= 900) particles(() => [px, py]);
}

/* ------------------------------------------------------------------ số */
const NUM = /([+\-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?/;
function parse(s) {
  if (/\d[\/:]\d/.test(s)) return null;
  const m = s.match(NUM);
  if (!m) return null;
  const neg = m[1] === '-' || m[1] === '−';
  return { v: parseFloat(m[2].replace(/,/g, '') + (m[3] || '')) * (neg ? -1 : 1), m,
           dec: m[3] ? m[3].length - 1 : 0, comma: m[2].includes(','), plus: m[1] === '+', minus: m[1] || '-' };
}
function fmt(x, p) {
  let s = Math.abs(x).toFixed(p.dec);
  if (p.comma) { const [i, f] = s.split('.'); s = i.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (f ? '.' + f : ''); }
  const zero = Number(s.replace(/,/g, '')) === 0;
  return (x < 0 && !zero ? (p.minus === '−' ? '−' : '-') : p.plus && x >= 0 ? '+' : '') + s;
}
function textNode(el) {
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) if (/\d/.test(n.nodeValue)) return n;
  return null;
}
function tween(el, from, dur) {
  const node = textNode(el);
  if (!node) return;
  const text = node.nodeValue, p = parse(text);
  if (!p || from === p.v) return;
  const pre = text.slice(0, p.m.index), post = text.slice(p.m.index + p.m[0].length), t0 = performance.now();
  const step = now => {
    if (!node.isConnected) return;
    const k = Math.min(1, (now - t0) / dur), e = k >= 1 ? 1 : 1 - Math.pow(2, -10 * k);
    node.nodeValue = e >= 1 ? text : pre + fmt(from + (p.v - from) * e, p) + post;
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/** Số có data-count: đếm lên từ 0 */
export function countUp(root) {
  if (reduce) return;
  root.querySelectorAll('[data-count]').forEach(el => tween(el, 0, 1300));
}

/** Trước khi vẽ lại: nhớ giá trị các ô có data-key */
export function snapshot(root) {
  const m = new Map();
  root.querySelectorAll('[data-key]').forEach(el => { const p = parse(el.textContent); if (p) m.set(el.dataset.key, p.v); });
  return m;
}
/** Sau khi vẽ lại: ô nào đổi giá trị -> nháy xanh/đỏ + chạy số từ giá cũ */
export function flashChanges(root, before) {
  root.querySelectorAll('[data-key]').forEach(el => {
    const old = before.get(el.dataset.key), p = parse(el.textContent);
    if (old == null || !p || old === p.v) return;
    el.setAttribute('data-flash', p.v > old ? 'up' : 'down');
    if (!reduce) tween(el, old, 800);
  });
}

/* ------------------------------------------------------------------ mạng hạt nền (máy tính) */
function particles(pointer) {
  const cv = document.createElement('canvas');
  cv.id = 'qfx-net';
  document.body.prepend(cv);
  const ctx = cv.getContext('2d');
  const COLORS = ['57,135,229', '144,133,233', '45,212,191', '124,179,240'];
  let W, H, pts = [];
  const resize = () => {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = innerWidth; H = innerHeight; cv.width = W * dpr; cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.round(Math.min(80, Math.max(30, W * H / 18000)));
    pts = Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .3,
      vy: (Math.random() - .5) * .3, r: .6 + Math.random() * 1.5, c: COLORS[(Math.random() * 4) | 0], ph: Math.random() * 6.3 }));
  };
  resize(); addEventListener('resize', resize);
  const LINK = 130, MOUSE = 180;
  const tick = t => {
    requestAnimationFrame(tick);
    if (document.hidden) return;
    const [mx, my] = pointer();
    ctx.clearRect(0, 0, W, H);
    for (const p of pts) {
      const dx = mx - p.x, dy = my - p.y, d = Math.hypot(dx, dy);
      if (d < MOUSE && d > 1) { p.vx += dx / d * .004; p.vy += dy / d * .004; }
      p.vx *= .995; p.vy *= .995;
      if (Math.hypot(p.vx, p.vy) < .08) { p.vx += (Math.random() - .5) * .04; p.vy += (Math.random() - .5) * .04; }
      p.x = (p.x + p.vx + W + 40) % (W + 40) - 20; p.y = (p.y + p.vy + H + 40) % (H + 40) - 20;
    }
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      for (let j = i + 1; j < pts.length; j++) {
        const b = pts[j], dd = (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
        if (dd < LINK * LINK) { ctx.strokeStyle = `rgba(${a.c},${(1 - Math.sqrt(dd) / LINK) * .22})`; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      }
      const dm = Math.hypot(mx - a.x, my - a.y);
      if (dm < MOUSE) { ctx.strokeStyle = `rgba(124,179,240,${(1 - dm / MOUSE) * .5})`; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mx, my); ctx.stroke(); }
    }
    for (const p of pts) {
      const tw = .55 + .45 * Math.sin(t / 900 + p.ph);
      ctx.fillStyle = `rgba(${p.c},${.35 + .5 * tw})`; ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (.8 + .4 * tw), 0, 6.283); ctx.fill();
    }
  };
  requestAnimationFrame(tick);
}
