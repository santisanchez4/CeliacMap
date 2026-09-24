// Copy regression for the #suggest section: each form card leads with a title
// that says what it is for, and every translatable string has an EN entry.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_forms_copy.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import assert from "node:assert/strict";

const squash = (s) => s.replace(/\s+/g, " ").trim();

async function load() {
  const html = await Deno.readTextFile("index.html");
  const main = await Deno.readTextFile("js/main.js");
  const { document } = parseHTML(html);
  const en = new Map();
  for (const m of main.matchAll(/"([\w.]+)":\s*("(?:[^"\\]|\\.)*")/g)) en.set(m[1], JSON.parse(m[2]));
  return { document, en };
}

const CARDS = [
  {
    id: "suggest-form",
    titleKey: "suggest.form.title",
    titleEs: "¿Conocés un lugar? Agregalo",
    titleEn: "Know a place? Add it",
    introKey: "suggest.form.intro",
    introEs: "Contanos de un lugar sin TACC que todavía no está en el mapa. Lo revisamos y, si se confirma, aparece para toda la comunidad.",
    introEn: "Tell us about a gluten-free place that isn't on the map yet. We review it and, if confirmed, it appears for the whole community.",
  },
  {
    id: "report-form",
    titleKey: "report.form.title",
    titleEs: "¿Ya fuiste a un lugar del mapa? Contanos cómo te fue",
    titleEn: "Been to a place on the map? Tell us how it went",
    introKey: "report.form.intro",
    introEs: "Recomendalo si te fue bien o reportá un problema. Lo sumamos como evidencia para revisión; nunca cambia el mapa por sí solo.",
    introEn: "Recommend it if it went well, or report a problem. We add it as evidence for review; it never changes the map on its own.",
  },
];

for (const c of CARDS) {
  Deno.test(`#${c.id} opens with a title and a message`, async () => {
    const { document, en } = await load();
    const form = document.getElementById(c.id);
    const title = form.firstElementChild;
    assert.equal(title.tagName, "H3");
    assert.ok(title.classList.contains("suggest-form-title"));
    assert.equal(title.getAttribute("data-i18n"), c.titleKey);
    assert.equal(squash(title.textContent), c.titleEs);
    const intro = title.nextElementSibling;
    assert.ok(intro.classList.contains("suggest-form-intro"));
    assert.equal(intro.getAttribute("data-i18n"), c.introKey);
    assert.equal(squash(intro.textContent), c.introEs);
    assert.equal(en.get(c.titleKey), c.titleEn);
    assert.equal(en.get(c.introKey), c.introEn);
  });
}

Deno.test("step 1 describes what the form really asks for", async () => {
  const { document, en } = await load();
  const step = document.querySelector('#suggest [data-i18n="suggest.s1.title"]');
  assert.equal(squash(step.textContent), "Completá los datos del lugar");
  const text = document.querySelector('#suggest [data-i18n="suggest.s1.text"]');
  assert.equal(squash(text.textContent), "Indicá el nombre, la dirección y el tipo de comercio.");
  assert.equal(en.get("suggest.s1.title"), "Fill in the place details");
  assert.equal(en.get("suggest.s1.text"), "Give the name, the address and the type of business.");
});

Deno.test("every data-i18n key in #suggest has an EN entry", async () => {
  const { document, en } = await load();
  const keys = [...document.querySelectorAll("#suggest [data-i18n]")].map((n) => n.getAttribute("data-i18n"));
  const missing = keys.filter((k) => !en.has(k));
  assert.deepEqual(missing, []);
});
