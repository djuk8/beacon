#!/bin/bash
# gate_o1.sh v1.3 -- G-O1 harness. Run on box1. Ships nothing to a live seed.
# v1.2 -> v1.3 (C, 2026-08-21, after the first real box1 run):
#  D  wall-clock minus cold start was BELOW THE JITTER FLOOR on a 5090 (cold
#     1.18 s +- 0.15 s vs 60 ms of kernel): it printed nonsense
#     ("cold-corrected=1000000000") and a wrong knee=1000.  Claude's bug.
#     D now parses the driver's OWN timing line ("| 0.133s | 15003.2 tests/s |"),
#     extends N to 256k, reports wall vs internal, and takes the knee from the
#     internal rate.  The 2k-batch line in stage A (15k t/s) already says the
#     kernel is latency-bound: saturation needs tens of thousands in flight.
#  C  also reports persistence mode / compute mode / MPS (the usual causes of
#     a >1 s cold start) and measures LAZY vs EAGER module loading.
#  STAGES=ABCDE env selects stages (e.g. STAGES=CDE after A+B passed).
#  D runs at 2048 bits and, if D_BITS2 is set (runner passes the fixture's
#     bit size), at the production bit size too -- knee/peak/latency scale.
#  E  MPS experiment on the gate GPU only (private pipe dir, daemon quit after).
# v1.1 -> v1.2 (C, 2026-08-21; every item caught on forced re-read + sandbox
# smoke with stub driver/stub ee_drive, see gate_o1_stubs/):
#  A  output header (MAGIC_V / bits / count / length) now CHECKED -- the
#     MAGIC_C-vs-MAGIC_V writer bug class that killed mono for 10 days;
#     composite->PRP is now COUNTED as a mismatch (v1.1 let an all-ones
#     driver pass); driver sha256 logged and compared to CERT_SHA if set;
#     driver rc + stderr head/tail printed (tail-only eats diagnoses).
#  B  v1.1's five rings contained ZERO primes (deterministic; checked with
#     gmpy2: P(21-ring has a prime) = 2.9%), so the early-exit path was
#     never exercised and PASS was vacuous.  v1.2 plants known primes at
#     index 0/3/7/8/20/none plus DECOY primes beyond each first-hit chunk
#     boundary; asserts prefix=0, hit in {1,2}, no PRP verdict beyond the
#     boundary (proves the skip happened), tested-count accounting matches
#     the plan, skip-marker uniform (its value is REPORTED, not assumed).
#     gmpy2 absent is now STOP (exit 2), not PASS.
#  C  unchanged (+ rc check).
#  D  NEW batch-size throughput curve 1k..32k: saturation knee of the
#     driver.  Early exit shrinks the per-wave batch as k's die; if waves
#     fall below the knee the 2.08x test saving does not become wall time.
#     Decides chunk/ring sizing and whether a per-card serve-loop is needed.
# Usage: [DRV=...] [EE=...] [PY=...] [GPU=n] [CERT_SHA=...] [LOG=...] bash gate_o1.sh
# box1: PY=/venv/main/bin/python3 ; CERT_SHA = sha256 from deploy/kit_v1 manifest.
set -uo pipefail
DRV=${DRV:-~/beacon/p3/g1_fermat_v2}
EE=${EE:-~/beacon/p3/ee_drive.py}
LOG=${LOG:-~/beacon/p3/gate_o1.log}
GPU=${GPU:-0}
PY=${PY:-python3}
CERT_SHA=${CERT_SHA:-}
CHUNK=${CHUNK:-8}
STAGES=${STAGES:-ABCD}
mkdir -p "$(dirname "$LOG")"
say(){ echo "$@" | tee -a "$LOG"; }
say ""; say "==== G-O1 v1.3 stages=$STAGES $(date -u +'%F %TZ') host=$(hostname) driver=$DRV ee=$EE gpu=$GPU py=$PY chunk=$CHUNK ===="
test -x "$DRV" || { say "driver not executable at $DRV -- set DRV="; exit 1; }
test -f "$EE"  || { say "ee_drive not found at $EE -- set EE="; exit 1; }
say "sha256 harness  $(sha256sum "$0" | cut -c1-16)"
say "sha256 driver   $(sha256sum "$DRV" | cut -c1-16)   (cert: ${CERT_SHA:-UNSET -- set CERT_SHA to bind to the certified binary})"
say "sha256 ee_drive $(sha256sum "$EE" | cut -c1-16)"
if [ -n "$CERT_SHA" ]; then
  [ "$(sha256sum "$DRV" | cut -d' ' -f1)" = "$CERT_SHA" ] && say "driver hash == CERT_SHA" || { say "A: FAIL -- driver hash != CERT_SHA (not the certified binary)"; exit 1; }
