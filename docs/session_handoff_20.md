# session_handoff_20.md — BEACON state as of 2026-09-09 (RC9 frozen; bucket sieve gated; block 9 running)

Resume file. Supersedes handoff 19. Numbers are MEASURED unless tagged [MODEL]. Author: C; reviewed by Mario.

## 1. One paragraph
Box1 hunts the crown at **RC9** (SELECT=12 MAKESLOTS=64 DEEPQ=1e8; kit v8.3+): ~41k w/s, pass1 0.236 (x1.32),
lambda-effective ~54k = **x1.30 over RC7**; crown median ~1,000 card-days = 31 d on 32 cards. Fleet reality: ~32 cards
rentable, so the go-rule (<=22 d) needs x1.42 more per card. The build for that -- a **persistent bucket sieve per card**
-- is written, referee-certified at every module, gated byte-identical on the box at 1e8 and identity-gated at 1e10, and
is running as controlled block 9 (queue_block9.txt) as this handoff is written. Harvest 0908: 197 new finds; campaign
ledger dedup -> **4,578 claimable first-occurrence rows at 610 digits** (+ merit-37 treasury rows), parade-ready pending a
fresh gaps.db recheck. Mario's sequence: close the gap -> publish -> parade -> campaign.

## 2. The experiment runner and the quiet-box protocol (how everything since Sep 4 was measured)
- `exp.sh NAME KEY=VAL...` relaunches with env overrides, settles, reads the ledger, appends one line to
  `~/beacon/raid610/experiments.log`: w/s, r1 t/s, t/w(r1), pass1, lam-eff w/s, megas, make_s, config.
  `expq.sh queue.txt` runs a list unattended. Knobs: KWIN CHUNK GROWTH MAKESLOTS EXTRA DEEPQ TMAX R1FEEDERS SELECT DEEPR
  BSD BSDQ BSDT SETTLE FM_DENSE_GUARD. ~60 experiments over 5 days.
- **Quiet-box protocol (Mario):** during a block NOTHING else runs on the box (no probes, harvests, builds). Reads have
  +/-3-5% day-to-day drift at the same config: promote only on replicated lines against same-block baselines.
- Baseline bracket lines (`base`, `rc9`) always open and close a block.

## 3. Verdicts of record (Sep 4-9)
- Feed knobs (KWIN/TMAX/R1FEEDERS/CHUNK+GROWTH/EXTRA/MAKESLOTS): all within noise -> GPU-bound plateau. 6/1.15 optimal both sides.
- **Regression bisected:** v7.7 js2 "density guard" forced the slow per-k path (41.9k -> 30k). Removed.
- **Selection** (SELECT_PREREG): pilot x1.33 pass at decile, rung-independent (1.055+/-0.07). Production: pass x1.21 (4x)
  ... x1.32 (12x) ... x1.38 (24x). Deployment limited by pooled-make cost: RC8 = select4/100 slots (x1.14);
  after the FK deepen, RC9 = select12/64 slots (x1.30). select24 still loses (make ~10 s).
- **Slot curve is contention, not feed:** more slots than needed reduce GPU serving (r1 t/s falls). The fix is always
  a cheaper/smaller make, never more slots.
- **fm_deepen v0.4 = Franke-Kleinjung lattice walk + bucketed landings** (fk_walk.c referee 50k trials): 12x make
  29 s -> 6.2 s (sandbox); plain make 5.0 -> 3.1 s. Byte-identical.
- **Rung-2 deepen: -15% replicated** (make 4.9 vs 1.9 s under load; mechanism = probable loop-cycle supply latency,
  untested). DEEPR stays 1. Annulus deepen is certified and free once sieving is persistent.
- **Per-block depth (DEEPQ 3e8/1e9): -17% / -52%**: the per-prime wall (~30 s makes at 1e9 under 64-way load).
  Depth exists only through the persistent sieve. (Block 8.)
