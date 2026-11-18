# Validator wording A/B, iteration 1 (2026-11-18)

Command: `python db/checks/validator_wording_ab.py --old-rev main --n 4 --max-calls 160`. Stopped at bajo_en_gluten: one model reply was malformed JSON (not retried). RESULT: FAIL (see the analysis in docs/DECISIONS.md).

```
PLAN: 20 case(s) x 2 arm(s) x n=4 = 160 call(s) to claude-sonnet-4-6, ~US$1.76; hard cap 160 call(s) (~US$1.76)

menu_con_aviso [tacc] — Café Plaza
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.62, 0.62, 0.62, 0.62]
  NEW: status {'needs_review': 4} | level {'options_available': 2, 'celiac_friendly': 2} | confidence [0.62, 0.62, 0.62, 0.62]

menu_con_aviso [gluten] — Café Plaza
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.55]
  NEW: status {'needs_review': 4} | level {'options_available': 3, 'celiac_friendly': 1} | confidence [0.6, 0.62, 0.62, 0.62]

menu_con_aviso [libre] — Café Plaza
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.55]
  NEW: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.62, 0.62, 0.62, 0.6]

exclusivo_redes [tacc] — Panadería La Espiga
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  NEW: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [gluten] — Panadería La Espiga
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  NEW: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

exclusivo_redes [libre] — Panadería La Espiga
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  NEW: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

web_con_protocolo [tacc] — Resto Lo de Ana
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  NEW: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]

web_con_protocolo [gluten] — Resto Lo de Ana
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  NEW: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

mencion_suelta [tacc] — Bar El Puerto
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

mencion_suelta [gluten] — Bar El Puerto
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.15, 0.15, 0.15]
  NEW: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]

dietetica [tacc] — Dietética Vida Sana
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]
  NEW: status {'approved': 4} | level {'options_available': 4} | confidence [0.86, 0.86, 0.86, 0.86]

dietetica [gluten] — Dietética Vida Sana
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.6, 0.55, 0.55, 0.6]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

cocina_compartida [tacc] — Pizzería Don Carlos
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.55, 0.55, 0.55, 0.55]

cocina_compartida [gluten] — Pizzería Don Carlos
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

solo_geocode [tacc] — Pastelería Dulce Vida
  OLD: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.55]

solo_geocode [gluten] — Pastelería Dulce Vida
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.35, 0.35, 0.35, 0.35]
  NEW: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.52, 0.52, 0.52, 0.52]

contradictorio [tacc] — Heladería Polo
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]
  NEW: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.15, 0.2]

contradictorio [gluten] — Heladería Polo
  OLD: status {'discarded': 4} | level {'options_available': 4} | confidence [0.15, 0.15, 0.15, 0.15]
  NEW: status {'discarded': 4} | level {'options_available': 4} | confidence [0.2, 0.2, 0.2, 0.2]

bajo_en_gluten [-] — Panadería Integral Sol
```
