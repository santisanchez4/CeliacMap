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
  window.HTMLElement.prototype.getBoundingClientRect = function () { return { top: 100, bottom: 600, height: 500 }; };
  Object.defineProperty(document.getElementById("place-panel"), "offsetWidth", { value: 360 });
  Object.defineProperty(document.getElementById("place-panel"), "offsetHeight", { value: 240 });
  const cities = document.getElementById("city-select");
  Object.defineProperty(cities, "value", { writable: true, value: "all" });
  const levels = ["gluten_free_100", "celiac_friendly", "options_available"];
  const rows = Array.from({ length: 12 }, (_, i) => ({
    id: "place-" + i, name: "Place " + String(i).padStart(2, "0"), city: "Montevideo",
    category: i === 0 ? "cafe" : "restaurant", safety_level: levels[i % 3], lat: -34.9, lng: -56.1,
    // The fixture clock starts at epoch + 10 s: place-3 was reported "now", place-6 over 30 days ago.
    community_warning_at: i === 3 ? "1970-01-01T00:00:05Z" : i === 6 ? "1969-11-01T00:00:00Z" : null,
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
    flyToBounds(bounds, options) { this.lastFrame = { bounds, options }; },
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
  const viewportListeners = {};
  const browser = {
    innerHeight: 700,
    CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture" },
    matchMedia: query => ({ matches: mobile && query.includes("max-width") }), addEventListener() {},
    scrollX: 0, scrollY: 840,
    scrollTo(x, y) { this.scrollX = x; this.scrollY = y; },
    visualViewport: { height: 500, offsetTop: 0, addEventListener(name, fn) { viewportListeners[name] = fn; } },
  };
  let now = 10000;
  const context = {
    window: browser, document, L, navigator: {}, CustomEvent: window.CustomEvent,
    Date: { now: () => (now += 3000), parse: Date.parse },
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
  return { document, window, browser, map, viewportListeners, click, markers, layers, mutations: () => mutations,
    loadChat: async () => vm.runInNewContext(await Deno.readTextFile("js/chat.js"), context),
    loadOpinions: async rows => {
      context.fetch = async () => ({ ok: true, json: async () => rows });
      vm.runInNewContext(await Deno.readTextFile("js/opinions.js"), context);
      await new Promise(resolve => setTimeout(resolve, 0));
    } };
}

Deno.test("selected pin is centered in the map area left of the desktop card", async () => {
  const f = await fixture();
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  const options = f.map.lastFrame.options;
  assert.equal(options.maxZoom, 16);
  // Leaflet's asymmetric padding moves the pin 180px left of map center.
  assert.equal((options.paddingBottomRight[0] - options.paddingTopLeft[0]) / 2, 180);
  assert.equal(options.paddingBottomRight[1], options.paddingTopLeft[1]);
});

Deno.test("mobile selection reserves only the bottom sheet overlap with the map", async () => {
  const f = await fixture(true);
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  const options = f.map.lastFrame.options;
  assert.equal(options.paddingBottomRight[0], options.paddingTopLeft[0]);
  // Map ends at 600; sheet starts at 700 - 240 = 460. Overlap is 140.
  assert.equal(options.paddingBottomRight[1] - options.paddingTopLeft[1], 140);
});

Deno.test("selecting a place leaves detail open and does not rebuild markers", async () => {
  const f = await fixture();
  const before = f.mutations();
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  assert.equal(f.document.getElementById("place-panel").getAttribute("aria-hidden"), "false");
  assert.equal(f.mutations(), before);
});

// Selecting a marker swaps its icon (setIcon), which replaces the very node the
// person clicked. By the time that click bubbles to document its target is
// detached, and the "click outside closes the panel" handler must not read that
// as an outside click (it closed the detail the instant it opened).
Deno.test("a marker click whose icon is replaced while handling it keeps the detail open", async () => {
  const f = await fixture();
  const mapEl = f.document.getElementById("cm-map");
  const icon = f.document.createElement("span");
  mapEl.appendChild(icon);
  mapEl.addEventListener("click", () => {
    f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
    icon.remove();
  });
  icon.dispatchEvent(new f.window.Event("click", { bubbles: true }));
  const panel = f.document.getElementById("place-panel");
  assert.equal(panel.getAttribute("aria-hidden"), "false");
  assert.ok(panel.classList.contains("is-open"));
});

Deno.test("a click outside the map and the panel still closes the detail", async () => {
  const f = await fixture();
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  const panel = f.document.getElementById("place-panel");
  assert.ok(panel.classList.contains("is-open"));
  f.click("#map .section-title");
  assert.equal(panel.getAttribute("aria-hidden"), "true");
});

// Two public levels: only a dedicated venue is "100% gluten-free"; celiac_friendly
// and options_available are both "has options" (the DB still stores three).
Deno.test("safety filters and legend expose two levels", async () => {
  const f = await fixture();
  const chips = Array.from(f.document.querySelectorAll(".safety-chip")).map(c => c.getAttribute("data-safety"));
  assert.deepEqual(chips, ["all", "gluten_free_100", "options_available"]);
  const legend = Array.from(f.document.querySelectorAll(".map-legend li span:last-child")).map(s => s.textContent);
  assert.deepEqual(legend, [
    "Espacio 100% sin gluten", "Tiene opciones sin TACC", "Reportado por la comunidad: consultá antes de ir",
  ]);
  assert.equal(f.document.querySelector('[data-safety="options_available"]').textContent, "Tiene opciones sin TACC");
});

Deno.test("the map legend is followed by the 'levels are an estimate' note, in both languages", async () => {
  const f = await fixture();
  const legend = f.document.querySelector(".map-legend");
  const note = legend.nextElementSibling;
  assert.ok(note && note.classList.contains("map-disclaimer"));
  assert.match(note.textContent, /estimación .* no una garantía médica/);
  assert.equal(note.getAttribute("data-i18n"), "map.disclaimer");
  assert.match(await Deno.readTextFile("js/main.js"), /"map\.disclaimer": "Levels are an estimate .* not a medical guarantee/);
});

Deno.test("the options filter also shows celiac_friendly places; the 100% filter shows only dedicated ones", async () => {
  const f = await fixture();
  const shown = () => f.markers.map((m, i) => f.layers.has(m) ? i : -1).filter(i => i >= 0);
  f.click('[data-safety="options_available"]');
  assert.deepEqual(shown(), [1, 2, 4, 5, 7, 8, 10, 11]);     // celiac_friendly + options_available
  f.click('[data-safety="gluten_free_100"]');
  assert.deepEqual(shown(), [0, 3, 6, 9]);                    // dedicated only
  f.click('[data-safety="all"]');
  assert.equal(shown().length, 12);
});

Deno.test("markers of celiac_friendly and unknown levels are never drawn as 100% gluten-free", async () => {
  const f = await fixture();
  const cls = m => m.options.icon.html;
  assert.ok(cls(f.markers[0]).includes("cm-marker--dedicated"));
  assert.ok(cls(f.markers[1]).includes("cm-marker--options"));   // celiac_friendly
  assert.ok(cls(f.markers[2]).includes("cm-marker--options"));   // options_available
  assert.equal(cls(f.markers[1]).includes("friendly"), false);
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

Deno.test("hero opens the page, the map follows it, and the map's side card is only the community Top 3", async () => {
  const f = await fixture();
  const sections = Array.from(f.document.querySelectorAll("main > section")).map(s => s.id);
  assert.deepEqual(sections.slice(0, 2), ["hero", "map"]);
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

// Same bug class as the marker click and the chat links: the click that opens a place from a
// "La voz de la comunidad" card bubbles to the document, where "a click outside the map closes the
// detail" ran right after the panel opened. Found live: the map flew to the place but the detail was shut.
Deno.test("real click on a community-opinion place link opens the map detail and keeps it open", async () => {
  const f = await fixture();
  await f.loadOpinions([{
    id: "o1", description: "Muy rico todo", author_name: null,
    place_id: "place-3", place_name: "Place 03", city: "Montevideo", country: "Uruguay",
  }]);
  f.click("#opinions-grid .review-place");
  const panel = f.document.getElementById("place-panel");
  assert.equal(panel.getAttribute("aria-hidden"), "false");
  assert.ok(panel.classList.contains("is-open"));
});

// Opening a place from a link elsewhere on the page (chat, community opinions) used to scroll to the
// section HEADING, leaving the map and its detail card half below the fold on a laptop. It must bring the
// map itself into view.
Deno.test("opening a place scrolls the map itself into view, not the section heading", async () => {
  const f = await fixture();
  const targets = [];
  f.window.HTMLElement.prototype.scrollIntoView = function () { targets.push(this.id || this.className); };
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  assert.ok(targets.includes("map-wrap"), "scrolled: " + targets.join(", "));
  assert.equal(targets.includes("map"), false, "must not scroll to the section heading");
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

Deno.test("ranking rows label celiac_friendly as options, in both languages", async () => {
  const f = await rankingFixture({ votes: { Argentina: placesFor("AR", 1) } });
  const badge = () => f.document.querySelector("#ranking-list .pp-badge");
  assert.equal(badge().textContent, "Tiene opciones sin TACC");
  assert.ok(badge().classList.contains("pp-badge--options"));
  f.document.documentElement.setAttribute("lang", "en");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang"));
  assert.equal(badge().textContent, "Has gluten-free options");
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
  assert.equal(f.document.body.style.getPropertyValue("--chat-scroll-top"), "-840px");
  assert.equal(f.document.documentElement.classList.contains("chat-mobile-open"), true);
  f.browser.scrollY = 0;
  f.browser.visualViewport.height = 280;
  f.browser.visualViewport.offsetTop = 12;
  f.viewportListeners.resize();
  assert.equal(panel.style.getPropertyValue("--chat-viewport-height"), "280px");
  assert.equal(panel.style.getPropertyValue("--chat-viewport-top"), "12px");
  assert.equal(f.document.body.style.getPropertyValue("--chat-scroll-top"), "-840px");
  assert.ok(f.document.querySelector("#chat-log .chat-disclaimers"));
  f.click("#chat-panel-close");
  assert.equal(f.browser.scrollY, 840);
  assert.equal(f.document.documentElement.classList.contains("chat-mobile-open"), false);
  assert.equal(f.document.querySelector("main").hasAttribute("inert"), false);
  assert.equal(f.document.body.classList.contains("chat-mobile-open"), false);
});

// Audit plan step 7: a recent negative report keeps the place on the map with a red "!" pin and
// a notice in the detail; the level badge still says 100% / options. Older than 30 days: gone.
Deno.test("a recently reported place gets the warning pin and notice; an old report does not", async () => {
  const f = await fixture();
  const cls = m => m.options.icon.html;
  assert.ok(cls(f.markers[3]).includes("cm-marker--warning"));
  assert.ok(cls(f.markers[3]).includes("cm-marker--dedicated"));
  assert.equal(cls(f.markers[6]).includes("cm-marker--warning"), false);
  assert.equal(cls(f.markers[0]).includes("cm-marker--warning"), false);

  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-3" } }));
  const body = f.document.getElementById("place-panel-body");
  assert.match(body.textContent, /Reportado por la comunidad/);
  assert.match(body.textContent, /Espacio 100% sin gluten/);
  assert.ok(cls(f.markers[3]).includes("cm-marker--warning"), "the selected pin keeps the warning");

  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-6" } }));
  assert.equal(/Reportado por la comunidad/.test(body.textContent), false);
});

Deno.test("the map reads community_warning_at, and the warning pin is styled", async () => {
  assert.match(await Deno.readTextFile("js/map.js"), /community_warning_at/);
  const css = await Deno.readTextFile("css/styles.css");
  assert.match(css, /\.cm-marker\.cm-marker--warning \{/);
  assert.match(css, /\.pp-warning \{/);
});

// Audit plan step 5: the detail explains what each label means.
Deno.test("the place detail explains the level label", async () => {
  const f = await fixture();
  const body = f.document.getElementById("place-panel-body");
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-0" } }));
  assert.match(body.textContent, /se cocinan y venden solo productos aptos para celíacos/);
  f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:open-place", { detail: { id: "place-1" } }));
  assert.match(body.textContent, /puede que también cocine con gluten/);
});
