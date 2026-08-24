#!/usr/bin/env python3
"""replay_compare.py v1.1 (bits + legacy t/s in the report) -- G-O1 step 2 (C, 2026-08-21).
Replay one fossil ring fixture (bin + manifest + legacy v.bin, e.g. the orphan
trios on box1, handoff 18 sec.9) through ee_drive.py and compare against the
legacy full-test verdicts.  Read-only on the fossil: everything is copied to a
scratch dir first (sweep-vs-live doctrine; fossils are never touched).

CONTRACT ASSUMED (same as gate_o1.sh v1.1/v1.2 -- if ee_drive differs, fix
the harness, do not guess):
  bin      : <IIQ>(MAGIC_C,bits,n) + n candidates, contiguous per k in manifest order
  manifest : JSON with "sizes" (per-k candidate counts) [and "ks", "js"]
  v.bin    : <IIQ>(MAGIC_V,bits,n) + n verdict bytes, 0 comp / 1,2 PRP-class / 0xFF untouched
  ee_drive : IN.bin OUT.v.bin --driver DRV --gpu G --chunk C --lock L
             reads IN.manifest.json, writes OUT.v.bin + IN.tested.json {tested_per_k:[...], waves}

Checks (all must hold):
  1. every k with a legacy PRP at index h: ee tested >= h+1, and the skip starts
     at a chunk boundary (or the ring end);
  2. every k with no legacy PRP (the survivors we care about): ee tested == size
     and ee verdicts == legacy verdicts byte-for-byte;
  3. on every tested position the ee verdict == legacy verdict (binary unchanged);
  4. beyond the tested prefix: no PRP-class byte, uniform skip marker (reported).
Reports: tests legacy vs ee (measured saving), ideal constant-chunk saving from
the legacy first-PRP positions, PRP/test rates, ee wall time and (with
--legacy-time) the legacy driver wall time on the same card.

usage: replay_compare.py FIXTURE.bin [--man F.manifest.json] [--legacy F.v.bin]
          [--ee ~/beacon/p3/ee_drive.py] [--driver ~/beacon/p3/g1_fermat_v2]
          [--gpu 0] [--chunk 8] [--legacy-time] [--py /venv/main/bin/python3]
exit 0 PASS / 1 FAIL / 3 contract mismatch
"""
import sys, os, json, struct, shutil, subprocess, time, argparse, collections, tempfile, hashlib
ap = argparse.ArgumentParser()
ap.add_argument("bin"); ap.add_argument("--man"); ap.add_argument("--legacy")
ap.add_argument("--ee", default="~/beacon/p3/ee_drive.py"); ap.add_argument("--driver", default="~/beacon/p3/g1_fermat_v2")
ap.add_argument("--gpu", default="0"); ap.add_argument("--chunk", type=int, default=8)
ap.add_argument("--legacy-time", action="store_true"); ap.add_argument("--py", default=sys.executable)
a = ap.parse_args()
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
stem = a.bin[:-4] if a.bin.endswith(".bin") else a.bin
man_p = a.man or stem + ".manifest.json"; leg_p = a.legacy or stem + ".v.bin"
ee, drv = os.path.expanduser(a.ee), os.path.expanduser(a.driver)
def die(code, msg): print("REPLAY:", msg); sys.exit(code)
for p in (a.bin, man_p, leg_p):
    if not os.path.exists(p): die(3, f"missing {p}")
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
print(f"REPLAY fixture={a.bin} sha={sha(a.bin)} manifest={man_p} legacy={leg_p} sha={sha(leg_p)} chunk={a.chunk}")
man = json.load(open(man_p))
if "sizes" not in man: die(3, f"manifest lacks 'sizes'; keys={list(man)}")
sizes = [int(s) for s in man["sizes"]]
hb = open(a.bin, "rb").read(16); mg, bits, n = struct.unpack("<IIQ", hb)
if mg != MAGIC_C: die(3, f"bin magic 0x{mg:08x} != MAGIC_C")
if sum(sizes) != n: die(3, f"sum(sizes)={sum(sizes)} != n={n}")
lb = open(leg_p, "rb").read(); lmg, lbits, ln = struct.unpack("<IIQ", lb[:16]); leg = lb[16:]
if lmg != MAGIC_V or ln != n or len(leg) != n: die(3, f"legacy v.bin header/length mismatch magic=0x{lmg:08x} n={ln} body={len(leg)}")
# --- scratch copy, run ee_drive ---
scratch = tempfile.mkdtemp(prefix="replay_" + os.path.basename(stem) + "_", dir="/tmp")
sb = os.path.join(scratch, "fix.bin"); shutil.copyfile(a.bin, sb); shutil.copyfile(man_p, os.path.join(scratch, "fix.manifest.json"))
out = os.path.join(scratch, "fix.v.bin"); tj = os.path.join(scratch, "fix.tested.json")
t0 = time.time()
r = subprocess.run([a.py, ee, sb, out, "--driver", drv, "--gpu", a.gpu, "--chunk", str(a.chunk),
                    "--lock", os.path.join(scratch, "ee.lock")], capture_output=True)
