// Tests for department / province search in the chatbot (docs/DECISIONS.md, "Búsqueda por departamento / provincia").
// Run with: deno test --no-lock -A supabase/functions/chat/
//
// The real conversation these pin (agent_log 2026-09-25): "cerca de Fraile Muerto Cerro Largo" -> the router put
// ciudad="Fraile Muerto", zona="Cerro Largo"; "y en cerro largo?" -> ciudad="Cerro Largo"; every place there is filed
// under Melo, and `places` had no department, so both turns answered "no tengo lugares confirmados".
import { assertEquals } from "jsr:@std/assert@1";
import {
  AMBIGUOUS_REGION_NAMES,
  AR_REGIONS,
  normalizeText,
  orderRegionRows,
  planRegionSearch,
  UY_REGIONS,
  widenedLabel,
} from "./regions.ts";
import { buildPlacesSearchUrl, fetchSearchPlaces, parseRouterOutput, searchPlacesForChat } from "./index.ts";

// ---------------------------------------------------------------------------
// normalizeText
// ---------------------------------------------------------------------------

Deno.test("normalizeText drops accents and case and collapses punctuation and spaces", () => {
  assertEquals(normalizeText("Córdoba"), "cordoba");
  assertEquals(normalizeText("  Entre   Ríos! "), "entre rios");
  assertEquals(normalizeText("Treinta y Tres"), "treinta y tres");
});

// ---------------------------------------------------------------------------
// The lists
// ---------------------------------------------------------------------------

Deno.test("the region lists hold 23 provinces and 19 departments with their accented canonical names", () => {
  assertEquals(Object.keys(AR_REGIONS).length, 23);
  assertEquals(Object.keys(UY_REGIONS).length, 19);
  assertEquals(AR_REGIONS["cordoba"], "Córdoba");
  assertEquals(AR_REGIONS["entre rios"], "Entre Ríos");
  assertEquals(UY_REGIONS["paysandu"], "Paysandú");
  assertEquals(UY_REGIONS["treinta y tres"], "Treinta y Tres");
  // C.A.B.A. is a city ("Buenos Aires"), never a region the chat searches by.
  assertEquals(Object.values(AR_REGIONS).includes("Ciudad Autónoma de Buenos Aires"), false);
});

Deno.test("the ambiguous names are the ones that are also a barrio, a street, a city elsewhere or a country clash", () => {
  for (
    const name of ["flores", "florida", "colonia", "rivera", "corrientes", "misiones", "san jose", "salto", "rio negro"]
  ) assertEquals(AMBIGUOUS_REGION_NAMES.has(name), true, name);
  for (const name of ["cerro largo", "maldonado", "entre rios", "cordoba", "mendoza"]) {
    assertEquals(AMBIGUOUS_REGION_NAMES.has(name), false, name);
  }
});

// ---------------------------------------------------------------------------
// planRegionSearch
// ---------------------------------------------------------------------------

type Input = { ciudad?: string | null; zona?: string | null; pais?: string | null; message?: string };
const plan = (i: Input) =>
  planRegionSearch({ ciudad: i.ciudad ?? null, zona: i.zona ?? null, pais: i.pais ?? null, message: i.message ?? "" });
const CITY = { kind: "city" };

Deno.test("plan: the real turn 1 (city + department in zona) searches the city and widens to the department", () => {
  assertEquals(
    plan({
      ciudad: "Fraile Muerto",
      zona: "Cerro Largo",
      pais: "Uruguay",
      message: "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?",
    }),
    { kind: "fallback", target: { region: "Cerro Largo", country: "Uruguay" }, searched: "Fraile Muerto" },
  );
});

Deno.test("plan: the real turn 2 (department as ciudad) searches by region and ranks its namesake city first", () => {
  assertEquals(plan({ ciudad: "Cerro Largo", pais: "Uruguay", message: "y en cerro largo?" }), {
    kind: "region",
    target: { region: "Cerro Largo", country: "Uruguay" },
    prefer: "cerro largo",
    dropZona: false,
  });
});

