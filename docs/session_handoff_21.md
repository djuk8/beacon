# session_handoff_21.md -- 2026-09-11 .. 09-17 (RC10 -> RC11)

## State
- Box1 on RC11 (kit v8.41 sha 77f60f2abb84e32d): sieve card, 10^10, predictor selection, core reservation. Sustained 42.5k w/s, pass1 0.2151, 60k crown-effective. Stability clock from 2026-09-17 13:02 (48 h).
- Files of record: o1_kit.tgz v8.41; CROWN_CALC_v1_RC11.md; PRED_NOTE.md; queue_block14..17.txt; experiments.log on the box.

## What happened (chronological, incidents included)
- 09-11: predictor built (C tables, ranking in the daemon), gated x1.42; block 14: predictor +7% w/s replicated on a storm-degraded base.
- 09-12/13: two days of plumbing failures, all self-inflicted and fixed: claim busy-spin (load 246), fallback make storms (62 concurrent makes, drivers starved), disk full, knob block eaten by a comment, onstart lock inherited by children (sampler) -> silent dead launches. Fixes: loops wait when daemons exist; claim back-off + any-queue; clean knob block; 9>&- on every launch; runner launch check + queue abort.
- 09-13: sieve card designed and gated (G-SV-3): one GPU sieves at 1e10 for the others. First reads showed the daemon's single-threaded tail (0.9 s/ring) as the limiter; pooled tail (8 workers via shm) -> 37.8k on 3 testers (block 16c, replicated).
- 09-14: sieve card also testing: 39.5k in 40-min reads but 33k sustained over 48 h (herd starves drivers).
- 09-17: core reservation (feeders/drivers on 0-31): 46.5k/43.3k in 40-min reads, 42.5k sustained over 3 h. Frozen as RC11.
- Box died once for credits (not code); watchdog resurrected it 33 times during that period.

## Measured facts to remember
- The herd (700 shell loops + interpreter starts) costs ~60 load units per card; it is the current wall. The ladder manager is the fix.
- Rung-1 lam-eff overstates; use crown-effective. 40-min reads overstate herd-heavy configs.
- GPU sieve on a shared card taxes testers ~40% when several daemons hammer; one daemon on a testing card costs ~6%.
- Predictor: corr -0.40 at PB 1e5; x1.42 per window; ~3 core-s per 240k block; tables shared on tmpfs.
- 25-min ledger reads are fine for comparisons, not for freezes.

## Pending
1. Stability to 09-19 13:00. 2. Ladder manager. 3. Papers/corrections, Zenodo/arXiv, parade pilot. 4. Rental: ~28 d on 32 cards at RC11; ~24 d with the ladder manager on 8-GPU boxes.
