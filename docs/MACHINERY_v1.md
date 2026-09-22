# BEACON MACHINERY v1.1 — the O1 hunting machine
2026-08-23. Status of record after G-SAT + G-4W. Kit v3.7 (`dd3d3b1f3a942ce7`). Zero-meter document; every number carries its gate.

## 1. What this machine is

A prime-gap record factory: it manufactures search windows (rings), eliminates composites in rungs of
increasing selectivity, and banks survivors as record candidates. Three principles shaped every design
decision, in order of precedence:

1. **Verdicts are sacred.** Any change to the path that produces a verdict byte must be byte-identical to a
   trusted reference, proven by a gate, before it runs in production. Speed never buys a byte.
2. **The GPU test is the unit of cost.** One Fermat test at 2048 bits = 2.05 us of 5090 time [G1-D]. Every
   component exists to either (a) avoid a test, or (b) keep the card testing at peak.
3. **Everything falls over; the system must not.** Loops die, feeders die, boxes reboot, disks fill. Every
   component restarts idempotently (pgrep-guarded), every hand-off is an atomic rename, every stop leaves a
   receipt, and the watchdog relaunches the world from cron.

## 2. The picture

```
                    BOX1 (4x RTX 5090, 256 cores, 160 GB overlay, 125 GB /dev/shm)
                                                                        watchdog cron (@reboot + */10)
  per card C = 0..3:                                                            |
                                                                          onstart_raid_v2.sh
   90 loops (raid_loop_v2.sh, seeds 101+90C ..)                                 |
   ring cycle in /dev/shm/beacon/hunt_sN            state+finish.log symlinked to overlay hunt dir
        |                                           r6/r7 bins+manifests copied to overlay (salvage fossils)
        |  make (scanhunt_v0.py v0.1 --fast 2)
        |    fastmake.py -> fastmake_c.so  (C sieve x8.3; C pack; byte-identical)      [G-M1/M2]
        v
   sc_r0R_XXXX.bin + .manifest.json  (in shm)
        |
        |  submit_wait: atomic request -> queue/cC/req/     cancel ONLY if no feeder process exists
        v
   ee_serve.py v2.1 (4 processes/card: 3x r1-lane + 1x hi-lane; rename-claims; gather lock on r1)
        |
        |  mega-ring: 20 r1 rings (kwin 165k) or any hi rings 1.5 s old
        |  one process: g1_fermat_v3 --bins list --ee sizes --lock /tmp/raidgpuC.lock
        |    loads bins -> device once; waves 8,20,38,65,105,S in-kernel by index;
        |    flock held ONLY around the GPU phase (loading overlaps siblings' waves)   [G-R4, S1-S7]
        v
   per-ring v.bin (atomic rename into shm hunt dir) + ledger.jsonl line; candidate bin DELETED (rm-bins)
        |
        |  fold (scanhunt unchanged): 1/2 = PRP-hit, 0x03 = untested marker (fold-safe), 0xFF = FATAL
        v
   carry -> next rung make ... rung 7 -> finish.log (per-seed ring counter = THE rate instrument)
```

Fallback chain, always armed: feeder absent -> loop legacy-launches g1_fermat_v2 under the same lock;
fastmake_c.so absent -> numpy kernel (byte-identical); v3 absent -> feeder wave path (byte-identical).

## 3. Contracts (byte formats)

- **cand bin**: `<u32 MAGIC_C 0x31433247><u32 bits><u64 count>` + count x (bits/8) LE integers.
- **manifest.json**: `cfg{zd,swap,d,kdig,merit,Q,deep_q,G,edges,seed,ln_n0,bits}, round, bid, ks[], js[][], sizes[]`.
  Candidate order within k: |j| ascending, ties negative-first (stable argsort, v0.1). bid = per-seed ring counter.
- **v.bin**: `<u32 MAGIC_V 0x31563247><u32 bits><u64 count>` + count verdict bytes. 1=PRP, 2=GEC-alarm
  (counts as hit), 0x03=untested-by-early-exit, 0xFF=FATAL (fold aborts). Early-exit invariant: per k, the
  tested prefix is byte-identical to the full run's prefix, stops at the first {1,2}, prefix ends on a
  schedule boundary; markers only after. [compare_vbin.py enforces all of it]
