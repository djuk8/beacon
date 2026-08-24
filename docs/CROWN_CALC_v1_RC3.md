# CROWN_CALC v1-RC3 (proposal, 2026-08-22) -- measured O1 numbers replace RC2 models

Status: PROPOSAL. RC2 stays frozen until the gate verdicts below are named in the ledger.
Changes vs RC2 are marked [MEASURED gate] or [MODEL]. Physics constants unchanged.

## 1. Constants carried from RC2 (unchanged)
- Target: merit 41.9388 @ D=616, k14/2310.  E = 28.16.
- W_med = 1.176e12 windows (median to crown).
- card-day = 4.461e10 tests (516,358 t/s @2048-bit).  Measured v3 in-driver: 514,170 t/s [G-R4 R3]. Consistent; keep 4.461e10.

## 2. Tests per window -- MEASURED (ledger_c0, 2026-08-22 19:33-19:53, 600 rung-1 rings, all rungs)
| rung | cands/window (legacy would test) | tested/window (early exit) |
|---|---|---|
| r1 | 117.3 | 65.4 |
| r2 | 20.8 | 11.7 |
| r3 | 4.4 | 2.2 |
| r4 | 0.73 | 0.33 |
| r5-r7 | 0.09 | 0.03 |
| **total** | **143.3** | **79.7** |
Test ratio 0.556 (stable across every read since 08-21). RC2 rows: 121.2 shallow as-deployed, 57.9 post-O1 -- both superseded:
legacy as-deployed is 143 t/w (RC2's 121 counted rung 1 only), post-O1 is 79.7 t/w [G-S5 + shadow ledger].

## 3. Card rate -- MEASURED
- Saturated card under v3 in-driver early exit: 514k t/s / 79.7 t/w = **6,450 w/s per card** [G-R4 R3 + ledger t/w].
- Shadow at 30 loops: 4,220 w/s (feed-bound, card 65%); 90-loop read pending = the saturation confirmation gate [G-SAT].
- Feed: ~4-5 loop-cores per saturated card with the C make [G-M1 x3.1 whole-make] (RC2 assumed 45).

## 4. Crown medians (40 contracted cards = 10 x 4-card boxes)
| plan | t/w | card-days (median) | days on 40 cards | GO-rule (<=20-22 d) |
|---|---|---|---|---|
| legacy, as deployed | 143 | 3,780 | 94 | NO |
| **Plan A, O1 (today, measured)** | **79.7** | **2,110** | **53** | **NO** |
| Plan A + O3-GPU @1e9 [MODEL: RC2 ratio 38.4/57.9 applied] | 53 | 1,400 | 35 | NO |
| Plan A + O3-GPU @1e12 [MODEL: 28.8/57.9] | 40 | 1,050 | 26 | NO (borderline) |
| + O4 DP x1.0-1.4 + O5 swap x1.05-1.2 [MODEL] | 24-38 | 640-1,000 | 16-25 | borderline -> GO at 60 cards |
| **Plan C: decapitate #2-#6 (m>=39.7)** [RC2 7 d scaled by 79.7/57.9] | 79.7 | ~390 | **~10** | **GO** |
Card-day cost at ~$0.44/card-h (TW box, cores included): Plan A-O1 ~$22k median, A+O3 ~$11-15k, Plan C ~$4k.

## 5. What the numbers say
1. O1 alone (early exit + C make) is real and banked: x1.8 tests/window, card saturated at 514k t/s, feed decoupled from cores. It does not, by itself, bring the crown under the GO rule on 40 cards (53 d median).
2. O3-GPU is required for Plan A: it is the only lever that changes t/w by more than the O4/O5 margins, and it also removes the CPU constraint entirely (8-card boxes at card price). Even then Plan A is borderline at 40 cards; GO at 60-80 cards or with O4/O5 measured, not modelled.
3. Plan C is GO today with O1 alone (~10 d median on 40 cards): five leaderboard rows (#2-#6) for the cost of about one week of the contracted fleet.
4. The by-catch numbers in RC2 (1.5 finds >=41, 4.9 >= #2-line, 19 >=38 at median crown) scale with windows, not tests -- unchanged per window; at Plan-C depth they are what is actually being hunted.

## 6. Gates that would freeze RC3
- [G-SAT] 90-loop shadow read: rung-1 w/s >= 6,000 on one card with queue not starved -> confirms row 3.
- [G-4W] four-wide 2 h read: box w/s and box-wide t/w within 5% of card x4.
- [G-K2] kappa_2 at J=29,743 (run_kappa2.py) -- still open from RC2; enters as a multiplier on W_med (expected x1.05).
- O3-GPU rows stay [MODEL] until the O3 gate ladder exists.
