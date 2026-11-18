# Validator wording A/B, iteration 6 (2026-11-18): isolating the A3 failures

Two combinations on the two failing cases, canonical_wording on: (1) A + structured outputs, without the admin's flag; (2) A3 without structured outputs. 16 calls.

```
=== arms: A --schema · set strong · case resenas_celiacos

resenas_celiacos [tacc] — Café Rambla
  OLD (from the log): {'approved': 4, '100': 0, 'malformed': 0}
  A: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

resenas_celiacos [gluten] — Café Rambla
  OLD (from the log): {'approved': 2, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

A: FAIL (2 failing check(s))
  !! FAIL: keep resenas_celiacos: tacc approved=0 vs OLD tacc 4
  !! FAIL: keep resenas_celiacos: gluten approved=0 vs OLD gluten 2

calls made: 4 of a cap of 4
RESULT: A FAIL
=== arms: A --schema · set base · case mixto_bajo_y_sin

mixto_bajo_y_sin [-] — Panadería Trigal
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A: status {'needs_review': 4} | level {'options_available': 4} | confidence [0.62, 0.62, 0.62, 0.62]

A: PASS (0 failing check(s))

calls made: 4 of a cap of 4
RESULT: A PASS
=== arms: A3 · set strong · case resenas_celiacos

resenas_celiacos [tacc] — Café Rambla
  OLD (from the log): {'approved': 4, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.72, 0.72, 0.72, 0.72]

resenas_celiacos [gluten] — Café Rambla
  OLD (from the log): {'approved': 2, '100': 0, 'malformed': 0}
  same prompt as [tacc]: results reused, no call

A3: FAIL (2 failing check(s))
  !! FAIL: keep resenas_celiacos: tacc approved=0 vs OLD tacc 4
  !! FAIL: keep resenas_celiacos: gluten approved=0 vs OLD gluten 2

calls made: 4 of a cap of 4
RESULT: A3 FAIL
=== arms: A3 · set base · case mixto_bajo_y_sin

mixto_bajo_y_sin [-] — Panadería Trigal
  OLD (from the log): {'approved': 0, '100': 0, 'malformed': 0}
  A3: status {'needs_review': 4} | level {'celiac_friendly': 4} | confidence [0.55, 0.55, 0.52, 0.52]

A3: PASS (0 failing check(s))

calls made: 4 of a cap of 4
RESULT: A3 PASS
```
