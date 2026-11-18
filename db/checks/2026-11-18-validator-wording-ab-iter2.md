# Validator wording A/B, iteration 2 (2026-11-18)

Command: `python db/checks/validator_wording_ab.py --arms B,A --old-log db/checks/2026-11-18-validator-wording-ab-iter1.md --n 4 --max-calls 168`. OLD reused from iteration 1 except the two controls. RESULT: B FAIL · A PASS.

```
PLAN: 20 case(s) x 2 candidate arm(s) ['B', 'A'] + OLD for 2 case(s) (reused from the log: 18), n=4 = 168 call(s) to claude-sonnet-4-6, ~US$1.85; hard cap 168 call(s) (~US$1.85)

menu_con_aviso [tacc] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 1, 'celiac_friendly': 3} | confidence [0.62, 0.62, 0.62, 0.6]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.62, 0.62, 0.62, 0.62]

menu_con_aviso [gluten] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.55]
  A: status {'needs_review': 4} | level {'celiac_friendly': 2, 'options_available': 2} | confidence [0.6, 0.6, 0.6, 0.62]

menu_con_aviso [libre] — Café Plaza
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'celiac_friendly': 3, 'options_available': 1} | confidence [0.55, 0.55, 0.55, 0.55]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.6, 0.55, 0.55, 0.6]

exclusivo_redes [tacc] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [gluten] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [libre] — Panadería La Espiga
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

web_con_protocolo [tacc] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]
  A: status {'needs_review': 3, 'approved': 1} | level {'celiac_friendly': 4} | confidence [0.72, 0.86, 0.72, 0.72]

web_con_protocolo [gluten] — Resto Lo de Ana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

mencion_suelta [tacc] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 3, 'discarded': 1} | level {'options_available': 4} | confidence [0.52, 0.52, 0.25, 0.52]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.25, 0.25, 0.25, 0.25]

mencion_suelta [gluten] — Bar El Puerto
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]

dietetica [tacc] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

dietetica [gluten] — Dietética Vida Sana
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

cocina_compartida [tacc] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

cocina_compartida [gluten] — Pizzería Don Carlos
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 3, 'discarded': 1} | level {'options_available': 4} | confidence [0.52, 0.35, 0.52, 0.52]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

solo_geocode [tacc] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

solo_geocode [gluten] — Pastelería Dulce Vida
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

contradictorio [tacc] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.15, 0.2]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]

contradictorio [gluten] — Heladería Polo
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  B: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.2, 0.15, 0.2]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]

bajo_en_gluten [-] — Panadería Integral Sol
  OLD: status {'discarded': 2} | level {'options_available': 2} | confidence [0.15, 0.15] | MALFORMED 2
  B: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]

dietas_especiales [-] — Restaurante Sabores
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]
  B: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]
  A: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]

B: FAIL (2 failing check(s))
  !! FAIL: no_rise web_con_protocolo: tacc approved=4 vs OLD tacc 0
  !! FAIL: parity web_con_protocolo: gluten approved=0 vs tacc 4

A: PASS (0 failing check(s))

calls made: 168 of a cap of 168
RESULT: B FAIL · A PASS
```
