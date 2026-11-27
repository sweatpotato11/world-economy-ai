// 앱처럼 설치했을 때 쓰는 서비스 워커예요.
// 항상 인터넷에서 최신 내용을 먼저 가져오고, 인터넷이 끊겼을 때만 저장해 둔 화면을 보여줘요.
const CACHE = 'wea-v3';
const SHELL = ['./', 'index.html', 'korea.html', 'weekly.html', 'glossary.html', 'issue.html', 'style.css', 'app.js',
  'manifest.webmanifest', 'icons/icon-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request, { ignoreSearch: url.pathname.endsWith('.html') }))
  );
});
