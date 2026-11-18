# Validator wording A/B, iteration 5 (2026-11-18)

A3 = A's criterion + the admin's «reducido en gluten» flag + canonical_wording in code, structured outputs on. OLD from the iteration 1-4 logs. RESULT: base PASS · strong FAIL (keep, resenas_celiacos: 0/4 approved vs OLD 4/4).

```
PLAN: 21 case(s), 13 distinct prompt(s), x 1 candidate arm(s) ['A3'] + OLD for 0 case(s) (reused from the log: 21), n=4 = 52 call(s) to claude-sonnet-4-6, ~US$0.57; hard cap 52 call(s) (~US$0.57)

menu_con_aviso [tacc] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.55, 0.62]

menu_con_aviso [gluten] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

menu_con_aviso [libre] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.62]

exclusivo_redes [tacc] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [gluten] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

exclusivo_redes [libre] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

web_con_protocolo [tacc] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

web_con_protocolo [gluten] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

mencion_suelta [tacc] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.25]

mencion_suelta [gluten] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

dietetica [tacc] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

dietetica [gluten] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

cocina_compartida [tacc] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 4} | level {'options_available': 4} | confidence [0.35, 0.35, 0.3, 0.35]

cocina_compartida [gluten] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

solo_geocode [tacc] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

solo_geocode [gluten] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

contradictorio [tacc] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]

contradictorio [gluten] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

bajo_en_gluten [-] — Panadería Integral Sol
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 4} | level {'options_available': 4} | confidence [0.1, 0.1, 0.1, 0.1]

dietas_especiales [-] — Restaurante Sabores
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 4} | level {'options_available': 4} | confidence [0.25, 0.25, 0.25, 0.25]

mixto_bajo_y_sin [-] — Panadería Trigal
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'discarded': 3, 'needs_review': 1} | level {'options_available': 4} | confidence [0.3, 0.55, 0.35, 0.35]

A3: PASS (0 failing check(s))

calls made: 52 of a cap of 52
RESULT: A3 PASS

PLAN: 6 case(s), 3 distinct prompt(s), x 1 candidate arm(s) ['A3'] + OLD for 0 case(s) (reused from the log: 6), n=4 = 12 call(s) to claude-sonnet-4-6, ~US$0.13; hard cap 12 call(s) (~US$0.13)

certificado [tacc] — Resto Buen Comer
  OLD (from the log): {'approved': 4, '100': 0, 'malformed': 0}
  A3: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]

certificado [gluten] — Resto Buen Comer
  OLD (from the log): {'approved': 2, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

resenas_celiacos [tacc] — Café Rambla
  OLD (from the log): {'approved': 4, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

resenas_celiacos [gluten] — Café Rambla
  OLD (from the log): {'approved': 2, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

preparacion_dedicada [tacc] — Pizzería La Esquina
  OLD (from the log): {'approved': 2, '100': 0, 'malformed': 0}
  A3: status {'approved': 3, 'needs_review': 1} | level {'celiac_friendly': 4} | confidence [0.86, 0.85, 0.85, 0.72]

preparacion_dedicada [gluten] — Pizzería La Esquina
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

A3: FAIL (2 failing check(s))
  !! FAIL: keep resenas_celiacos: tacc approved=0 vs OLD tacc 4
  !! FAIL: keep resenas_celiacos: gluten approved=0 vs OLD gluten 2

calls made: 12 of a cap of 12
RESULT: A3 FAIL
```
