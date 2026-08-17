#!/usr/bin/env python3
"""t1_anchors_v4.py -- k-hygiene structural bridge + emergent shelf
slope. PREREG: T1_PREREG_v4 (chat 2026-08-17). Self-contained.
  python3 t1_anchors_v4.py > t1a_v4.txt
"""
import math, sys, time
import numpy as np
import gmpy2

sys.set_int_max_str_digits(2_000_000)
GAMMA = 0.5772156649015329
EG = math.exp(GAMMA)
Q = 10 ** 6
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
        z = int(ds[:-1]); v = 1; ps = []; p = 2
        while p <= z:
            ps.append(p); v *= p; p = int(gmpy2.next_prime(p))
        return v, ps
    v = int(ds); ps = []; t = v; p = 2
    while p * p <= t:
        if t % p == 0:
            ps.append(p)
            while t % p == 0: t //= p
        p = int(gmpy2.next_prime(p))
    if t > 1: ps.append(int(t))
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

def side(J, zd, pc, sme, cls_ps, pizd):
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
    for p0 in cls_ps:
        mn = float(w[sl % p0 != 0].sum())
        fac *= (1.0 - mn / max(tot, 1e-9) / (p0 - 1))
    return fac * tot

def main():
    t0 = time.time()
    bs = np.ones(JMAX + 1, bool); bs[:2] = False
    for p in range(2, int(JMAX ** 0.5) + 1):
        if bs[p]: bs[p * p::p] = False
    pc = np.cumsum(bs)
    pr = np.nonzero(bs)[0]
    lg1m = np.log1p(-1.0 / pr.astype(float))
    cum = np.cumsum(lg1m)
    def thq(zd):
        i0 = int(np.searchsorted(pr, zd, side="right"))
        i1 = int(np.searchsorted(pr, Q, side="right"))
        return math.exp(float(cum[i1 - 1] - (cum[i0 - 1] if i0 else 0)))
    print(f"setup [{time.time()-t0:.0f}s]")
    print("\n== H7: hygiene-aware bridge vs published records ==")
    print(f"{'rk':>2} {'u':>6} {'struct':>10} {'infl':>6} "
          f"{'sig_ex':>7} {'sig_th':>7} {'dev%':>6}")
    uu, yth, yex, devs, inflR = [], [], [], [], {}
    for rk, gap, D, k, zd, ds, jl, sx in ROWS:
        dv, dps = factor_d(ds)
        odd = [p for p in dps if p != 2]
        strc = [p for p in odd if k % p == 0]
        clsp = [p for p in odd if k % p != 0]
        base = sorted([2] + clsp)
        theta = float(cum[0]) * 0  # placeholder keeps lints quiet
        th_zd = float(np.sum(np.log(pr[pr <= zd])))
        ln0 = float(gmpy2.log(gmpy2.mpz(k))) + th_zd - math.log(dv)
        m = gap / ln0
        u = 1.0 + math.log(m / 2.0) / math.log(ln0)
        jr = jl + gap
        sme = smooth_even(base, max(-jl, jr))
        pizd = int(pc[zd])
        T = (side(-jl, zd, pc, sme, clsp, pizd)
             + side(jr, zd, pc, sme, clsp, pizd))
        th = T * thq(zd) * EG * math.log(Q) / (ln0 * m)
        # inflation vs the hygiene-blind bridge (all odd d-primes as class)
        sme0 = smooth_even(sorted([2] + odd), max(-jl, jr))
        T0 = (side(-jl, zd, pc, sme0, odd, pizd)
              + side(jr, zd, pc, sme0, odd, pizd))
        th0 = T0 * thq(zd) * EG * math.log(Q) / (ln0 * m)
        infl = th / max(th0, 1e-12)
        dev = (th / sx - 1) * 100
        uu.append(u); yth.append(th); yex.append(sx); devs.append(dev)
        if strc: inflR[rk] = infl
        print(f"{rk:>2} {u:>6.3f} {str(strc):>10} {infl:>6.3f} "
              f"{sx:>7.3f} {th:>7.3f} {dev:>+6.1f}")
    h7 = all(abs(d) <= 8.0 for d in devs) and \
         all(1.30 <= inflR[r] <= 1.50 for r in (18, 20) if r in inflR)
    print(f"  within 8%: {sum(abs(d) <= 8 for d in devs)}/20")

    print("\n== H8: emergent shelf slope, theory vs measured ==")
    x = np.array(uu) - 1.0
    X = np.column_stack([x, x * x])
    at, bt = np.linalg.lstsq(X, np.array(yth), rcond=None)[0]
    am, bm = np.linalg.lstsq(X, np.array(yex), rcond=None)[0]
    print(f"  theory:   a = {at:.4f}  b = {bt:.4f}")
    print(f"  measured: a = {am:.4f}  b = {bm:.4f}   e^g = {EG:.4f}")
    h8 = (1.65 <= at <= 1.95) and (abs(at - am) <= 0.06)
    print(f"\nH7 hygiene bridge:  {'PASS' if h7 else 'REFUTED'}")
    print(f"H8 emergent e^g:    {'PASS' if h8 else 'REFUTED'}")
    print(f"[{time.time()-t0:.0f}s total]")

if __name__ == "__main__":
    main()