Deno.test("plan: the country comes from the region when the router gave none", () => {
  const p = plan({ ciudad: "Maldonado" });
  assertEquals(p.kind === "region" && p.target, { region: "Maldonado", country: "Uruguay" });
});

Deno.test("plan: a region in zona with ciudad null is a region search (the router's usual shape for a province)", () => {
  assertEquals(plan({ zona: "Córdoba", pais: "Argentina", message: "lugares sin tacc en la provincia de Córdoba" }), {
    kind: "region",
    target: { region: "Córdoba", country: "Argentina" },
    prefer: null,
    dropZona: true,
  });
  const entreRios = plan({ zona: "Entre Ríos", pais: "Argentina" });
  assertEquals(entreRios.kind === "region" && entreRios.target.region, "Entre Ríos");
});

Deno.test("plan: 'provincia de Buenos Aires' (the marker rides inside zona) is the province, never CABA", () => {
  assertEquals(plan({ zona: "provincia de Buenos Aires", pais: "Argentina" }), {
    kind: "region",
    target: { region: "Buenos Aires", country: "Argentina" },
    prefer: null,
    dropZona: true,
  });
  // The router also files it as ciudad: an explicit marker in the message settles it.
  const p = plan({ ciudad: "Buenos Aires", pais: "Argentina", message: "lugares en la provincia de Buenos Aires" });
  assertEquals(p.kind === "region" && p.target.region, "Buenos Aires");
  assertEquals(p.kind === "region" && p.prefer, null);
});

Deno.test("plan: a bare 'Buenos Aires' is only CABA, through the city filter as today", () => {
  assertEquals(plan({ ciudad: "Buenos Aires", pais: "Argentina", message: "algo sin tacc en Buenos Aires" }), CITY);
  assertEquals(plan({ ciudad: "Buenos Aires", zona: "Mataderos", pais: "Argentina" }), CITY);
});

Deno.test("plan: an explicit marker fixes the country of Río Negro, and so does the router's pais", () => {
  const uy = plan({ ciudad: "Río Negro", message: "lugares en el departamento de Río Negro" });
  assertEquals(uy.kind === "region" && uy.target, { region: "Río Negro", country: "Uruguay" });
  const ar = plan({ ciudad: "Río Negro", message: "lugares en la provincia de Río Negro" });
  assertEquals(ar.kind === "region" && ar.target, { region: "Río Negro", country: "Argentina" });
  assertEquals(plan({ ciudad: "Río Negro", pais: "Uruguay" }).kind, "region");
  // Bare, with no country: ambiguous, so the city filter stays as today.
  assertEquals(plan({ ciudad: "Río Negro" }), CITY);
});

Deno.test("plan: a country the router gave that contradicts the region keeps the city filter", () => {
  assertEquals(plan({ ciudad: "Maldonado", pais: "Argentina" }), CITY);
  assertEquals(plan({ ciudad: "Mendoza", pais: "Uruguay" }), CITY);
});

Deno.test("plan 2b: an ambiguous ciudad is a region only when router.pais resolves it (Flores)", () => {
  // Flores is a barrio of Buenos Aires and a department of Uruguay.
  assertEquals(plan({ ciudad: "Flores", pais: "Argentina" }), CITY);
  assertEquals(plan({ ciudad: "Flores", pais: null }), CITY);
  const uy = plan({ ciudad: "Flores", pais: "Uruguay" });
  assertEquals(uy.kind === "region" && uy.target, { region: "Flores", country: "Uruguay" });
  // "departamento de Flores" is explicit: the department, in Uruguay, even with no pais.
  const marked = plan({ ciudad: "Flores", message: "algo en el departamento de Flores" });
  assertEquals(marked.kind === "region" && marked.target, { region: "Flores", country: "Uruguay" });
});

