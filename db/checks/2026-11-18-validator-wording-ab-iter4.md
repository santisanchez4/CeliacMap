# Validator wording A/B, iteration 4 (2026-11-18)

Command: `python db/checks/validator_wording_ab.py --set base --arms A2 --schema --old-log ...iter1.md --old-log ...iter2.md --n 4 --max-calls 88`. A2 = A + «Los tres términos pesan igual» + the admin's «reducido en gluten» flag, with structured outputs. RESULT: A2 FAIL (web_con_protocolo). The strong set (24 calls) was not run: A2 had already failed. Structured outputs: 88/88 replies valid.

```
PLAN: 21 case(s) x 1 candidate arm(s) ['A2'] + OLD for 1 case(s) (reused from the log: 20), n=4 = 88 call(s) to claude-sonnet-4-6, ~US$0.97; hard cap 88 call(s) (~US$0.97)

menu_con_aviso [tacc] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

menu_con_aviso [gluten] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.6]

menu_con_aviso [libre] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.6, 0.62]

exclusivo_redes [tacc] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [gluten] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [libre] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

web_con_protocolo [tacc] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.86, 0.87]

web_con_protocolo [gluten] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

mencion_suelta [tacc] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.3, 0.3, 0.3, 0.3]

mencion_suelta [gluten] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.25, 0.25, 0.25, 0.25]

dietetica [tacc] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.65, 0.62, 0.62, 0.65]

dietetica [gluten] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

cocina_compartida [tacc] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.3, 0.35, 0.35, 0.3]

cocina_compartida [gluten] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.25, 0.3, 0.25, 0.25]

solo_geocode [tacc] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

solo_geocode [gluten] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

contradictorio [tacc] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.2, 0.2, 0.15]

contradictorio [gluten] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]

bajo_en_gluten [-] — Panadería Integral Sol
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.1, 0.1, 0.1, 0.1]

dietas_especiales [-] — Restaurante Sabores
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A2: status {'discarded': 4} | level {'options_available': 4} | confidence [0.25, 0.25, 0.25, 0.25]

mixto_bajo_y_sin [-] — Panadería Trigal
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.62, 0.62, 0.62, 0.62]
  A2: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.55]

A2: FAIL (2 failing check(s))
  !! FAIL: no_rise web_con_protocolo: tacc approved=4 vs OLD tacc 0
  !! FAIL: parity web_con_protocolo: gluten approved=0 vs tacc 4

calls made: 88 of a cap of 88
RESULT: A2 FAIL
```
