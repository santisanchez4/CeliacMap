// The "Aliados" section (ADR-009): labeled, separate, and absent from the map and the chat.
// No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_partners.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";

const LABEL_ES = "Aliado";
const LABEL_EN = "Partner";
const DISCLAIMER_ES = "Los aliados apoyan el proyecto. No influyen en qué lugares aparecen en el mapa ni en su etiqueta.";
const DISCLAIMER_EN = "Partners support the project. They have no influence on which places appear on the map or on their label.";

async function page() {
  const { window, document } = parseHTML(await Deno.readTextFile("index.html"));
  const context = { window: {}, document, localStorage: { getItem: () => null, setItem() {} }, CustomEvent: window.CustomEvent };
  vm.runInNewContext(await Deno.readTextFile("js/main.js"), context);
  return { window, document };
}

const text = (node) => node.textContent.replace(/\s+/g, " ").trim();

Deno.test("the #aliados section sits inside main, after every other section, before the footer", async () => {
  const { document } = await page();
  const section = document.getElementById("aliados");
  assert.ok(section, "section#aliados exists");
  assert.equal(section.tagName, "SECTION");
  assert.equal(section.parentElement.tagName, "MAIN");
  assert.equal(section, [...document.querySelectorAll("main > section")].at(-1));
  assert.ok(document.querySelector('.footer-nav a[href="#aliados"]'), "footer links to #aliados");
});

const count = (hay, needle) => hay.split(needle).length - 1;

Deno.test("the independence sentence is the section lead, exactly once, outside any card, in ES and EN", async () => {
  const { window, document } = await page();
  const section = document.getElementById("aliados");
  const label = section.querySelector(".partner-card .partner-label");
  const disclaimer = section.querySelector(".partner-disclaimer");
  assert.ok(disclaimer.closest(".section-head"), "the sentence sits in the section head");
  assert.equal(disclaimer.closest(".partner-card, .partner-invite"), null);
  assert.equal(text(document.getElementById("aliados-title")), "Quiénes apoyan CeliacMap");

  const check = (labelText, sentence) => {
    assert.equal(text(label), labelText);
    assert.equal(text(disclaimer), sentence);
    assert.equal(count(text(section), sentence), 1, "the sentence appears once in the section");
  };
  check(LABEL_ES, DISCLAIMER_ES);

  document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  assert.equal(document.documentElement.getAttribute("lang"), "en");
  check(LABEL_EN, DISCLAIMER_EN);
  assert.equal(text(document.getElementById("aliados-title")), "Who supports CeliacMap");
  assert.equal(text(document.querySelector('.footer-nav a[href="#aliados"]')), "Partners");

  document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  check(LABEL_ES, DISCLAIMER_ES);
});

Deno.test("every partner link is rel=sponsored noopener in a new tab", async () => {
  const { document } = await page();
  const links = [...document.querySelectorAll("#aliados .partner-card a")];
  assert.deepEqual(links.map((a) => a.getAttribute("href")), [
    "https://www.instagram.com/bienestar.glutenfree/",
    "https://wa.me/c/59899506403",
  ]);
  for (const a of links) {
    const rel = (a.getAttribute("rel") || "").split(/\s+/);
    assert.ok(rel.includes("sponsored") && rel.includes("noopener"), `${a.getAttribute("href")} rel="${rel.join(" ")}"`);
    assert.equal(a.getAttribute("target"), "_blank");
  }
});

Deno.test("the logo is local, lazy, sized, described and under 40 KB; no third-party script in the section", async () => {
  const { document } = await page();
  const img = document.querySelector("#aliados img");
  const src = img.getAttribute("src");
  assert.match(src, /^assets\/images\/[\w-]+\.(webp|png)$/);
  assert.ok((img.getAttribute("alt") || "").includes("Bienestar Gluten Free"));
  assert.ok(Number(img.getAttribute("width")) > 0 && Number(img.getAttribute("height")) > 0);
  assert.equal(img.getAttribute("loading"), "lazy");
  const { size } = await Deno.stat(src);
  assert.ok(size < 40 * 1024, `${src} is ${size} bytes`);
  assert.equal(document.querySelectorAll("#aliados script, #aliados iframe").length, 0);
});

Deno.test("the header nav ends with Aliados / Partners pointing at #aliados", async () => {
  const { window, document } = await page();
  const items = [...document.querySelectorAll("#main-nav .nav-list > li > a")];
  const last = items.at(-1);
  assert.equal(items.length, 6);
  assert.equal(items.at(-2).getAttribute("href"), "#about");
  assert.equal(last.getAttribute("href"), "#aliados");
  assert.equal(text(last), "Aliados");
  document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  assert.equal(text(last), "Partners");
});