Deno.test("plan 2b: every ambiguous name behaves like Flores (no pais -> city; pais that resolves -> region)", () => {
  const cases: [string, string][] = [
    ["Florida", "Uruguay"],
    ["Colonia", "Uruguay"],
    ["Rivera", "Uruguay"],
    ["Corrientes", "Argentina"],
    ["Misiones", "Argentina"],
    ["San José", "Uruguay"],
    ["Salto", "Uruguay"],
  ];
  for (const [name, pais] of cases) {
    assertEquals(plan({ ciudad: name, pais: null }), CITY, `${name} without pais`);
    assertEquals(plan({ ciudad: name, pais }).kind, "region", `${name} + ${pais}`);
    assertEquals(plan({ ciudad: name, pais: pais === "Uruguay" ? "Argentina" : "Uruguay" }), CITY, `${name} contradicted`);
  }
});

Deno.test("plan 3: a bare region in the message widens a city that gave nothing, unless the name is ambiguous", () => {
  assertEquals(plan({ ciudad: "Fraile Muerto", message: "hay algo por Fraile Muerto en Cerro Largo?" }), {
    kind: "fallback",
    target: { region: "Cerro Largo", country: "Uruguay" },
    searched: "Fraile Muerto",
  });
  // Ambiguous, bare: never a region on its own (a barrio, a street).
  assertEquals(plan({ ciudad: "Trinidad", message: "algo cerca de Trinidad, Flores" }), CITY);
  assertEquals(plan({ ciudad: "Palermo", message: "cerca de Av. Corrientes" }), CITY);
  // The router's country still has to agree.
  assertEquals(plan({ ciudad: "Paso de los Toros", pais: "Argentina", message: "algo por Paso de los Toros, Tacuarembó" }), CITY);
});

Deno.test("plan: a real city with an explicit province in the message searches the city first, then widens", () => {
  assertEquals(
    plan({ ciudad: "Villa Carlos Paz", pais: "Argentina", message: "en Villa Carlos Paz, provincia de Córdoba" }),
    { kind: "fallback", target: { region: "Córdoba", country: "Argentina" }, searched: "Villa Carlos Paz" },
  );
});

Deno.test("plan: no region anywhere is the search of today", () => {
  assertEquals(plan({ ciudad: "Palermo", pais: "Argentina", message: "un café en Palermo" }), CITY);
  assertEquals(plan({ message: "gracias" }), CITY);
  assertEquals(plan({ ciudad: "Punta del Este", zona: "La Barra", pais: "Uruguay" }), CITY);
});

Deno.test("plan 2b: a barrio in zona stays a filter when the ciudad is a region name (Montevideo + Pocitos)", () => {
  assertEquals(plan({ ciudad: "Montevideo", zona: "Pocitos", pais: "Uruguay" }), {
    kind: "region",
    target: { region: "Montevideo", country: "Uruguay" },
    prefer: "montevideo",
    dropZona: false,
  });
});

// ---------------------------------------------------------------------------
// orderRegionRows / widenedLabel
// ---------------------------------------------------------------------------

Deno.test("orderRegionRows puts the requested city first, then the rest of the region, up to the limit", () => {
  const rows = [
    ...Array.from({ length: 5 }, (_, i) => ({ id: `vcp${i}`, city: "Villa Carlos Paz" })),
    { id: "cba1", city: "Córdoba" },
    { id: "rc1", city: "Río Cuarto" },
    { id: "cba2", city: "CORDOBA" },
    { id: "cba3", city: "cordoba" },
    { id: "rc2", city: "Río Cuarto" },
    { id: "rc3", city: "Río Cuarto" },
  ];
  assertEquals(orderRegionRows(rows, "cordoba", 8).map((r) => r.id), [
    "cba1", "cba2", "cba3", "vcp0", "vcp1", "vcp2", "vcp3", "vcp4",
  ]);
  // No preference: the database order, cut at the limit.
  assertEquals(orderRegionRows(rows, null, 3).map((r) => r.id), ["vcp0", "vcp1", "vcp2"]);
});

Deno.test("widenedLabel names the region and the cities where its places are", () => {
  assertEquals(widenedLabel("Cerro Largo", [{ city: "Melo" }, { city: "Melo" }]), { city: "Cerro Largo (Melo)", count: 2 });
  assertEquals(
    widenedLabel("Maldonado", [
      { city: "Punta del Este" }, { city: "Punta del Este" }, { city: "Maldonado" }, { city: "La Barra" }, { city: "Piriápolis" },
    ]),
    { city: "Maldonado (Punta del Este, Maldonado, La Barra)", count: 5 },
  );
  assertEquals(widenedLabel("Flores", [{ city: null }]), { city: "Flores", count: 1 });
  assertEquals(widenedLabel("Flores", []), { city: "Flores", count: 0 });
});

