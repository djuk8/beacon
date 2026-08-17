#!/usr/bin/env python3
"""swap_instrument_v0 -- paper-1 Section-3/4 instrument as a campaign tool.

Legendre-recursion exact-prime density table F_j(x) = Phi(e^x, p_j) e^{-x}
(true primes, v0 default scope p <= 3203, linear-interp grid h=2^-13) plus
the Section-4 operator factorization for 2-adic swap stacks:
    #surv/G = [ prod_{p in T} ((p-2)/(p-1) Id + A_p) ] F(lambda).

USAGE (gate first on any new box, always):
  python3 swap_instrument_v0.py                     # 28-check gate vs the
                                                    #  paper's published battery
  python3 swap_instrument_v0.py umap --D 24000 --merit 4
      Where does a design sit? Computes campaign zd(D) (livefire theta rule),
      u = ln G / ln zd, regime verdict. Optional --zd for reduced anchors,
      --gap instead of --merit. Prints the stride check theta(zd) >= ln G.
  python3 swap_instrument_v0.py window --z 797
      Swap-window edges (u_on, u_off) at this z: where the 2-swap starts and
      stops paying. Paper receipts at 797: (2.341, 3.121).
  python3 swap_instrument_v0.py price --z 43 --u 2.5 --maxdepth 6
      Stack price sheet at (z, u): survivor ratio vs primorial for depths
      (2), (2,3), ..., optimal depth marked. If G = z^u <= 2e8 the ratios are
      ALSO verified by exact retargeted re-sieves (classes = 1), printed
      side by side -- at throne scale the instrument is exact-first.

v0 limits: raise --zmax for z > 3203 (cost ~ pi(zmax) grid ops); the race
model / fixed-merit crossover ladder is NOT in v0 -- next build joins these
densities to campaign cost constants (T_prp, 5090 curve, screen factors).
"""
import argparse, math, sys, time
import numpy as np

H = 2.0 ** -13
XMAX = 45.5
X = np.arange(0.0, XMAX, H)
LN = math.log
STACK_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19]


