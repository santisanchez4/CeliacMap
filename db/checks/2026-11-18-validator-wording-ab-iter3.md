# Validator wording A/B, iteration 3 (2026-11-18)

Command: `python db/checks/validator_wording_ab.py --set strong --arms A --n 4 --max-calls 48`. Strong evidence the OLD RUBRIC approves. RESULT: A FAIL (keep passes; no_rise + parity fail in preparacion_dedicada).

```
PLAN: 6 case(s) x 1 candidate arm(s) ['A'] + OLD for 6 case(s) (reused from the log: 0), n=4 = 48 call(s) to claude-sonnet-4-6, ~US$0.53; hard cap 48 call(s) (~US$0.53)

certificado [tacc] — Resto Buen Comer
  OLD: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]
  A: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]

certificado [gluten] — Resto Buen Comer
  OLD: status {'needs_review': 2, 'approved': 2} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.86, 0.86]
  A: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.87, 0.87, 0.87, 0.87]

resenas_celiacos [tacc] — Café Rambla
  OLD: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.86, 0.86, 0.86, 0.86]
  A: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.86, 0.86, 0.86, 0.86]

resenas_celiacos [gluten] — Café Rambla
  OLD: status {'approved': 2, 'needs_review': 2} | level {'celiac_friendly': 4} | confidence [0.86, 0.72, 0.72, 0.86]
  A: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.86, 0.86, 0.86, 0.86]

preparacion_dedicada [tacc] — Pizzería La Esquina
  OLD: status {'approved': 2, 'needs_review': 2} | level {'celiac_friendly': 4} | confidence [0.86, 0.72, 0.72, 0.87]
  A: status {'approved': 4} | level {'celiac_friendly': 4} | confidence [0.85, 0.86, 0.85, 0.86]

preparacion_dedicada [gluten] — Pizzería La Esquina
  OLD: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]
  A: status {'needs_review': 3, 'approved': 1} | level {'celiac_friendly': 4} | confidence [0.72, 0.86, 0.72, 0.72]

A: FAIL (2 failing check(s))
  !! FAIL: no_rise preparacion_dedicada: tacc approved=4 vs OLD tacc 2
  !! FAIL: parity preparacion_dedicada: gluten approved=1 vs tacc 4

calls made: 48 of a cap of 48
RESULT: A FAIL
```