// ---------------------------------------------------------------------------
// The URL and the orchestration, against a fake PostgREST that reads the real query strings
// ---------------------------------------------------------------------------

interface FakePlace {
  id: string;
  name: string;
  city: string;
  region: string;
  country: string;
  category: string;
  address?: string;
  status?: string;
  safety_level?: string;
}

const place = (id: string, name: string, city: string, region: string, country: string, category = "shop",
  more: Partial<FakePlace> = {}): FakePlace => ({ id, name, city, region, country, category, address: `${name} 1, ${city}`, ...more });

// Rows are listed in the order the database would return them (vote_count desc), which is what the chat relies on.
async function withFakePostgrest<T>(
  data: FakePlace[],
  run: (calls: URL[]) => Promise<T>,
): Promise<T> {
  const original = globalThis.fetch;
  const calls: URL[] = [];
  globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(String(input));
    calls.push(url);
    const q = url.searchParams;
    const like = (key: string) => (q.get(key) ?? "").replace(/^ilike\.\*/, "").replace(/\*$/, "").toLowerCase();
    let rows = data.filter((p) => (p.status ?? "approved") === "approved");
    if (q.get("city")) rows = rows.filter((p) => p.city.toLowerCase().includes(like("city")));
    if (q.get("address")) rows = rows.filter((p) => (p.address ?? "").toLowerCase().includes(like("address")));
    if (q.get("id")) rows = rows.filter((p) => (q.get("id") ?? "").slice(4, -1).split(",").includes(p.id));
    if (q.get("region")) rows = rows.filter((p) => `eq.${p.region}` === q.get("region"));
    if (q.get("country")) rows = rows.filter((p) => `eq.${p.country}` === q.get("country"));
    if (q.get("category")) rows = rows.filter((p) => `eq.${p.category}` === q.get("category"));
    if (q.get("safety_level")) rows = rows.filter((p) => `eq.${p.safety_level}` === q.get("safety_level"));
    const total = rows.length;
    rows = rows.slice(Number(q.get("offset") ?? 0), Number(q.get("offset") ?? 0) + Number(q.get("limit") ?? 1000));
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

const MELO_1 = place("m1", "EMPATIA GLUTEN FREE", "Melo", "Cerro Largo", "Uruguay", "shop");
const MELO_2 = place("m2", "Gluten Free | Sandra | Productos", "Melo", "Cerro Largo", "Uruguay", "shop");
const MELO_CAFE = place("m3", "Café Melo", "Melo", "Cerro Largo", "Uruguay", "cafe");
const CERRO_LARGO = [MELO_1, MELO_2, MELO_CAFE];
const NAMES = (rows: Record<string, unknown>[]) => rows.map((r) => r.name);

Deno.test("buildPlacesSearchUrl filters by region instead of city, and can raise the limit", () => {
  const url = new URL(
    buildPlacesSearchUrl("https://x.supabase.co", { region: "Entre Ríos", pais: "Argentina", category: "shop", limit: 500 }),
  );
  assertEquals(url.searchParams.get("region"), "eq.Entre Ríos");
  assertEquals(url.searchParams.get("country"), "eq.Argentina");
  assertEquals(url.searchParams.get("city"), null);
  assertEquals(url.searchParams.get("category"), "eq.shop");
  assertEquals(url.searchParams.get("limit"), "500");
  // Untouched by default: the top-eight cap.
  assertEquals(new URL(buildPlacesSearchUrl("https://x.supabase.co", { ciudad: "Palermo" })).searchParams.get("limit"), "8");
});

Deno.test("real turn 1: Fraile Muerto finds nothing, so the redactor gets the department's count and its cities, not the places", async () => {
  await withFakePostgrest([...CERRO_LARGO, place("x1", "Otro", "Montevideo", "Montevideo", "Uruguay")], async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co",
      "anon",
      router({ ciudad: "Fraile Muerto", zona: "Cerro Largo", pais: "Uruguay", category: "shop" }),
      "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?",
    );
    assertEquals(found.rows, []);
    // category=shop is kept: the count is what the follow-up "¿cuáles?" would list.
    assertEquals(found.datosCercanos, { city: "Cerro Largo (Melo)", count: 2 });
    assertEquals(found.nearbyCount, 2);
    assertEquals(found.queryLog.region, "Cerro Largo");
    assertEquals(found.queryLog.region_plan, "fallback");
    // The city was searched first. The only select=id request is the category_zero count (no category, limit 1); the old
    // same-city nearby count (no country, no order) did not run.
    assertEquals(calls[0].searchParams.get("city"), "ilike.*Fraile Muerto*");
    const idCalls = calls.filter((u) => u.searchParams.get("select") === "id");
    assertEquals(idCalls.length, 1);
    assertEquals(idCalls[0].searchParams.get("category"), null);
    assertEquals(idCalls[0].searchParams.get("country"), "eq.Uruguay");
    assertEquals(found.queryLog.category_zero, true);
    assertEquals(found.queryLog.count_without_category, 0);
  });
});

