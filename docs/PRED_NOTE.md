# PRED_NOTE.md -- full-window sparsity predictor (2026-09-11 night, C). Ready for the morning.

## Correction (by name: C)
The rung-1 selection running since RC9 lowers the rung-1 survivor count by ~13% but the FULL-window count by only
0.5-0.6% -> its gain in crown-lambda is x1.16-1.20, not the x1.32 the `lam-eff` column credits (that column scales
by the rung-1 pass gain; rung 1 is 5% of the window). Honest multipliers: RC9 x1.20 over RC7 (not 1.30); RC10
x1.28 (not 1.39); crown ~1,015 cd -> ~32 d on 32 cards. The lam-eff column is a rung-1 throughput metric, not crown-lambda.

## Measurement (sandbox, 24,935 full windows +/-31,576 at Q=1e6, seed 7302)
- Survivor count: mean 1751, sd 27.8 = 1.59% (sub-Poisson; the wheel is common to all windows).
- E_total = 28.3 is linear in survivors -> selecting the sparsest fraction: half x1.43, quarter x1.77, tenth x2.20,
  5% x2.52 per window -- but sieve cost per tested window scales with the pool (the deep sieve walks the span), so
  large pools do not pay. Swap-prime residue classes explain only 4% of the variance (not a shortcut).
- LOOKUP PREDICTOR: pred(k) = sum over linear primes p <= PB of cnt_p[(-k*pe_p) mod p], cnt_p = wheel-survivors per
  residue class (fixed per venue). corr(pred, true count) = -0.23 (PB 5e3) / -0.32 (2e4) / -0.37 (6e4) / -0.40 (1e5).
- Ranking TODAY'S 12x pool by prediction + rung-1 count (score = z(pred) - 0.6*z(S_r1)) instead of rung-1 count alone:
  full-window survivors -1.32% vs -0.64% -> crown-lambda x1.45 vs x1.20 per tested window (+21%), same pool, same sieve.
- Box-analog gate (fresh block): control 1752 | rung-1 ranking 1743 (x1.16) | predictor 1730 (x1.42) -> x1.23 better. PASS.

## Implementation (kit v8.28)
- bs_api.c: bs_pred_create (tables: 9,368 primes <= 1e5, 908 MB uint16, built once ~4 s), bs_predict (incremental
  residues, one add per (prime, t), threaded; ~3 core-s per 240k block), attach/export for shared tmpfs tables.
- bsd.py: --pred-pb (default 1e5; 0 = old ranking), --alpha (0.6), --pred-threads (4); tables shared on /dev/shm
  (first daemon builds under a lock dir); manifest origin carries pred_z; log line prints pred_z per ring.
- onstart/go_crown/exp.sh: BSDPB, BSDALPHA knobs; TMAXHI (hi-lane gather seconds, default 1.5; 6 in block 14).
  Auto-sizer counts 10 threads per daemon now.
- gate_pred.sh: on the box, fresh seed 7305: old vs new ranking vs control, full-window sieved -> PASS if new < old - 8.
- queue_block14.txt: rc10 | pred | pred+hi6 | rc10+hi6 | rc10_b | pred_b. Read w/s and t/w from the ledger; the
  crown factor per window comes from the gate (x1.16 old, x1.42 new). Expected: pass1 ~0.205 (intended), w/s ~same or +.

## Morning sequence (three pastes)
1. gate:   [ "$(sha256sum ~/o1_kit.tgz | cut -c1-16)" = 5a55be924672bfba ] && tar xzf ~/o1_kit.tgz -C ~/beacon/p3 && bash ~/beacon/p3/o1_kit/gate_pred.sh
2. block:  cp ~/queue_block14.txt ~/beacon/raid610/ && cd ~/beacon/raid610 && (setsid nohup bash ~/beacon/p3/o1_kit/expq.sh queue_block14.txt > expq_b14.log 2>&1 < /dev/null &); sleep 3; tail -1 expq_b14.log
3. after the block: the best config with w/s within noise of rc10 and the predictor on = RC11 (x1.28 * 1.23 = ~x1.57 over RC7, ~26 d on 32 cards); TMAXHI=6 promoted if its w/s wins.
