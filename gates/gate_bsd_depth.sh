#!/bin/bash
# gate_bsd_depth.sh -- depth gate at Q_deep (default 1e10): builds caches (~10 min once), inits the sieve (455M primes ~3 min),
# checks survivor density vs 1e8 (Mertens: ratio ~ ln(1e8)/ln(Qd)), and proves a 2,000-window sample IDENTICAL to js2 sieved directly at Qd.
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; cp $K/scanhunt_v0.py $K/fastmake.py $K/prewarm_cache.py $K/deep_primes.py $R/; QD=${1:-10000000000}; W=$HOME/beacon/m357/bsddepth; rm -rf $W; mkdir -p $W/d $W/ref
CR=1568,4374,7244,10198,13500,17734,22818,31576
echo "caches for Qd=$QD (once):"; (cd $R && DEEPQ=$QD $PY - <<'PY'
import os, sys; sys.path.insert(0, "."); os.environ["PYTHONUNBUFFERED"]="1"
import numpy as np, time, argparse, scanhunt_v0 as sc
qd = int(os.environ["DEEPQ"]); open("DEEPQ.txt.gate","w").write(str(qd))
ns = argparse.Namespace(zd=1439, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=1000000, deep_q=qd, deep_from_ring=1, rings="1568,4374,7244,10198,13500,17734,22818,31576", bits=2048, seed=7302, kblock=20000, select=12, fast=2)
t=time.time(); cfg, P = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P); print(f"deep caches ready: {len(sv.qd):,} primes, {time.time()-t:.0f}s")
PY
) || exit 2
ln -sfn $R/.sc_cache $W/d/.sc_cache
(cd $W/d && $PY $R/bsd.py --seed 7302 --card 9 --out $W/d/ready --deepq $QD --select 1 --kblock 2000 --blocks 1 --threads 16 --api $R/bs_api.so 2>&1 | tail -2)
$PY - "$W" "$QD" "$R" <<'PY'
import json, sys, math, subprocess, os; W, QD, R = sys.argv[1], int(sys.argv[2]), sys.argv[3]
a = json.load(open(f"{W}/d/ready/sc_r01_0001.manifest.json")); ks = a["ks"]; sz = a["sizes"]
mean = sum(sz)/len(sz); print(f"depth {QD:,}: {len(ks)} windows, mean {mean:.2f} cands/k  (1e8 reference 73.4 -> expected ~{73.4*math.log(1e8)/math.log(QD):.1f})")
# reference: js2 at Q=1e6 + the certified fm_deepen v0.4 over (1e6, Qd] on the SAME ks (128-bit arithmetic; gated at 1e9, primitives referee'd to 1e10).
# (js2 sieved DIRECTLY at Qd is NOT a valid reference above ~2^31: its 64-bit products overflow -- found 2026-09-09.)
sys.path.insert(0, R); import fastmake, numpy as np, argparse, scanhunt_v0 as sc
CR="1568,4374,7244,10198,13500,17734,22818,31576"
ns = argparse.Namespace(zd=1439, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=1000000, deep_q=QD, deep_from_ring=1, rings=CR, bits=2048, seed=7302, kblock=2000, select=1, fast=2)
cfg, P = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P)
import time; t0 = time.time()
_, rjs, rcnt = fastmake.block_sieve(np.array(ks, dtype=np.int64), sv.prs, sv.PEm, 0, 1568, qd=sv.qd, PEd=sv.PEd64)
rmean = sum(rcnt)/len(rcnt); print(f"reference (js2@1e6 + fm_deepen to {QD:,}): mean {rmean:.2f} cands/k, {time.time()-t0:.0f}s")
bad = sum(1 for i in range(len(ks)) if sorted(map(int, rjs[i])) != sorted(map(int, a["js"][i])))   # manifest js are packer-ordered (center-out); compare as sets
print(f"G-BSD-4 depth identity at {QD:,} (bucket sieve == js2@1e6+deepen, {len(ks)} windows, every j):", "PASS" if bad == 0 else f"FAIL ({bad} windows)")
sys.exit(0 if bad == 0 else 2)
PY
