// Android app (apps/mobile): what the APK packages, what it leaves out, the permissions it may ask for,
// and the Back button. No network, no browser, no Android toolchain.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_mobile.test.js
import { parseHTML } from "npm:linkedom@0.18.12";
import vm from "node:vm";
import assert from "node:assert/strict";
import {
  NATIVE_SCRIPT, SITE_DIRS, SITE_FILES, WEB_ONLY_FILES, appIndexHtml,
} from "../apps/mobile/scripts/web-bundle.mjs";

const MOBILE = "apps/mobile";
const html = await Deno.readTextFile("index.html");
const appHtml = appIndexHtml(html);
const manifestXml = await Deno.readTextFile(`${MOBILE}/android/app/src/main/AndroidManifest.xml`);
const config = JSON.parse(await Deno.readTextFile(`${MOBILE}/capacitor.config.json`));
const pkg = JSON.parse(await Deno.readTextFile(`${MOBILE}/package.json`));
const nativeSource = await Deno.readTextFile(`${MOBILE}/native/${NATIVE_SCRIPT}`);

const scriptSrcs = (source) =>
  [...parseHTML(source).document.querySelectorAll("script[src]")].map((s) => s.getAttribute("src"));

Deno.test("the app packages the same files GitHub Pages publishes, minus the PWA shell", async () => {
  const workflow = await Deno.readTextFile(".github/workflows/deploy-pages.yml");
  const files = workflow.match(/^\s*cp ([^\n]+?) _site\/\s*$/m)[1].trim().split(/\s+/);
  const dirs = workflow.match(/^\s*cp -r ([^\n]+?) _site\/\s*$/m)[1].trim().split(/\s+/);
  assert.deepEqual([...SITE_FILES, ...WEB_ONLY_FILES].sort(), files.sort());
  assert.deepEqual([...SITE_DIRS].sort(), dirs.sort());
  assert.deepEqual(WEB_ONLY_FILES.sort(), ["manifest.webmanifest", "service-worker.js"]);
});

Deno.test("the app's index.html has no analytics beacon and no web manifest, and is otherwise the site's page", () => {
  assert.ok(!/cloudflareinsights|cf-beacon/i.test(appHtml));
  assert.ok(!/rel="manifest"/.test(appHtml));
  const site = scriptSrcs(html).filter((src) => !src.includes("cloudflareinsights"));
  assert.deepEqual(scriptSrcs(appHtml), [...site, NATIVE_SCRIPT]);
  const kept = new Set(appHtml.split(/\r?\n/));
  const removed = html.split(/\r?\n/).filter((line) => line.trim() && !kept.has(line));
  assert.equal(removed.length, 5, "the beacon (comment + 2 lines), its preconnect and the manifest link");
  assert.ok(removed.every((line) => /cloudflare|data-cf-beacon|rel="manifest"/i.test(line)), removed.join("\n"));
});

Deno.test("the build stops if the beacon or the manifest link are no longer where it expects them", () => {
  assert.throws(() => appIndexHtml(appHtml), /expected the Cloudflare beacon exactly once, found 0/);
  assert.throws(() => appIndexHtml(html.replace('rel="manifest"', 'rel="x-manifest"')), /web manifest link/);
});

Deno.test("Capacitor serves the local copy: fixed app id, no remote URL, no bridge logging", () => {
  assert.equal(config.appId, "org.celiacmap.app");
  assert.equal(config.webDir, "www");
  assert.equal(config.server, undefined, "no server.url / allowNavigation: the WebView only loads the packaged files");
  assert.equal(config.loggingBehavior, "none");
  assert.equal(config.android.allowMixedContent, false);
});

