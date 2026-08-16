#!/usr/bin/env python3
"""deepsieve.py -- extend the architect's incidental sieve from Q to deep_q.

THE POINT. A lift's candidates are n0(t) + j for the design's surviving odd
j in [-L+1, L-1], with n0(t) = k(t) * P_eff and k(t) = r + M*(t0 + t) fixed
by the CRT (architect_v2.prep_lift). Therefore for ANY prime q:

    n0(t) mod q = ((A_q + B_q * (t mod q)) mod q) * PE_q mod q
    A_q = (r + M*t0) mod q,  B_q = M mod q,  PE_q = P_eff mod q

A/B/PE are LIFT-INDEPENDENT: three big-mods per prime, once per design,
then every lift's residues over ALL deep primes are ~10 vectorized int64
ops. Prime q kills exactly the j with j = -n0(t) mod q; for q > 2(L-1)
that is at most ONE j in the window, so the deep sieve is a landing test
against a survivor bitmap, not a j x q matrix.

WHAT IT BUYS. Sieving (Q, deep_q] removes composites with a factor in that
range before any primality test. Survivor count drops by ~ln Q / ln deep_q
(Mertens), so tests per lift drop by the same factor on the GPU screen
(which tests every packed candidate) and 1/beta -- the tests-to-first-prime
of a failed CPU lift -- drops identically.

E-INVARIANCE (the safety theorem). Every kill is certified on the spot by
explicit divisibility: (n0 + j) % q == 0 with q > Q >= 2*10^5 and
n0 + j ~ 10^D >> q, so every killed candidate is certainly composite and
NO PRIME IS EVER REMOVED. E = expected interior primes per lift is exactly
unchanged; only the cost of discovering them falls. If certification ever
fails the process dies loudly (assert) -- that is a bug, never a shrug.

LIMITS. deep_q < 2^31 (int64 product-safety: all intermediates < 2^62).
t of any size is handled (base-2^31 Horner) but the fast path is t < 2^62.

    python3 deepsieve.py selftest            # exhaustive small-D gate
    python3 deepsieve.py bench --digits 2700 --zd 401 --L 62000 \
        --Q 200000 --swap 3,5,7,11,13,17,19,23,29 --seed 1 \
        --deep-q 100000000 --lifts 5 --arch architect_v2.py
"""
import argparse, hashlib, json, math, os, sys, time
import numpy as np
import gmpy2

try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

QCAP = (1 << 31) - 1          # int64 product-safety ceiling for deep_q
PI = {10**5: 9592, 10**6: 78498, 2 * 10**5: 17984, 10**7: 664579,
      10**8: 5761455, 10**9: 50847534}   # known pi(x) anchors for self-check


