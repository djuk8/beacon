#!/usr/bin/env python3
"""t1_anchors_v2b.py -- saturation + 1/L extrapolation + PARITY-EXACT
s*q theory bridge. Supersedes v2 (overflow crash pre-data).
PREREG: T1_PREREG_v2 -- H1/H2 unchanged, H3 vs parity-exact bridge.
Same dir as resonance_map.py.
  python3 t1_anchors_v2b.py > t1a_v2b.txt
"""
import math, sys, time
import numpy as np
import gmpy2
from resonance_map import primes_upto, sieve_window, GAMMA

sys.set_int_max_str_digits(2_000_000)
EG = math.exp(GAMMA)
Q = 10 ** 6
A_P, B_P = 1.8169, -0.5587
ZDS = [79, 127, 199, 331, 613, 1009, 1777, 3163]
UT = [1.35, 1.45, 1.55, 1.65, 1.75, 1.85, 1.92, 1.97]
D = gmpy2.mpz(30030)
DPO = [3, 5, 7, 11, 13]        # odd d-primes; p=2 handled exactly

def cubic(x): return EG*x + (3 - 2*EG)*x*x + (EG - 2)*x**3
def expg(x):  return (EG/GAMMA)*(1.0 - math.exp(-GAMMA*x))
def poly(x):  return A_P*x + B_P*x*x

def smooth_upto(lim):
    out, base = [], [2] + DPO
    def rec(v, i):
        out.append(v)
        for j in range(i, len(base)):
            if v * base[j] > lim: break
            rec(v * base[j], j)
    rec(1, 0)
    return np.array(sorted(out), dtype=np.int64)

