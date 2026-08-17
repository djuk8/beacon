#!/usr/bin/env python3
"""LIVEFIRE-GW -- AB-window variant of livefire_g (P5), m1a semantics EXACT.

DIFFS vs livefire_g.py (all gated by gate_ab.py; desert mode == original):
  1. --zd-override Z: primorial = P#(Z); one big k0 per worker (first seeded
     draw), per-trial k = k0 + t, t in [0, 1e7). Replay/ckpt compatible.
  2. make_kbase precomputes (k0*P) mod p once; per-trial sieve stays int64
     (catch #1: raw big-k overflows the int64 sieve).
  3. bits class from (kmax * P) (leg B: 10^7 formula silently picks 2048).
  4. token logging s<seed>t<idx>; --reconstruct-k regenerates k.
  5. sys.set_int_max_str_digits raised; ckpt stores t-offset, not big k
     (catch #2: python>=3.11 4300-digit int-str limit; found on-box at
     D=9800, fenced by gate leg G at D=5000).

Original P5 notes:

The lossless-batching theorem this rests on: in livefire_m1a's merged
|j|-order walk, a side's tested set is exactly the PREFIX of that side's
survivor sequence up to and including its first prime -- independent of
interleaving. So trials can be batched and overtested freely on the GPU
while (k, gap, jleft, jright, tests, survivors) remain bit-identical to
the CPU hunter: tests = (left fence index + 1) + (right fence index + 1).

Flow per round: for every in-flight trial side without a fence, take the
next --round survivors, write ONE candidate file, run the G1 driver once,
fold verdicts back in per-side order. Verdict semantics: 0 composite;
1 Fermat-2 PRP -> host gmpy2.is_prime(mr) confirm (m1a acceptance);
2 GEC alarm -> retest next round, second alarm -> host arbitrates. A side
fences at its first in-order accepted prime; both fences -> log (rows
flushed in TRIAL-INDEX order so the CSV equals m1a's row-for-row).

Checkpoint (ckpt.json, atomic): {n_created, n_logged, pending rows,
active trials: k, n_surv, per-side decided-frontier + fence + found-tests}.
Resume: RNG-replay n_created draws asserting each k, re-sieve active
trials asserting survivor counts, continue. Loss <= one round.

Usage (gate, CPU driver):
  python3 livefire_g.py --digits 1000 --z 1e7 --trials 3 --seed 77 \
      --table ../tab --driver ../p3/g1_fermat_cpu --round 64
Usage (production, one orchestrator per card):
  python3 livefire_g.py --digits 9800 --z 1e9 --trials 99999 --seed 5001 \
      --table ../table_98_1e9 --driver ./g1_fermat --device 0
Log: livefire_log.csv, m1a schema -> check_records.py / notary_v1.py as-is.
"""
import argparse, csv, json, math, os, random, struct, subprocess, sys, time
try:
    sys.set_int_max_str_digits(2_000_000)   # catch #2: py>=3.11 limit
except AttributeError:
    pass
import numpy as np, gmpy2

MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
CKPT = "ckpt.json"
CLASSES = [2048, 4096, 8192, 16384, 32768]

