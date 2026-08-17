#!/usr/bin/env python3
"""t1_anchors_v3.py -- two-coordinate law: fixed-m transects, theory
vs the published top-20 (zero parameters), shelf lip slope.
PREREG: T1_PREREG_v3 (chat 2026-08-17). Same dir as resonance_map.py.
  python3 t1_anchors_v3.py > t1a_v3.txt
"""
import math, sys, time
import numpy as np
import gmpy2
from resonance_map import primes_upto, sieve_window, GAMMA

sys.set_int_max_str_digits(2_000_000)
EG = math.exp(GAMMA)
Q = 10 ** 6
A_P, B_P = 1.8169, -0.5587
JMAX = 8_600_000

ROWS = [  # rk, gap, D, k, zd, d, jl, sigma_exact
 (1, 16045848, 385713, 1217, 888887, "23#", -7636494, 0.274),
 (2, 8193558, 289083, 1, 666667, "17#", -6334558, 0.255),
 (3, 7769676, 289082, 43, 666667, "23#", -5594774, 0.230),
 (4, 7186572, 208095, 29, 479909, "9699690", -3531714, 0.251),
 (5, 6966714, 208096, 1, 479909, "30030", -3166622, 0.254),
 (6, 6647694, 337314, 2437, 777787, "23#", -2374658, 0.168),
 (7, 6582144, 216841, 1, 499973, "30030", -4509212, 0.254),
 (8, 6480930, 208093, 1, 479909, "9699690", -2492758, 0.240),
 (9, 6181674, 208094, 1, 479909, "510510", -3758926, 0.232),
 (10, 5384030, 173457, 829, 400009, "46410", -2470148, 0.246),
 (11, 5198448, 157490, 363257, 363269, "510510", -2177806, 0.251),
 (12, 5103138, 216849, 281, 499979, "46410", -2702372, 0.188),
 (13, 4854690, 208102, 479903, 479909, "2310", -1944886, 0.189),
 (14, 4680156, 99750, 1, 230077, "2229464046810", -3131794, 0.338),
 (15, 4656036, 303518, 1627, 700001, "23#", -2745914, 0.139),
 (16, 4397298, 97234, 1, 224423, "107371994730", -2375864, 0.323),
 (17, 4362420, 151940, 350351, 350377, "2310", -2859322, 0.251),
 (18, 3921168, 179864, 3652026499164494422179566474085691865,
  414949, "30030", -2237306, 0.239),
 (19, 3870360, 135376, 2267, 312583, "46410", -1157722, 0.259),
 (20, 3436432, 151952, 1322983044025855821143464371513327685,
  350293, "30030", -1051678, 0.286),
]

def factor_d(ds):
    if ds.endswith("#"):
        z = int(ds[:-1]); v = 1; ps = []
        p = 2
        while p <= z:
            ps.append(p); v *= p
            p = int(gmpy2.next_prime(p))
        return v, ps
    v = int(ds); ps = []; t = v; p = 2
    while p * p <= t and p < 10 ** 6:
        if t % p == 0:
            ps.append(p)
            while t % p == 0: t //= p
        p = int(gmpy2.next_prime(p))
    if t > 1: ps.append(t)
    return v, ps

def smooth_even(base, lim):
    out = []
    def rec(v, i):
        out.append(v)
        for j in range(i, len(base)):
            if v * base[j] > lim: break
            rec(v * base[j], j)
    rec(1, 0)
    a = np.array(sorted(out), dtype=np.int64)
    return a[a % 2 == 0]

