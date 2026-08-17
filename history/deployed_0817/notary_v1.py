#!/usr/bin/env python3
"""BEACON notary v1 -- independent re-verification of a logged gap find.

Doctrine: the notary never trusts the hunter. Everything is rebuilt from the
reconstruction tuple (k, zdesign, jleft, jright): fresh primorial, fresh
residues, fresh sieve, fresh arithmetic. Verification demands:
  1. p1 = k*P#(zd) + jleft  is PRP (strong bases 2,3,5,7,11,13 + GMP is_prime)
  2. p2 = k*P#(zd) + jright is PRP (same battery)
  3. EVERY interior integer is proven composite: an explicit sieve factor,
     or a failed base-2 Fermat test (deterministic compositeness proof).
Any interior survivor that tests PRP => verdict INVALID.

Usage:
  python3 notary_v1.py --log w7/livefire_log.csv --gap 131072 [--z 1e9]
  python3 notary_v1.py --k 4801994 --zd 6977 --jl -1 --jr 9743 [--z 1e8]

Output: human summary + notary_cert_gap<G>.json  (handle: djuk8)
"""
import argparse, csv, json, math, os, sys, time
import numpy as np, gmpy2

try:                       # catch #2: py>=3.11 caps int<->str at 4300 digits;
    sys.set_int_max_str_digits(2_000_000)   # window-arm k is ~9,655 digits
except AttributeError:
    pass

