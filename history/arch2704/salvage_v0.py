#!/usr/bin/env python3
"""salvage_v0.py -- harvest realized gaps from ring-5 casualties.
Every k that reaches ring 5 has a certified prime-free core of +/-77,524
(campaign rounds 1-4); the ring-5 prime that killed it usually lands on
ONE side, leaving the other side's fence far out. This walks the true
fences and banks the realized gap. Zero GPU; ~1-2 core-min per k.

  python3 salvage_v0.py            # scan hunt_s*/sc_r05_*.manifest.json
  python3 salvage_v0.py --span 220000
Outputs: salvage_finds.log + one find_salvage_*.txt per k (all gaps
reported; find files for gap >= --floor, default 155,000).
NOTE: the +/-77,524 core rests on campaign fold certification; the
portal notary independently re-proves endpoints AND re-sieves the full
interior at submission, so salvage claims get the same referee as any
find. Freeze discipline: this BANKS, it does not submit.
"""
import argparse, glob, json, math, time, sys
import numpy as np, gmpy2
sys.set_int_max_str_digits(2000000)

def primes_upto(n):
    s = np.ones(n+1, dtype=bool); s[:2] = False
    for i in range(2, int(n**.5)+1):
        if s[i]: s[i*i::i] = False
    return np.nonzero(s)[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--span", type=int, default=200000)
    ap.add_argument("--floor", type=int, default=155000)
    ap.add_argument("--glob", default="hunt_s*/sc_r05_*.manifest.json")
    a = ap.parse_args()
    mans = sorted(glob.glob(a.glob))
    if not mans:
        print("no ring-5 manifests found"); return
    done = set()
    try:
        for ln in open("salvage_finds.log"):
            done.add(int(ln.split()[2]))
    except FileNotFoundError:
        pass
    import os
    os.makedirs("salvaged", exist_ok=True)
    cfg = json.load(open(mans[0]))["cfg"]
    zd, d, core = cfg["zd"], cfg["d"], cfg["edges"][-2]
    print(f"salvage: {len(mans)} manifests, config zd={zd} d={d} "
          f"core +/-{core}, span +/-{a.span}")
    prs = primes_upto(10**6)
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p <= zd: P *= p; p = gmpy2.next_prime(p)
    P_eff = P//d
    PEm = np.array([int(P_eff % int(q)) for q in prs], dtype=np.int64)
    out = []
    for mf in mans:
        man = json.load(open(mf))
        pending = [k for k in man["ks"] if k not in done]
        if not pending:
            os.rename(mf, "salvaged/" + os.path.basename(mf))
            continue
        for k in pending:
            done.add(k)
            t0 = time.time()
            n0 = gmpy2.mpz(k)*P_eff
            ln = float(gmpy2.log(n0))
            n0m = (k % prs)*PEm % prs
            S = a.span
            js = np.arange(-S, S+1, dtype=np.int64)
            alive = np.ones(len(js), dtype=bool)
            par = int(n0 % 2)
            alive[(js % 2) != (0 if par else 1)] = False
            W = 2*S+1; small = prs[prs <= W]
            for i in range(1, len(small)):
                q = int(small[i]); j0 = (-int(n0m[i])) % q
                st = -S+((j0-(-S)) % q); alive[st+S::q] = False
            big = prs[len(small):]; m = n0m[len(small):]
            j0 = (-m) % big
            st = -S+((j0-(-S)) % big); ok = st <= S
            alive[(st[ok]+S).astype(np.int64)] = False
            idx = np.nonzero(alive)[0]-S
            def walk(sign):
                side = idx[idx > core] if sign > 0 else -idx[idx < -core]
                side.sort()
                for x in side:
                    j = int(x)*sign; n = n0+j
                    if gmpy2.powmod(2, n-1, n) == 1 and gmpy2.is_prime(n, 25):
                        return j
                return None
            jr = walk(+1); jl = walk(-1)
            if jr is None or jl is None:
                print(f"k={k}: fence beyond span (RECORD-CLASS?) -- "
                      f"rerun with --span {a.span+100000}"); continue
            gap = jr-jl; merit = gap/ln
            line = (f"k={k}: GAP {gap:,} merit {merit:.4f} "
                    f"(jl {jl} jr {jr}) [{time.time()-t0:.0f}s]")
            print(line); out.append((gap, merit, k, jl, jr))
            if gap >= a.floor:
                with open(f"find_salvage_D2702_g{gap}.txt", "w") as f:
                    f.write(f"gap {gap} merit {merit:.6f} k={k} zd={zd} "
                            f"d={d} jl={jl} jr={jr} core_certified={core} "
                            f"channel=salvage\n")
        os.rename(mf, "salvaged/" + os.path.basename(mf))
    out.sort(reverse=True)
    with open("salvage_finds.log", "a") as f:
        for gap, merit, k, jl, jr in out:
            f.write(f"{gap} {merit:.4f} {k} {jl} {jr}\n")
    print(f"\n{len(out)} salvaged; largest: "
          + (f"{out[0][0]:,} @ {out[0][1]:.4f}" if out else "none"))

if __name__ == "__main__":
    main()
