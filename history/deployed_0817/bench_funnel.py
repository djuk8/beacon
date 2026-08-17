#!/usr/bin/env python3
"""BEACON bench_funnel v1 -- screened funnel vs vanilla, full cost accounting.

Arm V (vanilla): random anchors, full trials. Supply --vanilla-log to use a
banked livefire_log.csv as the control arm (recommended); otherwise priced
from the frozen model.
Arm B (BEACON): screen N anchors at z_s (cheap sieve scoring), select top-n,
compute EXACT per-anchor posteriors (preregistered prediction), then run real
trials on the selected anchors. Screening time is charged to arm B.

Usage (shredder):
  python3 bench_funnel.py --digits 3000 --screen 2000000 --zs 1e6 --top 60 \
      --z 1e9 --target-merit 5 --vanilla-log livefire_log.csv
Self-test (small):
  python3 bench_funnel.py --digits 400 --screen 60000 --zs 1e4 --top 8 \
      --z 1e6 --target-merit 4
"""
import argparse, csv, math, time
import numpy as np, gmpy2

EG = 1.7810724179901979
LN10 = math.log(10)

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def build_base(D, PR):
    cum = np.cumsum(np.log(PR.astype(float)))
    i = int(np.searchsorted(cum, (D - 8) * LN10))
    zd = int(PR[i - 1]) if cum[min(i, len(cum) - 1)] > (D - 8) * LN10 else int(PR[i])
    design = PR[PR <= zd]
    P = gmpy2.mpz(1)
    for p in design: P *= int(p)
    return zd, design, P

def screen(ks, pd, Pmod, offs, W, chunk=20000):
    m1 = len(offs)
    col = np.full(W + 1, -1, np.int32); col[offs] = np.arange(m1)
    scores = np.empty(len(ks), np.int32)
    for c in range(0, len(ks), chunk):
        k = ks[c:c + chunk]; K = len(k); rows = np.arange(K)
        r = (k[:, None] * Pmod[None, :]) % pd[None, :]
        kill = np.zeros((K, 2 * m1), bool)
        for ip in range(len(pd)):
            p = int(pd[ip])
            for base, off0 in (((p - r[:, ip]) % p, 0), (r[:, ip] % p, m1)):
                h = base.copy()
                while True:
                    v = col[np.minimum(h, W)]
                    ok = (h <= W) & (v >= 0)
                    if ok.any(): kill[rows[ok], v[ok] + off0] = True
                    h = h + p
                    if (h > W).all(): break
        scores[c:c + chunk] = 2 * m1 - kill.sum(1)
    return scores

def pattern(k, pd, Pmod, offs, W):
    m1 = len(offs); colmap = {int(o): i for i, o in enumerate(offs)}
    r = (int(k) * Pmod) % pd
    killP = np.zeros(m1, bool); killM = np.zeros(m1, bool)
    for p, rr in zip(pd, r):
        for base, K in (((int(p) - int(rr)) % int(p), killP), (int(rr) % int(p), killM)):
            h = base
            while h <= W:
                if h in colmap: K[colmap[h]] = True
                h += int(p)
    return offs[~killP], offs[~killM]

def posterior(k, P, dl, dr, offs2, zd, ZS, W, L, Gstar):
    lnn = float(gmpy2.log(int(k) * P))
    q = EG * math.log(ZS) / lnn; beta = EG * math.log(zd) / lnn
    def leg(dlist):
        pmf = [(q * (1 - q) ** i, int(d)) for i, d in enumerate(dlist)]
        pW = (1 - q) ** len(dlist)
        for i, o in enumerate(offs2): pmf.append((pW * beta * (1 - beta) ** i, int(o)))
        E = sum(w * d for w, d in pmf)
        def S(x):
            if x <= 0: return 1.0
            n = int(np.searchsorted(dlist, x))
            if x <= W: return (1 - q) ** n
            return (1 - q) ** len(dlist) * (1 - beta) ** int(np.searchsorted(offs2, x))
        return pmf, E, S
    pl, EL, _ = leg(dl); pr, ER, SR = leg(dr)
    return sum(w * SR(Gstar - d) for w, d in pl), EL + ER

