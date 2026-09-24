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