Deno.test("real turn 2: 'y en cerro largo?' lists the department's places, in Melo, as datos", async () => {
  await withFakePostgrest(CERRO_LARGO, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co",
      "anon",
      router({ ciudad: "Cerro Largo", pais: "Uruguay", category: "shop" }),
      "y en cerro largo?",
    );
    assertEquals(NAMES(found.rows), ["EMPATIA GLUTEN FREE", "Gluten Free | Sandra | Productos"]);
    assertEquals(found.rows.every((r) => r.city === "Melo"), true);
    assertEquals(found.datosCercanos, null);
    assertEquals(found.queryLog.region_plan, "region");
    assertEquals(calls[0].searchParams.get("region"), "eq.Cerro Largo");
    assertEquals(calls[0].searchParams.get("country"), "eq.Uruguay");
    assertEquals(calls[0].searchParams.get("city"), null);
  });
});

Deno.test("2b (a): 'Córdoba' with more than eight places in the province returns the capital's first", async () => {
  const data = [
    ...Array.from({ length: 6 }, (_, i) => place(`v${i}`, `Carlos Paz ${i}`, "Villa Carlos Paz", "Córdoba", "Argentina")),
    ...Array.from({ length: 3 }, (_, i) => place(`c${i}`, `Capital ${i}`, "Córdoba", "Córdoba", "Argentina")),
    ...Array.from({ length: 3 }, (_, i) => place(`r${i}`, `Cuarto ${i}`, "Río Cuarto", "Córdoba", "Argentina")),
    place("caba", "Av Córdoba", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina"),
  ];
  await withFakePostgrest(data, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Córdoba", pais: "Argentina" }), "algo en Córdoba",
    );
    assertEquals(found.rows.length, 8);
    assertEquals(NAMES(found.rows).slice(0, 3), ["Capital 0", "Capital 1", "Capital 2"]);
    assertEquals(NAMES(found.rows).slice(3), ["Carlos Paz 0", "Carlos Paz 1", "Carlos Paz 2", "Carlos Paz 3", "Carlos Paz 4"]);
    // More than eight were fetched to be able to rank them.
    assertEquals(calls[0].searchParams.get("limit"), "500");
    assertEquals(found.rows.some((r) => r.name === "Av Córdoba"), false);
  });
});

Deno.test("2b: a region search by ciudad has no widening label (the person asked for that name)", async () => {
  await withFakePostgrest([place("p1", "Uno", "Punta del Este", "Maldonado", "Uruguay"), place("p2", "Dos", "Maldonado", "Maldonado", "Uruguay")],
    async () => {
      const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Maldonado", pais: "Uruguay" }), "algo en Maldonado");
      assertEquals(NAMES(found.rows), ["Dos", "Uno"]);
      assertEquals(found.datosCercanos, null);
    });
});

