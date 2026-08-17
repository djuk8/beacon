#!/usr/bin/env python3
"""M2 LIVE FIRE -- P2 hunter: m1a semantics + shared residue table + checkpoints.

Trial semantics are IDENTICAL to livefire_m1a.py (same k sequence per seed,
same sieve, same survivor ordering, same PRP walk, same log schema), verified
by gate_m2.py. New in P2:

  --table DIR   shared residue table from build_residue_table.py, opened
                read-only via mmap (fleet: build once, 60 workers share the
                pages; no per-worker 1 GB sieve, no per-worker residue prep).
                Without --table, falls back to m1a-style self-prep.
  checkpoints   ckpt.json (atomic tmp+rename) in the working directory:
                between trials {n_done}, mid-trial {n_done,k,n_surv,pos,jl,jr,
                tests,t_accum} every --ckpt tests and at sieve completion.
                Resume: replay n_done RNG draws, redraw k and ASSERT it equals
                the checkpoint (seed/ckpt integrity), rebuild the sieve
                deterministically, ASSERT survivor count, continue at pos.
                A kill costs minutes (<=ckpt*T_prp + resieve), not 11h.

Usage:
  python3 livefire_m2.py --digits 24000 --z 1e9 --trials 999 --seed 2001 \
      --table ../table_24k_1e9
Log: livefire_log.csv in cwd (schema unchanged -> check_records/notary as-is).
"""
import argparse, csv, json, math, os, random, time
import numpy as np, gmpy2

EG = 0.5614594836  # e^-gamma
CKPT = "ckpt.json"

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def build_base(D):
    """IDENTICAL to livefire_m1a.build_base."""
    limit = int(2.6 * D * math.log(10))
    pr = primes_upto(limit)
    P = gmpy2.mpz(1); zd = 0; used = []
    target = (D - 8) * math.log(10); theta = 0.0
    for p in pr:
        if theta >= target: break
        P *= int(p); theta += math.log(p); zd = int(p); used.append(int(p))
    return P, zd, used

def write_ckpt(obj):
    tmp = CKPT + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, CKPT)

def load_ckpt():
    if os.path.exists(CKPT):
        try: return json.load(open(CKPT))
        except Exception: pass
    return {}

def open_table(path, zd, z, D):
    meta = json.load(open(os.path.join(path, "meta.json")))
    assert meta["schema"] == 1
    assert meta["D"] == D, f"table D={meta['D']} != {D}"
    assert meta["zdesign"] == zd, f"table zdesign={meta['zdesign']} != {zd}"
    assert meta["z"] == z, f"table z={meta['z']} != {z}"
    tp = np.load(os.path.join(path, "primes.npy"), mmap_mode="r")
    tr = np.load(os.path.join(path, "resid.npy"), mmap_mode="r")
    assert len(tp) == meta["n_deep"]
    return tp, tr

def self_prep(P, zd, z):
    """m1a-style fallback: local sieve + residue prep (single-machine use)."""
    print("self-prep (no --table): sieving + residues locally ...", flush=True)
    t0 = time.time()
    deep = primes_upto(z); deep = deep[deep > zd]
    rP = np.empty(len(deep), dtype=np.int64)
    for i in range(len(deep)):
        rP[i] = int(P % int(deep[i]))
    print(f"  {len(deep):,} deep primes ready ({time.time()-t0:.0f}s)", flush=True)
    return deep, rP

def sieve_trial(k, W, Wside, design, small_p, small_r, tab_p, tab_r, n_med, chunk):
    """Rebuilds m1a's per-trial sieve exactly; big-prime pass chunked."""
    alive = np.ones(W, dtype=bool)
    for q in design:                          # design residues: j ≡ 0 (mod q) dead
        alive[Wside % q::q] = False
    r0s = (k * small_r) % small_p             # multi-hit medium primes
    lo_s = (r0s - Wside) % small_p
    for p, rl in zip(small_p, lo_s):
        alive[(p - rl) % p::p] = False
    for c0 in range(n_med, len(tab_p), chunk):  # single-hit large primes, chunked
        bp = np.asarray(tab_p[c0:c0 + chunk])
        br = np.asarray(tab_r[c0:c0 + chunk])
        r0b = (k * br) % bp
        lo_b = (r0b - Wside) % bp
        idx = (bp - lo_b) % bp
        hit = idx < W
        alive[idx[hit]] = False
    surv = np.flatnonzero(alive) - Wside
    return surv[np.argsort(np.abs(surv), kind="stable")]