def main():
    t0 = time.time()
    prs = primes_upto(Q)
    jmax = int(3163 ** 1.97) + 100
    bs = np.ones(jmax + 1, bool); bs[:2] = False
    for p in range(2, int(jmax ** 0.5) + 1):
        if bs[p]: bs[p*p::p] = False
    pc = np.cumsum(bs)
    sme = smooth_upto(jmax)
    sme = sme[sme % 2 == 0]              # even smooth only (n0 odd)
    print(f"setup [{time.time()-t0:.0f}s]  Q={Q:,}  jmax={jmax:,}  "
          f"n_even_smooth={len(sme)}")
    print(f"{'zd':>5} {'u':>5} {'m':>9} {'surv':>7} {'sig':>7} {'se':>6}"
          f" | {'CUBIC':>6} {'EXP':>6} {'POLY':>6} | {'S_hat/S':>7}")
    data, h3r = {}, []
    for zd in ZDS:
        P = gmpy2.mpz(1); p = gmpy2.mpz(2)
        while p <= zd:
            P *= p; p = gmpy2.next_prime(p)
        Pd = P // D
        thq = math.exp(sum(math.log1p(-1.0/int(q)) for q in prs
                           if int(q) > zd))
        k0 = gmpy2.mpz(round(float(D) *
                             math.exp(zd - float(gmpy2.log(P)))))
        NK = 6 if zd < 1000 else 4
        ks, k = [], k0
        for _ in range(NK):
            k = gmpy2.next_prime(k); ks.append(k)
        t1 = time.time()
        pdmod = np.array([int(Pd % int(q)) for q in prs], dtype=np.int64)
        kmods = [np.array([int(k % int(q)) for q in prs], dtype=np.int64)
                 for k in ks]
        pizd = int(pc[zd])
        ln00 = float(gmpy2.log(ks[0] * Pd))
        print(f"  zd={zd}: k~{len(gmpy2.digits(ks[0],10))} digits, "
              f"ln(n0)/zd={ln00/zd:.4f}, mods [{time.time()-t1:.0f}s]")
        for ut in UT:
            t1 = time.time(); sig = []; svs = []
            jf = 0
            for km, k in zip(kmods, ks):
                ln0 = float(gmpy2.log(k * Pd))
                L = math.log(ln0)
                m = 2.0 * math.exp((ut - 1.0) * L)
                jf = int(round(0.5 * m * ln0))
                n0mod = (km * pdmod) % prs
                s = sieve_window(n0mod, prs, -jf, jf)
                sig.append(s * EG * math.log(Q) / ln0 / m)
                svs.append(int(s))
            mu = float(np.mean(sig))
            se = float(np.std(sig, ddof=1)) / math.sqrt(len(sig))
            # parity-exact bridge: even j = s*q (q prime>zd) or pure smooth
            w_s, s_l = [], []
            smax = jf // zd + 1
            for s0 in sme:
                s0 = int(s0)
                if s0 < smax:
                    t = int(pc[jf // s0]) - pizd
                    if t > 0:
                        w_s.append(float(t)); s_l.append(s0)
                if s0 <= jf:
                    w_s.append(1.0); s_l.append(s0)
            w = np.array(w_s); sl = np.array(s_l)
            tot = float(w.sum())
            fac = 1.0
            for p0 in DPO:
                m_np = float(w[sl % p0 != 0].sum())
                fac *= (1.0 - m_np / max(tot, 1e-9) / (p0 - 1))
            Shat = thq * fac * 2.0 * tot
            ratio = Shat / max(np.mean(svs), 1e-9)
            x = ut - 1.0
            data.setdefault(ut, []).append((zd, mu, se))
            h3r.append((zd, ratio))
            print(f"{zd:>5} {ut:>5.2f} {m:>9.2f} {int(np.mean(svs)):>7d}"
                  f" {mu:>7.4f} {se:>6.4f} | {cubic(x):>6.4f} "
                  f"{expg(x):>6.4f} {poly(x):>6.4f} | {ratio:>7.3f}  "
                  f"[{time.time()-t1:.0f}s]")

    print("\n== 1/L extrapolation per u:  sig = sig_inf + c/L ==")
    print(f"{'u':>5} {'sig_inf':>8} {'se':>6} {'c':>7} | {'CUBIC':>6} "
          f"{'EXP':>6} {'POLY':>6}")
    si, sw = [], []
    for ut in UT:
        rows = data[ut]
        Ls = np.array([math.log(zd) for zd, _, _ in rows])  # ln ln n0
        yv = np.array([r[1] for r in rows])
        wv = 1.0 / np.array([max(r[2], 1e-4) for r in rows]) ** 2
        X = np.column_stack([np.ones_like(Ls), 1.0 / Ls])
        cov = np.linalg.inv(X.T @ (X * wv[:, None]))
        beta = cov @ (X * wv[:, None]).T @ yv
        s_inf, c1 = float(beta[0]), float(beta[1])
        se_inf = math.sqrt(max(cov[0, 0], 0.0))
        x = ut - 1.0
        si.append((ut, s_inf, se_inf))
        sw.append(1.0 / max(se_inf, 1e-4) ** 2)
        print(f"{ut:>5.2f} {s_inf:>8.4f} {se_inf:>6.4f} {c1:>7.3f} | "
              f"{cubic(x):>6.4f} {expg(x):>6.4f} {poly(x):>6.4f}")

    def wr(f):
        return math.sqrt(sum(wt * (s - f(u - 1)) ** 2
                             for (u, s, _), wt in zip(si, sw)) / len(si))
    rc, re_, rp = wr(cubic), wr(expg), wr(poly)
    print(f"\nwrms on sig_inf grid: CUBIC {rc:.4f}  EXP {re_:.4f}  "
          f"POLY {rp:.4f}")
    tail = {u: s for u, s, _ in si}
    h1 = (0.94 <= tail[1.92] <= 1.05 and 0.94 <= tail[1.97] <= 1.05
          and tail[1.97] >= tail[1.92] - 0.02)
    h2 = rc < re_ and rc < rp
    h3 = all(abs(r - 1) <= 0.05 for zd, r in h3r if zd >= 331)
    print(f"\nH1 saturation-at-1:      {'PASS' if h1 else 'REFUTED'}")
    print(f"H2 cubic wins:           {'PASS' if h2 else 'REFUTED'}")
    print(f"H3 parity-exact bridge:  {'PASS' if h3 else 'REFUTED'} "
          f"(zd>=331, 5%)")
    print(f"[{time.time()-t0:.0f}s total]")

if __name__ == "__main__":
    main()
