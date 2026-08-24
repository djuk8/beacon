#!/usr/bin/env python3
"""STUB -- a minimal early-exit orchestrator with the CLI/file contract that
gate_o1.sh v1.1 assumed for ~/beacon/p3/ee_drive.py.  Exists ONLY so the
harness can be dry-run end to end.  Contract (as assumed by the harness):
  ee_drive.py IN.bin OUT.v.bin --driver DRV --gpu G --chunk C --lock L
  reads IN.manifest.json (IN path with .bin -> .manifest.json): ks, sizes
  (per-k candidate counts, contiguous in IN.bin in manifest order)
  writes OUT.v.bin (<IIQ>(MAGIC_V,bits,n) + verdicts; skipped = 0x03 here)
  writes IN.tested.json: tested_per_k (list), waves, tested_total, marker
If the real ee_drive differs, the HARNESS is what must be re-read, not this."""
import sys, os, struct, json, argparse, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--driver", required=True); ap.add_argument("--gpu", default="0")
ap.add_argument("--chunk", type=int, default=8); ap.add_argument("--lock", default="/tmp/ee.lock")
a = ap.parse_args()
MAGIC_C, MAGIC_V, SKIP = 0x31433247, 0x31563247, 0x03
b = open(a.src, "rb").read(); mg, bits, n = struct.unpack("<IIQ", b[:16]); nb = bits // 8; body = b[16:]
man = json.load(open(a.src[:-4] + ".manifest.json")); sizes = man["sizes"]
offs = [0]
for s in sizes: offs.append(offs[-1] + s)
verd = bytearray([SKIP]) * n; tested = [0] * len(sizes); alive = [True] * len(sizes); waves = 0
env = dict(os.environ, CUDA_VISIBLE_DEVICES=a.gpu)
while any(alive):
    sel = []
    for ki, s in enumerate(sizes):
        if not alive[ki]: continue
        lo = offs[ki] + tested[ki]; hi = min(offs[ki] + s, lo + a.chunk)
        sel += list(range(lo, hi))
    if not sel: break
    tmp = a.src[:-4] + f".w{waves}.bin"; tv = tmp[:-4] + ".v.bin"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, len(sel)))
        for i in sel: f.write(body[i*nb:(i+1)*nb])
    r = subprocess.run([a.driver, tmp, tv], env=env, capture_output=True)
    if r.returncode != 0: sys.stderr.write(r.stderr.decode()); sys.exit(4)
    vv = open(tv, "rb").read()[16:]
    for i, vb in zip(sel, vv): verd[i] = vb
    os.remove(tmp); os.remove(tv); waves += 1
    for ki, s in enumerate(sizes):
        if not alive[ki]: continue
        lo = offs[ki] + tested[ki]; hi = min(offs[ki] + s, lo + a.chunk)
        tested[ki] = hi - offs[ki]
        if any(verd[i] in (1, 2) for i in range(lo, hi)) or tested[ki] >= s: alive[ki] = False
with open(a.dst, "wb") as f:
    f.write(struct.pack("<IIQ", MAGIC_V, bits, n)); f.write(bytes(verd))
json.dump(dict(tested_per_k=tested, waves=waves, tested_total=sum(tested), marker=SKIP),
          open(a.src[:-4] + ".tested.json", "w"))
