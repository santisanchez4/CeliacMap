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
    divIcon: x => x, layerGroup: () => group,
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

Deno.test("selecting a place leaves detail open and does not rebuild markers", async () => {
  const f = await fixture();
  const before = f.mutations();
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  assert.equal(f.document.getElementById("place-panel").getAttribute("aria-hidden"), "false");
  assert.equal(f.mutations(), before);
});

Deno.test("language changes translate the explorer without rebuilding map layers", async () => {
  const f = await fixture();
  const before = f.mutations();
  f.document.documentElement.setAttribute("lang", "en");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang"));
  assert.equal(f.document.querySelector('[data-safety="all"]').textContent, "All levels");
  assert.equal(f.document.getElementById("apply-filters").textContent, "View results");
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

Deno.test("map is first in document order and its side card is only the community Top 3", async () => {
  const f = await fixture();
  assert.equal(f.document.querySelector("main > section").id, "map");
  const side = f.document.querySelectorAll(".map-layout > aside");
  assert.equal(side.length, 1);
  assert.equal(side[0].id, "map-top3");
  assert.equal(f.document.getElementById("place-results"), null);
  assert.equal(f.document.getElementById("results-toggle"), null);
  const countries = Array.from(side[0].querySelectorAll("[data-country]")).map(b => b.getAttribute("data-country"));
  assert.deepEqual(countries, ["Argentina", "Uruguay"]);
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

Deno.test("chat opens with only its intro: no suggested prompts", async () => {
  const f = await fixture();
  await f.loadChat();
  f.click("#chat-fab");
  const log = f.document.getElementById("chat-log");
  assert.equal(log.children.length, 1);
  assert.ok(log.children[0].classList.contains("chat-msg--intro"));
  assert.equal(log.querySelectorAll("button").length, 0);
});

async function rankingFixture({ votes, fail = false }) {
  const html = await Deno.readTextFile("index.html");
  const source = await Deno.readTextFile("js/ranking.js");
  const { window, document } = parseHTML(html);
  const store = new Map();
  const urls = [];
  const context = {
    window: { CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture" } },
    document, CustomEvent: window.CustomEvent, Date, setTimeout, clearTimeout,
    localStorage: { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) },
    fetch: async url => {
      urls.push(String(url));
      if (fail) return { ok: false, status: 500, json: async () => ({}) };
      const country = decodeURIComponent(String(url).match(/country=eq\.([^&]+)/)[1]);
      return { ok: true, json: async () => votes[country] || [] };
    },
  };
  vm.runInNewContext(source, context);
  const settle = () => new Promise(resolve => setTimeout(resolve, 0));
  await settle();
  return {
    document, window, urls,
    async click(selector) {
      document.querySelector(selector).dispatchEvent(new window.Event("click", { bubbles: true }));
      await settle();
    },
    topNames: () => Array.from(document.querySelectorAll(".mt3-name")).map(n => n.textContent),
    cardHidden: () => document.getElementById("map-top3").hasAttribute("hidden"),
  };
}

const placesFor = (prefix, n) => Array.from({ length: n }, (_, i) => ({
  id: prefix + i, name: prefix + " " + i, city: "X", safety_level: "celiac_friendly", vote_count: n - i,
}));

Deno.test("Top 3 card lists the top three and its country tabs drive the full ranking too", async () => {
  const f = await rankingFixture({ votes: { Argentina: placesFor("AR", 5), Uruguay: placesFor("UY", 2) } });
  assert.equal(f.cardHidden(), false);
  assert.deepEqual(f.topNames(), ["AR 0", "AR 1", "AR 2"]);
  await f.click('.map-top3-tabs [data-country="Uruguay"]');
  assert.deepEqual(f.topNames(), ["UY 0", "UY 1"]);
  assert.equal(f.document.querySelectorAll("#ranking-list .ranking-item").length, 2);
  for (const sel of [".map-top3-tabs", ".ranking-tabs"]) {
    assert.ok(f.document.querySelector(sel + ' [data-country="Uruguay"]').classList.contains("chip-active"), sel);
    assert.equal(f.document.querySelector(sel + ' [data-country="Argentina"]').getAttribute("aria-pressed"), "false", sel);
  }
});

Deno.test("the section's country tabs also switch the Top 3 card", async () => {
  const f = await rankingFixture({ votes: { Argentina: placesFor("AR", 3), Uruguay: placesFor("UY", 3) } });
  await f.click('.ranking-tabs [data-country="Uruguay"]');
  assert.deepEqual(f.topNames(), ["UY 0", "UY 1", "UY 2"]);
  assert.ok(f.document.querySelector('.map-top3-tabs [data-country="Uruguay"]').classList.contains("chip-active"));
});

Deno.test("a country without votes keeps the Top 3 card and its tabs on screen", async () => {
  const f = await rankingFixture({ votes: { Argentina: placesFor("AR", 3), Uruguay: [] } });
  await f.click('.map-top3-tabs [data-country="Uruguay"]');
  assert.equal(f.cardHidden(), false);
  assert.equal(f.document.querySelectorAll(".map-top3-item").length, 0);
  assert.ok(f.document.querySelector(".map-top3-empty"));
  await f.click('.map-top3-tabs [data-country="Argentina"]');
  assert.deepEqual(f.topNames(), ["AR 0", "AR 1", "AR 2"]);
});

Deno.test("Top 3 card stays hidden when the ranking cannot load, even after a language change", async () => {
  const f = await rankingFixture({ votes: {}, fail: true });
  assert.equal(f.cardHidden(), true);
  f.document.documentElement.setAttribute("lang", "en");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang"));
  assert.equal(f.cardHidden(), true);
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
