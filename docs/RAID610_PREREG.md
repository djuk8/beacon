# RAID610_PREREG.md -- all-time merit raid, 610-digit theater
Preregistered 2026-08-08, BEFORE any meter. Discoverer: Djuk8.
Freeze discipline: every find BANKS; claimcheck (gaps.db + portal
staging) before any submission; parade sequencing unaffected.

## OBJECTIVE
RUNG 1 (PILOT + first campaign rung): first gap with merit > 37.8241
at D ~ 610 -> enters the all-time merit top-10 (current #10: 8382 @
97d, Jacobsen 2018). Portal-native: normal queue, notary C?d.
RUNG 2 (post-confirm): merit > 39.6202 -> all-time #2 (same config
family, E_best 26.18, margin +5.7).
CROWN (41.9388): separate siege decision, NOT part of this prereg.

## CONFIG (bridge-certified 2026-08-08, map gate 3/3 PASS)
zd = 1439, swap T = {2,3,5,7,11} (MJ), d = 2310, kdig = 13
per-k target: G_k = first even gap with G_k / ln(n0_k) > 37.8241
  (ln n0 ~ 1,404.6; G ~ 53,130; candidates ~2,026 bits -> 2048 class)
deep sieve Q = 1e6 (regime-inverted: tests near-free at this class;
  deep sieving buys nothing -- MEASURED economics, not habit)
ring ladder: from planner at cum-E ~ {1.7, 3.4, 5.2, 7.2, 9.6, 12.5,
  16.5, 24.7} [planner emits exact edges; fold band-check per ring]

## PREDICTIONS [flags]
E_best = 24.67; absolute E = 24.7-25.1 (E_mean - 0.35 selection-bias
  rule)                                             [EXACT-SIEVE]
windows N = e^E / A = 6.4e9 - 2.6e10               [A 2-8 MEASURED at
  frontier; D-transfer MODEL]
T_w ~ 166 tests/window @ Q=1e6                     [ladder ratio 2.9
  MEASURED @2705d; D-transfer MODEL]
total tests 1.1e12 - 4.3e12
wall: 4x5090 @ 516,358 t/s MEASURED -> 6-24 days; 12 cards -> 2-8
sieve ops ~ N x pi(1e6) = 5e14 - 2e15 int-ops (hours-scale on CPU
  quota IF the factory implementation reaches vectorized rates)

## DECLARED UNKNOWNS -- what the 1-card pilot MEASURES
U1. Factory throughput: windows/s/core of the minted scanhunt make at
    the 2048 class. Regime-inversion risk: at ~12,500 windows/s per
    4 cards the factory may be the meter, not the GPU.
U2. Block/IO shape: KB sizing at ~4,000x the strike's window rate
    (ring-1 ~ 97 cands/window ~ 25 KB/window; KB=3e5 start ~ 7.5 GB
    ring-1 file; 157-GB-fossil lesson applies -- grep-verify KB).
U3. End-to-end GPU duty cycle (make+fold+IO overhead vs 516k t/s).
U4. c_w at E ~ 25 (walk-model middle limb; free from fold logs).

## GATE LADDER (all green before 4-card ignition)
G-F1 mint byte-identity: minted candidate stream vs reference python
     generator, >= 1e5 candidates, 0 mismatches, exit-2-on-empty.
G-F2 ladder certification: exact sieve of 50 sample windows; per-ring
     cum-E within 2% of design.
G-L1 1-card livefire >= 1 h: fold round-1 E_meas in design band
     +/- 0.05; zero GEC alarms; U1-U3 measured and logged.

## CONFIRM -> CAMPAIGN
All gates green AND first folds in-band -> scale to 4 cards (rung 1).
Post-strike, +8 cards optional. Rung 2 follows rung 1's find under
the same prereg family. Any deviation from band: stop, diagnose,
re-prereg. No overclaim; corrections filed by name.

## BUILD LIST (the mint -- driver needs NOTHING, 2048 benched)
B1. scanhunt make: 2048-bit container path (256 B/cand) + config
    plumbing (zd/d/kdig/per-k G/ring edges from planner).
B2. Fold: verify 2048 container read + MAGIC_V (landmine 7).
B3. KB + block cadence per U2; duty instrumentation for U3.
