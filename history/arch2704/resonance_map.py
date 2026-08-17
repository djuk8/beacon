#!/usr/bin/env python3
"""resonance_map.py -- v5 design instrument. At fixed D, map E_res over
(zd, swap set, window alignment) for the primorial-resonance construction
n0 = k * zd# / d decoded from the frontier audit (2026-08-02):
    zd ~ 1.01 x ln n0, window inside u <= ~1.35, small-swap d, k-scan.

E_res(config) = mean over sampled k of [window survivors x beta(Q_map)],
computed by EXACT sieving of the exact window -- pure arithmetic, no
primality, no GPU. Windows needed for a target merit = e^{E_res} (the
scan's luck budget); alignment slide measures the free offset e-units.

SELF-GATE: --gate reruns the instrument on the three audited frontier
artifacts (their exact zd, d, k, window) and must reproduce the measured
E_res (17.85 / 16.91 / 16.71) within 2% before any map is trusted.

  python3 resonance_map.py --gate
  python3 resonance_map.py --digits 2700 --target 32.25
"""
import argparse, math, sys, time
import numpy as np
import gmpy2

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass
GAMMA = 0.5772156649015329


def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.nonzero(s)[0].astype(np.int64)


def primorial(zd):
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p <= zd:
        P *= p; p = gmpy2.next_prime(p)
    return P


def sieve_window(n0mod, prs, jl, jr):
    """Survivor count of (jl, jr) exclusive given n0 mod p for all p."""
    W = jr - jl - 1
    alive = np.ones(W, dtype=bool)
    off = jl + 1
    js = np.arange(off, jr)
    # parity: kill j with n0+j even
    if n0mod[0] == 1:
        alive[(js % 2) != 0] = False
    else:
        alive[(js % 2) == 0] = False
    small = prs[prs <= W]
    for i in range(1, len(small)):
        p = int(small[i])
        idx0 = ((-int(n0mod[i])) % p - off) % p
        alive[idx0::p] = False
    big = prs[len(small):]
    if len(big):
        m = n0mod[len(small):]
        j0 = (-m) % big                     # (-n0) mod p in [0, p)
        hi = j0 < jr                        # j0 itself in window (j0 >= 0 > off)
        lo = (j0 - big) >= off              # the negative-side landing
        for jj in (j0[hi], (j0 - big)[lo]):
            if len(jj):
                alive[(jj - off).astype(np.int64)] = False
    return int(alive.sum())


class Config:
    def __init__(self, zd, swap, Q, prs):
        self.zd, self.swap = zd, sorted(swap)
        self.d = 1
        for p in self.swap: self.d *= p
        self.P_eff = primorial(zd) // self.d
        self.digP = len(gmpy2.digits(self.P_eff, 10))
        self.prs = prs
        self.PEmod = np.array([int(self.P_eff % int(p)) for p in prs],
                              dtype=np.int64)

    def n0mod(self, k):
        return (int(k) % self.prs) * self.PEmod % self.prs

    def kdig(self, D):
        return D - self.digP


