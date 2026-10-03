// «Cerca mío»: one reading per tap, kept only in memory, never stored or sent.
// No network, no browser: Leaflet, geolocation, storage and fetch are stubs that record every call.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_nearby.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

// Distinctive coordinates, so any leak shows up as a plain substring.
const USER = { lat: -34.90013, lng: -56.16017 };
const LEAK = [/-34\.9001/, /-56\.1601/, /34\.9001/, /56\.1601/];

function rowsAround() {
  const rows = Array.from({ length: 12 }, (_, i) => ({
    id: "near-" + i, name: "Near " + String(i).padStart(2, "0"), city: "Montevideo", category: "restaurant",
    safety_level: i % 2 ? "celiac_friendly" : "gluten_free_100",
    lat: -34.9 - i * 0.004, lng: -56.16,
    community_warning_at: i === 1 ? "1970-01-01T00:00:05Z" : null,
  }));
  rows.push({ id: "far-17", name: "Far 17", city: "Montevideo", category: "cafe", safety_level: "options_available", lat: -35.05, lng: -56.16 });
  rows.push({ id: "ba", name: "Buenos Aires", city: "Buenos Aires", category: "shop", safety_level: "options_available", lat: -34.6037, lng: -58.3816 });
  return rows;
}

async function fixture({ permission = "prompt", secure = true, withGeolocation = true } = {}) {
  const html = await Deno.readTextFile("index.html");
  const { window, document } = parseHTML(html);
  window.HTMLElement.prototype.focus = function () { document.focused = this; };
  window.HTMLElement.prototype.getClientRects = function () { return [1]; };
  window.HTMLElement.prototype.scrollIntoView = function () {};
  window.HTMLElement.prototype.getBoundingClientRect = function () { return { top: 100, bottom: 600, height: 500 }; };
  Object.defineProperty(document, "activeElement", { get: () => document.focused });
  let visibility = "visible";
  Object.defineProperty(document, "visibilityState", { get: () => visibility, configurable: true });
  Object.defineProperty(document.getElementById("city-select"), "value", { writable: true, value: "all" });

  const events = [];
  const originalDispatch = document.dispatchEvent.bind(document);
  document.dispatchEvent = (event) => {
    let detail = "";
    try { detail = JSON.stringify(event.detail ?? null); } catch { detail = String(event.detail); }
    events.push({ type: event.type, detail });
    return originalDispatch(event);
  };

  const layers = new Set();
  const userLayers = [];
  const map = {
    setView(center, zoom) { this.lastView = { center, zoom }; return this; }, on() {}, invalidateSize() {},
    fitBounds(bounds, options) { this.lastFit = { bounds, options }; }, flyTo() {}, flyToBounds() {},
    getCenter() { return [0, 0]; }, getZoom() { return 12; }, scrollWheelZoom: { enable() {}, disable() {} },
  };
  let groups = 0;
  const L = {
    map: () => map, tileLayer: () => ({ addTo() {} }),
    latLngBounds: (points) => ({ points, pad() { return this; } }),
    divIcon: (x) => x,
    layerGroup: () => {
      const own = new Set();
      const isUserLayer = ++groups === 2; // first group: place markers; second: the user's location
      const group = {
        addTo() { return this; }, hasLayer: (m) => (isUserLayer ? own : layers).has(m),
        addLayer(m) { (isUserLayer ? own : layers).add(m); },
        removeLayer(m) { (isUserLayer ? own : layers).delete(m); },
        clearLayers() { own.clear(); }, size: () => own.size,
      };
      if (isUserLayer) userLayers.push(group);
      return group;
    },
    featureGroup: () => ({ getBounds: () => ({ pad() { return {}; } }) }),
    circle: (point, options) => ({ kind: "circle", point, options }),
    marker(coords, options) {
      const element = document.createElement("div");
      return { options, on() {}, getElement: () => element, getLatLng: () => coords, setIcon(icon) { this.options.icon = icon; } };
    },
  };

  const geoCalls = { get: 0, watch: 0, options: [], pending: [] };
  const geolocation = {
    getCurrentPosition(success, error, options) { geoCalls.get++; geoCalls.options.push(options); geoCalls.pending.push({ success, error }); },
    watchPosition() { geoCalls.watch++; return 1; },
    clearWatch() {},
  };
  const navigator = { permissions: { query: async () => ({ state: permission }) } };
  if (withGeolocation) navigator.geolocation = geolocation;

  const storageWrites = [];
  const storage = (name) => {
    const store = new Map();
    return {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => { storageWrites.push({ name, k, v: String(v) }); store.set(k, String(v)); },
      removeItem: (k) => store.delete(k),
    };
  };
  const localStorage = storage("localStorage");
  const sessionStorage = storage("sessionStorage");

  const windowListeners = {};
  const browser = {
    innerHeight: 700, isSecureContext: secure,
    CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture" },
    matchMedia: () => ({ matches: false }),
    addEventListener(type, fn) { (windowListeners[type] ||= []).push(fn); },
    scrollX: 0, scrollY: 0, scrollTo() {},
    visualViewport: { height: 500, offsetTop: 0, addEventListener() {} },
    localStorage, sessionStorage,
  };
  let now = 10_000;
  const requests = [];
  const rows = rowsAround();
  const context = {
    window: browser, document, L, navigator, localStorage, sessionStorage, CustomEvent: window.CustomEvent,
    Date: { now: () => now, parse: Date.parse },
    fetch: async (url, init = {}) => {
      requests.push({ url: String(url), body: init.body ? String(init.body) : "" });
      return { ok: true, json: async () => String(url).includes("functions/v1/chat")
        ? { reply: "Hola", places: [], pending_submission: null } : rows };
    },
    setTimeout, clearTimeout, AbortController,
  };
  vm.runInNewContext(await Deno.readTextFile("js/geo.js"), context);
  vm.runInNewContext(await Deno.readTextFile("js/map.js"), context);
  await settle();

  function click(target) {
    const el = typeof target === "string" ? document.querySelector(target) : target;
    assert.ok(Boolean(el), String(target));
    el.dispatchEvent(new window.Event("click", { bubbles: true }));
    return el;
  }
  async function settle() { for (let i = 0; i < 3; i++) await new Promise((r) => setTimeout(r, 0)); }
  async function grant(position = { ...USER, accuracy: 20 }) {
    const call = geoCalls.pending.shift();
    call.success({ coords: { latitude: position.lat, longitude: position.lng, accuracy: position.accuracy } });
    await settle();
  }
  async function fail(code) {
    geoCalls.pending.shift().error({ code });
    await settle();
  }
  const nearby = () => document.getElementById("nearby");
  const text = () => nearby().textContent;
  const action = (name) => document.querySelector(`[data-nearby-action="${name}"]`);
  const places = () => [...document.querySelectorAll(".nearby-place")];
  return {
    document, window, browser, map, geoCalls, requests, storageWrites, events, context, click, settle, grant, fail,
    nearby, text, action, places, windowListeners, userLayer: () => userLayers[0],
    tick: (ms) => { now += ms; },
    hide: () => { visibility = "hidden"; document.dispatchEvent(new window.Event("visibilitychange")); },
    show: () => { visibility = "visible"; },
    loadChat: async () => { vm.runInNewContext(await Deno.readTextFile("js/chat.js"), context); await settle(); },
  };
}

