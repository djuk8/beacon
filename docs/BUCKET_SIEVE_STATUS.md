# BUCKET_SIEVE_STATUS.md -- persistent bucket sieve, CPU-RAM tier (C, 2026-09-08 evening)

## What exists (all in the sandbox, all gated)
- **bsieve.c** -- the core. Per prime ONE record (p, next landing (t,i), FK basis a0,a1,b0,b1) living in the bucket of its
  landing's block. Per block: pop the bucket, emit each record's landings in the block (FK walk along t, O(1) each) into
  per-chunk landing buffers, flush chunk-locally to the block bitmaps, push the record to its next block. Per-prime
  work is paid once at init (first landing via the certified fm_next_hit + FK reduce, ~300 ns/prime).
- **Referee** (`-DBS_REFEREE`): random small progressions, 4 consecutive blocks each, every (t,i) bit vs brute force:
  400 trials / 338M checks / 0 mismatches (block-level buckets); 150 trials / 128M / 0 (each later variant).
- **Make-level identity**: production block (seed 7302, 12x, 99,740 coprime windows): bucket path (js2 shallow ->
  bitmaps -> bsieve (1e6,1e8]) == js2 + fm_deepen(1e8) on EVERY window, EVERY j. PASS.
- **bs_api.c** -- ctypes surface (create on a progression, apply block to caller bitmaps).
- **bs_bench.c** -- bench: 12x block (T=240k, I=1569) at 1e8: init 1.7 s once; **1.1-1.2 s per block, 10 ns/landing**
  (fm_deepen v0.4: ~4.5 s for the same block). Cost ∝ landings only: 1e10 ~ x1.75 landings -> ~2 s/block [MODEL].

## Facts the build must carry
- Landings are BURSTY when the step sp is small (I consecutive rows, then ~p/sp rows of nothing): the bucket ring
  must span ~p/T blocks (headers only; cheap), not p/(I*T).
- Record vectors must be DETACHED while a bucket is processed (a record can land back in the same block's successor
  chunk); the referee found the use-after-free.
- Chunk-granular BUCKETS lose (record traffic x59); chunk-granular LANDING BUFFERS with block-level buckets win.
- Memory: 48 B/record now -> pack to ~24 B. 1e10: 455M records -> 11 GB/card packed; 3e10: 34 GB/card; 1e11: 100+ GB/card
  (VRAM tier or shredder-central). Residue table PEd (int64 memmap, shared): 3.6 GB at 1e10.

## Remaining modules (this week)
1. Record packing (24 B) + checkpoint/restore of the bucket state (a card restart must not re-init 455M primes; ~2.5 min at 1e10 otherwise -- acceptable fallback).
2. **Sieve daemon per card**: owns one progression, produces SELECTED rings (select-12: sieve 240k, rank by survivors, pack the sparsest 8,312) into a ready-queue; js2 (Q<=1e6 + swap) supplies the base bitmaps in C, bsieve finishes to Q_deep.
3. **Loop consumer mode**: `make --round 1` takes the next ready ring instead of sieving; ledger bids/ks contiguous per card; rungs >= 2 unchanged (per-k at Q=1e6; annulus deepen available later from the same state).
4. Box gates: identity vs the production make on the card's own progression at 1e8; depth audit at 1e10 (sampled kills trial-divide; survivor density Mertens-exact); then ONE quiet block vs RC9/RC10.
Model: depth 1e10 x1.25 on tests (vs 1e8) / x1.11 (vs 1e9), make ~2 s -> selection deeper than 12x becomes affordable
(select 24 ~ +4% pass). Stacked on RC10: ~x1.3-1.4 -> go-rule band on 32 cards.
