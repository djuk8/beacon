#!/usr/bin/env python3
"""ee_serve.py v2.1 (driver-ee takes the GPU lock itself, GPU phase only) (--driver-ee: g1_fermat_v3 in-driver early exit, one process per mega-ring; --rm-bins) (gather lock: one r1 feeder collects at a time) (shm cleanup only for dead owner PIDs -- sibling start-up wiped a live wave dir; --lanes r1|hi|both per process) (hi-lane launches unlocked -- no convoy behind rung-1 waves; run N processes per card with --workers 1, not threads: GIL) (two lanes: rung-1 batched to kwin/tmax, rungs>=2 fire after tmax_hi -- the 20 s per-rung round trip was eating the loop cycle) (v1.1 worker died on a glob/stat race against a sibling claim -- fixed; workers log and continue) -- per-card FEEDER for the raid (BEACON O1).  C, 2026-08-21.
The driver binary is unchanged.  Loops make rings exactly as before; instead
of launching the driver themselves they drop a REQUEST in the card's queue
and wait for the verdict file.  The feeder gathers requests into a MEGA-RING
(>= --kwin windows or --tmax seconds, whichever first), runs per-k early-exit
waves (chunk schedule --chunk/--growth) with the unchanged binary, scatters
verdicts back and writes each ring's v.bin ATOMICALLY at the path the loop
expects.  Skipped positions carry --marker (0x03); the fold accepts it.

QUEUE PROTOCOL (filesystem, per card, all renames are atomic):
  <queue>/req/<name>.json      written by the loop: {"bin": abs, "out": abs, "seed", "round", "bid"}
  <queue>/claimed/<name>.json  feeder claimed it (rename)  -- the loop may CANCEL only while still in req/
  <queue>/done/<name>.json     verdict written, accounting inside
  <queue>/failed/<name>.json   driver failure; loop falls back to its legacy launch
  <queue>/ledger.jsonl         one line per ring: tested/skip accounting (beta_eff estimator input)
Manifest is <bin stem>.manifest.json (sizes = per-k counts, contiguous in bin).
Wave files live in /dev/shm, never in the hunt dirs.  Each launch is taken
under flock(--lock) so a loop's legacy fallback launch serialises with us.
Exit never on purpose: SIGTERM finishes the mega-ring in flight, re-queues
the rest, and exits.  On start, stale claimed/ entries are re-queued.
"""
import sys, os, json, struct, time, argparse, subprocess, tempfile, shutil, mmap, signal, threading, glob, fcntl
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
STOP = threading.Event()

def log(msg): sys.stderr.write(f"{time.strftime('%m-%d %H:%M:%S')} ee_serve: {msg}\n"); sys.stderr.flush()

def schedule(chunk, growth, S):
    b = [0]; c = float(chunk)
    while b[-1] < S:
        b.append(min(S, b[-1] + max(1, int(round(c))))); c = c * growth if growth > 1 else c
    return b

class Ring:
    def __init__(self, req_path, req):
        self.req_path, self.req = req_path, req
        self.bin = req["bin"]; self.out = req["out"]
        stem = self.bin[:-4] if self.bin.endswith(".bin") else self.bin
        self.man = json.load(open(req.get("man") or stem + ".manifest.json"))
        self.sizes = [int(s) for s in self.man["sizes"]]
        self.f = open(self.bin, "rb"); hdr = self.f.read(16)
        mg, self.bits, self.n = struct.unpack("<IIQ", hdr)
        if mg != MAGIC_C or sum(self.sizes) != self.n: raise ValueError(f"bad ring {self.bin}: magic 0x{mg:08x} n={self.n} sum={sum(self.sizes)}")
        self.nb = self.bits // 8
        if os.fstat(self.f.fileno()).st_size != 16 + self.n * self.nb: raise ValueError(f"bad length {self.bin}")
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        self.off = [16]
        for s in self.sizes: self.off.append(self.off[-1] + s * self.nb)
        self.voff = [0]
        for s in self.sizes: self.voff.append(self.voff[-1] + s)
    def close(self):
        try: self.mm.close(); self.f.close()
        except Exception: pass

