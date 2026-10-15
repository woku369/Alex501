// Service Worker der Alex-501-Tablet-Version: macht die App nach einmaligem Laden offline nutzbar.
// Beim Ändern der App VERSION erhöhen (und APP_VERSION in app.js angleichen), damit die Geräte die neuen Dateien holen.

const VERSION = '1.0.0';
const CACHE = `alex501-pwa-${VERSION}`;
const ASSETS = [
  './', './index.html', './styles.css', './app.js', './db.js', './calc.js', './measurement.js',
  './alkoholtabelle.js', './infotext.js', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/icon-maskable-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith('alex501-pwa-') && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

// Cache zuerst (garantiert Offline-Betrieb), im Hintergrund aktualisieren, wenn eine Verbindung besteht.
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(request, { ignoreSearch: true });
    const network = fetch(request).then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    }).catch(() => null);
    if (cached) {
      event.waitUntil(network);
      return cached;
    }
    const response = await network;
    if (response) return response;
    if (request.mode === 'navigate') return (await cache.match('./index.html')) || Response.error();
    return Response.error();
  })());
});