Deno.test("2b (b): 'Flores' with Argentina, or with no country, is searched by city exactly as today", async () => {
  const data = [place("f1", "Trinidad Sin Gluten", "Trinidad", "Flores", "Uruguay")];
  await withFakePostgrest(data, async (calls) => {
    for (const pais of ["Argentina", null]) {
      const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Flores", pais }), "algo en Flores");
      assertEquals(found.rows, []);
      assertEquals(found.queryLog.region_plan, "city");
    }
    assertEquals(calls[0].searchParams.get("city"), "ilike.*Flores*");
    assertEquals(calls[0].searchParams.get("country"), "eq.Argentina");
    assertEquals(calls[1].searchParams.get("city"), "ilike.*Flores*");
    assertEquals(calls[1].searchParams.get("country"), null);
    assertEquals(calls.every((u) => u.searchParams.get("region") === null), true);
  });
  await withFakePostgrest(data, async () => {
    const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Flores", pais: "Uruguay" }), "algo en Flores");
    assertEquals(NAMES(found.rows), ["Trinidad Sin Gluten"]);
  });
});

Deno.test("a bare 'Buenos Aires' stays CABA through the city filter; the province needs its marker", async () => {
  const data = [
    place("b1", "Palermo GF", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina"),
    place("b2", "La Plata GF", "La Plata", "Buenos Aires", "Argentina"),
  ];
  await withFakePostgrest(data, async () => {
    const caba = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Buenos Aires", pais: "Argentina" }), "algo en Buenos Aires");
    assertEquals(NAMES(caba.rows), ["Palermo GF"]);
    const province = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ zona: "provincia de Buenos Aires", pais: "Argentina" }), "lugares en la provincia de Buenos Aires",
    );
    assertEquals(NAMES(province.rows), ["La Plata GF"]);
    assertEquals(province.queryLog.region_plan, "region");
  });
});

Deno.test("a named lookup inside a department scans that department, not a city called like it", async () => {
  await withFakePostgrest(CERRO_LARGO, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon",
      router({ ciudad: "Cerro Largo", pais: "Uruguay", lugar_nombre: "Empatia" }), "Empatia en Cerro Largo",
    );
    assertEquals(NAMES(found.rows), ["EMPATIA GLUTEN FREE"]);
    assertEquals(calls[0].searchParams.get("select"), "id,name");
    assertEquals(calls[0].searchParams.get("region"), "eq.Cerro Largo");
  });
});

Deno.test("the search of today is unchanged: a barrio with no results still gets the city-level count", async () => {
  const data = [place("g1", "Palermo GF", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina"),
    place("g2", "Caballito GF", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina")];
  await withFakePostgrest(data, async () => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Buenos Aires", zona: "Mataderos", pais: "Argentina" }), "algo en Mataderos",
    );
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, { city: "Buenos Aires", count: 2 });
    assertEquals(found.nearbyCount, 2);
    assertEquals(found.queryLog.region_plan, "city");
  });
  // No barrio, no nearby lookup: nearbyCount stays null (logged as nearby_count: null, as before).
  await withFakePostgrest(data, async () => {
    const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Buenos Aires", pais: "Argentina" }), "algo");
    assertEquals(found.nearbyCount, null);
    assertEquals(found.datosCercanos, null);
  });
});

Deno.test("a failed department summary never fails the turn", async () => {
  const original = globalThis.fetch;
  let n = 0;
  globalThis.fetch = (() => (++n === 1
    ? Promise.resolve(new Response("[]"))
    : Promise.resolve(new Response("unavailable", { status: 503 })))) as typeof fetch;
  try {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Fraile Muerto", zona: "Cerro Largo", pais: "Uruguay" }), "Fraile Muerto Cerro Largo",
    );
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, null);
  } finally {
    globalThis.fetch = original;
  }
});

Deno.test("fetchSearchPlaces still ranks by the requested city when called with a region", async () => {
  const data = [place("a", "Fuera", "Villa Carlos Paz", "Córdoba", "Argentina"), place("b", "Dentro", "Córdoba", "Córdoba", "Argentina")];
  await withFakePostgrest(data, async () => {
    const rows = await fetchSearchPlaces("https://x.supabase.co", "anon", { region: "Córdoba", pais: "Argentina", regionPrefer: "cordoba" });
    assertEquals(NAMES(rows), ["Dentro", "Fuera"]);
  });
});

