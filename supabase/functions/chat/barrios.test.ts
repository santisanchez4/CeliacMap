// Tests for the barrio search by coordinates (docs/DECISIONS.md, «Barrios del chat por coordenadas»).
// Run with: deno test --no-lock -A supabase/functions/chat/
//
// The real conversation this pins (2026-11-20): «dime un lugar para cenar en Ciudad Vieja Montevideo» -> "no encontré
// nada en Ciudad Vieja, pero en Montevideo hay 50". No Google address in Montevideo names its barrio, so
// `address ilike '%Ciudad Vieja%'` found 0, and the follow-up count was the whole city with no category.
// Fixture coordinates are the real public map coordinates of those places.
import { assertEquals } from "jsr:@std/assert@1";
import { BARRIO_SHAPES } from "./barrios_data.ts";
import { BARRIO_PLACES_FIXTURE } from "./barrios_places_fixture.ts";
import { BARRIO_DISPLAY, barrioAt, NEARBY_KM, officialBarrioAt, resolveBarrio } from "./barrios.ts";
import { parseRouterOutput, searchPlacesForChat, toRedactorPlace } from "./index.ts";

// ---------------------------------------------------------------------------
// The lists and the polygons
// ---------------------------------------------------------------------------

Deno.test("62 barrios of Montevideo and 48 of CABA, each with a display name", () => {
  assertEquals(BARRIO_SHAPES.montevideo.length, 62);
  assertEquals(BARRIO_SHAPES.caba.length, 48);
  for (const key of ["montevideo", "caba"] as const) {
    assertEquals(BARRIO_SHAPES[key].map((s) => s.name).sort(), Object.keys(BARRIO_DISPLAY[key]).sort());
  }
  assertEquals(BARRIO_DISPLAY.montevideo["CORDON"], "Cordón");
  assertEquals(BARRIO_DISPLAY.caba["Nuñez"], "Núñez");
});

Deno.test("every approved place of both cities keeps the barrio the full official polygons give it", () => {
  // barrios_places_fixture.ts was computed with the unsimplified polygons by scripts/build_barrios.py --places.
  assertEquals(BARRIO_PLACES_FIXTURE.length > 100, true);
  const drift = BARRIO_PLACES_FIXTURE.filter((p) => officialBarrioAt(p.city, p.lat, p.lng) !== p.barrio);
  assertEquals(drift, []);
});

Deno.test("a point with no coordinates, or outside the city, has no barrio", () => {
  assertEquals(barrioAt("montevideo", null, null), null);
  assertEquals(barrioAt("montevideo", -34.6037, -58.3816), null); // Obelisco, Buenos Aires
  assertEquals(barrioAt("caba", -34.6037, -58.3816), "San Nicolás");
});

// ---------------------------------------------------------------------------
// resolveBarrio
// ---------------------------------------------------------------------------

const resolve = (zona: string, ciudad: string | null = null, pais: string | null = null) =>
  resolveBarrio({ zona, ciudad, pais });

Deno.test("Ciudad Vieja, Pocitos and Cordón resolve in Montevideo, with or without accents", () => {
  assertEquals(resolve("Ciudad Vieja", "Montevideo")?.names, ["CIUDAD VIEJA"]);
  assertEquals(resolve("ciudad vieja", "montevideo")?.label, "Ciudad Vieja");
  for (const zona of ["Cordón", "Cordon", "CORDON", "barrio Cordón"]) {
    assertEquals(resolve(zona, "Montevideo")?.names, ["CORDON"]);
    assertEquals(resolve(zona, "Montevideo")?.label, "Cordón");
  }
  assertEquals(resolve("Pocitos")?.city.key, "montevideo"); // unique name: no city needed
  assertEquals(resolve("Pocitos", null, "Argentina"), null);
  assertEquals(resolve("Centro", "Montevideo")?.names, ["CENTRO"]);
});

Deno.test("Palermo is decided by the city; with no city it is ambiguous and keeps the address search", () => {
  assertEquals(resolve("Palermo", "Buenos Aires")?.city.key, "caba");
  assertEquals(resolve("Palermo", "CABA")?.city.key, "caba");
  assertEquals(resolve("Palermo", "Montevideo")?.city.key, "montevideo");
  assertEquals(resolve("Palermo"), null);
  assertEquals(resolve("Palermo", null, "Argentina")?.city.key, "caba");
});