def run_mega(rings, a, lockpath, tag, use_lock=True):
    """early-exit waves over a list of Ring; returns per-ring (verdict bytes, tested list)."""
    bits = rings[0].bits; nb = rings[0].nb
    for r in rings:
        if r.bits != bits: raise ValueError("mixed bit sizes in one mega-ring")
    ks = [(ri, k) for ri, r in enumerate(rings) for k in range(len(r.sizes))]
    size = [rings[ri].sizes[k] for ri, k in ks]
    verd = [bytearray([a.marker]) * r.n for r in rings]
    tested = [0] * len(ks); alive = [True] * len(ks)
    S = max(size); b = schedule(a.chunk, a.growth, S)
    tmpdir = tempfile.mkdtemp(prefix=f"ees_c{a.gpu}_p{os.getpid()}_{tag}_", dir=a.tmp)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(a.gpu))
    launches = 0; t_drv = 0.0; t_lock = 0.0
    try:
        for w in range(1, len(b)):
            sel = []
            for i, (ri, k) in enumerate(ks):
                if not alive[i]: continue
                lo = tested[i]; hi = min(size[i], b[w])
                if hi > lo: sel.append((i, lo, hi))
            if not sel: break
            m = sum(hi - lo for _, lo, hi in sel)
            wb = os.path.join(tmpdir, f"w{w}.bin"); wv = wb[:-4] + ".v.bin"
            with open(wb, "wb") as f:
                f.write(struct.pack("<IIQ", MAGIC_C, bits, m))
                for i, lo, hi in sel:
                    ri, k = ks[i]; r = rings[ri]
                    f.write(r.mm[r.off[k] + lo * nb: r.off[k] + hi * nb])
            t0 = time.time()
            if use_lock:
                with open(lockpath, "w") as lk:
                    fcntl.flock(lk, fcntl.LOCK_EX); t1 = time.time(); t_lock += t1 - t0
                    rr = subprocess.run([a.driver, wb, wv], env=env, capture_output=True)
                    t_drv += time.time() - t1
            else:                                           # hi lane: tiny launches time-slice beside the big wave; no convoy
                t1 = time.time(); rr = subprocess.run([a.driver, wb, wv], env=env, capture_output=True); t_drv += time.time() - t1
            launches += 1
            if rr.returncode != 0 or not os.path.exists(wv):
                e = rr.stderr.decode(errors="replace"); raise RuntimeError(f"driver rc={rr.returncode} wave {w} batch {m}: {e[:300]!r} .. {e[-300:]!r}")
            vb = open(wv, "rb").read(); vmg, vbits, vn = struct.unpack("<IIQ", vb[:16]); vv = vb[16:]
            if vmg != MAGIC_V or vbits != bits or vn != m or len(vv) != m: raise RuntimeError(f"verdict contract violated on wave {w}")
            pos = 0
            for i, lo, hi in sel:
                ri, k = ks[i]; r = rings[ri]; wd = hi - lo; sl = vv[pos:pos + wd]; pos += wd
                verd[ri][r.voff[k] + lo: r.voff[k] + hi] = sl; tested[i] = hi
                if 1 in sl or 2 in sl or hi >= size[i]: alive[i] = False
            os.remove(wb); os.remove(wv)
            if a.verbose: log(f"{tag} wave {w}/{len(b)-1}: batch {m:,} ks {len(sel):,} alive {sum(alive):,} driver {t_drv:.2f}s")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    per_ring = []
    i0 = 0
    for ri, r in enumerate(rings):
        n = len(r.sizes); per_ring.append((verd[ri], tested[i0:i0 + n])); i0 += n
    return per_ring, dict(launches=launches, driver_s=round(t_drv, 3), lock_wait_s=round(t_lock, 3), waves=len(b) - 1, schedule=b)

