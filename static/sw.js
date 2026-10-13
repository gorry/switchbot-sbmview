// SwitchBot Meter View (sbmview) - Service Worker
const CACHE_NAME = 'sbmview-v1';
const PRECACHE_URLS = [
  '/',
  '/manifest.json',
  '/static/manifest.json',
  '/static/favicon.ico',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/js/index.js',
  '/static/js/detail.js',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// インストール処理：主要なアセットを事前キャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn('[SW] Precache partial fail:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// アクティベーション処理：古いキャッシュの削除
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// フェッチ処理：Network-First（ネットワーク優先、オフライン時はキャッシュ）
self.addEventListener('fetch', (event) => {
  // GET 以外のリクエストは処理しない
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Chrome 拡張機能などのリクエストはスキップ
  if (!url.protocol.startsWith('http')) return;

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // 成功したレスポンスをキャッシュに保存して更新
        if (networkResponse && networkResponse.status === 200) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // オフラインまたはネットワークエラー時はキャッシュから返す
        return caches.match(event.request);
      })
  );
});
