#!/usr/bin/env python3
"""BEACON bench_funnel v3 -- C-screen edition (screen kernel inline).

v3: the screen runs via the compiled screen_kernel (incremental residues,
~0.14 ms/anchor on shredder, 40x the numpy path), verified bit-faithful.
Requires: screen_kernel (compiled) + make_blob logic (inlined here).
Falls back to numpy screen with --no-c.

v2 changes (incident 2026-07 resolved):
  - SCORE IS TARGET-MATCHED: survivors weighted by walk probability
    w_i = exp(-q*tau*i) (posterior surrogate), so selection concentrates
    where legs actually travel. v1's raw count selected far-region noise.
  - ARM V runs LIVE random trials (--vanilla-trials); no synthetic baseline.
  - progress prints; sampled preregistration (--prereg-sample, unbiased
    random subsample of the selected, scaled).

Shredder (deep-target punch bench):
  python3 bench_funnel2.py --digits 400 --screen 400000 --zs 1e6 --top 12000 \
      --z 1e6 --target-merit 8 --vanilla-trials 40000
Smoke:
  python3 bench_funnel2.py --digits 400 --screen 20000 --zs 1e5 --top 300 \
      --z 1e6 --target-merit 8 --vanilla-trials 400
"""
import argparse, math, time, os, subprocess, tempfile
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

def screen_weighted(ks, pd, Pmod, offs, W, wv, chunk=20000):
    """Returns killed-weight score (HIGHER = better anchor) per k."""
    m1 = len(offs)
    col = np.full(W + 1, -1, np.int32); col[offs] = np.arange(m1)
    sc = np.empty(len(ks), np.float64)
    t0 = time.time()
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
        sc[c:c + chunk] = kill @ wv
        print(f"  screened {c + K:,}/{len(ks):,}  ({time.time()-t0:.0f}s)", flush=True)
    return sc

def write_blob(path, pd, Pmod, W, wv_full1):
    """wv_full1: length-(W+1) dense weight array (0 off offsets)."""
    with open(path, "wb") as f:
        np.array([len(pd)], np.int64).tofile(f)
        pd.astype(np.int64).tofile(f)
        Pmod.astype(np.int64).tofile(f)
        np.array([W], np.int64).tofile(f)
        wv_full1.astype(np.float64).tofile(f)

def screen_c(ks, pd, Pmod, offs, W, wv_off, exe="./screen_kernel"):
    """Run the compiled kernel over CONSECUTIVE anchors ks (must be arange)."""
    wv_dense = np.zeros(W + 1, np.float64); wv_dense[offs] = wv_off
    d = tempfile.mkdtemp(prefix="bf3_")
    blob = os.path.join(d, "s.blob"); out = os.path.join(d, "s.bin")
    write_blob(blob, pd, Pmod, W, wv_dense)
    k0 = int(ks[0]); K = len(ks)
    t0 = time.time()
    subprocess.run([exe, blob, str(k0), str(K), out], check=True)
    sc = np.fromfile(out, np.float64)
    print(f"  C screen: {K:,} anchors in {time.time()-t0:.0f}s "
          f"({1e6*(time.time()-t0)/K:.0f} us/anchor)", flush=True)
    os.remove(blob); os.remove(out); os.rmdir(d)
    return sc

def pattern(k, pd, Pmod, offs, W, colmap):
    m1 = len(offs)
    r = (int(k) * Pmod) % pd
    killP = np.zeros(m1, bool); killM = np.zeros(m1, bool)
    for p, rr in zip(pd, r):
        for base, K in (((int(p) - int(rr)) % int(p), killP), (int(rr) % int(p), killM)):
            h = int(base)
            while h <= W:
                if h in colmap: K[colmap[h]] = True
                h += int(p)
    return offs[~killP], offs[~killM]

def posterior(k, P, dl, dr, offs2, ZS, W, Gstar):
    lnn = float(gmpy2.log(int(k) * P))
    q = EG * math.log(ZS) / lnn
    zd_beta = None
    def leg(dlist):
        pmf = [(q * (1 - q) ** i, int(d)) for i, d in enumerate(dlist)]
        pW = (1 - q) ** len(dlist)
        for i, o in enumerate(offs2): pmf.append((pW * 0.5 * q * (1 - 0.5 * q) ** i, int(o)))
        E = sum(w * d for w, d in pmf)
        def S(x):
            if x <= 0: return 1.0
            n = int(np.searchsorted(dlist, x))
            if x <= W: return (1 - q) ** n
            return (1 - q) ** len(dlist) * (1 - 0.5 * q) ** int(np.searchsorted(offs2, x))
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

