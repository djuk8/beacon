#!/usr/bin/env python3
"""rewalk.py -- rebuild prime-gap submission lines from k alone, for the crown venue n0 = k * 1439#/2310.
A gap is fully determined by its k: walk outward from n0 to the first probable prime on each side
(sieve by every prime up to 1e5, then 25-round Miller-Rabin via gmpy2) and print the form line
    gap merit k*1439#/2310-|jl|
If an expected merit is given, the line is checked against it (MISMATCH is printed loudly).
  python3 rewalk.py --selftest                  known answers incl. the 42.5192 record + GMP prev/next_prime cross-check
  python3 rewalk.py lost_finds.txt              file lines: k [expected_merit] [label...]; '#' starts a comment
  python3 rewalk.py 201504264571199 ...         k's on the command line
Options: --jobs N (default: all cores)  --span S (default 120000; the walk widens itself if needed)
Needs: python3 with numpy and gmpy2   (pip install numpy gmpy2)"""
import sys, os, math, time, argparse
from multiprocessing import Pool
import numpy as np, gmpy2

Q = 100_000
_C = {}
def ctx():
    if not _C:
        P = gmpy2.mpz(1); p = gmpy2.mpz(2)
        while p <= 1439: P *= p; p = gmpy2.next_prime(p)
        P //= 2310
        s = np.ones(Q + 1, bool); s[:2] = False
        for i in range(2, int(Q ** .5) + 1):
            if s[i]: s[i * i::i] = False
        pr = np.flatnonzero(s).astype(np.int64)
        _C.update(P=P, pr=pr, pm=np.array([int(P % int(q)) for q in pr], np.int64))
    return _C

def walk(task):
    k, exp, label, span = task
    c = ctx(); P, pr, pm = c["P"], c["pr"], c["pm"]
    if k % 2 == 0 or math.gcd(k, 1155) != 1:
        return (k, None, f"k={k}: not a valid crown-venue k (must be odd and coprime to 3,5,7,11)", exp, label)
    n0 = gmpy2.mpz(k) * P; t0 = time.time()
    while True:
        r = (-(np.int64(k) % pr) * pm) % pr                     # n0 + j == 0 (mod p)  <=>  j == r (mod p)
        alive = np.ones(2 * span + 1, bool)                     # index i <-> offset j = i - span
        for q, rr in zip(pr.tolist(), r.tolist()):
            alive[(rr + span) % q::q] = False
        js = np.flatnonzero(alive) - span
        jl = next((int(j) for j in js[js < 0][::-1] if gmpy2.is_prime(n0 + int(j), 25)), None)
        jr = next((int(j) for j in js[js > 0] if gmpy2.is_prime(n0 + int(j), 25)), None)
        if jl is not None and jr is not None: break
        span *= 2                                               # gap wider than the span: widen and redo
    gap = jr - jl; merit = float(gap / gmpy2.log(n0 + jl))
    return (k, (gap, merit, jl, jr, time.time() - t0), None, exp, label)

def line(k, gap, merit, jl):
    return f"{gap} {merit:.4f} {k}*1439#/2310{jl:+d}"

def run(tasks, jobs):
    out, bad = [], 0
    with Pool(jobs, initializer=ctx) as pool:
        for k, res, err, exp, label in pool.imap_unordered(walk, tasks):
            if err: print("ERROR", err, flush=True); bad += 1; continue
            gap, merit, jl, jr, dt = res
            flag = ""
            if exp is not None:
                ok = abs(merit - exp) < 1.5e-4
                flag = "   ok" if ok else f"   MISMATCH: expected merit {exp:.4f}"; bad += (not ok)
            print(f"{line(k, gap, merit, jl):52}  jl {jl:+7d} jr {jr:+7d}  {dt:5.1f}s{flag}  {label}", flush=True)
            out.append((merit, gap, k, jl))
    return out, bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("items", nargs="*"); ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--span", type=int, default=120000); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        known = [(17440361647223, 42.5192, -21464, 38260, "the September record 59724"),
                 (17067099855263, 34.9078, -25226, 23806, "salvage_v1 selftest"),
                 (161038747121537, 32.3231, -20606, 24868, "box-2 harvest line"),
                 (29217524367931, 32.5317, -31012, 14700, "Japan-box harvest line")]
        _, bad = run([(k, m, lab, a.span) for k, m, _, _, lab in known], a.jobs)
        c = ctx(); n0 = gmpy2.mpz(known[0][0]) * c["P"]
        nx = int(gmpy2.next_prime(n0) - n0)
        try: pv = int(gmpy2.prev_prime(n0) - n0)
        except AttributeError: pv = None
        print(f"independent GMP check on the record: next_prime(n0) - n0 = {nx:+d} (want +38260)"
              + (f", prev_prime(n0) - n0 = {pv:+d} (want -21464)" if pv is not None else ", prev_prime not in this gmpy2 build"))
        bad += (nx != 38260) + (pv is not None and pv != -21464)
        print("SELFTEST", "PASSED" if bad == 0 else f"FAILED ({bad})"); sys.exit(1 if bad else 0)
    tasks = []
    for it in a.items:
        rows = [ln for ln in open(it)] if os.path.isfile(it) else [it]
        for ln in rows:
            f = ln.split("#")[0].split()
            if not f: continue
            k = int(f[0].replace("k=", "")); exp = float(f[1]) if len(f) > 1 else None
            tasks.append((k, exp, " ".join(f[2:]), a.span))
    if not tasks: ap.print_help(); sys.exit(2)
    print(f"rewalking {len(tasks)} k's on {a.jobs} cores (each ~5-15 s per core at 611 digits)\n", flush=True)
    out, bad = run(tasks, a.jobs)
    out.sort(reverse=True)
    with open("rewalk_lines.txt", "w") as f:
        for merit, gap, k, jl in out: f.write(line(k, gap, merit, jl) + "\n")
    print(f"\n{len(out)} lines -> rewalk_lines.txt (sorted by merit)" + (f"  |  {bad} problem(s) above" if bad else "  |  all as expected"))

if __name__ == "__main__":
    main()
