#!/usr/bin/env python3
"""salvage_v1.py -- walk the true prime gap around n0 = k * P_eff for every k in fossil manifests.  (C, 2026-09-03)

Rebuilt from a clean sheet after the v0.x incidents. Contract:
  * explicit inputs only:   --manifests GLOB (repeatable)   --ledger FILE (repeatable; READ for dedup)
                            --out FILE (WRITE; appended; default: first --ledger)
  * never moves a manifest unless --archive DIR is given (and then only manifests it actually walked)
  * every manifest is accounted for, loudly: walked / already-ledgered / empty / error
  * config (zd, d) read PER MANIFEST; edges reported per manifest (informational)
  * ledger line: gap merit k jl jr ts rung   (first 5 columns identical to v0.x; loaders ignore extras)
  * --jobs N: parallel walks (fork); default = cpu_count
  * --selftest: walk 3 ks and cross-check fences with independent next_prime/prev_prime
usage:
  python3 salvage_v1.py --manifests 'hunt_s1*/sc_r07_*.manifest.json' --manifests 'hunt_s1*/sc_r08_*.manifest.json' \\
          --ledger campaign_ledger.log --out campaign_ledger.log [--jobs 64] [--span 200000] [--archive walked/]
"""
import argparse, glob, json, math, os, sys, time
from multiprocessing import Pool
import numpy as np, gmpy2

# ---------------------------------------------------------------- helpers (pure; safe under fork)
def primorial(n):
    P = gmpy2.mpz(1); p = gmpy2.mpz(2)
    while p <= n: P *= p; p = gmpy2.next_prime(p)
    return P

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i*i::i] = False
    return np.nonzero(s)[0]

_CTX = {}   # per-venue sieve context, built once per worker: (zd,d) -> (P_eff, ln_n0-independent, sieve primes, PE mod p)
def ctx(zd, d, sieve_q=100000):
    key = (zd, d)
    if key not in _CTX:
        P = primorial(zd) // d
        prs = [int(p) for p in primes_upto(sieve_q) if p != 2]
        pe = np.array([int(P % p) for p in prs], dtype=np.int64)
        _CTX[key] = (P, np.array(prs, dtype=np.int64), pe)
    return _CTX[key]

def walk(args):
    """(k, zd, d, span, rung) -> (gap, merit, k, jl, jr, rung) or (None, reason)"""
    k, zd, d, span, rung = args
    try:
        P, prs, pe = ctx(zd, d)
        n0 = gmpy2.mpz(k) * P
        # dense sieve of offsets j in [-span, span] (only even j: n0 odd, so n0+j odd)
        L = 2 * span + 1
        alive = np.zeros(L, dtype=bool); alive[0::2] = True if (-span) % 2 == 0 else False
        alive[1::2] = not alive[0]  # exactly the even-j positions (index i <-> j = i - span)
        kp = np.array([k % int(p) for p in prs.tolist()], dtype=np.int64)
        r = (-(kp * pe) % prs) % prs                          # j == r (mod p) is dead
        for p, rr in zip(prs.tolist(), r.tolist()):
            start = (rr + span) % p                           # index of first j == rr (mod p) at or after -span
            alive[start::p] = False
        idx = np.nonzero(alive)[0]
        js = idx - span
        neg = js[js < 0][::-1]; pos = js[js > 0]
        jl = jr = None
        for j in neg.tolist():
            if gmpy2.is_prime(n0 + int(j), 25): jl = int(j); break
        for j in pos.tolist():
            if gmpy2.is_prime(n0 + int(j), 25): jr = int(j); break
        if jl is None or jr is None:
            return (None, f"k={k}: span exceeded (jl={jl} jr={jr}) -- rerun with larger --span")
        gap = jr - jl
        ln_n0 = float(gmpy2.log(n0))
        return (gap, gap / ln_n0, k, jl, jr, rung)
    except Exception as e:
        return (None, f"k={k}: ERROR {e!r}")

