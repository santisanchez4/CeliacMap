// Kitchen block ("Sobre la cocina"): markup in both forms, behavior of js/kitchen.js, and
// the payloads js/suggest.js and js/report.js send. No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_kitchen.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

async function page(scripts = ["js/kitchen.js"]) {
  const html = await Deno.readTextFile("index.html");
  const { window, document } = parseHTML(html);
  const browser = { CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture" } };
  const bodies = [];
  // A realistic epoch: with a tiny value, `Date.now() - 0` is under the forms' 60 s cooldown.
  let now = 1_700_000_000_000;
  const context = {
    window: browser, document, setTimeout, clearTimeout,
    Date: { now: () => (now += 5000) },
    fetch: async (url, init) => { bodies.push({ url: String(url), body: JSON.parse(init.body) }); return { ok: true }; },
  };
  for (const file of scripts) vm.runInNewContext(await Deno.readTextFile(file), context);
  return { window, document, browser, bodies };
}

// linkedom does not implement radio-group exclusivity: emulate what a browser does natively.
function choose(f, name, value) {
  const radios = [...f.document.querySelectorAll(`input[name="${name}"]`)];
  for (const r of radios) r.checked = r.value === value;
  radios.find((r) => r.value === value).dispatchEvent(new f.window.Event("change", { bubbles: true }));
}

// read() builds its result inside the vm context (another realm): strict deepEqual compares prototypes,
// so compare a plain copy instead.
const plain = (x) => JSON.parse(JSON.stringify(x));

const PREFIXES = [["sg", "suggest-form"], ["rp", "report-form"]];

for (const [pfx, formId] of PREFIXES) {
  Deno.test(`#${pfx}-kitchen markup: a fieldset in #${formId}, three groups, "No sé" checked, question 2 hidden`, async () => {
    const f = await page();
    const root = f.document.getElementById(`${pfx}-kitchen`);
    assert.ok(root, "fieldset missing");
    assert.equal(root.tagName, "FIELDSET");
    assert.ok(f.document.getElementById(formId).contains(root));
    assert.ok(root.querySelector("legend"));
    for (const q of ["exclusive", "prep", "owner"]) {
      const radios = [...root.querySelectorAll(`input[data-kitchen-q="${q}"]`)];
      assert.ok(radios.length >= 3, `${q}: options`);
      assert.equal(radios.find((r) => r.value === "unknown").hasAttribute("checked"), true, `${q}: default is "No sé"`);
      assert.equal(new Set(radios.map((r) => r.name)).size, 1, `${q}: one radio group`);
    }
    assert.equal(root.querySelector("[data-kitchen-prep]").hasAttribute("hidden"), true);
  });
}

Deno.test("read(): nothing answered -> {}", async () => {
  const f = await page();
  const kitchen = f.browser.CeliacKitchen.attach(f.document.getElementById("sg-kitchen"));
  assert.deepEqual(plain(kitchen.read()), {});
});

Deno.test("read(): not exclusive shows question 2 and reports every answered key", async () => {
  const f = await page();
  const root = f.document.getElementById("sg-kitchen");
  const kitchen = f.browser.CeliacKitchen.attach(root);
  choose(f, "sg-kitchen-exclusive", "no");
  assert.equal(root.querySelector("[data-kitchen-prep]").hidden, false);
  choose(f, "sg-kitchen-prep", "separate_prep");
  choose(f, "sg-kitchen-owner", "yes");
  assert.deepEqual(plain(kitchen.read()), { kitchen_exclusive: false, celiac_prep: "separate_prep", owner_celiac: true });
});

Deno.test("read(): exclusive kitchen never sends celiac_prep, even if it was chosen before", async () => {
  const f = await page();
  const root = f.document.getElementById("sg-kitchen");
  const kitchen = f.browser.CeliacKitchen.attach(root);
  choose(f, "sg-kitchen-exclusive", "no");
  choose(f, "sg-kitchen-prep", "shared_kitchen");
  choose(f, "sg-kitchen-exclusive", "yes");
  assert.equal(root.querySelector("[data-kitchen-prep]").hidden, true);
  assert.deepEqual(plain(kitchen.read()), { kitchen_exclusive: true });
});

Deno.test("read(): 'No' for the owner is a real answer (false), not 'unknown'", async () => {
  const f = await page();
  const kitchen = f.browser.CeliacKitchen.attach(f.document.getElementById("sg-kitchen"));
  choose(f, "sg-kitchen-owner", "no");
  assert.deepEqual(plain(kitchen.read()), { owner_celiac: false });
});

Deno.test("setVisible(false) hides the block, clears the answers and read() returns {}", async () => {
  const f = await page();
  const root = f.document.getElementById("rp-kitchen");
  const kitchen = f.browser.CeliacKitchen.attach(root);
  choose(f, "rp-kitchen-owner", "yes");
  kitchen.setVisible(false);
  assert.equal(root.hidden, true);
  kitchen.setVisible(true);
  assert.deepEqual(plain(kitchen.read()), {});
});

Deno.test("EN dictionary carries every kitchen key (copy test covers the rest)", async () => {
  const main = await Deno.readTextFile("js/main.js");
  for (const key of ["kitchen.legend", "kitchen.intro", "kitchen.q1", "kitchen.q1.yes", "kitchen.q1.no",
    "kitchen.unknown", "kitchen.q2", "kitchen.q2.separateKitchen", "kitchen.q2.separatePrep",
    "kitchen.q2.sharedKitchen", "kitchen.q3", "kitchen.yes", "kitchen.no", "kitchen.ownerNote"]) {
    assert.ok(main.includes(`"${key}":`), key);
  }
});

async function submitSuggest(choices = []) {
  const f = await page(["js/kitchen.js", "js/suggest.js"]);
  const d = f.document;
  d.getElementById("sg-name").value = "Pan Justo";
  d.getElementById("sg-address").value = "Corrientes 100";
  d.getElementById("sg-city").value = "Rosario";
  // linkedom <select>: define value explicitly, as the explorer test does.
  Object.defineProperty(d.getElementById("sg-country"), "value", { writable: true, value: "Argentina" });
  Object.defineProperty(d.getElementById("sg-category"), "value", { writable: true, value: "" });
  for (const [name, value] of choices) choose(f, name, value);
  d.getElementById("suggest-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  return f.bodies;
}

Deno.test("suggest.js: everything on 'No sé' sends exactly today's payload (no kitchen keys)", async () => {
  const [sent] = await submitSuggest();
  assert.deepEqual(Object.keys(sent.body).sort(),
    ["address", "category", "city", "country", "evidence_url", "name", "notes", "origin"]);
});

Deno.test("suggest.js: answered kitchen questions travel with the suggestion", async () => {
  const [sent] = await submitSuggest([
    ["sg-kitchen-exclusive", "no"], ["sg-kitchen-prep", "separate_kitchen"], ["sg-kitchen-owner", "yes"],
  ]);
  assert.equal(sent.body.kitchen_exclusive, false);
  assert.equal(sent.body.celiac_prep, "separate_kitchen");
  assert.equal(sent.body.owner_celiac, true);
});

async function submitReport(type, choices = []) {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  d.getElementById("rp-place-id").value = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10";
  d.getElementById("rp-description").value = "Muy buena atención y opciones para celíacos";
  const radio = d.getElementById(`rp-type-${type}`);
  for (const r of d.querySelectorAll('input[name="rp-type"]')) r.checked = r === radio;
  for (const [name, value] of choices) choose(f, name, value);
  radio.dispatchEvent(new f.window.Event("change", { bubbles: true }));
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  return f.bodies;
}

Deno.test("report.js: 'No sé' everywhere sends exactly today's payload", async () => {
  const [sent] = await submitReport("positive");
  assert.deepEqual(Object.keys(sent.body).sort(), ["description", "place_id", "report_type"]);
});

Deno.test("report.js: a positive recommendation carries the answered kitchen keys", async () => {
  const [sent] = await submitReport("positive", [["rp-kitchen-exclusive", "yes"], ["rp-kitchen-owner", "no"]]);
  assert.equal(sent.body.report_type, "positive");
  assert.equal(sent.body.kitchen_exclusive, true);
  assert.equal(sent.body.owner_celiac, false);
  assert.equal("celiac_prep" in sent.body, false);
});

Deno.test("report.js: a negative report never carries kitchen keys, even if answered before switching", async () => {
  // Answers are chosen while 'positive' is selected, then the person switches to 'negative'.
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  d.getElementById("rp-place-id").value = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10";
  d.getElementById("rp-description").value = "Me contaminaron la comida";
  choose(f, "rp-kitchen-exclusive", "yes");
  const neg = d.getElementById("rp-type-negative");
  for (const r of d.querySelectorAll('input[name="rp-type"]')) r.checked = r === neg;
  neg.dispatchEvent(new f.window.Event("change", { bubbles: true }));
  assert.equal(d.getElementById("rp-kitchen").hidden, true);
  d.getElementById("report-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  const [sent] = f.bodies;
  assert.equal(sent.body.report_type, "negative");
  assert.equal("kitchen_exclusive" in sent.body, false);
});

Deno.test("report.js: after a negative report is SENT the kitchen block comes back for the next recommendation", async () => {
  const f = await page(["js/kitchen.js", "js/report.js"]);
  const d = f.document;
  const form = d.getElementById("report-form");
  const pos = d.getElementById("rp-type-positive");
  const neg = d.getElementById("rp-type-negative");
  // linkedom has no radio-group reset: emulate a browser's form.reset(), which re-selects the default
  // radio ("Recomendar") and fires NO change event.
  form.reset = () => { pos.checked = true; neg.checked = false; };
  d.getElementById("rp-place-id").value = "3f2b6c1e-8d3a-4e21-9a55-0c7d6f1b2a10";
  d.getElementById("rp-description").value = "Me contaminaron la comida";
  pos.checked = false;
  neg.checked = true;
  neg.dispatchEvent(new f.window.Event("change", { bubbles: true }));
  assert.equal(d.getElementById("rp-kitchen").hidden, true);
  form.dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(pos.checked, true, "the form went back to 'Recomendar'");
  assert.equal(d.getElementById("rp-kitchen").hidden, false, "the block must follow the type after the reset");
});
