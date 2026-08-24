# CROWN LADDER — preregistration v1.0 (2026-08-23)

## 0. Decision of record
raid610 hunting ENDS: the venue's cap (merit 37.83) is reached in the treasury (52,868 @ 37.6945). Box1
migrates to the CROWN venue on G-L1+G-L2 green. All raid610 state, fossils and the treasury are untouched.

## 1. Venue tuple (what changes, what does not)
| field | raid610 | CROWN | note |
|---|---|---|---|
| zd / d / swap / kdig / Q / bits | 1439 / 2310 / {2,3,5,7,11} / 13 / 1e6 / 2048 | same | same center, same certified P_eff, caches, C make, driver |
| MERIT cap | 37.8241 (G=53,082) | **45.0 (G~63,153, half~31,577)** | tail math: 8 d x 40 cards -> P(best>=44.8) ~ 1%; cap must not truncate the outlier |
| rungs | 7 (ETARG ..15.0) | **8 (ETARG ..15.0, 20.5)** | outer territory split so per-rung candidate counts stay driver-shaped |
| seeds | 101-460 (+702 band) | **1101-1460** (card c: 1101+90c) | clean k-band; 462-701 stays reserved for box4/5 |
| expected t/w | 67.0 measured | ~67-69 [G-V2 measures] | rung-1/2 unchanged; only e^-15 survivors pay for the width |

Open item (zero-meter, non-blocking): RC2 priced the crown at D=616; this venue is D=610.5. Merit boards are
D-blind; pricer_v1 said the cost/merit optimum is a wide plateau. Re-run pricer_v1 to confirm the delta <3%.

## 2. Design + gate ladder
- **G-L1 (design)**: `ladder_crown.py edges` on box1 (40-k dense sieve, independent code path) -> --rings
  string + ladder_crown.json + full-window E. Sanity: full-E ~ 24.7 x (31,577/26,542) ~ 29-30; edges 1-6
  within a few positions of raid610's (same targets, same physics). Freeze the printed band as the prereg band.
- **G-L2 (mint)**: first crown block minted by the production make (--merit 45.0 --rings <new>) passes
  `ladder_crown.py gate` — independent dense re-sieve, byte-compare, ring-1 cum-E within 2%.
- **G-V2 (venue pilot)**: 30-min one-card shadow on the crown config -> t/w and w/s into RC5. PASS: t/w <= 71,
  card w/s >= 6,800. Then full box via go_fourwide (VENUE=crown), soak clock continues.

## 3. What 8 days buys (40 cards, from RC4 rates, cap 45)
median best ~ 39.8; P(>=39.7 row) ~ 54%; E[>=38] ~ 3.3; P(crown >= 41.94) ~ 11%; P(>=44) ~ 2-3%.
Box1 alone meanwhile: ~1.5 finds >= 37.5/week feeding the top-20 table stays as by-catch of the same hunt.

## 4. Migration mechanics (one paste each, receipts throughout)
1. G-L1 on box1 (read-only, ~2 min).  2. Loop venue block: --merit 45.0 --rings <G-L1 output> + seed base
1101 in onstart (VENUE knob).  3. G-L2 on the first minted block.  4. G-V2 shadow, then go_fourwide.
raid610 loops are NOT restarted after the switch; their last rings drain through the feeders and fold.