const INVITE_ES = "¿Tenés un negocio sin gluten o sin TACC y querés sumarte como aliado? Escribinos a hola@celiacmap.org.";
const INVITE_EN = "Run a gluten-free business and want to become a partner? Write to hola@celiacmap.org.";
const subject = (a) => new URL(a.getAttribute("href")).searchParams.get("subject");

Deno.test("the invitation sits outside the partner card, with its mailto subject and text in ES and EN", async () => {
  const { window, document } = await page();
  const invite = document.querySelector("#aliados .partner-invite");
  assert.ok(invite && !invite.closest(".partner-card"), "invitation is not inside a partner card");
  const mail = invite.querySelector('a[href^="mailto:"]');
  assert.equal(new URL(mail.getAttribute("href")).pathname, "hola@celiacmap.org");
  assert.equal(mail.getAttribute("rel"), null, "the invitation is not a sponsored link");
  assert.equal(invite.querySelectorAll("p").length, 1, "the invitation has no extra note");

  assert.equal(text(invite.querySelector(".partner-invite-text")), INVITE_ES);
  assert.equal(subject(mail), "Quiero ser aliado de CeliacMap");

  document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  assert.equal(text(invite.querySelector(".partner-invite-text")), INVITE_EN);
  assert.equal(subject(mail), "Partnership with CeliacMap");

  document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  assert.equal(subject(mail), "Quiero ser aliado de CeliacMap");
});

// supabase/functions/chat/prompts.ts is left out on purpose: it has used Bienestar as a few-shot
// example since before the partnership, and a prompt change needs the jailbreak battery (ADR-009).
Deno.test("the map and the chat code never mention the partner", async () => {
  for (const file of ["js/map.js", "js/chat.js", "supabase/functions/chat/index.ts", "supabase/functions/chat/regions.ts"]) {
    const source = (await Deno.readTextFile(file)).toLowerCase();
    assert.ok(!source.includes("bienestar"), `${file} mentions the partner`);
  }
});

/* ------------------- Partner program (ADR-011, phase 1) ------------------- */

const FIXTURE = { SUPABASE_URL: "https://fixture.invalid", SUPABASE_ANON_KEY: "fixture-anon" };

// config: "production" loads js/config.js as published; an object replaces it (the staging copy's overrides).
async function programPage(config, rows = []) {
  const { window, document } = parseHTML(await Deno.readTextFile("index.html"));
  const browser = { crypto: { getRandomValues: (a) => a } };
  const calls = [];
  const context = {
    window: browser, document, setTimeout, clearTimeout, CustomEvent: window.CustomEvent,
    localStorage: { getItem: () => null, setItem() {} },
    fetch: async (url, init = {}) => {
      calls.push({ url: String(url), init });
      return { ok: true, status: 200, json: async () => rows, text: async () => "" };
    },
  };
  vm.runInNewContext(await Deno.readTextFile("js/main.js"), context);
  if (config === "production") vm.runInNewContext(await Deno.readTextFile("js/config.js"), context);
  else browser.CELIACMAP_CONFIG = config;
  vm.runInNewContext(await Deno.readTextFile("js/partners.js"), context);
  for (let i = 0; i < 4; i++) await new Promise((r) => setTimeout(r, 0));
  const toggleLang = () => document.getElementById("lang-toggle").dispatchEvent(new window.Event("click"));
  return { window, document, browser, calls, toggleLang, mount: document.getElementById("partner-program") };
}

const on = (rows) => programPage({ ...FIXTURE, PARTNER_PROGRAM: true }, rows);

Deno.test("production config: PARTNER_PROGRAM is false, the mount stays empty and hidden, no request is made", async () => {
  const f = await programPage("production");
  assert.equal(f.browser.CELIACMAP_CONFIG.PARTNER_PROGRAM, false);
  assert.equal(f.mount.hasAttribute("hidden"), true);
  assert.equal(f.mount.childNodes.length, 0);
  assert.equal(f.document.getElementById("partners-published"), null);
  assert.equal(f.calls.length, 0);
});

Deno.test("the static page carries only the empty mount, after the Bienestar card and before the invitation", async () => {
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const mount = document.getElementById("partner-program");
  assert.equal(mount.innerHTML.trim(), "");
  assert.equal(mount.hasAttribute("hidden"), true);
  assert.equal(mount.nextElementSibling.classList.contains("partner-invite"), true);
  assert.equal(mount.previousElementSibling.classList.contains("partner-card"), true);
});