def audit_gate(prs, Q):
    beta = math.exp(GAMMA) * math.log(Q)
    REF = [("213240", 6703, [2, 3, 5, 7, 13, 17], 586399, -131770, 213240,
            17.85),
           ("313842", 9923, [2, 3, 5, 7, 13, 17], 343921, -205340, 313842,
            16.91),
           ("247370", 7919, [2, 3, 5, 7, 11], 30006181, -112238, 247370,
            16.71)]
    ok = True
    for name, zd, sw, k, jl, gap, want in REF:
        c = Config(zd, sw, Q, prs)
        n0 = k * c.P_eff
        ln_n0 = float(gmpy2.log(n0))
        s = sieve_window(c.n0mod(k), prs, jl, jl + gap)
        E = s * beta / ln_n0
        d = abs(E - want) / want
        print(f"  gate {name}: E_res {E:.2f} vs audited {want:.2f} "
              f"({100*d:.1f}%)")
        ok &= d < 0.02
    print("MAP GATE", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--digits", type=int, default=2700)
    ap.add_argument("--target", type=float, default=32.25)
    ap.add_argument("--Q", type=int, default=10**7)
    ap.add_argument("--zd-grid", default="")
    ap.add_argument("--nk", type=int, default=8)
    ap.add_argument("--align", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    t0 = time.time()
    prs = primes_upto(a.Q)
    print(f"primes to {a.Q:,}: {len(prs):,} [{time.time()-t0:.0f}s]")
    if not audit_gate(prs, a.Q):
        sys.exit(1)
    if a.gate:
        return

    ln_n0 = a.digits * math.log(10)
    beta = math.exp(GAMMA) * math.log(a.Q) / ln_n0
    G = math.ceil(a.target * ln_n0)           # target gap
    SWAPS = [("RS", [2, 3, 5, 7, 13, 17]),
             ("MJ", [2, 3, 5, 7, 11]),
             ("RS+19", [2, 3, 5, 7, 13, 17, 19]),
             ("RS+19.23", [2, 3, 5, 7, 13, 17, 19, 23]),
             ("RS+19..31", [2, 3, 5, 7, 13, 17, 19, 23, 29, 31]),
             ("cons..17", [2, 3, 5, 7, 11, 13, 17])]
    # zd is SOLVED, not chosen: walk the primorial until digits(zd#/d)
    # leaves the desired k budget. (theta(zd) < zd: that 1.6% gap is
    # exactly where k and d live -- the frontier's one-equation dial.)
    prim_p, prim_v = [], []
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p < 9000:
        P *= p; prim_p.append(int(p)); prim_v.append(P); p = gmpy2.next_prime(p)
    def solve_zd(digd, kdig):
        want = a.digits - kdig + digd          # digits(zd#) target
        for i, Pv in enumerate(prim_v):
            if len(gmpy2.digits(Pv, 10)) >= want:
                return prim_p[i]
        return None
    rng = np.random.default_rng(a.seed)
    rows = []
    cfgs = []
    for lab, sw in SWAPS:
        digd = len(str(math.prod(sw)))
        for kdt in (5, 8):
            zd = solve_zd(digd, kdt)
            if zd and (zd, tuple(sw)) not in [(z, tuple(s2)) for z, _, s2 in cfgs]:
                cfgs.append((zd, lab, sw))
    print(f"\ntarget gap {G:,} (merit {a.target}); "
          f"{a.nk} k-samples x {a.align} alignments per config")
    print(f"{'zd':>6} {'zd/ln':>6} {'swap':>10} {'kdig':>4} | "
          f"{'E_mean':>6} {'E_sd':>5} {'E_min':>6} {'u_max':>5} | "
          f"{'wins(e^E)':>10}")
    for zd, lab, sw in cfgs:
            c = Config(zd, sw, a.Q, prs)
            kd = c.kdig(a.digits)
            if not (4 <= kd <= 10):
                continue
            klo, khi = 10 ** (kd - 1), 10 ** kd - 1
            Es = []
            for ai in range(a.align):
                jl = -(G // 2) - (ai - a.align // 2) * (G // (2 * a.align))
                jr = jl + G
                um = max(math.log(-jl), math.log(jr)) / math.log(zd)
                for _ in range(a.nk):
                    while True:
                        k = int(rng.integers(klo, khi)) | 1
                        if math.gcd(k, c.d) == 1: break
                    s = sieve_window(c.n0mod(k), prs, jl, jr)
                    Es.append((s * beta, ai))
            E = np.array([e for e, _ in Es])
            # best alignment by mean
            ali = {}
            for e, ai in Es: ali.setdefault(ai, []).append(e)
            best = min(np.mean(v) for v in ali.values())
            rows.append((zd, lab, kd, E.mean(), E.std(ddof=1), best, um))
            print(f"{zd:>6} {zd/ln_n0:>6.3f} {lab:>10} {kd:>4} | "
                  f"{E.mean():>6.2f} {E.std(ddof=1):>5.2f} {best:>6.2f} "
                  f"{um:>5.2f} | {math.exp(best):>10.2e}")
    if not rows:
        sys.exit("no admissible configs -- widen kdig targets")
    rows.sort(key=lambda r: r[5])
    zd, lab, kd, em, es, best, um = rows[0]
    tests_per_win = 1.0 / (math.exp(GAMMA) * math.log(10**9) / ln_n0)
    cd = math.exp(best) * tests_per_win / 2165.0 / 86400.0
    print(f"\nBEST: zd={zd} swap={lab} kdig={kd}: E_res(best-align) "
          f"{best:.2f} -> {math.exp(best):.2e} windows x {tests_per_win:.0f} "
          f"tests (1/beta@1e9, center-out) / 2,165 t/s = {cd:.1f} card-days "
          f"[MODEL: scan-mode orchestration + alignment/phase freedom beyond "
          f"the {a.align}-slide]")
    print(f"[{time.time()-t0:.0f}s total]")


if __name__ == "__main__":
    main()