Deno.test("parts of INE's merged barrios, and names that need the city", () => {
  assertEquals(resolve("Parque Batlle", "Montevideo")?.names, ["PQUE BATLLE VILLA DOLORES"]);
  assertEquals(resolve("Prado", "Montevideo")?.label, "Prado");
  assertEquals(resolve("Colón", "Montevideo")?.names, ["COLON CENTRO Y NOROESTE", "COLON SURESTE ABAYUBA"]);
  assertEquals(resolve("Centro"), null); // every city has one
  assertEquals(resolve("La Paloma"), null); // a town in Rocha
  assertEquals(resolve("Flores", "Buenos Aires")?.names, ["Flores"]);
  assertEquals(resolve("Flores"), null); // a department of Uruguay
});

Deno.test("an unknown barrio, another city or no zona keeps today's search", () => {
  assertEquals(resolve("Microcentro", "Buenos Aires"), null);
  assertEquals(resolve("Palermo Soho", "Buenos Aires"), null); // a sub-zone is smaller than the polygon
  assertEquals(resolve("Centro", "Córdoba"), null);
  assertEquals(resolveBarrio({ zona: null, ciudad: "Montevideo", pais: "Uruguay" }), null);
});

// ---------------------------------------------------------------------------
// The search
// ---------------------------------------------------------------------------

interface FakePlace {
  id: string;
  name: string;
  city: string;
  region: string;
  country: string;
  category: string;
  safety_level: string;
  lat: number | null;
  lng: number | null;
  address: string;
}

const MVD = (id: string, name: string, category: string, lat: number, lng: number): FakePlace => ({
  id, name, city: "Montevideo", region: "Montevideo", country: "Uruguay", category, safety_level: "options_available",
  lat, lng, address: `${name} 1, 11000 Montevideo, Departamento de Montevideo, Uruguay`,
});
const BA = (id: string, name: string, category: string, lat: number, lng: number, city = "Buenos Aires"): FakePlace => ({
  id, name, city, region: "Ciudad Autónoma de Buenos Aires", country: "Argentina", category, safety_level: "options_available",
  lat, lng, address: `${name} 1, C1414 Cdad. Autónoma de Buenos Aires, Argentina`,
});

const DALBERTT = MVD("d", "Dalbertt", "restaurant", -34.9045079, -56.1995907); // Ciudad Vieja, 10 m from Centro
const MOLIENDA_SARANDI = MVD("ms", "La Molienda - Sarandí", "shop", -34.9072767, -56.2038858); // Ciudad Vieja
const LOS_LENOS = MVD("ll", "Los Leños", "restaurant", -34.9071844, -56.1966805); // Centro, 120 m from Ciudad Vieja
const RAMONA_CENTRO = MVD("rc", "Café Ramona - Centro", "cafe", -34.9073634, -56.1969872); // Centro
const BICOQUE = MVD("b", "Bicoque Gluten free", "restaurant", -34.909918, -56.1489334); // Pocitos
const DELIRIO = MVD("dl", "Delirio Sin Gluten", "restaurant", -34.912976, -56.1588556); // Pocitos
const ME_GUSTA = MVD("mg", "Me Gusta", "restaurant", -34.9045402, -56.181322); // Cordón
const SELKKIS = MVD("s", "Selkkis Gluten Free", "shop", -34.8986652, -56.1780234); // Cordón
const DELI_FOR_LIFE = MVD("dfl", "Deli for Life", "shop", -34.886226, -56.1873483); // Aguada
const MONTEVIDEO = [DALBERTT, BICOQUE, LOS_LENOS, ME_GUSTA, MOLIENDA_SARANDI, DELIRIO, RAMONA_CENTRO, SELKKIS, DELI_FOR_LIFE];

const TACCOFF = BA("t1", "TACCOFF - 100% Gluten Free", "cafe", -34.5785529, -58.4371113); // Palermo
const GOUT_PALERMO = BA("g1", "GOUT Gluten Free Palermo", "cafe", -34.5796095, -58.4248407); // Palermo
// Named "Belgrano" and on Av. Lacroze, but inside the official Palermo, 0.33 km from Belgrano.
const GOUT_BELGRANO = BA("g2", "GOUT GLUTEN FREE BELGRANO", "restaurant", -34.5672182, -58.4425144);
const TACCOUT = BA("t2", "TACCOUT", "restaurant", -34.5721186, -58.4308559); // Palermo, 1.14 km from Belgrano
const RENATITAS = BA("r", "Renatitas Pastelería Sin Tacc", "cafe", -34.5656397, -58.4592102); // Belgrano
// Same place filed with the city label the Updater wrote on 2026-11-01: found through its region.
const CABA_LABEL = BA("c", "Palermo con otra etiqueta", "cafe", -34.5790, -58.4300, "Ciudad Autónoma de Buenos Aires");
const CABA = [TACCOFF, GOUT_PALERMO, GOUT_BELGRANO, TACCOUT, RENATITAS, CABA_LABEL];

