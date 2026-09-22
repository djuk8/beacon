#!/usr/bin/env python3
"""pricer_v2.py r2 (2026-08-24) -- THE EXCHANGE with O1 constants + RC5 exact anchoring (shadow rescaled where an exact chain exists): measured Blackwell sub-16K rates + early-exit ratio.
pricer_v1.py -- THE EXCHANGE: one metric for every board, both axes.

Unifies merit_price_v0 (design pricing) + audit_top20_v0 (artifact audit)
under one law and one number:

  u(m,D)   = 1 + ln(m/2)/ln(D*ln10)          [grammar identity]
  E(m,D)   = m * sigma(u)                     [sigma = measured knots]
  L(target)= E - ln A + ln c_w - ln beta + ln s(D)   [log core-seconds]

Division of labor: THIS tool scans with the sigma SHADOW (fast, flagged);
exact certification of any chosen config = merit_price_v0 / resonance_map
(the gated bridge). Never fire on a shadow number alone.

MODES
  --selftest                     shadow vs six exact-audited anchors
  --audit "expr:jl:gap"          exact-sieve audit of any artifact
                                 (k*zd#/d, /17# divisors, L<literal>)
  --target "G@D" | "m@D" | G     price a target (G alone -> scan D)
  --frontier --budget CD         iso-budget record frontier, core-days
FLEET (defaults = today's owned+strike fleet; override freely)
  --gpus 12  --cpu-eff 55  --Q 1e9

FLAG LEDGER (every number inherits these):
  sigma knots MEASURED (20 artifacts + monument + strike + frontier +
  87d crowns); interpolation MODEL; u>1.66 REFUSED (outside data).
  A in [2,8] frontier-MEASURED, transfer MODEL. c_w: 2.9 MEASURED at
  E~17-19; low-E limb 1+E/2 MODEL (mega audits); theaters' folds are
  measuring the middle now. s_cpu anchored at 26.6k/208k/389kd MEASURED
  (26.6k point under contention -> conservative), log-log interp,
  extrapolation flagged. GPU rates MEASURED per class on 5090; D<=9,863
  only; sub-16K classes unmeasured on Blackwell -> 16K rate used as
  floor. Entropy-wall zone (D <~ 200): shadow cannot see the kdig
  penalty -> exact pricer REQUIRED there (flagged).
"""
import argparse, math, sys, time

GAMMA = 0.5772156649015329
LN10 = math.log(10)

# ---- sigma(u): measured knots, efficient (designed) line -------------
SIGMA_KNOTS = [
    (1.000, 0.000),   # structural: resonance floor is free
    (1.102, 0.139), (1.128, 0.178), (1.158, 0.252), (1.192, 0.323),
    (1.211, 0.341),   # size table (audit 2026-08-05, 20 artifacts)
    (1.280, 0.490),   # 6,152d strike, live folds
    (1.335, 0.540),   # frontier audits + our record
    (1.600, 0.835),   # 87-175d merit crowns (concavity visible)
]
U_MAX = 1.66


def sigma(u):
    if u > U_MAX:
        return None                     # REFUSED: outside measured range
    ks = SIGMA_KNOTS
    if u <= ks[0][0]:
        return 0.0
    for (u0, s0), (u1, s1) in zip(ks, ks[1:]):
        if u <= u1:
            return s0 + (s1 - s0) * (u - u0) / (u1 - u0)
    return ks[-1][1]


def u_of(m, D):
    return 1.0 + math.log(m / 2.0) / math.log(D * LN10)


def E_shadow(m, D):
    s = sigma(u_of(m, D))
    return None if s is None else m * s


# ---- substrate: measured anchors --------------------------------------
S_ANCH = [(26600, 9.0), (208096, 642.8), (388655, 2107.7)]  # s/PRP, 1 core


def s_cpu(D):
    a = S_ANCH
    if D <= a[0][0]:
        (d0, s0), (d1, s1) = a[0], a[1]; flag = "EXTRAP<26.6kd"
    elif D >= a[-1][0]:
        (d0, s0), (d1, s1) = a[-2], a[-1]
        flag = "EXTRAP>389kd" if D > a[-1][0] else ""
    else:
        flag = ""
        for (d0, s0), (d1, s1) in zip(a, a[1:]):
            if D <= d1:
                break
    k = math.log(s1 / s0) / math.log(d1 / d0)
    return s0 * (D / d0) ** k, flag


