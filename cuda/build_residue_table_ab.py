#!/usr/bin/env python3
"""build_residue_table_ab -- P2 shared table builder + --zd-override (AB-window).

Identical to build_residue_table.py except the primorial may be overridden:
with --zd-override Z the base is P#(Z) and deep primes are (Z, z]. Output
schema unchanged (meta/primes.npy/resid.npy); livefire_gw's open_table
asserts meta zdesign == its own override. Window tables build FASTER than
desert tables (residues of a ~150-digit P instead of a ~22.5k-digit one).

Usage (vast box):
  python3 build_residue_table_ab.py --digits 9800 --z 1e9 --zd-override 349 \
      --out ../table_98w_1e9 --procs 64
"""
import argparse, json, math, os, sys, time
try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass
import multiprocessing as mp
import numpy as np

try:
    import gmpy2
    MPZ = gmpy2.mpz
except ImportError:
    MPZ = int


def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)


def build_base(D, zdo=None):
    """IDENTICAL to livefire_gw.build_base (and to m1a's when zdo is None)."""
    limit = int(2.6 * D * math.log(10))
    pr = primes_upto(limit)
    if zdo is not None:
        used = [int(p) for p in pr[pr <= zdo]]
        P = MPZ(1)
        for p in used: P *= p
        return P, int(used[-1]), used
    P = MPZ(1); zd = 0; used = []
    target = (D - 8) * math.log(10); theta = 0.0
    for p in pr:
        if theta >= target: break
        P *= int(p); theta += math.log(p); zd = int(p); used.append(int(p))
    return P, zd, used


_P = None
def _init(pstr):
    global _P
    _P = MPZ(pstr)


def _chunk_mod(args):
    lo, hi, primes = args
    return lo, np.array([int(_P % int(p)) for p in primes], dtype=np.int64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--z", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--zd-override", type=int, default=None)
    a = ap.parse_args()
    z = int(a.z)
    t0 = time.time()

    print(f"building base primorial for D={a.digits:,}"
          + (f" (zd-override {a.zd_override})" if a.zd_override else "")
          + " ...", flush=True)
    P, zd, used = build_base(a.digits, a.zd_override)
    print(f"  zdesign={zd:,} ({len(used):,} design primes, "
          f"P has {len(str(P)):,} digits)  [{time.time()-t0:.0f}s]", flush=True)

    print(f"sieving primes to z={z:.0e} ...", flush=True)
    pr = primes_upto(z)
    deep = pr[pr > zd]
    del pr
    print(f"  {len(deep):,} deep primes  [{time.time()-t0:.0f}s]", flush=True)

    print(f"residues P mod p on {a.procs} procs ...", flush=True)
    resid = np.empty(len(deep), dtype=np.int64)
    CH = 200_000
    jobs = [(i, min(i + CH, len(deep)), deep[i:i + CH])
            for i in range(0, len(deep), CH)]
    with mp.Pool(a.procs, initializer=_init, initargs=(str(P),)) as pool:
        for lo, arr in pool.imap_unordered(_chunk_mod, jobs, chunksize=1):
            resid[lo:lo + len(arr)] = arr
    print(f"  residues done  [{time.time()-t0:.0f}s]", flush=True)

    os.makedirs(a.out, exist_ok=True)
    np.save(os.path.join(a.out, "primes.npy"), deep)
    np.save(os.path.join(a.out, "resid.npy"), resid)
    meta = dict(schema=1, D=a.digits, zdesign=zd, z=z, n_deep=int(len(deep)),
                p_digits=len(str(P)), built_ts=int(time.time()),
                zd_override=bool(a.zd_override))
    tmp = os.path.join(a.out, "meta.json.tmp")
    json.dump(meta, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(a.out, "meta.json"))
    sz = sum(os.path.getsize(os.path.join(a.out, f))
             for f in ("primes.npy", "resid.npy"))
    print(f"table -> {a.out}  ({sz/1e6:.0f} MB)  [{time.time()-t0:.0f}s total]")


if __name__ == "__main__":
    main()
