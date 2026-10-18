// scripts/stage_site.mjs: the local copy of the site pointed at staging (docs/runbooks/staging.md).
// Pure functions only: no file is written, no network.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_stage_site.test.js
import vm from "node:vm";
import assert from "node:assert/strict";
import { PROD_REF, parseEnv, stagingConfig, stagingOverrides } from "../scripts/stage_site.mjs";

const REF = "abcdefghijklmnopqrst";
const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
const jwt = (claims) => `${b64({ alg: "HS256", typ: "JWT" })}.${b64(claims)}.signature`;
const env = (url, key) => ({ STAGING_SUPABASE_URL: url, STAGING_SUPABASE_ANON_KEY: key });

Deno.test("reads the same variables as staging_guard from .env.staging", () => {
  const parsed = parseEnv(`# comment\nSTAGING_SUPABASE_URL="https://${REF}.supabase.co"\r\nSTAGING_SUPABASE_ANON_KEY=k\nOTHER = x \n`);
  assert.equal(parsed.STAGING_SUPABASE_URL, `https://${REF}.supabase.co`);
  assert.equal(parsed.STAGING_SUPABASE_ANON_KEY, "k");
  assert.equal(parsed.OTHER, "x");
});

Deno.test("overrides only the URL, the anon key and the switch", () => {
  const key = jwt({ ref: REF, role: "anon" });
  assert.deepEqual(stagingOverrides(env(`https://${REF}.supabase.co/`, key)), {
    SUPABASE_URL: `https://${REF}.supabase.co`, SUPABASE_ANON_KEY: key, PARTNER_PROGRAM: true,
  });
  assert.equal(stagingOverrides(env(`https://${REF}.supabase.co`, "sb_publishable_x")).SUPABASE_ANON_KEY, "sb_publishable_x");
});

Deno.test("refuses production, a service_role or secret key, another project's key and a malformed URL", () => {
  const refusals = [
    [env(`https://${PROD_REF}.supabase.co`, jwt({ ref: PROD_REF, role: "anon" })), /production/],
    [env(`https://${REF}.supabase.co`, jwt({ ref: REF, role: "service_role" })), /not an anon key/],
    [env(`https://${REF}.supabase.co`, "sb_secret_abc"), /secret key/],
    [env(`https://${REF}.supabase.co`, jwt({ ref: "zzzzzzzzzzzzzzzzzzzz", role: "anon" })), /another project/],
    [env("http://localhost:54321", "k"), /not https/],
    [env("", ""), /needs STAGING_SUPABASE_URL/],
  ];
  for (const [input, message] of refusals) {
    assert.throws(() => stagingOverrides(input), message);
    try { stagingOverrides(input); } catch (error) {
      assert.ok(!error.message.includes(input.STAGING_SUPABASE_ANON_KEY || "\u0000"), "a refusal never echoes the key");
    }
  }
});

Deno.test("the staged config is the published one plus the overrides, and switches the program on", async () => {
  const source = await Deno.readTextFile("js/config.js");
  const key = jwt({ ref: REF, role: "anon" });
  const staged = stagingConfig(source, stagingOverrides(env(`https://${REF}.supabase.co`, key)));
  assert.ok(staged.startsWith(source.trimEnd()), "the published config is kept as is");
  const browser = {};
  vm.runInNewContext(staged, { window: browser });
  assert.equal(browser.CELIACMAP_CONFIG.SUPABASE_URL, `https://${REF}.supabase.co`);
  assert.equal(browser.CELIACMAP_CONFIG.SUPABASE_ANON_KEY, key);
  assert.equal(browser.CELIACMAP_CONFIG.PARTNER_PROGRAM, true);
  assert.ok(browser.CELIACMAP_CONFIG.CARTO_BASEMAP_KEY, "the rest of the config is not duplicated, it is kept");
});

Deno.test("no staging value is committed: _staging/ is ignored and the repo has no staging config file", async () => {
  const ignore = await Deno.readTextFile(".gitignore");
  assert.match(ignore, /^_staging\/$/m);
  assert.match(ignore, /^\.env\.\*$/m);
  await assert.rejects(() => Deno.stat("config/frontend.staging.js"));
  for (const file of ["js/config.js", "scripts/stage_site.mjs", "docs/runbooks/staging.md"]) {
    assert.ok(!(await Deno.readTextFile(file)).includes("egqclfomloqmddvlpepx.supabase.co"), `${file} has the staging URL`);
  }
});
