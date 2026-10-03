// Pure distance helpers behind «Cerca mío» (js/geo.js). No DOM, no network.
// deno test --allow-read --no-lock --node-modules-dir=none tests/frontend_geo.test.js
import vm from "node:vm";
import assert from "node:assert/strict";

const window = {};
vm.runInNewContext(await Deno.readTextFile("js/geo.js"), { window });
const geo = window.CeliacGeo;

Deno.test("distanceKm is the great-circle distance", () => {
  const montevideo = { lat: -34.9011, lng: -56.1645 };
  const buenosAires = { lat: -34.6037, lng: -58.3816 };
  const km = geo.distanceKm(montevideo, buenosAires);
  assert.ok(km > 204 && km < 207, String(km));
  assert.equal(geo.distanceKm(montevideo, montevideo), 0);
  const oneHundredth = geo.distanceKm({ lat: -34.9, lng: -56.16 }, { lat: -34.91, lng: -56.16 });
  assert.ok(Math.abs(oneHundredth - 1.112) < 0.002, String(oneHundredth));
});

Deno.test("formatDistance always says it is a straight line, in Spanish and English", () => {
  assert.equal(geo.formatDistance(0.26, 20, "es"), "A 250 m en línea recta");
  assert.equal(geo.formatDistance(0.26, 20, "en"), "250 m away in a straight line");
  assert.equal(geo.formatDistance(1.234, 20, "es"), "A 1,2 km en línea recta");
  assert.equal(geo.formatDistance(1.234, 20, "en"), "1.2 km away in a straight line");
  assert.equal(geo.formatDistance(12.6, 20, "es"), "A 13 km en línea recta");
  assert.equal(geo.formatDistance(0.03, 10, "es"), "A menos de 50 m en línea recta");
  assert.equal(geo.formatDistance(0.03, 10, "en"), "Less than 50 m away in a straight line");
  assert.equal(geo.formatDistance(0.98, 20, "es"), "A 1,0 km en línea recta");
});

Deno.test("formatDistance is never more precise than the reading", () => {
  assert.equal(geo.formatDistance(0.26, 150, "es"), "A 300 m en línea recta");
  assert.equal(geo.formatDistance(0.08, 150, "es"), "A menos de 100 m en línea recta");
  assert.equal(geo.isApproximate(1000), false);
  assert.equal(geo.isApproximate(1500), true);
  assert.equal(geo.formatDistance(2.4, 1500, "es"), "A unos 2 km en línea recta");
  assert.equal(geo.formatDistance(0.3, 3000, "en"), "About 1 km away in a straight line");
});

Deno.test("nearest keeps places inside the radius, nearest first, ties by name, up to the limit", () => {
  const origin = { lat: -34.9, lng: -56.16 };
  const items = [
    { place: { id: "far", name: "Far", lat: -34.99, lng: -56.16 } },
    { place: { id: "b", name: "B", lat: -34.91, lng: -56.16 } },
    { place: { id: "a", name: "A", lat: -34.91, lng: -56.16 } },
    { place: { id: "near", name: "Near", lat: -34.901, lng: -56.16 } },
    { place: { id: "bad", name: "Bad", lat: null, lng: -56.16 } },
  ];
  const found = geo.nearest(items, origin, 5, 10);
  assert.deepEqual([...found.map((r) => r.item.place.id)], ["near", "a", "b"]);
  assert.ok(found[0].km < found[1].km);
  assert.deepEqual([...geo.nearest(items, origin, 20, 2).map((r) => r.item.place.id)], ["near", "a"]);
  assert.equal(geo.nearest(items, { lat: NaN, lng: 0 }, 5, 10).length, 0);
  assert.equal(geo.nearest(items, null, 5, 10).length, 0);
});

Deno.test("geo.js has no DOM, network or storage access", async () => {
  const source = await Deno.readTextFile("js/geo.js");
  assert.ok(!/document\.|fetch\(|XMLHttpRequest|localStorage|sessionStorage|indexedDB|navigator/.test(source));
});
