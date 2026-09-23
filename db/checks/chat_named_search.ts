// Read-only smoke check against the same public records as the map.
// deno run --allow-read=js/config.js --allow-net db/checks/chat_named_search.ts
import { fetchSearchPlaces } from "../../supabase/functions/chat/index.ts";
import { assertEquals } from "jsr:@std/assert@1";

const config = await Deno.readTextFile("js/config.js");
const base = config.match(/SUPABASE_URL: "([^"]+)/)![1];
const key = config.match(/SUPABASE_ANON_KEY:\s*"([^"]+)/)![1];
for (const query of ["Los Lenos; Ramona; dalbert", "Dalebertt"]) {
  const rows = await fetchSearchPlaces(base, key, {
    ciudad: "Montevideo", pais: "Uruguay", lugar_nombre: query,
    zona: "Ciudad Vieja", category: "restaurant",
  });
  const names = rows.map((row) => row.name);
  assertEquals(names.includes("Dalbertt"), true);
  if (query.includes("Ramona")) {
    assertEquals(names.includes("Café Ramona - Centro"), true);
    assertEquals(names.includes("Los Leños"), true);
  }
  console.log(JSON.stringify({ query, names }));
}