def run_trials(tag, klist, P, design, deep, rP, Wside, Gstar, every=200):
    t0 = time.time(); gaps = []
    for i, k in enumerate(klist):
        g, _ = trial(k, P, design, deep, rP, Wside)
        gaps.append(g)
        if (i + 1) % every == 0:
            s = sum(g >= Gstar for g in gaps)
            print(f"  {tag}: {i+1:,}/{len(klist):,} trials, {s} successes ({time.time()-t0:.0f}s)", flush=True)
    return gaps, time.time() - t0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--zs", type=float, required=True)
    ap.add_argument("--top", type=int, required=True)
    ap.add_argument("--z", type=float, required=True)
    ap.add_argument("--target-merit", type=float, required=True)
    ap.add_argument("--vanilla-trials", type=int, default=0)
    ap.add_argument("--prereg-sample", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--no-c", action="store_true", help="use numpy screen instead of the C kernel")
    a = ap.parse_args()
    D, ZS, Z = a.digits, int(a.zs), int(a.z)
    L = D * LN10; W = int(10 * L); Gstar = int(a.target_merit * L)
    PR = primes_upto(max(Z, int(30 * L), ZS))
    zd, design, P = build_base(D, PR)
    offs = PR[(PR > zd) & (PR <= W)]
    offs2 = PR[(PR > W) & (PR <= int(30 * L))]
    pd = PR[(PR > zd) & (PR <= ZS)]
    Pmod = np.array([int(P % int(p)) for p in pd], np.int64)
    tau = float(np.exp(np.sum(np.log1p(-1.0 / pd))))
    q = EG * math.log(ZS) / L
    wv1 = np.exp(-q * tau * (np.arange(len(offs)) + 1.0))   # walk-probability weights
    wv = np.concatenate([wv1, wv1])
    print(f"D={D:,} zd={zd:,} | screen z_s={ZS:.0e} ({len(pd):,} primes) | trial z={Z:.0e} | "
          f"target merit {a.target_merit} (G*={Gstar:,}) | MATCHED score", flush=True)

    rng = np.random.default_rng(a.seed)
    if a.no_c:
        ks = rng.integers(10 ** 6, 10 ** 7, a.screen)
        sc = screen_weighted(ks, pd, Pmod, offs, W, wv)
    else:
        k0 = int(rng.integers(10 ** 6, 10 ** 7 - a.screen))   # random consecutive block
        ks = np.arange(k0, k0 + a.screen, dtype=np.int64)
        sc = screen_c(ks, pd, Pmod, offs, W, wv1)
    best = np.argsort(-sc)[:a.top]
    print(f"score: mu={sc.mean():.3f} sigma={sc.std():.3f} | selection depth "
          f"{(sc[best].mean()-sc.mean())/sc.std():.2f} sigma (weighted kills)", flush=True)

    colmap = {int(o): i for i, o in enumerate(offs)}
    samp = rng.choice(a.top, size=min(a.prereg_sample, a.top), replace=False)
    tot = 0.0
    for i in samp:
        k = ks[best[i]]
        dl, dr = pattern(k, pd, Pmod, offs, W, colmap)
        Pk, _ = posterior(k, P, dl, dr, offs2, ZS, W, Gstar)
        tot += Pk
    prereg = tot / len(samp) * a.top
    print(f"PREREGISTERED (from {len(samp)}-anchor unbiased sample): "
          f"~{prereg:.1f} successes expected in {a.top:,} selected trials", flush=True)

    deep = PR[(PR > zd) & (PR <= Z)]
    rP = np.array([int(P % int(p)) for p in deep], np.int64)
    Wside = int(25 * L)
    gaps_b, t_b = run_trials("ARM B", ks[best], P, design, deep, rP, Wside, Gstar)
    sb = sum(g >= Gstar for g in gaps_b)
    t_screen = 0.0  # screen time reported live above; recompute for ledger:
    print(f"ARM B: {sb} successes / {a.top:,} trials | mean gap {np.mean(gaps_b):,.0f}", flush=True)

    if a.vanilla_trials:
        kv = rng.integers(10 ** 6, 10 ** 7, a.vanilla_trials)
        gaps_v, t_v = run_trials("ARM V", kv, P, design, deep, rP, Wside, Gstar, every=1000)
        sv = sum(g >= Gstar for g in gaps_v)
        print(f"ARM V: {sv} successes / {a.vanilla_trials:,} trials | mean gap {np.mean(gaps_v):,.0f}", flush=True)
        print(f"\nRATES: BEACON {sb/a.top:.5f} vs vanilla {sv/max(a.vanilla_trials,1):.5f} "
              f"-> lift {sb/a.top/max(sv/a.vanilla_trials,1e-12):.2f}x", flush=True)
        print("(cost verdict: divide each arm's successes by its wall time incl. the screen line above)")

if __name__ == "__main__":
    main()