async function withFakePostgrest<T>(data: FakePlace[], run: (calls: URL[]) => Promise<T>): Promise<T> {
  const original = globalThis.fetch;
  const calls: URL[] = [];
  globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(String(input));
    calls.push(url);
    const q = url.searchParams;
    const like = (key: string) => (q.get(key) ?? "").replace(/^ilike\.\*/, "").replace(/\*$/, "").toLowerCase();
    let rows = data;
    if (q.get("city")) rows = rows.filter((p) => p.city.toLowerCase().includes(like("city")));
    if (q.get("address")) rows = rows.filter((p) => p.address.toLowerCase().includes(like("address")));
    for (const key of ["region", "country", "category", "safety_level"] as const) {
      if (q.get(key)) rows = rows.filter((p) => `eq.${p[key]}` === q.get(key));
    }
    const total = rows.length;
    rows = rows.slice(0, Number(q.get("limit") ?? 1000));
    const headers: Record<string, string> = {};
    if (new Headers(init?.headers).get("Prefer") === "count=exact") headers["content-range"] = `0-0/${total}`;
    return Promise.resolve(new Response(JSON.stringify(rows), { headers }));
  }) as typeof fetch;
  try {
    return await run(calls);
  } finally {
    globalThis.fetch = original;
  }
}

const router = (fields: Record<string, unknown>) =>
  parseRouterOutput(JSON.stringify({ modulo: "buscar", idioma: "es", ...fields }));
const search = (fields: Record<string, unknown>, message = "busco algo") =>
  searchPlacesForChat("https://x.supabase.co", "anon", router(fields), message);
const NAMES = (rows: Record<string, unknown>[]) => rows.map((r) => r.name);

Deno.test("real turn: «dime un lugar para cenar en Ciudad Vieja Montevideo» lists Dalbertt, by its coordinates", async () => {
  await withFakePostgrest(MONTEVIDEO, async (calls) => {
    const found = await search(
      { ciudad: "Montevideo", zona: "Ciudad Vieja", pais: "Uruguay", category: "restaurant" },
      "dime un lugar para cenar en Ciudad Vieja Montevideo",
    );
    assertEquals(NAMES(found.rows), ["Dalbertt"]);
    assertEquals(found.rows[0].barrio, "Ciudad Vieja");
    assertEquals(found.datosCercanos, null);
    assertEquals(found.queryLog.region_plan, "barrio");
    assertEquals(found.queryLog.barrio, "Ciudad Vieja");
    // One request: the department's places with the same category, no address filter.
    assertEquals(calls.length, 1);
    assertEquals(calls[0].searchParams.get("region"), "eq.Montevideo");
    assertEquals(calls[0].searchParams.get("category"), "eq.restaurant");
    assertEquals(calls[0].searchParams.get("address"), null);
  });
  await withFakePostgrest(MONTEVIDEO, async () => {
    const found = await search({ ciudad: "Montevideo", zona: "Ciudad Vieja", pais: "Uruguay" });
    assertEquals(NAMES(found.rows), ["Dalbertt", "La Molienda - Sarandí"]);
  });
});

Deno.test("Pocitos lists only the places inside it, each with its barrio", async () => {
  await withFakePostgrest(MONTEVIDEO, async () => {
    const found = await search({ zona: "Pocitos", pais: "Uruguay" }, "lugares sin gluten en Pocitos");
    assertEquals(NAMES(found.rows), ["Bicoque Gluten free", "Delirio Sin Gluten"]);
    assertEquals(found.rows.map((r) => r.barrio), ["Pocitos", "Pocitos"]);
  });
});

Deno.test("Cordón and Cordon find the same places", async () => {
  await withFakePostgrest(MONTEVIDEO, async () => {
    const a = await search({ ciudad: "Montevideo", zona: "Cordón" });
    const b = await search({ ciudad: "Montevideo", zona: "Cordon" });
    assertEquals(NAMES(a.rows), ["Me Gusta", "Selkkis Gluten Free"]);
    assertEquals(NAMES(b.rows), NAMES(a.rows));
    assertEquals(a.rows[0].barrio, "Cordón");
  });
});

