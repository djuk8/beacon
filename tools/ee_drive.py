#!/usr/bin/env python3
"""ee_drive.py v1.0 -- per-k EARLY EXIT as a composition over the UNCHANGED
g1_fermat_v2 binary (BEACON O1).  C, 2026-08-21.  The binary is never
modified; this script only decides WHICH candidates are sent to it, in waves.

CONTRACT (the same one gate_o1.sh v1.2 and replay_compare.py check):
  ee_drive.py IN.bin OUT.v.bin --driver DRV --gpu G [--chunk 8] [--growth 1.0]
              [--lock FILE] [--tmp DIR] [--marker 3] [--manifest F] [--verbose]
  IN.bin            <IIQ>(MAGIC_C, bits, n) + n candidates, little-endian,
                    bits/8 bytes each, contiguous per k in manifest order
  IN.manifest.json  {"sizes": [...], ...}  sizes[i] = candidate count of k i
  OUT.v.bin         <IIQ>(MAGIC_V, bits, n) + n verdict bytes: the driver's own
                    bytes on every TESTED position (0 composite, 1/2 PRP-class),
                    --marker (default 0x03) on every SKIPPED position
  IN.tested.json    {"tested_per_k": [...], "waves", "launches", "tested_total",
                     "prp_ks", "survivor_ks", "marker", "chunk", "growth",
                     "wall_s", "driver_s", "lock_wait_s"}

SEMANTICS: each k is tested --chunk positions per wave (chunk *= --growth each
wave, rounded, when growth > 1).  A k dies at the first wave that contains a
PRP-class verdict; its remaining positions are never sent to the GPU.  A k with
no PRP (a survivor -- the ones we want) is tested to the end, so its verdict
bytes are byte-identical to a legacy full run.  --chunk 0 = one wave over
everything = legacy-equivalent (A/B control).

SAFETY: wave files live in a private temp dir (default /dev/shm), never in the
ring dir -- no sweep, age-gate or fold can see them.  OUT.v.bin and
IN.tested.json are written atomically (tmp + rename); on any driver failure no
OUT.v.bin is left behind, so the caller's legacy failure path applies unchanged.
Exit: 0 ok | 3 contract error | 4 driver failure.
"""
import sys, os, json, struct, time, argparse, subprocess, tempfile, shutil, mmap
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247

