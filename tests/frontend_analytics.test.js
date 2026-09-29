// Cloudflare Web Analytics: one deferred beacon with the site token, and nothing else that measures.
// No network, no browser.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_analytics.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import assert from "node:assert/strict";

const BEACON = "https://static.cloudflareinsights.com/beacon.min.js";
const TOKEN = "e3bf12852c54464e91938f7d14898f09";

const html = await Deno.readTextFile("index.html");
const { document } = parseHTML(html);

Deno.test("the Cloudflare beacon is in the page exactly once, deferred, with the site token", () => {
  const beacons = [...document.querySelectorAll("script[src]")].filter((s) => s.getAttribute("src") === BEACON);
  assert.equal(beacons.length, 1);
  const [beacon] = beacons;
  assert.ok(beacon.hasAttribute("defer"), "beacon is deferred");
  assert.equal(beacon.parentElement.tagName, "BODY");
  assert.equal(beacon, [...document.body.querySelectorAll("script")].at(-1), "beacon is the last script of the body");
  assert.deepEqual(JSON.parse(beacon.getAttribute("data-cf-beacon")), { token: TOKEN });
  assert.equal(html.split("cloudflareinsights.com/beacon").length - 1, 1);
});

Deno.test("static.cloudflareinsights.com is preconnected", () => {
  assert.ok(document.querySelector('link[rel="preconnect"][href="https://static.cloudflareinsights.com"]'));
});

Deno.test("the site's own scripts never call the beacon (no custom events, no chat or form tracking)", async () => {
  for await (const entry of Deno.readDir("js")) {
    if (!entry.name.endsWith(".js")) continue;
    const source = await Deno.readTextFile(`js/${entry.name}`);
    assert.ok(!/cloudflareinsights|__cfBeacon|cfBeacon/i.test(source), `js/${entry.name} talks to the analytics beacon`);
  }
});
