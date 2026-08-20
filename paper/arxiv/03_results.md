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

## Proposition 3.2 (exact average count)
Fix $z, d, Q, j_f$ and let $k$ range over odd residues coprime
to $d$ in $[K, 2K]$. Then as $K \to \infty$,
$$ \mathbb{E}_k[S] \;=\; \bigl(1 + o(1)\bigr)\,
   2\,T_d(j_f; z, Q). $$
*Proof sketch.* Condition on the structural survivors of
Prop. 3.1. Each class or deep prime $p$ eliminates the residue
$-n_0 \equiv -k\,(z\#/d) \pmod p$; as $k$ traverses full
residue systems these classes are exactly uniform and, by CRT,
exactly independent across $p$, so the per-position survival
probability over a full period is
$\prod_p (1 - \mathbf{1}[p \nmid j]/(p-1'))$ with the
appropriate local factor, and boundary effects are $O(1/K)$ per
modulus. Summing per channel: for $j = sq$ the survival factor
is $c_d(s)$ for the fixed divisor part, while for the prime
cofactor the count of $q \in (z, J/s]$ in each admissible class
mod the (finitely many, bounded) odd divisors of $d$
equidistributes by the prime number theorem in arithmetic
progressions (Siegel--Walfisz suffices; moduli are fixed).
Deep primes contribute the exact factor $\Theta(z,Q)$ in the
average. Collecting terms yields $T_d$. $\square$

## Proposition 3.3 (channel-mass identity)
$\displaystyle \sum_{s\ \mathrm{even}\ d\text{-smooth}} w_d(s)
 = 1$ for every admissible $d$.
*Proof.* The sum factors as an Euler product over the primes of
$d$. The prime $2$ contributes $\sum_{a\ge 1} 2^{-a} = 1$. Each
odd $p \mid d$ contributes
$\bigl(1 - \tfrac1{p-1}\bigr)\cdot 1 + \sum_{a\ge 1} p^{-a}
 = \tfrac{p-2}{p-1} + \tfrac{1}{p-1}\cdot\tfrac{p}{p}\cdot
 \tfrac{p}{p-1}^{-1}$; explicitly, the $p$-free mass carries
weight $1 - \tfrac1{p-1}$ and the $p$-divisible mass
$\tfrac1{p-1}$, summing to $1$. Multiplying over $p \mid d$
gives $1$. $\square$

*Interpretation.* $\{w_d(s)\}$ is a probability mass on
channels: the divisor dial redistributes cost among channels but
cannot create or destroy it. The truncation $s \le m/2$ imposed
by $q > z$ (Prop. 3.1) makes the reachable mass
$F_d(m) = \sum_{s \le m/2} w_d(s) < 1$ the sole source of the
structural discount; it opens as a staircase, channel $s$ at
merit $2s$ with jump $w_d(s)$ (e.g. $w_{30030}(2) = 0.1289$).

## Proposition 3.4 (Q-invariance)
With $\beta$ as in (H1),
$\beta \cdot \Theta(z,Q) = e^{\gamma}\ln z\,/\lambda\cdot
 (1 + O(1/\ln z))$, independent of $Q$. Consequently
$E = \beta\,\mathbb{E}[S]$ does not depend on the sieve depth.
*Proof.* Mertens' third theorem applied to the ratio
$\prod_{p \le Q}/\prod_{p \le z}$. $\square$
(Measured drift $10^5 \to 10^6$: $0.24\%$.)

## Corollary 3.5 (normalization; hygiene defect)
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

## 3.6 The two-variable law and the shelf
Define $u = 1 + \ln(m/2)/L$. The exact expression depends on
$(u, m)$ jointly -- the prime side through $u$, the truncation
through $m$ -- and no scalar coordinate reproduces it
(preregistered exclusion, Section 4). Records occupy a narrow
locus ("the shelf") on which $m$ and $u$ are linked through
$L \in [5.3, 13.7]$ across the entire record universe; along it
the surface projects to the practitioners' curve $\sigma(u)$
with fitted slope $1.8169 \pm 0.0367$.

## Conjecture 3.7 (shelf slope)
In the shelf limit ($\lambda \to \infty$, $z = \lambda$, $d$
fixed, $\ln Q/\ln z$ fixed, $m$ and $u$ linked as above),
$$ \frac{\partial \sigma}{\partial u} \longrightarrow
   e^{\gamma} \quad (u \to 1^+), $$
uniformly in admissible $d$, with corrections $O(1/L)$.
Numerically the exact sum yields slope $1.6749$ against a
measured $1.6981$ on identical design matrices
($e^{\gamma} = 1.7811$). The naive local derivation fails --
the lip is the channel staircase of Prop. 3.3, not a smooth
density -- and the constant is emergent along the shelf; the
refuted derivation is preserved in Appendix A (H6).
