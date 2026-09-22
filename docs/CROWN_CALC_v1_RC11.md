# CROWN_CALC_v1_RC11 -- the sieve-card configuration (frozen 2026-09-17, kit v8.41, sha 77f60f2abb84e32d)

## Configuration (go_crown defaults; one bare `bash go_crown.sh` launches it)
- BSD=3: one GPU sieve daemon (gbsd.py) on the sieve card (SIEVECARD=3) at depth 10^10, serving all four cards' ready queues round-robin;
  8 CPU workers for the per-block tail (predict / rank / extract / pack / write) via shared-memory bitmaps; GPU stage serial (0.03-0.18 s/block).
- SIEVETEST=1: the sieve card also tests (the daemon takes ~6% of it).
- Selection: SELECT=12 pool, ranked by z(predicted full-window kills) - 0.6 z(rung-1 survivors); predictor tables for primes <= 1e5 (908 MB, tmpfs).
- Core reservation: feeders (and drivers) on GPUCORES=0-31; herd (700 loops), sieve daemon and workers on HERDCORES=32-255.
- Loops: v2.18 -- consume from any card's queue, wait when a daemon exists (no fallback storms), claim back-off.
- Ladder unchanged: rings 1568,4374,7244,10198,13500,17734,22818,31576, cap merit 45, 2048-bit Fermat, EE waves 6/1.15.

## Measured constants of record (box1: 4x RTX 5090, 128 physical cores)
- SUSTAINED (3 h, 2026-09-17 13:02-16:00): w/s 42.2k / 42.2k / 43.1k -> 42.5k; t/w(r1) 29.8; pass1 0.2151; all four GPUs 100%; load ~235; fallback 0.
- 40-minute reads run above sustained (46.5k / 43.3k in block 17): the herd's outer-rung population takes ~1 h to reach steady state. Use sustained.
- Selection factor (full-window sparsity, gate G-PRED on the box, fresh seed): x1.40-1.42 crown-lambda per tested window vs unselected; rung-1 ranking (RC9/RC10) was x1.15-1.16.
- Crown-effective rate = w/s x selection factor:
  RC7 41.9k x 1.00 = 41.9k | RC9 41.9k x 1.15 = 48k | RC10 41.5k x 1.16 = 48k | RC11 42.5k x 1.42 = **60k**  (x1.25 RC9, x1.44 RC7)

## Crown calculation
- Crown (median) at RC7 = 1,300 card-days (fence law, unchanged).
- RC11: 1,300 / 1.44 = **~905 card-days** -> **~28 days median on 32 cards** (eight 4-GPU boxes), 80th percentile ~45 days.
- Per 4-GPU box: 60k crown-eff. 8-GPU boxes (1 sieve : 7 testers) do NOT pay yet: the herd's CPU cost (~60 load units per card) starves seven testers. Requires the ladder manager (below).

## Corrections filed with this RC
1. `lam-eff` (w/s x pass1/0.1766) is a RUNG-1 metric; it overstated RC9/RC10 by ~15% (rung 1 is 5% of the window). Crown-effective replaces it.
2. 40-minute runner reads overstate herd-heavy configs by 10-15%; block verdicts are comparative, freezes need >= 2 h sustained.
3. Two dead-launch causes found and fixed: children inheriting onstart's singleton lock fd (every launch after a survivor exited at once), and a comment character swallowing the knob assignments. The runner now aborts loudly if a launch is not alive after 150 s.
4. Consume-or-make fallback on boxes WITH daemons caused make storms (-25% for two days). Rule: boxes with daemons wait.

## Gates passed for RC11
G-GBS-2/3 (GPU sieve byte-identical to make at 1e8/1e10), G-SV-3 (sieve card == CPU daemon at 1e10 with the predictor, 6 blocks, pooled tail), G-PRED (selection statistics on the box), blocks 16c/16d/17, 3 h sustained.

## Next (in order)
1. 48 h stability (to 2026-09-19 13:00): hourly w/s within 5% of 42.5k, fallback 0, no relaunches.
2. Ladder manager (off-box, replay-gated): one process per card, windows as in-memory state machines -> herd load ~10/card; expected +10-15% here, enables 8-GPU boxes (~24 d).
3. Papers: constants and corrections above; Zenodo/arXiv; parade pilot; rental behind the calc.
