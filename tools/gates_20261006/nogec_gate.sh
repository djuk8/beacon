#!/bin/bash
# nogec_gate.sh -- build the Fermat driver with and without the Gerbicz-Li check FROM THE SAME SOURCE, prove the verdicts identical
# (against known primes and composites, and on 200k random candidates), then time both on an idle card. Changes nothing in production.
# Usage on the hunt box: bash nogec_gate.sh        (~10 min; the hunt is frozen for ~1 min during the timing, then resumed)
set -u
P3=/root/beacon/p3; PY=/venv/main/bin/python3; W=$P3/cuda_nogec; say(){ echo "$(date -u +%T) nogec: $*"; }
SRC=/root/lab/beacon/cuda/g1_fermat_v3.cu; [ -f "$SRC" ] || SRC=$P3/o1_kit/g1_fermat_v3.cu; [ -f "$SRC" ] || { say "driver source not found"; exit 1; }
mkdir -p $W && cp "$SRC" $W/g1_fermat_v3.cu && cd $W && $PY - <<'PYEOF'
p = "g1_fermat_v3.cu"; s = open(p).read(); n = 0
def rep(a, b):
    global s, n
    assert s.count(a) == 1, "anchor not unique/absent: " + a[:60]; s = s.replace(a, b); n += 1
if "FERMAT_GEC" not in s:
    rep("#include <stdio.h>\n", "#ifndef FERMAT_GEC\n#define FERMAT_GEC 1\n#endif\n#include <stdio.h>\n")
    rep("      if(chunk_in_blk==J) {                    /* block boundary */", "      if(FERMAT_GEC && chunk_in_blk==J) {      /* block boundary */")
    rep("    if(blk_in_span>0) {                        /* final partial span */", "    if(FERMAT_GEC && blk_in_span>0) {          /* final partial span */")
open(p, "w").write(s); print("source patched:", n, "edits (0 = already patched)")
PYEOF
[ -d $P3/CGBN ] || { say "no $P3/CGBN"; exit 1; }
CC=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .); say "building g1_gec and g1_nogec for sm_$CC in parallel"
( nvcc -O3 -arch=sm_$CC -I ../CGBN/include -DFERMAT_GEC=1 -o $P3/g1_gec   g1_fermat_v3.cu -lgmp 2>&1 | grep -iv warning | tail -2 ) &
( nvcc -O3 -arch=sm_$CC -I ../CGBN/include -DFERMAT_GEC=0 -o $P3/g1_nogec g1_fermat_v3.cu -lgmp 2>&1 | grep -iv warning | tail -2 ) &
wait; [ -x $P3/g1_gec ] && [ -x $P3/g1_nogec ] || { say "build failed"; exit 1; }
say "making the canary (200 known primes + 200 composites near 2^2029) and 200k random candidates"
cd $P3 && $PY - <<'PYEOF'
import struct, random, gmpy2
MAGIC_C = 0x31433247; BITS = 2048; NB = BITS // 8
def write(path, xs):
    with open(path, "wb") as f:
        f.write(struct.pack("<IIQ", MAGIC_C, BITS, len(xs)))
        for x in xs: f.write(int(x).to_bytes(NB, "little"))
rng = random.Random(20261005)
pr, co = [], []
x = gmpy2.mpz(rng.getrandbits(2029) | (1 << 2028))
while len(pr) < 200: x = gmpy2.next_prime(x + rng.getrandbits(48)); pr.append(x)
while len(co) < 200:
    y = gmpy2.mpz(rng.getrandbits(2029) | (1 << 2028) | 1)
    if not gmpy2.is_prime(y, 25): co.append(y)
mix = [(p, 1) for p in pr] + [(c, 0) for c in co]; rng.shuffle(mix)
write("/root/beacon/p3/canary_2048.bin", [m[0] for m in mix])
open("/root/beacon/p3/canary_truth.txt", "w").write("".join(str(m[1]) for m in mix))
write("/tmp/nogec_rand.bin", [rng.getrandbits(2029) | (1 << 2028) | 1 for _ in range(200000)])
print("canary: 400 candidates (200 prime), random set: 200,000")
PYEOF
# identity: GEC build against truth, then NOGEC against GEC byte for byte
./g1_gec   canary_2048.bin /tmp/cv_gec.bin   > /dev/null 2>&1; ./g1_nogec canary_2048.bin /tmp/cv_nogec.bin > /dev/null 2>&1
$PY - <<'PYEOF'
truth = open("/root/beacon/p3/canary_truth.txt").read(); v = open("/tmp/cv_gec.bin", "rb").read()[16:]
pv = {v[i] for i in range(len(truth)) if truth[i] == "1"}; cv = {v[i] for i in range(len(truth)) if truth[i] == "0"}
ok = len(pv) == 1 and len(cv) == 1 and pv != cv
print(f"GEC build vs truth: primes -> {sorted(pv)}, composites -> {sorted(cv)}: {'CORRECT' if ok else 'WRONG'}")
PYEOF
cmp -s /tmp/cv_gec.bin /tmp/cv_nogec.bin && say "canary: NOGEC verdicts byte-identical to GEC" || say "canary: NOGEC DIFFERS - stop"
./g1_gec /tmp/nogec_rand.bin /tmp/rv_gec.bin > /dev/null 2>&1; ./g1_nogec /tmp/nogec_rand.bin /tmp/rv_nogec.bin > /dev/null 2>&1
cmp -s /tmp/rv_gec.bin /tmp/rv_nogec.bin && say "random 200k: NOGEC verdicts byte-identical to GEC" || say "random 200k: NOGEC DIFFERS - stop"
cp /tmp/cv_gec.bin $P3/canary_expected.bin
# timing on an idle card 0: freeze the hunt's drivers and feeders (SIGSTOP; the respawn loops cannot react), time, resume
say "freezing the hunt for the timing"; pkill -STOP -f "g1_fermat_v3"; pkill -STOP -f ee_serve.py; sleep 8
nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader | tr '\n' ' '; echo
for b in g1_gec g1_nogec g1_gec g1_nogec; do s=$(date +%s.%N); ./$b /tmp/nogec_rand.bin /tmp/tv.bin --repeat 10 --device 0 > /dev/null 2>&1; e=$(date +%s.%N); $PY -c "print(f'  {\"$b\":>9}: {2e6/($e-$s):>9,.0f} tests/s')"; done | tee /tmp/nogec_timing.txt
pkill -CONT -f "g1_fermat_v3"; pkill -CONT -f ee_serve.py; sleep 10; nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader | tr '\n' ' '; echo; say "hunt resumed"
$PY - <<'PYEOF'
import re, statistics as st
r = {"g1_gec": [], "g1_nogec": []}
for ln in open("/tmp/nogec_timing.txt"):
    m = re.match(r"\s*(g1_\w+):\s*([\d,]+)", ln)
    if m: r[m.group(1)].append(int(m.group(2).replace(",", "")))
g, n = st.mean(r["g1_gec"]), st.mean(r["g1_nogec"])
print(f"RESULT: GEC {g:,.0f}/s  NOGEC {n:,.0f}/s  gain {100*(n/g-1):+.1f}%   (deploy if verdicts identical and gain >= 5%: bash nogec_deploy.sh)")
PYEOF
