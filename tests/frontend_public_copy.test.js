// Public copy guard (2026-11-20). CeliacMap does not visit, inspect or certify places, so the public
// site never calls a place "seguro", "verificado" or "validado" (ES) / "safe", "verified" or "validated"
// (EN), and it never says "sin TACC" again (the label is "sin gluten" since 2026-11-18).
// Covers what a visitor reads: index.html (text and text attributes), the manifest, the footer of the
// legal pages and every string literal of js/*.js. The body of the legal pages is the text of
// docs/legal/*.md (versioned, guarded by frontend_legal.test.js) and is not covered here.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_public_copy.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import assert from "node:assert/strict";

const BANNED = [
  ["sin TACC", /sin\s+t\.?\s?a\.?\s?c\.?\s?c/i],
  ["seguro/a", /(?<![\wáéíóúñ-])segur[oa]s?(?![\wáéíóúñ-])/i],
  ["verificado/a", /(?<![\wáéíóúñ-])verificad[oa]s?(?![\wáéíóúñ-])/i],
  ["validado/a", /(?<![\wáéíóúñ-])validad[oa]s?(?![\wáéíóúñ-])/i],
  ["safe", /(?<![\w-])safe(?:r|ly|st)?(?![\w-])/i],
  ["verified", /(?<![\w-])verified(?![\w-])/i],
  ["validated", /(?<![\w-])validated(?![\w-])/i],
];

function offences(text) {
  return BANNED.filter(([, re]) => re.test(text)).map(([word]) => word);
}

function assertClean(where, text) {
  assert.deepEqual(offences(text), [], where + ": " + text.replace(/\s+/g, " ").trim().slice(0, 160));
}

const TEXT_ATTRIBUTES = ["content", "aria-label", "placeholder", "title", "alt"];

Deno.test("the guard itself catches each word and ignores identifiers", () => {
  for (const bad of ["Lugares sin TACC", "sin T.A.C.C.", "lugares seguros", "una forma más segura", "Lugares verificados",
    "validado por la comunidad", "Safe places", "ate at safely", "a safer way", "Verified places", "community validated"]) {
    assert.equal(offences(bad).length, 1, bad);
  }
  for (const fine of ["nivel de seguridad del servicio", "dot dot-safe", "safety_level", "data-safety", "se revisa antes de publicarse",
    "sin gluten", "novalidate", "aseguró"]) {
    assert.deepEqual(offences(fine), [], fine);
  }
});

Deno.test("index.html never calls a place safe, verified or validated, and never says sin TACC", async () => {
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  for (const node of document.querySelectorAll("script, style")) node.remove();
  assertClean("index.html title", document.querySelector("title").textContent);
  assertClean("index.html text", document.body.textContent);
  for (const node of document.querySelectorAll("*")) {
    for (const attr of TEXT_ATTRIBUTES) {
      const value = node.getAttribute(attr);
      if (value) assertClean("index.html [" + attr + "]", value);
    }
  }
});

Deno.test("the English dictionary and every other string of js/*.js are clean too", async () => {
  const literal = /"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'/g;
  let checked = 0;
  for await (const entry of Deno.readDir("js")) {
    if (!entry.name.endsWith(".js")) continue;
    const lines = (await Deno.readTextFile("js/" + entry.name)).split(/\r?\n/);
    lines.forEach((line, i) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) return;
      for (const m of line.matchAll(literal)) {
        assertClean("js/" + entry.name + ":" + (i + 1), m[0]);
        checked++;
      }
    });
  }
  assert.ok(checked > 500, "string literals were scanned");
});

Deno.test("the manifest and the legal pages' footer are clean", async () => {
  const manifest = JSON.parse(await Deno.readTextFile("manifest.webmanifest"));
  for (const key of ["name", "short_name", "description"]) assertClean("manifest." + key, String(manifest[key] || ""));
  for (const page of ["privacidad.html", "terminos.html"]) {
    const { document } = parseHTML(await Deno.readTextFile(page));
    assertClean(page + " title", document.querySelector("title").textContent);
    assertClean(page + " footer", document.querySelector("footer").textContent);
  }
});

Deno.test("the hero no longer claims a community validation percentage", async () => {
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const stats = Array.from(document.querySelectorAll(".hero-stats li")).map(li => li.textContent.replace(/\s+/g, " ").trim());
  assert.equal(stats.some(s => /100%/.test(s)), false, stats.join(" | "));
});
