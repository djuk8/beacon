#!/usr/bin/env python3
"""merit_price_v0.py -- price the ALL-TIME MERIT crowns with the derived law.

Targets (from arbitrage_map top): 8350/41.9388@87d (Gapcoin 2017),
15900/39.6202@175d (Jacobsen), 14496/38.5122@164d (Loizides),
8382/37.8241@97d (Jacobsen). All sit at u ~ 1.5-1.6 < 2: bridge-valid.

REUSES resonance_map.py's gated machinery (sieve_window, Config,
audit_gate). Must sit in the same directory. Run --gate first; a FAIL
means do not trust any number below.

NEW PHYSICS THIS MEASURES (small-D corner):
  ln(k-space) = kdig*ln10 can be SMALLER than E  ->  the crown is
  scan-space-limited, not compute-limited. We sweep kdig 5..16 (smaller
  zd buys k-entropy at the cost of worse resonance) and report
  margin = kdig*ln10 + ln(align_slots) - E_best. Feasible needs
  margin >> 0. This may be WHY 41.94 stood nine years.

FLAGS: E is EXACT-SIEVE MEASURED per config (given class-equidistribution
<=1e-4). T_w uses ladder-ratio 2.9 = 490 * beta(1e9, 2705d) MEASURED at
m=32.25, D-transfer ASSUMED [MODEL]. GPU rate at ~290-1000 bit classes:
UNMEASURED -- do not extrapolate; run the CPU bench one-liner and (if
worth it) a real small-class GPU bench before any fleet decision.

  python3 merit_price_v0.py --gate
  python3 merit_price_v0.py --crown 87:41.9388 --Q 1000000
  python3 merit_price_v0.py --crown 175:39.6202 --crown 164:38.5122
  python3 merit_price_v0.py --audit "L<87-digit-literal>:-4100:8350"
  python3 merit_price_v0.py --audit "1234567*397#/30030:-7900:15900"
"""
import argparse, math, sys, time
import numpy as np
import gmpy2
from resonance_map import primes_upto, primorial, sieve_window, \
    Config, audit_gate, GAMMA

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass


def build_prims(pmax=12000):
    prim_p, prim_v = [], []
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p < pmax:
        P *= p; prim_p.append(int(p)); prim_v.append(P)
        p = gmpy2.next_prime(p)
    return prim_p, prim_v


def solve_zd(prim_p, prim_v, D, digd, kdig):
    want = D - kdig + digd
    for i, Pv in enumerate(prim_v):
        if len(gmpy2.digits(Pv, 10)) >= want:
            return prim_p[i]
    return None


SWAPS = [("MJ", [2, 3, 5, 7, 11]),
         ("13#", [2, 3, 5, 7, 11, 13]),
         ("RS", [2, 3, 5, 7, 13, 17]),
         ("cons17", [2, 3, 5, 7, 11, 13, 17]),
         ("RS+19", [2, 3, 5, 7, 13, 17, 19])]


