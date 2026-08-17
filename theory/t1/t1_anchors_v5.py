#!/usr/bin/env python3
"""t1_anchors_v5.py -- swap-aware bridge: campaigns + designs + raid
ladder + crown-siege re-price. PREREG: T1_PREREG_v5 (2026-08-17).
Exact per-position class survival (upgrade over v4 mass-fac).
  python3 t1_anchors_v5.py > t1a_v5.txt
"""
import math, sys, time
import numpy as np
import gmpy2

sys.set_int_max_str_digits(2_000_000)
G = 0.5772156649015329
EG = math.exp(G)
LN10 = math.log(10)
Q = 10 ** 6
LNQ = math.log(Q)
JMAX = 640_000
A_P, B_P = 1.8169, -0.5587

# name, m, ln_n0, zd (0 = derive), odd d-primes, sigma_exact
CAMP = [
    ("monument", 20.05, 26600 * LN10, 61493, (3, 5, 7, 11, 13), 0.3576),
    ("strike",   30.10,  6152 * LN10, 14341, (3, 5, 7, 11, 13), 0.4897),
    ("record",   32.385, 2705 * LN10,  6301, (3, 5, 7, 11, 13), 0.5391),
]
DESIGN = [
    ("87d MJ", 41.9388,  87 * LN10, (3, 5, 7, 11),     0.8427),
    ("87d RS", 41.9388,  87 * LN10, (3, 5, 7, 13, 17), 0.8586),
    ("97d",    37.8241,  97 * LN10, (3, 5, 7, 11),     0.8233),
    ("164d",   38.5122, 164 * LN10, (3, 5, 7, 11),     0.7676),
    ("175d",   39.6202, 175 * LN10, (3, 5, 7, 11),     0.7608),
]
RINGS = [(1568, 1.70), (4374, 3.41), (7244, 5.40), (10198, 7.80),
         (13500, 10.80), (17734, 15.00), (26542, 24.63)]


def smooth_even(odd_ps, lim):
    base = [2] + list(odd_ps)
    out = []
    def rec(v, i):
        out.append(v)
        for j in range(i, len(base)):
            if v * base[j] > lim:
                break
            rec(v * base[j], j)
    rec(1, 0)
    a = np.array(sorted(out), dtype=np.int64)
    return a[(a % 2 == 0)]


def survf(s, odd_ps):
    f = 1.0
    for p in odd_ps:
        if s % p:
            f *= 1.0 - 1.0 / (p - 1)
    return f