# Dmax, raw t/s per 5090.  2026-08-24 update: Blackwell sub-16K classes MEASURED (G1-D/G-R4 R3);
# 4096/8192 raw = MODEL interpolation pending a 5-min G1-D each, flagged below.
GPU_CLASSES = [(616, 514170.0), (1232, 130000.0), (2465, 33000.0),
               (4931, 2165.0), (7397, 383.4), (9863, 215.8)]
GPU_MODEL_CLASSES = {1232, 2465}                     # raw rate is MODEL, not measured

# Early exit (O1, in production 2026-08-22): tested/candidates ratio, measured anchors vs beta.
# (0.01488, 0.556) crown ledger 56e9 tests; (0.0131, 0.545) 16K fossil; (2.6e-4, 0.0652) rescal record scale.
# Log-log interpolation between anchors [MODEL between, MEASURED at]; ratio -> 1 as beta -> large.
import bisect as _bis
_EE = [(2.6e-4, 0.0652), (0.0131, 0.545), (0.01488, 0.556)]
def ee_ratio(beta):
    if beta <= _EE[0][0]: return _EE[0][1] * (beta / _EE[0][0]) ** 0.55   # MODEL tail
    if beta >= _EE[-1][0]: return min(1.0, _EE[-1][1] * (beta / _EE[-1][0]) ** 0.3)
    xs = [math.log(b) for b, _ in _EE]; ys = [math.log(r) for _, r in _EE]
    i = _bis.bisect_left(xs, math.log(beta)); x0, x1, y0, y1 = xs[i-1], xs[i], ys[i-1], ys[i]
    return math.exp(y0 + (y1 - y0) * (math.log(beta) - x0) / (x1 - x0))


def gpu_rate(D):
    for dmax, r in GPU_CLASSES:
        if D <= dmax:
            return r
    return 0.0


# ---- exact anchors: where the exact chain has priced a venue, the shadow PRP count is RESCALED to it ----
# Unit = TESTS (the invariant).  RC5 crown chain: W_med 1.176e12 windows x 67.2 t/w = 7.90e13 tests median.
EXACT_ANCHORS = [(41.9388, 610, 7.90e13, "RC5 crown chain (tests)")]

def shadow_prp_mid(m, D):
    E = E_shadow(m, D)
    if E is None: return None
    lam = D * LN10; beta = math.exp(GAMMA) * math.log(1e9) / lam
    return math.exp(E) / 4 * (c_walk(E) / beta) * ee_ratio(beta)

def anchor_scale(m, D):
    for am, aD, at, lab in EXACT_ANCHORS:
        if abs(math.log(D / aD)) < 0.35 and abs(m - am) < 4.5:
            ap = shadow_prp_mid(am, aD)
            if ap: return at / ap, lab
    return None, None

def c_walk(E):
    return min(2.9, 1.0 + 0.5 * E)      # 2.9 MEASURED; low-E limb MODEL


# ---- the log-price ----------------------------------------------------
def price(m, D, gpus, cpu_eff, Q):
    E = E_shadow(m, D)
    if E is None:
        return None
    lam = D * LN10
    beta = math.exp(GAMMA) * math.log(Q) / lam
    Tw = c_walk(E) / beta
    prp_lo, prp_hi = math.exp(E) / 8 * Tw, math.exp(E) / 2 * Tw
    ee = ee_ratio(beta)                                  # O1 early exit: fewer tests, same windows
    prp_lo, prp_hi = prp_lo * ee, prp_hi * ee
    a_scale, a_lab = anchor_scale(m, D)
    if a_scale: prp_lo, prp_hi = prp_lo * a_scale, prp_hi * a_scale
    scpu, cflag = s_cpu(D)
    rate = gpus * gpu_rate(D) + cpu_eff / scpu          # tests/s fleet
    cd_lo, cd_hi = prp_lo * scpu / 86400, prp_hi * scpu / 86400
    wall_lo, wall_hi = prp_lo / rate / 86400, prp_hi / rate / 86400
    flags = []
    if D < 200:
        flags.append("ENTROPY-WALL ZONE: exact pricer required")
    if cflag:
        flags.append(cflag)
    if gpu_rate(D) == 0 and D <= 9863:
        flags.append("GPU class unmeasured")
    for dmax, _r in GPU_CLASSES:
        if D <= dmax:
            if dmax in GPU_MODEL_CLASSES: flags.append(f"GPU raw rate MODEL for class Dmax={dmax}")
            break
    flags.append(f"O1 early-exit ratio {ee:.3f} applied (MEASURED anchors, interp MODEL)")
    if a_scale:
        flags = [f for f in flags if not f.startswith("EXTRAP")]
        flags.append(f"ANCHORED x{a_scale:.2f} to {a_lab}; wall assumes fleet at raw class rate (box efficiency ~0.90 not applied)")
    return dict(E=E, u=u_of(m, D), Tw=Tw, prp=(prp_lo, prp_hi),
                core_days=(cd_lo, cd_hi), wall_days=(wall_lo, wall_hi),
                flags=flags)




