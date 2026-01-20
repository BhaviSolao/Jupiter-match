self.addEventListener("install", event => {
  event.waitUntil(
    caches.open("jupiter-match-cache").then(cache => {
      return cache.addAll([
        "/ui"
      ]);
    })
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
