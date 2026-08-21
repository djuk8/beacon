# SESSION HANDOFF 18 -- gate day + one-paper + crown replan
# (2026-08-21; supersedes 16a/17. Resume file. Read top-down.)

## 1. WHERE WE ARE (one paragraph)
The flagship is ONE self-contained arXiv paper, synced+committed
to the repo with licenses (Apache-2.0 code / CC BY 4.0 docs) and
a web-verified bibliography. A full gate day ran S0-S9: treasury
freeze verified intact; G-D1 closed the d-dial and corrected
Example 3.5 with measurement; the fleet's true economics were
decoded from its own manifests; O2 was retired (absorbed by O1);
O3-via-CPU was REFUTED at fleet scale; the S9 file-parse restored
the cross-validation leg (law vs Troisi's estimator vs measured
counts: 940/942/942.6) plus a free sub-Poisson variance
confirmation (Fano 0.64) of Prop 2.6's error structure.
CROWN_CALC v1-RC2 is frozen: 1,527 card-days post-O1; the fleet
reality is 5x8=40 cards; 20 days is reachable via O1+O3-GPU@1e12
(19.0d, $6.8K) or @1e9 with O4*O5 >= 1.27. Go-rule: fire only if
the gated number <= 20-22d on the contracted fleet; else Plan C
(decapitate #2-#6) or stand down.

## 2. FROZEN NUMBERS (change only via named gate verdicts)
E(41.9388 @ 616/k14/2310)=28.16; W_med=1.176e12; card-day =
4.461e10 tests. t/w: 121.2 shallow | 57.9 O1 | 38.4 +O3G@1e9 |
28.8 @1e12  =>  3,196 | 1,527 | 1,013 | 760 card-days median.
40 cards: 79.9 | 38.2 | 25.3 | 19.0 days. 80% = x2.32.
By-catch at median crown: 1.5 >=41, 3.5 >=40, 4.9 >= 39.62
(#2 line -> owns top ~6 slots), 19 >=38. t/w-independent.

## 3. GATE-DAY LEDGER (verdict : consequence)
S0 freeze-teeth ZERO ROWS : parade premise guarded.
G-D1 PASS x3 (0.9142 / 1.2904 @24.1% / 1.0050) : d-dial closed;
  Ex 3.5 corrected in-paper; Thm 3.3 invariance measured at
  finite m to 0.5%.
S2 fold-stat : beta_eff=0.01744; rung 4->5 = e^-2.414 vs design
  2.4; tests/k 120-143 (docstring 300-400 STALE -- kit fix owed).
S5 config : ladder610.json cum_e exact match; production
  --Q 100000 --deep-q 0 --deep-from-ring 99 (fastmake
  shallow-only contract is WHY).
S6-S8 combined_sieve : built (explicit targets; needs libgmp/
  sqlite3/primesieve dev; t<=16; unknowns/ dir; -u filename
  form; mstart+minc<=1e10; gcd(SL,K)=1 -> SL=26620).
  Marginal cost 5.55 core-ms/window => O3-CPU REFUTED at fleet
  scale (feed math: 25.9k w/s appetite vs 64-core supply).
S9 file-parse : 942.6 (N=437) vs 942 (his est) vs 940 (T1);
  1065.9/1060/1057 @1e8; depth ratio 0.887 vs 0.889; Fano 0.64
  sub-Poisson -> paper Sec 5.6. P-S7a restored via real counts.

## 4. CORRECTIONS FILED THIS SESSION (C = Claude)
Ex3.5 "8.3% discount" refuted by G-D1 (C). S-W invocation in
3.2 proof unnecessary (C). "saving X/Y" misread -> premature
S7 PASS retracted then restored by S9 (C). P-S8a cost prereg
refuted 5.55 vs <=2.0 (C; ~173ns/search vs 10ns guess). Stale
docstring 300-400 treated as baseline (C). O1xO2 stacking
double-counted (C; O2 retired-absorbed). Certified 2,100
silently assumed Q=1e9 sieving (C) -> three-row honest table.
min-round=entry-ring heuristic (C). tail-only log filter ate
diagnoses (C). bash brace-closure bug in runner v1 (C).
"nine-year" -> "since 2017" (paper).

## 5. PAPER STATE
arxiv track at v0.5 + D1 + Sec 5.6, committed. Theorems: 3.2
exact class-average (CRT-only), 3.3 invariance + probabilistic
form (smooth term ~24% of E, not boundary), Cor 3.4, Ex 3.5
(measured split), Prop 2.6 (PGF; exact iff Poisson; factorial
cumulants). Asymptotics quarantined to (H1),(H2),Conj 3.9.
Bib verified (Granville/Cramer/Shanks/FGKT/Maynard/FGKMT/BFT/
Troisi/Gapcoin/Nicely). Licenses landed. export_public.sh
MISSING on shredder -- regenerate at export step. Remaining
paper work: LaTeX conversion at content freeze; Zenodo DOI slot.

## 6. BUILD ORDER (next sessions)
wk1  O1 early-exit driver vs g1_fermat_v2 (+make/drive
     pipelining). Gate: G-A0-class corpus 2,008,000 verdicts
     zero mismatch + 1-hr shadow on box1 (~$100).
wk1  O4 asymmetric-completion optimal-stopping DP on exact
     rho(j). PREREG BANDS FIRST, then compute. Zero meter.
wk2  O3-GPU in-driver deep sieve. Gate: byte-match vs S7/S8
     unknowns files (mstart<=1e10) + T1 canary at production
     mstart; depth 1e9 then 1e12 probe (host primesieve
     streaming). O3b fork-patch (mstart cap + 128-bit audit)
     only if production integration prefers combined_sieve.
wk2  O5 swap sweep pilot (box1, one bay).
then CROWN_CALC v1 FINAL (green gates only) -> both sign ->
     hash -> rent 5x8, >=3 landlords, pilot + observed
     resurrection each -> fire.

## 7. STANDING QUEUE (unchanged, background)
R2 salvage crontab; R5 kit freeze/runbook; k-recovery RNG
replay (box1 dirs w5001-5004/w51xx -- do not overwrite);
mono receipts; census stragglers (waves/, beacon_box3.tgz,
bench/kit3/eu/CGBN); claimchecks vs gaps.db + staging 84,777;
parade timing (Renyer active); fold-stat docstring fix in kit.

## 8. DOCTRINE (additions this week, non-negotiable)
One runner, one log, one paste. Syntax-gate every shell
deliverable (bash -n + smoke) and ship as a downloadable file.
Read the source before guessing (gap_common.cpp:890 lesson).
Capture head+tail of failing runs. Frozen-doc numbers change
only by citing a named gate verdict. Prereg bands before
computing your own levers (O4 will demonstrate).
