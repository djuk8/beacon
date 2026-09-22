#!/bin/bash
# gate_sieve.sh -- sieve-card gates: build; serve-mode rings land round-robin; rings byte-identical to the CPU daemon (bsd) at 1e10 with the same predictor ranking.
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; W=$HOME/beacon/m357/sievegate; rm -rf $W; mkdir -p $W/g $W/b
cp $K/scanhunt_v0.py $K/fastmake.py $K/bsd.py $K/gbsd.py $K/bs_api.c $K/bsieve.c $K/gbs.cu $R/ && (cd $R && gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread && ([ -f gbs.so ] && [ gbs.so -nt gbs.cu ] || /usr/local/cuda/bin/nvcc -O3 -shared -Xcompiler -fPIC -gencode arch=compute_120,code=sm_120 -o gbs.so gbs.cu)) && echo "G-SV-1 build: PASS" || { echo "G-SV-1 build: FAIL"; exit 2; }
for d in g b; do ln -sfn $R/.sc_cache $W/$d/.sc_cache; done
(cd $W/g && $PY $R/gbsd.py --seed 7311 --card 3 --out $W/g/ready --serve 0,1,2 --deepq 10000000000 --select 12 --kblock 2000 --blocks 3 --workers 4 --state $W/g/state.json --pred-pb 100000 --alpha 0.6 --api $R/bs_api.so --gpu-api $R/gbs.so 2>&1 | grep -c 'block [0-2] ->')
(cd $W/g && $PY $R/gbsd.py --seed 7311 --card 3 --out $W/g/ready --serve 0,1,2 --deepq 10000000000 --select 12 --kblock 2000 --blocks 6 --workers 4 --state $W/g/state.json --pred-pb 100000 --alpha 0.6 --api $R/bs_api.so --gpu-api $R/gbs.so 2>&1 | grep -E 'origin shifted|resuming' | head -2)
echo "G-SV-2 round-robin: $(for c in 0 1 2; do printf "c$c=%s " $(ls $W/g/ready/c$c/*.manifest.json 2>/dev/null | wc -l); done)"
(cd $W/b && $PY $R/bsd.py --seed 7311 --card 9 --out $W/b/ready --deepq 10000000000 --select 12 --kblock 2000 --blocks 6 --threads 16 --shallow-threads 2 --pred-pb 100000 --alpha 0.6 --api $R/bs_api.so 2>&1 | tail -1)
$PY - "$W" <<'PY'
import json, filecmp, sys, glob, os; W = sys.argv[1]; bad = 0; n = 0
g = {os.path.basename(f): f for f in glob.glob(f"{W}/g/ready/c*/sc_r01_*.manifest.json")}; b = {os.path.basename(f): f for f in glob.glob(f"{W}/b/ready/sc_r01_*.manifest.json")}
for name in sorted(b):
    if name not in g: bad += 1; continue
    A = json.load(open(g[name])); B = json.load(open(b[name])); n += 1
    ok = A["ks"] == B["ks"] and A["js"] == B["js"] and A["sizes"] == B["sizes"] and filecmp.cmp(g[name].replace(".manifest.json", ".bin"), b[name].replace(".manifest.json", ".bin"), shallow=False)
    bad += not ok; print(f"  {name}: pred_z gpu {A['origin'].get('pred_z')} cpu {B['origin'].get('pred_z')} -> {'identical' if ok else 'DIFFER'}")
print("G-SV-3/4 identity incl. RESUME (blocks 0-2 fresh, 3-5 after relaunch) == CPU daemon at 1e10, same predictor ranking:", "PASS" if bad == 0 and n == 6 else f"FAIL ({bad}, n={n})"); sys.exit(0 if bad == 0 and n == 6 else 2)
PY
