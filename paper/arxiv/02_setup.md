# 2. Setup and notation

## 2.1 The construction
Fix $D$ and write $\lambda = \ln n_0 \approx D\ln 10$,
$L = \ln\lambda$. Let $z$ be a bound, $d$ an even squarefree
divisor of the primorial $z\#$, and $k$ an odd integer with
$\gcd(k,d) = 1$. Set
$$ n_0 = k\, z\# / d, \qquad \text{candidates } n_0 + j,\
   |j| \le j_f . $$
Supply of centers at fixed height forces
$z = \lambda\,(1 + O(\mathrm{kdig}\cdot\ln 10/\lambda))$; all
certified configurations satisfy $z/\lambda \in [0.98, 1.03]$.
Windows are indexed by $k$; the admissible count is
$\tfrac{9}{10}\,10^{\mathrm{kdig}}\,\varphi(d)/d$.

## 2.2 Prime regimes
For a prime $p \le Q$ acting on the window:
- structural ($p \le z$, $p \nmid d$): $p \mid n_0$, so
  $p \mid n_0 + j \iff p \mid j$;
- class ($p \mid d$): $p \nmid n_0$; $p$ eliminates the single
  residue $j \equiv -n_0 \pmod p$, determined by $k \bmod p$;
- deep ($z < p \le Q$): as class, with
  $-n_0 \bmod p$ equidistributing in $k$.
Since $d$ is even and $k$ odd, $n_0$ is odd and all odd $j$ are
eliminated; parity is the first class prime.

## 2.3 Survivors and channels
Call $j$ a survivor if $n_0 + j$ has no prime factor $\le Q$.
Throughout the working range $j_f = (m/2)\lambda \ll z^2$.
For $s$ an even $d$-smooth integer define the channel weight
$$ c_d(s) = \prod_{p \mid d,\ p\ \mathrm{odd},\ p \nmid s}
   \Bigl(1 - \tfrac{1}{p-1}\Bigr), \qquad
   w_d(s) = c_d(s)/s, $$
and the deep thinning
$\Theta(z,Q) = \prod_{z < p \le Q}(1 - 1/p)$.

## 2.4 The counting expression
For a one-sided edge $J$ define
$$ T_d(J; z, Q) \;=\; \Theta(z,Q) \sum_{s\ \mathrm{even}\
   d\text{-smooth}} c_d(s)\,
   \Bigl[ \bigl(\pi(J/s) - \pi(z)\bigr)_+ + \mathbf{1}_{s\le J}
   \Bigr], $$
and for the symmetric window $S^{\mathrm{th}}(m)
= 2\,T_d\bigl((m/2)\lambda\bigr)$. Section 3 proves this is
exactly the class-torus average of the survivor count
(Theorem 3.2).

## 2.5 Model hypotheses (quarantined)
The passage from counting to cost uses exactly two unproved
assumptions, stated once:
(H1) survivor primality: for $j$ a survivor,
$\Pr[\,n_0+j \text{ prime}\,] = \beta\,(1+o(1))$ with
$\beta = e^{\gamma}\ln Q/\lambda$ (Mertens-normalized; of
Hardy--Littlewood type);
(H2) independence: primality events across survivors of a
window are independent.
The passage from (H1)--(H2) to the success probability and the
geometric cost law is carried out, with its exact error
structure, in Proposition 2.6 below; everything in Section 3 is
unconditional.

## 2.6 From the hypotheses to the cost law
Throughout, $\beta$ is taken constant across a window: the
variation of $\lambda$ over $|j| \le j_f$ is $O(j_f/n_0)$ and
beneath every other scale in this paper.

**Proposition 2.6.** Assume (H1)--(H2). Then:

(a) A realized window with survivor count $S$ succeeds (no
survivor in the target range is prime) with probability
$(1-\beta)^S$; over the class torus of Theorem 3.2 the success
probability is the probability generating function of $S$,
$$ P \;=\; \mathbb{E}_k\bigl[(1-\beta)^{S}\bigr]. $$

(b) If $S$ were Poisson with mean $\mathbb{E}[S]$, then
$P = e^{-\beta\,\mathbb{E}[S]} = e^{-E}$ exactly.

(c) In general, with $\kappa_{[r]}$ the factorial cumulants of
$S$ ($\kappa_{[1]} = \mathbb{E}[S]$),
$$ -\ln P \;=\; \beta\,\mathbb{E}[S]
   \;-\; \sum_{r \ge 2} \frac{(-\beta)^r}{r!}\,\kappa_{[r]}, $$
and every $\kappa_{[r]}$ is exactly computable on the torus by
the $r$-tuple extension of Theorem 3.2 (Remark 3.2.1 displays
$r = 2$). The leading correction enters $E$ at
$O(\beta^2 \kappa_{[2]})$, with $\beta \le 0.02$ at every
production configuration; pairwise torus correlations are
negative at deep primes and positive for class-aligned pairs,
so the sign and size are matters of computation, not
assumption.

(d) Distinct cofactors realize distinct torus points, so a
campaign's windows-to-success is a geometric mixture over
realizations of $S$; by the concentration of $S$
(Remark 3.2.1) it collapses to the geometric law with success
probability $e^{-E}$, exactly in the Poisson case and up to the
same factorial-cumulant corrections in general.

*Proof.* (a) is (H1)--(H2) directly. (b): the Poisson
probability generating function is
$\mathbb{E}[x^S] = e^{\mu(x-1)}$; put $x = 1-\beta$. (c): the
factorial-cumulant expansion
$\ln \mathbb{E}[(1+u)^S] = \sum_{r\ge 1} \kappa_{[r]} u^r/r!$
at $u = -\beta$; exact computability of the $r$-tuple joint
survival factors is the CRT argument of Theorem 3.2 applied to
$r$ distinct offsets. (d) is immediate. $\square$

We define $E = \beta\,\mathbb{E}[S]$ and report all costs as
quantiles of the geometric law with mean $e^{E}$;
Proposition 2.6 fixes the status of that convention -- exact
under Poisson statistics, first factorial cumulant in general
-- and the composite law is additionally tested against
realized campaigns in Sections 4.4 and 6.5.
