const CACHE_NAME = "meteo-radar-sanse-v2";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  const radarPath = new URL("./data/radar.json", self.registration.scope).pathname;

  // Meteorología: red primero para no mostrar previsiones antiguas; caché como respaldo sin conexión.
  if (url.origin === self.location.origin && url.pathname === radarPath) {
    event.respondWith(
      fetch(request).then(response => {
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, copy)));
        }
        return response;
      }).catch(async () => {
        const cached = await caches.match(request);
        return cached || new Response("No hay datos meteorológicos guardados para consultar sin conexión.", {
          status:503, headers:{"Content-Type":"text/plain; charset=utf-8"}
        });
      })
    );
    return;
  }

  // Recursos estáticos: caché primero; navegación intenta red y usa la app guardada si falla.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).then(response => {
      if (response.ok) {
        const copy=response.clone();
        event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.put("./index.html",copy)));
      }
      return response;
    }).catch(() => caches.match("./index.html")));
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
