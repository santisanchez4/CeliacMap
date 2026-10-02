// PWA shell: manifest, icons, the service worker's closed allowlist and network-first
// behavior, and the offline notice. No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_pwa.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

const SCOPE = "https://celiacmap.org/";
const html = await Deno.readTextFile("index.html");
const swSource = await Deno.readTextFile("service-worker.js");
const manifest = JSON.parse(await Deno.readTextFile("manifest.webmanifest"));

async function pngSize(path) {
  const bytes = await Deno.readFile(path);
  const view = new DataView(bytes.buffer);
  return `${view.getUint32(16)}x${view.getUint32(20)}`;
}

function loadWorker({ network }) {
  const listeners = {};
  const stores = new Map();
  const fetched = [];
  const cacheFor = (name) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const store = stores.get(name);
    return {
      addAll: async (requests) => { for (const r of requests) store.set(r.url, new Response("shell:" + r.url)); },
      put: async (key, response) => { store.set(key, response); },
      match: async (key) => store.get(key)?.clone(),
    };
  };
  const self = {
    registration: { scope: SCOPE },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    skipWaiting: async () => {}, clients: { claim: async () => {} },
  };
  const context = {
    self, URL, Request, Response,
    caches: {
      open: async (name) => cacheFor(name),
      keys: async () => [...stores.keys()],
      delete: async (name) => stores.delete(name),
    },
    fetch: async (request) => { fetched.push(request.url); return network(request); },
  };
  vm.runInNewContext(swSource, context);

  async function dispatch(type, extra = {}) {
    const pending = [];
    let responded = null;
    const event = {
      ...extra,
      waitUntil: (p) => pending.push(p),
      respondWith: (p) => { responded = p; },
    };
    listeners[type](event);
    const response = responded ? await responded.catch((e) => e) : null;
    await Promise.all(pending);
    return { intercepted: responded !== null, response };
  }

  const request = (url, init = {}) => ({ url, method: "GET", mode: "cors", ...init });
  return { listeners, stores, fetched, dispatch, request, context };
}

const shell = vm.runInNewContext(swSource + "; SHELL", {
  self: { addEventListener() {}, registration: { scope: SCOPE } }, URL,
});

Deno.test("the manifest describes an installable, standalone app scoped to the site", () => {
  assert.equal(manifest.start_url, "./");
  assert.equal(manifest.scope, "./");
  assert.equal(manifest.id, "./");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.short_name, "CeliacMap");
  assert.equal(manifest.theme_color, "#2d6a4f");
  assert.equal(manifest.background_color, "#fdfaf5");
});

Deno.test("manifest icons exist with their declared sizes, including a maskable 512", async () => {
  for (const icon of manifest.icons) {
    assert.equal(await pngSize(icon.src), icon.sizes, icon.src);
  }
  const purposes = manifest.icons.map((i) => `${i.sizes}:${i.purpose}`);
  assert.ok(purposes.includes("192x192:any"));
  assert.ok(purposes.includes("512x512:any"));
  assert.ok(purposes.includes("512x512:maskable"));
});

Deno.test("the page links the manifest and loads pwa.js before the analytics beacon", () => {
  const { document } = parseHTML(html);
  assert.ok(Boolean(document.querySelector('link[rel="manifest"][href="manifest.webmanifest"]')));
  const scripts = [...document.body.querySelectorAll("script")].map((s) => s.getAttribute("src"));
  assert.ok(scripts.includes("js/pwa.js"));
  assert.ok(scripts.indexOf("js/pwa.js") < scripts.length - 1, "the beacon stays the last script");
});

