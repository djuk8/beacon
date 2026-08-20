# 8. Pricing the sport

## 8.1 From law to invoice
E = beta * E[S] makes windows-to-success geometric with mean e^E;
we quote exact quantiles (median ln2 * e^E; 80%-budget x2.32;
lucky quartile x0.415; see 4.5 for why prior "measured bands"
were survivorship). Tests per window follow the ladder factor
dE/(1 - e^-dE) / beta -- exact for an E-geometric ring ladder
(2.0800 at the deployed rung dE = 1.7). Hardware: the unit is ONE
NVIDIA RTX 5090 running the repository's gated kernel for a day;
the measured sustained ladder is 516,358 / 67,232 / 8,723 /
1,201 / 383.4 / 141.8 tests/s at the 2048...32768-bit classes
(burst figures retired to the ledger). The NVIDIA 4090 column is
x0.60 [MODEL] pending a one-hour gate run any reader can perform.
Dollars use the dated cluster rate $0.375 per 5090-card-hour
(Aug 2026: 4x @ $1.5/hr, 8x @ $3.0/hr; we pay ~$0.325). Above
9,863 digits no measured GPU class exists; costs print in
core-days against three measured CPU anchors.

## 8.2 The supply wall
A configuration is buyable only if enough centers exist:
ln(supply) = kdig ln 10 + ln(0.9 phi(d)/d), feasible iff
ln(supply) >= E + 1. This prices the "entropy wall" exactly and
explains the sport's greatest monument: the all-time merit crown
(41.9388 at 87 digits) was set by a proof-of-work cryptocurrency
swarm and has stood nine years because at its home height the
required e^E exceeds the entire k-supply -- constructive attack
there is not expensive, it is IMPOSSIBLE at certified designs.
Merit crowns, however, fall at any height: the D-scan escapes the
wall, and the calendar optimum lands exactly on the 2048-bit
class boundary at D = 616 -- 2.1K NVIDIA-5090-days median, about
$19K. Placement is worth x260 against the crown's home height
before design quality is even discussed.

## 8.3 The boards table
[SLOT: frozen table from boards_full.csv after column cull --
one row per leaderboard: optimum placement and design, E, median
cost in NV5090-days / 4090[MODEL] / USD, practice cost, savings,
flags. Interim full-precision table: repository
exchange/boards_csv.py output.]
Baseline definition, fixed here: PRACTICE = the same pipeline at
the incumbent's own height (their placement, our best design
there -- conservative in their favor) times the MEASURED design
premium x1.3-2.0 (Renyer brute band; belt incumbents run
~1.0-1.4; the merit crown's PoW incumbent paid far above any
band). The unstructured baseline sigma = 1 is an exact theorem
and yields 10^4-10^7x on merit boards; no serious hunter works
that way, so it lives in this sentence and the docs, not the
table.

## 8.4 Proof by existence
Fed nothing but the public thresholds, the optimizer reproduces
our own deployed theaters: the monument campaign (chosen D
26,558 vs deployed 26,600; E 7.17 vs 7.17), the merit-30 strike
(6,137 vs 6,152; 14.70 vs 14.74), and the 616-class raid theater
-- whose deployed k-budget the feasibility test identifies as
riding the supply wall, exactly as its designers experienced.
The campaigns built by measurement, before this law existed, are
the configurations a rational agent derives from it. Conversely
the law's global cost minimum -- the 6.4-8.1k-digit
first-occurrence belt at E ~ 2 -- is precisely where the
community's 2026 compute already farms. We did not teach the
market; we derived it.

## 8.5 First touch
The repository ships price_one: one target in (merit or gap),
one screen out -- placement map with flags, the priced optimum,
the practice comparison, and the certification statement -- with
an identical client-side web twin whose footer prints the live
three-anchor fingerprint. The demo is the argument; the paper is
its receipts.