# ---- incumbent bars (the sport, one table) ----------------------------
BARS = [
    ("all-time merit #1", "m", 41.9388, 87),
    ("all-time merit #2", "m", 39.6202, 175),
    ("all-time merit #10", "m", 37.8241, 97),
    ("size crown (???)", "G", 16045848, 385713),
    ("size crown VERIFIED", "G", 7186572, 208095),
    ("size top-20 bar", "G", 3436432, 151952),
    ("monument #1 (m>=20)", "G", 4680156, 99750),
    ("monument top-10 bar", "G", 1226120, 26600),
    ("merit>30 size crown", "G", 424654, 6148),
    ("proven-endpoint crown", "G", 1113106, 18662),
    (">=2,500d merit (OURS)", "m", 33.638045, 2704),
]


def bar_md(kind, val, D):
    lam = D * LN10
    return (val, val / lam) if kind == "G" else (val * lam, val)


# ---- modes ------------------------------------------------------------
def do_selftest():
    exact = [("top20 row1", 18.0669, 385713, 4.94),
             ("top20 row14", 20.3767, 99750, 6.89),
             ("top20 row15", 6.6622, 303518, 0.93),
             ("monument", 20.05, 26600, 7.17),
             ("strike", 30.10, 6152, 14.74),
             ("frontier record", 32.385, 2705, 17.46)]
    ok = True
    for name, m, D, Ex in exact:
        Es = E_shadow(m, D)
        d = (Es - Ex) / Ex * 100
        tag = "ok" if abs(d) <= 15 else "FAIL"
        ok &= abs(d) <= 15
        print(f"  {name:>16}: shadow {Es:5.2f} vs exact {Ex:5.2f} "
              f"({d:+5.1f}%) {tag}")
    print("SELFTEST", "PASS (shadow within 15%; certify with bridge)"
          if ok else "FAIL - do not use shadow numbers")
    return ok


def do_target(spec, gpus, cpu_eff, Q):
    if "@" in spec:
        v, D = spec.split("@"); D = int(D)
        m = float(v[1:]) if v.startswith("m") else None
        if m is None:
            G = float(v); m = G / (D * LN10)
        rows = [(D, m)]
    else:
        G = float(spec)
        if G < 100:
            sys.exit(f"target {G} looks like a MERIT, not a gap. Use: --target mM@D (e.g. m41.94@610), "
                     f"G@D (e.g. 58857@610), or a bare GAP for a D-scan (e.g. 58857).")
        rows = []
        for D in [int(1000 * 1.35 ** i) for i in range(1, 24)]:
            m = G / (D * LN10)
            if 4 <= m <= 45:
                rows.append((D, m))
    print(f"{'D':>7} {'m':>7} {'u':>5} {'E':>6} {'PRPs(A2-8)':>19} "
          f"{'core-days':>15} {'fleet wall-d':>13}  flags")
    best = None
    for D, m in rows:
        p = price(m, D, gpus, cpu_eff, Q)
        if p is None:
            print(f"{D:>7} {m:>7.2f}   REFUSED (u > {U_MAX})"); continue
        print(f"{D:>7} {m:>7.2f} {p['u']:>5.3f} {p['E']:>6.2f} "
              f"{p['prp'][0]:>8.2e}-{p['prp'][1]:>8.2e} "
              f"{p['core_days'][0]:>6.1f}-{p['core_days'][1]:>7.1f} "
              f"{p['wall_days'][0]:>5.2f}-{p['wall_days'][1]:>6.2f}  "
              f"{';'.join(p['flags'])}")
        if best is None or p['core_days'][0] < best[1]['core_days'][0]:
            best = ((D, m), p)
    if best and len(rows) > 1:
        (D, m), p = best
        print(f"OPTIMUM: D={D} m={m:.2f} -> {p['core_days'][0]:.0f}-"
              f"{p['core_days'][1]:.0f} core-days  "
              f"[shadow; certify at this D with merit_price_v0]")