Deno.test("no Mercado Pago link or checkout anywhere in index.html or js/", async () => {
  const files = ["index.html"];
  for await (const entry of Deno.readDir("js")) if (entry.name.endsWith(".js")) files.push(`js/${entry.name}`);
  for (const file of files) {
    const source = (await Deno.readTextFile(file)).toLowerCase();
    assert.ok(!/mercadopago\.|mpago\.la|mercadolibre\.|init_point|preapproval/.test(source), `${file} links to Mercado Pago`);
  }
});

Deno.test("switched on: the Plan Fundador card, without the Aliado label, in ES and EN", async () => {
  const f = await on();
  const card = f.mount.querySelector("article.partner-plan");
  assert.equal(Boolean(card), true);
  assert.equal(f.mount.hasAttribute("hidden"), false);
  assert.equal(card.querySelectorAll(".partner-label").length, 0, "the offer is not a partner");
  assert.equal(card.getAttribute("aria-labelledby"), "pp-title");
  const es = text(card);
  for (const s of ["Plan Fundador", "CeliacMap Aliado", "$U 790", "/ mes", "Sin permanencia",
    "Ser aliado es publicidad. No significa que CeliacMap certifique la seguridad alimentaria del comercio ni cambia cómo aparece en el mapa."]) {
    assert.ok(es.includes(s), `missing «${s}»`);
  }
  f.toggleLang();
  const en = text(card);
  for (const s of ["Founding Plan", "CeliacMap Partner", "$U 790", "/ month", "No minimum term",
    "Being a partner is advertising. It does not mean CeliacMap certifies the business's food safety"]) {
    assert.ok(en.includes(s), `missing «${s}»`);
  }
  assert.equal(count(text(f.document.getElementById("aliados")), DISCLAIMER_EN), 1, "the independence sentence is still once");
});

Deno.test("only the 4 benefits of the terms §2: no statistics, no Market", async () => {
  const f = await on();
  const card = f.mount.querySelector(".partner-plan");
  const { PROGRAM } = f.browser.CeliacPartners;
  assert.equal(card.querySelectorAll(".pp-benefit").length, 4);
  assert.equal(PROGRAM.text.es.benefits.length, 4);
  assert.equal(PROGRAM.text.en.benefits.length, 4);
  for (const lang of ["es", "en"]) {
    const all = JSON.stringify(PROGRAM.text[lang]).toLowerCase();
    // «supermercado» / "supermarket" are fine (who cannot be a partner); the future Market is not.
    for (const banned of [/estad[ií]stica/, /statistic/, /\bmarket\b/, /m[eé]trica/, /\bmetric/, /\bclic/, /\bclick/]) {
      assert.ok(!banned.test(all), `${lang} mentions ${banned}`);
    }
  }
});

Deno.test("price, currency, consent version and texts come from one PROGRAM object; ES and EN have the same keys", async () => {
  const f = await on();
  const { PROGRAM } = f.browser.CeliacPartners;
  const source = await Deno.readTextFile("js/partners.js");
  assert.equal(PROGRAM.price, 790);
  assert.equal(PROGRAM.currency, "$U");
  assert.equal(count(source, "790"), 1, "the price is written once");
  assert.equal(count(source, "condiciones-aliados-"), 1, "the consent version is written once");
  assert.ok(!(await Deno.readTextFile("index.html")).includes("790"));
  const shape = (o) => JSON.stringify(o, (k, v) => (typeof v === "string" ? "" : v));
  assert.equal(shape(PROGRAM.text.es), shape(PROGRAM.text.en));
});

const CONDITIONS_ES = ["$U 790 por mes", "mensual y recurrente", "Sin permanencia", "hasta el final del período ya pagado",
  "publicidad", "5 días hábiles", "No se paga nada antes de esa respuesta"];

Deno.test("the terms summary sits in the form before the consent box and the submit button, faithful to the terms", async () => {
  const f = await on();
  const form = f.document.getElementById("pp-form");
  const nodes = [...form.querySelectorAll("#pp-conditions, #pp-consent, #pp-submit")].map((n) => n.id);
  assert.deepEqual(nodes, ["pp-conditions", "pp-consent", "pp-submit"]);
  assert.equal(form.querySelector("#pp-conditions").tagName, "DETAILS");
  const summary = text(form.querySelector("#pp-conditions"));
  for (const s of CONDITIONS_ES) assert.ok(summary.includes(s), `terms summary is missing «${s}»`);
  assert.ok(text(form.querySelector(".pp-recap")).includes("$U 790"), "the price is repeated before sending");
  const terms = (await Deno.readTextFile("docs/legal/condiciones-aliados.md")).replace(/\*\*/g, "");
  for (const s of ["$U 790 por mes", "5 días hábiles", "sigue visible hasta el final del período ya pagado",
    "No hay que pagar nada antes de esa respuesta"]) {
    assert.ok(terms.includes(s), `the terms no longer say «${s}»: update PROGRAM`);
  }
});

