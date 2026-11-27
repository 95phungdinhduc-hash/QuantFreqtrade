/* Lil_Duck Quant — hiệu ứng chuyển động cho dashboard (chạy trong trang chính, ui.inject_fx nạp 1 lần).
   - Mạng hạt nền + quầng sáng đi theo chuột
   - Đèn soi + nghiêng 3D theo chuột trên thẻ; nút "hút" theo chuột; gợn sóng khi bấm
   - Hiện dần khi cuộn tới (IntersectionObserver), số đếm lên, giá nháy xanh/đỏ khi đổi
   - Tiêu đề mục "giải mã" chữ khi xuất hiện
   Chỉ thêm thuộc tính data-* / biến CSS, không đổi nội dung React quản lý -> không làm hỏng Streamlit. */
(() => {
  if (window.__qfx) return;
  window.__qfx = true;
  const d = document, root = d.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = matchMedia('(pointer: fine)').matches;

  try {
    /* ------------------------------------------------------------ hiện dần khi cuộn tới */
    const REVEAL = '.grid > *, .steps > *, .lib > *, .mood > *, .hero-stats > *, [data-testid="stMetric"], ' +
      '[data-testid="stPlotlyChart"], .empty, .disclaimer, .tape, .ai-box, .sec';
    const COUNT = '.hstat .v, .px, .big, .score, [data-testid="stMetricValue"], .cmp .n';
    const SCRAMBLE = '.sec h3';

    const io = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        const el = e.target;
        io.unobserve(el);
        el.setAttribute('data-qin', '');
        if (!reduce) {
          el.querySelectorAll?.(SCRAMBLE).forEach(scramble);
          if (el.matches(COUNT)) countIn(el);
          el.querySelectorAll?.(COUNT).forEach(countIn);
        }
      }
    }, { rootMargin: '0px 0px -4% 0px', threshold: 0.01 });

    const counted = new WeakSet();
    function scan(node) {
      if (node.nodeType !== 1) return;
      const list = node.matches(REVEAL) ? [node] : [];
      node.querySelectorAll(REVEAL).forEach(e => list.push(e));
      for (const el of list) if (!el.hasAttribute('data-qin')) io.observe(el);
      // số nằm ngoài khối "hiện dần" (vd. hero) -> đếm ngay khi thấy
      const nums = node.matches(COUNT) ? [node] : [...node.querySelectorAll(COUNT)];
      for (const el of nums) if (!el.closest(REVEAL)) cio.observe(el);
    }
    const cio = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { cio.unobserve(e.target); if (!reduce) countIn(e.target); }
    }), { threshold: 0.2 });

    /* ------------------------------------------------------------ số đếm lên + nháy khi đổi */
    const NUM = /([+\-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?/;
    const SKIP = /\d[\/:]\d|\d{4}-\d\d/;          // ngày giờ -> không đếm
    const mine = new WeakMap();                    // text node -> chuỗi do mình viết
    const value = new WeakMap();                   // element -> giá trị cuối cùng đã thấy
    const tokens = new WeakMap();

    function numNode(el) {
      const w = d.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) if (/\d/.test(n.nodeValue)) return n;
      return null;
    }
    function parse(s) {
      if (SKIP.test(s)) return null;
      const m = s.match(NUM);
      if (!m) return null;
      const neg = m[1] === '-' || m[1] === '−';
      const v = parseFloat(m[2].replace(/,/g, '') + (m[3] || '')) * (neg ? -1 : 1);
      return { v, m, dec: m[3] ? m[3].length - 1 : 0, comma: m[2].includes(','), plus: m[1] === '+',
               minus: m[1] === '−' ? '−' : '-' };
    }
    function fmt(x, p) {
      let s = Math.abs(x).toFixed(p.dec);
      if (p.comma) { const [i, f] = s.split('.'); s = i.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (f ? '.' + f : ''); }
      const zero = Number(s.replace(/,/g, '')) === 0;
      return (x < 0 && !zero ? p.minus : (p.plus && x >= 0 ? '+' : '')) + s;
    }
    function animate(el, node, text, p, from, dur) {
      const pre = text.slice(0, p.m.index), post = text.slice(p.m.index + p.m[0].length);
      const tok = {}; tokens.set(el, tok);
      const t0 = performance.now();
      const step = now => {
        if (tokens.get(el) !== tok) return;
        if (mine.has(node) && node.nodeValue !== mine.get(node)) return;   // React vừa ghi giá trị mới
        let k = Math.min(1, (now - t0) / dur);
        k = k >= 1 ? 1 : 1 - Math.pow(2, -10 * k);                        // easeOutExpo
        const out = k >= 1 ? text : pre + fmt(from + (p.v - from) * k, p) + post;
        mine.set(node, out);
        node.nodeValue = out;
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
    function countIn(el) {
      if (counted.has(el)) return;
      counted.add(el);
      const node = numNode(el);
      if (!node) return;
      const text = node.nodeValue, p = parse(text);
      if (!p) return;
      value.set(el, p.v);
      if (p.v !== 0) animate(el, node, text, p, 0, 1400);
    }
    function changed(el) {
      const node = numNode(el);
      if (!node) return;
      if (mine.has(node) && node.nodeValue === mine.get(node)) return;     // chính mình vừa ghi
      const text = node.nodeValue, p = parse(text);
      if (!p) return;
      const old = value.get(el);
      value.set(el, p.v);
      counted.add(el);
      if (old === undefined || old === p.v) return;
      el.removeAttribute('data-flash');
      void el.offsetWidth;                                                 // chạy lại animation
      el.setAttribute('data-flash', p.v > old ? 'up' : 'down');
      if (!reduce) animate(el, node, text, p, old, 800);
    }

    /* ------------------------------------------------------------ chữ "giải mã" */
    const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+=<>/';
    function scramble(el) {
      if (el.hasAttribute('data-qsc')) return;
      el.setAttribute('data-qsc', '');
      const nodes = [...el.childNodes].filter(n => n.nodeType === 3 && n.nodeValue.trim().length > 2);
      for (const node of nodes) {
        const target = node.nodeValue, chars = Array.from(target);
        const t0 = performance.now(), dur = 650 + chars.length * 18;
        const at = chars.map((_, i) => (i / chars.length) * dur * 0.75 + Math.random() * dur * 0.25);
        const step = now => {
          if (mine.has(node) && node.nodeValue !== mine.get(node)) return;
          const t = now - t0;
          let out = '';
          for (let i = 0; i < chars.length; i++) {
            const c = chars[i];
            out += t >= at[i] || !/[\p{L}\p{N}]/u.test(c) ? c : GLYPHS[(Math.random() * GLYPHS.length) | 0];
          }
          if (t >= dur) out = target;
          mine.set(node, out);
          node.nodeValue = out;
          if (t < dur) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
    }

    /* ------------------------------------------------------------ theo dõi DOM (Streamlit vẽ lại liên tục) */
    const mo = new MutationObserver(records => {
      const seen = new Set();
      for (const r of records) {
        if (r.type === 'childList') r.addedNodes.forEach(scan);
        const host = (r.target.nodeType === 3 ? r.target.parentElement : r.target)?.closest?.(COUNT);
        if (host && counted.has(host) && !seen.has(host)) { seen.add(host); changed(host); }
      }
    });
    scan(d.body);
    mo.observe(d.body, { childList: true, subtree: true, characterData: true });

    /* ------------------------------------------------------------ đèn soi, nghiêng 3D, nút hút theo chuột */
    const SPOT = '.card, .hstat, .step, [data-testid="stMetric"], .hero';
    const TILT = '.hstat, .grid > .card';
    let px = -1e4, py = -1e4, hover = null, tilted = null, magnet = null, queued = false;
    function frame() {
      queued = false;
      const el = hover;
      if (el) {
        const r = el.getBoundingClientRect();
        el.style.setProperty('--mx', `${px - r.left}px`);
        el.style.setProperty('--my', `${py - r.top}px`);
      }
      const t = el && finePointer && !reduce && el.matches(TILT) ? el : null;
      if (tilted && tilted !== t) tilted.style.transform = '';
      tilted = t;
      if (t) {
        const r = t.getBoundingClientRect();
        const dx = (px - r.left) / r.width - 0.5, dy = (py - r.top) / r.height - 0.5;
        t.style.transform = `perspective(900px) rotateX(${(-dy * 7).toFixed(2)}deg) rotateY(${(dx * 8).toFixed(2)}deg) translateY(-4px)`;
      }
    }
    d.addEventListener('pointermove', e => {
      px = e.clientX; py = e.clientY;
      root.classList.add('qfx-pointer');
      hover = e.target.closest?.(SPOT) || null;
      const b = finePointer && !reduce ? e.target.closest?.('.btn') : null;
      if (magnet && magnet !== b) magnet.style.transform = '';
      magnet = b;
      if (b) {
        const r = b.getBoundingClientRect();
        b.style.transform = `translate(${((px - r.left - r.width / 2) * 0.22).toFixed(1)}px, ` +
                            `${((py - r.top - r.height / 2) * 0.35).toFixed(1)}px)`;
      }
      if (!queued) { queued = true; requestAnimationFrame(frame); }
    }, { passive: true });
    root.addEventListener('pointerleave', () => { root.classList.remove('qfx-pointer'); hover = null; frame(); });

    // gợn sóng khi bấm nút
    d.addEventListener('pointerdown', e => {
      const b = e.target.closest?.('.stButton > button, .stFormSubmitButton > button, .stLinkButton > a, .stDownloadButton > button');
      if (!b || reduce) return;
      const r = b.getBoundingClientRect();
      b.style.setProperty('--rx', `${e.clientX - r.left}px`);
      b.style.setProperty('--ry', `${e.clientY - r.top}px`);
      b.removeAttribute('data-rip'); void b.offsetWidth; b.setAttribute('data-rip', '');
    }, { passive: true });

    /* ------------------------------------------------------------ nền: mạng hạt + quầng sáng theo chuột */
    if (!reduce) {
      const glow = d.createElement('div');
      glow.id = 'qfx-glow';
      const cv = d.createElement('canvas');
      cv.id = 'qfx-net';
      d.body.prepend(cv, glow);
      const ctx = cv.getContext('2d');
      const COLORS = ['57,135,229', '144,133,233', '45,212,191', '124,179,240'];
      let W = 0, H = 0, dpr = 1, pts = [];
      function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = innerWidth; H = innerHeight;
        cv.width = W * dpr; cv.height = H * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const n = Math.round(Math.min(90, Math.max(36, (W * H) / 17000)));
        pts = Array.from({ length: n }, () => ({
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.32, vy: (Math.random() - 0.5) * 0.32,
          r: 0.6 + Math.random() * 1.6, c: COLORS[(Math.random() * COLORS.length) | 0], ph: Math.random() * 6.28,
        }));
      }
      resize();
      addEventListener('resize', resize);
      let gx = innerWidth / 2, gy = innerHeight / 3;
      const LINK = 135, MOUSE = 190;
      function tick(t) {
        requestAnimationFrame(tick);
        if (d.hidden) return;
        gx += (px - gx) * 0.08; gy += (py - gy) * 0.08;
        if (px > -1e3) glow.style.transform = `translate3d(${gx.toFixed(1)}px, ${gy.toFixed(1)}px, 0)`;
        ctx.clearRect(0, 0, W, H);
        for (const p of pts) {
          const dxm = px - p.x, dym = py - p.y, dm = Math.hypot(dxm, dym);
          if (dm < MOUSE && dm > 1) { p.vx += (dxm / dm) * 0.004; p.vy += (dym / dm) * 0.004; }
          p.vx *= 0.995; p.vy *= 0.995;
          const sp = Math.hypot(p.vx, p.vy);
          if (sp < 0.08) { p.vx += (Math.random() - 0.5) * 0.04; p.vy += (Math.random() - 0.5) * 0.04; }
          p.x += p.vx; p.y += p.vy;
          if (p.x < -20) p.x = W + 20; else if (p.x > W + 20) p.x = -20;
          if (p.y < -20) p.y = H + 20; else if (p.y > H + 20) p.y = -20;
        }
        ctx.lineWidth = 1;
        for (let i = 0; i < pts.length; i++) {
          const a = pts[i];
          for (let j = i + 1; j < pts.length; j++) {
            const b = pts[j], dx = a.x - b.x, dy = a.y - b.y, dd = dx * dx + dy * dy;
            if (dd < LINK * LINK) {
              ctx.strokeStyle = `rgba(${a.c},${(1 - Math.sqrt(dd) / LINK) * 0.22})`;
              ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
            }
          }
          const dm = Math.hypot(px - a.x, py - a.y);
          if (dm < MOUSE) {
            ctx.strokeStyle = `rgba(124,179,240,${(1 - dm / MOUSE) * 0.5})`;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(px, py); ctx.stroke();
          }
        }
        for (const p of pts) {
          const tw = 0.55 + 0.45 * Math.sin(t / 900 + p.ph);
          ctx.fillStyle = `rgba(${p.c},${0.35 + 0.5 * tw})`;
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (0.8 + 0.4 * tw), 0, 6.283); ctx.fill();
        }
      }
      requestAnimationFrame(tick);
    }

    root.classList.add('qfx');   // bật chế độ "chờ cuộn tới" chỉ khi mọi thứ ở trên đã chạy được
  } catch (err) {
    root.classList.remove('qfx');
    console.warn('[qfx] tắt hiệu ứng:', err);
  }
})();