def primes_upto(n):
    s = np.ones(n + 1, bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return [int(p) for p in np.flatnonzero(s)]


def build_table(zmax, keep=()):
    PR = primes_upto(max(zmax + 10, 60))
    y = np.exp(X)
    F = np.where(y < 2 ** 53, np.floor(y) / np.maximum(y, 1e-300), 1.0)
    snaps, theta = {}, 0.0
    for p in PR:
        if p > zmax: break
        F = F - np.interp(X - LN(p), X, F, left=0.0) / p
        theta += LN(p)
        if p in keep:
            snaps[p] = (F.copy(), theta)
    snaps.setdefault(zmax if zmax in keep else max(keep, default=zmax),
                     (F, theta)) if keep else snaps.setdefault(zmax, (F, theta))
    if zmax not in snaps: snaps[zmax] = (F, theta)
    return snaps


def Ftab(snaps, z, lam):
    return float(np.interp(lam, X, snaps[z][0]))


def phi_exact(G, z, retarget=None):
    alive = np.ones(G + 1, dtype=bool); alive[0] = False
    rt = retarget or {}
    for p in primes_upto(z):
        c = rt.get(p, 0)
        alive[c if c else p::p] = False
    return int(alive.sum())


def D_exact(G, z):
    d = phi_exact(G, z); a = 1
    while G >> a >= 1:
        d -= phi_exact(G >> a, z); a += 1
    return d


def A_op(Fz, p):
    out = np.zeros_like(Fz); a = 1
    while a * LN(p) < XMAX:
        out += np.interp(X - a * LN(p), X, Fz, left=0.0) * p ** (-a)
        a += 1
    return out


def stack_arrays(snaps, z, maxd):
    """Cumulative stack survivor-density arrays for depths 1..maxd."""
    cur = snaps[z][0]; arrs = []
    for p in STACK_PRIMES[:maxd]:
        cur = ((p - 2) / (p - 1)) * cur + A_op(cur, p)
        arrs.append(cur)
    return arrs


def window_edges(snaps, z):
    Fz = snaps[z][0]
    tow = A_op(Fz, 2)
    us = np.arange(2.02, 3.40, 0.002)
    lam = us * LN(z)
    r = np.interp(lam, X, tow) / np.interp(lam, X, Fz)
    below = r < 1.0
    on = off = None
    for i in range(1, len(us)):
        if below[i] and not below[i - 1] and on is None:
            f = (1 - r[i - 1]) / (r[i] - r[i - 1]); on = us[i - 1] + f * 0.002
        if on is not None and not below[i] and below[i - 1]:
            f = (1 - r[i - 1]) / (r[i] - r[i - 1]); off = us[i - 1] + f * 0.002
            break
    return on, off


def theta_and_zd(D):
    """livefire build_base rule: add primes while theta < (D-8)*ln10."""
    target = (D - 8) * LN(10)
    theta, zd = 0.0, 0
    for p in primes_upto(int(2.6 * D * LN(10)) + 100):
        if theta >= target: break
        theta += LN(p); zd = p
    return zd, theta


def theta_of(z):
    return sum(LN(p) for p in primes_upto(z))


# ----------------------------------------------------------------- commands
def cmd_umap(a):
    if a.zd:
        zd, th = a.zd, theta_of(a.zd)
        src = "user-specified"
    else:
        zd, th = theta_and_zd(a.D)
        src = "campaign theta rule"
    G = a.gap if a.gap else a.merit * a.D * LN(10)
    u = LN(G) / LN(zd)
    print(f"D={a.D:,}  zd={zd:,} ({src})  theta(zd)={th:,.1f}  "
          f"G={G:,.0f}  ln G={LN(G):.2f}")
    print(f"u = ln G / ln zd = {u:.3f}")
    print(f"stride check theta(zd) >= ln G: "
          f"{'OK' if th >= LN(G) else 'VIOLATED (beacons not independent)'}")
    if zd < 389:
        print("regime: z BELOW the opening edge z0=389 (paper Rmk 23): the "
              "swap window is CLOSED here -- counterexamples throughout "
              "101<=z<=383, and price-sheet losses below that. Primorial "
              "stands; to use stacks move zd >= 389.")
        return
    if 2.0 <= u <= 3.35 and zd <= 20000:
        snaps = build_table(zd, keep=(zd,))
        on, off = window_edges(snaps, zd)
        if on is not None and off is not None and on <= u <= off:
            print(f"regime: SWAP WINDOW (exact edges at z={zd}: "
                  f"{on:.3f}..{off:.3f}) -- run: price --z {zd} --u {u:.2f}")
        else:
            edge = (f"{on:.3f}..{off:.3f}" if on is not None and off is not None
                    else "not found on scan grid")
            print(f"regime: OUTSIDE window at this z (exact edges: {edge}) -- "
                  "primorial locally optimal; adjust u or zd.")
    elif u < 2.3:
        print("regime: BELOW window -- primorial locally optimal; every "
              "single-prime retarget loses (paper Thm-3 side). No design change.")
    elif u <= 3.1:
        print(f"regime: likely SWAP WINDOW -- confirm exact edges with: "
              f"window --z {zd}, then price --z {zd} --u {u:.2f}")
    else:
        print("regime: ABOVE window -- swap loses; shrink u or grow zd.")


def cmd_window(a):
    snaps = build_table(a.z, keep=(a.z,))
    on, off = window_edges(snaps, a.z)
    print(f"z={a.z}: u_on = {on:.3f}, u_off = {off:.3f}"
          + ("   (paper at 797: 2.341, 3.121)" if a.z == 797 else ""))


def cmd_price(a):
    t0 = time.time()
    snaps = build_table(a.z, keep=(a.z,))
    lam = a.u * LN(a.z); G = int(round(math.exp(lam)))
    base = Ftab(snaps, a.z, lam)
    arrs = stack_arrays(snaps, a.z, a.maxdepth)
    ratios = [float(np.interp(lam, X, ar)) / base for ar in arrs]
    do_exact = (G <= 2 * 10 ** 8) and not a.no_exact
    exact_base = phi_exact(G, a.z) if do_exact else None
    print(f"(z={a.z}, u={a.u})  G={G:,}  primorial density F={base:.6f}"
          + (f"  exact survivors={exact_base:,}" if do_exact else ""))
    best = int(np.argmin(ratios))
    for d, r in enumerate(ratios):
        T = STACK_PRIMES[:d + 1]
        line = f"  depth {d+1} T={tuple(T)}: model ratio {r:.4f}"
        if do_exact:
            ce = phi_exact(G, a.z, {p: 1 for p in T}) / exact_base
            line += f" | exact {ce:.4f}"
        line += f"  gain {100*(1-r):+.2f}%" + ("   <== optimal" if d == best else "")
        print(line)
    print(f"[{time.time()-t0:.0f}s]")


# ---------------------------------------------------------------------- gate
def gate():
    t0 = time.time(); npass = 0
    def ok(cond, msg):
        nonlocal npass
        print(("  pass: " if cond else "  FAIL: ") + msg)
        if not cond: sys.exit(1)
        npass += 1

    keep = (29, 31, 37, 41, 47, 53, 61, 101, 331, 797, 1601)
    snaps = build_table(3203, keep)
    print(f"table built: {len(X):,} grid points, primes<=3203  [{time.time()-t0:.0f}s]")

    print("[W] wall identity")
    for z in (29, 31, 37, 41, 47, 53):
        mert = 1.0
        for p in primes_upto(z): mert *= (1 - 1 / p)
        r = Ftab(snaps, z, snaps[z][1]) / mert
        ok(abs(r - 1) < 2e-3, f"W z={z}: r_wall = {r:.5f} (paper: 1.0000)")

    print("[T1] table density vs exact sieve")
    for z, u in [(61, 2.5), (61, 3.0), (61, 3.5), (61, 4.0), (101, 2.5),
                 (101, 3.0), (331, 2.5), (331, 3.0), (797, 2.5), (1601, 2.5)]:
        G = int(z ** u)
        ratio = Ftab(snaps, z, LN(G)) * G / phi_exact(G, z)
        ok(0.996 < ratio < 1.004, f"T1 (z={z}, u={u}): ratio = {ratio:.4f} "
                                  f"(paper band 0.9992-1.0009)")

    print("[T2] stack rows at (797, 2.8): constructed vs operator model")
    z, u = 797, 2.8
    G = int(z ** u); lam = LN(G)
    base = phi_exact(G, z); Fb = Ftab(snaps, z, lam)
    arrs = stack_arrays(snaps, z, 3)
    for (T, (pc, pm)), ar in zip(
            {(2,): (0.9869, 0.9872), (2, 3): (0.9791, 0.9796),
             (2, 3, 5): (0.9791, 0.9795)}.items(), arrs):
        cons = phi_exact(G, z, {p: 1 for p in T}) / base
        modl = float(np.interp(lam, X, ar)) / Fb
        ok(abs(cons - pc) < 1.5e-3 and abs(modl - pm) < 1.5e-3,
           f"T2 T={T}: constructed {cons:.4f} (paper {pc}), "
           f"model {modl:.4f} (paper {pm})")

    print("[TH] Theorem-3 exact integer anchors")
    d1 = D_exact(1646116, 389)
    ok(d1 == 42, f"TH D(1646116, 389) = {d1} (paper: 42, the range minimum)")
    d2 = D_exact(1588478, 383)
    ok(d2 == -5, f"TH D(1588478, 383) = {d2} (paper: -5, the sharp violator)")

    print("[SW] swap window signs at z=797")
    for uu in (2.4, 2.5, 2.7):
        G = int(797 ** uu); d = D_exact(G, 797)
        ok(d > 0, f"SW u={uu}: D = {d} > 0 (in Theorem box)")
    G32 = int(797 ** 3.2); lam32 = LN(G32)
    tow = float(np.interp(lam32, X, A_op(snaps[797][0], 2)))
    r32 = tow / Ftab(snaps, 797, lam32)
    ok(r32 > 0.9995, f"SW u=3.2: 2-swap ratio = {r32:.4f} "
                     f"(paper: 1.0002, swap loses past the window)")

    print("[WE] window edges at z=797 (paper: 2.341, 3.121)")
    on, off = window_edges(snaps, 797)
    ok(abs(on - 2.341) < 0.02, f"WE u_on = {on:.3f}")
    ok(3.02 < off < 3.20, f"WE u_off = {off:.3f} (shallow crossing)")

    print("[DP] optimal stack depth at (797, 3.0) (paper Table 3: depth 4)")
    lam30 = 3.0 * LN(797); b30 = Ftab(snaps, 797, lam30)
    rs = [float(np.interp(lam30, X, ar)) / b30
          for ar in stack_arrays(snaps, 797, 6)]
    ok(int(np.argmin(rs)) + 1 == 4 and abs(rs[3] - 0.9851) < 2e-3,
       f"DP argmin depth = {int(np.argmin(rs))+1}, ratio {rs[3]:.4f} "
       f"(paper model 0.9851)")

    print(f"\nSWAP INSTRUMENT v0: ALL CHECKS PASS -- {npass} checks "
          f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    pu = sub.add_parser("umap"); pu.add_argument("--D", type=int, required=True)
    pu.add_argument("--merit", type=float, default=None)
    pu.add_argument("--gap", type=float, default=None)
    pu.add_argument("--zd", type=int, default=None)
    pw = sub.add_parser("window"); pw.add_argument("--z", type=int, required=True)
    pp = sub.add_parser("price"); pp.add_argument("--z", type=int, required=True)
    pp.add_argument("--u", type=float, required=True)
    pp.add_argument("--maxdepth", type=int, default=6)
    pp.add_argument("--no-exact", action="store_true")
    a = ap.parse_args()
    if a.cmd == "umap":
        if a.merit is None and a.gap is None:
            sys.exit("umap needs --merit or --gap")
        cmd_umap(a)
    elif a.cmd == "window": cmd_window(a)
    elif a.cmd == "price": cmd_price(a)
    else: gate()
