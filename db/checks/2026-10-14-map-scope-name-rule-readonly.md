# Regla de alcance en código sobre `places` — solo lectura (2026-10-14)

`python db/checks/map_scope_name_rule_readonly.py` · 2026-10-14 03:31 UTC

**No se escribió nada.** Un `SELECT` paginado sobre `places` (todos los estados), sin llamadas a modelos ni a Google. La regla no es retroactiva: corre antes de que el Validator llame al modelo y solo sobre filas `pending`.

- Filas leídas: 1387.
- Filas que `out_of_scope_reason` excluiría: **13**.
- Aprobadas: **0**.
- Con encabezado APROBACIÓN MANUAL / OVERRIDE MANUAL / CORRECCIÓN MANUAL: 4.
- Aprobadas o **protegidas** por una decisión manual (`manual_override_marker`): **0**. Una CORRECCIÓN MANUAL que solo dice «no aplica al mapa» es una corrección de dato y no protege la fila.

| Lugar | Ciudad, país | Estado | Regla | Encabezado manual | Protegida |
|---|---|---|---|---|---|
| Autoservicio El Ñandu (`d048a485`) | Tacuarembó, Uruguay | discarded | nombre de autoservicio / supermercado independiente | no | no |
| Carrefour Market (`beb397c0`) | La Plata, Argentina | discarded | cadena (nombre o dominio) | CORRECCIÓN MANUAL | no |
| Carrefour Market (`deeb1695`) | Mendoza, Argentina | discarded | cadena (nombre o dominio) | no | no |
| Géant Fresh Market (`9f9abf53`) | Montevideo, Uruguay | discarded | cadena (nombre o dominio) | CORRECCIÓN MANUAL | no |
| Instituto Catel (`2bed94d3`) | Montevideo, Uruguay | discarded | no vende (nombre) | no | no |
| Instituto Savez (`0cb69c96`) | Uruguay, Uruguay | discarded | no vende (nombre) | no | no |
| Supermercado Giordano (`552b9529`) | Durazno, Uruguay | discarded | nombre de autoservicio / supermercado independiente | no | no |
| Supermercado La Familiar (`0a48afe8`) | Fray Bentos, Uruguay | discarded | nombre de autoservicio / supermercado independiente | no | no |
| Supermercados El Dorado (`82c2ce01`) | Fray Bentos, Uruguay | discarded | cadena (nombre o dominio) | no | no |
| Tienda Inglesa (`1aab916e`) | Montevideo, Uruguay | discarded | cadena (nombre o dominio) | CORRECCIÓN MANUAL | no |
| Tienda Inglesa (`b735ee91`) | Punta del Este, Uruguay | discarded | cadena (nombre o dominio) | CORRECCIÓN MANUAL | no |
| Vea (`361a023a`) | Gualeguaychú, Argentina | discarded | cadena (nombre o dominio) | no | no |
| Supermercado Betel (`e83241f1`) | Fray Bentos, Uruguay | needs_review | nombre de autoservicio / supermercado independiente | no | no |