- **sizes sidecar** (`--ee`): `<u32 0x31533247><u32 nk>` + nk x u32, in bin order.
- **queue**: req/ -> claimed/ -> done|failed/ by atomic rename; cancelled/ by the loop, possible only while
  in req/. ledger.jsonl: one line per ring (ts, card, seed, round, bid, ks, n, tested, prp_ks, mega stats).
- **schedule**: boundaries 0, +rint(c), c*=growth from chunk=8, growth=1.5, capped at S. rint = round-half-even
  = Python round(). C/CUDA/Python pinned to this by [G-R4 R2b: the 106-vs-105 lesson].

## 4. Life of a ring (steady state, measured)

make r1 (C sieve 0.7 s + pack, in shm) -> submit -> gathered into a 20-ring mega-ring (<=20 s wait) ->
v3 loads ~5 GB, takes the lock, 6 waves ~33 s GPU, releases -> v.bin back, bin deleted -> fold (advance
~18% of ks) -> make r2 (tiny) -> hi lane fires within 1.5 s, unlocked -> ... rung 7 -> finish.log line.
Loop cycle ~112 s; card saturates at ~90 loops; the card, not the feed, is the limit. [G-SAT]

## 5. Knobs (where the machine is tuned)

| knob | where | current | meaning |
|---|---|---|---|
| Q | raid610/Q.txt -> loop env | 1e6 | sieve depth; survivors/k 117.2 / 97.7 / 83.7 at 1e5/1e6/1e7; E is Q-invariant, edges frozen [Prop 3.6 + probe 2026-08-23] |
| LPC | raid610/LPC.txt | 90 | loops per card = saturation count; seeds 101+c*LPC, <=460 (box4/5 blocks 462-701 reserved) |
| kwin / tmax | feeder args | 165k / 20 s | r1 mega-ring size (20 rings) / max wait |
| tmax_hi | feeder args | 1.5 s | hi-lane latency bound |
| chunk / growth | feeder+v3 | 8 / 1.5 | early-exit schedule (see 3.) |
| SHM_MIN_MB | loop env | 20480 | shm watermark: loops wait instead of dying |
| R1N | restart env | 3 | r1 feeder processes per card (pipelining depth) |
| GENCODE | gate env | sm_89+sm_120+PTX | driver build targets (sm_120-only for fast gate builds) |

## 6. The gate ladders (how change enters this system)

- **G1 (binary physics)**: A cold start, C module loading, D peak/knee/latency per bit class, E MPS. Certified
  2048: peak 488k t/s, knee 128k, cold 503 ms, ser-init 363 ms, MPS dead. 16384: 1,175 t/s, knee 4,000.
- **G-M (make)**: M0 build, M1 rung-1 x3 (REF production / patched+numpy / patched+C), M2 carry. PASS =
  C-vs-numpy byte-identical, C-vs-production set-identical. [PASS box1 2026-08-22, Q=1e5 and 1e6]
- **G-R4 (driver v3)**: R0 build, R1 legacy path byte-identical to v2, R2 --ee identical to ee_serve(v2),
  R2b 40-ring mega-ring identical per ring, R3 throughput. [PASS box1: 514,170 t/s in-driver]
- **G-S (feeder)**: S1 byte-identity through the queue, S2 fallback (no feeder -> cancel -> legacy identical),
  S3 kill -9 mid-mega-ring -> re-queue -> identical, S4 fossils, S5 40 real rings throughput, S6 wave-path
  vs in-driver identical, S7 rm-bins. [ALL PASS box1 2026-08-22]
- **Doctrine**: gates run on the real binary on a quiet card; gate artifacts get their own dir; a green gate on
  code the gate does not cover is worse than no gate; corrections filed by name; one runner one log one paste.

## 7. Constants of record (frozen; change only via a named gate verdict)

