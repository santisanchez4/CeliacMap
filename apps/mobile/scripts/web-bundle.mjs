// What goes into the app's www/ folder and how index.html differs from the site's. Pure: no file system, no network.
// The lists mirror the "Stage static site" step of .github/workflows/deploy-pages.yml (tests/frontend_mobile.test.js).

export const SITE_FILES = ["index.html", "privacidad.html", "terminos.html"];
export const SITE_DIRS = ["css", "js", "assets"];
// Published on the web, left out of the app: the files are already local, so there is no shell to cache or install.
export const WEB_ONLY_FILES = ["manifest.webmanifest", "service-worker.js"];
export const NATIVE_SCRIPT = "native.js";

const ANALYTICS = [
  ["the Cloudflare beacon", /[ \t]*<!-- Cloudflare Web Analytics[^>]*-->\s*<script\b[^>]*cloudflareinsights\.com[^>]*><\/script>[ \t]*\r?\n/],
  ["the Cloudflare preconnect", /[ \t]*<link rel="preconnect" href="https:\/\/static\.cloudflareinsights\.com"[^>]*>[ \t]*\r?\n/],
];
const REMOVALS = [...ANALYTICS, ["the web manifest link", /[ \t]*<link rel="manifest"[^>]*>[ \t]*\r?\n/]];

function removeEach(html, removals) {
  let out = html;
  for (const [label, pattern] of removals) {
    const global = new RegExp(pattern.source, "g");
    const found = (out.match(global) || []).length;
    if (found !== 1) throw new Error(`index.html: expected ${label} exactly once, found ${found}`);
    out = out.replace(pattern, "");
  }
  if (/cloudflareinsights/i.test(out)) throw new Error("index.html: a Cloudflare analytics reference survived");
  return out;
}

// The site's page without the analytics beacon: scripts/stage_site.mjs, so a local staging copy is never counted.
export function withoutAnalytics(html) {
  return removeEach(html, ANALYTICS);
}

export function appIndexHtml(html) {
  const out = removeEach(html, REMOVALS);
  if ((out.match(/<\/body>/g) || []).length !== 1) throw new Error("index.html: expected one </body>");
  return out.replace("</body>", `  <script src="${NATIVE_SCRIPT}"></script>\n</body>`);
}