async function located(options = {}) {
  const f = await fixture(options);
  f.click("#nearby-button");
  await f.settle();
  f.click(f.action("locate"));
  await f.grant(options.position);
  return f;
}

Deno.test("nothing is asked on load: the button appears and no location is read", async () => {
  const f = await fixture();
  assert.equal(f.document.getElementById("nearby-button").hidden, false);
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.geoCalls.get, 0);
  assert.equal(f.geoCalls.watch, 0);
});

Deno.test("the first tap explains before the browser asks, and reads nothing yet", async () => {
  const f = await fixture();
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.nearby().hidden, false);
  assert.match(f.text(), /una sola vez/);
  assert.match(f.text(), /No la guardamos ni la enviamos/);
  assert.match(f.text(), /proveedor del mapa puede deducir la zona/);
  assert.equal(f.geoCalls.get, 0);
  assert.ok(Boolean(f.action("locate")) && Boolean(f.action("city")));
});

Deno.test("one tap is one reading: getCurrentPosition once, never watchPosition, 10 s timeout, no cached fix", async () => {
  const f = await located();
  assert.equal(f.geoCalls.get, 1);
  assert.equal(f.geoCalls.watch, 0);
  assert.deepEqual({ ...f.geoCalls.options[0] }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });
});

Deno.test("results: the 10 nearest within 5 km, nearest first, each with its public label and a straight-line distance", async () => {
  const f = await located();
  const items = f.places();
  assert.equal(items.length, 10);
  assert.deepEqual(items.map((b) => b.getAttribute("data-nearby-id")), Array.from({ length: 10 }, (_, i) => "near-" + i));
  for (const item of items) {
    const label = item.querySelector(".pp-badge").textContent;
    assert.ok(["Espacio 100% sin gluten", "Tiene opciones sin TACC"].includes(label), label);
    assert.match(item.querySelector(".nearby-distance").textContent, /^A .+ en línea recta$/);
  }
  assert.equal(items[0].querySelector(".pp-badge").textContent, "Espacio 100% sin gluten");
  assert.equal(items[1].querySelector(".pp-badge").textContent, "Tiene opciones sin TACC");
  assert.match(items[1].textContent, /Reportado por la comunidad/);
  assert.match(f.text(), /a menos de 5 km/);
  assert.equal(f.userLayer().size(), 2, "user marker + accuracy circle");
});

