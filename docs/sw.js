/* Service worker: cho app mở được khi mất mạng (dữ liệu giá lần cuối lưu trong máy).
   - File của app: lấy bản mới qua mạng trước (hỏi lại GitHub bằng ETag, bỏ qua cache 10 phút của trình duyệt),
     mất mạng thì dùng bản đã lưu -> đẩy code lên là lần mở sau thấy ngay.
   - Font + thư viện biểu đồ (CDN, đã ghim phiên bản): dùng bản đã lưu trước.
   - API giá (Binance, alternative.me): không đụng tới, luôn lấy trực tiếp. */
const CACHE = 'duckquant-v5';
const SHELL = ['./', 'index.html', 'css/theme.css', 'css/app.css', 'js/app.js', 'js/indicators.js', 'js/api.js', 'js/fx.js',
               'js/ui.js', 'js/advisor.js', 'js/charts.js', 'data/snapshot.json', 'manifest.webmanifest', 'icons/icon-192.png',
               'icons/apple-touch-icon.png'];
const CDN = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    e.respondWith(fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' }).then(res => {
      if (req.mode === 'navigate' && res.redirected) return Response.redirect(res.url, 302);   // Safari không nhận trang bị chuyển hướng từ SW
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then(r => r || caches.match('./'))));
  } else if (CDN.includes(url.hostname)) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === 'opaque') { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
