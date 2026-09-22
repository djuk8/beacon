# RUNG_PROFILE_NOTE.md -- the crown ladder's per-ring E, measured at 28 billion windows (2026-09-08, C)

## Correction (by name: C, 2026-09-08)
On 2026-09-08 I stated that the crown ladder "assumed a flat E ~1.72 per ring" and that the outer rings ran
"2-4x the design". That was wrong. ladder_crown.py places edges at CUMULATIVE-E targets [1.7, 3.4, 5.4, 7.8, 10.8,
15.0, 20.5] + final edge G/2 -- a deliberately growing per-ring schedule (1.7, 1.7, 2.0, 2.4, 3.0, 4.2, 5.5, rest).
The ledger measurement CONFIRMS that design to ~1% at rings 1-6.

## Measurement (box1 ledger, all rungs, Sep 2-8; survivors/ks per rung)
ring  design E  measured E   ratio   windows
  1     1.7       1.69       0.99    28,052,413,363
  2     1.7       1.71       1.00     5,164,665,557
  3     2.0       1.99       1.00       933,630,777
  4     2.4       2.42       1.01       127,250,345
  5     3.0       3.01       1.00        11,256,525
  6     4.2       4.18       0.99           553,372
  7     5.5       6.27       1.14             8,480   (n small; ~2 genuine passers; the 16 'survivors' were 2 windows replayed)
cum through ring 6: design 15.0, measured 15.00. Through ring 7: 20.5 vs ~21.3 (ring-7 excess within its own noise).

## What this is
The designer predicts E per ring from a dense-sieve SAMPLE of nk ks at Q=1e6 (beta = e^gamma ln Q / ln n0), i.e. a
pure Mertens/CRT calculation of survivor density along |j| in the swap construction. Production, at 28 billion
independent windows, reproduces those predictions ring by ring to 1%. This is the largest test of the construction's
survivor-density profile ever run, and it is a direct validation of the paper's E-accounting (the fence law's
regime for 1 < u < 2 is the same calculation; the paper's out-of-sample fence tests were at ~1e5 windows).
Ring 7 (+14%) and ring 8 (unmeasured; 0/2) are the only open items -- both are small-n and sit where the design's
sample statistics are thinnest. A dedicated outer-ring E measurement (sieve-only, no tests) closes them cheaply.

## What it does NOT change
The crown lambda (W_med) was anchored on the full-window E measured by real sieving (E45 = 30.62), not on the
ladder schedule; unchanged. The ladder's test cost is dominated by rings 1-2 (38.6 + ~10.5 of the 49.7 t/w at RC7);
unchanged. Rung-2+ deepening was measured -15% in production (block 7) and is filed; unchanged.

## Housekeeping it exposed
Windows that fail their last rung are replayed after every relaunch (the same two rung-7/8 windows six times);
the loop must mark finished windows. Kit v8.6.
