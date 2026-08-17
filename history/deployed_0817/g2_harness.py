#!/usr/bin/env python3
"""BEACON G2 harness v3 -- zero-tolerance correctness gate for the G1 driver.

v3 (after two parent-process segfaults on grinder under two different pool
architectures): the reference path uses NO multiprocessing at all. Workers
are independent subprocesses (`python3 g2_harness.py --worker ...`), each
reading its candidate slice from the file and writing a verdict part-file
(tmp+rename). The parent only spawns, polls, folds part-files, and persists
a contiguous-prefix watermark cache (g2r_<bits>.bin) -- any crash resumes.
Candidate generation streams to disk (the parent never holds the list).

Split modes (lets the heavy gmpy2 reference run on shredder's 64 cores):
  --gpu-only    write candidates, run driver, save verdicts, run drill; skip
                the reference/compare stage.
  --check-only  skip the driver; use existing g2v_<bits>.bin, regenerate or
                reuse g2c_<bits>.bin (seed-deterministic), compute reference,
                compare. Only g2v_*.bin (~1 MB total) must travel between
                machines; candidates regenerate identically anywhere.

Container G2-pre (CPU/mpz):   python3 g2_harness.py --driver ./g1_fermat_cpu
Grinder GPU stage:            python3 g2_harness.py --driver ./g1_fermat \
    --plan 2048:600000,4096:300000,8192:100000,16384:30000,32768:8000 \
    --gpu-only
Shredder check stage (after copying g2v_*.bin, same --plan): add --check-only
Exit nonzero on ANY failure.
"""
import argparse, math, os, struct, subprocess, sys, time
import numpy as np, gmpy2

MAGIC_C, MAGIC_V, MAGIC_R = 0x31433247, 0x31563247, 0x31523247

def sieve(n):
    s = np.ones(n + 1, dtype=bool); s[:2] = False
    for i in range(2, int(n ** 0.5) + 1):
        if s[i]: s[i * i::i] = False
    return np.flatnonzero(s).astype(np.int64)

SMALL = [int(p) for p in sieve(10_000)]

def rand_odd(bits, rng):
    return rng.getrandbits(bits - 1) | (1 << (bits - 1)) | 1

def twofactor(bits, rng):
    """product of two ~half-size random odds: composite by construction"""
    h = bits // 2
    p = rng.getrandbits(h - 1) | (1 << (h - 2)) | 1
    q = rng.getrandbits(bits - h) | (1 << (bits - h - 1)) | 1
    n = p * q
    while n.bit_length() > bits: n >>= 1; n |= 1
    return n | 1

def anchored(bits, rng, cache={}):
    """n0 = k * P#(zd) + j -- production candidate shape at this size."""
    if bits not in cache:
        digits = int(bits * 0.30103) - 4
        target = (digits - 8) * math.log(10)
        P, theta, zd = 1, 0.0, 0
        for p in SMALL:
            if theta >= target: break
            P *= p; theta += math.log(p); zd = p
        cache[bits] = (P, zd)
    P, zd = cache[bits]
    while True:
        k = rng.randrange(10 ** 6, 10 ** 7)
        j = rng.randrange(3, 200_000) | 1
        n = k * P + j
        if n.bit_length() >= bits: continue
        if any(n % p == 0 for p in SMALL[:1229]): continue   # trial to 10^4
        return n

def gen_one(bits, i, rng):
    r = i % 4
    return (rand_odd(bits, rng) if r < 2 else
            twofactor(bits, rng) if r == 2 else anchored(bits, rng))

def gen_write(path, bits, count, seed):
    """streamed generation: the parent never holds the candidate list"""
    import random
    rng = random.Random(seed * 1000003 + bits)
    nb = bits // 8
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, count))
        for i in range(count):
            f.write(gen_one(bits, i, rng).to_bytes(nb, "little"))
    os.replace(tmp, path)

def gen_list(bits, count, seed):
    import random
    rng = random.Random(seed * 1000003 + bits)
    return [gen_one(bits, i, rng) for i in range(count)]

def cand_file_ok(path, bits, count):
    try:
        with open(path, "rb") as f:
            m, b, c = struct.unpack("<IIQ", f.read(16))
        return m == MAGIC_C and b == bits and c == count
    except Exception:
        return False