t_ee = time.time() - t0
err = r.stderr.decode(errors="replace")
print(f"REPLAY ee_drive rc={r.returncode} wall={t_ee:.2f}s stderr[{len(err)}] {err[:300]!r}{' ... '+repr(err[-300:]) if len(err)>600 else ''}")
if r.returncode != 0 or not os.path.exists(out): die(1, "ee_drive failed / no verdict file")
ob = open(out, "rb").read(); omg, obits, on = struct.unpack("<IIQ", ob[:16]); new = ob[16:]
if omg != MAGIC_V or on != n or len(new) != n: die(1, f"ee v.bin header/length mismatch magic=0x{omg:08x} n={on} body={len(new)}")
try:
    t = json.load(open(tj)); tk = t.get("tested_per_k")
except Exception as e:
    die(3, f"tested.json unreadable: {e}")
if not isinstance(tk, list) or len(tk) != len(sizes): die(3, f"tested_per_k not a per-k list of length {len(sizes)}: {type(tk).__name__}")
# --- compare ---
ok = True; fails = collections.Counter(); markers = collections.Counter()
def bad(key, msg):
    global ok; ok = False; fails[key] += 1
    if fails[key] <= 5: print("REPLAY FAIL", key, "--", msg)
off = 0; ideal = 0; prp_leg = 0; surv = 0; mism = 0
for ki, (s, tt) in enumerate(zip(sizes, tk)):
    L = leg[off:off + s]; N = new[off:off + s]; off += s
    h = next((i for i, b in enumerate(L) if b in (1, 2)), None)
    if 0xFF in L: bad("legacy-untouched", f"k{ki}: legacy has untouched positions (fixture incomplete)")
    if h is None:
        surv += 1; ideal += s
        if tt != s: bad("survivor-tested", f"k{ki}: no legacy PRP but ee tested {tt} != {s}")
        if N != L: bad("survivor-verdicts", f"k{ki}: survivor verdicts differ from legacy")
    else:
        prp_leg += 1; ideal += min(s, ((h // a.chunk) + 1) * a.chunk)
        if tt < h + 1 or tt > s: bad("tested-range", f"k{ki}: tested {tt} outside [{h+1},{s}]")
        if tt != s and tt % a.chunk != 0: bad("boundary", f"k{ki}: skip starts at {tt}, not a multiple of chunk {a.chunk}")
        beyond = N[tt:]
        if any(b in (1, 2) for b in beyond): bad("prp-beyond", f"k{ki}: PRP-class verdict beyond tested prefix {tt}")
        markers.update(beyond)
    d = sum(1 for x, y in zip(N[:tt], L[:tt]) if x != y); mism += d
    if d: bad("verdict-mismatch", f"k{ki}: {d} verdict mismatches inside tested prefix")
if len(markers) > 1: bad("marker", f"skip marker not uniform: {dict(markers)}")
mk = next(iter(markers)) if markers else None
tests_leg, tests_ee = sum(sizes), sum(tk)
print(f"REPLAY bits={bits} ks={len(sizes)} sizes[min/med/max]={min(sizes)}/{sorted(sizes)[len(sizes)//2]}/{max(sizes)} legacy-PRP ks={prp_leg} survivors={surv}")
print(f"REPLAY tests legacy={tests_leg} ee={tests_ee} ratio={tests_ee/tests_leg:.4f} (ideal constant-chunk {ideal} = {ideal/tests_leg:.4f}); "
      f"tests/k legacy={tests_leg/len(sizes):.1f} ee={tests_ee/len(sizes):.1f}; legacy PRP/test={prp_leg/tests_leg:.5f}")
print(f"REPLAY verdict mismatches in tested prefixes={mism}; skip marker={('0x%02x' % mk) if mk is not None else '-'} x{sum(markers.values())}"
      + ("  WARN marker 0 = skipped reads as composite; fold MUST use tested counts" if mk == 0 else ""))
if a.legacy_time:
    lt0 = time.time(); rr = subprocess.run([drv, sb, os.path.join(scratch, "full.v.bin")], env=dict(os.environ, CUDA_VISIBLE_DEVICES=a.gpu), capture_output=True)
    t_leg = time.time() - lt0
    print(f"REPLAY wall legacy(full bin, one launch)={t_leg:.2f}s (= {n/max(t_leg,1e-6):,.0f} t/s at {bits} bits incl. cold start) ee={t_ee:.2f}s wall ratio={t_ee/max(t_leg,1e-6):.3f} "
          f"(test ratio {tests_ee/tests_leg:.3f}; gap between the two = launch/occupancy overhead; rc={rr.returncode})")
print("REPLAY", "PASS" if ok else f"FAIL {dict(fails)}", f"scratch={scratch}")
sys.exit(0 if ok else 1)
