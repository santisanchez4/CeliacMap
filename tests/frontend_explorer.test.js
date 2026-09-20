// DOM-level regressions. No Supabase/LLM calls and no browser dependencies.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_explorer.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

async function fixture(mobile = false) {
  const html = await Deno.readTextFile("index.html");
  const source = await Deno.readTextFile("js/map.js");
  const { window, document } = parseHTML(html);
  window.HTMLElement.prototype.focus = function () { document.focused = this; };
  window.HTMLElement.prototype.getClientRects = function () { return this.closest("[hidden]") ? [] : [1]; };
  Object.defineProperty(document, "activeElement", { get: () => document.focused });
  window.HTMLElement.prototype.scrollIntoView = function () {};
  const cities = document.getElementById("city-select");
  Object.defineProperty(cities, "value", { writable: true, value: "all" });
  const rows = Array.from({ length: 12 }, (_, i) => ({
    id: "place-" + i, name: "Place " + String(i).padStart(2, "0"), city: "Montevideo",
    category: i === 0 ? "cafe" : "restaurant", safety_level: "gluten_free_100", lat: -34.9, lng: -56.1,
  }));
  const markers = [];
  let mutations = 0;
  const layers = new Set();
  const group = {
    addTo() { return this; }, hasLayer: m => layers.has(m),
    addLayer(m) { mutations++; layers.add(m); }, removeLayer(m) { mutations++; layers.delete(m); },
  };
  const map = {
    setView() { return this; }, on() {}, invalidateSize() {}, fitBounds() {}, flyTo() {},
    getCenter() { return [0, 0]; }, getZoom() { return 12; },
    scrollWheelZoom: { enable() {}, disable() {} },
  };
  const L = {
    map: () => map, tileLayer: () => ({ addTo() {} }), latLngBounds: () => ({}),
    divIcon: x => x, markerClusterGroup: () => group,
    featureGroup: () => ({ getBounds: () => ({ pad() { return {}; } }) }),
    marker(coords, options) {
      const m = { options, on() {}, getLatLng: () => coords, setIcon(icon) { this.options.icon = icon; } };
      markers.push(m); return m;
    },
  };
  const browser = {
    CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture" },
    matchMedia: query => ({ matches: mobile && query.includes("max-width") }), addEventListener() {},
    visualViewport: { height: 500, offsetTop: 0, addEventListener() {} },
  };
  let now = 10000;
  const context = {
    window: browser, document, L, navigator: {}, CustomEvent: window.CustomEvent,
    Date: { now: () => (now += 3000) },
    fetch: async url => ({ ok: true, json: async () => String(url).includes("functions/v1/chat")
      ? { reply: "Found a place", places: [rows[0]], pending_submission: null } : rows }),
    setTimeout, clearTimeout,
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setTimeout(resolve, 0));
  function click(selector) {
    const el = document.querySelector(selector);
    assert.ok(el, selector);
    el.dispatchEvent(new window.Event("click", { bubbles: true }));
    return el;
  }
  return { document, window, click, markers, layers, mutations: () => mutations,
    loadChat: async () => vm.runInNewContext(await Deno.readTextFile("js/chat.js"), context) };
}

Deno.test("result click leaves detail open and does not rebuild markers", async () => {
  const f = await fixture();
  const before = f.mutations();
  const button = f.click(".place-result");
  assert.equal(f.document.getElementById("place-panel").getAttribute("aria-hidden"), "false");
  assert.equal(button.getAttribute("aria-pressed"), "true");
  assert.equal(f.mutations(), before);
  assert.equal(button.isConnected, true);
});

Deno.test("pagination and language changes do not rebuild map layers", async () => {
  const f = await fixture();
  const before = f.mutations();
  f.click("#results-more");
  assert.equal(f.document.querySelectorAll(".place-result").length, 12);
  f.document.documentElement.setAttribute("lang", "en");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang"));
  assert.equal(f.document.getElementById("explorer-results-title").textContent, "Places found");
  assert.equal(f.mutations(), before);
});

Deno.test("chat selection clears conflicting filters and reveals its marker", async () => {
  const f = await fixture();
  f.click('[data-category="restaurant"]');
  assert.equal(f.layers.has(f.markers[0]), false);
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-0" } }));
  assert.equal(f.layers.has(f.markers[0]), true);
  assert.equal(f.document.querySelector('[data-category="all"]').getAttribute("aria-pressed"), "true");
  assert.equal(f.document.getElementById("place-panel").getAttribute("aria-hidden"), "false");
});

Deno.test("map is first in document order and mobile results can be closed", async () => {
  const f = await fixture();
  assert.equal(f.document.querySelector("main > section").id, "map");
  f.click("#results-toggle");
  assert.ok(f.document.getElementById("explorer-results").classList.contains("is-results-open"));
  f.click("#results-close");
  assert.equal(f.document.getElementById("results-toggle").getAttribute("aria-expanded"), "false");
});

Deno.test("autocomplete respects category filters", async () => {
  const f = await fixture();
  f.click('[data-category="restaurant"]');
  const input = f.document.getElementById("place-search");
  input.value = "Place";
  input.dispatchEvent(new f.window.Event("input"));
  assert.equal(f.document.getElementById("search-suggest").textContent.includes("Place 00"), false);
  await new Promise(resolve => setTimeout(resolve, 300));
});

Deno.test("real chat recommendation click keeps the map detail open", async () => {
  const f = await fixture();
  await f.loadChat();
  f.click("#chat-fab");
  f.document.getElementById("chat-input").value = "Find cafés";
  f.document.getElementById("chat-form").dispatchEvent(new f.window.Event("submit", { bubbles: true, cancelable: true }));
  await new Promise(resolve => setTimeout(resolve, 0));
  f.click(".chat-place-links button");
  assert.equal(f.document.getElementById("place-panel").getAttribute("aria-hidden"), "false");
});

Deno.test("mobile chat follows viewport, isolates background and opens without focusing input", async () => {
  const f = await fixture(true);
  await f.loadChat();
  f.click("#chat-fab");
  const panel = f.document.getElementById("chat-panel");
  assert.equal(panel.style.getPropertyValue("--chat-viewport-height"), "500px");
  assert.equal(f.document.activeElement.id, "chat-panel-close");
  assert.equal(f.document.querySelector("main").hasAttribute("inert"), true);
  f.click("#chat-panel-close");
  assert.equal(f.document.querySelector("main").hasAttribute("inert"), false);
  assert.equal(f.document.body.classList.contains("chat-mobile-open"), false);
});
