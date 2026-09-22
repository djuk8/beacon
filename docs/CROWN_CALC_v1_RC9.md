# CROWN_CALC v1-RC9 (2026-09-08) -- frozen on controlled block 6 (quiet-box protocol)

Supersedes RC8. G-K2 caveat (x1.05 W_med) still open.

## 1. Measured base
- Box1, kit v8.3: venue default **SELECT=12, MAKESLOTS=64**. fm_deepen v0.4 = Franke-Kleinjung lattice walk (referee
  fk_walk.c: 50,000 random (p,s,tc), 0 mismatches) + bucketed landing application; pooled 12x make 29 s -> 6.2 s
  (sandbox), byte-identical to the certified v0.2 outputs on plain and selected blocks.
- **w/s 41.8k / 40.0k (GPU-bound, = plain base), pass1 0.2359 (x1.32 vs 0.1790), t/w(r1) 35.7 (x0.925),
  lambda-effective 55.9k / 53.4k = ~54.6k = x1.30 over RC7** (block-6 base 41.0k).
- Curve: select4 x1.14 (RC8); select12 x1.30; select24 22.4k w/s (make ~10 s + contention) -> knee = 12x.
  select12+DEEPQ 3e8: t/w 33.6 (-6%) but lam-eff 51.8k (make cost) -> depth does not pay on this arch yet.
- Card-day (lambda-equivalent) = 1.18e9 windows-equivalent.

## 2. Crown economics (W_med = 1.176e12)
| play | median cd (RC7 -> RC9) | box1 | 32 cards | 80 cards |
|---|---|---|---|---|
| CROWN >41.94 | 1,300 -> **1,000** | 250 d | **31.3 d** | 12.5 d |
| #2 >40.25 | 384 -> 295 | 74 d | 9.2 d | 3.7 d |
| #3 >39.62 | 239 -> 184 | 46 d | 5.7 d | 2.3 d |
| top-6 >38.43 | 97 -> 75 | 19 d | 2.3 d | 0.9 d |
Go-rule (<=22 d on 32 cards) needs x1.42 more: bucket sieve depth to 1e11 (x1.3, the FK walk is its inner loop)
+ cheaper first-hit making DEEPQ 3e8-1e9 free (+6-12%) + O5 pilot margin.

## 3. Ledger (Sep 7-8)
- Block 5: deeper selection lost with MORE slots (contention, r1 t/s fell to 0.67M at 180 slots) -> fix must cut
  make footprint, not add slots. Profile: 27 s make = 15.5 s C (per-prime ROW SCAN 8.9e9 iterations, not landings)
  + 10 s python/pack waste. Fixes, each gated byte-identical: pool sieved-not-packed (-26%), tight C rebuild,
  vectorized slicing, bucketed landings (-15%), FK lattice walk (x2.3 on the pooled make, x1.6 on plain).
- Prediction/actual: select12 predicted 51k lam-eff, measured 54.6k (contention fell with the make).

## 4. Queue
(1) 4-h production receipt at RC9; (2) docs + handoff 20 + memory; (3) cheaper first-hit from the FK basis
(DEEPQ 3e8/1e9 free) [+6-12% MODEL]; (4) select16 at 64 slots (+2% MODEL); (5) bucket sieve to 1e11 (x1.3 MODEL);
(6) O5 prereg + pilot; (7) rent 32 cards behind <=22-23 d.
