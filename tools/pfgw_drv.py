#!/usr/bin/env python3
"""pfgw_drv.py -- CPU driver for scanhunt bins via PFGW/gwnum.
Drop-in replacement for g1_fermat at heights beyond the GPU classes: reads the
same candidate .bin, writes the same .v.bin, so make/fold/finish and
every gate work unchanged.

  python3 pfgw_drv.py cand.bin verdict.bin --pfgw ~/pfgw/pfgw64 -j 60

Design notes (paid for by the benchmark session):
* PFGW segfaults AT EXIT when it cannot write pfgw.ini -- results are
  already printed. We therefore PARSE STDOUT for the verdict line and
  IGNORE exit codes entirely.
* One pfgw process per shard (few hundred candidates each), fed via a
  -q call per candidate would cost a process spawn per test; instead we
  use PFGW's file mode: one decimal number per line, one process per
  shard, verdicts parsed from the combined log.
* Verdict semantics match g1_fermat: byte 1 = probable prime (PFGW
  "is a probable prime" / 3-PRP), byte 0 = composite. GEC has no
  analogue here; gwnum's own roundoff checks stand in.
* Work runs in a private tmp dir (writable => no ini warnings).
"""
import argparse, os, re, struct, subprocess, sys, tempfile, time
sys.set_int_max_str_digits(3000000)
from concurrent.futures import ThreadPoolExecutor

def run_shard(pfgw, lines, workdir, idx):
    # PFGW's ABC reader rejects long decimal literals (measured), so one
    # -q call per candidate: spawn cost is nothing next to big-FFT tests,
    # and each process maps 1:1 to a verdict -- no count matching at all.
    sd = os.path.join(workdir, f"s{idx:04d}")   # private cwd: ini/log isolation
    os.makedirs(sd, exist_ok=True)
    verd = []
    for cand in lines:
        v = None
        for _ in range(2):                       # one retry on unparsable output
            out = subprocess.run([pfgw, "-f0", "-b2", "-q" + cand],
                                 capture_output=True, text=True, cwd=sd).stdout
            for ln in (x.replace("\r", "") for x in out.splitlines()):
                if " is composite" in ln: v = 0; break
                if "PRP!" in ln or "probable prime" in ln: v = 1; break
            if v is not None: break
        if v is None:
            return idx, None                     # caller refuses loudly
        verd.append(v)
    return idx, verd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand"); ap.add_argument("verdict")
    ap.add_argument("--pfgw", default="pfgw64")
    ap.add_argument("-j", type=int, default=os.cpu_count() or 8)
    ap.add_argument("--shard", type=int, default=200,
                    help="candidates per pfgw process")
    a = ap.parse_args()
    t0 = time.time()
    with open(a.cand, "rb") as f:
        magic, bits, count = struct.unpack("<IIQ", f.read(16))
        nb = bits // 8
        cands = [str(int.from_bytes(f.read(nb), "little"))
                 for _ in range(count)]
    shards = [cands[i:i+a.shard] for i in range(0, len(cands), a.shard)]
    verdicts = bytearray(count)
    bad = []
    with tempfile.TemporaryDirectory(prefix="pfgwdrv_") as wd, \
         ThreadPoolExecutor(max_workers=a.j) as ex:
        futs = [ex.submit(run_shard, a.pfgw, sh, wd, i)
                for i, sh in enumerate(shards)]
        for fu in futs:
            i, v = fu.result()
            if v is None: bad.append(i); continue
            off = i * a.shard
            verdicts[off:off+len(v)] = bytes(v)
    if bad:
        print(f"FATAL: shards {bad} returned mismatched verdict counts "
              f"(pfgw output drift) -- refusing to emit", file=sys.stderr)
        sys.exit(3)
    with open(a.verdict, "wb") as f:
        f.write(struct.pack("<IIQ", 0x31563247, bits, count))
        f.write(bytes(verdicts))
    prp = sum(verdicts)
    dt = time.time() - t0
    print(f"pfgw_drv[CPU]: bits={bits} count={count} | {dt:.1f}s | "
          f"{count/dt:.1f} tests/s | prp={prp} shards={len(shards)} j={a.j}")

if __name__ == "__main__":
    main()
