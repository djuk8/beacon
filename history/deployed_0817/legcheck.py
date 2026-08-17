#!/usr/bin/env python3
"""legcheck.py -- one tool, three open items from PAPER1_REVISION_BRIEF.

Answers, per arm, from any livefire log (m1a / u / g schema):

  (A) LEG INDEPENDENCE  [brief 3.1 / handoff 3, the last open item]
      corr(left leg, right leg) in merit units, Pearson + Spearman, Fisher z.
      The two-leg law CONVOLVES two independent legs. If they are not
      independent the mean is still right but every tail probability -- i.e.
      every record rate and the whole design table -- is wrong. Sign matters:
        r < 0  prime repulsion in the rough set -> tails run LOW  (the 5-10%
               level deficit seen at D=1,500 and D=9,800)
        r > 0  local density clustering        -> tails run HIGH
        r = 0  the paper as written is correct and the deficit is elsewhere

  (B) LEVEL   observed mean leg vs the Buchstab prediction (0 free params),
      with the Mertens null alongside.

  (C) LENGTH BIAS  [brief 6.3, gates the -11% paragraph]
      tests/trial vs the parameter-free 2*ln(n0)/(e^gamma*ln z).
      Completion-truncated samples over-represent short legs because
      corr(tests, gap) ~ 0.997. Calibrated on the clean D=3,000 arm: a
      COMPLETE sample sits at 1.02, not 1.00.

No scipy. DictReader throughout (log schemas move; positional awk breaks).

  python3 legcheck.py LOG [LOG ...] [--min-n 100]
  python3 legcheck.py --selftest        # reproduces the D=3,000 numbers
"""
import argparse, csv, math, sys, collections
import numpy as np

EG = math.exp(0.5772156649015329)          # e^gamma = 1.7810724179901979

# ---------------------------------------------------------------- Buchstab
def _omega_grid(h=1e-4, umax=12.0):
    n = int(round((umax - 1.0) / h))
    us = 1.0 + h * np.arange(n + 1)
    w = np.zeros(n + 1)
    w[us <= 2.0] = 1.0 / us[us <= 2.0]
    i2 = int(round(1.0 / h))
    for i in range(i2, n + 1):
        if us[i] <= 2.0:
            continue
        w[i] = (us[i - 1] * w[i - 1] + 0.5 * h * (w[i - 1 - i2] + w[i - i2])) / us[i]
    return us, w

_US, _W = _omega_grid()
omega = lambda u: np.where(np.asarray(u, float) < 1.0, 0.0, np.interp(u, _US, _W))
lam = lambda u: EG * omega(u)              # fence primes per unit merit


def mean_leg(zd, L, rate, xmax=14.0, N=140001):
    """E[excess leg] in merit units under hazard rate(u), u=ln(zd+e)/ln(zd)."""
    x = np.linspace(0.0, xmax, N)
    u = np.log(np.maximum(zd + x * L, zd + 1.0)) / math.log(zd)
    h = rate(u)
    H = np.concatenate([[0.0], np.cumsum(0.5 * (h[1:] + h[:-1]) * np.diff(x))])
    return float(np.trapezoid(np.exp(-H), x))


def fisher(r, n):
    r = min(max(r, -0.999999), 0.999999)
    return 0.5 * math.log((1 + r) / (1 - r)) * math.sqrt(max(n - 3, 1))


def rank(a):
    return np.argsort(np.argsort(a)).astype(float)


# ------------------------------------------------------------------- input
def load(paths):
    arms = collections.defaultdict(list)
    for p in paths:
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh):       # schema-tolerant by design
                try:
                    D = int(float(row["D"]))
                    zd = int(float(row["zdesign"]))
                    z = float(row["z"])
                    g = float(row["gap"])
                    jl = abs(float(row["jleft"]))
                    jr = float(row["jright"])
                except (KeyError, ValueError, TypeError):
                    continue
                if g <= 0:
                    continue
                m = float(row.get("merit") or 0.0)
                Ln0 = g / m if m > 0 else D * math.log(10)
                t = float(row.get("tests") or 0.0)
                arms[(D, zd, z)].append((g, jl, jr, Ln0, t))
    return arms


