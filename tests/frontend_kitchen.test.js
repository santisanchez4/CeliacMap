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
  let now = 10000;
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
