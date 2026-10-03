// Builds apps/mobile/www from the site at the repo root: the same files GitHub Pages publishes, minus the PWA
// shell and the analytics beacon, plus native.js. www/ is generated and never committed.
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { NATIVE_SCRIPT, SITE_DIRS, SITE_FILES, appIndexHtml } from "./web-bundle.mjs";

const mobile = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(mobile, "..", "..");
const www = join(mobile, "www");

rmSync(www, { recursive: true, force: true });
mkdirSync(www, { recursive: true });

for (const dir of SITE_DIRS) cpSync(join(root, dir), join(www, dir), { recursive: true });
for (const file of SITE_FILES) {
  if (file === "index.html") continue;
  cpSync(join(root, file), join(www, file));
}
writeFileSync(join(www, "index.html"), appIndexHtml(readFileSync(join(root, "index.html"), "utf8")));
cpSync(join(mobile, "native", NATIVE_SCRIPT), join(www, NATIVE_SCRIPT));

console.log(`www ready: ${[...SITE_FILES, ...SITE_DIRS, NATIVE_SCRIPT].join(", ")}`);
