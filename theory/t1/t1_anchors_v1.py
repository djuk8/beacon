#!/usr/bin/env python3
"""t1_anchors_v1.py -- T1 high-u anchors on the gated instrument.
PREREG: T1_PREREG_v1 (chat 2026-08-17). Same dir as resonance_map.py.
Method = audit_top20_v0's bridge: exact sieve_window at Q, E = s*beta.
Anchors sit ON the grammar: k chosen so ln n0 = zd to <0.1%.
  python3 t1_anchors_v1.py > t1a_1e6.txt          # Q=1e6
  python3 t1_anchors_v1.py --Q 100000 > t1a_1e5.txt   # G6 re-read
"""
import argparse, math, sys, time
import numpy as np
import gmpy2
from resonance_map import primes_upto, sieve_window, GAMMA

sys.set_int_max_str_digits(2_000_000)
EG = math.exp(GAMMA)
A_P, B_P = 1.8169, -0.5587       # frozen 26-pt poly (reference)
K_ALT = 2.0 * GAMMA / EG          # 0.6482 = TAY curvature family

ZDS = [79, 127, 199, 331]
UT = [1.55, 1.65, 1.75, 1.85, 1.92]
NK = 5
D = gmpy2.mpz(30030)

def sk(x, k):
    return (EG / k) * (1.0 - math.exp(-k * x))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Q", type=int, default=10 ** 6)
    a = ap.parse_args()
    t0 = time.time()
    prs = primes_upto(a.Q)
    print(f"T1 anchors  Q={a.Q:,}  primes {len(prs):,} "
          f"[{time.time()-t0:.0f}s]")
    print(f"{'zd':>4} {'u':>5} {'m':>8} {'jf':>7} {'surv':>7} "
          f"{'sig':>7} {'se':>6} | {'EXPg':>6} {'ALT':>6} {'POLY':>6} "
          f"{'d_exp%':>6}")
    rows = []
    for zd in ZDS:
        P = gmpy2.mpz(1); p = gmpy2.mpz(2)
        while p <= zd:
            P *= p; p = gmpy2.next_prime(p)
        Pd = P // D
        k0 = gmpy2.mpz(round(float(D) *
                             math.exp(zd - float(gmpy2.log(P)))))
        ks, k = [], k0
        for _ in range(NK):
            k = gmpy2.next_prime(k); ks.append(int(k))
        pdmod = np.array([int(Pd % int(q)) for q in prs], dtype=np.int64)
        for ut in UT:
            t1 = time.time(); sig = []; svs = []
            for k in ks:
                ln0 = float(gmpy2.log(gmpy2.mpz(k) * Pd))
                L = math.log(ln0)
                m = 2.0 * math.exp((ut - 1.0) * L)
                jf = int(round(0.5 * m * ln0))
                n0mod = ((k % prs) * pdmod) % prs
                s = sieve_window(n0mod, prs, -jf, jf)
                E = s * EG * math.log(a.Q) / ln0
                sig.append(E / m); svs.append(int(s))
            sig = np.array(sig)
            mu = float(sig.mean())
            se = float(sig.std(ddof=1)) / math.sqrt(NK)
            x = ut - 1.0
            pe, pa = sk(x, GAMMA), sk(x, K_ALT)
            pp = A_P * x + B_P * x * x
            rows.append((ut, mu, se))
            print(f"{zd:>4} {ut:>5.2f} {m:>8.2f} {jf:>7d} "
                  f"{int(np.mean(svs)):>7d} {mu:>7.4f} {se:>6.4f} | "
                  f"{pe:>6.4f} {pa:>6.4f} {pp:>6.4f} "
                  f"{(mu/pe-1)*100:>+6.1f}  [{time.time()-t1:.0f}s]")

    x = np.array([r[0] - 1.0 for r in rows])
    y = np.array([r[1] for r in rows])
    w = 1.0 / np.array([max(r[2], 1e-4) for r in rows]) ** 2
    kg = np.linspace(0.20, 1.20, 2001)
    sse = np.array([float(np.sum(w * (y - (EG / k) *
                    (1 - np.exp(-k * x))) ** 2)) for k in kg])
    i = int(np.argmin(sse)); khat = kg[i]
    s2 = sse[i] / (len(y) - 1)
    b1 = kg[sse <= sse[i] + s2]; b2 = kg[sse <= sse[i] + 4 * s2]
    sig_g = math.sqrt(s2 / max(np.sum(w * (x * np.exp(-khat * x)) ** 2
                                      * (EG / khat) ** 2), 1e-12))
    print(f"\nkappa (anchors alone): khat={khat:.3f} "
          f"1s[{b1[0]:.3f},{b1[-1]:.3f}] 2s[{b2[0]:.3f},{b2[-1]:.3f}]")
    zg = abs(khat - GAMMA) / max((b1[-1] - b1[0]) / 2, 1e-9)
    za = abs(khat - K_ALT) / max((b1[-1] - b1[0]) / 2, 1e-9)
    print(f"  gamma={GAMMA:.3f} at {zg:.1f}s   "
          f"K_ALT={K_ALT:.4f} at {za:.1f}s")

    hi = [(u, mu, se) for (u, mu, se) in rows if u >= 1.75]
    g5 = all(abs(mu / sk(u - 1, GAMMA) - 1) <= 0.06 for u, mu, se in hi)
    g4 = (b1[0] <= GAMMA <= b1[-1]) and (za >= 1.5)
    print(f"\nG4 kappa-discrimination: {'PASS' if g4 else 'REFUTED'}")
    print(f"G5 high-u within 6% of EXP(gamma): "
          f"{'PASS' if g5 else 'REFUTED'}")
    print(f"G6: compare sig columns across Q runs by hand (<=1%)")
    print(f"[{time.time()-t0:.0f}s total]")

if __name__ == "__main__":
    main()
