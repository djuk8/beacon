# 2. The object

## 2.1 The construction
Fix a height of D decimal digits and write lam = ln n0 ~ D ln 10.
Choose a bound zd, a small even squarefree divisor d of the
primorial zd#, and an odd integer k with gcd(k, d) = 1. Campaign
centers and candidates are

    n0 = k * zd# / d,      candidates n0 + j,  |j| <= jf.

The supply of centers at fixed height forces the design grammar:
k carries kdig ~ D - digits(zd#/d) digits, hence
zd ~ lam - kdig*ln10 + ln d ~ lam. Every certified configuration
in this paper sits at z := zd/lam in [0.98, 1.03]; the number of
admissible k -- the window supply -- is 0.9 * 10^kdig * phi(d)/d,
a constraint priced explicitly in Section 8.

## 2.2 Who kills whom
Three prime regimes act on a window:

- STRUCTURAL (p <= zd, p not | d): p | n0, so p | (n0+j) iff
  p | j. These carve the desert, killing exactly j = 0 mod p.
- CLASS (p | d): p does not divide n0; it kills the single
  nonzero residue class j = -n0 mod p, set by k mod p.
- DEEP (zd < p <= Q): kills j = -n0 mod p, equidistributed in k.

Parity is the first class prime: d even and k odd make n0 odd, so
every odd offset is composite and all candidates are even.

## 2.3 The survivor decomposition
Throughout the working range (jf = (m/2)*lam ~ (m/2)*zd << zd^2),
an offset survives the structural sieve iff every odd prime factor
of j divides d or exceeds zd. Each survivor therefore factors
uniquely as

    j = s * q,   s an even d-smooth integer,  q = 1 or prime > zd.

We call s the CHANNEL of j. The constraint q > zd truncates the
channel spectrum:

    s <= j/zd <= jf/zd ~ m/2

-- a fence position's smooth part cannot exceed half the merit.
This truncation is the origin of every nontrivial feature of the
cost law (Section 3).

## 2.4 The counting formula
Averaging over admissible k (classes equidistribute; certified
against exhaustive sieves in Section 4), the expected two-sided
survivor count is

    E[S] = Theta(zd,Q) * SUM_sides SUM_{s even d-smooth}
             c_d(s) * [ (pi(J/s) - pi(zd))_+  +  1_{s <= J} ]

with J the side's edge, per-channel class survival

    c_d(s) = PROD_{p | d, p odd, p not | s} (1 - 1/(p-1)),

and deep thinning Theta(zd,Q) = PROD_{zd < p <= Q} (1 - 1/p).
The bracket's first term counts prime channels s*q; the second,
pure-smooth positions. With the standard sieve normalization
beta = e^gamma * ln Q / lam (probability that a Q-rough candidate
at height lam is prime), the campaign's luck exponent is

    E = beta * E[S],     P(window is a record) = e^(-E),

and windows-to-success is geometric with mean e^E; all cost
statistics in Section 8 are exact quantiles of this law.

## 2.5 Two exact identities
(i) Q-INVARIANCE. Theta(zd,Q) = (ln zd / ln Q)(1 + o(1)) by
Mertens, cancelling the ln Q in beta: E does not depend on sieve
depth. Measured drift between Q = 10^5 and 10^6: 0.24%.

(ii) d-NEUTRALITY. In the untruncated limit, smooth enrichment
and class thinning cancel exactly -- the d-smooth mass carries
weight PROD_{p|d}(1-1/p)^(-1) and the classes remove
PROD_{p|d}(1-1/p) of it. The divisor d is asymptotically
cost-free; its entire effect enters through the truncation
geometry of 2.3 and the parity gain. This upgrades two previously
fitted nulls -- the wings-null and the collapsed swap-depth
coefficient -- from empirical zeros to identities.

## 2.6 Hygiene
If p | d and p | k, the prime reverts from class to structural:
it kills j = 0 mod p, closes every channel it divides, and
applies no class thinning. The survivor count inflates by an
exactly computable factor; Section 6 measures this inflation
across a decade of the public record.