fi

# --- A: legacy byte-identity on a 2048-bit mixed sample (binary unchanged => must agree with gmpy2) ---
if [[ $STAGES == *A* ]]; then
say "--- A legacy contract + verdict check (2000 x 2048-bit: 500 primes, 1500 random) ---"
"$PY" - "$DRV" "$GPU" <<'PYA' 2>&1 | tee -a "$LOG"
import sys, struct, subprocess, os, random, collections
try:
    import gmpy2; HAVE=True
except Exception:
    HAVE=False
DRV, GPU = os.path.expanduser(sys.argv[1]), sys.argv[2]
MAGIC_C, MAGIC_V = 0x31433247, 0x31563247
bits = 2048; nb = bits // 8; N = 2000
random.seed(1)
vals, isp = [], []
if HAVE:
    x = gmpy2.mpz(1) << (bits - 4)
    for _ in range(N // 4):
        x = gmpy2.next_prime(x); vals.append(int(x)); isp.append(True)
while len(vals) < N:
    v = random.getrandbits(bits) | 1
    vals.append(v); isp.append(bool(gmpy2.is_prime(v)) if HAVE else None)
idx = list(range(N)); random.shuffle(idx)
vals = [vals[i] for i in idx]; isp = [isp[i] for i in idx]
with open("/tmp/a_c.bin", "wb") as f:
    f.write(struct.pack("<IIQ", MAGIC_C, bits, len(vals)))
    for v in vals: f.write(v.to_bytes(nb, "little"))
env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU)
r = subprocess.run([DRV, "/tmp/a_c.bin", "/tmp/a_v.bin"], env=env, capture_output=True)
err = r.stderr.decode(errors="replace")
print(f"A: driver rc={r.returncode} stderr[{len(err)}]: {err[:300]!r}{' ... '+repr(err[-300:]) if len(err)>600 else ''}")
if r.returncode != 0 or not os.path.exists("/tmp/a_v.bin"):
    print("A: FAIL -- driver did not run cleanly"); sys.exit(1)
hv = open("/tmp/a_v.bin", "rb").read()
if len(hv) < 16:
    print(f"A: FAIL -- verdict file too short ({len(hv)} bytes)"); sys.exit(1)
mg, bo, no = struct.unpack("<IIQ", hv[:16]); w = hv[16:]
print(f"A: out header magic=0x{mg:08x} (MAGIC_V=0x{MAGIC_V:08x}) bits={bo} count={no} body={len(w)}")
if mg != MAGIC_V or bo != bits or no != N or len(w) != N:
    print("A: FAIL -- output header/length contract violated"); sys.exit(1)
hist = collections.Counter(w)
print("A: verdict histogram " + ", ".join(f"0x{k:02x}:{c}" for k, c in sorted(hist.items())))
unt = hist.get(0xFF, 0)
if HAVE:
    bad_p = sum(1 for p, g in zip(isp, w) if p and g not in (1, 2))       # prime must read PRP-class
    bad_c = sum(1 for p, g in zip(isp, w) if (not p) and g in (1, 2))     # random composite reading PRP = driver bug at 2048 bits
    print(f"A: N={N} primes={sum(isp)} prime-row mismatches={bad_p} composite-row mismatches={bad_c} untouched={unt}  (all must be 0)")
    sys.exit(1 if (bad_p or bad_c or unt) else 0)
else:
    print(f"A: gmpy2 ABSENT in this interpreter -- contract checked, verdict semantics NOT checked; untouched={unt}")
    sys.exit(2)
PYA
rc=${PIPESTATUS[0]}
case $rc in 0) say "A: PASS";; 2) say "A: STOP -- install gmpy2 into $PY and rerun"; exit 2;; *) say "A: FAIL"; exit 1;; esac
fi

# --- B: early-exit semantics vs planted known answers ---
if [[ $STAGES == *B* ]]; then
say "--- B early-exit semantics (ee_drive, chunk=$CHUNK, planted first-primes 0/3/7/8/20/none + decoys) ---"
"$PY" - "$DRV" "$GPU" "$EE" "$CHUNK" <<'PYB' 2>&1 | tee -a "$LOG"
import sys, struct, json, subprocess, os, random, collections
DRV, GPU, EE, CH = os.path.expanduser(sys.argv[1]), sys.argv[2], os.path.expanduser(sys.argv[3]), int(sys.argv[4])
try:
    import gmpy2
