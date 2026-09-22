# O3 STATUS — end of build day 1 (2026-08-25)

## Certified chain (every claim has a gate)
1. gate_o3_unit: 400 randomized trials, enum == brute force (prime moduli). PASS.
2. **G-O3-A**: solve(1e5->1e6] o fastmake(1e5) == fastmake(1e6), SET-IDENTICAL on all 832 ks of a real
   minted crown block (same seed, both depths). 16,204 kills, 97,859 -> 81,655 exact. PASS.
3. **G-O3-B** at Q=1e8: 5.68M primes, 903k landings, 23,334 kill events; 513 sampled kills ALL trial-divide
   to their claimed prime (0 wrong). Survivor density after multi-factor dedup 73.7/k vs Mertens 73.6. PASS.

## Measured economics
- land_enum solve (incremental step): 2.04 us/prime -> (1e6,1e8] band = 11.6 s/block single-core in C
  (the 25.7 s in the audit = python-side landing filter; production keeps the apply in C).
- Box cost at Q=1e8: ~58 of 256 cores. Projected: t/w 61.85 -> 46.4, **box ~40.6k w/s (x1.33, x2.8 R1)**.
- Q=1e9 (final x1.50) needs the FK three-distance walk: v0.2, ported from CADO-NFS source (the two-stride
  reinvention failed its own gate in the sparse regime -- trial 59, filed).

## Remaining work
(1) C-side apply: land kills -> alive bitmaps inside the make (mirror fm_block contract; no python in the path).
(2) scanhunt --deep-q backend hook read + wiring; M-ladder rerun (M1/M2 at deep-q), shadow, four-wide Q=1e8.
(3) build_tables_o3 (c_p cache per venue) -- optional micro-opt; inv_mod inline is already cheap.
(4) v0.2 FK walk for 1e9 (CADO read first).
Files: land_enum.c 8fd9dc2c45e5, gate_o3_unit.c, bench_o3.c, this note.