def log(msg): sys.stderr.write(f"ee_drive: {msg}\n"); sys.stderr.flush()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--driver", required=True); ap.add_argument("--gpu", default="0")
    ap.add_argument("--chunk", type=int, default=8, help="positions per k per wave; 0 = no early exit")
    ap.add_argument("--growth", type=float, default=1.0, help="chunk multiplier per wave (>1 = fewer launches, more overshoot)")
    ap.add_argument("--lock", default=None, help="flock this file around each driver launch (per-card serialisation)")
    ap.add_argument("--tmp", default=None, help="private scratch dir (default /dev/shm or $TMPDIR)")
    ap.add_argument("--marker", type=lambda s: int(s, 0), default=0x03, help="verdict byte for skipped positions")
    ap.add_argument("--manifest", default=None); ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    t_start = time.time()
    if a.marker in (0, 1, 2, 0xFF) and a.marker != 0xFF:
        log(f"refusing marker 0x{a.marker:02x}: it would be read as a real verdict"); return 3
    drv = os.path.expanduser(a.driver)
    if not os.access(drv, os.X_OK): log(f"driver not executable: {drv}"); return 3
    stem = a.src[:-4] if a.src.endswith(".bin") else a.src
    man_p = a.manifest or stem + ".manifest.json"
    try:
        man = json.load(open(man_p)); sizes = [int(s) for s in man["sizes"]]
    except Exception as e:
        log(f"manifest unreadable ({man_p}): {e}"); return 3
    fsrc = open(a.src, "rb"); hdr = fsrc.read(16)
    if len(hdr) < 16: log("bin too short"); return 3
    mg, bits, n = struct.unpack("<IIQ", hdr)
    if mg != MAGIC_C: log(f"bin magic 0x{mg:08x} != MAGIC_C 0x{MAGIC_C:08x}"); return 3
    nb = bits // 8
    if sum(sizes) != n: log(f"sum(sizes)={sum(sizes)} != n={n}"); return 3
    if os.fstat(fsrc.fileno()).st_size != 16 + n * nb: log("bin length != header"); return 3
    body = mmap.mmap(fsrc.fileno(), 0, access=mmap.ACCESS_READ)
    K = len(sizes); offs = [16]
    for s in sizes: offs.append(offs[-1] + s * nb)              # byte offsets into the file
    verd = bytearray([a.marker]) * n
    voff = [0]
    for s in sizes: voff.append(voff[-1] + s)                   # verdict offsets
    tested = [0] * K; alive = [True] * K
    chunk = a.chunk if a.chunk > 0 else max(sizes)
    tmpdir = tempfile.mkdtemp(prefix="ee_", dir=a.tmp or ("/dev/shm" if os.path.isdir("/dev/shm") else None))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(a.gpu))
    waves = 0; driver_s = 0.0; lock_wait = 0.0; lockfd = None
    if a.lock:
        import fcntl
        lockfd = os.open(a.lock, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        while True:
            sel = []
            for k in range(K):
                if not alive[k]: continue
                lo = tested[k]; hi = min(sizes[k], lo + chunk)
                if hi > lo: sel.append((k, lo, hi))
            if not sel: break
            m = sum(hi - lo for _, lo, hi in sel)
            wb = os.path.join(tmpdir, f"w{waves}.bin"); wv = os.path.join(tmpdir, f"w{waves}.v.bin")
            with open(wb, "wb") as f:
                f.write(struct.pack("<IIQ", MAGIC_C, bits, m))
                for k, lo, hi in sel:
                    f.write(body[offs[k] + lo * nb: offs[k] + hi * nb])
            if lockfd is not None:
                import fcntl; tl = time.time(); fcntl.flock(lockfd, fcntl.LOCK_EX); lock_wait += time.time() - tl
            td = time.time()
            try:
                r = subprocess.run([drv, wb, wv], env=env, capture_output=True)
            finally:
                if lockfd is not None:
                    import fcntl; fcntl.flock(lockfd, fcntl.LOCK_UN)
            driver_s += time.time() - td
            if r.returncode != 0 or not os.path.exists(wv):
                e = r.stderr.decode(errors="replace")
                log(f"driver rc={r.returncode} on wave {waves} (batch {m}); stderr head: {e[:400]!r} tail: {e[-400:]!r}"); return 4
            vb = open(wv, "rb").read()
            if len(vb) < 16: log(f"wave {waves}: verdict file too short"); return 4
            vmg, vbits, vn = struct.unpack("<IIQ", vb[:16]); vv = vb[16:]
            if vmg != MAGIC_V or vbits != bits or vn != m or len(vv) != m:
                log(f"wave {waves}: verdict header/length contract violated magic=0x{vmg:08x} bits={vbits} n={vn} body={len(vv)}"); return 4
            pos = 0; died = 0
            for k, lo, hi in sel:
                w = hi - lo; sl = vv[pos:pos + w]; pos += w
                verd[voff[k] + lo: voff[k] + hi] = sl
                tested[k] = hi
                if 1 in sl or 2 in sl:
                    alive[k] = False; died += 1
                elif hi >= sizes[k]:
                    alive[k] = False
            os.remove(wb); os.remove(wv); waves += 1
            if a.verbose: log(f"wave {waves}: batch {m} ks {len(sel)} died {died} alive {sum(alive)} driver {time.time()-td:.3f}s")
            if a.growth > 1.0: chunk = max(1, int(round(chunk * a.growth)))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if lockfd is not None: os.close(lockfd)
        body.close(); fsrc.close()
    prp_ks = sum(1 for k in range(K) if (1 in verd[voff[k]:voff[k] + tested[k]] or 2 in verd[voff[k]:voff[k] + tested[k]]))
    # atomic outputs: OUT.v.bin first, then the accounting
    part = a.dst + ".part"
    with open(part, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_V, bits, n)); f.write(bytes(verd)); f.flush(); os.fsync(f.fileno())
    os.replace(part, a.dst)
    acct = dict(tested_per_k=tested, waves=waves, launches=waves, tested_total=sum(tested), prp_ks=prp_ks,
                survivor_ks=K - prp_ks, marker=a.marker, chunk=a.chunk, growth=a.growth,
                wall_s=round(time.time() - t_start, 3), driver_s=round(driver_s, 3), lock_wait_s=round(lock_wait, 3),
                n=n, ks=K, src=os.path.abspath(a.src), driver=drv, gpu=str(a.gpu), version="ee_drive v1.0")
    tpart = stem + ".tested.json.part"
    with open(tpart, "w") as f: json.dump(acct, f); f.flush(); os.fsync(f.fileno())
    os.replace(tpart, stem + ".tested.json")
    log(f"ok ks={K} n={n} tested={sum(tested)} ({sum(tested)/max(n,1):.3f} of legacy) waves={waves} prp_ks={prp_ks} survivors={K-prp_ks} "
        f"wall={acct['wall_s']}s driver={acct['driver_s']}s lock_wait={acct['lock_wait_s']}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