// ---------------------------------------------------------------------------
// Telemetry: a category that found nothing (docs/DECISIONS.md, "`category_zero` telemetry"). The log only ever
// showed what the router filtered by, never whether the filter hid anything. Nothing that is returned or shown to the
// redactor may change: only queryLog gains fields, and only when a category was set, gave 0 rows and it was no name lookup.
// ---------------------------------------------------------------------------

const CENTRO = [
  place("c1", "Café Uno", "Montevideo", "Montevideo", "Uruguay", "cafe"),
  place("c2", "Café Dos", "Montevideo", "Montevideo", "Uruguay", "cafe"),
  place("c3", "Resto Tres", "Montevideo", "Montevideo", "Uruguay", "restaurant"),
];
const isCountCall = (u: URL) => u.searchParams.get("select") === "id" && u.searchParams.get("limit") === "1";

Deno.test("category_zero: a category with 0 rows counts the same search without it, and returns exactly what it did before", async () => {
  await withFakePostgrest(CERRO_LARGO, async (calls) => {
    // Melo is a city, not a department: the search is by city.
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Melo", pais: "Uruguay", category: "restaurant" }), "restaurantes en Melo",
    );
    // What the person and the redactor get is untouched: no rows, no nearby figure.
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, null);
    assertEquals(found.nearbyCount, null);
    // The log says the filter emptied a city that has places (a number only comes back when Prefer: count=exact was sent).
    assertEquals(found.queryLog.region_plan, "city");
    assertEquals(found.queryLog.category, "restaurant");
    assertEquals(found.queryLog.category_zero, true);
    assertEquals(found.queryLog.count_without_category, 3);
    // The extra request: same city and country, no category, one row asked for.
    const count = calls.filter(isCountCall);
    assertEquals(count.length, 1);
    assertEquals(count[0].searchParams.get("city"), "ilike.*Melo*");
    assertEquals(count[0].searchParams.get("country"), "eq.Uruguay");
    assertEquals(count[0].searchParams.get("category"), null);
    assertEquals(count[0].searchParams.get("status"), "eq.approved");
  });
});

Deno.test("category_zero: 0 without the category too is logged as 0 (nothing there, not hidden)", async () => {
  await withFakePostgrest(CENTRO, async () => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Chuy", pais: "Uruguay", category: "cafe" }), "cafes en Chuy",
    );
    assertEquals(found.rows, []);
    assertEquals(found.queryLog.category_zero, true);
    assertEquals(found.queryLog.count_without_category, 0);
  });
});

Deno.test("category_zero: a department search counts by region, not by a city called like it", async () => {
  await withFakePostgrest(CERRO_LARGO, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Cerro Largo", pais: "Uruguay", category: "restaurant" }), "restaurantes en Cerro Largo",
    );
    assertEquals(found.rows, []);
    assertEquals(found.queryLog.region_plan, "region");
    assertEquals(found.queryLog.category_zero, true);
    assertEquals(found.queryLog.count_without_category, 3);
    const count = calls.filter(isCountCall)[0];
    assertEquals(count.searchParams.get("region"), "eq.Cerro Largo");
    assertEquals(count.searchParams.get("country"), "eq.Uruguay");
    assertEquals(count.searchParams.get("city"), null);
    assertEquals(count.searchParams.get("category"), null);
  });
});