except Exception:
    print("B: gmpy2 ABSENT -- cannot build known-answer rings. STOP (exit 2)."); sys.exit(2)
MAGIC_C = 0x31433247; bits = 2048; nb = bits // 8; W = 21
random.seed(7)
def comp():
    while True:
        x = random.getrandbits(bits) | 1 | (1 << (bits - 1))
        if not gmpy2.is_prime(x): return x
def prime():
    return int(gmpy2.next_prime(gmpy2.mpz(random.getrandbits(bits - 2) | (1 << (bits - 3)))))
plan   = [0, 3, 7, 8, 20, None]                   # first-prime index per k
bound  = [min(W, ((h // CH) + 1) * CH) if h is not None else W for h in plan]   # constant-chunk tested count
decoy  = {0: 9, 1: 12, 3: 17}                     # ki -> index of a SECOND prime, beyond that k's boundary
for ki, d in decoy.items(): assert d >= bound[ki], "decoy must sit beyond the first-hit boundary"
ks, sizes, cands = list(range(len(plan))), [], []
for ki, h in enumerate(plan):
    row = [comp() for _ in range(W)]
    if h is not None: row[h] = prime()
    if ki in decoy: row[decoy[ki]] = prime()
    sizes.append(W); cands += row
with open("/tmp/b.bin", "wb") as f:
    f.write(struct.pack("<IIQ", MAGIC_C, bits, len(cands)))
    for c in cands: f.write(int(c).to_bytes(nb, "little"))
with open("/tmp/b.manifest.json", "w") as f:
    json.dump(dict(bid="b", cfg={}, round=1, ks=ks, js=[list(range(s)) for s in sizes], sizes=sizes), f)
for p in ("/tmp/b.v.bin", "/tmp/b.tested.json"):
    if os.path.exists(p): os.remove(p)
r = subprocess.run([sys.executable, EE, "/tmp/b.bin", "/tmp/b.v.bin", "--driver", DRV, "--gpu", GPU,
                    "--chunk", str(CH), "--lock", "/tmp/eeg.lock"], capture_output=True)
err = r.stderr.decode(errors="replace"); out = r.stdout.decode(errors="replace")
print(f"B: ee_drive rc={r.returncode} stdout[{len(out)}] {out[:200]!r} stderr[{len(err)}] {err[:300]!r}{' ... '+repr(err[-300:]) if len(err)>600 else ''}")
if r.returncode != 0 or not os.path.exists("/tmp/b.v.bin"):
    print("B: FAIL -- ee_drive did not run cleanly / no verdict file"); sys.exit(1)
hv = open("/tmp/b.v.bin", "rb").read(); v = hv[16:]
if len(v) != len(cands):
    print(f"B: FAIL -- verdict body {len(v)} != candidates {len(cands)}"); sys.exit(1)
ok = True; off = 0; markers = collections.Counter()
def bad(msg):
    global ok; ok = False; print("B: FAIL --", msg)
for ki, h in enumerate(plan):
    sl = v[off:off + W]; off += W; b = bound[ki]
    hist = ", ".join(f"0x{k:02x}:{c}" for k, c in sorted(collections.Counter(sl).items()))
    if h is None:
        if 0xFF in sl: bad(f"k{ki}: no-prime ring has untested positions")
        if any(x in (1, 2) for x in sl): bad(f"k{ki}: PRP verdict in an all-composite ring")
    else:
        if any(x != 0 for x in sl[:h]): bad(f"k{ki}: prefix before hit not all 0 (tested composite)")
        if sl[h] not in (1, 2): bad(f"k{ki}: planted prime at {h} reads 0x{sl[h]:02x}, expected 1/2")
        if 0xFF in sl[:b]: bad(f"k{ki}: untested position inside the first-hit chunk [0,{b})")
        beyond = sl[b:]
        if any(x in (1, 2) for x in beyond): bad(f"k{ki}: PRP verdict beyond boundary {b} -- decoy was tested: NO early exit")
        markers.update(beyond)
    print(f"k{ki}: planted@{h} decoy@{decoy.get(ki,'-')} boundary={b} verdict@hit={sl[h] if h is not None else '-'} hist[{hist}]")
if len(markers) > 1: bad(f"skip-marker not uniform beyond boundaries: {dict(markers)}")
mk = next(iter(markers)) if markers else None
print(f"B: skip-marker beyond boundary = {('0x%02x' % mk) if mk is not None else '-'} x{sum(markers.values())}"
      + ("   WARN: marker 0 conflates skipped with tested-composite; fold stats MUST use tested counts" if mk == 0 else "")
      + ("   NOTE: 0xFF = left untouched; fold must treat 0xFF as skipped" if mk == 0xFF else ""))
try:
    t = json.load(open("/tmp/b.tested.json"))
except Exception as e:
    bad(f"tested.json unreadable: {e}"); t = {}
tk = t.get("tested_per_k"); waves = t.get("waves")
need = [(h + 1) if h is not None else W for h in plan]
if isinstance(tk, list):
    if len(tk) != len(plan): bad(f"tested_per_k length {len(tk)} != {len(plan)}")
    else:
        for ki, (n, m, h) in enumerate(zip(tk, need, plan)):
            if n < m or n > W: bad(f"k{ki}: tested {n} outside [{m},{W}]")
        if tk[-1] != W: bad(f"no-prime ring tested {tk[-1]} != {W}")
        mean = sum(tk) / len(tk)
        print(f"B: tested_per_k={tk} (plan constant-chunk {bound}; need>={need}) mean={mean:.1f}/{W} waves={waves}")
        if mean > 0.85 * W: bad(f"mean tested {mean:.1f} > 0.85*W -- early exit not saving tests")
elif isinstance(tk, (int, float)):
    print(f"B: tested_per_k={tk} (scalar; plan mean {sum(bound)/len(bound):.1f}, floor {sum(need)/len(need):.1f}) waves={waves}")
    if tk > 0.85 * W or tk < sum(need) / len(need): bad("scalar tested_per_k outside plan band")
else:
    bad(f"tested_per_k missing/unknown type: {tk!r}")
print("B: all checks", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
PYB
rc=${PIPESTATUS[0]}
case $rc in 0) say "B: PASS";; 2) say "B: STOP -- gmpy2 absent in $PY"; exit 2;; *) say "B: FAIL"; exit 1;; esac
fi

# --- C: cold-start cost + the usual suspects (persistence / compute mode / MPS / module loading) ---
if [[ $STAGES == *C* ]]; then
say "--- C driver cold-start (1-candidate launches x20) + GPU mode report ---"
if command -v nvidia-smi >/dev/null; then
  say "C: gpu modes: $(nvidia-smi --query-gpu=index,persistence_mode,compute_mode --format=csv,noheader | tr '\n' ';')  MPS control daemon: $(pgrep -fc nvidia-cuda-mps-control) proc(s)  CUDA_MODULE_LOADING=${CUDA_MODULE_LOADING:-<unset>}"
  nvidia-smi --query-gpu=persistence_mode --format=csv,noheader | grep -q Disabled && say "C: persistence mode DISABLED on at least one GPU -- each new process re-initialises the driver (~0.5-1 s). Try (host permitting): nvidia-smi -pm 1 ; then rerun STAGES=CD"
fi
"$PY" - "$DRV" "$GPU" <<'PYC' 2>&1 | tee -a "$LOG"
import sys, struct, subprocess, os, time, re
DRV, GPU = os.path.expanduser(sys.argv[1]), sys.argv[2]
MAGIC_C = 0x31433247; bits = 2048; nb = bits // 8
one = (1 << (bits - 2)) | 1
with open("/tmp/c1.bin", "wb") as f:
    f.write(struct.pack("<IIQ", MAGIC_C, bits, 1)); f.write(one.to_bytes(nb, "little"))
def launch(env):
    t0 = time.time(); r = subprocess.run([DRV, "/tmp/c1.bin", "/tmp/c1.v.bin"], env=env, capture_output=True); dt = time.time() - t0
    m = re.search(r"\|\s*([0-9.]+)s\s*\|", r.stderr.decode(errors="replace"))
    return dt, (float(m.group(1)) if m else None), r.returncode
base = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU)
ts = []; ins = []; rcs = set()
for _ in range(20):
    dt, ti, rc = launch(base); ts.append(dt); rcs.add(rc)
    if ti is not None: ins.append(ti)
ts.sort(); cold = sum(ts[3:17]) / 14
print(f"C: rcs={sorted(rcs)} median cold-start {ts[10]*1000:.0f} ms, trimmed mean {cold*1000:.0f} ms/launch, min {ts[0]*1000:.0f} max {ts[-1]*1000:.0f}"
      + (f"; driver-internal time {sum(ins)/len(ins)*1000:.0f} ms (the rest is process+context+module init)" if ins else "; (driver prints no internal timing line)"))
res = {"unset": [], "LAZY": [], "EAGER": []}
for _ in range(6):                                   # interleaved, so drift/contention hits all three alike
    for mode in res:
        env = dict(base); env.pop("CUDA_MODULE_LOADING", None)
        if mode != "unset": env["CUDA_MODULE_LOADING"] = mode
        res[mode].append(launch(env)[0])
for mode, tt in res.items():
    tt.sort(); print(f"C: CUDA_MODULE_LOADING={mode}: median {tt[3]*1000:.0f} ms (min {tt[0]*1000:.0f}, max {tt[-1]*1000:.0f}) over 6, interleaved")
print(f"C: per-ring launches = waves; at 12 waves/ring: {cold*12*1000:.0f} ms/ring of launch latency vs make ~7 s/ring")
with open("/tmp/cold_ms", "w") as f: f.write(f"{cold*1000:.1f}")
PYC
say "C: measured"
fi

# --- D: batch-size throughput curve from the driver's OWN timing, at 2048 bits (certified reference) and at the production bit size ---
if [[ $STAGES == *D* ]]; then
D_BITS=${D_BITS:-2048}; D_BITS2=${D_BITS2:-}
say "--- D throughput vs batch (driver-internal t/s) at bits=$D_BITS${D_BITS2:+ and $D_BITS2} ---"
for BITS in $D_BITS $D_BITS2; do
D_BITS_NOW=$BITS "$PY" - "$DRV" "$GPU" <<'PYD' 2>&1 | tee -a "$LOG"
import sys, struct, subprocess, os, time, random, re
DRV, GPU = os.path.expanduser(sys.argv[1]), sys.argv[2]
MAGIC_C = 0x31433247; bits = int(os.environ["D_BITS_NOW"]); nb = bits // 8; tag = f"D[{bits}]"
cold = float(open("/tmp/cold_ms").read()) / 1000 if os.path.exists("/tmp/cold_ms") else 0.0
env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU)
random.seed(3); rows = []; buf = bytearray()
Ns = tuple(int(x) for x in os.environ.get("D_NS", "1000,4000,16000,32000,64000,128000,256000" if bits <= 4096 else "1000,4000,16000,32000,64000,128000").split(","))
for N in Ns:
    while len(buf) < N * nb: buf += (random.getrandbits(bits) | 1 | (1 << (bits - 1))).to_bytes(nb, "little")
    with open("/tmp/d.bin", "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, N)); f.write(buf[:N * nb])
    best_w = None; best_i = None; tps_i = None
    for _ in range(3):
        t0 = time.time(); r = subprocess.run([DRV, "/tmp/d.bin", "/tmp/d.v.bin"], env=env, capture_output=True); dt = time.time() - t0
        best_w = dt if best_w is None else min(best_w, dt)
        m = re.search(r"\|\s*([0-9.]+)s\s*\|\s*([0-9.]+)\s*tests/s", r.stderr.decode(errors="replace"))
        if m:
            ti, tp = float(m.group(1)), float(m.group(2))
            if best_i is None or ti < best_i: best_i, tps_i = ti, tp
    if best_i is None:
        net = best_w - cold; tps_i = (N / net) if net > 0.05 else None; best_i = net if net > 0.05 else None
    rows.append((N, best_w, best_i, tps_i))
    print(f"{tag}: N={N:7d} wall={best_w*1000:7.0f} ms  internal={(best_i*1000 if best_i else float('nan')):7.0f} ms  t/s={(tps_i or float('nan')):10.0f}  "
          f"launch overhead={(best_w-(best_i or 0))*1000:6.0f} ms" + ("" if best_i else "  (no internal timing and below jitter floor)"))
good = [r for r in rows if r[3]]
if good:
    peak = max(r[3] for r in good); knee = next((r[0] for r in good if r[3] >= 0.9 * peak), good[-1][0]); lat = good[0][2]
    print(f"{tag}: peak {peak:.0f} t/s; smallest batch within 90% of peak = {knee}; single-test latency ~{lat*1000:.0f} ms at N={good[0][0]} -> in-flight needed for peak ~{peak*lat:.0f} tests")
else:
    print(f"{tag}: could not resolve throughput (no internal timing line and wall below jitter floor)")
PYD
done
say "D: measured"
fi

# --- E: MPS experiment (private daemon on the gate GPU only): cold start under MPS, and 8 concurrent small launches vs one big one ---
if [[ $STAGES == *E* ]]; then
MPSB=${MPSB:-nvidia-cuda-mps-control}
if ! command -v "$MPSB" >/dev/null; then say "E: $MPSB not found -- MPS experiment skipped"; else
say "--- E MPS (private pipe dir, gpu $GPU only; daemon quit at the end) ---"
export CUDA_MPS_PIPE_DIRECTORY=/tmp/mps_gate_$GPU CUDA_MPS_LOG_DIRECTORY=/tmp/mps_gate_$GPU/log; mkdir -p "$CUDA_MPS_LOG_DIRECTORY"
trap 'echo quit | "$MPSB" 2>/dev/null; true' EXIT
CUDA_VISIBLE_DEVICES=$GPU "$MPSB" -d 2>&1 | tee -a "$LOG"; sleep 2
if pgrep -f "nvidia-cuda-mps-control -d" >/dev/null; then
"$PY" - "$DRV" "$GPU" <<'PYE' 2>&1 | tee -a "$LOG"
import sys, struct, subprocess, os, time, random, re
DRV, GPU = os.path.expanduser(sys.argv[1]), sys.argv[2]
MAGIC_C = 0x31433247; bits = 2048; nb = bits // 8
env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU)            # inherits CUDA_MPS_PIPE_DIRECTORY -> MPS client
nomps = {k: v for k, v in env.items() if not k.startswith("CUDA_MPS")}
def mk(path, N, seed):
    random.seed(seed)
    with open(path, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, bits, N))
        for _ in range(N): f.write((random.getrandbits(bits) | 1).to_bytes(nb, "little"))
