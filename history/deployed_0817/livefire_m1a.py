#!/usr/bin/env python3
"""M1a LIVE FIRE -- real anchored gap trials + model validation (run locally).

Each trial: build primorial anchor n0 = k * P#, sieve the window [n0-W, n0+W]
to depth z, PRP outward from the anchor until the nearest prime is found on
each side. The straddled gap is a genuine prime gap. Logs gap, merit, tests,
timing; compares measured constants against the planner model:
    tests/trial ~ 2*F*L,   gap ~ Gamma(2, L)  (size-biased straddling).

Usage:
    pip install gmpy2 numpy
    python3 livefire_m1a.py --digits 3000 --trials 20 --z 1e8     # first contact
    python3 livefire_m1a.py --digits 3000 --trials 200 --z 1e9    # overnight
Note: this python kit supports z <= 1e9 (simple sieve, ~1 GB RAM at 1e9).
Deeper z is engine (M1) territory.

Outputs: livefire_log.csv (appended), prp_fit.npy (feeds planner_v1.py).
Every logged find is reconstructible: p1 = k * (product of primes <= zdesign) + jleft.
"""
import argparse, math, time, random, csv, os
import numpy as np, gmpy2

EG = 0.5614594836  # e^-gamma

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def bench_prp():
    print("benchmarking PRP on this machine...")
    res = {}
    for D in (1000, 2000, 4000, 8000):
        n = gmpy2.mpz(random.randrange(10 ** (D - 1), 10 ** D)) | 1
        t0 = time.time(); gmpy2.powmod(2, n - 1, n); dt = time.time() - t0
        reps = max(1, min(10, int(1.0 / max(dt, 1e-4))))
        t0 = time.time()
        for _ in range(reps): gmpy2.powmod(2, n - 1, n)
        res[D] = (time.time() - t0) / reps
        print(f"  {D:>6,} digits: {res[D]*1000:9.1f} ms/test")
    Ds = np.array(sorted(res)); Ts = np.array([res[d] for d in Ds])
    b, la = np.polyfit(np.log(Ds), np.log(Ts), 1)
    np.save("prp_fit.npy", np.array([math.exp(la), b]))
    print(f"  fit: T_prp(D) = {math.exp(la):.3e} * D^{b:.3f} s   (saved prp_fit.npy)\n")

def build_base(D):
    """Primorial P over primes <= zdesign, sized so k*P has ~D digits."""
    limit = int(2.6 * D * math.log(10))
    pr = primes_upto(limit)
    P = gmpy2.mpz(1); zd = 0; used = []
    target = (D - 8) * math.log(10); theta = 0.0
    for p in pr:
        if theta >= target: break
        P *= int(p); theta += math.log(p); zd = int(p); used.append(int(p))
    return P, zd, used

def run(a):
    D, z, N = a.digits, int(a.z), a.trials
    if z > 2e9:
        raise SystemExit("this kit supports z <= 1e9; deeper sieving is engine territory")
    random.seed(a.seed)
    L = D * math.log(10)
    Wside = int(25 * L); W = 2 * Wside + 1
    print(f"D={D:,} digits | z={z:.0e} | window +/-{Wside:,} | trials={N}")

    P, zd, design = build_base(D)
    print(f"anchor base: P# over primes <= {zd:,} ({len(design):,} primes, {P.num_digits(10):,} digits)")

    print("deep-sieve prep (one-time): residues of P mod every sieve prime...")
    t0 = time.time()
    deep = primes_upto(z); deep = deep[deep > zd]
    rP = np.empty(len(deep), dtype=np.int64)
    for i in range(len(deep)):
        rP[i] = int(P % int(deep[i]))
    med = deep < W
    small_p, small_r = deep[med], rP[med]
    big_p, big_r = deep[~med], rP[~med]
    print(f"  {len(deep):,} deep primes ready ({time.time()-t0:.0f}s)")

    fields = ["ts", "D", "zdesign", "z", "k", "gap", "merit", "jleft", "jright",
              "tests", "survivors", "t_trial_s"]
    newlog = not os.path.exists("livefire_log.csv")
    logf = open("livefire_log.csv", "a", newline=""); logw = csv.writer(logf)
    if newlog: logw.writerow(fields)

    gaps, tests_all, Fs = [], [], []
    for t in range(N):
        t0 = time.time()
        k = random.randrange(10 ** 6, 10 ** 7)
        n0 = int(k) * P
        lnn = float(gmpy2.log(n0))
        alive = np.ones(W, dtype=bool)
        for q in design:                      # design residues: j ≡ 0 (mod q) dead
            alive[Wside % q::q] = False
        r0s = (k * small_r) % small_p         # n0 mod p, vectorized
        lo_s = (r0s - Wside) % small_p
        for p, rl in zip(small_p, lo_s):      # multi-hit medium primes
            alive[(p - rl) % p::p] = False
        r0b = (k * big_r) % big_p
        lo_b = (r0b - Wside) % big_p
        idx = (big_p - lo_b) % big_p          # single-hit large primes
        hit = idx < W
        alive[idx[hit]] = False
        surv = np.flatnonzero(alive) - Wside
        order = surv[np.argsort(np.abs(surv), kind="stable")]

        jl = jr = None; tests = 0
        for j in order:
            if j == 0 or (j < 0 and jl is not None) or (j > 0 and jr is not None):
                continue
            tests += 1
            cand = n0 + int(j)
            if gmpy2.powmod(2, cand - 1, cand) == 1 and gmpy2.is_prime(cand, 25):
                if j < 0: jl = int(j)
                else: jr = int(j)
                if jl is not None and jr is not None: break
        dt = time.time() - t0
        if jl is None or jr is None:
            print(f"  trial {t+1:>3}: window exceeded (rare) -- skipped"); continue
        gap = jr - jl; merit = gap / lnn
        gaps.append(gap); tests_all.append(tests); Fs.append(len(surv) / W)
        logw.writerow([int(time.time()), D, zd, z, k, gap, f"{merit:.4f}",
                       jl, jr, tests, len(surv), f"{dt:.1f}"])
        logf.flush()
        print(f"  trial {t+1:>3}: k={k} gap={gap:>8,} merit={merit:6.3f} "
              f"tests={tests:>5} ({dt:6.1f}s)")

    if gaps:
        F = float(np.mean(Fs))
        print("\n=== MODEL vs MEASURED ===")
        print(f"survivor density F:  model {EG/math.log(z):.4f}   measured {F:.4f}")
        print(f"tests/trial:         model {2*F*L:7.0f}   measured {np.mean(tests_all):7.0f}"
              f"   kappa = {np.mean(tests_all)/(2*F*L):.2f}")
        print(f"mean straddled gap:  model {2*L:7.0f}   measured {np.mean(gaps):7.0f}"
              f"   r_eff = {2*L/np.mean(gaps):.3f}")
        print(f"max merit this run:  {max(gaps)/L:.2f}  over {len(gaps)} trials")
        print("\nsend back: livefire_log.csv + this summary block")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, default=3000)
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--z", type=float, default=1e8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bench", action="store_true", help="run only the PRP benchmark")
    args = ap.parse_args()
    bench_prp()
    if not args.bench:
        run(args)