Deno.test("the consent box is required and links to the privacy policy", async () => {
  const f = await on();
  const box = f.document.getElementById("pp-consent");
  assert.equal(box.getAttribute("type"), "checkbox");
  assert.equal(box.hasAttribute("required"), true);
  const links = [...box.closest("label").querySelectorAll("a")].map((a) => a.getAttribute("href"));
  assert.deepEqual(links, ["privacidad.html"]);
});

// Phase 3 guard: production may switch the program on only with a final consent version and published terms.
function phase3Problems(config, PROGRAM, consentLinks, publishedFiles) {
  if (config.PARTNER_PROGRAM !== true) return [];
  const problems = [];
  if (/borrador/i.test(PROGRAM.consentVersion)) problems.push("consent_version is still a draft");
  if (!consentLinks.some((href) => /condiciones/i.test(href) && publishedFiles.includes(href))) {
    problems.push("the consent box does not link to a published terms page");
  }
  return problems;
}

Deno.test("phase 3 guard: production never turns the program on with draft terms", async () => {
  const f = await on();
  const { PROGRAM } = f.browser.CeliacPartners;
  const links = [...f.document.getElementById("pp-consent").closest("label").querySelectorAll("a")].map((a) => a.getAttribute("href"));
  const { SITE_FILES } = await import("../apps/mobile/scripts/web-bundle.mjs");
  const published = [];
  for (const file of SITE_FILES) if (!/borrador/i.test(await Deno.readTextFile(file))) published.push(file);
  const production = (await programPage("production")).browser.CELIACMAP_CONFIG;
  assert.deepEqual(phase3Problems(production, PROGRAM, links, published), []);
  // The guard bites: today's texts with the switch on in production fail on both counts.
  assert.deepEqual(phase3Problems({ PARTNER_PROGRAM: true }, PROGRAM, links, published), [
    "consent_version is still a draft",
    "the consent box does not link to a published terms page",
  ]);
});

const ROWS = [{
  public_name: "Panadería <b>Prueba</b>", public_text_es: "Pan sin TACC.", public_text_en: "Gluten-free bread.",
  logo_path: "prueba/logo.webp",
  public_links: [
    { label: "Instagram", url: "https://www.instagram.com/prueba/" },
    { label: "Inseguro", url: "http://example.com/" },
    { label: "Script", url: "javascript:alert(1)" },
  ],
}];

Deno.test("published partners: the 5 public columns of partners_public, after Bienestar, labeled and sponsored", async () => {
  const f = await on(ROWS);
  const read = f.calls.find((c) => c.url.includes("/rest/v1/partners_public"));
  assert.equal(new URL(read.url).searchParams.get("select"), "public_name,public_text_es,public_text_en,logo_path,public_links");
  assert.equal(read.init.method, undefined, "a GET");
  const cards = () => [...f.document.querySelectorAll("#aliados .partner-card")];
  assert.equal(cards().length, 2);
  assert.equal(text(cards()[0].querySelector(".partner-name")), "Bienestar Gluten Free", "the static card stays first");
  const card = cards()[1];
  assert.equal(text(card.querySelector(".partner-label")), LABEL_ES);
  assert.equal(text(card.querySelector(".partner-name")), "Panadería <b>Prueba</b>", "names are text, never HTML");
  assert.equal(card.querySelectorAll("b, script").length, 0);
  const links = [...card.querySelectorAll("a")];
  assert.deepEqual(links.map((a) => a.getAttribute("href")), ["https://www.instagram.com/prueba/"], "https links only");
  assert.equal(links[0].getAttribute("rel"), "sponsored noopener");
  assert.equal(links[0].getAttribute("target"), "_blank");
  assert.equal(card.querySelector("img").getAttribute("src"),
    "https://fixture.invalid/storage/v1/object/public/partner-logos/prueba/logo.webp");
  assert.equal(card.querySelector("img").getAttribute("loading"), "lazy");
  f.toggleLang();
  assert.equal(text(cards()[1].querySelector(".partner-text")), "Gluten-free bread.");
  assert.equal(text(cards()[1].querySelector(".partner-label")), LABEL_EN);
});

Deno.test("partners.js only POSTs to partner_applications and only reads partners_public", async () => {
  const source = await Deno.readTextFile("js/partners.js");
  const paths = [...source.matchAll(/\/rest\/v1\/([a-z_]+)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(paths)].sort(), ["partner_applications", "partners_public"]);
});