- **Rung profile (RUNG_PROFILE_NOTE.md):** measured E per ring 1.69/1.71/1.99/2.42/3.01/4.17/6.27 at 28e9 windows vs
  the ladder DESIGN 1.7/1.7/2.0/2.4/3.0/4.2/5.5 -> design confirmed to 1% through ring 6 (largest validation of the
  construction's E-accounting). Correction by name (C): my "flat 1.72 per ring" claim was wrong. Windows failing
  their last rung are REPLAYED after relaunch (2 windows x 6) -> loop must mark finished windows (todo).
- Cards power-capped 600 W (perf/W regime); NUMA membind -6%; P3 geometry optimal; CGBN has no squaring (shelved);
  size re-site wash (E45 32.31 vs 30.62). All filed.

## 4. The bucket sieve (BUCKET_SIEVE_STATUS.md; kit v8.6-8.14)
- **bsieve.c**: one record per prime (p, next landing (t,i), FK basis) in the bucket of its landing's BLOCK; per block:
  pop, FK-walk landings in O(1) each into per-chunk landing buffers, flush cache-locally, push to next block.
  Per-prime work once at init (~0.3-0.7 us/prime). 10 ns/landing. Landings BURST when the step is small -> ring spans
  ~p/T blocks. Chunk-granular BUCKETS lose (record traffic); chunk-granular LANDING BUFFERS win.
- **bs_api.c**: threaded partition of the prime range (ROUND-ROBIN -- index ranges put 40-60% of landings in one
  partition and capped scaling at ~0.85 s), private all-ones bitmaps + parallel AND-merge (atomics into a shared bitmap
  were SLOWER: +35%/landing and cache-line ping-pong). Box scaling: 2.25/0.60/0.37/0.45 s at P=1/4/8/16.
- **bsd.py**: daemon per card (seeds 2001-2004), one progression each, three-stage pipeline (shallow js2 || sieve ||
  pack), emits selected rings (byte-identical to `make --select 12`) into `ready/c$c`; loop v2.12 consumer mode claims
  by atomic rename. Ring-to-ring on the box ~0.5-0.9 s at 8 threads (need ~0.6 s at 1e10).
- **Gates:** referee 466M checks (small p) + large-p referees to 1e10 (fh_big.c, bs_bigp.c); make-level identity at 1e8
  sandbox + box (G-BSD-2); depth identity at 1e10 vs js2@1e6+certified deepen (G-BSD-4 PASS, density 58.89 = Mertens).
  **Gate lessons:** (1) a crashed cache build left a plausible zero-filled table -> all cache builds now atomic
  (.part + rename); (2) js2 is NOT a valid reference above ~2^31 (64-bit products overflow) -> the deepen (128-bit) is;
  (3) compare js as SETS (packer order != sieve order); (4) residue tables above 2^31 must be int64 (built directly).
- Memory: 48 B/record -> 22 GB per daemon at 1e10 (4 daemons ~90 GB; fine on box1 and 256-GB rentals); pack to 24 B later.
  Init 455M primes ~5 min per daemon (SETTLE=900 in exp lines).
- **Block 9 (running):** rc9 | bsd1e8 (feed effect alone) | bsd1e10 | bsd1e10_t12 | rc9_b | bsd1e10_b.
  Model: t/w(r1) 35.7 -> ~28.6, pass1 ~0.24, lam-eff x1.25 over RC9 if fed -> RC10 ~x1.6 over RC7, ~25 d on 32 cards.

## 5. Harvest / parade
- Harvest 0908 (1,244 r7/r8 manifests, path-list method; salvage_v1 `--manifests 'glob'`): 197 new finds, best
  46,220@32.91. Campaign ledger deduped by k -> claimcheck (`claimcheck_harvest.py ledger_dedup.log /dev/null
  arbitrage_map_v0.csv --digits 610`): **4,578 claimable rows**. Treasury rows in the same ledger: 52,868@37.69,
  52,376@37.34, 51,432@36.67 (all-time top-15 class as of the last sync).
- Parade protocol: fresh gaps.db + staging -> regenerate map -> recheck; pilot of 5 rows, one observed merge; batches of
  a few hundred with per-batch claimchecks incl. our own earlier batches; tribute post after first merges. Timing = Mario.
- Weekly: harvest (box tar by path list -> shredder -> salvage_v1 -> claimcheck -> append to campaign ledger).

## 6. Queue
1. Block 9 read -> RC10 freeze (calc + 4-h receipt) or diagnosis.
2. Loop: mark finished windows (no replays); runner pid file; harvest cron on shredder. Record packing (24 B).
3. Selection deeper than 12x on the daemon (free now): select 24 (+4% pass [MODEL]).
4. O5 swap prereg + 24-h pilot (margin).
5. Papers: RC constants; selection note; rung-profile note (+correction); FK/bucket-sieve notes; js2 range note;
   Appendix A; reword "theater". Zenodo DOI -> arXiv -> parade -> rent 32 cards behind <=22-23 d.
6. Later: manifest v2 (binary js sidecar; JSON is the remaining Python cost); C residue builder (11 min -> 2 min per box);
   mono line sieve-side levers on shredder; GPU-NTT moonshot; k-tuples note.

## 7. Files of record (outputs)
o1_kit.tgz v8.14 (8a3d2676ad90a28d); CROWN_CALC_v1_RC9.md; SELECT_PREREG.md (with results); RUNG_PROFILE_NOTE.md;
BUCKET_SIEVE_STATUS.md; bsieve.c bs_api.c bsd.py fk_walk.c bs_bigp.c fh_big.c; queue_block1..9.txt; select_pilot.py;
salvage_v1.py; claimcheck_harvest.py; arbitrage_map_v0.csv; VRAM_ARCH_v1.md; session_handoff_19.md.
