// Builds _staging/: the site GitHub Pages publishes, pointed at the staging Supabase project with the partner program
// on (docs/runbooks/staging.md). The staging URL and anon key are read from .env.staging and written ONLY into
// _staging/js/config.js (gitignored); nothing of staging is ever committed. Refuses the production project and any
// key that is not an anon / publishable key of that same staging project.
//
//   node scripts/stage_site.mjs [--env-file PATH]
//   python -m http.server 8080 --directory _staging
//
// Without --env-file it reads .env.staging from the main checkout (the same file scripts/staging_guard.py uses).
import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { SITE_DIRS, SITE_FILES, WEB_ONLY_FILES, withoutAnalytics } from "../apps/mobile/scripts/web-bundle.mjs";

export const PROD_REF = "pgblbyvetclllaqvknvc";
const URL_RE = /^https:\/\/([a-z0-9]{20})\.supabase\.co\/?$/;

export function parseEnv(text) {
  const env = {};
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (!match) continue;
    env[match[1]] = match[2].replace(/^(["'])(.*)\1$/, "$2");
  }
  return env;
}

function jwtPayload(key) {
  const part = key.split(".")[1];
  if (!part) return null;
  try {
    return JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=")));
  } catch {
    return null;
  }
}

// The only values the staging copy changes. Throws, without echoing any key, if they are not staging's public ones.
export function stagingOverrides(env) {
  const url = (env.STAGING_SUPABASE_URL || "").trim();
  const key = (env.STAGING_SUPABASE_ANON_KEY || "").trim();
  if (!url || !key) throw new Error(".env.staging needs STAGING_SUPABASE_URL and STAGING_SUPABASE_ANON_KEY");
  const match = url.match(URL_RE);
  if (!match) throw new Error("STAGING_SUPABASE_URL is not https://<ref>.supabase.co");
  const ref = match[1];
  if (ref === PROD_REF) throw new Error("STAGING_SUPABASE_URL is the production project: refusing");
  if (key.startsWith("sb_secret_")) throw new Error("STAGING_SUPABASE_ANON_KEY is a secret key: refusing");
  if (!key.startsWith("sb_publishable_")) {
    const claims = jwtPayload(key);
    if (!claims || claims.role !== "anon") throw new Error("STAGING_SUPABASE_ANON_KEY is not an anon key: refusing");
    if (claims.ref !== ref) throw new Error("STAGING_SUPABASE_ANON_KEY belongs to another project: refusing");
  }
  return { SUPABASE_URL: url.replace(/\/+$/, ""), SUPABASE_ANON_KEY: key, PARTNER_PROGRAM: true };
}

// js/config.js as published, plus one block that overrides only the staging values.
export function stagingConfig(source, overrides) {
  if (!source.includes("window.CELIACMAP_CONFIG = {")) throw new Error("js/config.js: CELIACMAP_CONFIG not found");
  return `${source.replace(/\s*$/, "\n")}\n// scripts/stage_site.mjs: local staging copy, never published or committed.\n` +
    `Object.assign(window.CELIACMAP_CONFIG, ${JSON.stringify(overrides, null, 2)});\n`;
}

function defaultEnvFile(root) {
  const common = execFileSync("git", ["rev-parse", "--path-format=absolute", "--git-common-dir"], { cwd: root, encoding: "utf8" });
  return join(dirname(common.trim()), ".env.staging");
}

function main(argv) {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const flag = argv.indexOf("--env-file");
  const envFile = flag >= 0 ? resolve(argv[flag + 1] || "") : defaultEnvFile(root);
  const overrides = stagingOverrides(parseEnv(readFileSync(envFile, "utf8")));
  const out = join(root, "_staging");

  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  for (const dir of SITE_DIRS) cpSync(join(root, dir), join(out, dir), { recursive: true });
  for (const file of [...SITE_FILES, ...WEB_ONLY_FILES]) cpSync(join(root, file), join(out, file));
  writeFileSync(join(out, "index.html"), withoutAnalytics(readFileSync(join(root, "index.html"), "utf8")));
  writeFileSync(join(out, "js", "config.js"), stagingConfig(readFileSync(join(root, "js", "config.js"), "utf8"), overrides));

  const ref = overrides.SUPABASE_URL.match(URL_RE)[1];
  console.log(`_staging/ ready: Supabase ${ref}, PARTNER_PROGRAM on, no analytics beacon.`);
  console.log("Serve it with: python -m http.server 8080 --directory _staging");
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(`refused: ${error.message}`);
    process.exit(2);
  }
}
