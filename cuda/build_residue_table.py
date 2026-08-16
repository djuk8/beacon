#!/usr/bin/env python3
"""BEACON build_residue_table -- P2 shared residue table, built ONCE per (D, z).

Replaces the per-worker deep-sieve prep in livefire_m1a.py (each of 60 hunters
sieving primes to z and computing P mod p independently: ~3 GB/worker peak,
180 GB fleet-wide) with one build shared read-only via mmap (~0.8 GB total at
z=1e9). Workers open it with np.load(mmap_mode='r'); the kernel page cache
dedups across all processes.

Output directory:
  primes.npy  int64, deep primes p with zdesign < p <= z, ascending
  resid.npy   int64, P#(zdesign) mod p, aligned with primes.npy
  meta.json   {schema, D, zdesign, z, n_deep, p_digits, built_ts}

Usage (shredder, once):
  python3 build_residue_table.py --digits 24000 --z 1e9 --out table_24k_1e9 --procs 60
"""
import argparse, json, math, os, time
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

def build_base(D):
    """IDENTICAL to livefire_m1a.build_base -- zdesign must match the hunter."""
    limit = int(2.6 * D * math.log(10))
    pr = primes_upto(limit)
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
    a = ap.parse_args()
    z = int(a.z)
    t0 = time.time()

    print(f"building base primorial for D={a.digits:,} ...", flush=True)
    P, zd, used = build_base(a.digits)
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
                p_digits=len(str(P)), built_ts=int(time.time()))
    tmp = os.path.join(a.out, "meta.json.tmp")
    json.dump(meta, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(a.out, "meta.json"))
    sz = sum(os.path.getsize(os.path.join(a.out, f))
             for f in ("primes.npy", "resid.npy"))
    print(f"table -> {a.out}  ({sz/1e6:.0f} MB, shared by all workers via mmap)"
          f"  [{time.time()-t0:.0f}s total]")

if __name__ == "__main__":
    main()
