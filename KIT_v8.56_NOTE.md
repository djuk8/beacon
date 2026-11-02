# Kit v8.56 - single-class hunting (2026-11-02, branch v8.56-single-class, A/B candidate)

Why: k's residue class mod 2310 fixes where the swap primes 3, 5, 7, 11 kill (CLASS_RESULT_v0, 2026-10-18). Exact arithmetic gives each
of the 480 valid classes its value; the best pair is k = 317 / 1993 (mod 2310, mirror classes): rung-6 entries x1.077 per tested
window, confirmed on 377,244 rental entries (tilt-corrected GLM slope b = 1.00 +- 0.03), and record odds x1.21 at merit 42.55 (the
walk part is what the A/B measures). A daemon walking one class also wastes nothing: every pool row is a valid window (today 99,740 of
240,000 rows are), so the GPU sieve lands ~2.4x fewer kills per kept window.

What changed (tools/make_v856.py, anchor-checked, in place, from kit v8.55; --step 2 everywhere = v8.55 byte for byte):
1. gbsd.py: --step 2310 --kclass C [--kbase K]: k = k0 + 2310 t, k0 = first k >= K (default 1e15) in class C; kblock defaults to 8311
   at step 2310 (99,732-row pool, 8,311 windows per ring as today); state file and ring manifests carry step/kclass/k0; a daemon refuses
   to resume another progression's state, and refuses v8.55 libraries at step 2310.
2. bs_api.c: bs_records_flat_s / bs_js2_consts_s / bs_predict_s - the per-row shift is (S/2)*pe instead of pe; the old names are S=2
   wrappers; every S-dependent line keeps the v8.55 expression when S == 2.
3. gbs.cu: k_rows uses k = k0 + S t and the small-prime row shift (S/2)*pe (zero for 3, 5, 7, 11 at S = 2310: the same kill in every
   row); gbs_set_step(). The medium and deep kernels are unchanged (their constants come from the host).
4. fastmake.py: a single-class set (all k in one class mod 2310) takes the per-k kernel - js2 and fm_deepen index rows over the odd-k
   span, 1,155 rows per window for such a set, ~500x the work at rung 2. Measured: rung-2 make on a 4,600-window single-class carry
   0.8 s. Deepening a single-class set refuses loudly (DEEPR must stay 1; it does - see the 10-06 DEEPR=2 lesson).
5. onstart_raid_v2.sh: knobs SIEVESTEP / SIEVECLASS / SIEVEKBASE / SIEVEBID (first sieve daemon) and SIEVESTEP2 / ...2 (second); absent =
   the v8.55 launch line. Single-class rings are numbered from 1e9 (daemon 1) / 2e9 (daemon 2), so the feeder ledgers split the arms by bid
   (a mixed daemon makes ~0.5M rings a day: it would need years to reach 1e9).
New files: cuda/gbs_cpu.c (CPU twin of gbs.cu: same API, kernels as loops - gates without a GPU, and the GPU's referee on the box),
tools/sieve/ref856.c (direct per-(k,p) referee: no progressions, lattices or shared constants), gates/gate_856_cpu.py + gate_856.sh,
theater/raid610/deploy_856.sh (switch ONE daemon, with rollback), tools/ab856.py (A/B read and live-ring audit).

k-space and seeds: single-class k starts at 1e15 (every mixed-class segment so far is below 4.5e14). A single-class daemon climbs k 480x
faster per window (2310 per row, 12 rows per kept window): at box-6 pace (~5.5 rings/s per daemon) ~1.1e14 a day, so a month of one
daemon reaches ~4.4e15. The height costs record odds (merit falls with ln n: ~-2.4% odds per e-fold of k at merit 42.5): x0.98 at 1e15,
~x0.95 after a month vs today's 4.4e14 - the net gain is ~x1.18 over the next two weeks, not the full x1.21. Single-class daemons get
fresh seeds (60000+: the state file name is per seed); a later box hunting 317 / 1993 starts above the range already used.

Gates, sandbox (2 cores, CPU twin), 10/10 PASS:
- G0a S=2 constants v8.55 == v8.56 == _s(S=2): js2 consts (78,444 medium primes), records (5,682,957 at 1e8), masks, wheel, predictor
- G0b S=2 rings, v8.55 gbsd == v8.56 gbsd: 2 rings at 1e8, select 12, predictor on - bin + manifest bytes identical
- G0c twin fidelity: twin (S=2) == certified `scanhunt make --select 12` at 1e8 (8,311 ks, 508,628 candidates, bin identical)
- G1 S=2310, every row of 2 blocks (8,000 windows) == referee at 1e7; ks = 1000000000001627 + 2310 t exactly
- G2 production geometry: 2 x 8,311 kept windows == referee; tapped pool bitmaps == referee on sampled rows; the selection recomputed
  from referee predictor sums + pool counts == the ring (pred_z +1.61 / +1.60)
- G2r resume after stop == continuous run (bytes); an S=2 daemon refuses the single-class state
- G2b class 1993 at 1e8: sampled kept windows == referee;  G3 bs_predict_s == direct sums, 99,732 rows x 3 origins
- G4 rung-2 make on a single-class carry == referee (Q 1e5), 0.8 s; mixed sets old == new fastmake; single-class deepen refuses
- G5 onstart: knobs absent -> launch lines unchanged; SIEVESTEP2=2310 -> the v8.56 arguments
Box: gates/gate_856.sh adds GB2 (S=2 GPU rings v8.55 == v8.56), GB3 (S=2310 GPU rings == CPU twin), GB4 (every GPU kept window ==
referee at 1e8); deploy_856.sh demands that receipt, installs the gated binaries by atomic rename, switches the second daemon, restarts
the ladders once (they must load the new fastmake before a single-class ring reaches rung 2; ~1-2 min of in-flight rings are dropped), and audits the first live single-class
ring against the referee at production depth (1e10) - a failure rolls back by itself.

Open: the A/B read (ab856.py read: rung-6 entries per window x1.077, +-2% after ~6 h; walked merit >= 30 x1.22, readable in 3-4 days);
then the first daemon (class 317), merge to main + stamp; select 24 re-test (each pool is now 99,732 rows of real windows).
