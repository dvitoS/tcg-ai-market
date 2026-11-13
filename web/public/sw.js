/* Soft Ink offline shell — precache static assets only; never pin live HTML/JS
 * (avoids React #418 when a stale "/" shell hydrates against a new deploy). */
const CACHE = "kestrel-shell-v4";
const PRECACHE = [
  "/offline",
  "/manifest.webmanifest",
  "/kestrel-logo.png",
  "/kestrel-mark.png",
  "/icons/favicon-32.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

function sameOrigin(url) {
  return url.origin === self.location.origin;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  let url;
  try {
    url = new URL(req.url);
  } catch {
    return;
  }
  if (!sameOrigin(url)) return;
  // Live market data must stay network-only.
  if (url.pathname.startsWith("/api/")) return;
  // App HTML + Next chunks must stay network-first so deploys don't hydrate
  // against a stale shell (React #418).
  if (req.mode === "navigate" || url.pathname.startsWith("/_next/")) {
    event.respondWith(
      fetch(req).catch(async () => {
        if (req.mode === "navigate") {
          const cached = await caches.match(req);
          return cached || caches.match("/offline");
        }
        return caches.match(req);
      }),
    );
    return;
  }

  const staticAsset =
    url.pathname.startsWith("/icons/") ||
    /\.(?:png|svg|webp|jpe?g|gif|ico|woff2?)$/i.test(url.pathname);

  if (!staticAsset) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    }),
  );
});
