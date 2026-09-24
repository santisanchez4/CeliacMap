// Public opinions: the optional name in Form B and the "La voz de la comunidad" section.
// No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_opinions.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

const PLACE = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10";

async function page(scripts, respond) {
  const html = await Deno.readTextFile("index.html");
  const { window, document } = parseHTML(html);
  const browser = { CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture-anon" } };
  const calls = [];
  let now = 1_700_000_000_000; // realistic epoch: a tiny value trips the 60 s cooldown
  const context = {
    window: browser, document, setTimeout, clearTimeout, CustomEvent: window.CustomEvent,
    Date: { now: () => (now += 5000) },
    fetch: async (url, init = {}) => {
      calls.push({ url: String(url), init, body: init.body ? JSON.parse(init.body) : null });
      return respond ? respond(String(url)) : { ok: true };
    },
  };
  for (const file of scripts) vm.runInNewContext(await Deno.readTextFile(file), context);
  await new Promise((r) => setTimeout(r, 0));
  return { window, document, browser, calls };
}

const setType = (f, type) => {
  const radios = [...f.document.querySelectorAll('input[name="rp-type"]')];
  for (const r of radios) r.checked = r.value === type;
  radios.find((r) => r.value === type).dispatchEvent(new f.window.Event("change", { bubbles: true }));
};

async function submitReport({ type = "positive", author, switchTo } = {}) {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  d.getElementById("rp-place-id").value = PLACE;
  d.getElementById("rp-description").value = "Muy buena atención y opciones para celíacos";
  setType(f, type);
  if (author !== undefined) d.getElementById("rp-author").value = author;
  if (switchTo) setType(f, switchTo);
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  return { f, sent: f.calls.filter((c) => c.url.endsWith("/place_reports")).map((c) => c.body) };
}

/* ------------------------------- Form B -------------------------------- */

Deno.test("form B: the name field sits inside #rp-details, capped at 40, never autofilled", async () => {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const input = f.document.getElementById("rp-author");
  assert.ok(input, "#rp-author missing");
  assert.ok(f.document.getElementById("rp-details").contains(input));
  assert.equal(input.getAttribute("maxlength"), "40");
  assert.equal(input.getAttribute("autocomplete"), "off");
  assert.equal(f.document.getElementById("rp-author-notice-negative").hasAttribute("hidden"), true);
  assert.equal(f.document.getElementById("rp-author-notice-positive").hasAttribute("hidden"), false);
});

Deno.test("form B: a positive recommendation sends the trimmed name", async () => {
  const { sent } = await submitReport({ author: "  Ana  " });
  assert.equal(sent[0].author_name, "Ana");
});

Deno.test("form B: without a name the payload is exactly today's (no author_name key)", async () => {
  const { sent } = await submitReport({});
  assert.deepEqual(Object.keys(sent[0]).sort(), ["description", "place_id", "report_type"]);
});

Deno.test("form B: a name of only spaces is not sent", async () => {
  const { sent } = await submitReport({ author: "     " });
  assert.equal("author_name" in sent[0], false);
});

Deno.test("form B: a name is cut at 40 characters", async () => {
  const { sent } = await submitReport({ author: "x".repeat(60) });
  assert.equal(sent[0].author_name.length, 40);
});

Deno.test("form B: a report hides the name field, shows its own notice and never sends a name", async () => {
  const { f, sent } = await submitReport({ author: "Ana", switchTo: "negative" });
  const d = f.document;
  assert.equal(d.getElementById("rp-author-field").hidden, true);
  assert.equal(d.getElementById("rp-author-notice-negative").hidden, false);
  assert.equal(sent[0].report_type, "negative");
  assert.equal("author_name" in sent[0], false, "a typed name must not survive switching to 'Reportar'");
});

Deno.test("form B: after SENDING a report the name field and notices follow the type again", async () => {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  const pos = d.getElementById("rp-type-positive");
  const neg = d.getElementById("rp-type-negative");
  // linkedom has no radio-group reset: emulate a browser's form.reset() (re-selects "Recomendar", no change event)
  d.getElementById("report-form").reset = () => { pos.checked = true; neg.checked = false; d.getElementById("rp-author").value = ""; };
  d.getElementById("rp-place-id").value = PLACE;
  d.getElementById("rp-description").value = "Me contaminaron la comida";
  setType(f, "negative");
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(pos.checked, true);
  assert.equal(d.getElementById("rp-author-field").hidden, false);
  assert.equal(d.getElementById("rp-author-notice-negative").hidden, true);
});

Deno.test("form B: every new data-i18n key has an EN entry", async () => {
  const main = await Deno.readTextFile("js/main.js");
  const en = new Set([...main.matchAll(/"([\w.]+)":\s*"/g)].map((m) => m[1]));
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const keys = [...document.querySelectorAll("#rp-details [data-i18n], #rp-details [data-i18n-placeholder]")]
    .map((n) => n.getAttribute("data-i18n") || n.getAttribute("data-i18n-placeholder"));
  assert.deepEqual(keys.filter((k) => !en.has(k)), []);
});

/* ---------------------------- Opinions section ---------------------------- */

const rowsOf = (n, extra = {}) => Array.from({ length: n }, (_, i) => ({
  id: `id-${i}`, description: `Comentario ${i}`, author_name: `Persona ${i}`,
  place_id: `place-${i}`, place_name: `Lugar ${i}`, city: "Rosario", country: "Argentina", ...extra,
}));
const okJson = (rows) => ({ ok: true, json: async () => rows });
const cards = (f) => [...f.document.querySelectorAll("#opinions-grid .review:not(.review-cta)")];
const cta = (f) => f.document.querySelector("#opinions-grid .review-cta");

async function opinions(rows, opts = {}) {
  const f = await page(["js/opinions.js"], () => (rows instanceof Error ? Promise.reject(rows) : okJson(rows)));
  if (opts.lang) {
    f.document.documentElement.setAttribute("lang", opts.lang);
    f.document.dispatchEvent(new f.window.CustomEvent("celiacmap:lang", { detail: opts.lang }));
  }
  return f;
}

Deno.test("#reviews: the three invented testimonials are gone and the grid is there", async () => {
  const html = await Deno.readTextFile("index.html");
  const { document } = parseHTML(html);
  const section = document.getElementById("reviews");
  assert.ok(section.querySelector("#opinions-grid"));
  for (const invented of ["María L.", "Joaquín R.", "Valentina S.", "Celíaca hace 8 años"]) {
    assert.equal(section.textContent.includes(invented), false, invented);
  }
  assert.ok(html.includes('<script src="js/opinions.js"></script>'));
  const main = await Deno.readTextFile("js/main.js");
  assert.equal(/"reviews\.r[123]\./.test(main), false, "orphaned EN keys for the removed testimonials");
});

Deno.test("#reviews: every data-i18n key has an EN entry", async () => {
  const main = await Deno.readTextFile("js/main.js");
  const en = new Set([...main.matchAll(/"([\w.]+)":\s*"/g)].map((m) => m[1]));
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const keys = [...document.querySelectorAll("#reviews [data-i18n]")].map((n) => n.getAttribute("data-i18n"));
  assert.deepEqual(keys.filter((k) => !en.has(k)), []);
});

Deno.test("opinions: reads the public view with the anon key, newest first, at most 6", async () => {
  const f = await opinions(rowsOf(1));
  const call = f.calls[0];
  assert.ok(call.url.startsWith("https://fixture.invalid/rest/v1/community_opinions?select="), call.url);
  assert.ok(call.url.includes("order=published_at.desc"));
  assert.ok(call.url.includes("limit=6"));
  assert.equal(call.init.headers.apikey, "fixture-anon");
  assert.equal(call.url.includes("place_reports"), false, "must never read the closed table");
});

Deno.test("opinions: a name is shown with its initial, no name means Anónimo with the neutral avatar", async () => {
  const f = await opinions([
    { ...rowsOf(1)[0], author_name: "ana" },
    { ...rowsOf(1)[0], id: "b", author_name: null },
    { ...rowsOf(1)[0], id: "c", author_name: "   " },
  ]);
  const [a, b, c] = cards(f);
  assert.equal(a.querySelector("strong").textContent, "ana");
  assert.equal(a.querySelector(".avatar").textContent, "A");
  assert.equal(a.querySelector(".avatar").classList.contains("avatar--anon"), false);
  for (const anon of [b, c]) {
    assert.equal(anon.querySelector("strong").textContent, "Anónimo");
    assert.equal(anon.querySelector(".avatar").classList.contains("avatar--anon"), true);
    assert.equal(anon.querySelector(".avatar").textContent, "");
  }
});

Deno.test("opinions: each card names the place and its city", async () => {
  const f = await opinions(rowsOf(1));
  assert.equal(cards(f)[0].querySelector(".review-place").textContent, "Sobre Lugar 0 · Rosario");
});

Deno.test("opinions: three or more show only opinions; fewer add the invitation card", async () => {
  assert.equal(cta(await opinions(rowsOf(3))), null);
  const two = await opinions(rowsOf(2));
  assert.equal(cards(two).length, 2);
  assert.ok(cta(two));
  assert.equal(cta(two).querySelector("a").getAttribute("href"), "#report-form");
});

Deno.test("opinions: none published -> only the invitation card, with the empty-state copy", async () => {
  const f = await opinions([]);
  assert.equal(cards(f).length, 0);
  assert.ok(cta(f).textContent.includes("Todavía no hay comentarios publicados"));
});

Deno.test("opinions: a failed load shows the empty state and does not throw", async () => {
  const f = await opinions(new Error("network down"));
  assert.equal(cards(f).length, 0);
  assert.ok(cta(f));
});

Deno.test("opinions: a comment with HTML is text, never markup", async () => {
  const evil = `<img src=x onerror="alert(1)"><script>alert(2)</script>`;
  const f = await opinions([{ ...rowsOf(1)[0], description: evil, author_name: `<b>Ana</b>` }]);
  const card = cards(f)[0];
  assert.equal(card.querySelector("img"), null);
  assert.equal(card.querySelector("script"), null);
  assert.equal(card.querySelector("b"), null);
  assert.ok(card.querySelector(".review-text").textContent.includes("<img src=x"));
  assert.equal(card.querySelector("strong").textContent, "<b>Ana</b>");
});

Deno.test("opinions: a long comment is cut at a whole word with an ellipsis; a short one is untouched", async () => {
  const long = "palabra ".repeat(250).trim();
  const f = await opinions([{ ...rowsOf(1)[0], description: long }, { ...rowsOf(1)[0], id: "s", description: "Corto y bueno" }]);
  const [big, small] = cards(f).map((c) => c.querySelector(".review-text").textContent);
  const inner = big.slice(1, -1); // the curly quotes
  assert.ok(inner.endsWith("…"));
  assert.ok(inner.length <= 281, String(inner.length));
  assert.equal(inner.slice(0, -1).endsWith("palabra"), true, "cut mid-word");
  assert.equal(small, "“Corto y bueno”");
});

Deno.test("opinions: dynamic cards never use .reveal (the observer would leave them invisible)", async () => {
  const f = await opinions(rowsOf(2));
  assert.equal(f.document.querySelectorAll("#opinions-grid .reveal").length, 0);
});

Deno.test("opinions: switching to English redraws the labels", async () => {
  const f = await opinions([{ ...rowsOf(1)[0], author_name: null }], { lang: "en" });
  assert.equal(cards(f)[0].querySelector("strong").textContent, "Anonymous");
  assert.equal(cards(f)[0].querySelector(".review-place").textContent, "About Lugar 0 · Rosario");
  assert.ok(cta(f).textContent.includes("Tell us about your experience"));
});

Deno.test("opinions: clicking the place opens it on the map through the shared event", async () => {
  const f = await opinions(rowsOf(1));
  let detail = null;
  f.document.addEventListener("celiacmap:open-place", (e) => { detail = e.detail; });
  cards(f)[0].querySelector(".review-place").dispatchEvent(new f.window.Event("click", { bubbles: true }));
  assert.deepEqual(JSON.parse(JSON.stringify(detail)), { id: "place-0" });
});

Deno.test("opinions: rows missing a place or a text are ignored", async () => {
  const f = await opinions([{ ...rowsOf(1)[0], place_name: null }, { ...rowsOf(1)[0], description: "" }, ...rowsOf(1)]);
  assert.equal(cards(f).length, 1);
});

Deno.test("form B: `.field { display: flex }` must not beat [hidden], or the name field stays visible in 'Reportar' mode", async () => {
  // Found in the browser, invisible to a DOM emulation: the hidden attribute is only a UA style (display: none),
  // so any author rule that sets `display` wins over it.
  const css = await Deno.readTextFile("css/styles.css");
  assert.ok(/\.field\[hidden\]\s*\{\s*display:\s*none/.test(css));
});
