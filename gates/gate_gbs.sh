#!/bin/bash
# gate_gbs.sh -- GPU sieve gates on the box (uses GPU 3 for ~2 min beside production).
#   G-GBS-1 build (nvcc)  G-GBS-2 identity at 1e8: gbsd ring == scanhunt make --select 12 (seed 7302)  G-GBS-3 identity at 1e10: gbsd == bsd (certified) on the same block
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; W=$HOME/beacon/m357/gbsgate; rm -rf $W; mkdir -p $W/g $W/m $W/g10 $W/b10
cp $K/scanhunt_v0.py $K/fastmake.py $K/bsd.py $K/gbsd.py $K/bs_api.c $K/bsieve.c $K/gbs.cu $R/ && (cd $R && gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread && /usr/local/cuda/bin/nvcc -O3 -shared -Xcompiler -fPIC -gencode arch=compute_120,code=sm_120 -o gbs.so gbs.cu) && echo "G-GBS-1 build: PASS" || { echo "G-GBS-1 build: FAIL"; exit 2; }
for d in g m g10 b10; do ln -sfn $R/.sc_cache $W/$d/.sc_cache; done
CR=1568,4374,7244,10198,13500,17734,22818,31576
(cd $W/g && $PY $R/gbsd.py --seed 7302 --card 3 --out $W/g/ready --deepq 100000000 --select 12 --blocks 3 --api $R/bs_api.so --gpu-api $R/gbs.so 2>&1 | tail -3)
(cd $W/m && $PY $R/scanhunt_v0.py make --round 1 --zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q 1000000 --deep-q 100000000 --deep-from-ring 1 --rings $CR --bits 2048 --seed 7302 --kblock 20000 --select 12 2>&1 | grep -E "make wall")
$PY - "$W" <<'PY'
import json, filecmp, sys; W = sys.argv[1]
a = json.load(open(f"{W}/g/ready/sc_r01_0001.manifest.json")); b = json.load(open(f"{W}/m/sc_r01_0001.manifest.json"))
ok = a["ks"] == b["ks"] and a["js"] == b["js"] and a["sizes"] == b["sizes"] and filecmp.cmp(f"{W}/g/ready/sc_r01_0001.bin", f"{W}/m/sc_r01_0001.bin", shallow=False)
print("G-GBS-2 identity at 1e8 (GPU ring == make --select 12, bin+ks+js+sizes):", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 2)
PY
[ $? -eq 0 ] || exit 2
(cd $W/g10 && $PY $R/gbsd.py --seed 7302 --card 3 --out $W/g10/ready --deepq 10000000000 --select 1 --kblock 2000 --blocks 2 --api $R/bs_api.so --gpu-api $R/gbs.so 2>&1 | tail -2)
(cd $W/b10 && $PY $R/bsd.py --seed 7302 --card 9 --out $W/b10/ready --deepq 10000000000 --select 1 --kblock 2000 --blocks 2 --threads 16 --api $R/bs_api.so 2>&1 | tail -1)
$PY - "$W" <<'PY'
import json, filecmp, sys; W = sys.argv[1]; bad = 0
for n in ("0001", "0002"):
    a = json.load(open(f"{W}/g10/ready/sc_r01_{n}.manifest.json")); b = json.load(open(f"{W}/b10/ready/sc_r01_{n}.manifest.json"))
    bad += not (a["ks"] == b["ks"] and a["js"] == b["js"] and a["sizes"] == b["sizes"] and filecmp.cmp(f"{W}/g10/ready/sc_r01_{n}.bin", f"{W}/b10/ready/sc_r01_{n}.bin", shallow=False))
print("G-GBS-3 identity at 1e10, 2 consecutive blocks (GPU == certified CPU sieve):", "PASS" if bad == 0 else f"FAIL ({bad} blocks)"); sys.exit(0 if bad == 0 else 2)
PY
echo "GATES DONE"
