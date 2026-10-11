// P11.S4.T2 (PWA-01): an offline shell, nothing more. The only thing ever cached is the self-contained offline page.
// Page navigations go to the network and fall back to that page only when the network fails; every other request
// (API calls, answers, assets, files) is left entirely to the browser and the network. So no exam answer, key or
// personal page is ever kept in a service-worker cache, and signing out leaves nothing behind here.
const CACHE = "portal-offline-v1";
const OFFLINE = "/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.add(new Request(OFFLINE, { cache: "reload" }))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || req.mode !== "navigate") return;
  event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
});
