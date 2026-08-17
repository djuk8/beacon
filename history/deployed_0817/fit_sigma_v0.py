#!/usr/bin/env python3
"""fit_sigma_v0.py -- the proper sigma(u) fit with swap-depth covariate.

Data: 20 exact-sieve audits of the public top-20 (2026-08-05) + the two
live theaters' exact E (monument, strike) + our record (all MEASURED),
plus 5 merit-crown design points at u 1.56-1.66 (min-of-7 selection bias
corrected by -0.35 e-units, down-weighted 0.5 -- they alone pin the
quadratic term, flag stands). Renyer's two brute-k rows are EXCLUDED
from the fit and reported as residuals: their positive offset IS the
measured value of design vs brute force.

Model: sigma = a*x + b*x^2 + c*(nsw - 6),  x = u - 1, NO intercept
(sigma(1) = 0 is structural: the resonance floor is free).
Test of interest: a vs e^gamma = 1.7811.

Outputs: coefficients +/- approx SE, weighted R^2, per-point residuals,
brute-inefficiency in e-units, fitted-vs-exact on the six pricer_v1
selftest anchors, and a paste-ready SIGMA_KNOTS block (nsw=6 line).
"""
import math
import numpy as np

GAMMA = 0.5772156649015329
LN10 = math.log(10)

# (u, sigma, nsw, weight, tag)
PTS = [
    (1.164, 0.274, 9, 1.0, "t20r01 Hoglund"),
    (1.168, 0.255, 7, 1.0, "t20r02 Hoglund"),
    (1.159, 0.230, 9, 1.0, "t20r03 Hoglund"),
    (1.155, 0.251, 8, 1.0, "t20r04 J&A"),
    (1.158, 0.254, 6, 1.0, "t20r05 J&A"),
    (1.126, 0.168, 9, 1.0, "t20r06 Hoglund"),
    (1.168, 0.254, 6, 1.0, "t20r07 Raab"),
    (1.162, 0.240, 8, 1.0, "t20r08 J&A"),
    (1.157, 0.232, 7, 1.0, "t20r09 J&A"),
    (1.154, 0.246, 6, 1.0, "t20r10 RS/J&A"),
    (1.165, 0.251, 7, 1.0, "t20r11 J&A"),
    (1.129, 0.188, 6, 1.0, "t20r12 RSmith"),
    (1.138, 0.189, 5, 1.0, "t20r13 J&A"),
    (1.211, 0.338, 9, 1.0, "t20r14 Raab nearzd"),
    (1.102, 0.139, 9, 1.0, "t20r15 Hoglund"),
    (1.192, 0.323, 8, 1.0, "t20r16 Raab nearzd"),
    (1.164, 0.251, 5, 1.0, "t20r17 J&A"),
    (1.171, 0.259, 6, 1.0, "t20r19 RSmith"),
    (1.209, 0.3576, 6, 1.5, "monument exact"),
    (1.280, 0.4897, 6, 1.5, "strike exact"),
    (1.317, 0.5391, 6, 1.5, "our record exact"),
    # design points, bias-corrected (E_mean - 0.35)/m, wt 0.5
    (1.66, 0.8427, 5, 0.5, "87d design MJ"),
    (1.65, 0.8586, 6, 0.5, "87d design RS"),
    (1.63, 0.8233, 5, 0.5, "97d design"),
    (1.56, 0.7676, 5, 0.5, "164d design"),
    (1.56, 0.7608, 5, 0.5, "175d design"),
]
BRUTE = [(1.130, 0.239, 6, "Renyer r18 (brute 37-digit k)"),
         (1.150, 0.286, 6, "Renyer r20 (brute 37-digit k)")]

ANCHORS = [  # (name, m, D, E_exact, nsw)
    ("t20 row1", 18.0669, 385713, 4.94, 9),
    ("t20 row14", 20.3767, 99750, 6.89, 9),
    ("t20 row15", 6.6622, 303518, 0.93, 9),
    ("monument", 20.05, 26600, 7.17, 6),
    ("strike", 30.10, 6152, 14.74, 6),
    ("record", 32.385, 2705, 17.46, 6),
]


def design_matrix(rows):
    X = np.array([[u - 1, (u - 1) ** 2, n - 6] for u, s, n, *_ in rows])
    y = np.array([s for _, s, *_ in rows])
    return X, y


def main():
    X, y = design_matrix(PTS)
    w = np.array([p[3] for p in PTS])
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    a, b, c = beta
    yhat = X @ beta
    resid = y - yhat
    dof = len(y) - 3
    s2 = float(np.sum(w * resid ** 2) / dof)
    cov = s2 * np.linalg.inv((X * w[:, None]).T @ X)
    se = np.sqrt(np.diag(cov))
    ybar = np.average(y, weights=w)
    r2 = 1 - np.sum(w * resid ** 2) / np.sum(w * (y - ybar) ** 2)

    print("sigma(u) = a*(u-1) + b*(u-1)^2 + c*(nsw-6)   [no intercept]")
    print(f"  a = {a:.4f} +/- {se[0]:.4f}   (e^gamma = {math.exp(GAMMA):.4f}"
          f" -> a - e^g = {a - math.exp(GAMMA):+.4f}, "
          f"{abs(a - math.exp(GAMMA)) / se[0]:.1f} sigma)")
    print(f"  b = {b:.4f} +/- {se[1]:.4f}   (concavity; pinned by the 5"
          " design points, wt 0.5 -- flag stands)")
    print(f"  c = {c:+.5f} +/- {se[2]:.5f}  per extra swapped prime")
    print(f"  weighted R^2 = {r2:.4f}, dof = {dof}, "
          f"rms resid = {math.sqrt(s2):.4f}\n")

    print("residuals (obs - fit):")
    for (u, s, n, wt, tag), r in zip(PTS, resid):
        print(f"  {tag:>22} u={u:.3f} nsw={n} wt={wt}: {r:+.4f}")
    print("\nbrute-k rows (excluded from fit; offset = design premium):")
    for u, s, n, tag in BRUTE:
        pred = a * (u - 1) + b * (u - 1) ** 2 + c * (n - 6)
        print(f"  {tag:>34}: obs {s:.3f} vs designed-line {pred:.3f} "
              f"-> +{s - pred:.3f} sigma-units")

    print("\nanchor check (fitted E vs exact, u from identity):")
    for name, m, D, Ex, n in ANCHORS:
        u = 1 + math.log(m / 2) / math.log(D * LN10)
        Ef = m * (a * (u - 1) + b * (u - 1) ** 2 + c * (n - 6))
        print(f"  {name:>10}: fitted {Ef:5.2f} vs exact {Ex:5.2f} "
              f"({(Ef - Ex) / Ex * 100:+5.1f}%)")

    print("\npaste into pricer_v1.SIGMA_KNOTS (nsw=6 line):")
    print("SIGMA_KNOTS = [")
    for u in (1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.45,
              1.55, 1.66):
        x = u - 1
        print(f"    ({u:.3f}, {max(0.0, a * x + b * x * x):.4f}),")
    print("]")


if __name__ == "__main__":
    main()
