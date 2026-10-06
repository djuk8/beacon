#!/bin/bash
# spin_gate.sh -- build the production driver (FERMAT_GEC=0) twice from the same source: as today (CUDA default: the host thread spins a core
# while the GPU works) and with blocking sync (the thread sleeps). Proves identical verdicts, then measures GPU throughput AND the driver's own
# CPU time for both. Changes nothing in production. Needs the nogec gate's files (canary, /tmp/nogec_rand.bin).
set -u; P3=/root/beacon/p3; PY=/venv/main/bin/python3; W=$P3/cuda_sync; say(){ echo "$(date -u +%T) spin: $*"; }
[ -f $P3/cuda_nogec/g1_fermat_v3.cu ] && [ -f $P3/canary_2048.bin ] && [ -f /tmp/nogec_rand.bin ] || { say "nogec gate files missing"; exit 1; }
mkdir -p $W && cp $P3/cuda_nogec/g1_fermat_v3.cu $W/ && cd $W && $PY - <<'PYEOF'
p = "g1_fermat_v3.cu"; s = open(p).read(); n = 0
def rep(a, b):
    global s, n
    assert s.count(a) == 1, "anchor: " + a[:50]; s = s.replace(a, b); n += 1
if "DRIVER_SPIN" not in s:
    rep("#ifndef FERMAT_GEC\n", "#ifndef DRIVER_SPIN\n#define DRIVER_SPIN 0   /* 1 = CUDA default (host thread spins a core while waiting); 0 = blocking sync (sleeps) */\n#endif\n#ifndef FERMAT_GEC\n")
    rep("  cudaSetDevice(device);\n", "  cudaSetDevice(device);\n#if !DRIVER_SPIN\n  { cudaError_t fe = cudaSetDeviceFlags(cudaDeviceScheduleBlockingSync); if (fe != cudaSuccess) fprintf(stderr, \"warning: blocking sync not set: %s\\n\", cudaGetErrorString(fe)); }\n#endif\n")
open(p, "w").write(s); print("source patched:", n, "edits")
PYEOF
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .); say "building g1_spin and g1_block (sm_$CC)"
( nvcc -O3 -arch=sm_$CC -I ../CGBN/include -DFERMAT_GEC=0 -DDRIVER_SPIN=1 -o $P3/g1_spin  g1_fermat_v3.cu -lgmp 2>&1 | grep -iv warning | tail -2 ) &
( nvcc -O3 -arch=sm_$CC -I ../CGBN/include -DFERMAT_GEC=0 -DDRIVER_SPIN=0 -o $P3/g1_block g1_fermat_v3.cu -lgmp 2>&1 | grep -iv warning | tail -2 ) &
wait; [ -x $P3/g1_spin ] && [ -x $P3/g1_block ] || { say "build failed"; exit 1; }
cd $P3
./g1_block canary_2048.bin /tmp/cb.bin > /dev/null 2>&1; cmp -s /tmp/cb.bin canary_expected.bin && say "canary: g1_block identical to the gated verdicts" || say "canary: g1_block DIFFERS - stop"
./g1_spin /tmp/nogec_rand.bin /tmp/rs.bin > /dev/null 2>&1; ./g1_block /tmp/nogec_rand.bin /tmp/rb.bin > /dev/null 2>&1
cmp -s /tmp/rs.bin /tmp/rb.bin && say "random 200k: spin and block verdicts byte-identical" || say "random 200k: DIFFER - stop"
say "freezing the hunt for the timing"; pkill -STOP -f "g1_fermat_v3"; pkill -STOP -f ee_serve.py; sleep 8
$PY - <<'PYEOF'
import subprocess, time, resource
for b in ("g1_spin", "g1_block", "g1_spin", "g1_block"):
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN); t = time.time()
    subprocess.run([f"/root/beacon/p3/{b}", "/tmp/nogec_rand.bin", "/tmp/tv.bin", "--repeat", "10", "--device", "0"], capture_output=True)
    w = time.time() - t; r1 = resource.getrusage(resource.RUSAGE_CHILDREN); cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
    print(f"  {b:9}: {2e6/w:>9,.0f} tests/s   driver CPU {cpu:5.2f}s over {w:5.2f}s wall = {100*cpu/w:3.0f}% of a core")
PYEOF
pkill -CONT -f "g1_fermat_v3"; pkill -CONT -f ee_serve.py; sleep 5; say "hunt resumed - deploy if identical, same tests/s, and g1_block's CPU far below g1_spin's: bash spin_deploy.sh"
