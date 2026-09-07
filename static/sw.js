/* Service worker minim pentru Glow Diary — face site-ul instalabil ca aplicație
   și păstrează în cache fișierele statice (CSS/JS/iconițe) pentru încărcări
   mai rapide la vizite repetate. Paginile HTML merg mereu în rețea întâi,
   ca să nu vezi niciodată conținut vechi despre produse. */
var CACHE_NAME = "glow-diary-v1";
var STATIC_ASSETS = [
  "/static/css/style.css",
  "/static/js/favorites.js",
  "/static/js/cards.js",
  "/static/js/milestone.js",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (key) {
          return key !== CACHE_NAME;
        }).map(function (key) {
          return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  var url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;

  var isStatic = url.pathname.indexOf("/static/") === 0 || url.pathname.indexOf("/media/") === 0;

  if (isStatic) {
    event.respondWith(
      caches.match(event.request).then(function (cached) {
        return (
          cached ||
          fetch(event.request).then(function (response) {
            var copy = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(event.request, copy);
            });
            return response;
          })
        );
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request).catch(function () {
      return caches.match(event.request);
    })
  );
});