def price_crown(D, m_beat, prs, Q, nk, align, rng):
    prim_p, prim_v = build_prims()
    beta_run = math.exp(GAMMA) * math.log(Q)
    print(f"\n=== CROWN CLASS {D}d, beat merit {m_beat} ===")
    print(f"{'zd':>5} {'zd/ln':>6} {'swap':>7} {'kdig':>4} {'u_max':>5} | "
          f"{'E_mean':>6} {'sd':>4} {'E_best':>6} | {'lnK':>5} {'margin':>6}")
    rows = []
    seen = set()
    for lab, sw in SWAPS:
        digd = len(str(math.prod(sw)))
        for kdt in range(5, 17):
            zd = solve_zd(prim_p, prim_v, D, digd, kdt)
            if zd is None or (zd, tuple(sw)) in seen:
                continue
            seen.add((zd, tuple(sw)))
            c = Config(zd, sw, Q, prs)
            kd = c.kdig(D)
            if not (4 <= kd <= 16):
                continue
            klo, khi = 10 ** (kd - 1), 10 ** kd - 1
            Es, um = [], 0.0
            for ai in range(align):
                # per-k exact ln n0 and per-k gap target
                for _ in range(nk):
                    while True:
                        k = int(rng.integers(klo, khi)) | 1
                        if math.gcd(k, c.d) == 1:
                            break
                    n0 = k * c.P_eff
                    ln_n0 = float(gmpy2.log(n0))
                    G = int(m_beat * ln_n0) + 1      # first gap that beats
                    jl = -(G // 2) - (ai - align // 2) * (G // (2 * align))
                    jr = jl + G
                    um = max(um,
                             max(math.log(-jl), math.log(jr)) / math.log(zd))
                    s = sieve_window(c.n0mod(k), prs, jl, jr)
                    Es.append((s * beta_run / ln_n0, ai))
            E = np.array([e for e, _ in Es])
            ali = {}
            for e, ai in Es:
                ali.setdefault(ai, []).append(e)
            best = min(np.mean(v) for v in ali.values())
            lnK = kd * math.log(10)                  # k-entropy (upper bnd)
            margin = lnK + math.log(align) - best    # phi(d)/d ~ -1.2 more
            rows.append((zd, lab, kd, um, E.mean(), E.std(ddof=1),
                         best, lnK, margin))
            print(f"{zd:>5} {zd/ (D*math.log(10)):>6.3f} {lab:>7} {kd:>4} "
                  f"{um:>5.2f} | {E.mean():>6.2f} {E.std(ddof=1):>4.2f} "
                  f"{best:>6.2f} | {lnK:>5.1f} {margin:>+6.1f}")
    feas = [r for r in rows if r[8] > 2.0]
    pool = feas if feas else rows
    pool.sort(key=lambda r: r[6])
    zd, lab, kd, um, em, es, best, lnK, margin = pool[0]
    ln_n0 = D * math.log(10)
    beta9 = math.exp(GAMMA) * math.log(10 ** 9) / ln_n0
    T_w = 2.9 / beta9        # ladder ratio 2.9 MEASURED @2705d [MODEL here]
    N_lo, N_hi = math.exp(best) / 8, math.exp(best) / 2   # A in [2,8]
    print(f"\nBEST {'FEASIBLE' if feas else '(NONE FEASIBLE -- scan-space '
          'wall; best anyway)'}: zd={zd} swap={lab} kdig={kd} "
          f"E_best={best:.2f} margin={margin:+.1f} e-units")
    print(f"windows N = e^E/A          : {N_lo:.2e} - {N_hi:.2e}   [A 2-8]")
    print(f"tests/window T_w ~ 2.9/beta9: {T_w:.0f}   "
          f"[MODEL: ladder ratio D-transfer]")
    print(f"total tests                : {N_lo*T_w:.2e} - {N_hi*T_w:.2e}")
    print(f"sieve ops ~ N x pi({Q:.0e}) : "
          f"{N_lo*len(prs):.1e} - {N_hi*len(prs):.1e}  [scan-mode ABPE]")
    print("RATES: GPU@this bit-class UNMEASURED (do NOT extrapolate n^3 or "
          "x2.95 past range). CPU MR-25 rate: run the bench one-liner. "
          "At this size the CPU fleet may be competitive.")
    if not feas:
        print("SCAN-SPACE WALL: kdig*ln10 + ln(align) < E for every config "
              "-- the k-scan cannot spend the luck budget. Levers: more "
              "alignment slots, d-variants, multi-zd portfolio. This "
              "structural fact is itself a paper-2 result.")


def parse_audit(spec, prs, Q):
    head, jl, gap = spec.rsplit(":", 2)
    jl, gap = int(jl), int(gap)
    if head.startswith("L"):
        n0 = gmpy2.mpz(head[1:])
    else:
        expr = head.replace(" ", "")
        kpart, rest = expr.split("*")
        zdpart, dpart = (rest.split("/") + ["1"])[:2]
        n0 = gmpy2.mpz(kpart) * primorial(int(zdpart.rstrip("#"))) \
            // gmpy2.mpz(dpart)
    ln_n0 = float(gmpy2.log(n0))
    n0mod = np.array([int(n0 % int(p)) for p in prs], dtype=np.int64)
    s = sieve_window(n0mod, prs, jl, jl + gap)
    E = s * math.exp(GAMMA) * math.log(Q) / ln_n0
    print(f"AUDIT {head[:40]}... gap={gap} jl={jl}: survivors={s}  "
          f"E_res={E:.2f}  merit={gap/ln_n0:.4f}  E/m={E*ln_n0/gap:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--crown", action="append", default=[],
                    help="D:merit_to_beat, e.g. 87:41.9388")
    ap.add_argument("--audit", action="append", default=[],
                    help="'k*zd#/d:jl:gap' or 'L<decimal>:jl:gap'")
    ap.add_argument("--Q", type=int, default=10 ** 6)
    ap.add_argument("--nk", type=int, default=12)
    ap.add_argument("--align", type=int, default=7)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    t0 = time.time()
    prs = primes_upto(a.Q)
    print(f"primes to {a.Q:,}: {len(prs):,} [{time.time()-t0:.0f}s]")
    if not audit_gate(prs, a.Q):
        sys.exit(1)
    if a.gate:
        return
    rng = np.random.default_rng(a.seed)
    for spec in a.audit:
        parse_audit(spec, prs, a.Q)
    for cs in a.crown:
        D, m = cs.split(":")
        price_crown(int(D), float(m), prs, a.Q, a.nk, a.align, rng)
    print(f"[{time.time()-t0:.0f}s total]")


if __name__ == "__main__":
    main()