def write_cands(path, bits, cands):
    nb = bits // 8
    with open(path, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, len(cands)))
        for n in cands:
            f.write(n.to_bytes(nb, "little"))

def verdict_file_ok(path, bits, count):
    """complete iff header matches AND size is exactly 16 + count bytes"""
    try:
        if os.path.getsize(path) != 16 + count: return False
        with open(path, "rb") as f:
            m, b, c = struct.unpack("<IIQ", f.read(16))
        return m == MAGIC_V and b == bits and c == count
    except Exception:
        return False

def read_verdicts(path, bits, count):
    with open(path, "rb") as f:
        m, b, c = struct.unpack("<IIQ", f.read(16))
        assert m == MAGIC_V and b == bits and c == count, "verdict header"
        return np.frombuffer(f.read(count), dtype=np.uint8)

def _ref(n):
    return 1 if gmpy2.powmod(2, n - 1, n) == 1 else 0

# ---------------------------------------------------------------- worker --
def worker_main(path, bits, start, cnt, out):
    """independent shard process: read slice from candidate file, write
    verdict bytes to `out` via tmp+rename. No IPC, no shared state."""
    nb = bits // 8
    buf = bytearray(cnt)
    with open(path, "rb") as f:
        f.seek(16 + start * nb)
        for i in range(cnt):
            n = int.from_bytes(f.read(nb), "little")
            buf[i] = 1 if gmpy2.powmod(2, n - 1, n) == 1 else 0
    tmp = out + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes(buf))
    os.replace(tmp, out)

# ------------------------------------------------------------- reference --
def _load_cache(cache, bits, count, ref):
    done = 0
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            hdr = f.read(24)
            if len(hdr) == 24:
                m, b, c, d = struct.unpack("<IIQQ", hdr)
                if m == MAGIC_R and b == bits and c == count and d <= count:
                    done = int(d)
                    ref[:done] = np.frombuffer(f.read(done), dtype=np.uint8)
    return done

def _save_cache(cache, bits, count, ref, done):
    tmp = cache + ".tmp"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<IIQQ", MAGIC_R, bits, count, done))
        f.write(ref[:done].tobytes())
    os.replace(tmp, cache)

def reference_file(path, bits, count, procs, cache):
    """No-multiprocessing reference: shard subprocesses write part files;
    the parent folds them and persists a contiguous-prefix watermark."""
    ref = np.zeros(count, dtype=np.uint8)
    done = _load_cache(cache, bits, count, ref)
    if done:
        print(f"  reference cache: resuming at {done:,}/{count:,}", flush=True)
    if done >= count:
        return ref
    CH = max(32, int(8000 * (2048 / bits) ** 2))
    shards = [(s, min(CH, count - s)) for s in range(done, count, CH)]
    filled = {}                      # start -> length, folded but > watermark
    # fold any leftover part files from a previous crash
    for s, c in shards:
        part = f"{cache}.part_{s}"
        if os.path.exists(part) and os.path.getsize(part) == c:
            with open(part, "rb") as f:
                ref[s:s + c] = np.frombuffer(f.read(), dtype=np.uint8)
            filled[s] = c
            os.remove(part)
    todo = [(s, c) for s, c in shards if s not in filled]
    live, retried = {}, set()
    me = os.path.abspath(__file__)
    def advance(done):
        while done in filled:
            done += filled.pop(done)
        return done
    done = advance(done)
    _save_cache(cache, bits, count, ref, done)
    while todo or live:
        while todo and len(live) < procs:
            s, c = todo.pop(0)
            part = f"{cache}.part_{s}"
            p = subprocess.Popen([sys.executable, me, "--worker", path,
                                  str(bits), str(s), str(c), part])
            live[p.pid] = (p, s, c, part)
        time.sleep(0.2)
        for pid in list(live):
            p, s, c, part = live[pid]
            rc = p.poll()
            if rc is None: continue
            del live[pid]
            if rc == 0 and os.path.exists(part) and os.path.getsize(part) == c:
                with open(part, "rb") as f:
                    ref[s:s + c] = np.frombuffer(f.read(), dtype=np.uint8)
                os.remove(part)
                filled[s] = c
                nd = advance(done)
                if nd != done:
                    done = nd
                    _save_cache(cache, bits, count, ref, done)
            else:
                if s in retried:
                    raise SystemExit(f"reference worker failed twice at "
                                     f"start={s} (rc={rc})")
                retried.add(s)
                todo.insert(0, (s, c))
    _save_cache(cache, bits, count, ref, count)
    return ref