| quantity | value | gate |
|---|---|---|
| Fermat 2048-bit on 5090 | 2.05 us/test (488k single-launch; 514k in-driver waves) | G1-D / G-R4 R3 |
| early-exit test ratio | 0.556-0.562, every read since 08-21 | ledgers |
| tests/window, full ladder | 143.3 legacy -> 79.7 @Q=1e5 -> 67.1 @Q=1e6 | RC3 + G-4W ledger |
| card, saturated | 6,550-6,810 w/s | G-SAT / G-4W |
| **box1** | **26,776 w/s = 2.31e9 windows/day = x1.85 R1** | **G-4W 2026-08-23** |
| C sieve | x8.3 rung-1 (0.64 s vs 5.3 s); whole make x3-5 | G-M1 |
| record scale (16k-bit) | x15 fewer tests (rescal, beta 2.6e-4) | replay + S4 |
| crown (RC3, this box's economics) | Plan A ~44 d on 40 cards NO-GO; Plan C ~9 d GO | RC3 + G-4W |

## 8. Named failure modes (paid for; never repeat)

1. Manifests are not a rate measure; finish.log counters are (r01 manifests are deleted after fold). -C
2. nvidia-smi utilization lies for short bursty kernels. -C
3. Cancel-into-fallback under a shared lock is a self-sustaining convoy: fall back only when the resource
   is ABSENT, never merely slow. -C (the 2026-08-21 convoy)
4. N gatherers split arrivals into tiny batches: serialize the gather, not the work. -C
5. Threads are not workers (GIL); processes are. Sibling cleanup must check owner liveness. -C (shm wipe)
6. Python round() is banker's; (int)(c+0.5) is not. Pin rounding semantics across languages. -C (wave 5)
7. Globs must be [0-9]-anchored (sc_r01_*.bin ate .v.bin; twice now, gl_*.bin before). -C
8. Loops call engines and binaries by ABSOLUTE path; cwd is a lie (../scanhunt in shm; PYBIN before). -C
9. The overlay disk is a resource with a budget: ~0.5 GB in-flight per loop. shm + watermark, not hope. -C
10. bc scale=0 truncates; audit every shell arithmetic line that feeds a conclusion. -C
11. tail on a piped long-runner shows nothing until the end: stream to a log, read the log.
12. A kit downloaded is not a kit installed: hash the tarball on the box before extracting (now in the paste).
13. **Concurrency is a memory-bandwidth question before it is a core question.** Q=1e7 makes the sieve's
    per-k working set 16 MB (664k primes x 24 B): cache-resident at 1e6, RAM-streaming at 1e7, ~265 GB of
    traffic per rung-1 make; 560 concurrent makes want ~3x the box's bandwidth and the whole floor crawls.
    The single-core probe (21.5 s) cannot see this. T1b struck as standalone; deep Q belongs to O3's
    landing enumeration, whose touches scale with landings (~5,400/window), not (k,p) pairs. -C
14. **A venue is a tuple; every consumer must read ALL of it.** The crown venue changed the edge list to 8
    rungs while the loop's rung counter stayed hardcoded at 7: effective cap merit ~32.5 masquerading as 45
    for a full day, invisible to G-L1/G-L2 (they gate the design and the mint, not the loop's coverage).
    Rung count now derives from the edge list; the live confirmation is natural r8 fossils (~3/day expected).
    Corollary: no 2>/dev/null on any copy whose absence would be silent. -C

## 9. Other venues (the machine is a tuple, not a target)

venue = (D, zd, d, swap, edges, bits, Q). Everything in 2.-6. is invariant; per-venue calibration is:
resonance_map ladder design (fence law G^0.438) -> G1 A+D for the bit class -> 20-min shadow for the feed
number. At 16k+ bits a test costs ~1 ms, so make cost and O3 are irrelevant there — early exit alone is the
lever (x15 measured); the >=2,500d crown track and the monument track run on this same kit with a different
tuple, PFGW beyond 32,768 bits (per-shard cwd doctrine, -b2, never pipe live).


## 9b. Card catalog (fleet selection)

Selection rule: rank listings by **tests/s per $/h per slot**, then verify each rented card with G1 A+D
(5 min) before loops start — the catalog below informs the shortlist, the gate sets the number of record.
Feed with the C make: 1-5 loop-cores per card (all cards). VRAM sizes kwin: mega-ring bytes ~ kwin x 117 x 256 B
(+ device verdicts); 32 GB -> kwin 250k, 16 GB -> ~120k, 12 GB -> ~90k.

| card | 2048-bit t/s | basis | typ. $/h | t/s per $/h | note |
|---|---|---|---|---|---|
| RTX 5090 | 488-514k | **MEASURED** [G1-D / G-R4 R3] | ~0.44 | ~1.15M | the fleet card; 32 GB |
| RTX 4090 | ~250k | [MODEL: sm_89 in binary, ~half 5090] | ~0.30 | ~0.85M | balanced on ordinary boxes; gate before use |
| RTX 5060 Ti 16 GB | ~130-160k | [MODEL: 36/170 SM, 448/1792 GB/s -> ~3.5x down] | ~0.08-0.10 | ~1.4-1.6M | $/test competitive; needs ~3.5x slots; thin listings; kwin ~120k; strong fit for the >=2,500d track (16k-bit is compute-bound anyway) |
| L40S | -- | excluded | -- | -- | Mario's lab rule: excluded from rentals |

MODEL rows freeze only via G1 A+D on a rented unit; until then they steer the shortlist, never the calc.

## 10. Pre-O3 optimization audit (everything on the table, priced)

| # | idea | cost | expected gain | verdict |
|---|---|---|---|---|
| T1b | Q=1e7 on box1 + LPC 140 | zero code | (was +13-15%) | **STRUCK 2026-08-23**: memory-bandwidth wall at concurrency (8.13); folded into O3 |
| T1c | kwin 165k -> 250k (30-ring mega-rings) | knob | amortize v3 load + cold start, +3-5% | DO with T1b, same relaunch |
| O4' | early-exit schedule from the measured beta(position) profile (the ledger already holds it) instead of geometric | offline fit + a boundary-list arg | ratio 0.556 -> floor ~0.50: +5-10% | DO before O3: zero risk, data in hand |
| P1 | manifest as npy sidecar (json of 975k ints costs CPU s/ring) | small patch + gate | cores only, not w/s | LATER (matters on CPU-poor boxes) |
| P2 | persistent v3 daemon per card (kill the 0.5 s cold starts) | moderate | +2-3% | SKIP (O3 absorbs it) |
| P3 | CGBN param sweep (TPI / LTPB) at 2048 | G1-D matrix, idle hours | unknown; maybe +5-10% | CHEAP PROBE during the soak |
| P4 | candidate compression over PCIe (k + js, expand on device) | part of O3 anyway | ~0.4 s/mega-ring | FOLD INTO O3 |
| O3 | landing-enumeration deepen to 1e9: c_p = (2 P_eff)^-1 mod p one-time table; enumerate LANDINGS (~2 ns each, ~5,400/window), never (k,p) pairs | tables + C lib + CUDA pre-pass + 4-stage gate | t/w 57 -> ~44: **+25-30% on top of T1b** | GO after T1b + O4'; bitmap-identical vs fastmake_c at 1e6/1e7, trial-division audit of kills at 1e9 |
| O3-CPU@1e8 | the same C lib on CPU for rented boxes (tier 1.5) | falls out of the O3 C lib | rented-box t/w -15% at ~zero cores | FREE BY-PRODUCT |
| - | Q=1e12 (RC2 last row) | lattice sieving, research | ~12% over 1e9 at huge cost | STRUCK: net ~zero (the wings lesson, again) |

**Recommendation**: T1b + T1c this week (one relaunch, ~+18% together), O4' offline from the existing
ledgers, P3 as an idle probe during the soak — then O3 with the landing-enumeration design. Projected box1
after all of it: **~38-40k w/s ~ x2.7 R1**, and the O3 C library cuts every future rented box's bill (tier 1.5)
before any CUDA is written. Plan-A crown still wants 60-80 cards; Plan C is GO throughout. The naive O3
(enumerate (k,p) pairs to 1e9) is a x12 net LOSS at measured constants and is struck by name. -C