def do_frontier(budget_cd, gpus, cpu_eff, Q):
    print(f"ISO-BUDGET FRONTIER at {budget_cd} core-days "
          f"(fleet: {gpus} gpus + {cpu_eff} eff cores)")
    print(f"{'D':>7} {'m_max':>6} {'G_max':>10} {'u':>5} {'E':>6}  "
          f"beats")
    for D in [87, 150, 300, 610, 1230, 2704, 6152, 9800, 18662, 26600,
              50000, 99750, 151952, 208095, 303518, 385713, 600000]:
        best = None
        m = 4.0
        while m <= 45:
            p = price(m, D, gpus, cpu_eff, Q)
            if p is None:
                break
            if p['core_days'][1] <= budget_cd:      # conservative end
                best = (m, p)
            m += 0.05
        if best is None:
            print(f"{D:>7}   -- nothing inside budget --"); continue
        m, p = best
        G = m * D * LN10
        beats = [n for (n, k, v, Db) in BARS
                 for (Gb, mb) in [bar_md(k, v, Db)]
                 if (k == "G" and G > Gb and abs(D - Db) / Db < 0.6)
                 or (k == "m" and m > mb)]
        w = "ENTROPY-WALL ZONE" if D < 200 else ""
        print(f"{D:>7} {m:>6.2f} {G:>10.0f} {p['u']:>5.3f} "
              f"{p['E']:>6.2f}  {', '.join(beats) or '-'} {w}")
    print("[shadow frontier; every chosen point gets bridge "
          "certification before any meter]")


def do_audit(spec, Q):
    import numpy as np
    import gmpy2
    from resonance_map import primes_upto, sieve_window, audit_gate
    try:
        sys.set_int_max_str_digits(2_000_000)
    except Exception:
        pass
    prs = primes_upto(Q)
    if not audit_gate(prs, Q):
        sys.exit(1)
    head, jl, gap = spec.rsplit(":", 2)
    jl, gap = int(jl), int(gap)
    if head.startswith("L"):
        n0 = gmpy2.mpz(head[1:])
    else:
        kp, rest = head.replace(" ", "").split("*")
        zdp, dp = (rest.split("/") + ["1"])[:2]

        def prim(z):
            P, p = gmpy2.mpz(1), gmpy2.mpz(2)
            while p <= z:
                P *= p; p = gmpy2.next_prime(p)
            return P
        d = prim(int(dp[:-1])) if dp.endswith("#") else gmpy2.mpz(dp)
        n0 = gmpy2.mpz(kp) * prim(int(zdp.rstrip("#"))) // d
    lam = float(gmpy2.log(n0))
    n0m = np.array([int(n0 % int(p)) for p in prs], dtype=np.int64)
    s = sieve_window(n0m, prs, jl, jl + gap)
    E = s * math.exp(GAMMA) * math.log(Q) / lam
    m = gap / lam
    D = len(gmpy2.digits(n0, 10))
    u = max(math.log(-jl), math.log(jl + gap)) / math.log(1.01 * lam)
    Es = E_shadow(m, D)
    print(f"AUDIT: D={D} gap={gap} m={m:.4f} u={u:.3f} | "
          f"E_exact={E:.2f} sigma={E/m:.3f} | shadow {Es:.2f} "
          f"({(E-Es)/E*100 if Es else 0:+.0f}% dev) | "
          f"windows e^E={math.exp(E):.2e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--audit")
    ap.add_argument("--target")
    ap.add_argument("--frontier", action="store_true")
    ap.add_argument("--budget", type=float, default=500)
    ap.add_argument("--gpus", type=int, default=12)
    ap.add_argument("--cpu-eff", type=float, default=55)
    ap.add_argument("--Q", type=float, default=1e9)
    a = ap.parse_args()
    t0 = time.time()
    if a.selftest and not do_selftest():
        sys.exit(1)
    if a.audit:
        do_audit(a.audit, int(min(a.Q, 1e6)))
    if a.target:
        do_target(a.target, a.gpus, a.cpu_eff, a.Q)
    if a.frontier:
        do_frontier(a.budget, a.gpus, a.cpu_eff, a.Q)
    print(f"[{time.time()-t0:.1f}s]")


if __name__ == "__main__":
    main()
