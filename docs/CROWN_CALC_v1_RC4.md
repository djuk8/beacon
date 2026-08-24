# CROWN_CALC v1-RC4 (2026-08-23) -- frozen on G-4W-final

Supersedes RC3. Every production number below is MEASURED; the only [MODEL] rows are O3/O4' projections.
Open caveat carried: G-K2 (kappa_2 at J=29,743) may multiply W_med by ~x1.05.

## 1. Measured base (gate names)
- Box1, kit v3.9 (Q=1e6, LPC=90, KWIN=250k, v3 in-driver EE, C make, shm cycle):
  **29,293 w/s = 2.531e9 windows/day = x2.02 R1** [G-4W-final 2026-08-23]
- Per saturated card: 7,310 w/s avg (7,205-7,354), 490k t/s = 95% of the 514k in-driver ceiling [G-SAT/G-R4]
- tests/window, full ladder, Q=1e6: **67.0** (ledger arithmetic 1.962M/29.29k; RC3 predicted 67.1)
- Q-scaling verified Mertens-exact: survivors/k ratio = ln Q1 / ln Q2 (117.2@1e5 -> 97.7@1e6, ratio 0.833 = ln1e5/ln1e6)
- Q=1e7 on CPU: STRUCK (memory-bandwidth wall at concurrency, MACHINERY 8.13); deep Q belongs to O3.

## 2. Crown (merit 41.9388 @ D=616; W_med = 1.176e12 windows; E = 28.16 unchanged)
windows/card-day measured: 7,310 x 86,400 = 6.316e8.
| plan | t/w | box1-days | card-days (median) | 40 cards | 80 cards | GO (<=20-22 d) |
|---|---|---|---|---|---|---|
| legacy R1 | 143 | 940 | 3,780 | 94 d | 47 d | NO |
| **today (O1+T1c), MEASURED** | **67.0** | **465** | **1,862** | **46.5 d** | **23 d** | NO / borderline |
| + O4' schedule fit [MODEL +5-10%] | 67.0, ratio->0.51 | ~430 | ~1,730 | 43 d | 21.5 d | borderline at 80 |
| + O3 landing-enum @1e9 [MODEL: Mertens 97.7->65.1 surv] | ~44.6 | ~310 | ~1,240 | 31 d | **15.5 d** | **GO at 80** |
| Plan C: decapitate #2-#6 (m>=39.7) | 67.0 | -- | ~344 | **8.6 d** | 4.3 d | **GO today** |
Cost at ~$10.5/card-day: Plan A today $19.5k; +O3 $13k; Plan C $3.6k.

## 3. The decision surface (as of this freeze)
1. **Plan C is GO on today's machine**: ~9 days median on 40 cards for five leaderboard rows. No new code needed.
2. **Plan A (crown) is a fleet question, not a software question anymore**: even with O3+O4' it wants ~80 cards
   for a comfortable GO (~15-16 d median). 40 cards never gets under the wire at any Q.
3. **O3 buys x1.5 on tests/window** [MODEL until its gate ladder runs] and, as important, makes every rented
   card cheaper forever (landing enumeration on CPU = tier 1.5 for CPU-poor boxes). Build order per MACHINERY
   10: O4' (offline, zero risk) -> O3 C library + bitmap gate vs fastmake_c -> CUDA pre-pass -> S5.
4. By-catch at Plan-A depth scales with windows: unchanged per RC2 (1.5 finds >=41, ~19 >=38 at median crown).

## 4. Standing caveats
- G-K2 open: W_med may be x1.05 (run_kappa2.py at J=29,743; queue it zero-meter).
- Fleet numbers assume boxes matching box1's w/s per card; per-box 20-min shadow remains the rule [R5 runbook].
- Soak clock restarted at the 2026-08-23 relaunch; R3 completion (48-72 h + observed resurrection) pending
  before any new box is rented [R-ladder].
