# 4. The road here, and the checks

## 4.1 Three strands, one paper
[P0], the crossover/2-adic swap paper, is the CONSTRUCTION: it
introduces the d-axis -- dividing the primorial to relocate
small-prime kill classes -- measures the drop-2 parity gain and
the swap multiplier ladder live, and fixes the design grammar
zd ~ lam used throughout Section 2. [P1], the squarefree
singular-series paper, is the MICROSCOPIC LAW: the fence rate
e^gamma * omega(u) per unit merit, its two constants
e^gamma*omega(1) = 1.7811 and e^gamma*omega(2) = 0.8905 measured
as leg rates, a preregistered forward prediction confirmed at
6-7 sigma in both directions, the Buchstab cusp at u = 2 at
8.45 sigma, and a 94,885-fence out-of-sample test with zero
fitted parameters (chi^2 p = 0.19); the Mertens-style rate is
rejected at > 8 sigma. This paper is the third step: the exact
counting law that contains [P1]'s rate as its untruncated limit
(3.2) and prices [P0]'s construction (Section 8). A fourth
companion, [P2], records the pipeline engineering and the
realized cost ledger, with receipts.

## 4.2 The journey
The program paid to learn before it learned to price. A
first-occurrence factory at ~2,700 digits produced hundreds of
finds and the first hard window economics; the [P0] construction
then took the >=2,500-digit merit crown twice (32.385, then
33.638), priced by extrapolation and paid for in surprises. The
microscopic era followed: the fence-rate measurements of [P1],
and a graveyard of plausible accelerants killed against finished
controls -- candidate scoring (null at 14 sigma), wing-weighted
covering (net zero at production), sieving past the regime
boundary (cost, not benefit). Every retired multiplier stays in
the record. The theater era fitted the empirical sigma(u) on 26
exact-sieved artifacts (leading coefficient within 1.0 sigma of
e^gamma) and spent it on three campaigns at three heights --
26,600, 6,152, and 610 digits -- each priced before it was
hunted, each landing inside its predicted band. The final week
is this paper: attempts to DERIVE the fitted curve's e^gamma
refuted five preregistered hypotheses in sequence, and each
refutation exposed structure -- the second coordinate, the
filling, the channel staircase -- until the fitted curve was
demoted to the shadow of an exact convolution, and the published
decade fell to retrodiction within days. Appendix A is that arc,
verbatim; the refutations were the instrument.

## 4.3 What we used
One liturgy runs every campaign at every height:
design -> make (sieve) -> drive (PRP) -> fold (verdicts) ->
finish (fence walk), with salvage of discarded centers as a
by-product economy. The instruments: a vectorized sieve factory,
byte-gated against a reference path; a CUDA Fermat kernel with a
Gerbicz error check on every test (zero alarms across 18.5M+
verdicts; admitted on a 2,008,000-verdict known-answer corpus
with zero mismatches); PFGW sharding at heights beyond the GPU
classes; an independent re-proof library before any find is
banked; and the community notary as the adversarial finish.
Admission rule for every component: a known-answer corpus, a
bit-exact comparison against an independent implementation, and
a fault-injection drill -- a green gate on code the gate does
not cover is worse than no gate. The pricing core carries a
three-anchor fingerprint executed at every import; drift aborts
the caller. AI assistance (Claude, Anthropic) ran through the
entire program as research assistant; its hypotheses were
preregistered under its own name and its errors filed verbatim
(Appendix A; disclosure in Section 10).

## 4.4 Independence of the central number
Every survivor count in this paper is produced by three
unrelated routes: the production landing-arithmetic sieve; a
dense boolean sieve written as a deliberately different code
path and byte-compared per candidate; and the analytic
convolution (2.4). Their agreement is the central empirical
fact: sub-1% for zd >= 331 and <= 3% at zd = 79 on 64 synthetic
anchors; campaign anchors at +0.1% / -0.0% / +0.2%; all seven
production rings within 0.8%, including the smooth-zone ring 1,
with the theater's ln n0 reproduced to one part in 10^4;
Q-invariance measured at 0.24% across a decade of sieve depth;
the published record set in Section 5. Public submission adds a
fourth, adversarial route: the notary re-proves both endpoints
and re-sieves the interior on independent hardware.

## 4.5 The cost statistic, and a survivorship lesson
Windows-to-success is geometric with mean e^E -- a consequence
of the law, not an added model -- so every cost figure is an
exact quantile: median = ln2 * e^E, 80%-budget = 2.32x median,
lucky quartile = 0.415x median. A prior operating band,
"measured at the frontier," proved on audit to span the
12th-39th percentiles: banked campaigns are the lucky ones, and
bands measured on survivors inherit their luck. The band was
retired to the ledger; this paper reports medians and quantiles
only.

## 4.6 Not certified, and said so
Shipping as flagged models, not measurements: the NVIDIA 4090
ladder (x0.60 of the gated 5090 ladder, pending a one-hour gate
run any reader can perform); theta(zd) beyond 10^6 (PNT); desert
ratios z outside [0.98, 1.03]; CPU seconds-per-test beyond its
three anchors; one ladder-factor bookkeeping reconciliation
against deployed fold statistics. A number without a flag in
this paper is exact or measured; a number with a flag tells you
which caution it carries.