def run_mega_ee(rings, a, lockpath, tag, use_lock=True):
    """v3 in-driver early exit: one process per mega-ring (--bins list + sizes sidecar). Same outputs as run_mega."""
    import numpy as np
    bits = rings[0].bits
    for r in rings:
        if r.bits != bits: raise ValueError("mixed bit sizes in one mega-ring")
    tmpdir = tempfile.mkdtemp(prefix=f"ees_c{a.gpu}_p{os.getpid()}_{tag}_", dir=a.tmp)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(a.gpu)); t_lock = 0.0
    try:
        lst = os.path.join(tmpdir, "list.txt"); szp = os.path.join(tmpdir, "sizes.bin"); out = os.path.join(tmpdir, "mega.v.bin")
        with open(lst, "w") as f: f.write("".join(r.bin + "\n" for r in rings))
        allsz = [s for r in rings for s in r.sizes]
        with open(szp, "wb") as f: f.write(struct.pack("<II", 0x31533247, len(allsz)) + struct.pack(f"<{len(allsz)}I", *allsz))
        cmd = [a.driver_ee, lst, out, "--bins", "--ee", szp, "--chunk", str(a.chunk), "--growth", str(a.growth), "--marker", str(a.marker)]
        if use_lock: cmd += ["--lock", lockpath]            # the driver locks only around its GPU phase: loading overlaps siblings' waves
        t1 = time.time(); rr = subprocess.run(cmd, env=env, capture_output=True)
        t_drv = time.time() - t1
        err = rr.stderr.decode(errors="replace")
        if rr.returncode != 0 or not os.path.exists(out): raise RuntimeError(f"driver-ee rc={rr.returncode}: {err[-400:]!r}")
        vb = open(out, "rb").read(); vmg, vbits, vn = struct.unpack("<IIQ", vb[:16]); body = np.frombuffer(vb, dtype=np.uint8, offset=16)
        ntot = sum(r.n for r in rings)
        if vmg != MAGIC_V or vbits != bits or vn != ntot or len(body) != ntot: raise RuntimeError("verdict contract violated (ee)")
        import re
        m = re.search(r"waves=(\d+)", err); waves = int(m.group(1)) if m else -1
        per_ring = []; off = 0
        for r in rings:
            arr = body[off:off + r.n]; off += r.n
            ismark = (arr == a.marker).astype(np.int64)
            cnt = np.add.reduceat(ismark, np.array(r.voff[:-1], dtype=np.int64)) if r.n else np.zeros(0, dtype=np.int64)
            tested = [int(s - c) for s, c in zip(r.sizes, cnt)]
            per_ring.append((bytearray(arr.tobytes()), tested))
        return per_ring, dict(launches=1, driver_s=round(t_drv, 3), lock_wait_s=round(t_lock, 3), waves=waves, schedule=None)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def write_atomic_bytes(path, data):
    part = path + ".part"
    with open(part, "wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(part, path)

def move(src, dstdir):
    dst = os.path.join(dstdir, os.path.basename(src))
    try: os.rename(src, dst); return dst
    except FileNotFoundError: return None

def mt(p):
    try: return os.path.getmtime(p)
    except OSError: return float("inf")                  # claimed by a sibling between glob and stat

def peek_round(p):
    try: return int(json.load(open(p)).get("round") or 1)
    except Exception: return None                        # vanished or unreadable: skip this pass

def gather(a, qd):
    """r1 lane gathers under a per-queue GATHER LOCK so sibling feeders do not split the arrivals into tiny mega-rings."""
    lk = None
    try:
        if a.lanes != "hi":
            lk = open(os.path.join(qd, "gather.lock"), "w"); fcntl.flock(lk, fcntl.LOCK_EX)
        return _gather(a, qd)
    finally:
        if lk:
            try: fcntl.flock(lk, fcntl.LOCK_UN); lk.close()
            except Exception: pass

def _gather(a, qd):
    """Two lanes.  HI lane = rungs >= 2 (tiny rings): claim everything waiting once the oldest is >= tmax_hi old.
    R1 lane = rung-1 rings: claim until kwin windows or tmax since the oldest.  Returns list of claimed paths."""
    t_first = None; claimed = []; wins = 0; lane = None
    while not STOP.is_set():
        reqs = sorted(glob.glob(os.path.join(qd, "req", "*.json")), key=mt)
        now = time.time()
        if lane is None:
            hi = [p for p in reqs if peek_round(p) not in (None, 1)]
            if a.lanes == "hi": lane = "hi" if hi and (now - mt(hi[0]) >= a.tmax_hi or len(hi) >= a.nmax) else None
            elif a.lanes == "r1": lane = "r1"
            elif hi and (now - mt(hi[0]) >= a.tmax_hi or len(hi) >= a.nmax): lane = "hi"
            else: lane = "r1"
            if lane is None: time.sleep(a.poll); continue
        pool = [p for p in reqs if (peek_round(p) not in (None, 1)) == (lane == "hi")]
        for p in pool:
            if (lane == "r1" and wins >= a.kwin) or len(claimed) >= a.nmax: break
            c = move(p, os.path.join(qd, "claimed"))
            if not c: continue                       # loop cancelled it first
            try:
                req = json.load(open(c)); w = int(req.get("ks") or 0)
                if not w:
                    w = len(json.load(open((req.get("man") or req["bin"][:-4] + ".manifest.json")))["sizes"])
            except Exception as e:
                log(f"bad request {c}: {e}"); move(c, os.path.join(qd, "failed")); continue
            claimed.append(c); wins += w
            if t_first is None: t_first = time.time()
        if lane == "hi" and claimed: break                              # tiny rings: go now
        if lane == "r1" and claimed and (wins >= a.kwin or len(claimed) >= a.nmax or time.time() - t_first >= a.tmax): break
        if not claimed: lane = None                                     # re-decide the lane next pass
        time.sleep(a.poll)
    return claimed, lane

def serve_once(a, qd, lockpath, tag):
    claimed, lane = gather(a, qd)
    if not claimed: return 0
    rings = []; bad = []
    for c in claimed:
        try: rings.append(Ring(c, json.load(open(c))))
        except Exception as e:
            log(f"{tag} unreadable ring {c}: {e}"); bad.append(c)
    for c in bad: move(c, os.path.join(qd, "failed"))
    if not rings: return 0
    # one mega-ring per bit size (production is all 2048; gates mix fixtures)
    groups = {}
    for r in rings: groups.setdefault(r.bits, []).append(r)
    done_n = 0
    for bits, grp in groups.items():
        done_n += serve_group(a, qd, lockpath, f"{tag}{lane}b{bits}", grp, use_lock=(lane != "hi"))
    return done_n

def serve_group(a, qd, lockpath, tag, rings, use_lock=True):
    t0 = time.time()
    try:
        per_ring, stats = (run_mega_ee if a.driver_ee else run_mega)(rings, a, lockpath, tag, use_lock)
    except Exception as e:
        log(f"{tag} MEGA-RING FAILED ({len(rings)} rings): {e}")
        for r in rings:
            r.close(); move(r.req_path, os.path.join(qd, "failed"))
        return 0
    wall = time.time() - t0
    ntest = 0; ntot = 0
    for r, (vb, tk) in zip(rings, per_ring):
        write_atomic_bytes(r.out, struct.pack("<IIQ", MAGIC_V, r.bits, r.n) + bytes(vb))
        prp_ks = sum(1 for k in range(len(r.sizes)) if (1 in vb[r.voff[k]:r.voff[k] + tk[k]] or 2 in vb[r.voff[k]:r.voff[k] + tk[k]]))
        rec = dict(ts=round(time.time(), 3), card=a.gpu, seed=r.req.get("seed"), round=r.req.get("round"), bid=r.req.get("bid"),
                   ks=len(r.sizes), n=r.n, tested=sum(tk), prp_ks=prp_ks, survivors=len(r.sizes) - prp_ks, marker=a.marker,
                   mega=tag, mega_rings=len(rings), mega_launches=stats["launches"], mega_wall_s=round(wall, 3))
        with open(os.path.join(qd, "ledger.jsonl"), "a") as lf: lf.write(json.dumps(rec) + "\n")
        ntest += sum(tk); ntot += r.n
        r.req["done"] = rec; r.close()
        if a.rm_bins:
            try: os.remove(r.bin)                       # verdict is on disk; the loop's rm -f tolerates absence
            except OSError: pass
        json.dump(r.req, open(r.req_path + ".part", "w")); os.replace(r.req_path + ".part", r.req_path)
        move(r.req_path, os.path.join(qd, "done"))
    log(f"{tag} {len(rings)} rings, {ntot:,} cands -> tested {ntest:,} ({ntest/max(ntot,1):.3f}), {stats['launches']} launches, driver {stats['driver_s']}s, wall {wall:.1f}s, {ntest/max(wall,1e-6):,.0f} t/s")
    return len(rings)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", required=True); ap.add_argument("--gpu", required=True); ap.add_argument("--driver", required=True)
    ap.add_argument("--kwin", type=int, default=330000, help="windows per mega-ring before launching"); ap.add_argument("--nmax", type=int, default=400)
    ap.add_argument("--tmax", type=float, default=20.0, help="rung-1 lane: max seconds the oldest request waits")
    ap.add_argument("--tmax-hi", dest="tmax_hi", type=float, default=1.5, help="rungs>=2 lane: fire once the oldest request is this old"); ap.add_argument("--poll", type=float, default=0.25)
    ap.add_argument("--chunk", type=int, default=6); ap.add_argument("--growth", type=float, default=1.15)
    ap.add_argument("--marker", type=lambda s: int(s, 0), default=0x03); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--lock", default=None); ap.add_argument("--tmp", default="/dev/shm" if os.path.isdir("/dev/shm") else None)
    ap.add_argument("--lanes", choices=("both", "r1", "hi"), default="both", help="which requests this process serves")
    ap.add_argument("--driver-ee", dest="driver_ee", default=None, help="g1_fermat_v3 with --ee: one process per mega-ring (in-driver waves); omit for the v2 wave path")
    ap.add_argument("--rm-bins", dest="rm_bins", type=int, default=1, help="1 = delete each candidate bin once its verdict is written (disk footprint)")
    ap.add_argument("--once", action="store_true", help="serve one mega-ring per worker then exit (gates)"); ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    if a.marker in (0, 1, 2): sys.exit("marker would be read as a real verdict")
    a.driver = os.path.expanduser(a.driver)
    if a.driver_ee: a.driver_ee = os.path.expanduser(a.driver_ee)
    qd = a.queue; lockpath = a.lock or f"/tmp/raidgpu{a.gpu}.lock"
    for d in ("req", "claimed", "done", "failed"): os.makedirs(os.path.join(qd, d), exist_ok=True)
    # clean this card's wave leftovers from a previous life (never another card's), then re-queue stale claims
    import re as _re
    for d in glob.glob(os.path.join(a.tmp or "/tmp", f"ees_c{a.gpu}_p*")):
        m = _re.search(r"_p(\d+)_", os.path.basename(d)); pid = int(m.group(1)) if m else 0
        if pid and os.path.exists(f"/proc/{pid}"): continue            # a live sibling's wave dir: leave it
        shutil.rmtree(d, ignore_errors=True)
    for d in glob.glob(os.path.join(a.tmp or "/tmp", f"ees_c{a.gpu}_c*")): shutil.rmtree(d, ignore_errors=True)   # pre-v1.5 naming, always stale
    # re-queue stale claims from a previous life
    for c in glob.glob(os.path.join(qd, "claimed", "*.json")):
        log(f"re-queue stale claim {os.path.basename(c)}"); move(c, os.path.join(qd, "req"))
    signal.signal(signal.SIGTERM, lambda *x: STOP.set()); signal.signal(signal.SIGINT, lambda *x: STOP.set())
    log(f"card {a.gpu} lanes {a.lanes} queue {qd} driver {a.driver} driver_ee {a.driver_ee} rm_bins {a.rm_bins} kwin {a.kwin} tmax {a.tmax}s tmax_hi {a.tmax_hi}s chunk {a.chunk} growth {a.growth} workers {a.workers} lock {lockpath}")
    def worker(wi):
        n = 0
        while not STOP.is_set():
            try:
                got = serve_once(a, qd, lockpath, f"c{a.gpu}p{os.getpid()%10000}w{wi}m{n}")
            except Exception as e:                        # a worker never dies silently
                import traceback; log(f"worker {wi} exception: {e!r}\n{traceback.format_exc()[-600:]}"); time.sleep(1); continue
            if got: n += 1
            if a.once and got: break
            if not got: time.sleep(a.poll)
    ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(a.workers)]
    for t in ths: t.start()
    for t in ths: t.join()
    log("exit")

if __name__ == "__main__":
    main()
