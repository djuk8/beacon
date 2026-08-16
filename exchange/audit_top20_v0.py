#!/usr/bin/env python3
"""audit_top20_v0.py -- exact-sieve audit of the all-time largest-gaps
top-20 (table as published, 2026-08). Every row is a complete audit
input: n0 = k*zd#/d, left offset jl, gap. Per row this measures:
  E_res   exact window sieve at Q (Q-invariant, gated instrument)
  u_max   depth of the window in the resonance coordinate
  E/m     the size-game slope -- unmeasured band until this run
  e^E     implied windows (luck spent), asymmetry jl:jr
  merit   recomputed from the expression (transcription check)
  ???     rows also get the interior re-verification price:
          survivors@1e9 x s_PRP(D), s_PRP = 2107.7*(D/388655)^2.1 s
          [anchor MEASURED on shredder; exponent MODEL, gwnum FFT]

Reuses resonance_map.sieve_window (gated). Must sit in the same dir.
  python3 audit_top20_v0.py --Q 1000000
  python3 audit_top20_v0.py --rows 1,14,15
"""
import argparse, math, time
import numpy as np
import gmpy2
from resonance_map import primes_upto, sieve_window, GAMMA

try:
    import sys
    sys.set_int_max_str_digits(2_000_000)
except Exception:
    pass

# rank, gap, D, merit_listed, k, zd, d, jl, flag, who, year
ROWS = [
 (1, 16045848, 385713, 18.0669, 1217, 888887, "23#", -7636494, "???", "Hoglund", 2024),
 (2, 8193558, 289083, 12.3094, 1, 666667, "17#", -6334558, "???", "Hoglund", 2023),
 (3, 7769676, 289082, 11.6726, 43, 666667, "23#", -5594774, "???", "Hoglund", 2023),
 (4, 7186572, 208095, 14.9985, 29, 479909, "9699690", -3531714, "PRP", "J&A", 2022),
 (5, 6966714, 208096, 14.5395, 1, 479909, "30030", -3166622, "PRP", "J&A", 2022),
 (6, 6647694, 337314, 8.5590, 2437, 777787, "23#", -2374658, "???", "Hoglund", 2023),
 (7, 6582144, 216841, 13.1829, 1, 499973, "30030", -4509212, "PRP", "Raab", 2017),
 (8, 6480930, 208093, 13.5259, 1, 479909, "9699690", -2492758, "PRP", "J&A", 2022),
 (9, 6181674, 208094, 12.9012, 1, 479909, "510510", -3758926, "PRP", "J&A", 2022),
 (10, 5384030, 173457, 13.4804, 829, 400009, "46410", -2470148, "PRP", "RS/J&A", 2022),
 (11, 5198448, 157490, 14.3353, 363257, 363269, "510510", -2177806, "PRP", "J&A", 2021),
 (12, 5103138, 216849, 10.2203, 281, 499979, "46410", -2702372, "PRP", "RSmith", 2016),
 (13, 4854690, 208102, 10.1314, 479903, 479909, "2310", -1944886, "PRP", "J&A", 2022),
 (14, 4680156, 99750, 20.3767, 1, 230077, "2229464046810", -3131794, "PRP", "Raab", 2016),
 (15, 4656036, 303518, 6.6622, 1627, 700001, "23#", -2745914, "???", "Hoglund", 2023),
 (16, 4397298, 97234, 19.6406, 1, 224423, "107371994730", -2375864, "PRP", "Raab", 2021),
 (17, 4362420, 151940, 12.4693, 350351, 350377, "2310", -2859322, "PRP", "J&A", 2022),
 (18, 3921168, 179864, 9.4680,
  3652026499164494422179566474085691865, 414949, "30030", -2237306,
  "PRP", "Renyer", 2026),
 (19, 3870360, 135376, 12.4164, 2267, 312583, "46410", -1157722, "PRP",
  "RSmith", 2018),
 (20, 3436432, 151952, 9.8217,
  1322983044025855821143464371513327685, 350293, "30030", -1051678,
  "PRP", "Renyer", 2026),
]

_pc = {}


def prim(z):
    if z not in _pc:
        P = gmpy2.mpz(1); p = gmpy2.mpz(2)
        while p <= z:
            P *= p; p = gmpy2.next_prime(p)
        _pc[z] = P
    return _pc[z]


def dval(s):
    return prim(int(s[:-1])) if s.endswith("#") else gmpy2.mpz(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Q", type=int, default=10 ** 6)
    ap.add_argument("--rows", default="")
    a = ap.parse_args()
    sel = set(int(x) for x in a.rows.split(",")) if a.rows else None
    t0 = time.time()
    prs = primes_upto(a.Q)
    print(f"primes to {a.Q:,}: {len(prs):,} [{time.time()-t0:.0f}s]")
    print(f"{'rk':>2} {'who':>7} {'yr':>4} {'flag':>4} {'D':>6} {'zd':>6} "
          f"{'m_list':>7} {'m_re':>7} {'u':>5} {'asym':>5} | "
          f"{'E':>6} {'E/m':>5} {'e^E':>9} | {'surv@1e9':>8} {'ver_cd':>7}")
    out = []
    for r in ROWS:
        rk, gap, D, ml, k, zd, ds, jl, fl, who, yr = r
        if sel and rk not in sel:
            continue
        t1 = time.time()
        num = gmpy2.mpz(k) * prim(zd)
        d = dval(ds)
        assert num % d == 0, f"row {rk}: d does not divide k*zd#"
        n0 = num // d
        ln_n0 = float(gmpy2.log(n0))
        assert abs(len(gmpy2.digits(n0, 10)) - D) <= 1, f"row {rk}: digits"
        n0mod = np.array([int(n0 % int(p)) for p in prs],
                         dtype=np.int64)
        jr = jl + gap
        s = sieve_window(n0mod, prs, jl, jr)
        E = s * math.exp(GAMMA) * math.log(a.Q) / ln_n0
        m_re = gap / ln_n0
        u = max(math.log(-jl), math.log(jr)) / math.log(zd)
        asym = (-jl) / jr
        surv9 = E * ln_n0 / (math.exp(GAMMA) * math.log(10 ** 9))
        sprp = 2107.7 * (D / 388655.0) ** 2.1
        ver_cd = surv9 * sprp / 86400.0
        out.append((rk, u, E, E / m_re))
        print(f"{rk:>2} {who:>7} {yr:>4} {fl:>4} {D:>6} {zd:>6} "
              f"{ml:>7.4f} {m_re:>7.4f} {u:>5.3f} {asym:>5.2f} | "
              f"{E:>6.2f} {E/m_re:>5.3f} {math.exp(E):>9.2e} | "
              f"{surv9:>8.0f} {ver_cd:>7.1f}"
              f"   [{time.time()-t1:.0f}s]")
    if len(out) > 3:
        out.sort(key=lambda x: x[1])
        lo = [x for x in out if x[1] < 1.17]
        hi = [x for x in out if x[1] >= 1.17]
        for name, grp in (("u<1.17", lo), ("u>=1.17", hi)):
            if grp:
                print(f"slope read {name}: mean E/m = "
                      f"{np.mean([g[3] for g in grp]):.3f} "
                      f"(n={len(grp)}, sd {np.std([g[3] for g in grp]):.3f})")
    print(f"[{time.time()-t0:.0f}s total]  ver_cd = interior re-verify "
          f"price, core-days [s_PRP exponent MODEL]")


if __name__ == "__main__":
    main()
