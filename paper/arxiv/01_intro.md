# 1. Introduction and main results

Let $G(p)$ denote the gap to the next prime and $m = G(p)/\ln p$
its merit. The public record tables -- first occurrences per gap
size, maximal merits, and largest gaps above merit thresholds --
now hold over $1.2\times 10^5$ entries, essentially all of the
large ones produced by variants of one construction: centers
$n_0 = k\,z\#/d$ with $z\#$ a primorial, $d \mid z\#$ small, and
$k$ a small cofactor, so that the neighborhood of $n_0$ is born
free of small prime factors. The construction is community
folklore; what has been lacking is a quantitative law for what a
given target costs under it. Costs have historically been
discovered by spending them.

This paper supplies that law and verifies it to the limit of the
available data. Write $S$ for the number of offsets $j$ in a
window $|j| \le (m/2)\ln n_0$ that survive sieving by all primes
$\le Q$. Our main object is the class-torus average of $S$ over
admissible $k$, evaluated exactly (Theorem 3.2): a truncated
convolution of even $d$-smooth integers against primes exceeding
$z$, weighted by elementary local factors. The structural facts
are theorems. The survivor set factors through smooth channels
(Proposition 3.1), and its class average is a finite exact
identity requiring no asymptotics (Theorem 3.2). The class-thinned channel masses form a
probability distribution (Theorem 3.3): the divisor $d$
redistributes cost but cannot create or destroy it, and the
entire finite-window content of a design is which mass the
truncation leaves reachable -- an exactly computable staircase,
worked in Example 3.5. In the deep-channel limit the marginal
rate is $e^{\gamma}\omega(u)$ for every admissible $d$
(Corollary 3.4); this is the fence-rate law measured and
confirmed independently, at $6$--$8\sigma$, in an earlier phase
of the program (Section 5.5), including the cusp at $u = 2$
that the present framework identifies as the opening of the
two-prime channels. The cost exponent is invariant in the sieve
depth (Proposition 3.6). Under two standard probabilistic
hypotheses (Section 2.5) the expression becomes a complete cost
model (Proposition 2.6): record attempts are geometric with
mean $e^{E}$,
$E = \beta\,\mathbb{E}[S]$, and every leaderboard target
acquires exact cost quantiles.

The model is then confronted with every artifact we could
obtain: $64$ synthetic calibration points spanning $87$ to
$385{,}713$ decimal digits, the complete ring designs of three
record campaigns of our own, and -- with no fitted parameters --
the exact survivor counts of all twenty published maximal prime
gaps of the past decade, reproduced to $1$--$4\%$ (Section 5).
Two published entries that initially deviated by $29\%$ are
explained exactly by a divisibility defect of the discoverer's
cofactors (Corollary 3.7 and Section 6), turning the model's
only failures into its sharpest confirmations.

Finally, the empirical cost curve used by practitioners -- a
one-variable profile $\sigma(u)$ in the rescaled coordinate
$u = 1 + \ln(m/2)/\ln\ln n_0$, with fitted slope
$1.82 \pm 0.04$ -- is identified as the shadow of the
two-variable law along the narrow locus that records inhabit,
and its slope emerges numerically as $e^{\gamma}$ with nothing
to tune. That the shelf limit of the exact sum equals
$e^{\gamma}$ is stated as Conjecture 3.9; we consider it
approachable by classical methods and would regard a proof by
others as the best outcome of this paper.

This paper is self-contained. Earlier drafts organized the
material as three companion manuscripts -- the construction,
the fence-rate law, and the computational pipeline -- and all
three are folded here: the construction is Section 2, the
fence-rate law is Corollary 3.4 with its independent
statistical confirmation in Section 5.5, and the pipeline and
its instruments are Section 4, with engineering detail in the
public repository. Section 2 fixes notation; Section 3 states
results; Sections 4--5 certify; Section 6 derives applications;
Section 7 discusses context and open problems.
