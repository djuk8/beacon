# 3. Results

## Proposition 3.1 (channel factorization)
Let $|j| \le j_f < z^2$, $j \ne 0$. Then $j$ survives the
structural sieve iff $j = s q$ with $s$ even $d$-smooth and $q$
either $1$ or a prime exceeding $z$; the factorization is
unique.
*Proof.* Structural primes eliminate exactly $p \mid j$; parity
eliminates odd $j$. Hence a structural survivor's odd prime
factors either divide $d$ or exceed $z$, and since $j < z^2$ at
most one factor exceeds $z$, to the first power. Uniqueness is
immediate. $\square$

## Theorem 3.2 (exact class-average identity)
Let $M = \mathrm{rad}(d)\prod_{z < p \le Q} p$ and let $k$ be
uniform on the admissible residues modulo $M$ (odd, coprime to
$d$). Then
$$ \mathbb{E}_k[S] \;=\; 2\,T_d(j_f;\, z, Q)
   \qquad\text{exactly}, $$
where, moreover, every quantity in $T_d$ is a finite exact
count: each $\pi(J/s) - \pi(z)$ is the literal number of primes
in an interval, not an asymptotic.
*Proof.* By Prop. 3.1 the structural survivors are exactly the
$j = sq$. Fix such a $j$ and consider the eliminating primes.
For an odd class prime $p \mid d$: $k$ occupies the $p-1$
nonzero residues; the killed offset class is
$j \equiv -n_0 \equiv -k\,(z\#/d) \pmod p$, a bijective image
of $k \bmod p$, hence uniform on the nonzero classes. If
$p \mid j$ (equivalently $p \mid s$, since $q > z > p$), the
killed class is never $0$: survival $1$. If $p \nmid j$:
exactly one of the $p-1$ admissible residues kills $j$:
survival $1 - \tfrac{1}{p-1}$. Collecting over $p \mid d$ gives
$c_d(s)$. For a deep prime $p \in (z, Q]$: $k$ occupies all $p$
residues. If $p \nmid j$, the killing residue
$k \equiv -j\,(z\#/d)^{-1}$ is one class of $p$: survival
$1 - \tfrac1p$. If $p \mid j$ (possible only as $p = q$,
$j = sp$), the kill condition is $p \mid n_0$, i.e.
$p \mid k$: again one class of $p$, survival $1 - \tfrac1p$.
Hence each deep prime contributes the uniform factor
$(1 - 1/p)$ and their product is $\Theta(z,Q)$. The moduli of
$M$ are distinct primes, so by CRT the per-prime events are
exactly independent over the torus, and the survival
probability of $j = sq$ is exactly $c_d(s)\,\Theta(z,Q)$.
Summing over the enumerated survivors of each side --
$\pi(J/s) - \pi(z)$ prime-cofactor positions plus the
pure-smooth position $j = s$ when $s \le J$ -- yields
$T_d$ per side. $\square$

**Remark 3.2.1 (from the torus to practice).** Campaign
cofactors range over intervals far shorter than the torus
period ($\ln K/\ln Q \in [1.4,\,2.6]$ in production); passing
from the torus mean to interval means is classical sieve
territory (the fundamental lemma, with one excluded class per
prime), and we do not rely on such a passage anywhere. Instead,
Sections 4--5 certify the identity directly at single
realizations. The same argument as in the Theorem computes all
torus moments exactly; for instance, for survivors
$j \ne j'$ the joint survival factor at a deep prime $p$ is
$1 - 2/p$ when $p \nmid (j - j')$ and $1 - 1/p$ when
$p \mid (j - j')$, so the variance is exactly computable and
lies at the scale of the independent-Bernoulli value (generic
pairwise torus correlations are $O(1/p^2)$ per prime and
negative). The observed single-realization scatter of Sections
4--5 is consistent with this scale.

## Theorem 3.3 (channel-mass invariance)
Let $\mathcal{S}_d$ be the set of even $d$-smooth integers and
define $W_d\{s\} = w_d(s) = c_d(s)/s$.

(a) $W_d$ is a probability measure on $\mathcal{S}_d$:
$w_d(s) > 0$ and $\sum_{s \in \mathcal{S}_d} w_d(s) = 1$ for
every admissible $d$.

(b) Consequently the total channel mass is the same for every
admissible divisor: changing $d$ cannot change the total
asymptotic channel mass, it can only redistribute it. All
$d$-dependence of $\mathbb{E}[S]$ at a finite window enters
through which mass the truncation of Prop. 3.1 leaves
reachable,
$$ F_d(m) \;=\; W_d\bigl(\{\,s \le m/2\,\}\bigr)
   \;=\; \sum_{s \le m/2} w_d(s) \;<\; 1, $$
and through the channel-resolved weights below. The advantage
of a construction comes from which mass is reachable under the
finite truncation, not from generating additional mass.

*Proof of (a).* Positivity is clear. The sum factors as an
Euler product over the primes of $d$. The prime $2$ contributes
$\sum_{a\ge 1} 2^{-a} = 1$. Each odd $p \mid d$ contributes
$\bigl(1 - \tfrac{1}{p-1}\bigr)$ from the $p$-free mass plus
$\sum_{a\ge 1} p^{-a} = \tfrac{1}{p-1}$ from the $p$-divisible
mass, totalling $1$. Multiplying over $p \mid d$ gives $1$.
(b) is immediate from (a) with Prop. 3.1 and Theorem 3.2.
$\square$

*Probabilistic form.* Let $u_s = \ln(J/s)/\ln z$. Then the
marginal cost per unit merit is an expectation against $W_d$
over the reachable channels,
$$ \frac{dE}{dm} \;=\; e^{\gamma}\,
   \mathbb{E}_{W_d}\!\bigl[\,\omega(u_S)\,
   \mathbf{1}\{S \le m/2\}\,\bigr]
   \;+\; (\text{smooth-channel term}), $$
(the smooth term is not a boundary correction: it carries
$\approx 24\%$ of $E$ at production configurations and is the
agent of the finite-$m$ invariance measured in Example 3.5),
with $\omega(u) = 1/u$ on the working range $u \in (1,2)$: the
Buchstab factor weighted by the channel distribution, cut by
the truncation.

## Corollary 3.4 (deep limit: the fence-rate law, d-free)
Fix $u \in (1, 2)$ and let $L \to \infty$. Then
$\ln s/\ln z \to 0$ for every fixed channel and $F_d \to 1$, so
$$ \frac{dE}{dm} \;\longrightarrow\; e^{\gamma}\,\omega(u)
   \qquad\text{for every admissible } d. $$
This is the microscopic fence-rate law, measured and confirmed
independently in an earlier phase of the program (statistics in
Section 5.5). The independently observed cusp of the rate at
$u = 2$ is, in the present framework, the opening of the
two-prime channels at the boundary of Prop. 3.1's range.

## Example 3.5 (redistribution: d = 2310 versus d = 30030)
The lightest channel weights $w_d(s)$:

    s        2       4       6       8      10
    2310   .1406   .0703   .0938   .0352   .0375
    30030  .1289   .0645   .0859   .0322   .0344

Reachable mass $F_d(m)$ (channel $s$ opens at merit $2s$):

    m        4      12      24      40    ->inf
    2310   .1406  .3047   .4242   .5159    1
    30030  .1289  .2793   .3889   .4729    1
    ratio  .9167  .9167   .9167   .9167    1

The ratio is exactly $11/12$ throughout $m < 52$, and the
general mechanism is exact: adjoining a new odd prime $p$ to
$d$ multiplies every $p$-coprime channel mass by
$(p-2)/(p-1)$ and creates $p$-divisible channels carrying the
removed mass, the lightest at $s = 2p$ -- so all reachable
mass below merit $4p$ is rescaled by $(p-2)/(p-1)$ and the
difference is parked beyond merit $4p$. The prime-channel
mass thus shifts, but the total cost does NOT follow it: the
pure-smooth positions run to $s \le J = (m/2)\lambda$, far past
the prime-channel truncation, and their mass moves oppositely.
Measured at $(D, m) = (616, 41.94)$: prime-side ratio
$30030/2310 = 0.9142$ (the predicted $11/12$), smooth-side
ratio $1.2904$ at a $24.1\%$ share, total $1.0050$ -- the
invariance of Theorem 3.3 manifests at finite $m$ to half a
percent. The divisor dial is therefore cost-neutral in total at
working merits, redistributing between prime and smooth
channels; residual $d$-selection in the optimizer of Section 6
is driven by the supply terms ($(p-1)/p$ of admissible
cofactors, $\ln p$ of budget; Sections 2.1, 6.3), not by rate.

## Proposition 3.6 (Q-invariance)
With $\beta$ as in (H1),
$\beta \cdot \Theta(z,Q) = e^{\gamma}\ln z\,/\lambda\cdot
 (1 + O(1/\ln z))$, independent of $Q$. Consequently
$E = \beta\,\mathbb{E}[S]$ does not depend on the sieve depth.
*Proof.* Mertens' third theorem applied to the ratio
$\prod_{p \le Q}/\prod_{p \le z}$. $\square$
(Measured drift $10^5 \to 10^6$: $0.24\%$.)

## Corollary 3.7 (normalization; hygiene defect)
(a) For a window with no primorial structure the survivor
density is $e^{-\gamma}/\ln Q\,(1+o(1))$ and
$\sigma := E/m = 1$ identically: $\sigma$ measures the
structural discount against unstructured search.
(b) If $p \mid d$ and $p \mid k$, then $p \mid n_0$: the prime
reverts to structural, closes every channel it divides, and
applies no class thinning; the average count inflates by the
exactly computable factor
$T_d^{(p\ \mathrm{struct})}/T_d$. (Applied to the public record
set in Sections 5--6.)

## 3.8 The two-variable law and the shelf
Define $u = 1 + \ln(m/2)/L$. The exact expression depends on
$(u, m)$ jointly -- the prime side through $u$, the truncation
through $m$ -- and no scalar coordinate reproduces it
(preregistered exclusion, Section 4). Records occupy a narrow
locus ("the shelf") on which $m$ and $u$ are linked through
$L \in [5.3, 13.7]$ across the entire record universe; along it
the surface projects to the practitioners' curve $\sigma(u)$
with fitted slope $1.8169 \pm 0.0367$.

## Conjecture 3.9 (shelf slope)
In the shelf limit ($\lambda \to \infty$, $z = \lambda$, $d$
fixed, $\ln Q/\ln z$ fixed, $m$ and $u$ linked as above),
$$ \frac{\partial \sigma}{\partial u} \longrightarrow
   e^{\gamma} \quad (u \to 1^+), $$
uniformly in admissible $d$, with corrections $O(1/L)$.
Numerically the exact sum yields slope $1.6749$ against a
measured $1.6981$ on identical design matrices
($e^{\gamma} = 1.7811$). The naive local derivation fails --
the lip is the channel staircase of Theorem 3.3, not a smooth
density -- and the constant is emergent along the shelf; the
refuted derivation is preserved in Appendix A (H6).
