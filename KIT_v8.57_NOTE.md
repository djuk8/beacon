# Kit v8.57 - ring 2 deep-sieved on the GPU daemon (built 2026-11-03, branch v8.57-ring2, A/B candidate)

Why: ring 2 (1568 < |j| <= 4374) costs ~28% of all GPU tests, ~60 tests per window that reaches it, because the ladder sieves it only
to 1e5 on the CPU. Sieved to the daemon's depth (1e10) its survivors halve (Mertens: ln 1e5 / ln 1e10) and so do its tests: about
-14% tests per window, ~+16% windows/s on a GPU-bound box, minus the wider GPU sieve on the two sieve cards (~-3%) -> ~+13% net.
A deeper sieve removes only composites, so every ladder decision is unchanged (the ring-2 pass rate is the live canary). This is the
correct version of the 2026-10-06 DEEPR=2 attempt, which dropped primes; here the GPU output is gated against an independent referee.

What changed (tools/make_v857.py, anchor-checked, in place, from kit v8.56; --gpu-rings 1 everywhere = v8.56 byte for byte):
1. gbsd.py --gpu-rings 2: the GPU sieves rings 1+2 (I = 4,375 columns). Selection still reads ring 1 only (bs_row_counts_rng on the
   ring-1 columns), so the kept windows and the rung-1 ring file are byte-identical to --gpu-rings 1. The kept windows' ring-2
   survivors ride in the manifest as "r2" (lo, hi, depth, counts, int16 offsets in base64; ~2 MB per ring).
2. bs_api.c: bs_records_flat_w - the same per-prime records in a WIDE layout (i 13 / a0 14 / b0 13 bits; the v2 layout tops out at
   I = 2047); bs_row_counts_rng. bsieve.c (the CPU daemon) is untouched.
3. gbs.cu / gbs_cpu.c: gbs_set_format(g, 1) switches k_deep to the wide layout (v2 stays the default); gbs_block refuses a window
   wider than 2047 columns in the v2 layout instead of mis-reading it.
4. scanhunt_v0.py: cmd_fold carries "r2" for exactly the windows that pass ring 1; cmd_make round 2 packs the carried survivors
   (same packer, same order) instead of re-sieving to 1e5. Old manifests and carries (no "r2") take the old path unchanged; an old
   scanhunt simply ignores "r2" - safe in both directions.
5. onstart: knobs SIEVERINGS (first sieve daemon) / SIEVERINGS2 (second) = 2 -> --gpu-rings 2. Absent = v8.56 launch line.
New: gates/gate_857_cpu.py + gate_857.sh, theater/raid610/deploy_857.sh (second daemon first, with rollback), tools/ab857.py.

Gates, sandbox (2 cores, CPU twin), 7/7 PASS:
- G0 --gpu-rings 1 == v8.56: single-class (class 317, 99,732-row pools) and mixed, 2 rings each at 1e8 - bins + manifests identical
- G1 --gpu-rings 2 vs 1, single-class at 1e7: ring files identical, manifests identical but for "r2"; all 16,622 kept windows'
  ring 2 == referee (81.9 survivors/window at 1e7)
- G1b class 1993 at 1e8: sampled kept windows' ring 2 == referee (71.8/window);  G2 mixed classes: same identities
- G3 ladder path: synthetic verdicts -> fold carried 1,882 of 8,311 windows with exactly their ring 2; the rung-2 make took the
  GPU path, == referee and a subset of the 1e5 make in every window; candidates 215,715 -> 154,126 = x0.714 = ln 1e5 / ln 1e7
  (at 1e10: x0.5); rung-2 make 0.37 s -> 0.10 s
- G4 onstart knobs; G5 refusals: --gpu-rings 2 with a v8.56 bs_api.so stops, a wide window in the v2 layout fails loudly
Box: gate_857.sh adds GB0 (GPU --gpu-rings 1: v8.56 == v8.57), GB1 (GPU --gpu-rings 2 == CPU twin, bins + manifests with r2), GB2
(every GPU kept window's ring 2 == referee at 1e8). deploy_857.sh: atomic install, ladders restarted once (they must load the new
scanhunt), SIEVERINGS2=2 + restart of the second daemon (resumes its own seed), first ring-2 payload audited vs the referee at 1e10.

A/B (ab857.py read, daemon 2 vs daemon 1, mirror classes): ring-2 pass rate must not move; round-2 tests per entering window ~x0.5;
tests per window ~x0.86; rung-6 entries per window ~x1.00; the sieve cards' tests/s and the daemons' "gpu stage" per block show the
cost. Then daemon 1 (SIEVERINGS=2), merge to main + stamp.
