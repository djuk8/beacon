# SELECT_PREREG.md — sparse-window selection at rung 1 (preregistration, 2026-09-04, C)

## Claim under test
Windows whose rung-1 survivor count S (after Q=1e8) is low have lower E1 = beta*S and therefore a higher P(pass r1)
and fewer EE tests -- WITHOUT changing the pass probability of later rungs (independence). If true, testing only
the sparsest fraction f of sieved windows raises lambda per GPU-second at rung 1 by (pass_sel/pass_ctl)/(tests_sel/tests_ctl).
Scope note: the retired "Score" result was a 14-sigma null on predicting RECORD-class outcomes from window features;
this test asks a narrower throughput question at rung 1 and checks rung-2 independence explicitly.

## Protocol (select_pilot.py; one card, ~15 min; no theater freeze -- verdicts are contention-independent)
1. Pool: 12 production blocks (seeds 9400-9411, kblock 20000, Q=1e6 + deep 1e8, js2) = ~99.7k windows.
2. Arms: SEL = the 8,312 windows with the smallest S (bottom ~8.3%); CTL = 8,312 windows drawn uniformly from the pool.
3. Both arms written as synthetic rings (bin + manifest), full-tested by the certified driver (legacy mode, all
   candidates) on GPU 3; EE tests per window computed as the ideal center-out first-hit index (same rule both arms).
4. Rung-2 independence: survivors of each arm -> make --round 2 (FM_JS2=0, scattered ks) -> full test -> pass2.

## Predictions (written before data)
- CTL: mean S ~73.4, pass1 = 0.177 +/- 0.005 (n=8,312), EE tests/window ~38.6.
- SEL: mean S ~62-64 (-12 to -16%); pass1 = 0.22-0.24 (+25-35%); EE tests/window 32-34 (-12 to -16%).
- pass2(SEL survivors) within +/-10% of pass2(CTL survivors) if rungs are independent.

## Decision rule
PASS  : pass1_sel/pass1_ctl >= 1.15 AND tests_sel/tests_ctl <= 0.92 AND |pass2_sel/pass2_ctl - 1| <= 0.10
  -> production candidate: select the bottom quartile-to-decile (cost: 4-12 extra makes per tested block; at ~5 s
     js2 makes that is 88-264 cores at 4.4 rings/s -> quartile is the affordable default; decile needs shallow-S
     ranking at Q=1e6, ~1 s/make). Predicted box gain: quartile x1.3-1.4, decile x1.45-1.5 [MODEL].
FAIL  : pass1 ratio < 1.08, or tests ratio > 0.95, or rung-2 anti-correlation > 10% -> selection retired for good,
  filed next to Score with the numbers.
INCONCLUSIVE otherwise -> rerun with a 24-block pool.

## RESULT (2026-09-05, box1 GPU 3, pool 12 blocks = 99.7k windows, n = 8,312 per arm, GPU verdicts)
SEL: mean S 61.2, pass1 0.2459 +/- 0.0047, tests/w 33.4, survivors 2,044
CTL: mean S 73.2, pass1 0.1849 +/- 0.0043, tests/w 35.2, survivors 1,537
pass ratio 1.330 (band 1.25-1.35: HIT, ~10 sigma) | tests ratio 0.949 (band 0.84-0.88: MISSED -- prereg model error:
EE cost ~ geometric 1/beta search, only passing windows save tests; corrected expectation ~0.95) | rung-2 pass2 ratio
1.055 +/- 0.07 (band 0.90-1.10: HIT). Letter of the rule: INCONCLUSIVE (tests criterion). Substance: the selection
effect is real and rung-independent; lambda per GPU-second at rung 1 = x1.40 (decile). Filed as a MEASURED lever.
Deployment: decile needs ~12x sieving -> not affordable with per-block makes (~260 cores) -> affordable interim =
quartile (4 blocks/ring, ~70 cores, x1.29 [MODEL]); full value arrives with the bucket sieve (cost ∝ landings):
bucket 1e11 (x1.38) x selection decile (x1.40) ~ x1.9 per card [MODEL] -> 32 cards ~21 d crown median.