def primes_upto(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

def build_base(D, zdo=None):
    """IDENTICAL to livefire_m1a.build_base when zdo is None. With zdo:
    primorial = P#(zdo) (AB-window design); k carries the size closure."""
    limit = int(2.6 * D * math.log(10))
    pr = primes_upto(limit)
    if zdo is not None:
        used = [int(p) for p in pr[pr <= zdo]]
        P = gmpy2.mpz(1)
        for p in used: P *= p
        return P, int(used[-1]), used
    P = gmpy2.mpz(1); zd = 0; used = []
    target = (D - 8) * math.log(10); theta = 0.0
    for p in pr:
        if theta >= target: break
        P *= int(p); theta += math.log(p); zd = int(p); used.append(int(p))
    return P, zd, used


def make_kbase(k0, small_p, small_r, tab_p, tab_r, n_med, chunk):
    """Window mode: precompute (k0*P) mod p once per worker so per-trial
    sieving stays int64. Returns (k0, base_small, base_big)."""
    K = gmpy2.mpz(k0)
    bs = np.array([int(K % int(p)) for p in small_p], dtype=np.int64)
    bs = (bs * small_r) % small_p
    nbig = len(tab_p) - n_med
    bb = np.empty(nbig, dtype=np.int64)
    done = 0
    for c0 in range(n_med, len(tab_p), chunk):
        bp = np.asarray(tab_p[c0:c0 + chunk])
        br = np.asarray(tab_r[c0:c0 + chunk])
        kr = np.array([int(K % int(p)) for p in bp], dtype=np.int64)
        bb[done:done + len(bp)] = (kr * br) % bp
        done += len(bp)
    return (int(k0), bs, bb)

def open_table(path, zd, z, D):
    meta = json.load(open(os.path.join(path, "meta.json")))
    assert meta["schema"] == 1 and meta["D"] == D
    assert meta["zdesign"] == zd and meta["z"] == z
    tp = np.load(os.path.join(path, "primes.npy"), mmap_mode="r")
    tr = np.load(os.path.join(path, "resid.npy"), mmap_mode="r")
    return tp, tr

def self_prep(P, zd, z):
    print("self-prep (no --table): sieving + residues locally ...", flush=True)
    deep = primes_upto(z); deep = deep[deep > zd]
    rP = np.empty(len(deep), dtype=np.int64)
    for i in range(len(deep)):
        rP[i] = int(P % int(deep[i]))
    return deep, rP

def sieve_trial(k, W, Wside, design, small_p, small_r, tab_p, tab_r, n_med,
                chunk, kb=None):
    """IDENTICAL to livefire_m2.sieve_trial when kb is None. Window mode:
    kb=(k0, base_small, base_big), t = k - k0 < 1e7, all products int64."""
    alive = np.ones(W, dtype=bool)
    for q in design:
        alive[Wside % q::q] = False
    if kb is None:
        r0s = (k * small_r) % small_p
    else:
        t_off = int(k - kb[0])
        assert 0 <= t_off < 10 ** 7, "window k outside k0 stride"
        r0s = (kb[1] + t_off * small_r) % small_p
    lo_s = (r0s - Wside) % small_p
    for p, rl in zip(small_p, lo_s):
        alive[(p - rl) % p::p] = False
    done_big = 0
    for c0 in range(n_med, len(tab_p), chunk):
        bp = np.asarray(tab_p[c0:c0 + chunk])
        br = np.asarray(tab_r[c0:c0 + chunk])
        if kb is None:
            r0b = (k * br) % bp
        else:
            r0b = (kb[2][done_big:done_big + len(bp)] + t_off * br) % bp
        done_big += len(bp)
        lo_b = (r0b - Wside) % bp
        idx = (bp - lo_b) % bp
        hit = idx < W
        alive[idx[hit]] = False
    surv = np.flatnonzero(alive) - Wside
    return surv[np.argsort(np.abs(surv), kind="stable")]

def write_ckpt(obj):
    tmp = CKPT + ".tmp"
    json.dump(obj, open(tmp, "w"))
    os.replace(tmp, CKPT)

class Side:
    __slots__ = ("seq", "cur", "fence", "tests", "cache", "alarmed", "pending")
    def __init__(self, seq):
        self.seq = seq          # survivor offsets, |j|-ascending
        self.cur = 0            # decided frontier (all < cur decided composite)
        self.fence = None       # offset of first accepted prime
        self.tests = None       # fence index + 1 (m1a tests contribution)
        self.cache = {}         # idx -> verdict for decided-out-of-order
        self.alarmed = set()    # idxs that alarmed once (retry pending)
        self.pending = None     # (idx, Popen) host MR confirmation in flight

class Trial:
    __slots__ = ("t", "k", "n0", "lnn", "L", "R", "n_surv", "born")
    def __init__(self, t, k, P, order):
        self.t = t; self.k = k
        self.n0 = int(k) * P
        self.lnn = float(gmpy2.log(self.n0))
        self.L = Side([int(j) for j in order if j < 0])
        self.R = Side([int(j) for j in order if j > 0])
        self.n_surv = len(order)
        self.born = time.time()

def run(a):
    D, z, N = a.digits, int(a.z), a.trials
    if not a.driver: raise SystemExit("--driver required for runs")
    if z > 2e9:
        raise SystemExit("python kit supports z <= 1e9")
    L = D * math.log(10)
    Wside = int(25 * L); W = 2 * Wside + 1
    P, zd, design = build_base(D, a.zd_override)
    if a.zd_override:
        k0_lo = 10 ** (D - 1) // P + 1
        k0_hi = 10 ** D // P - 10 ** 7
        kmax = k0_hi + 10 ** 7
    else:
        kmax = 10 ** 7
    def ktag(t, kk): return f"s{a.seed}t{t}" if a.zd_override else kk
    bits = next(b for b in CLASSES
                if b >= (kmax * P).bit_length() + 1)
    nb = bits // 8
    print(f"D={D:,} | z={z:.0e} | window +/-{Wside:,} | trials={N} | "
          f"class {bits} bits | round {a.round} | inflight {a.inflight}",
          flush=True)
    if a.table:
        tab_p, tab_r = open_table(a.table, zd, z, D)
    else:
        tab_p, tab_r = self_prep(P, zd, z)
    n_med = int(np.searchsorted(np.asarray(tab_p[:min(len(tab_p), 10_000_000)]), W))
    small_p = np.asarray(tab_p[:n_med]).copy()
    small_r = np.asarray(tab_r[:n_med]).copy()

    fields = ["ts", "D", "zdesign", "z", "k", "gap", "merit", "jleft", "jright",
              "tests", "survivors", "t_trial_s"]
    newlog = (not os.path.exists("livefire_log.csv")
              or os.path.getsize("livefire_log.csv") == 0)
    logf = open("livefire_log.csv", "a", newline=""); logw = csv.writer(logf)
    if newlog: logw.writerow(fields); logf.flush()   # flush: survive SIGKILL

    # ---- state (with resume) ----
    random.seed(a.seed)
    if a.zd_override:
        k0 = random.randrange(k0_lo, k0_hi)
        print(f"window mode: k0 drawn ({k0.bit_length()} bits ~ "
              f"{int(k0.bit_length()/3.3219)+1} digits); precomputing "
              f"(k0*P) mod p over the table ...", flush=True)
        _tk = time.time()
        kbase = make_kbase(k0, small_p, small_r, tab_p, tab_r, n_med, a.chunk)
        print(f"  kbase ready [{time.time()-_tk:.0f}s]", flush=True)
        def draw_k(): return k0 + random.randrange(0, 10 ** 7)
    else:
        k0, kbase = 0, None
        def draw_k(): return random.randrange(10 ** 6, 10 ** 7)
    ck = json.load(open(CKPT)) if os.path.exists(CKPT) else {}
    n_created = int(ck.get("n_created", 0))
    n_logged = int(ck.get("n_logged", 0))
    pending = {int(t): row for t, row in ck.get("pending", {}).items()}
    ks = [draw_k() for _ in range(n_created)]
    active = {}
    for st in ck.get("active", []):
        t = int(st["t"]); k = ks[t]
        st_k = int(st["k"])
        if a.zd_override: st_k += k0        # ckpt stores t-offset (catch #2)
        assert k == st_k, f"ckpt/seed mismatch trial {t}"
        order = sieve_trial(k, W, Wside, design, small_p, small_r,
                            tab_p, tab_r, n_med, a.chunk, kb=kbase)
        tr = Trial(t, k, P, order)
        assert tr.n_surv == int(st["n_surv"]), f"survivor mismatch trial {t}"
        for S, sst in ((tr.L, st["L"]), (tr.R, st["R"])):
            S.cur = int(sst["cur"])
            S.fence = sst["fence"] if sst["fence"] is None else int(sst["fence"])
            S.tests = sst["tests"] if sst["tests"] is None else int(sst["tests"])
        active[t] = tr
    if n_created or pending:
        print(f"resume: {n_logged} logged, {len(active)} active, "
              f"{len(pending)} pending rows", flush=True)

    def save_ckpt():
        write_ckpt(dict(
            n_created=n_created, n_logged=n_logged,
            pending={str(t): row for t, row in pending.items()},
            active=[dict(t=tr.t,
                         k=(tr.k - k0 if a.zd_override else tr.k),
                         n_surv=tr.n_surv,
                         L=dict(cur=tr.L.cur, fence=tr.L.fence, tests=tr.L.tests),
                         R=dict(cur=tr.R.cur, fence=tr.R.fence, tests=tr.R.tests))
                    for tr in active.values()]))

    def flush_rows():
        nonlocal n_logged
        while n_logged in pending:
            row = pending.pop(n_logged)
            if row is not None:            # None = window-exceeded skip
                logw.writerow(row); logf.flush()
            n_logged += 1

    def pump():
        # advance decided frontiers; PRP at frontier -> async host confirm
        done = []
        for t, tr in active.items():
            for S in (tr.L, tr.R):
                if S.pending is not None:              # poll confirmation
                    idx, pr = S.pending
                    rc = pr.poll()
                    if rc is None: continue
                    ok = pr.stdout.read().strip() == b"True"
                    S.pending = None
                    if ok:
                        S.fence = S.seq[idx]; S.tests = idx + 1
                    else:
                        S.cur = idx + 1    # Fermat pseudoprime: composite
                while (S.fence is None and S.pending is None
                       and S.cur in S.cache):
                    v = S.cache.pop(S.cur)
                    if v == 1:
                        cand = tr.n0 + S.seq[S.cur]
                        stats["prp"] += 1
                        pr = subprocess.Popen(
                            ["python3", "-c",
                             "import sys,gmpy2;d=sys.stdin.buffer.read();"
                             "print(gmpy2.is_prime(int.from_bytes(d,'little'),"
                             f"{a.mr}))"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                        pr.stdin.write(int(cand).to_bytes(
                            (int(cand).bit_length() + 7) // 8, "little"))
                        pr.stdin.close()
                        S.pending = (S.cur, pr)
                    else:
                        S.cur += 1
            if tr.L.fence is not None and tr.R.fence is not None:
                gap = tr.R.fence - tr.L.fence
                merit = gap / tr.lnn
                dt = time.time() - tr.born
                pending[t] = [int(time.time()), D, zd, z, ktag(t, tr.k), gap,
                              f"{merit:.4f}", tr.L.fence, tr.R.fence,
                              tr.L.tests + tr.R.tests, tr.n_surv, f"{dt:.1f}"]
                done.append(t)
                print(f"  trial {t+1:>3}: k={ktag(t, tr.k)} gap={gap:>8,} "
                      f"merit={merit:6.3f} tests={tr.L.tests+tr.R.tests:>5} "
                      f"({dt:6.1f}s)", flush=True)
        for t in done: del active[t]
        flush_rows()
        save_ckpt()

    stats = dict(tested=0, prp=0, alarms=0, t0=time.time())
    while n_logged < N:
        # top up in-flight trials
        while len(active) < a.inflight and n_created < N:
            k = draw_k(); ks.append(k)
            order = sieve_trial(k, W, Wside, design, small_p, small_r,
                                tab_p, tab_r, n_med, a.chunk, kb=kbase)
            active[n_created] = Trial(n_created, k, P, order)
            n_created += 1
        save_ckpt()

        # assemble one round: (trial, side, idx, candidate)
        batch = []
        for tr in active.values():
            for S in (tr.L, tr.R):
                if S.fence is not None or S.pending is not None: continue
                idxs = sorted(S.alarmed) + [i for i in
                        range(S.cur, min(S.cur + a.round, len(S.seq)))
                        if i not in S.cache and i not in S.alarmed]
                for i in idxs[:a.round]:
                    batch.append((tr, S, i, tr.n0 + S.seq[i]))
        if not batch:
            pump()
            if any(S.pending is not None for tr in active.values()
                   for S in (tr.L, tr.R)):
                time.sleep(0.05); continue     # confirmations in flight
            # every active trial exhausted a side without a prime -> skip them
            for t in sorted(active):
                tr = active[t]
                if (tr.L.fence is None and tr.L.cur >= len(tr.L.seq)) or \
                   (tr.R.fence is None and tr.R.cur >= len(tr.R.seq)):
                    print(f"  trial {t+1:>3}: window exceeded (rare) -- skipped")
                    pending[t] = None
                    del active[t]
            flush_rows()
            save_ckpt()
            if not active and n_created >= N: break
            continue

        # write candidates, run driver, read verdicts
        with open("gb_c.bin.tmp", "wb") as f:
            f.write(struct.pack("<IIQ", MAGIC_C, bits, len(batch)))
            for _, _, _, n in batch:
                f.write(int(n).to_bytes(nb, "little"))
        os.replace("gb_c.bin.tmp", "gb_c.bin")
        cmd = f"{a.driver} gb_c.bin gb_v.bin" + \
              (f" --device {a.device}" if a.device >= 0 else "")
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"driver failed:\n{r.stdout}\n{r.stderr}")
        with open("gb_v.bin", "rb") as f:
            m, b, c = struct.unpack("<IIQ", f.read(16))
            assert m == MAGIC_V and b == bits and c == len(batch)
            verdicts = f.read(len(batch))
        stats["tested"] += len(batch)

        # fold verdicts into side caches (alarm arbitration on second strike)
        for (tr, S, i, n), v in zip(batch, verdicts):
            if v == 2:
                stats["alarms"] += 1
                if i in S.alarmed:
                    S.alarmed.discard(i)
                    v = 1 if gmpy2.powmod(2, int(n) - 1, int(n)) == 1 else 0
                else:
                    S.alarmed.add(i); continue
            elif i in S.alarmed:
                S.alarmed.discard(i)
            S.cache[i] = v

        pump()

    el = time.time() - stats["t0"]
    print(f"done: {n_logged} trials | GPU-tested {stats['tested']:,} "
          f"({stats['tested']/max(el,1e-9):,.0f}/s) | prp {stats['prp']} | "
          f"gec_alarms {stats['alarms']} | {el:,.0f}s", flush=True)

def reconstruct(a):
    import re
    m = re.fullmatch(r"s(\d+)t(\d+)", a.reconstruct_k)
    if not m: raise SystemExit("token format: s<seed>t<index>")
    seed, idx = int(m.group(1)), int(m.group(2))
    P, zd, _ = build_base(a.digits, a.zd_override)
    if a.zd_override:
        k0_lo = 10 ** (a.digits - 1) // P + 1
        k0_hi = 10 ** a.digits // P - 10 ** 7
        random.seed(seed)
        k0 = random.randrange(k0_lo, k0_hi)
        for _ in range(idx + 1):
            k = k0 + random.randrange(0, 10 ** 7)
    else:
        random.seed(seed)
        for _ in range(idx + 1):
            k = random.randrange(10 ** 6, 10 ** 7)
    print(f"# token {a.reconstruct_k}  D={a.digits}  zdesign={zd}  "
          f"k_digits={len(str(k))}")
    print(f"# p1 = k * P#({zd}) + jleft")
    print(k)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--digits", type=int, required=True)
    ap.add_argument("--z", type=float, required=True)
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--table", default=None)
    ap.add_argument("--driver", default=None)
    ap.add_argument("--device", type=int, default=-1)
    ap.add_argument("--round", type=int, default=256,
                    help="candidates per unfenced side per round")
    ap.add_argument("--inflight", type=int, default=32)
    ap.add_argument("--mr", type=int, default=25,
                    help="host MR rounds on GPU-PRP fences (m1a: 25)")
    ap.add_argument("--chunk", type=int, default=4_000_000)
    ap.add_argument("--zd-override", type=int, default=None)
    ap.add_argument("--reconstruct-k", default=None,
                    help="token s<seed>t<idx> -> print k (needs --digits, --zd-override)")
    _a = ap.parse_args()
    if _a.reconstruct_k:
        reconstruct(_a)
    else:
        run(_a)