def report(key, recs):
    D, zd, z = key
    g, jl, jr, Ln0, tests = (np.array(c, float) for c in zip(*recs))
    n = len(g)
    a, b = (jl - zd) / Ln0, (jr - zd) / Ln0        # excess legs, merit units
    L = float(Ln0.mean())

    # S3: fences inside the desert floor are the unit-offset channel. They are
    # REPORTED and EXCLUDED from leg statistics -- never silently dropped.
    uo = int((jl <= zd).sum() + (jr <= zd).sum())
    both = (jl > zd) & (jr > zd)
    legs = np.concatenate([a[jl > zd], b[jr > zd]])

    mB, mM = mean_leg(zd, L, lam), mean_leg(zd, L, lambda u: np.ones_like(u))
    obs = float(legs.mean())
    se_leg = float(legs.std(ddof=1)) / math.sqrt(len(legs))

    aa, bb = a[both], b[both]
    r, rs = np.corrcoef(aa, bb)[0, 1], np.corrcoef(rank(aa), rank(bb))[0, 1]
    vr = float(np.var(aa + bb, ddof=1) / (np.var(aa, ddof=1) + np.var(bb, ddof=1)))
    ncor = int(both.sum())

    print(f"\n=== D={D:,}  zd={zd:,}  z={z:.0e}   n={n:,} trials / {2*n:,} fences")
    print(f"    ln(n0) = {L:,.1f}   mean gap {g.mean():,.0f} +/- {g.std(ddof=1)/math.sqrt(n):,.0f}"
          f"   (all trials)")
    print(f"  (S3) UNIT-OFFSET CHANNEL  {uo} fences at |j| <= zd  ({100.0*uo/(2*n):.2f}% of fences)"
          f"  -- excluded below, per prereg S3")

    print("  (B) LEVEL      obs leg {:.4f} +/- {:.4f} merit   [{:,} leg fences]"
          .format(obs, se_leg, len(legs)))
    print("      Buchstab   pred {:.4f}   ratio {:.4f}  ({:+.2f} sigma)"
          .format(mB, obs / mB, (obs - mB) / se_leg))
    print("      Mertens    pred {:.4f}   ratio {:.4f}  ({:+.2f} sigma)"
          .format(mM, obs / mM, (obs - mM) / se_leg))

    print("  (A) LEG CORR   Pearson {:+.4f}  z {:+.2f}   Spearman {:+.4f}  z {:+.2f}   [n={:,}]"
          .format(r, fisher(r, ncor), rs, fisher(rs, ncor), ncor))
    print("      Var(a+b)/[Var a + Var b] = {:.4f}   (1.000 = independent)".format(vr))
    verdict = ("INDEPENDENT (consistent with the paper as written)" if abs(fisher(r, ncor)) < 2
               else ("ANTI-correlated: tails run LOW, design table needs the pair term"
                     if r < 0 else "CORRELATED: tails run HIGH"))
    print(f"      -> {verdict}")

    if tests.max() > 0 and z > 1:
        pf = 2 * L / (EG * math.log(z))
        obs_t = float(tests.mean()); se_t = float(tests.std(ddof=1)) / math.sqrt(n)
        cg = float(np.corrcoef(tests, g)[0, 1])
        print("  (C) LENGTH BIAS  tests/trial {:,.1f} +/- {:,.1f}  vs parameter-free {:,.1f}"
              "   ratio {:.4f}".format(obs_t, se_t, pf, obs_t / pf))
        print("      corr(tests, gap) = {:+.3f}   [clean reference: ratio ~1.02 at D=3,000]"
              .format(cg))
        if obs_t / pf < 0.97:
            print("      -> SAMPLE IS LENGTH-BIASED. Hazard estimates from it are inflated.")


SELFTEST = {"mean_gap": 22306, "leg_ratio_B": 1.011, "pearson_z": 0.41, "tests_ratio": 1.021}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="*")
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    logs = args.logs or (["/mnt/project/livefire_log.csv"] if args.selftest else [])
    if not logs:
        ap.error("give at least one log")
    arms = load(logs)
    if not arms:
        print("no usable rows", file=sys.stderr); sys.exit(2)
    for key in sorted(arms):
        if len(arms[key]) >= args.min_n:
            report(key, arms[key])
    if args.selftest:
        print("\nSELFTEST reference (D=3,000 zd=6,977 z=1e9, n=500):")
        for k, v in SELFTEST.items():
            print(f"    {k:<12} {v}")
        print("    pooled leg hazard should be 1.656 +/- 0.053 "
              "(brief 5.2 quotes 1.654 +/- 0.052)")


if __name__ == "__main__":
    main()