Deno.test("category_zero: the count keeps the barrio and the 100% level, and nivel is now in the log", async () => {
  const data = [
    place("k1", "Pocitos 100", "Montevideo", "Montevideo", "Uruguay", "cafe", { address: "Benito Blanco 1, Pocitos", safety_level: "gluten_free_100" }),
    place("k2", "Pocitos opciones", "Montevideo", "Montevideo", "Uruguay", "cafe", { address: "Benito Blanco 2, Pocitos", safety_level: "options_available" }),
    place("k3", "Centro 100", "Montevideo", "Montevideo", "Uruguay", "cafe", { address: "18 de Julio 1, Centro", safety_level: "gluten_free_100" }),
  ];
  await withFakePostgrest(data, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon",
      router({ ciudad: "Montevideo", pais: "Uruguay", zona: "Pocitos", category: "shop", nivel: "100" }), "solo 100% en Pocitos",
    );
    assertEquals(found.queryLog.nivel, "100");
    assertEquals(found.queryLog.count_without_category, 1);
    const count = calls.filter(isCountCall)[0];
    assertEquals(count.searchParams.get("safety_level"), "eq.gluten_free_100");
    assertEquals(count.searchParams.get("address"), "ilike.*Pocitos*");
  });
});

Deno.test("nivel is always in the log: null when the search did not ask for 100%", async () => {
  await withFakePostgrest(CENTRO, async () => {
    const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Montevideo", pais: "Uruguay" }), "algo");
    assertEquals(found.queryLog.nivel, null);
    assertEquals(found.rows.length, 3);
  });
});

Deno.test("category_zero: the count runs only when a category was set, gave 0 rows and it was not a name lookup", async () => {
  // No category: 0 rows is not a category problem.
  await withFakePostgrest(CENTRO, async (calls) => {
    const found = await searchPlacesForChat("https://x.supabase.co", "anon", router({ ciudad: "Chuy", pais: "Uruguay" }), "algo en Chuy");
    assertEquals(calls.length, 1);
    assertEquals("category_zero" in found.queryLog, false);
    assertEquals("count_without_category" in found.queryLog, false);
  });
  // A category that found rows.
  await withFakePostgrest(CENTRO, async (calls) => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Montevideo", pais: "Uruguay", category: "cafe" }), "cafes en Montevideo",
    );
    assertEquals(found.rows.length, 2);
    assertEquals(calls.length, 1);
    assertEquals("category_zero" in found.queryLog, false);
    assertEquals("count_without_category" in found.queryLog, false);
  });
  // A name lookup already ignores the category, so an empty result is not the category's doing.
  for (const names of [{ lugar_nombre: "Inexistente" }, { texto_libre: "Inexistente" }]) {
    await withFakePostgrest(CENTRO, async (calls) => {
      const found = await searchPlacesForChat(
        "https://x.supabase.co", "anon", router({ ciudad: "Montevideo", pais: "Uruguay", category: "shop", ...names }), "Inexistente",
      );
      assertEquals(found.rows, []);
      assertEquals(calls.filter(isCountCall).length, 0);
      assertEquals("category_zero" in found.queryLog, false);
    });
  }
});

Deno.test("category_zero: the barrio nearby count and its datos_cercanos are unchanged, and the category count runs beside them", async () => {
  const data = [place("g1", "Palermo GF", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina", "cafe"),
    place("g2", "Caballito GF", "Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Argentina", "restaurant")];
  await withFakePostgrest(data, async () => {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon",
      router({ ciudad: "Buenos Aires", zona: "Mataderos", pais: "Argentina", category: "cafe" }), "cafes en Mataderos",
    );
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, { city: "Buenos Aires", count: 2 });
    assertEquals(found.nearbyCount, 2);
    assertEquals(found.queryLog.category_zero, true);
    // Mataderos matches no address, with or without the category.
    assertEquals(found.queryLog.count_without_category, 0);
  });
});

Deno.test("category_zero: a failed count never fails the turn nor changes what it returns", async () => {
  const original = globalThis.fetch;
  let n = 0;
  globalThis.fetch = (() => (++n === 1
    ? Promise.resolve(new Response("[]"))
    : Promise.resolve(new Response("unavailable", { status: 503 })))) as typeof fetch;
  try {
    const found = await searchPlacesForChat(
      "https://x.supabase.co", "anon", router({ ciudad: "Montevideo", pais: "Uruguay", category: "shop" }), "locales en Montevideo",
    );
    assertEquals(found.rows, []);
    assertEquals(found.datosCercanos, null);
    assertEquals(found.queryLog.category_zero, true);
    assertEquals(found.queryLog.count_without_category, null);
  } finally {
    globalThis.fetch = original;
  }
});