def make_side(pc, pizd, zd, odd_ps, lim):
    sm = smooth_even(odd_ps, lim)
    sf = np.array([survf(int(s), odd_ps) for s in sm])
    def side(J):
        tot = 0.0
        for s, f in zip(sm, sf):
            s = int(s)
            if s > J:
                break
            if J // s > zd:
                t = int(pc[J // s]) - pizd
                if t > 0:
                    tot += f * t
            tot += f            # the pure-smooth position j = s
        return tot
    return side


def main():
    t0 = time.time()
    bs = np.ones(JMAX + 1, bool); bs[:2] = False
    for p in range(2, int(JMAX ** 0.5) + 1):
        if bs[p]:
            bs[p * p::p] = False
    pc = np.cumsum(bs)
    pr = np.nonzero(bs)[0]
    prs6 = pr[pr <= Q] if JMAX >= Q else None
    # thq needs primes to Q=1e6
    s6 = np.ones(Q + 1, bool); s6[:2] = False
    for p in range(2, 1001):
        if s6[p]:
            s6[p * p::p] = False
    P6 = np.nonzero(s6)[0]
    CUM = np.cumsum(np.log1p(-1.0 / P6.astype(float)))
    def thq(zd):
        i0 = int(np.searchsorted(P6, zd, side="right")) - 1
        return math.exp(float(CUM[-1] - CUM[i0]))
    th_tab = np.zeros(JMAX + 1)
    th_tab[pr] = np.log(pr)
    THC = np.cumsum(th_tab)      # theta(x)
    print(f"setup [{time.time()-t0:.0f}s]")

    def sigma(m, ln0, zd, odd_ps):
        jf = int(round(0.5 * m * ln0))
        side = make_side(pc, int(pc[zd]), zd, odd_ps, jf)
        S = 2.0 * side(jf) * thq(zd)
        return S * EG * LNQ / (ln0 * m), jf

    print("\n== H9: campaign rows ==")
    print(f"{'name':>9} {'u':>6} {'zd':>6} {'sig_ex':>7} {'sig_th':>7} "
          f"{'dev%':>6}")
    d9 = []
    for name, m, ln0, zd, odd_ps, sx in CAMP:
        st, _ = sigma(m, ln0, zd, odd_ps)
        u = 1 + math.log(m / 2) / math.log(ln0)
        d9.append((st / sx - 1) * 100)
        print(f"{name:>9} {u:>6.3f} {zd:>6} {sx:>7.4f} {st:>7.4f} "
              f"{d9[-1]:>+6.1f}")

    print("\n== H10: design rows (zd unknown -> two candidates) ==")
    print(f"{'name':>7} {'u':>6} {'zd_a':>5} {'th_a':>7} {'zd_b':>5} "
          f"{'th_b':>7} {'sig_ex':>7} {'best%':>6}")
    d10 = []
    for name, m, ln0, odd_ps, sx in DESIGN:
        za = int(gmpy2.next_prime(int(1.005 * ln0)))
        zb = int(gmpy2.next_prime(int(1.02 * ln0)))
        sa, _ = sigma(m, ln0, za, odd_ps)
        sb, _ = sigma(m, ln0, zb, odd_ps)
        u = 1 + math.log(m / 2) / math.log(ln0)
        best = min((sa / sx - 1), (sb / sx - 1), key=abs) * 100
        d10.append(best)
        print(f"{name:>7} {u:>6.3f} {za:>5} {sa:>7.4f} {zb:>5} "
              f"{sb:>7.4f} {sx:>7.4f} {best:>+6.1f}")

    print("\n== H11: raid610 ladder, theory vs design ==")
    zd, odd_ps = 1439, (3, 5, 7, 11)
    ln0 = math.log(5e12) + float(THC[zd]) - math.log(2310.0)
    side = make_side(pc, int(pc[zd]), zd, odd_ps, RINGS[-1][0])
    tq = thq(zd)
    print(f"  ln_n0 = {ln0:.1f}   (design 1403.3)")
    print(f"{'ring':>5} {'edge':>6} {'E_des':>6} {'E_th':>6} {'ratio':>6}")
    rat = []
    for i, (e, Ed) in enumerate(RINGS, 1):
        Et = 2.0 * side(e) * tq * EG * LNQ / ln0
        rat.append(Et / Ed)
        print(f"  r{i:<3} {e:>6} {Ed:>6.2f} {Et:>6.2f} {Et/Ed:>6.3f}")

    print("\n== SIEGE RE-PRICE (87d MJ, m just above 41.9388) ==")
    m = 41.9430
    ln0s = 87 * LN10
    for ztag, zf in (("a", 1.005), ("b", 1.02)):
        zs = int(gmpy2.next_prime(int(zf * ln0s)))
        st, _ = sigma(m, ln0s, zs, (3, 5, 7, 11))
        E = m * st
        for rate, tag in ((14500.0, "now "), (43000.0, "f20 ")):
            days = math.exp(E) / rate / 86400.0
            print(f"  zd_{ztag}={zs}: E={E:6.2f}  e^E={math.exp(E):9.3e} "
                  f"windows  {tag}{days:9.1f} days")
    u = 1 + math.log(m / 2) / math.log(ln0s)
    x = u - 1
    Ep = m * (A_P * x + B_P * x * x)
    print(f"  poly (retired figure): E={Ep:6.2f}  "
          f"ratio e^(E_th-E_poly) = windows multiplier vs old price")

    h9 = all(abs(d) <= 8.0 for d in d9)
    h10 = sum(abs(d) <= 12.0 for d in d10) >= 4
    h11 = all(abs(r - 1) <= 0.08 for r in rat[4:])
    print(f"\nH9  campaigns <=8%:      {'PASS' if h9 else 'REFUTED'}")
    print(f"H10 designs 4/5 <=12%:   {'PASS' if h10 else 'REFUTED'}")
    print(f"H11 rings 5-7 <=8%:      {'PASS' if h11 else 'REFUTED'} "
          f"(ring-1 stress ratio {rat[0]:.3f}, info)")
    print(f"[{time.time()-t0:.0f}s total]")


if __name__ == "__main__":
    main()