Deno.test("Palermo, Buenos Aires: the official Palermo, through the region (a row with another city label included)", async () => {
  await withFakePostgrest(CABA, async (calls) => {
    const found = await search({ ciudad: "Buenos Aires", zona: "Palermo", pais: "Argentina" }, "dónde comer en Palermo, Buenos Aires");
    assertEquals(NAMES(found.rows), [
      "TACCOFF - 100% Gluten Free", "GOUT Gluten Free Palermo", "GOUT GLUTEN FREE BELGRANO", "TACCOUT", "Palermo con otra etiqueta",
    ]);
    assertEquals(found.rows.every((r) => r.barrio === "Palermo"), true);
    assertEquals(calls[0].searchParams.get("region"), "eq.Ciudad Autónoma de Buenos Aires");
    assertEquals(calls[0].searchParams.get("city"), null);
  });
  // Palermo of Montevideo has none of these.
  await withFakePostgrest([...CABA, ...MONTEVIDEO], async () => {
    const found = await search({ ciudad: "Montevideo", zona: "Palermo" });
    assertEquals(found.rows, []);
  });
});

Deno.test("none inside: <datos> stays empty and <datos_cercanos> names the barrios of the places near it", async () => {
  // «un restaurante en Belgrano»: Belgrano's two places are cafés; the restaurants near it are in Palermo.
  await withFakePostgrest(CABA, async () => {
    const found = await search({ ciudad: "Buenos Aires", zona: "Belgrano", category: "restaurant" }, "un restaurante en Belgrano");
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, [{ barrio: "Palermo", count: 2 }]);
    assertEquals(found.nearbyCount, 2);
    assertEquals(found.queryLog.barrio_inside, 0);
  });
  // Ciudad Vieja with only cafés asked for: Centro's café is 90 m away, Aguada's shop does not count (category).
  await withFakePostgrest(MONTEVIDEO, async () => {
    const found = await search({ ciudad: "Montevideo", zona: "Ciudad Vieja", category: "cafe" });
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, [{ barrio: "Centro", count: 1 }]);
  });
  assertEquals(NEARBY_KM, 1.5);
});

Deno.test("none inside and none near: the city's count for the same search", async () => {
  await withFakePostgrest(MONTEVIDEO, async () => {
    const found = await search({ ciudad: "Montevideo", zona: "Carrasco", category: "restaurant" });
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, { city: "Montevideo", count: 5 });
    assertEquals(found.nearbyCount, 5);
  });
  await withFakePostgrest([], async () => {
    const found = await search({ ciudad: "Montevideo", zona: "Carrasco" });
    assertEquals(found.datosCercanos, null);
  });
});

Deno.test("an unknown barrio keeps the address search, then the filtered city count", async () => {
  await withFakePostgrest(MONTEVIDEO, async (calls) => {
    const found = await search({ ciudad: "Montevideo", zona: "Malvín Alto", category: "restaurant" }, "algo en Malvín Alto");
    assertEquals(found.rows, []);
    assertEquals(found.queryLog.region_plan === "barrio", false);
    assertEquals(calls[0].searchParams.get("address"), "ilike.*Malvín Alto*");
    assertEquals(found.datosCercanos, { city: "Montevideo", count: 5 });
  });
});

Deno.test("a named lookup ignores the barrio, as it ignores the zona today", async () => {
  await withFakePostgrest(MONTEVIDEO, async (calls) => {
    const found = await search({ ciudad: "Montevideo", zona: "Pocitos", lugar_nombre: "Dalbertt" });
    assertEquals(NAMES(found.rows), ["Dalbertt"]);
    assertEquals(found.queryLog.region_plan === "barrio", false);
    assertEquals(calls[0].searchParams.get("select"), "id,name");
  });
});

Deno.test("the redactor gets the computed barrio and still nothing outside the allowlist", () => {
  const out = toRedactorPlace({ ...DALBERTT, barrio: "Ciudad Vieja", validation_notes: "x", community_warning_at: null });
  assertEquals(out.barrio, "Ciudad Vieja");
  assertEquals("validation_notes" in out, false);
  assertEquals("id" in out, false);
  assertEquals("region" in out, false);
  assertEquals("barrio" in toRedactorPlace({ name: "X" }), false);
});
