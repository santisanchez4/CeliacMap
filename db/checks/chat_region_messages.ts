// Builds the exact user messages the chat redactor receives for the department searches, by running the REAL
// code (searchPlacesForChat + buildResponderUserMessage) over fixture rows. Used by chat_region_redactor_check.py.
//
//   deno run --no-lock --no-check -A db/checks/chat_region_messages.ts < rows.json > messages.json
//
// stdin: the public rows of the places in the department (as the anon key reads them). No network, no writes.
import {
  buildResponderUserMessage,
  parseRouterOutput,
  searchPlacesForChat,
  toRedactorPlace,
} from "../../supabase/functions/chat/index.ts";

const fixture: Record<string, unknown>[] = JSON.parse(await new Response(Deno.stdin.readable).text());
const REGION = "Cerro Largo";
// A decoy in another department proves the region filter is real, not a pass-through.
const data: Record<string, unknown>[] = [
  ...fixture.map((row) => ({ ...row, region: REGION, status: "approved" })),
  { id: "decoy", name: "Decoy Montevideo", city: "Montevideo", country: "Uruguay", region: "Montevideo", category: "shop", status: "approved" },
];

globalThis.fetch = ((input: string | URL | Request) => {
  const q = new URL(String(input)).searchParams;
  let rows = data;
  if (q.get("region")) rows = rows.filter((p) => `eq.${p.region}` === q.get("region"));
  if (q.get("city")) rows = rows.filter((p) => String(p.city).toLowerCase().includes(String(q.get("city")).replace(/^ilike\.\*/, "").replace(/\*$/, "").toLowerCase()));
  if (q.get("country")) rows = rows.filter((p) => `eq.${p.country}` === q.get("country"));
  if (q.get("category")) rows = rows.filter((p) => `eq.${p.category}` === q.get("category"));
  return Promise.resolve(new Response(JSON.stringify(rows.slice(0, Number(q.get("limit") ?? 1000)))));
}) as typeof fetch;

const router = (fields: Record<string, unknown>) => parseRouterOutput(JSON.stringify({ modulo: "buscar", idioma: "es", ...fields }));

async function message(label: string, fields: Record<string, unknown>, userMessage: string) {
  const found = await searchPlacesForChat("https://x.supabase.co", "anon", router(fields), userMessage);
  return {
    label,
    plan: found.queryLog.region_plan,
    message: buildResponderUserMessage({
      modulo: "buscar", userMessage, datos: found.rows.map((r) => toRedactorPlace(r)), datosCercanos: found.datosCercanos,
    }),
  };
}

const TURN1 = "que locales puedo visitar para conseguir productos libre de gluten cerca de Fraile Muerto Cerro Largo?";
const out = [
  await message("W", { ciudad: "Fraile Muerto", zona: REGION, pais: "Uruguay", category: "shop" }, TURN1),
  await message("R", { ciudad: REGION, pais: "Uruguay", category: "shop" }, "y en cerro largo?"),
  // Control = what production sent for turn 1 before this change: nothing found, no nearby.
  {
    label: "B0",
    plan: "city (before the change)",
    message: buildResponderUserMessage({ modulo: "buscar", userMessage: TURN1, datos: [], datosCercanos: null }),
  },
];
console.log(JSON.stringify(out));
