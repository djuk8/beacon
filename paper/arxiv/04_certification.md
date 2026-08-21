# 4. Certification methodology

## 4.1 Instruments
All computations run on instruments admitted by three criteria:
a known-answer corpus; a bit-exact comparison against an
independently written implementation; and a fault-injection
drill demonstrating that the gate fails when it should. The
primality kernel was admitted on a corpus of $2{,}008{,}000$
verdicts with zero mismatches and executes a Gerbicz error check
on every production test (zero alarms across more than
$1.85\times 10^7$ verdicts). The evaluator of $T_d$ carries a
three-anchor fingerprint executed at every import; drift aborts
the calling program.

## 4.2 Independence of the central quantity
Every survivor count is produced by three unrelated routes: the
production landing-arithmetic sieve; a dense boolean sieve
written as a deliberately different code path and byte-compared
per candidate; and the analytic expression $T_d$. Their
agreement is the central empirical fact of the paper: sub-$1\%$
for $z \ge 331$ and $\le 3\%$ at $z = 79$ over $64$ synthetic
anchors; campaign anchors at $+0.1\%$, $-0.0\%$, $+0.2\%$;
all seven rings of a production ladder within $0.8\%$,
including the smooth-dominated innermost ring, with the
theater's $\ln n_0$ reproduced to one part in $10^4$; measured
$Q$-drift $0.24\%$ across a decade of sieve depth. Public
submission adds an adversarial fourth route: the community
notary re-proves both endpoints and re-sieves the interior on
independent hardware.

## 4.3 Preregistration and exclusions
Quantitative hypotheses were filed before measurement with
numeric pass bands and named authors, and verdicts recorded
verbatim; refuted entries are retained (Appendix A). Of fifteen
filed hypotheses five were refuted, and each refutation
localized structure: the failure of one-dimensional
extrapolation exposed the second coordinate; the failure of a
saturation ansatz exposed the truncation mass $F_d$; the failure
of the local lip derivation exposed the channel staircase.
We record one result of the exclusion kind explicitly:

**Empirical Exclusion 4.1.** No preregistered scalar coordinate
$v(m, \lambda)$ reproduces the certified values of $\sigma$
across the calibration set within stated bands; the dependence
on $(u, m)$ is genuinely two-dimensional. (Signature in raw
data: at fixed $u$ the $1/L$ coefficient of $\sigma$ changes
sign near $u \approx 1.55$.)

## 4.4 Cost statistics and a survivorship caution
Under (H1)--(H2) windows-to-success is geometric with mean
$e^{E}$ (Proposition 2.6: exact for Poisson survivor
statistics, factorial-cumulant-controlled in general); all
cost figures are exact quantiles (median
$\ln 2\cdot e^{E}$; $80\%$ budget $2.32\times$ median; lower
quartile $0.415\times$ median). An earlier operating band,
calibrated on completed campaigns, proved on audit to span the
12th--39th percentiles of the geometric law: completed
campaigns are the lucky ones, and intervals calibrated on
survivors inherit their luck. The band was retired; only
quantiles are reported.

## 4.5 Certified domain
Exhaustive-sieve certification covers $z \in [79,\ 888{,}887]$,
$u \le 1.97$, $z/\lambda \in [0.98, 1.03]$, $d$ from $2310$ to
$23\#$, $k$ up to $10^{36}$. Outside this domain every emitted
number carries an explicit flag (extrapolated CPU timing;
$\theta(z)$ by PNT beyond $10^6$; desert ratio outside the
certified band; a device rate modeled rather than measured).
A number without a flag is exact or measured.