BASES = [2, 3, 5, 7, 11, 13]

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log"); ap.add_argument("--gap", type=int)
    ap.add_argument("--k", type=int)
    ap.add_argument("--k-file", help="file holding k (safer for big k: no "
                                     "9,000-digit argv, no shell limits)")
    ap.add_argument("--token", help="reconstruction token e.g. s5101t2864; "
                                    "recorded in the certificate")
    ap.add_argument("--parse-only", action="store_true",
                    help="reconstruct + report, then exit (seconds, not hours)")
    ap.add_argument("--zd", type=int)
    ap.add_argument("--jl", type=int); ap.add_argument("--jr", type=int)
    ap.add_argument("--z", type=float, default=1e9, help="verification sieve depth")
    ap.add_argument("--mr", type=int, default=50, help="Miller-Rabin rounds on endpoints")
    a = ap.parse_args()

    if a.log:
        row = next(r for r in csv.DictReader(open(a.log)) if int(r["gap"]) == a.gap)
        k, zd, jl, jr = int(row["k"]), int(row["zdesign"]), int(row["jleft"]), int(row["jright"])
    else:
        if a.k_file:
            a.k = int(open(a.k_file).read().split()[0])
        if a.k is None:
            raise SystemExit("need --k, --k-file, or --log/--gap")
        k, zd, jl, jr = a.k, a.zd, a.jl, a.jr
    z = int(a.z); t0 = time.time()

    # fresh reconstruction
    design = primes_upto(zd)
    P = gmpy2.mpz(1)
    for p in design: P *= int(p)
    n0 = int(k) * P
    D = n0.num_digits(10)
    gap = jr - jl
    merit = gap / float(gmpy2.log(n0))
    kd = len(gmpy2.digits(gmpy2.mpz(k), 10))
    ktag = a.token or (f"{k}" if kd <= 20 else f"<{kd}-digit k>")
    print(f"reconstructed n0 = {ktag} * P#({zd:,})  [{D:,} digits]  "
          f"gap {gap:,}  merit {merit:.4f}")
    if a.parse_only:
        print(f"PARSE-ONLY: k has {kd} digits, n0 {D:,} digits, "
              f"gap {gap:,}, merit {merit:.6f}  (no verification run)")
        return

    # 1+2: endpoints
    ends = {}
    ok_ends = True
    for name, j in (("p1", jl), ("p2", jr)):
        cand = n0 + j
        fer = {b: gmpy2.powmod(b, cand - 1, cand) == 1 for b in BASES}
        strong = bool(gmpy2.is_prime(cand, a.mr))
        ends[name] = {"offset": j, "digits": cand.num_digits(10),
                      "fermat_bases_pass": all(fer.values()), "is_prime_mr": strong}
        ok_ends &= all(fer.values()) and strong
        print(f"  {name} = n0 {'+' if j>=0 else '-'} {abs(j):,}: "
              f"fermat[{','.join(map(str,BASES))}] {'PASS' if all(fer.values()) else 'FAIL'}, "
              f"is_prime({a.mr}) {'PASS' if strong else 'FAIL'}")

    # 3: interior, rebuilt from scratch
    lo, n_int = jl + 1, gap - 1                     # offsets jl+1 .. jr-1
    alive = np.ones(n_int, dtype=bool)
    for q in design:                                 # design factors: q | n0 and q | j
        start = (-lo) % q
        alive[start::q] = False
    deep = primes_upto(z); deep = deep[deep > zd]
    rP = np.empty(len(deep), dtype=np.int64)
    for i in range(len(deep)):                       # fresh residues, independent pass
        rP[i] = int(P % int(deep[i]))
    # n0 mod p. Desert finds have k ~ 10^7 (fits int64, vectorized). Window
    # finds have k ~ 10^9,655 -- numpy cannot hold it, so reduce k modulo each
    # prime first (catch #3, found by the first window-arm certification).
    if int(k).bit_length() > 62:
        K = gmpy2.mpz(k)
        print(f"  big-k path: reducing a {len(gmpy2.digits(K, 10)):,}-digit k "
              f"modulo {len(deep):,} primes ...", flush=True)
        _t = time.time()
        kr = np.fromiter((int(K % int(p)) for p in deep),
                         dtype=np.int64, count=len(deep))
        r0 = (kr * rP) % deep                        # both < p <= z, product fits
        print(f"    reduced [{time.time()-_t:.0f}s]", flush=True)
    else:
        r0 = (k * rP) % deep                         # n0 mod p
    lo_r = (r0 + lo) % deep                          # (n0 + lo) mod p
    first = (deep - lo_r) % deep                     # first index with p | n0+j
    med = deep < n_int
    for p, f in zip(deep[med], first[med]):
        alive[f::p] = False
    hit = first[~med] < n_int
    alive[first[~med][hit]] = False
    surv = np.flatnonzero(alive) + lo
    print(f"  interior: {n_int:,} integers | sieve({z:.0e}) factored {n_int - len(surv):,} "
          f"| {len(surv):,} survivors to test")

    fermat_comp = pseudo = 0; alarms = []
    for j in surv:
        cand = n0 + int(j)
        if gmpy2.powmod(2, cand - 1, cand) != 1:
            fermat_comp += 1                         # deterministic composite
        elif not gmpy2.is_prime(cand, a.mr):
            pseudo += 1                              # Fermat-2 pseudoprime, still composite
        else:
            alarms.append(int(j))                    # interior PRP => gap is FALSE

    valid = ok_ends and not alarms
    dt = time.time() - t0
    verdict = "VALID" if valid else "INVALID"
    print(f"  interior composite proofs: {n_int - len(surv):,} factored, "
          f"{fermat_comp:,} fermat-fail, {pseudo} pseudoprime")
    if alarms:
        print(f"  *** ALARM: interior PRP at offsets {alarms} -- GAP IS FALSE ***")
    print(f"VERDICT: {verdict}   ({dt:.0f}s)")

    cert = {"handle": "djuk8", "verdict": verdict, "k": k, "zdesign": zd,
            "token": a.token, "k_digits": kd,
            "jleft": jl, "jright": jr, "gap": gap, "merit": round(merit, 6),
            "n0_digits": D, "endpoints": ends,
            "interior": {"count": n_int, "sieve_factored": int(n_int - len(surv)),
                         "fermat_composite": fermat_comp, "pseudoprimes": pseudo,
                         "prp_alarms": alarms},
            "z_verify": z, "mr_rounds": a.mr, "runtime_s": round(dt, 1),
            "ts": int(time.time()), "notary": "beacon-notary-v1"}
    fn = f"notary_cert_gap{gap}.json"
    json.dump(cert, open(fn, "w"), indent=1)
    print(f"certificate -> {fn}")

if __name__ == "__main__":
    main()
