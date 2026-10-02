/* =====================================================================
   CeliacMap — service-worker.js
   Installable-app shell only. Network first: online, every request goes
   to the network exactly as without a service worker; the cached copy is
   used only when the network fails. Only the files in SHELL are touched.
   Places, Supabase, the chat, map tiles, CDNs and fonts are never
   intercepted or cached, and no location is ever stored.
   ===================================================================== */
"use strict";

var CACHE_PREFIX = "celiacmap-shell-";
var CACHE_NAME = CACHE_PREFIX + "v1";

var SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "css/styles.css",
  "js/main.js",
  "js/config.js",
  "js/map.js",
  "js/kitchen.js",
  "js/suggest.js",
  "js/report.js",
  "js/ranking.js",
  "js/opinions.js",
  "js/chat.js",
  "js/pwa.js",
  "assets/icons/favicon.svg",
  "assets/icons/favicon-48.png",
  "assets/icons/favicon-96.png",
  "assets/icons/apple-touch-icon.png",
  "assets/icons/icon-192.png",
  "assets/icons/icon-512.png",
  "assets/icons/icon-maskable-512.png",
  "assets/images/bienestar-gluten-free.webp"
];

function scopeUrl(path) {
  return new URL(path, self.registration.scope).href;
}

function shellKey(request) {
  if (request.method !== "GET") return null;
  var url = new URL(request.url);
  if (url.origin !== new URL(self.registration.scope).origin) return null;
  url.hash = "";
  if (request.mode === "navigate") {
    url.search = "";
    if (url.href === scopeUrl("./") || url.href === scopeUrl("index.html")) return scopeUrl("index.html");
    return null;
  }
  if (url.search) return null;
  for (var i = 0; i < SHELL.length; i++) {
    if (SHELL[i] !== "./" && url.href === scopeUrl(SHELL[i])) return url.href;
  }
  return null;
}

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL.filter(function (path) { return path !== "./"; }).map(function (path) {
        return new Request(scopeUrl(path), { cache: "reload" });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (key) {
        return key.indexOf(CACHE_PREFIX) === 0 && key !== CACHE_NAME;
      }).map(function (key) { return caches.delete(key); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var key = shellKey(event.request);
  if (!key) return;
  event.respondWith(
    fetch(event.request).then(function (response) {
      if (response.ok && response.type === "basic") {
        var copy = response.clone();
        event.waitUntil(caches.open(CACHE_NAME).then(function (cache) { return cache.put(key, copy); }));
      }
      return response;
    }, function (error) {
      return caches.open(CACHE_NAME).then(function (cache) { return cache.match(key); }).then(function (cached) {
        if (cached) return cached;
        throw error;
      });
    })
  );
});
