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
= 2\,T_d\bigl((m/2)\lambda\bigr)$. Section 3 proves this is the
exact large-$k$ average of the survivor count.

## 2.5 Model hypotheses (quarantined)
The passage from counting to cost uses exactly two unproved
assumptions, stated once:
(H1) survivor primality: for $j$ a survivor,
$\Pr[\,n_0+j \text{ prime}\,] = \beta\,(1+o(1))$ with
$\beta = e^{\gamma}\ln Q/\lambda$ (Mertens-normalized; of
Hardy--Littlewood type);
(H2) independence: primality events across survivors of a
window are independent.
Under (H1)--(H2), a window succeeds (no survivor is prime across
the target range) with probability $e^{-E}$,
$E = \beta\,\mathbb{E}[S]$, and windows-to-success is geometric
with mean $e^{E}$. All cost statements in Section 6 are exact
quantiles of this law; everything in Section 3 before the model
is unconditional.
