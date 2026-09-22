#!/bin/bash
# gate_bsd.sh -- bucket-sieve daemon gates on the box (CPU only; ~5 min; safe beside production, adds ~16 cores briefly)
#   G-BSD-1 build   G-BSD-2 identity: daemon ring == scanhunt make --select 12 (seed 7302, 1e8)   G-BSD-3 thread scaling
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; cp $K/scanhunt_v0.py $K/fastmake.py $K/prewarm_cache.py $K/deep_primes.py $R/; W=$HOME/beacon/m357/bsdgate; rm -rf $W; mkdir -p $W/d $W/m
cp $K/bsd.py $K/bs_api.c $K/bsieve.c $K/bs_bench_mt.c $R/ && (cd $R && gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread && gcc -O3 -o bs_bench_mt bs_bench_mt.c -lpthread) && echo "G-BSD-1 build: PASS" || { echo "G-BSD-1 build: FAIL"; exit 2; }
ln -sfn $R/.sc_cache $W/d/.sc_cache; ln -sfn $R/.sc_cache $W/m/.sc_cache
CR=1568,4374,7244,10198,13500,17734,22818,31576
(cd $W/d && $PY $R/bsd.py --seed 7302 --card 9 --out $W/d/ready --deepq 100000000 --select 12 --blocks 1 --threads 8 --api $R/bs_api.so 2>&1 | tail -2)
(cd $W/m && $PY $R/scanhunt_v0.py make --round 1 --zd 1439 --swap 2 3 5 7 11 --kdig 13 --merit 45.0 --Q 1000000 --deep-q 100000000 --deep-from-ring 1 --rings $CR --bits 2048 --seed 7302 --kblock 20000 --select 12 2>&1 | grep -E "make wall")
$PY - "$W" <<'PY'
import json, filecmp, sys; W = sys.argv[1]
a = json.load(open(f"{W}/d/ready/sc_r01_0001.manifest.json")); b = json.load(open(f"{W}/m/sc_r01_0001.manifest.json"))
ok = a["ks"] == b["ks"] and a["js"] == b["js"] and a["sizes"] == b["sizes"] and filecmp.cmp(f"{W}/d/ready/sc_r01_0001.bin", f"{W}/m/sc_r01_0001.bin", shallow=False)
print("G-BSD-2 identity (daemon ring == make --select 12, bin+ks+js+sizes):", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 2)
PY
[ $? -eq 0 ] || exit 2
echo "G-BSD-3 thread scaling (12x block, 1e8):"; for P in 1 4 8 16; do $R/bs_bench_mt $R/.sc_cache $P | tail -1; done
echo "GATES DONE"
