# 3. The law

## 3.1 The benchmark and the sigma normalization
Write E = beta * E[S] for a window (2.4) and define sigma = E/m.
For a window with NO primorial structure the survivor density is
Mertens' e^-gamma / ln Q, and the e^gamma in beta cancels it:

    sigma_unstructured = 1,  identically and exactly.

sigma is therefore the STRUCTURAL DISCOUNT relative to blind
search: the entire content of gap engineering is how far below 1
a design pushes sigma, and for how much merit.

## 3.2 The channel-mass identity and the truncated rate
Define the class-thinned harmonic weight of channel s:

    w_d(s) = c_d(s) / s     (s even d-smooth, c_d as in 2.4).

IDENTITY (d-neutrality, sharp form). SUM over ALL even d-smooth s
of w_d(s) = 1, for every admissible d. (Per odd prime p | d the
channel sum factorizes to (p-2)/(p-1) + 1/(p-1) = 1.) The w_d are
a probability mass on channels; the divisor dial redistributes
cost, it cannot create or destroy it.

The marginal cost per unit merit then takes the continuum form

    rate(u, m) ~ e^gamma * SUM_{s <= m/2} w_d(s) * omega(u_s),

with omega the Buchstab function, u_s the roughness of the
channel's prime cofactor, and the sum truncated by 2.3's
constraint s <= m/2. Two limits anchor it. Untruncated (all
channels open) the identity gives the microscopic fence-rate law
rate = e^gamma * omega(u) -- the skeleton, confirmed
independently at 6-8 sigma including the Buchstab cusp at u = 2
[P1]. Truncated, the reachable mass

    F_d(m) = SUM_{s <= m/2} w_d(s)  < 1

is the FILLING: the discount 1 - sigma is missing channel mass,
and it fills as a staircase -- channel s opens at merit m = 2s
with jump w_d(s). For d = 30030, w_d(2) = 0.1289: a fresh desert
edge runs at ~13% of the skeleton rate, which is why deserts are
cheap and why the lip of the cost curve is a staircase, not a
line (this killed the naive lip derivation; App A, H6). All
certified numbers below come from the exact sum (2.4); this
subsection is its readable shadow.

## 3.3 Two coordinates, not one
Set lamda-height L = ln lam and the identity coordinate

    u(m, D) = 1 + ln(m/2) / L,

the roughness of the fence position. The skeleton depends on u;
the filling depends on m alone. The cost surface is genuinely
two-dimensional: no scalar coordinate exists (preregistered test
H4, REFUTED for every candidate). The signature is visible in raw
data: at fixed u, sigma FALLS with L on the near shelf (u < 1.55)
and RISES with L beyond it -- the 1/L-coefficient changes sign --
which no sigma(u)-only law can produce.

## 3.4 The record shelf, and where e^gamma lives
Records inhabit a narrow locus -- the SHELF -- where m and u lock
together through L, and L spans only 5.30 to 13.70 across the
ENTIRE record universe (87 to 385,713 digits): log-log is flat,
and a two-variable surface photographed along the shelf looks
like a curve. That curve is the empirical sigma(u): fitted on 26
exact-sieved artifacts as

    sigma(u) ~ a (u-1) + b (u-1)^2,   a = 1.8169 +/- 0.0367,
                                      b = -0.5587 +/- 0.0858,

with a within 1.0 sigma of e^gamma = 1.7811. The convolution
reproduces the shelf without adjustment: on the identical design
matrix, theory slope 1.6749 versus measured 1.6981. That the
shelf slope equals e^gamma exactly, in a suitable limit of the
certified sum, is Conjecture T1 (Section 7); numerically it
emerges to a few percent with no parameter anywhere.

## 3.5 The Cramer scale
u = 2 corresponds to gap = 2 lam^2 -- the Cramer-Shanks maximal
scale. Approaching it, the filling saturates and the measured
surface crosses sigma = 1 near u ~ 1.9 at moderate heights,
continuing to rise slowly (1.11 at u = 1.97, zd = 3163): the
structural discount is EXHAUSTED at the Cramer scale, and mildly
inverted past it. An earlier, prettier hypothesis -- exact
saturation at 1 with classical marginal rate on the boundary --
was preregistered and REFUTED (App A, H1/H2); the connection to
the Cramer-Granville correction remains suggestive and is
discussed, with citations to be verified, in Section 10.

## 3.6 Certified domain
Exhaustive-sieve certification covers: zd from 79 to 888,887; u
to 1.97; z = zd/lam in [0.98, 1.03]; d-families from 2310 to 23#;
k from 1 to 10^36; 64 synthetic anchors, 20 published records,
3 campaigns, 7 production ring designs, fixed-m transects.
Outside this domain every emitted number carries an explicit
extrapolation flag (Section 8). Failed closed forms and dead
coordinates are not deleted; they are the ledger (Section 4,
App A).
