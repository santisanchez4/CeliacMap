// The «Plan Fundador» request form (js/partners.js, PLAN-partner-program.md §3 and §9, phase 1).
// No network, no browser: fetch, the clock and crypto are fakes.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_partner_form.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

// The 11 columns anon may INSERT (db/migrations/2026-10-14-partner-program.PENDING.sql, `grant insert (...)`).
const ANON_COLUMNS = [
  "ref_code", "business_name", "city", "country", "contact_name", "contact_email", "contact_phone", "links",
  "description", "on_map_claim", "consent_version",
].sort();

const conflict = (constraint) => ({
  ok: false, status: 409, json: async () => ({}),
  text: async () => JSON.stringify({ code: "23505", message: `duplicate key value violates unique constraint "${constraint}"` }),
});
const created = { ok: true, status: 201, text: async () => "", json: async () => [] };

async function page({ step = 5000, inserts = [] } = {}) {
  const { window, document } = parseHTML(await Deno.readTextFile("index.html"));
  let byte = 0;
  const browser = {
    CELIACMAP_CONFIG: { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture-anon", PARTNER_PROGRAM: true },
    crypto: { getRandomValues: (arr) => { for (let i = 0; i < arr.length; i++) arr[i] = byte++ % 252; return arr; } },
  };
  const store = new Map();
  const calls = [];
  let now = 1_700_000_000_000;
  const context = {
    window: browser, document, setTimeout, clearTimeout, CustomEvent: window.CustomEvent,
    Date: class extends Date { static now() { return (now += step); } },
    localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) },
    fetch: async (url, init = {}) => {
      calls.push({ url: String(url), init, body: init.body ? JSON.parse(init.body) : null });
      if (String(url).includes("/partners_public")) return { ok: true, status: 200, json: async () => [] };
      return inserts.length ? inserts.shift() : created;
    },
  };
  vm.runInNewContext(await Deno.readTextFile("js/main.js"), context);
  vm.runInNewContext(await Deno.readTextFile("js/partners.js"), context);
  const $ = (id) => document.getElementById(id);
  $("pp-form").reset = () => {}; // linkedom has no HTMLFormElement.reset
  $("pp-toggle").dispatchEvent(new window.Event("click"));
  const posts = () => calls.filter((c) => c.init.method === "POST");
  return { window, document, $, calls, posts, store };
}

function fill(f, values = {}) {
  const v = {
    "pp-business": "Panadería Prueba", "pp-city": "Fray Bentos", "pp-country": "Uruguay", "pp-contact": "Ana Pérez",
    "pp-email": "ana@example.com", "pp-onmap": "unsure", ...values,
  };
  for (const [id, value] of Object.entries(v)) {
    if (id === "consent") continue;
    const node = f.$(id);
    // linkedom: a <select>'s value is read-only; it follows the option carrying `selected`.
    if (node.tagName === "SELECT") {
      for (const option of node.querySelectorAll("option")) option.toggleAttribute("selected", option.value === value);
    } else node.value = value;
  }
  if (values.consent !== false) f.$("pp-consent").checked = true;
}

const tick = () => new Promise((r) => setTimeout(r, 0));
async function submit(f) {
  f.$("pp-form").dispatchEvent(new f.window.Event("submit", { cancelable: true }));
  for (let i = 0; i < 6; i++) await tick();
}
const status = (f) => f.$("pp-status").textContent.trim();
const shown = (f, id) => !f.$(id).hasAttribute("hidden");

Deno.test("the button opens the form in the card with aria-expanded and aria-controls", async () => {
  const f = await page();
  const toggle = f.$("pp-toggle");
  assert.equal(toggle.getAttribute("aria-controls"), "pp-form");
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(shown(f, "pp-form"), true);
  assert.equal(f.$("pp-form").closest(".partner-plan") !== null, true);
  toggle.dispatchEvent(new f.window.Event("click"));
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  assert.equal(shown(f, "pp-form"), false);
});

Deno.test("a valid request POSTs exactly the 11 anon columns with return=minimal, never place_id or a state", async () => {
  const f = await page();
  fill(f, { "pp-phone": " 099 123 456 ", "pp-links": "instagram.com/prueba", "pp-description": "Pan sin TACC" });
  await submit(f);
  const [post] = f.posts();
  assert.equal(f.posts().length, 1);
  assert.equal(post.url, "https://fixture.invalid/rest/v1/partner_applications");
  assert.equal(post.init.headers.Prefer, "return=minimal");
  assert.equal(post.init.headers.apikey, "fixture-anon");
  assert.deepEqual(Object.keys(post.body).sort(), ANON_COLUMNS);
  for (const banned of ["place_id", "payment_status", "publication_status", "mp_preapproval_id", "paid_through"]) {
    assert.equal(banned in post.body, false, `${banned} in the payload`);
  }
  assert.match(post.body.ref_code, /^CM-[A-Z0-9]{6}$/);
  assert.equal(post.body.contact_phone, "099 123 456");
  assert.equal(post.body.on_map_claim, "unsure");
  assert.equal(post.body.consent_version, "condiciones-aliados-1.0-borrador");
});