# ---------------------------------------------------------------- primes ---
def primes_range(lo, hi, cache_dir=None, verbose=False):
    """All primes p with lo < p <= hi, int64, via segmented sieve.
    Disk-cached as int32 (hi < 2^31 enforced by caller)."""
    assert hi <= QCAP, f"deep_q {hi} exceeds int64-safe cap {QCAP}"
    cf = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cf = os.path.join(cache_dir, f"primes_{lo}_{hi}.npy")
        if os.path.exists(cf):
            return np.load(cf).astype(np.int64)
    t0 = time.time()
    root = int(hi ** 0.5) + 1
    s = np.ones(root + 1, dtype=bool); s[:2] = False
    for i in range(2, int(root ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    base = np.nonzero(s)[0]
    out, SEG = [], 1 << 23
    start = lo + 1
    while start <= hi:
        end = min(start + SEG - 1, hi)
        seg = np.ones(end - start + 1, dtype=bool)
        if start == 1: seg[0] = False
        for p in base:
            p = int(p)
            first = max(p * p, ((start + p - 1) // p) * p)
            if first > end: continue
            seg[first - start::p] = False
        out.append((np.nonzero(seg)[0] + start).astype(np.int64))
        start = end + 1
    pr = np.concatenate(out) if out else np.empty(0, np.int64)
    if verbose:
        print(f"  primes_range({lo:,}, {hi:,}]: {len(pr):,} primes "
              f"[{time.time()-t0:.1f}s]")
    if cf:
        np.save(cf, pr.astype(np.int32))
    return pr


def _mod_many(t, q):
    """t mod q for python int t of any size, int64 array q (q < 2^31)."""
    t = int(t)
    assert t >= 0
    if t.bit_length() <= 62:
        return np.int64(t) % q
    base = np.int64(1 << 31) % q
    acc = np.zeros(len(q), dtype=np.int64)
    limbs = []
    tt = t
    while tt:
        limbs.append(tt & QCAP); tt >>= 31
    for limb in reversed(limbs):
        acc = (acc * base + np.int64(limb)) % q
    return acc


# ------------------------------------------------------------- the sieve ---
class DeepSieve:
    def __init__(self, dz, deep_q, cache_dir=".ds_cache", block=4_000_000,
                 verbose=True):
        assert deep_q <= QCAP, f"deep_q {deep_q} exceeds cap {QCAP}"
        Q = int(dz["Q"])
        assert deep_q > Q, "deep_q must exceed the design Q"
        if "crt_M" not in dz:
            raise ValueError("dz must be prep_lift'ed before DeepSieve")
        self.L = int(dz["L"])
        self.Q, self.deep_q, self.block = Q, int(deep_q), int(block)
        self.M = gmpy2.mpz(dz["crt_M"])
        self.R0 = gmpy2.mpz(dz["crt_r"]) + self.M * int(dz["crt_t0"])
        self.PEz = gmpy2.mpz(dz["P_eff"])
        self.n_kills = self.n_lifts = 0
        fp = hashlib.sha256()
        for x in (self.R0, self.M, self.PEz, Q, self.deep_q):
            fp.update(str(int(x)).encode()); fp.update(b"|")
        self.fp = fp.hexdigest()[:16]
        os.makedirs(cache_dir, exist_ok=True)
        qpath = os.path.join(cache_dir,
                             f"primes_{Q}_{self.deep_q}.npy")
        if not os.path.exists(qpath):
            primes_range(Q, self.deep_q, cache_dir, verbose)
        self.q_mm = np.load(qpath, mmap_mode="r")           # int32 on disk
        self.nq = len(self.q_mm)
        self._q64 = None
        base = os.path.join(cache_dir, f"abpe_{self.fp}")
        paths = [base + x + ".npy" for x in ("A", "B", "PE")]
        meta = base + ".done.json"
        if os.path.exists(meta) and all(os.path.exists(p) for p in paths):
            md = json.load(open(meta))
            assert md["nq"] == self.nq, "ABPE cache/prime-range drift"
            self.A_mm, self.B_mm, self.PE_mm = \
                (np.load(p, mmap_mode="r") for p in paths)
            for p, arr, want in zip(paths,
                                    (self.A_mm, self.B_mm, self.PE_mm),
                                    md["sha"]):
                h = hashlib.sha256()
                for i in range(0, self.nq, 1 << 22):
                    h.update(arr[i:i + (1 << 22)].tobytes())
                if h.hexdigest() != want:
                    raise RuntimeError(
                        f"DEEPSIEVE CACHE CORRUPT: {p} checksum mismatch "
                        f"-- delete abpe_{self.fp}* and rebuild")
            if verbose:
                print(f"  deepsieve: ABPE cache hit, checksums OK "
                      f"({self.nq:,} primes, fp {self.fp})")
        else:
            t0 = time.time()
            tmps = [p + ".building" for p in paths]
            prog = base + ".progress"
            start = 0
            if all(os.path.exists(p) for p in tmps) \
                    and os.path.exists(prog):
                start = int(open(prog).read().strip() or 0)
                mms = [np.lib.format.open_memmap(p, mode="r+")
                       for p in tmps]
                if len(mms[0]) != self.nq:
                    start = 0
                    mms = [np.lib.format.open_memmap(
                        p, mode="w+", dtype=np.int32, shape=(self.nq,))
                        for p in tmps]
                elif verbose and start:
                    print(f"  deepsieve: resuming ABPE build at prime "
                          f"{start:,}/{self.nq:,}")
            else:
                mms = [np.lib.format.open_memmap(p, mode="w+",
                                                 dtype=np.int32,
                                                 shape=(self.nq,))
                       for p in tmps]
            R0, M, PEz = self.R0, self.M, self.PEz
            BL = self.block
            for i in range(start, self.nq, BL):
                ql = self.q_mm[i:i + BL].tolist()
                for arr, X in zip(mms, (R0, M, PEz)):
                    arr[i:i + len(ql)] = [X % p for p in ql]
                for arr in mms:
                    arr.flush()
                open(prog, "w").write(str(i + len(ql)))
            shas = []
            for arr in mms:
                h = hashlib.sha256()
                for i in range(0, self.nq, 1 << 22):
                    h.update(np.ascontiguousarray(
                        arr[i:i + (1 << 22)]).tobytes())
                shas.append(h.hexdigest())
            del mms
            for tp, p in zip(tmps, paths):
                os.replace(tp, p)
            json.dump(dict(nq=self.nq, sha=shas), open(meta, "w"))
            if os.path.exists(prog):
                os.remove(prog)
            self.A_mm, self.B_mm, self.PE_mm = \
                (np.load(p, mmap_mode="r") for p in paths)
            if verbose:
                print(f"  deepsieve: ABPE built for {self.nq:,} primes "
                      f"[{time.time()-t0:.1f}s] -> cached+checksummed "
                      f"(fp {self.fp})")

    @property
    def q(self):
        """Full int64 prime array (materialized on demand; gate/tests only
        -- the production path stays blockwise off the int32 memmap)."""
        if self._q64 is None:
            self._q64 = self.q_mm[:].astype(np.int64)
        return self._q64

    # residues of n0(t) modulo every deep prime, blockwise
    def _block(self, sl):
        q = self.q_mm[sl].astype(np.int64)
        A = self.A_mm[sl].astype(np.int64)
        B = self.B_mm[sl].astype(np.int64)
        PE = self.PE_mm[sl].astype(np.int64)
        return q, A, B, PE

    def _n0_mod_block(self, t, sl):
        q, A, B, PE = self._block(sl)
        tm = _mod_many(t, q)
        return q, ((A + B * tm) % q) * PE % q

    def n0_mod(self, t):
        out = np.empty(self.nq, np.int64)
        for i in range(0, self.nq, self.block):
            sl = slice(i, min(i + self.block, self.nq))
            out[sl] = self._n0_mod_block(t, sl)[1]
        return out

    def kills(self, t):
        """All (j, q) with q | n0(t)+j, j odd in [-(L-1), L-1]. Exact."""
        L = self.L
        lim = L - 1
        jout, qout = [], []
        for i in range(0, self.nq, self.block):
            sl = slice(i, min(i + self.block, self.nq))
            q, n0m = self._n0_mod_block(t, sl)
            jstar = (q - n0m) % q                       # -n0 mod q in [0,q)
            big = q > 2 * lim
            # big regime: at most one landing, jstar or jstar-q
            hi = big & (jstar <= lim)
            lo = big & (jstar >= q - lim)
            if hi.any():
                j = jstar[hi]; odd = (j & 1) == 1
                jout.append(j[odd]); qout.append(q[hi][odd])
            if lo.any():
                j = jstar[lo] - q[lo]; odd = (j & 1) == 1
                jout.append(j[odd]); qout.append(q[lo][odd])
            # small regime (only when Q < 2(L-1)): every landing in window
            sm = ~big
            if sm.any():
                for qq, jj in zip(q[sm].tolist(), jstar[sm].tolist()):
                    start = jj - qq * ((jj + lim) // qq)
                    land = np.arange(start, lim + 1, qq, dtype=np.int64)
                    land = land[(land & 1) == 1]
                    if len(land):
                        jout.append(land)
                        qout.append(np.full(len(land), qq, np.int64))
        if not jout:
            return (np.empty(0, np.int64), np.empty(0, np.int64))
        return np.concatenate(jout), np.concatenate(qout)

    def filter(self, js_alive, t, n0=None, certify=True):
        """Deep-sieve a survivor list. Returns (surviving js, kills_in_set).
        certify=True re-proves every effective kill by explicit divisibility
        on the reconstructed n0 (mpz) -- E-invariance enforced at runtime."""
        js_alive = np.asarray(js_alive, dtype=np.int64)
        L = self.L
        bmp = np.zeros(L, dtype=bool)
        bmp[(js_alive + (L - 1)) >> 1] = True
        jk, qk = self.kills(t)
        if len(jk):
            inset = bmp[(jk + (L - 1)) >> 1]
            jk, qk = jk[inset], qk[inset]
        if certify and len(jk):
            assert n0 is not None, "certification needs n0"
            n0 = gmpy2.mpz(n0)
            for j, q in zip(jk.tolist(), qk.tolist()):
                assert (n0 + j) % q == 0, \
                    f"DEEPSIEVE CERT FAIL: q={q} does not divide n0+{j}"
        if len(jk):
            bmp[(jk + (L - 1)) >> 1] = False
        keep = bmp[(js_alive + (L - 1)) >> 1]
        self.n_kills += int(len(jk)); self.n_lifts += 1
        return js_alive[keep], int(len(jk))

    def mertens_factor(self):
        return math.log(self.Q) / math.log(self.deep_q)


# ------------------------------------------------------------------ CLI ---
def _load_arch(path):
    ns = {}
    src = open(path).read().replace(
        'if __name__ == "__main__":\n    main()', "")
    exec(compile(src, path, "exec"), ns)
    return ns


def _build(arch, a):
    swap = [int(x) for x in a.swap.split(",") if x]
    dz = arch["design"](a.digits, a.zd, a.L, a.Q, swap, a.seed, verbose=False)
    arch["prep_lift"](dz)
    if a.lift_seed is not None:
        import random
        dz["rng"] = random.Random(a.lift_seed)
    return dz


def cmd_selftest(a):
    """Exhaustive small-D gate: brute force is the referee."""
    arch = _load_arch(a.arch)
    # Q=2000 < 2(L-1) so BOTH landing regimes are exercised.
    D, zd, L, Q, DQ = 120, 97, 2000, 2000, 100_000
    dz = arch["design"](D, zd, L, Q, [3, 5, 7], 1, verbose=False)
    arch["prep_lift"](dz)
    ds = DeepSieve(dz, DQ, cache_dir=a.cache, verbose=False)
    ok = True
    for trial in range(a.trials):
        k, t = arch["crt_lift"](dz)
        n0 = gmpy2.mpz(k) * dz["P_eff"]
        js = arch["incidental_survivors"](dz, t)
        surv, nk = ds.filter(js, t, n0=n0, certify=True)
        # referee 1: brute-force kill set by direct trial division
        br = set()
        for j in np.asarray(js, np.int64).tolist():
            c = n0 + j
            for q in ds.q.tolist():
                if c % q == 0:
                    br.add(j); break
        mine = set(np.asarray(js, np.int64).tolist()) - set(surv.tolist())
        if br != mine:
            print(f"  trial {trial}: KILL-SET MISMATCH "
                  f"(brute {len(br)} vs sieve {len(mine)}, "
                  f"diff {sorted(br ^ mine)[:6]})"); ok = False
        # referee 2: no final survivor has a deep factor
        for j in surv.tolist():
            c = n0 + j
            for q in ds.q.tolist():
                if c % q == 0:
                    print(f"  trial {trial}: MISSED KILL j={j} q={q}")
                    ok = False; break
    # referee 3: residues vs gmpy2 for a huge multi-limb t
    thuge = int(gmpy2.mpz(2) ** 200 + 12345)
    khuge = int(dz["crt_r"] + dz["crt_M"] * (dz["crt_t0"] + thuge))
    n0h = gmpy2.mpz(khuge) * dz["P_eff"]
    got = ds.n0_mod(thuge)
    idx = np.random.default_rng(7).choice(len(ds.q), 4000, replace=False)
    for i in idx.tolist():
        if int(n0h % int(ds.q[i])) != int(got[i]):
            print(f"  huge-t residue mismatch at q={ds.q[i]}"); ok = False
            break
    # referee 4: pi(x) anchors on the segmented sieve
    for hi in (10**5, 10**6):
        n = len(primes_range(0, hi, None))
        if n != PI[hi]:
            print(f"  pi({hi}) = {n} != {PI[hi]}"); ok = False
    print("SELFTEST", "PASS" if ok else "FAIL",
          f"({a.trials} trials, both landing regimes, huge-t, pi anchors)")
    sys.exit(0 if ok else 1)


def cmd_bench(a):
    arch = _load_arch(a.arch)
    print(f"bench: D={a.digits} zd={a.zd} L={a.L} Q={a.Q:,} "
          f"deep_q={a.deep_q:,}")
    t0 = time.time()
    dz = _build(arch, a)
    print(f"  design+prep [{time.time()-t0:.1f}s], "
          f"design survivors {int(dz['alive'].sum()):,}")
    t0 = time.time()
    ds = DeepSieve(dz, a.deep_q, cache_dir=a.cache, block=a.block)
    print(f"  DeepSieve init [{time.time()-t0:.1f}s], disk tables "
          f"~{4*ds.nq*4/1e6:.0f} MB int32, runtime ~"
          f"{6*min(a.block, ds.nq)*8/1e6:.0f} MB/block")
    pred = ds.mertens_factor()
    cuts, tsv, tds = [], [], []
    for i in range(a.lifts):
        k, t = arch["crt_lift"](dz)
        n0 = gmpy2.mpz(k) * dz["P_eff"]
        t1 = time.time()
        js = arch["incidental_survivors"](dz, t)
        t2 = time.time()
        surv, nk = ds.filter(js, t, n0=n0, certify=not a.no_certify)
        t3 = time.time()
        cuts.append(len(surv) / len(js)); tsv.append(t2 - t1)
        tds.append(t3 - t2)
        print(f"  lift {i+1}: shallow {len(js):,} -> deep {len(surv):,} "
              f"(cut {cuts[-1]:.4f}, {nk} kills certified) "
              f"shallow {tsv[-1]:.2f}s deep {tds[-1]:.2f}s")
    m = float(np.mean(cuts))
    print(f"  mean cut {m:.4f} vs Mertens lnQ/lnQ' = {pred:.4f} "
          f"({len(cuts)} lifts)  |  deep sieve {np.mean(tds):.2f}s/lift, "
          f"shallow {np.mean(tsv):.2f}s/lift  |  GPU tests/lift x{1/m:.2f} "
          f"fewer")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["selftest", "bench"])
    ap.add_argument("--arch", default="architect_v2.py")
    ap.add_argument("--digits", type=int, default=2700)
    ap.add_argument("--zd", type=int, default=401)
    ap.add_argument("--L", type=int, default=62000)
    ap.add_argument("--Q", type=int, default=200_000)
    ap.add_argument("--swap", default="3,5,7,11,13,17,19,23,29")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lift-seed", type=int, default=None)
    ap.add_argument("--deep-q", type=int, default=10**8)
    ap.add_argument("--lifts", type=int, default=5)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--block", type=int, default=4_000_000)
    ap.add_argument("--cache", default=".ds_cache")
    ap.add_argument("--no-certify", action="store_true")
    a = ap.parse_args()
    (cmd_selftest if a.cmd == "selftest" else cmd_bench)(a)


if __name__ == "__main__":
    main()
