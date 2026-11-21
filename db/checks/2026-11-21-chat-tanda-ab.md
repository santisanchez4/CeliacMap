# Tanda de prompts del chat, A/B offline (2026-11-21)

`RESPONDER_PROMPT` de `feat/chat-prompts-tanda` (WORKTREE) contra `main` (= chat v29), `claude-haiku-4-5`, sin escrituras en
producción. Con el «dale» del administrador y tope de llamadas: corrida 1, 264 llamadas (~US$1,32); corrida 2, solo la celda
`solo_cerca` con el prompt nuevo, 8 llamadas (~US$0,04), con las respuestas guardadas en `2026-11-21-chat-tanda-solo-cerca.json`.

## Resultado

| Criterio | main | tanda |
|---|---|---|
| «confirmado/verificado» (lista, mezcla, solo_cerca, sin_limites, sin_ciudad) | 8, 8, 8, 8, 7 de 8 | 0 de 8 en todas |
| «sin gluten» a secas | 5/8 en solo_cerca | 0 en todas |
| Cercanos como si estuvieran en el barrio pedido | 0 | 0 |
| Cercanos con su barrio: mezcla / solo_cerca (2 lugares × 8) | 0/16 / 0/16 | 16/16 / 16/16 (*) |
| Zona sin polígono con ciudad: «no puedo filtrar» / «no hay» / ofrece Montevideo | 0 / 8 / 8 | 8 / 0 / 8 |
| Zona sin polígono sin ciudad: «no puedo filtrar» / «no hay» / pregunta la ciudad | 0 / 8 / 0 | 8 / 0 / 8 |
| ACA: dominio nuevo / viejo | 0 / 8 | 8 / 0 |
| labels (es/en × 3 niveles) | 8/8 | 8/8 |
| f4 (mg/día, 10 ppm, síntomas) | cifra 0/8, 8/8 (repite la del usuario), 0/8 | igual |
| router (3 «gracias» con borrador) | sin cambios | idéntico |
| legit (falsos positivos del guardián) | — | 0/40 |

(*) La corrida 1 dio 2/16 en solo_cerca: el detector tomaba como encabezado la línea en blanco entre «Cerca, en Palermo:» y
la lista. Las 8 respuestas guardadas de la corrida 2 nombran Palermo en el encabezado en 8/8. El detector corregido da 16/16
sobre ellas, sin volver a llamar al modelo. Lo fija `tests/test_chat_prompt_ab_detector.py`.

## Salida de la corrida 1

```
PLAN: tanda 96, labels 32, f4 48, router 48, legit 40 = 264 call(s) to claude-haiku-4-5, ~US$1.32; hard cap 264
model=claude-haiku-4-5  OLD=main  NEW=WORKTREE

=== f4: redactor, N=8 per cell ===
[mg/dia   OLD] figure 0/8 | urgency 0/8 | guard would replace 0/8
[mg/dia   NEW] figure 0/8 | urgency 0/8 | guard would replace 0/8
[10ppm    OLD] figure 8/8 | urgency 0/8 | guard would replace 8/8
[10ppm    NEW] figure 8/8 | urgency 0/8 | guard would replace 8/8
     fig: Los 10 ppm (partes por millón) son un límite legal para rotular un producto "sin gluten" en muchos países — es una concentración máxima *en el alimento*, no una dosis dia
     fig: Los 10 ppm (partes por millón) es un límite legal para rotular un producto "sin gluten" en muchos países, pero es una concentración máxima *en el alimento*, no una dosis 
[sintomas OLD] figure 0/8 | urgency 0/8 | guard would replace 0/8
[sintomas NEW] figure 0/8 | urgency 0/8 | guard would replace 0/8

=== legit: NEW prompt only, N=4 per question (any guard hit = FALSE POSITIVE) ===
[qué es la celiaquía?                                      ] guard would replace 0/4
[qué es la contaminación cruzada?                          ] guard would replace 0/4
[qué significa sin TACC?                                   ] guard would replace 0/4
[cómo leo un rótulo para saber si un producto es sin gluten] guard would replace 0/4
[en qué consiste una dieta libre de gluten?                ] guard would replace 0/4
[la avena es segura para celíacos?                         ] guard would replace 0/4
[qué cereales tienen gluten?                               ] guard would replace 0/4
[los medicamentos pueden tener gluten?                     ] guard would replace 0/4
[puedo compartir la tostadora con alguien que come gluten? ] guard would replace 0/4
[cuál es la diferencia entre celiaquía y sensibilidad al gl] guard would replace 0/4
legit total: 0/40 legitimate answers would be replaced by the fixed message

=== labels: buscar turn with one place per level, N=8 per cell ===
[es OLD gluten_free_100   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[es OLD celiac_friendly   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[es OLD options_available ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[es NEW gluten_free_100   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[es NEW celiac_friendly   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[es NEW options_available ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en OLD gluten_free_100   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en OLD celiac_friendly   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en OLD options_available ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en NEW gluten_free_100   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en NEW celiac_friendly   ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0
[en NEW options_available ] correct 8/8 | says 100%: 0 | bare label: 0 | overclaim words: 0 | not listed: 0 | ES label in EN reply: 0 | old label: 0

=== tanda: 2026-11-21 batch, N=8 per cell ===
[lista       OLD] confirm 8/8 | bare sin gluten 0/8
[lista       NEW] confirm 0/8 | bare sin gluten 0/8
[mezcla      OLD] confirm 8/8 | bare sin gluten 0/8 | near ok 0/8 | near as inside 0/8
[mezcla      NEW] confirm 0/8 | bare sin gluten 0/8 | near ok 16/8 | near as inside 0/8
[solo_cerca  OLD] confirm 8/8 | bare sin gluten 5/8 | near ok 0/8 | near as inside 0/8
[solo_cerca  NEW] confirm 0/8 | bare sin gluten 0/8 | near ok 2/8 | near as inside 0/8
[sin_limites OLD] confirm 8/8 | bare sin gluten 0/8 | cant filter 0/8 | claims none 8/8 | offers Montevideo 8/8 | asks city 0/8
[sin_limites NEW] confirm 0/8 | bare sin gluten 0/8 | cant filter 8/8 | claims none 0/8 | offers Montevideo 8/8 | asks city 0/8
[sin_ciudad  OLD] confirm 7/8 | bare sin gluten 0/8 | cant filter 0/8 | claims none 8/8 | offers Montevideo 0/8 | asks city 0/8
[sin_ciudad  NEW] confirm 0/8 | bare sin gluten 0/8 | cant filter 8/8 | claims none 0/8 | offers Montevideo 0/8 | asks city 8/8
[aca         OLD] confirm 0/8 | bare sin gluten 0/8 | new domain 0/8 | old domain 8/8
[aca         NEW] confirm 0/8 | bare sin gluten 0/8 | new domain 8/8 | old domain 0/8

=== router: thanks while a report draft is pending, N=8 ===
['genial, gracias'                  OLD] cortesia/confirma=False: 8
['genial, gracias'                  NEW] cortesia/confirma=False: 8
['mil gracias, excelente atención'  OLD] cortesia/confirma=False: 8
['mil gracias, excelente atención'  NEW] cortesia/confirma=False: 8
['dale, gracias'                    OLD] reportar/confirma=True: 8
['dale, gracias'                    NEW] reportar/confirma=True: 8
```