def run(a):
    D, z, N = a.digits, int(a.z), a.trials
    if z > 2e9:
        raise SystemExit("python kit supports z <= 1e9; deeper is engine territory")
    L = D * math.log(10)
    Wside = int(25 * L); W = 2 * Wside + 1
    print(f"D={D:,} digits | z={z:.0e} | window +/-{Wside:,} | trials={N}")

    P, zd, design = build_base(D)
    print(f"anchor base: P# over primes <= {zd:,} ({len(design):,} primes, "
          f"{P.num_digits(10):,} digits)")

    if a.table:
        tab_p, tab_r = open_table(a.table, zd, z, D)
        print(f"shared table: {len(tab_p):,} deep primes via mmap ({a.table})")
    else:
        tab_p, tab_r = self_prep(P, zd, z)

    n_med = int(np.searchsorted(np.asarray(tab_p[:min(len(tab_p), 10_000_000)]), W))
    small_p = np.asarray(tab_p[:n_med]).copy()
    small_r = np.asarray(tab_r[:n_med]).copy()

    fields = ["ts", "D", "zdesign", "z", "k", "gap", "merit", "jleft", "jright",
              "tests", "survivors", "t_trial_s"]
    newlog = not os.path.exists("livefire_log.csv")
    logf = open("livefire_log.csv", "a", newline=""); logw = csv.writer(logf)
    if newlog: logw.writerow(fields)

    random.seed(a.seed)
    ck = load_ckpt()
    n_done = int(ck.get("n_done", 0))
    for _ in range(n_done):                   # RNG replay of finished trials
        random.randrange(10 ** 6, 10 ** 7)
    mid = ck if "k" in ck else None
    if n_done or mid:
        print(f"resume: {n_done} trials done"
              + (f", mid-trial k={ck['k']} pos={ck['pos']} tests={ck['tests']}"
                 if mid else ""), flush=True)

    for t in range(n_done, N):
        t0 = time.time(); t_accum = 0.0
        k = random.randrange(10 ** 6, 10 ** 7)
        if mid:
            assert k == int(mid["k"]), \
                f"ckpt/seed mismatch: replayed k={k} vs ckpt {mid['k']}"
        n0 = int(k) * P
        lnn = float(gmpy2.log(n0))
        order = sieve_trial(k, W, Wside, design, small_p, small_r,
                            tab_p, tab_r, n_med, a.chunk)
        if mid:
            assert len(order) == int(mid["n_surv"]), \
                f"ckpt survivors {mid['n_surv']} != rebuilt {len(order)}"
            start, jl, jr = int(mid["pos"]), mid["jl"], mid["jr"]
            jl = int(jl) if jl is not None else None
            jr = int(jr) if jr is not None else None
            tests = int(mid["tests"]); t_accum = float(mid.get("t_accum", 0.0))
            mid = None
        else:
            start, jl, jr, tests = 0, None, None, 0
            write_ckpt(dict(n_done=t, k=k, n_surv=len(order), pos=0,
                            jl=None, jr=None, tests=0, t_accum=0.0))

        for pos in range(start, len(order)):
            j = order[pos]
            if j == 0 or (j < 0 and jl is not None) or (j > 0 and jr is not None):
                continue
            tests += 1
            cand = n0 + int(j)
            if gmpy2.powmod(2, cand - 1, cand) == 1 and gmpy2.is_prime(cand, 25):
                if j < 0: jl = int(j)
                else: jr = int(j)
                if jl is not None and jr is not None: break
            if tests % a.ckpt == 0:
                write_ckpt(dict(n_done=t, k=k, n_surv=len(order), pos=pos + 1,
                                jl=jl, jr=jr, tests=tests,
                                t_accum=t_accum + (time.time() - t0)))

        dt = t_accum + (time.time() - t0)
        if jl is None or jr is None:
            print(f"  trial {t+1:>3}: window exceeded (rare) -- skipped")
            write_ckpt(dict(n_done=t + 1)); continue
        gap = jr - jl; merit = gap / lnn
        logw.writerow([int(time.time()), D, zd, z, k, gap, f"{merit:.4f}",
                       jl, jr, tests, len(order), f"{dt:.1f}"])
        logf.flush()
        write_ckpt(dict(n_done=t + 1))
        print(f"  trial {t+1:>3}: k={k} gap={gap:>8,} merit={merit:6.3f} "
              f"tests={tests:>5} ({dt:6.1f}s)", flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, default=3000)
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--z", type=float, default=1e8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--table", default=None, help="shared residue table dir")
    ap.add_argument("--ckpt", type=int, default=10, help="checkpoint every N tests")
    ap.add_argument("--chunk", type=int, default=4_000_000,
                    help="big-prime pass chunk (bounds private RAM)")
    run(ap.parse_args())