Deno.test("the shell lists every same-origin file the page loads, and every listed file exists", async () => {
  const { document } = parseHTML(html);
  const local = [
    ...[...document.querySelectorAll("script[src], img[src]")].map((n) => n.getAttribute("src")),
    ...[...document.querySelectorAll("link[href]")].map((n) => n.getAttribute("href")),
  ].filter((u) => u && !/^(https?:|mailto:|#|data:)/.test(u));
  for (const path of local) assert.ok(shell.includes(path), `${path} is missing from SHELL`);
  for (const path of shell) {
    if (path === "./") continue;
    assert.ok((await Deno.stat(path)).isFile, `${path} does not exist`);
  }
});

Deno.test("the shell is closed: relative paths only, no data, API, tiles, config of agents or docs", () => {
  for (const path of shell) {
    assert.ok(!/^(https?:)?\/\//.test(path), `${path} is not relative`);
    assert.ok(/^(\.\/|index\.html|manifest\.webmanifest|css\/|js\/|assets\/)/.test(path), `${path} is outside the site shell`);
  }
});

Deno.test("install precaches the shell under the registration scope", async () => {
  const sw = loadWorker({ network: async () => new Response("net") });
  await sw.dispatch("install");
  const [name] = sw.stores.keys();
  assert.equal(name, "celiacmap-shell-v1");
  assert.ok(sw.stores.get(name).has(SCOPE + "index.html"));
  assert.ok(sw.stores.get(name).has(SCOPE + "js/map.js"));
  assert.equal(sw.stores.get(name).size, shell.length - 1);
});

Deno.test("activate deletes old shell caches and nothing else", async () => {
  const sw = loadWorker({ network: async () => new Response("net") });
  for (const name of ["celiacmap-shell-v0", "celiacmap-shell-v1", "someone-else"]) await sw.context.caches.open(name);
  await sw.dispatch("activate");
  assert.deepEqual([...sw.stores.keys()].sort(), ["celiacmap-shell-v1", "someone-else"]);
});

Deno.test("data, chat, tiles, CDNs, fonts, analytics and writes are never intercepted", async () => {
  const sw = loadWorker({ network: async () => new Response("net") });
  const untouched = [
    sw.request("https://abc.supabase.co/rest/v1/places?select=id,name&status=eq.approved"),
    sw.request("https://abc.supabase.co/functions/v1/chat", { method: "POST" }),
    sw.request("https://a.basemaps.cartocdn.com/light_all/12/1400/2400.png"),
    sw.request("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
    sw.request("https://fonts.googleapis.com/css2?family=DM+Sans"),
    sw.request("https://static.cloudflareinsights.com/beacon.min.js"),
    sw.request(SCOPE + "js/map.js", { method: "POST" }),
    sw.request(SCOPE + "js/map.js?v=2"),
    sw.request(SCOPE + "db/schema.sql"),
    sw.request(SCOPE + "docs/legal/privacidad.html", { mode: "navigate" }),
  ];
  for (const request of untouched) {
    const { intercepted } = await sw.dispatch("fetch", { request });
    assert.equal(intercepted, false, request.url);
  }
  assert.equal(sw.stores.size, 0, "nothing was cached");
});

Deno.test("online, shell files come from the network and refresh the cache", async () => {
  const sw = loadWorker({ network: async (r) => Object.defineProperty(new Response("fresh:" + r.url), "type", { value: "basic" }) });
  const { intercepted, response } = await sw.dispatch("fetch", { request: sw.request(SCOPE + "css/styles.css") });
  assert.equal(intercepted, true);
  assert.equal(await response.text(), "fresh:" + SCOPE + "css/styles.css");
  assert.deepEqual(sw.fetched, [SCOPE + "css/styles.css"]);
  const cached = await sw.stores.get("celiacmap-shell-v1").get(SCOPE + "css/styles.css").text();
  assert.equal(cached, "fresh:" + SCOPE + "css/styles.css");
});

Deno.test("offline, the cached shell answers and navigations to the root fall back to index.html", async () => {
  const sw = loadWorker({ network: async () => { throw new TypeError("offline"); } });
  await sw.dispatch("install");
  const asset = await sw.dispatch("fetch", { request: sw.request(SCOPE + "js/chat.js") });
  assert.equal(await asset.response.text(), "shell:" + SCOPE + "js/chat.js");
  for (const url of [SCOPE, SCOPE + "?utm_source=qr", SCOPE + "index.html#map"]) {
    const page = await sw.dispatch("fetch", { request: sw.request(url, { mode: "navigate" }) });
    assert.equal(await page.response.text(), "shell:" + SCOPE + "index.html", url);
  }
});

Deno.test("offline with nothing cached, the network error is passed through", async () => {
  const sw = loadWorker({ network: async () => { throw new TypeError("offline"); } });
  const { intercepted, response } = await sw.dispatch("fetch", { request: sw.request(SCOPE + "js/main.js") });
  assert.equal(intercepted, true);
  assert.ok(response instanceof TypeError);
});

Deno.test("failed responses are not cached", async () => {
  const sw = loadWorker({ network: async () => Object.defineProperty(new Response("nope", { status: 404 }), "type", { value: "basic" }) });
  await sw.dispatch("fetch", { request: sw.request(SCOPE + "js/main.js") });
  assert.equal(sw.stores.size, 0);
});

Deno.test("the offline notice is hidden online, shown offline, and translated", async () => {
  const { window, document } = parseHTML(html);
  const notice = document.getElementById("offline-notice");
  assert.equal(notice.getAttribute("role"), "status");
  assert.equal(notice.hidden, true);
  const listeners = {};
  const navigator = { onLine: true, serviceWorker: { register: async () => {} } };
  const browser = { addEventListener: (type, fn) => { listeners[type] = fn; } };
  vm.runInNewContext(await Deno.readTextFile("js/pwa.js"), { window: browser, document, navigator });
  assert.equal(notice.hidden, true);
  navigator.onLine = false; listeners.offline();
  assert.equal(notice.hidden, false);
  navigator.onLine = true; listeners.online();
  assert.equal(notice.hidden, true);
  assert.ok(typeof listeners.load === "function", "the service worker registers on load");

  const css = await Deno.readTextFile("css/styles.css");
  assert.ok(/\.offline-notice\[hidden\]\s*\{\s*display:\s*none;?\s*\}/.test(css));
  const main = await Deno.readTextFile("js/main.js");
  assert.ok(main.includes('"offline.notice":'));
});

Deno.test("pwa.js registers the worker relative to the page and never touches location or storage", async () => {
  const source = await Deno.readTextFile("js/pwa.js");
  assert.ok(source.includes('register("service-worker.js")'));
  assert.ok(!/geolocation|localStorage|sessionStorage|indexedDB/.test(source));
  assert.ok(!/geolocation|localStorage|indexedDB|postMessage/.test(swSource));
});
