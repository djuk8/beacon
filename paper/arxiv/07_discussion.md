# 7. Discussion and open problems

## 7.1 Context
The asymptotic theory of large gaps concerns lower bounds for
$\max_{p \le x} G(p)$: Westzynthius [westzynthius1931], Erd\H{o}s
[erdos1935] and Rankin [rankin1938] established the classical
orders, and the Erd\H{o}s prize problem on Rankin's bound was
resolved in 2016 by Ford--Green--Konyagin--Tao [fgkt2016] and,
independently, Maynard [maynard2016], with the five-author sequel
[fgkmt2018]; refined probabilistic models appear in
Banks--Ford--Tao [banksfordtao2023]. This paper concerns the
complementary finite, constructive regime -- the exact price of
a specified gap at a specified height -- and the two regimes
meet at $u = 2$, the Cram\'er--Shanks maximal scale
$G \sim \ln^2 p$ [cramer1936, shanks1964]. Granville
[granville1995], correcting Cram\'er's model for divisibility by
small primes in the spirit of Maier [maier1985, maier1981,
maierpomerance1990], proposed
$\limsup G(p)/\ln^2 p \ge 2e^{-\gamma} = 1.1229\ldots$; in our
coordinate every constant-$\xi$ locus $G = \xi \ln^2 p$ is the
line $u \to 2$, distinct constants differing only at $O(1/L)$,
so the certified crossing of $\sigma = 1$ near $u \approx 1.9$
and its mild inversion beyond sit precisely in the regime those
corrections address. An exact-saturation hypothesis at the
boundary was preregistered and refuted (Appendix A); the present
data neither prove nor contradict the Granville constant, and we
regard the certified surface near $u = 2$ as a measurement the
refined models can be tested against.

## 7.2 Open problems
1. Conjecture 3.9 (the shelf slope equals $e^{\gamma}$).
2. Asymptotics of $T_d$: the expression interpolates Buchstab
   [buchstab1937, debruijn1950] on the prime side and Dickman
   [dickman1930, debruijn1951] on the smooth side with
   elementary weights; a uniform two-variable asymptotic would
   subsume 3.9 and likely name a special function.
3. Replacement of (H1)--(H2) by average results of
   Hardy--Littlewood type [hardylittlewood1923] over the
   $k$-family.
4. Constellations: the same channel calculus with admissible
   tuples in place of empty windows, tied to the
   Hardy--Littlewood singular series (the constellation
   analogue of Theorem 3.3).
5. Finite-size Cram\'er: testing the surface against the
   exhaustive below-$2^{64}$ gap data [nicely1999,
   primegaplist].

## 7.3 Data and code availability
Every number in this paper reconstructs from the public
repository (certified evaluator with import-time fingerprint,
gates, preregistration files, correction ledger) and the data
deposit (DOI: [SLOT]); every find reconstructs from a one-line
artifact $(k, z, d, \text{fences})$. Code is released under the
Apache License 2.0; text and data under CC BY 4.0.
