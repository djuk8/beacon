# 6. Applications

## 6.1 From counts to costs
Under (H1)--(H2), a target's cost in windows is geometric with
mean $e^{E}$ (Proposition 2.6) and we report medians ($\ln 2\, e^{E}$). Tests per
window for an $E$-geometric ring ladder equal
$\Delta E/(1 - e^{-\Delta E})/\beta$ exactly ($2.0800$ at the
deployed rung $\Delta E = 1.7$). Device unit: one NVIDIA RTX
5090 executing the repository's gated kernel for $86{,}400$ s
("device-day"), with the measured sustained rate ladder
$516{,}358 / 67{,}232 / 8{,}723 / 1{,}201 / 383.4 / 141.8$
tests/s at the $2048,\dots,32768$-bit classes; a second device
(NVIDIA RTX 4090) is modeled at $0.60\times$ pending a
one-hour gate run reproducible by any reader. Above $9{,}863$
digits no measured device class exists and costs are stated in
core-days against three measured CPU anchors.
[Footnote: at the dated cluster rate of \$0.375 per device-hour
(August 2026 market), one device-day is \$9.00; the optimum of
Table 6.1 corresponds to roughly \$19{,}000 median.]

## 6.2 Placement
$E(m, D)$ is computable everywhere, so any target admits a
placement scan. Table 6.1, maximal-merit target $m = 41.9388$:

    D        E      median device-days
      87   35.66     5.4e5   (z-extrapolated; infeasible, 6.3)
     340   30.01     7.4e3
     480   28.81     3.1e3
     616   28.16     2.1e3   <- optimum (2048-bit boundary)
    1230   26.37     5.4e3
    2460   24.81     1.74e4

$E$ falls monotonically with height while the per-test cost
rises through device classes; calendar optima therefore sit on
class boundaries. Placement alone is worth a factor $\approx
260$ against the incumbent record's home height, before design
quality enters.

## 6.3 The supply constraint
A configuration is realizable only if enough centers exist:
$\ln(\mathrm{supply}) = \mathrm{kdig}\,\ln 10 +
\ln(0.9\,\varphi(d)/d)$, feasible iff
$\ln(\mathrm{supply}) \ge E + 1$. At the maximal-merit record's
own height ($m = 41.94$, $D = 87$) every certified design is
infeasible by many orders of magnitude in supply, and even the
extrapolated designs of Table 6.1 require the entire admissible
$k$-range. This explains why that record --
set by the Gapcoin proof-of-work network in December 2017
[gapcoin2017] -- has stood since: constructive attack at its home height is not
expensive but impossible at certified designs, while the same
merit is realizable at $D = 616$ for the cost in Table 6.1.

## 6.4 The hygiene census
Parsing the full public list ($121{,}457$ rows; $118{,}718$
primorial expressions, $100.0\%$ of non-literal non-power rows)
and applying Corollary 3.7(b) to each artifact yields $3{,}263$
records with survivor inflation $\ge 1.15$:

    discoverer   rows   defect          inflation
    A.Renyer    1,998   715 | k         1.32--1.42
    Jacobsen      876   15 | k          2.2--2.42
    M.Jansen      232   mixed           --
    RobSmith      112;  Rosnthal 42;  PierCami 3.

Inflation $r$ multiplies the exponent, hence the window bill by
$e^{(r-1)E}$ -- typically $2$--$5\times$ at the affected
configurations. Notably, the $107{,}102$-row historical
first-occurrence family (small divisors such as $d = 30$) is
almost entirely clean, although random cofactors would flag
nearly half of it: the classical community evidently enforced
$\gcd(k, d) = 1$ as folklore, and the modern large-$d$
campaigns dropped the habit. The remedy is a one-line
constraint in any cofactor generator; we suggest the same check
as a submission-time lint for the public list.

## 6.5 Deployed practice and the computed optima
Fed only the public thresholds, the optimizer reproduces the
authors' own deployed campaigns -- monument board: chosen
$D = 26{,}558$, $E = 7.17$ versus deployed $26{,}600$, $7.17$;
merit-$30$ board: $6{,}137$, $14.70$ versus $6{,}152$, $14.74$;
and the $616$-class theater, whose deployed $k$-budget the
feasibility test identifies as marginal, exactly as operated.
Conversely the law's global cost minimum -- the
$6.4$--$8.1\times 10^3$-digit first-occurrence band at
$E \approx 2$ -- is precisely where the community's current
submissions concentrate. Deployed practice, placed before this
law existed, is consistent with its optima on both sides.