mk("/tmp/e1.bin", 1, 1)
ts = []; rcs = set()
for _ in range(10):
    t0 = time.time(); r = subprocess.run([DRV, "/tmp/e1.bin", "/tmp/e1.v.bin"], env=env, capture_output=True); ts.append(time.time() - t0); rcs.add(r.returncode)
ts.sort(); print(f"E: MPS cold-start median {ts[5]*1000:.0f} ms (rcs {sorted(rcs)}; compare C)")
if rcs != {0}: print("E: driver failed under MPS -- MPS not usable in this container"); sys.exit(0)
def tint(b):
    m = re.search(r"\|\s*([0-9.]+)s\s*\|", b.decode(errors="replace")); return float(m.group(1)) if m else None
P, N = 8, 8000
for i in range(P): mk(f"/tmp/e_{i}.bin", N, 10 + i)
mk("/tmp/e_big.bin", P * N, 99)
for label, e in (("MPS", env), ("no-MPS", nomps)):
    t0 = time.time(); procs = [subprocess.Popen([DRV, f"/tmp/e_{i}.bin", f"/tmp/e_{i}.v.bin"], env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(P)]
    outs = [p.communicate() for p in procs]; wall = time.time() - t0
    ints = [tint(o[1]) for o in outs]; ints = [x for x in ints if x]
    print(f"E: {label}: {P} concurrent launches x {N} -> wall {wall:.2f} s, sum of internal {sum(ints):.2f} s, max internal {max(ints) if ints else float('nan'):.2f} s "
          f"-> effective {P*N/wall:,.0f} t/s wall-clock")
t0 = time.time(); r = subprocess.run([DRV, "/tmp/e_big.bin", "/tmp/e_big.v.bin"], env=nomps, capture_output=True); wall1 = time.time() - t0; ti = tint(r.stderr)
print(f"E: single launch x {P*N} -> wall {wall1:.2f} s, internal {ti if ti else float('nan'):.2f} s -> {P*N/wall1:,.0f} t/s wall-clock")
print("E: VERDICT: if 'MPS concurrent' wall ~= 'single launch' wall, small per-process waves CAN fill the card under MPS (per-loop composition lives if the cold start is also paid); if it ~= 'no-MPS concurrent', they time-slice and only an aggregator fills the card.")
PYE
else say "E: MPS daemon did not start (container may not allow it) -- skipped"; fi
echo quit | "$MPSB" 2>&1 | tee -a "$LOG"; trap - EXIT; unset CUDA_MPS_PIPE_DIRECTORY CUDA_MPS_LOG_DIRECTORY
say "E: measured"
fi
fi
say "--- G-O1 v1.3 stages=$STAGES done. Next: step-2 replay on fossil fixtures (replay_compare.py), then shadow hour (1 card/1 bay). ---"
