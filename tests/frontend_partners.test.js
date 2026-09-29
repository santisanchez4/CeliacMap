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
