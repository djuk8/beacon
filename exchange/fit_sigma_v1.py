#!/usr/bin/env python3
"""fit_sigma_v1.py -- sigma(u) refit in ONE coordinate.

v0 mixed coordinates: audit points carried measured u_max (asymmetry-
inflated) while the pricer and anchors use the identity
u = 1 + ln(m/2)/ln(D*ln10). This version stores (m, D, sigma) and
computes identity-u internally for every point -- chart and engine now
share one coordinate. Same model, same outputs, plus a direct test of
the closed-form candidate  sigma(u) = e^gamma * ln(u).

Model: sigma = a*x + b*x^2 + c*(nsw-6), x = u-1, no intercept.
"""
import math
import numpy as np

GAMMA = 0.5772156649015329
EG = math.exp(GAMMA)
LN10 = math.log(10)

# (m, D, sigma_exact, nsw, weight, tag)
PTS = [
    (18.0669, 385713, 0.274, 9, 1.0, "t20r01"),
    (12.3094, 289083, 0.255, 7, 1.0, "t20r02"),
    (11.6726, 289082, 0.230, 9, 1.0, "t20r03"),
    (14.9985, 208095, 0.251, 8, 1.0, "t20r04"),
    (14.5395, 208096, 0.254, 6, 1.0, "t20r05"),
    (8.5590, 337314, 0.168, 9, 1.0, "t20r06"),
    (13.1829, 216841, 0.254, 6, 1.0, "t20r07"),
    (13.5259, 208093, 0.240, 8, 1.0, "t20r08"),
    (12.9012, 208094, 0.232, 7, 1.0, "t20r09"),
    (13.4804, 173457, 0.246, 6, 1.0, "t20r10"),
    (14.3353, 157490, 0.251, 7, 1.0, "t20r11"),
    (10.2203, 216849, 0.188, 6, 1.0, "t20r12"),
    (10.1314, 208102, 0.189, 5, 1.0, "t20r13"),
    (20.3767, 99750, 0.338, 9, 1.0, "t20r14 nearzd"),
    (6.6622, 303518, 0.139, 9, 1.0, "t20r15"),
    (19.6406, 97234, 0.323, 8, 1.0, "t20r16 nearzd"),
    (12.4693, 151940, 0.251, 5, 1.0, "t20r17"),
    (12.4164, 135376, 0.259, 6, 1.0, "t20r19"),
    (20.05, 26600, 0.3576, 6, 1.5, "monument"),
    (30.10, 6152, 0.4897, 6, 1.5, "strike"),
    (32.385, 2705, 0.5391, 6, 1.5, "record"),
    (41.9388, 87, 0.8427, 5, 0.5, "87d design MJ"),
    (41.9388, 87, 0.8586, 6, 0.5, "87d design RS"),
    (37.8241, 97, 0.8233, 5, 0.5, "97d design"),
    (38.5122, 164, 0.7676, 5, 0.5, "164d design"),
    (39.6202, 175, 0.7608, 5, 0.5, "175d design"),
]
BRUTE = [(9.4680, 179864, 0.239, 6, "Renyer r18"),
         (9.8217, 151952, 0.286, 6, "Renyer r20")]


def uid(m, D):
    return 1.0 + math.log(m / 2.0) / math.log(D * LN10)


def main():
    u = np.array([uid(m, D) for m, D, *_ in PTS])
    y = np.array([p[2] for p in PTS])
    n = np.array([p[3] for p in PTS])
    w = np.array([p[4] for p in PTS])
    X = np.column_stack([u - 1, (u - 1) ** 2, n - 6])
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    a, b, c = beta
    resid = y - X @ beta
    dof = len(y) - 3
    s2 = float(np.sum(w * resid ** 2) / dof)
    cov = s2 * np.linalg.inv((X * w[:, None]).T @ X)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - np.sum(w * resid ** 2) / np.sum(
        w * (y - np.average(y, weights=w)) ** 2)

    print("IDENTITY-COORDINATE FIT: sigma = a*x + b*x^2 + c*(nsw-6)")
    print(f"  a = {a:.4f} +/- {se[0]:.4f}   e^gamma = {EG:.4f}  "
          f"(a - e^g = {a - EG:+.4f}, {abs(a - EG)/se[0]:.1f} sigma)")
    print(f"  b = {b:.4f} +/- {se[1]:.4f}   -a/2 = {-a/2:.4f}  "
          f"(b vs -a/2: {abs(b + a/2)/se[1]:.1f} sigma)")
    print(f"  c = {c:+.5f} +/- {se[2]:.5f}")
    print(f"  weighted R^2 = {r2:.4f}, rms = {math.sqrt(s2):.4f}, "
          f"dof = {dof}\n")

    # closed-form candidate head-to-head
    for name, f in [("e^g*ln(u)", lambda uu, nn: EG * math.log(uu)),
                    ("fit poly", lambda uu, nn: a*(uu-1) + b*(uu-1)**2
                     + c*(nn-6))]:
        rr = y - np.array([f(uu, nn) for uu, nn in zip(u, n)])
        print(f"  {name:>10}: weighted rms = "
              f"{math.sqrt(np.sum(w*rr**2)/len(y)):.4f}")
    print()

    print("brute rows (design premium, identity coord):")
    for m, D, s, nn, tag in BRUTE:
        uu = uid(m, D)
        pred = a*(uu-1) + b*(uu-1)**2 + c*(nn-6)
        print(f"  {tag}: obs {s:.3f} vs line {pred:.3f} -> "
              f"+{s-pred:.3f} ({(s-pred)*m:+.2f} e-units at their m)")

    print("\nanchor check (same coordinate now):")
    for name, m, D, Ex, nn in [
            ("t20 row1", 18.0669, 385713, 4.94, 9),
            ("t20 row14", 20.3767, 99750, 6.89, 9),
            ("t20 row15", 6.6622, 303518, 0.93, 9),
            ("monument", 20.05, 26600, 7.17, 6),
            ("strike", 30.10, 6152, 14.74, 6),
            ("record", 32.385, 2705, 17.46, 6)]:
        uu = uid(m, D)
        Ef = m * (a*(uu-1) + b*(uu-1)**2 + c*(nn-6))
        print(f"  {name:>10}: fitted {Ef:5.2f} vs exact {Ex:5.2f} "
              f"({(Ef-Ex)/Ex*100:+5.1f}%)")

    print("\npaste into pricer_v1.SIGMA_KNOTS (nsw=6):")
    print("SIGMA_KNOTS = [")
    for uu in (1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.45,
               1.55, 1.66):
        x = uu - 1
        print(f"    ({uu:.3f}, {max(0.0, a*x + b*x*x):.4f}),")
    print("]")


if __name__ == "__main__":
    main()