# ------------------------------------------------------------------ gate --
FAILS = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok: FAILS.append(name)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver")
    ap.add_argument("--plan", default="2048:2000,4096:400,8192:80,16384:16,32768:6")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    ap.add_argument("--skip-inject", action="store_true")
    ap.add_argument("--gpu-only", action="store_true",
                    help="candidates + driver + drill; skip reference/compare")
    ap.add_argument("--check-only", action="store_true",
                    help="skip driver; use existing g2v files; reference+compare")
    ap.add_argument("--force", action="store_true",
                    help="re-run the driver even if a complete verdict file exists")
    a = ap.parse_args()
    if not a.check_only and not a.driver:
        ap.error("--driver is required unless --check-only")
    total = 0
    t0 = time.time()

    for spec in a.plan.split(","):
        bits, count = (int(x) for x in spec.split(":"))
        print(f"== class {bits} bits, n={count} ==", flush=True)
        cf, vf = f"g2c_{bits}.bin", f"g2v_{bits}.bin"
        if not cand_file_ok(cf, bits, count):
            gen_write(cf, bits, count, a.seed)
        if not a.check_only:
            if not a.force and verdict_file_ok(vf, bits, count):
                print(f"  complete verdict file exists -- skipping driver "
                      f"(--force to rerun)", flush=True)
            else:
                r = subprocess.run(f"{a.driver} {cf} {vf}", shell=True,
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    print(r.stdout, r.stderr)
                    check(f"{bits} driver ran", False); continue
                print("  " + r.stderr.strip().splitlines()[-1])
        if a.gpu_only:
            v = read_verdicts(vf, bits, count)
            check(f"{bits} verdicts saved, no spurious GEC alarms",
                  int((v == 2).sum()) == 0,
                  f"alarms={int((v == 2).sum())}, prp(GPU)={int((v == 1).sum())}")
            total += count
            continue
        v = read_verdicts(vf, bits, count)
        ref = reference_file(cf, bits, count, a.procs, f"g2r_{bits}.bin")
        alarms = int((v == 2).sum())
        bad = int((v != ref).sum())
        total += count
        check(f"{bits} no spurious GEC alarms", alarms == 0, f"alarms={alarms}")
        check(f"{bits} verdicts byte-exact vs gmpy2", bad == 0,
              f"mismatches={bad}/{count}, prp={int(ref.sum())}")

    if not a.skip_inject and not a.check_only:
        print("== GEC fault-injection drill (2048 bits) ==", flush=True)
        cands = gen_list(2048, 3, a.seed + 7)
        write_cands("g2c_inj.bin", 2048, cands)
        r = subprocess.run(f"{a.driver} g2c_inj.bin g2v_inj.bin --inject 1 3",
                           shell=True, capture_output=True, text=True)
        print("  " + r.stderr.strip().splitlines()[-1])
        v = read_verdicts("g2v_inj.bin", 2048, 3)
        ref = np.array([_ref(n) for n in cands], dtype=np.uint8)
        check("injected candidate raises GEC alarm", v[1] == 2, f"v={list(v)}")
        check("uninjected candidates unaffected",
              v[0] == ref[0] and v[2] == ref[2])

    print()
    if FAILS:
        print(f"G2: {len(FAILS)} FAILURE(S): {FAILS}  [{time.time()-t0:.0f}s]")
        sys.exit(1)
    mode = " [GPU-ONLY: reference stage pending]" if a.gpu_only else ""
    print(f"G2: ALL CHECKS PASS -- {total:,} candidates{mode}  "
          f"[{time.time()-t0:.0f}s]")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        _, _, path, bits, start, cnt, out = sys.argv
        worker_main(path, int(bits), int(start), int(cnt), out)
        sys.exit(0)
    main()
