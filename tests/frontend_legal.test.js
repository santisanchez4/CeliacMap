// Published legal pages (privacidad.html, terminos.html): they carry the text of docs/legal/*.md, load no script,
// are deployed and packaged, and the landing links to them from the footer, both forms and the chat.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_legal.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import assert from "node:assert/strict";
import { SITE_FILES } from "../apps/mobile/scripts/web-bundle.mjs";

const PAGES = [
  { html: "privacidad.html", md: "docs/legal/politica-de-privacidad.md", title: "Política de privacidad de CeliacMap" },
  { html: "terminos.html", md: "docs/legal/terminos-de-uso.md", title: "Términos de uso de CeliacMap" },
];
const VERSION = "Versión 1.1 · Última actualización: 6 de octubre de 2026";

const squash = (s) => s.replace(/\s+/g, " ").trim();

// The markdown source as plain text blocks: one per paragraph, list item, heading or table cell.
function sourceBlocks(md) {
  const blocks = [];
  let current = [];
  const flush = () => {
    if (current.length) blocks.push(current.join(" "));
    current = [];
  };
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (/^\|[\s|:-]+\|$/.test(line)) continue;
    if (line.startsWith("|")) {
      flush();
      blocks.push(...line.replace(/^\||\|$/g, "").split("|"));
      continue;
    }
    if (/^(#{1,3} |- )/.test(line)) flush();
    current.push(line.replace(/^(#{1,3} |- )/, ""));
    if (/^#{1,3} /.test(line)) flush();
  }
  flush();
  return blocks
    .map((b) => squash(b.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/\*\*|`/g, "")))
    .filter(Boolean);
}

for (const page of PAGES) {
  Deno.test(`${page.html} carries every block of ${page.md}, with its title, version and date`, async () => {
    const { document } = parseHTML(await Deno.readTextFile(page.html));
    const md = await Deno.readTextFile(page.md);
    const article = document.querySelector("main article.legal");
    const text = squash(article.textContent);
    assert.equal(squash(article.querySelector("h1").textContent), page.title);
    assert.equal(squash(article.querySelector(".legal-version").textContent), VERSION);
    assert.ok(md.includes(`**${VERSION}**`));
    const blocks = sourceBlocks(md);
    assert.ok(blocks.length > 40, `${blocks.length} blocks parsed`);
    for (const block of blocks) assert.ok(text.includes(block), `missing from ${page.html}: ${block.slice(0, 80)}`);
    const words = (s) => s.split(" ").length;
    assert.ok(Math.abs(words(text) - words(blocks.join(" "))) < 30, "the page has text that the source does not");
    assert.ok(!/BORRADOR|PENDIENTE|A CONFIRMAR/.test(text));
  });

  Deno.test(`${page.html} is a static Spanish page: no scripts, no beacon, same stylesheet and fonts as the site`, async () => {
    const source = await Deno.readTextFile(page.html);
    const { document } = parseHTML(source);
    assert.equal(document.documentElement.getAttribute("lang"), "es");
    assert.equal(document.querySelectorAll("script").length, 0);
    assert.ok(!/cloudflareinsights|unpkg.com|rel="manifest"/.test(source));
    const sheets = [...document.querySelectorAll('link[rel="stylesheet"]')].map((l) => l.getAttribute("href"));
    assert.equal(sheets.length, 2);
    assert.ok(sheets[0].startsWith("https://fonts.googleapis.com/"));
    assert.equal(sheets[1], "css/styles.css");
    for (const a of document.querySelectorAll("a[href]")) {
      const href = a.getAttribute("href");
      assert.ok(/^(index\.html|privacidad\.html|terminos\.html|#main|mailto:hola@celiacmap\.org)$/.test(href), href);
    }
    assert.equal(document.querySelectorAll("table caption").length, document.querySelectorAll("table").length);
  });
}

Deno.test("the location section is published as approved: the device gives it to the page, browser or app", async () => {
  const md = squash(await Deno.readTextFile("docs/legal/politica-de-privacidad.md"));
  const section = md.slice(md.indexOf("### 3.10"), md.indexOf("## 4."));
  assert.ok(section.includes("tu dispositivo le da tu ubicación a la página **una vez**"));
  assert.ok(!section.includes("nos da tu ubicación"));
  assert.equal((section.match(/navegador/g) || []).length, (section.match(/navegador o de la app/g) || []).length);
  assert.ok(!md.includes("BORRADOR"));
});

Deno.test("the legal pages are deployed to Pages and packaged in the app", async () => {
  const workflow = await Deno.readTextFile(".github/workflows/deploy-pages.yml");
  const staged = workflow.match(/^\s*cp ([^\n]+?) _site\/\s*$/m)[1].trim().split(/\s+/);
  for (const page of PAGES) {
    assert.ok(staged.includes(page.html), `${page.html} is not staged for Pages`);
    assert.ok(SITE_FILES.includes(page.html), `${page.html} is not packaged in the app`);
  }
});

Deno.test("the landing links to both pages from the footer and to the policy from each form and the chat", async () => {
  const { document } = parseHTML(await Deno.readTextFile("index.html"));
  const main = await Deno.readTextFile("js/main.js");
  const chat = await Deno.readTextFile("js/chat.js");
  const footer = [...document.querySelectorAll(".site-footer .footer-nav a")].map((a) => a.getAttribute("href"));
  assert.ok(footer.includes("privacidad.html") && footer.includes("terminos.html"));

  for (const [formId, submitId] of [["suggest-form", "sg-submit"], ["report-form", "rp-submit"]]) {
    const submit = document.getElementById(submitId);
    const notice = document.getElementById(submit.getAttribute("aria-describedby"));
    assert.ok(document.getElementById(formId).contains(notice), `${formId} has no privacy notice`);
    assert.equal(squash(notice.textContent), "Al enviar aceptás la política de privacidad.");
    assert.equal(notice.querySelector("a").getAttribute("href"), "privacidad.html");
  }

  const link = document.querySelector(".chat-disclaimers a");
  assert.equal(link.getAttribute("href"), "privacidad.html");
  assert.equal(link.getAttribute("target"), "_blank");
  assert.equal(link.getAttribute("rel"), "noopener");
  for (const key of ["privacyPre", "privacyLink", "privacyPost"]) {
    assert.ok(document.querySelector(`.chat-disclaimers [data-chat-text="${key}"]`), key);
    assert.equal((chat.match(new RegExp(`\\b${key}: "`, "g")) || []).length, 2, `${key} needs ES and EN`);
  }
  assert.ok(chat.includes('privacyPost: ". No compartas datos de salud tuyos ni de otras personas."'));
  for (const key of ["footer.privacy", "footer.terms", "privacy.notice.send", "privacy.notice.link"]) {
    assert.ok(document.querySelector(`[data-i18n="${key}"]`), `${key} is not used`);
    assert.ok(main.includes(`"${key}": "`), `${key} has no EN entry`);
  }
});