Deno.test("optional fields left blank go as null, never as empty strings", async () => {
  const f = await page();
  fill(f);
  await submit(f);
  const body = f.posts()[0].body;
  assert.equal(body.contact_phone, null);
  assert.equal(body.links, null);
  assert.equal(body.description, null);
});

Deno.test("after sending, the code and the next steps replace the form; nothing links to Mercado Pago", async () => {
  const f = await page();
  fill(f);
  await submit(f);
  const ref = f.posts()[0].body.ref_code;
  assert.equal(shown(f, "pp-done"), true);
  assert.equal(shown(f, "pp-form"), false);
  assert.equal(shown(f, "pp-toggle"), false);
  assert.equal(f.$("pp-code").textContent, ref);
  const done = f.$("pp-done").textContent;
  assert.ok(done.includes("5 días hábiles"), done);
  assert.ok(done.includes("número de operación"), done);
  assert.equal(f.document.querySelectorAll('#partner-program a[href*="mercadopago"]').length, 0);
});

Deno.test("required fields: nothing is sent and the missing message shows", async () => {
  for (const missing of ["pp-business", "pp-city", "pp-country", "pp-contact", "pp-email", "pp-onmap"]) {
    const f = await page();
    fill(f, { [missing]: "" });
    await submit(f);
    assert.equal(f.posts().length, 0, missing);
    assert.equal(status(f), "Completá los campos marcados con * y aceptá las condiciones.", missing);
  }
});

Deno.test("the consent box is required", async () => {
  const f = await page();
  fill(f, { consent: false });
  await submit(f);
  assert.equal(f.posts().length, 0);
  assert.equal(f.$("pp-consent").hasAttribute("required"), true);
});

Deno.test("an invalid email is not sent", async () => {
  const f = await page();
  fill(f, { "pp-email": "ana@example" });
  await submit(f);
  assert.equal(f.posts().length, 0);
  assert.equal(status(f), "Revisá el email: no parece válido.");
});

Deno.test("honeypot: looks accepted, sends nothing", async () => {
  const f = await page();
  fill(f, { "pp-website": "https://spam.example" });
  await submit(f);
  assert.equal(f.posts().length, 0);
  assert.equal(shown(f, "pp-done"), true);
});

Deno.test("a submit faster than the minimum fill time looks accepted and sends nothing", async () => {
  const f = await page({ step: 0 });
  fill(f);
  await submit(f);
  assert.equal(f.posts().length, 0);
  assert.equal(shown(f, "pp-done"), true);
});

Deno.test("cooldown: a second request within a minute is held back", async () => {
  const f = await page();
  f.store.set("celiacmap-partner-last", String(1_700_000_000_000));
  fill(f);
  await submit(f);
  assert.equal(f.posts().length, 0);
  assert.equal(status(f), "Esperá un momento antes de enviar otra solicitud.");
});

Deno.test("a ref_code collision generates a new code and retries silently", async () => {
  const f = await page({ inserts: [conflict("partner_applications_ref_code_key"), created] });
  fill(f);
  await submit(f);
  const [first, second] = f.posts().map((p) => p.body.ref_code);
  assert.equal(f.posts().length, 2);
  assert.notEqual(first, second);
  assert.match(second, /^CM-[A-Z0-9]{6}$/);
  assert.equal(f.$("pp-code").textContent, second);
  assert.equal(shown(f, "pp-done"), true);
});

Deno.test("ref_code retries stop after three; the request then shows the generic error", async () => {
  const clash = () => conflict("partner_applications_ref_code_key");
  const f = await page({ inserts: [clash(), clash(), clash(), clash(), created] });
  fill(f);
  await submit(f);
  assert.equal(f.posts().length, 4);
  assert.equal(status(f), "No se pudo enviar. Probá de nuevo en unos minutos.");
  assert.equal(shown(f, "pp-done"), false);
});

Deno.test("an open request with the same email + business shows the duplicate message, without retrying", async () => {
  const f = await page({ inserts: [conflict("partner_applications_open_request_idx")] });
  fill(f);
  await submit(f);
  assert.equal(f.posts().length, 1);
  assert.ok(status(f).startsWith("Ya tenemos una solicitud tuya"), status(f));
  assert.equal(shown(f, "pp-done"), false);
});

Deno.test("a server error shows the generic error and keeps the form", async () => {
  const f = await page({ inserts: [{ ok: false, status: 500, text: async () => "" }] });
  fill(f);
  await submit(f);
  assert.equal(status(f), "No se pudo enviar. Probá de nuevo en unos minutos.");
  assert.equal(shown(f, "pp-form"), true);
});

Deno.test("switching language keeps what was typed and translates the status", async () => {
  const f = await page();
  fill(f, { "pp-email": "ana@example" });
  await submit(f);
  f.$("lang-toggle").dispatchEvent(new f.window.Event("click"));
  assert.equal(f.$("pp-email").value, "ana@example");
  assert.equal(status(f), "Please check the email: it does not look valid.");
  assert.equal(f.$("pp-toggle").textContent, "Hide the form");
});