def theory_side(J, zd, pc, sme, odd_ps, pizd):
    w, sl = [], []
    for s0 in sme:
        s0 = int(s0)
        if s0 > J: break
        if J // s0 > zd:
            t = int(pc[J // s0]) - pizd
            if t > 0: w.append(float(t)); sl.append(s0)
        w.append(1.0); sl.append(s0)
    if not w: return 0.0
    w = np.array(w); sl = np.array(sl)
    tot = float(w.sum()); fac = 1.0
    for p0 in odd_ps:
        mn = float(w[sl % p0 != 0].sum())
        fac *= (1.0 - mn / max(tot, 1e-9) / (p0 - 1))
    return fac * tot

def main():
    t0 = time.time()
    prs = primes_upto(Q)
    bs = np.ones(JMAX + 1, bool); bs[:2] = False
    for p in range(2, int(JMAX ** 0.5) + 1):
        if bs[p]: bs[p * p::p] = False
    pc = np.cumsum(bs)
    lgp = np.zeros(JMAX + 1)
    pr_all = np.nonzero(bs)[0]
    lgp[pr_all] = np.log(pr_all)
    thcum = np.cumsum(lgp)          # theta(x)
    print(f"setup [{time.time()-t0:.0f}s]")

    # ---- Part 1: fixed-m transects (measurement + theory) ----
    print("\n== H4: fixed-m transects ==")
    print(f"{'m':>4} {'zd':>5} {'u':>6} {'sig':>7} {'se':>6} "
          f"{'sig*u':>6} {'th':>6} {'poly*u':>7}")
    D0 = gmpy2.mpz(30030); odd0 = [3, 5, 7, 11, 13]
    h4 = []
    for mfix in (30, 100, 300):
        band, pband = [], []
        for zd in (199, 331, 613, 1009, 1777, 3163):
            P = gmpy2.mpz(1); p = gmpy2.mpz(2)
            while p <= zd:
                P *= p; p = gmpy2.next_prime(p)
            Pd = P // D0
            thq = math.exp(sum(math.log1p(-1.0 / int(q)) for q in prs
                               if int(q) > zd))
            k0 = gmpy2.mpz(round(float(D0) *
                                 math.exp(zd - float(gmpy2.log(P)))))
            ks, k = [], k0
            for _ in range(4):
                k = gmpy2.next_prime(k); ks.append(k)
            pdmod = np.array([int(Pd % int(q)) for q in prs],
                             dtype=np.int64)
            sme = smooth_even([2] + odd0, JMAX)
            sig = []
            jf = 0; u = 0.0
            for k in ks:
                ln0 = float(gmpy2.log(k * Pd)); L = math.log(ln0)
                u = 1.0 + math.log(mfix / 2.0) / L
                jf = int(round(0.5 * mfix * ln0))
                km = np.array([int(k % int(q)) for q in prs],
                              dtype=np.int64)
                s = sieve_window((km * pdmod) % prs, prs, -jf, jf)
                sig.append(s * EG * math.log(Q) / ln0 / mfix)
            mu = float(np.mean(sig))
            se = float(np.std(sig, ddof=1)) / 2.0
            T = theory_side(jf, zd, pc, sme, odd0, int(pc[zd]))
            th = 2.0 * T * thq * EG * math.log(Q) / (zd * mfix)
            x = u - 1.0
            band.append(mu * u); pband.append((A_P*x + B_P*x*x) * u)
            h4.append((mfix, mu * u))
            print(f"{mfix:>4} {zd:>5} {u:>6.3f} {mu:>7.4f} {se:>6.4f} "
                  f"{mu*u:>6.3f} {th:>6.3f} {(A_P*x+B_P*x*x)*u:>7.3f}")
        rm = max(band) / min(band); rp = max(pband) / min(pband)
        print(f"  m={mfix}: spread sig*u = {rm:.3f}x   poly*u = {rp:.3f}x")
        if mfix >= 100:
            h4.append(("verdict", rm <= 1.15 and rp >= 1.25))

    # ---- Part 2: theory vs published top-20, zero parameters ----
    print("\n== H5: theory vs published records (zero-parameter) ==")
    print(f"{'rk':>2} {'zd':>6} {'d':>12} {'u':>6} {'sig_ex':>7} "
          f"{'sig_th':>7} {'dev%':>6}")
    hits = 0
    for rk, gap, D, k, zd, ds, jl, sx in ROWS:
        dv, dps = factor_d(ds)
        odd_ps = [p for p in dps if p != 2]
        theta = float(thcum[zd])
        ln0 = float(gmpy2.log(gmpy2.mpz(k))) + theta - math.log(dv)
        m = gap / ln0
        u = 1.0 + math.log(m / 2.0) / math.log(ln0)
        jr = jl + gap
        base = sorted(set([2] + odd_ps))
        sme = smooth_even(base, max(-jl, jr))
        thq = 1.0
        if zd < Q:
            thq = math.exp(sum(math.log1p(-1.0 / int(q)) for q in prs
                               if int(q) > zd))
        pizd = int(pc[zd])
        T = (theory_side(-jl, zd, pc, sme, odd_ps, pizd)
             + theory_side(jr, zd, pc, sme, odd_ps, pizd))
        th = T * thq * EG * math.log(Q) / (ln0 * m)
        dev = (th / sx - 1) * 100
        hits += (abs(dev) <= 8.0)
        print(f"{rk:>2} {zd:>6} {ds[:12]:>12} {u:>6.3f} {sx:>7.3f} "
              f"{th:>7.3f} {dev:>+6.1f}")
    print(f"  within 8%: {hits}/20")

    # ---- Part 3: shelf lip slope, theory only ----
    print("\n== H6: shelf lip slope (theory, L=12.3, d=30030) ==")
    zd_s = int(math.exp(12.3))
    ln0 = math.exp(12.3)
    sme = smooth_even([2] + odd0, JMAX)
    xs, ys = [], []
    for m in (5, 6, 7, 8, 9, 10, 11, 12):
        jf = int(0.5 * m * ln0)
        u = 1.0 + math.log(m / 2.0) / 12.3
        T = theory_side(jf, zd_s, pc, sme, odd0, int(pc[zd_s]))
        th = 2.0 * T * EG * math.log(Q) / (ln0 * m)   # zd>Q: thq=1
        xs.append(u - 1.0); ys.append(th)
        print(f"  m={m:>2}  u={u:.4f}  sig_th={th:.4f}")
    A = np.column_stack([xs, np.square(xs)])
    co, *_ = np.linalg.lstsq(A, np.array(ys), rcond=None)
    a_th = float(co[0])
    print(f"  lip slope a_th = {a_th:.4f}   (e^g = {EG:.4f}, "
          f"poly a = {A_P})")

    v4 = all(v for tag, v in h4 if tag == "verdict")
    print(f"\nH4 coordinate test:   {'PASS' if v4 else 'REFUTED'}")
    print(f"H5 zero-param top20:  {'PASS' if hits >= 16 else 'REFUTED'} "
          f"({hits}/20)")
    print(f"H6 lip slope:         "
          f"{'PASS' if 1.65 <= a_th <= 1.95 else 'REFUTED'} "
          f"({a_th:.3f})")
    print(f"[{time.time()-t0:.0f}s total]")

if __name__ == "__main__":
    main()