Deno.test("results follow the category and safety filters", async () => {
  const f = await located();
  f.click('[data-safety="gluten_free_100"]');
  await f.settle();
  const labels = f.places().map((b) => b.querySelector(".pp-badge").textContent);
  assert.ok(labels.length > 0 && labels.every((l) => l === "Espacio 100% sin gluten"));
  assert.match(f.text(), /con los filtros activos/);
});

Deno.test("nothing within 5 km offers to widen to 20 km and to choose a city", async () => {
  const f = await located({ position: { lat: -35.2, lng: -56.16, accuracy: 20 } });
  assert.equal(f.places().length, 0);
  assert.match(f.text(), /No encontramos lugares a menos de 5 km/);
  assert.ok(Boolean(f.action("city")));
  f.click(f.action("widen"));
  await f.settle();
  assert.deepEqual(f.places().map((b) => b.getAttribute("data-nearby-id")), ["far-17"]);
  assert.match(f.text(), /a menos de 20 km/);
  assert.equal(Boolean(f.action("widen")), false);
});

Deno.test("an approximate reading says so and only gives whole kilometres", async () => {
  const f = await located({ position: { ...USER, accuracy: 3000 } });
  assert.match(f.text(), /Tu ubicación es aproximada \(unos 3 km\)/);
  for (const item of f.places()) assert.match(item.querySelector(".nearby-distance").textContent, /^A unos \d+ km en línea recta$/);
});

Deno.test("privacy: the position never reaches a request, storage, an event or the DOM", async () => {
  const f = await located();
  f.click(f.places()[0]);
  f.click(f.action("widen"));
  await f.settle();
  const surfaces = [
    ...f.requests.map((r) => r.url + " " + r.body),
    ...f.storageWrites.map((w) => w.k + "=" + w.v),
    ...f.events.map((e) => e.type + " " + e.detail),
    f.document.documentElement.outerHTML,
  ];
  for (const surface of surfaces) for (const pattern of LEAK) assert.ok(!pattern.test(surface), "leak: " + pattern);
  assert.equal(f.storageWrites.length, 0, "map.js writes nothing to storage");
});

Deno.test("privacy: a chat message sent after locating carries no position", async () => {
  const f = await located();
  await f.loadChat();
  f.click("#chat-fab");
  f.tick(5000);
  const input = f.document.getElementById("chat-input");
  input.value = "¿Qué lugares hay cerca?";
  input.dispatchEvent(new f.window.Event("input", { bubbles: true }));
  f.document.getElementById("chat-form").dispatchEvent(new f.window.Event("submit", { bubbles: true, cancelable: true }));
  await f.settle();
  const chat = f.requests.filter((r) => r.url.includes("functions/v1/chat"));
  assert.equal(chat.length, 1, "the chat request was sent");
  for (const pattern of LEAK) assert.ok(!pattern.test(chat[0].body), "leak in chat body: " + pattern);
  assert.ok(!/lat|lng|latitude|longitude|accuracy|distance|distancia/i.test(chat[0].body));
  for (const w of f.storageWrites) for (const pattern of LEAK) assert.ok(!pattern.test(w.v));
});

Deno.test("a second tap within 60 s reuses the reading; after 60 s it reads again without re-explaining", async () => {
  const f = await located();
  f.tick(30_000);
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.geoCalls.get, 1);
  assert.equal(f.places().length, 10);
  f.tick(31_000);
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.geoCalls.get, 2);
  assert.match(f.text(), /Buscando tu ubicación/);
  assert.equal(f.userLayer().size(), 0, "the old marker is gone while reading again");
});

Deno.test("hiding the page drops the position, the marker and the list; a late answer is ignored", async () => {
  const f = await located();
  f.hide();
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.userLayer().size(), 0);
  f.show();
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.geoCalls.get, 2, "a new tap reads again");
  f.hide();
  await f.grant();
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.userLayer().size(), 0);
});

Deno.test("an answer that arrives while the page was already hidden is dropped, not left «finding»", async () => {
  const f = await fixture();
  f.click("#nearby-button");
  await f.settle();
  f.click(f.action("locate"));
  Object.defineProperty(f.document, "visibilityState", { get: () => "hidden", configurable: true });
  await f.grant();
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.userLayer().size(), 0);
  assert.equal(Boolean(f.document.querySelector(".pp-distance")), false);
});