def trial(k, P, design, deep, rP, Wside):
    n0 = int(k) * P
    Wt = 2 * Wside + 1
    alive = np.ones(Wt, bool)
    for q in design: alive[Wside % q::q] = False
    r0 = (int(k) * rP) % deep; lo = (r0 - Wside) % deep
    med = deep < Wt
    for p, rl in zip(deep[med], lo[med]): alive[(p - rl) % p::p] = False
    idx = (deep[~med] - lo[~med]) % deep[~med]; hit = idx < Wt
    alive[idx[hit]] = False
    so = np.flatnonzero(alive) - Wside
    order = so[np.argsort(np.abs(so), kind='stable')]
    jl = jr = None; tests = 0
    for j in order:
        if j == 0 or (j < 0 and jl is not None) or (j > 0 and jr is not None): continue
        tests += 1
        c = n0 + int(j)
        if gmpy2.powmod(2, c - 1, c) == 1 and gmpy2.is_prime(c, 25):
            if j < 0: jl = int(j)
            else: jr = int(j)
            if jl is not None and jr is not None: break
    return (jr - jl if jl is not None and jr is not None else 0), tests

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--zs", type=float, required=True)
    ap.add_argument("--top", type=int, required=True)
    ap.add_argument("--z", type=float, required=True)
    ap.add_argument("--target-merit", type=float, required=True)
    ap.add_argument("--vanilla-log")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    D, ZS, Z = a.digits, int(a.zs), int(a.z)
    L = D * LN10; W = int(10 * L); Gstar = int(a.target_merit * L)
    PR = primes_upto(max(Z if Z <= 2_000_000_000 else 0, int(30 * L), ZS))
    if Z > 2_000_000_000: raise SystemExit("z <= 2e9 in this kit")
    PRz = primes_upto(Z) if Z > PR[-1] else PR
    zd, design, P = build_base(D, PR)
    offs = PR[(PR > zd) & (PR <= W)]
    offs2 = PR[(PR > W) & (PR <= int(30 * L))]
    pd = PR[(PR > zd) & (PR <= ZS)]
    Pmod = np.array([int(P % int(p)) for p in pd], np.int64)
    print(f"D={D:,} zd={zd:,} | screen z_s={ZS:.0e} ({len(pd):,} primes) | trial z={Z:.0e} | target merit {a.target_merit}")

    # ---- ARM B: screen ----
    rng = np.random.default_rng(a.seed)
    ks = rng.integers(10 ** 6, 10 ** 7, a.screen)
    t0 = time.time()
    sc = screen(ks, pd, Pmod, offs, W)
    t_screen = time.time() - t0
    best = np.argsort(sc)[:a.top]
    depth = (sc.mean() - sc[best].mean()) / sc.std()
    print(f"screened {a.screen:,} anchors in {t_screen:.0f}s ({1e6*t_screen/a.screen:.0f} us/anchor) | "
          f"score mu={sc.mean():.1f} sigma={sc.std():.2f} | selection depth {depth:.2f} sigma")

    # ---- preregistration: exact posteriors of the selected ----
    tot = 0.0; Em = []
    for k in ks[best]:
        dl, dr = pattern(k, pd, Pmod, offs, W)
        Pk, E = posterior(k, P, dl, dr, offs2, zd, ZS, W, L, Gstar)
        tot += Pk; Em.append(E)
    print(f"PREREGISTERED: sum of exact posteriors = {tot:.2f} successes in {a.top} trials | "
          f"predicted mean gap {np.mean(Em):,.0f}")

    # ---- ARM B: trials ----
    deep = PRz[PRz > zd]
    rP = np.array([int(P % int(p)) for p in deep], np.int64)
    Wside = int(25 * L)
    t0 = time.time(); gaps = []; tests_all = 0
    for k in ks[best]:
        g, t = trial(k, P, design, deep, rP, Wside)
        gaps.append(g); tests_all += t
    t_trial = time.time() - t0
    succ = sum(g >= Gstar for g in gaps)
    print(f"MEASURED: {succ} successes | mean gap {np.mean(gaps):,.0f} | "
          f"{tests_all} tests | trials {t_trial:.0f}s")
    costB = (t_screen + t_trial) / max(succ, 1)
    print(f"ARM B cost/success: ({t_screen:.0f}s screen + {t_trial:.0f}s trials)/{succ} = {costB:,.0f}s")

    # ---- ARM V ----
    if a.vanilla_log:
        rows = [r for r in csv.DictReader(open(a.vanilla_log)) if int(r["D"]) == D]
        vt = sum(float(r["t_trial_s"]) for r in rows)
        vs = sum(1 for r in rows if int(r["gap"]) >= Gstar)
        print(f"ARM V (banked, {len(rows)} trials): {vs} successes | cost/success = {vt/max(vs,1):,.0f}s")
        if succ and vs:
            print(f"\nVERDICT: BEACON funnel = {(vt/vs)/costB:.2f}x vanilla (cost per merit>={a.target_merit} find)")
    else:
        print("ARM V: no log supplied -- run vanilla trials separately or supply --vanilla-log")

if __name__ == "__main__":
    main()