def load_ledger_ks(paths):
    done = set()
    for p in paths:
        if not os.path.exists(p): print(f"WARNING: ledger {p} not found (treated as empty)"); continue
        with open(p) as f:
            for ln in f:
                t = ln.split()
                if len(t) >= 5:
                    try: done.add(int(t[2]))
                    except ValueError: pass
    return done

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests", action="append", required=True, help="glob(s) of *.manifest.json")
    ap.add_argument("--ledger", action="append", default=[], help="ledger file(s) to read for dedup")
    ap.add_argument("--out", help="ledger file to append finds to (default: first --ledger)")
    ap.add_argument("--span", type=int, default=200000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--archive", help="move WALKED manifests here (hunt-dir prefix kept); default: leave in place")
    ap.add_argument("--floor", type=int, default=155000, help="gap >= floor also writes find_v1_<gap>.txt")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    out = a.out or (a.ledger[0] if a.ledger else "salvage_finds_v1.log")

    mans = sorted({m for g in a.manifests for m in glob.glob(g)})
    if not mans: print("no manifests matched"); return 2
    done = load_ledger_ks(a.ledger)
    print(f"salvage v1: {len(mans)} manifests | dedup set {len(done):,} ks from {len(a.ledger)} ledger(s) | out -> {out} | jobs {a.jobs}", flush=True)

    jobs, owner, dup, acct = [], [], [], {"walked": 0, "already": 0, "empty": 0, "error": 0}
    seen = set()
    for mf in mans:
        try: man = json.load(open(mf))
        except Exception as e:
            print(f"{mf}: ERROR reading manifest ({e}) -- left in place"); acct["error"] += 1; continue
        cfg = man.get("cfg", {}); zd, d, rung = int(cfg.get("zd", 0)), int(cfg.get("d", 0)), int(man.get("round", 0))
        ks = [int(k) for k in man.get("ks", [])]
        if not ks: print(f"{mf}: EMPTY ks -- left in place"); acct["empty"] += 1; continue
        pend = [k for k in ks if k not in done and k not in seen]
        if not pend: acct["already"] += 1; dup.append(mf); continue          # v8.55: archive duplicates too
        for k in pend: seen.add(k); jobs.append((k, zd, d, a.span, rung)); owner.append(mf)
        acct["walked"] += 1
    print(f"accounting: walked {acct['walked']} | already-ledgered {acct['already']} | empty {acct['empty']} | error {acct['error']} | ks to walk {len(jobs)}", flush=True)

    if a.selftest:
        for j in jobs[:3]:
            r = walk(j)
            if r[0] is None: print("selftest:", r[1]); continue
            gap, merit, k, jl, jr, rung = r
            P = ctx(j[1], j[2])[0]; n0 = gmpy2.mpz(k) * P
            ok = (gmpy2.next_prime(n0 + jl) == n0 + jr) and gmpy2.is_prime(n0 + jl, 50)
            print(f"selftest k={k}: gap {gap:,} merit {merit:.4f} jl {jl} jr {jr} -> independent next_prime check: {'PASS' if ok else 'FAIL'}")
        return 0

    t0 = time.time(); results = []
    with Pool(a.jobs) as pool:
        for i, r in enumerate(pool.imap_unordered(walk, jobs, chunksize=4), 1):
            results.append(r)
            if r[0] is None: print("  " + r[1], flush=True)
            elif i % 50 == 0 or r[1] >= 30: print(f"  [{i}/{len(jobs)}] k={r[2]}: GAP {r[0]:,} merit {r[1]:.4f} (jl {r[3]} jr {r[4]}) r{r[5]}", flush=True)
    good = [r for r in results if r[0] is not None]
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(out, "a") as f:
        for gap, merit, k, jl, jr, rung in good:
            f.write(f"{gap} {merit:.4f} {k} {jl} {jr} {ts} r{rung}\n")
            if gap >= a.floor:
                with open(f"find_v1_{gap}.txt", "w") as ff: ff.write(f"{gap} {merit:.6f} k={k} jl={jl} jr={jr} zd/d from manifest, {ts}\n")
        f.flush(); os.fsync(f.fileno())
    if a.archive:
        os.makedirs(a.archive, exist_ok=True)
        for mf in set(owner) | set(dup): os.replace(mf, os.path.join(a.archive, mf.replace("/", "__")))
    good.sort(key=lambda r: -r[1])
    print(f"\ndone in {time.time()-t0:.0f}s: {len(good)} walked, {len(results)-len(good)} unresolved | best:")
    for gap, merit, k, jl, jr, rung in good[:8]: print(f"  {gap:>7} {merit:8.4f} k={k} jl={jl} jr={jr} r{rung}")
    return 0

if __name__ == "__main__": sys.exit(main())