Deno.test("pagehide drops the position too", async () => {
  const f = await located();
  f.windowListeners.pagehide.forEach((fn) => fn());
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.userLayer().size(), 0);
});

Deno.test("«Quitar mi ubicación» drops it, its distances, and returns focus to the button", async () => {
  const f = await located();
  f.click(f.places()[0]);
  assert.equal(Boolean(f.document.querySelector(".pp-distance")), true);
  f.click(f.action("clear"));
  assert.equal(Boolean(f.document.querySelector(".pp-distance")), false);
  assert.equal(f.nearby().hidden, true);
  assert.equal(f.userLayer().size(), 0);
  assert.equal(f.document.activeElement?.id, "nearby-button");
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.geoCalls.get, 2);
});

Deno.test("denied permission explains and offers a city; the map keeps working", async () => {
  const f = await fixture();
  f.click("#nearby-button");
  await f.settle();
  f.click(f.action("locate"));
  await f.fail(1);
  assert.match(f.text(), /No tenemos permiso para usar tu ubicación/);
  assert.equal(Boolean(f.action("locate")), false);
  f.click(f.action("city"));
  assert.equal(f.document.getElementById("explorer-filters").open, true);
  assert.equal(f.document.activeElement?.id, "city-select");
  assert.ok(f.document.querySelectorAll(".nearby-place").length === 0);
});

Deno.test("a timeout or unavailable position offers to try again", async () => {
  const f = await fixture();
  f.click("#nearby-button");
  await f.settle();
  f.click(f.action("locate"));
  await f.fail(3);
  assert.match(f.text(), /No pudimos obtener tu ubicación/);
  f.click(f.action("locate"));
  assert.equal(f.geoCalls.get, 2);
});

Deno.test("an already granted permission skips the explanation", async () => {
  const f = await fixture({ permission: "granted" });
  f.click("#nearby-button");
  await f.settle();
  assert.equal(f.geoCalls.get, 1);
  assert.match(f.text(), /Buscando tu ubicación/);
});

Deno.test("without a secure context or geolocation it offers a city and reads nothing", async () => {
  for (const options of [{ secure: false }, { withGeolocation: false }]) {
    const f = await fixture(options);
    f.click("#nearby-button");
    await f.settle();
    assert.match(f.text(), /Este navegador no puede darnos tu ubicación/);
    assert.equal(f.geoCalls.get, 0);
  }
});

Deno.test("a place in the list opens its detail with the straight-line distance, and stays open", async () => {
  const f = await located();
  f.click(f.places()[3]);
  const panel = f.document.getElementById("place-panel");
  assert.equal(panel.getAttribute("aria-hidden"), "false");
  assert.match(f.document.querySelector(".pp-distance").textContent, /^A .+ en línea recta$/);
  assert.match(f.document.querySelector(".pp-title").textContent, /Near 03/);
});

Deno.test("English: labels and the straight-line wording switch with the page language", async () => {
  const f = await located();
  f.document.documentElement.setAttribute("lang", "en");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang", { detail: "en" }));
  const first = f.places()[0];
  assert.match(first.querySelector(".nearby-distance").textContent, /away in a straight line$/);
  assert.equal(first.querySelector(".pp-badge").textContent, "100% gluten-free venue");
  assert.match(f.text(), /Near me/);
});

Deno.test("the chat shortcut only opens the map flow: no model call, no reading before the explanation", async () => {
  const f = await fixture();
  await f.loadChat();
  const shortcut = f.document.querySelector('[data-chat-action="nearby"]');
  assert.ok(Boolean(shortcut));
  f.click(shortcut);
  await f.settle();
  assert.match(f.text(), /una sola vez/);
  assert.equal(f.geoCalls.get, 0);
  assert.equal(f.requests.filter((r) => r.url.includes("functions/v1/chat")).length, 0);
});

Deno.test("static guard: no stored, watched or sent location anywhere in the frontend", async () => {
  const map = await Deno.readTextFile("js/map.js");
  const geo = await Deno.readTextFile("js/geo.js");
  for (const source of [map, geo]) {
    assert.ok(!/watchPosition|localStorage|sessionStorage|indexedDB/.test(source));
  }
  assert.equal((map.match(/getCurrentPosition/g) || []).length, 1);
  for await (const entry of Deno.readDir("js")) {
    if (!entry.name.endsWith(".js") || entry.name === "map.js") continue;
    const source = await Deno.readTextFile(`js/${entry.name}`);
    assert.ok(!/geolocation|getCurrentPosition|watchPosition/.test(source), `js/${entry.name} touches geolocation`);
  }
  const sw = await Deno.readTextFile("service-worker.js");
  assert.ok(sw.includes('"js/geo.js"'));
});