Deno.test("Android permissions are exactly internet + foreground location; no backup, no services", () => {
  const permissions = [...manifestXml.matchAll(/<uses-permission\s+android:name="([^"]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(permissions, [
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.INTERNET",
  ]);
  assert.ok(!/BACKGROUND_LOCATION|FOREGROUND_SERVICE|<service\b|<receiver\b/.test(manifestXml));
  assert.ok(manifestXml.includes('android:allowBackup="false"'));
  assert.equal((manifestXml.match(/<activity\b/g) || []).length, 1);
});

Deno.test("dependencies are pinned and limited to Capacitor core, Android and the App plugin", () => {
  assert.deepEqual(Object.keys(pkg.dependencies).sort(), ["@capacitor/android", "@capacitor/app", "@capacitor/core"]);
  assert.deepEqual(Object.keys(pkg.devDependencies), ["@capacitor/cli"]);
  for (const version of [...Object.values(pkg.dependencies), ...Object.values(pkg.devDependencies)]) {
    assert.ok(/^\d+\.\d+\.\d+$/.test(version), `${version} is not an exact version`);
  }
  assert.equal(pkg.private, true);
});

Deno.test("the signing key stays outside the repo", async () => {
  const gradle = await Deno.readTextFile(`${MOBILE}/android/app/build.gradle`);
  assert.ok(gradle.includes('applicationId "org.celiacmap.app"'));
  assert.ok(gradle.includes("CELIACMAP_KEYSTORE_PROPERTIES"));
  assert.ok(!/storePassword\s+['"]|keyPassword\s+['"]/.test(gradle), "no password literal in build.gradle");
  const ignore = await Deno.readTextFile(".gitignore");
  for (const rule of ["apps/mobile/www/", "*.jks", "*.keystore", "keystore.properties"]) {
    assert.ok(ignore.split(/\r?\n/).includes(rule), `.gitignore lacks ${rule}`);
  }
});

Deno.test("inside the app pwa.js keeps the offline notice and registers no service worker", async () => {
  const { document } = parseHTML(html);
  const listeners = {};
  let registered = 0;
  const navigator = { onLine: false, serviceWorker: { register: async () => { registered += 1; } } };
  const window = { Capacitor: {}, addEventListener: (type, fn) => { listeners[type] = fn; } };
  vm.runInNewContext(await Deno.readTextFile("js/pwa.js"), { window, document, navigator });
  assert.equal(document.getElementById("offline-notice").hidden, false);
  assert.equal(listeners.load, undefined);
  assert.equal(registered, 0);
});

function loadNative({ withApp = true } = {}) {
  const { document } = parseHTML(html);
  const calls = { minimize: 0, clicks: [] };
  let back = null;
  const app = {
    addListener: (name, fn) => { if (name === "backButton") back = fn; },
    minimizeApp: () => { calls.minimize += 1; },
  };
  for (const id of ["chat-panel-close", "place-panel-close", "map-expand"]) {
    document.getElementById(id).click = () => {
      calls.clicks.push(id);
      if (id === "chat-panel-close") document.getElementById("chat-panel").hidden = true;
      if (id === "place-panel-close") document.getElementById("place-panel").classList.remove("is-open");
      if (id === "map-expand") document.getElementById("map-expand").setAttribute("aria-expanded", "false");
    };
  }
  const window = withApp ? { Capacitor: { Plugins: { App: app } } } : {};
  vm.runInNewContext(nativeSource, { window, document });
  return { document, calls, back: () => back() , registered: () => back !== null };
}

Deno.test("Back closes the chat, then the place panel, then the expanded map, and only then leaves the app", () => {
  const { document, calls, back } = loadNative();
  document.getElementById("chat-panel").hidden = false;
  document.getElementById("place-panel").classList.add("is-open");
  document.getElementById("map-expand").setAttribute("aria-expanded", "true");

  back(); back(); back();
  assert.deepEqual(calls.clicks, ["chat-panel-close", "place-panel-close", "map-expand"]);
  assert.equal(calls.minimize, 0);
  back();
  assert.equal(calls.minimize, 1);
  assert.equal(calls.clicks.length, 3);
});

Deno.test("native.js does nothing on the website and never touches location, storage or the network", () => {
  assert.equal(loadNative({ withApp: false }).registered(), false);
  assert.ok(!/geolocation|localStorage|sessionStorage|indexedDB|fetch\(|XMLHttpRequest|sendBeacon/.test(nativeSource));
  assert.ok(!scriptSrcs(html).includes(NATIVE_SCRIPT), "the website does not load native.js");
});
