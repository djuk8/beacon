#!/usr/bin/env python3
"""BEACON make_blob3 -- paired blob generator for the kernel-v3 gate.

Emits, from ONE config, both blob formats so kernel2 and kernel3 screen the
IDENTICAL anchor family:
  blob v2 (kernel2): np | pd[np] | pm[np] | R0[np] | W | wv[0..W] (f64)
  blob v3 (kernel3): np | pd[np] | pm[np] | R0[np] | W | ntgt | tgt[ntgt] | tw[ntgt]
Contract: 0 < pm < p, 0 <= R0 < p, gcd(pm,p)=1, targets strictly ascending in
[1,W], tw[j] = wv[tgt[j]] and wv is zero off-target (post-sweep-v3 production
shape: score support = target window only).

Cases:
  real   -- D-digit primorial family, targets = prime offsets in (zd, G/2],
            W = 10L (kernel2 walks the full window; that IS the dead work).
  adv_*  -- adversarial synthetics for the zero-tolerance gate.
"""
import argparse, json, math, random
import numpy as np

LN10 = math.log(10)

def sieve(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def write_b2(path, pd, pm, R0, W, wv):
    with open(path, "wb") as f:
        np.array([len(pd)], np.int64).tofile(f)
        pd.astype(np.int64).tofile(f); pm.astype(np.int64).tofile(f)
        R0.astype(np.int64).tofile(f)
        np.array([W], np.int64).tofile(f)
        wv.astype(np.float64).tofile(f)

def write_b3(path, pd, pm, R0, W, tgt, tw):
    with open(path, "wb") as f:
        np.array([len(pd)], np.int64).tofile(f)
        pd.astype(np.int64).tofile(f); pm.astype(np.int64).tofile(f)
        R0.astype(np.int64).tofile(f)
        np.array([W, len(tgt)], np.int64).tofile(f)
        tgt.astype(np.int64).tofile(f); tw.astype(np.float64).tofile(f)

def emit(prefix, pd, pm, R0, W, tgt, tw, meta):
    assert np.all(pd > 1) and np.all((pm > 0) & (pm < pd)) and np.all((R0 >= 0) & (R0 < pd))
    assert np.all(np.diff(tgt) > 0) and tgt[0] >= 1 and tgt[-1] <= W
    from math import gcd
    for p, m in zip(pd.tolist(), pm.tolist()):
        assert gcd(p, m) == 1, (p, m)
    wv = np.zeros(W + 1)
    wv[tgt] = tw
    write_b2(prefix + ".b2", pd, pm, R0, W, wv)
    write_b3(prefix + ".b3", pd, pm, R0, W, tgt, tw)
    meta.update(dict(np=int(len(pd)), W=int(W), ntgt=int(len(tgt)),
                     pmax=int(pd.max()), tw_sum=float(tw.sum())))
    json.dump(meta, open(prefix + ".json", "w"), indent=1)
    print(f"  {prefix}: np={len(pd):,} W={W:,} ntgt={len(tgt)} pmax={pd.max():,}")

def weights_for(mode, n, rng):
    if mode == "ones":  return np.ones(n)
    if mode == "randint": return rng.integers(1, 1000, n).astype(np.float64)
    if mode == "frac":  return rng.uniform(0.1, 2.0, n)
    raise SystemExit("weights: ones|randint|frac")

def case_real(prefix, D, zs, merit, seed, wmode):
    PR = sieve(zs)
    cum = np.cumsum(np.log(PR.astype(float)))
    i0 = int(np.searchsorted(cum, (D - 8) * LN10))
    zd = int(PR[i0 - 1]) if cum[i0] > (D - 8) * LN10 else int(PR[i0])
    design = PR[PR <= zd]; scr = PR[(PR > zd) & (PR <= zs)]
    P = 1
    for q in design: P *= int(q)
    rng = random.Random(seed); k0 = rng.randrange(10 ** 6, 10 ** 7)
    pm = np.array([P % int(p) for p in scr], np.int64)
    R0 = np.array([(k0 * int(m)) % int(p) for m, p in zip(pm, scr)], np.int64)
    L = D * LN10; W = int(10 * L); half = int(merit * L) // 2
    tgt = PR[(PR > zd) & (PR <= half)].astype(np.int64)
    nrng = np.random.default_rng(seed)
    tw = weights_for(wmode, len(tgt), nrng)
    emit(prefix, scr, pm, R0, W, tgt, tw,
         dict(case="real", D=D, zs=zs, merit=merit, seed=seed, k0=k0, zd=zd,
              weights=wmode))

def case_adv(prefix, name, seed):
    rng = np.random.default_rng(seed)
    if name == "adv_small":          # tiny primes incl 2, zero residues, pm=1/p-1
        pd = np.array([2, 3, 5, 7, 11, 13, 17, 19], np.int64)
        pm = np.array([1, 2, 1, 6, 10, 1, 12, 18], np.int64)
        R0 = np.array([0, 0, 4, 0, 1, 12, 16, 0], np.int64)
        W = 23
        tgt = np.array([1, 2, 3, 5, 7, 11, 13, 17, 19, 22, 23], np.int64)
        tw = weights_for("randint", len(tgt), rng)
    elif name == "adv_bigp":         # every prime >> K: skip / single-hit paths
        PR = sieve(5000); pd = PR[(PR > 101)]
        pm = (rng.integers(1, 1 << 30, len(pd)) % (pd - 1)) + 1
        R0 = rng.integers(0, 1 << 30, len(pd)) % pd
        W = 200
        tgt = np.unique(rng.integers(1, W + 1, 40)).astype(np.int64)
        tw = weights_for("randint", len(tgt), rng)
    elif name == "adv_edge":         # residues forcing t0=0 and h ≡ 0 (mod p)
        pd = np.array([3, 5, 7, 11, 101, 997], np.int64)
        pm = np.array([2, 4, 3, 10, 100, 996], np.int64)
        R0 = np.array([2, 4, 6, 10, 100, 996], np.int64)
        W = 1010
        tgt = np.array([1, 3, 5, 7, 11, 33, 101, 202, 505, 997, 1010], np.int64)
        tw = weights_for("frac", len(tgt), rng)
    else:
        raise SystemExit("unknown adversarial case " + name)
    from math import gcd
    keep = np.array([gcd(int(p), int(m)) == 1 for p, m in zip(pd, pm)])
    pd, pm, R0 = pd[keep], pm[keep], R0[keep]
    emit(prefix, pd, pm, R0, W, tgt, tw, dict(case=name, seed=seed))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--digits", type=int, default=400)
    ap.add_argument("--zs", type=int, default=10 ** 6)
    ap.add_argument("--merit", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--weights", default="ones")
    a = ap.parse_args()
    if a.case == "real":
        case_real(a.out, a.digits, a.zs, a.merit, a.seed, a.weights)
    else:
        case_adv(a.out, a.case, a.seed)
