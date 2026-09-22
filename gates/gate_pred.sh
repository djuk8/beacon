#!/bin/bash
# gate_pred.sh -- selection-statistics gate for the full-window predictor (CPU only, ~4 min beside production, fresh seed).
# Sieves the kept windows' FULL window at 1e6 for: random control | rung-1 ranking | prediction+rung-1 ranking. PASS = new beats old by >= 8 survivors.
set -u; R=$HOME/beacon/raid610; K=$HOME/beacon/p3/o1_kit; PY=/venv/main/bin/python3; W=$HOME/beacon/m357/predgate; rm -rf $W; mkdir -p $W/old $W/new
cp $K/scanhunt_v0.py $K/fastmake.py $K/bsd.py $K/bs_api.c $K/bsieve.c $R/ && (cd $R && gcc -O3 -shared -fPIC -o bs_api.so bs_api.c -lpthread) || { echo "build FAIL"; exit 2; }
for d in old new; do ln -sfn $R/.sc_cache $W/$d/.sc_cache; done
(cd $W/old && $PY $R/bsd.py --seed 7305 --card 9 --out $W/old/ready --deepq 100000000 --select 12 --blocks 1 --threads 4 --shallow-threads 2 --pred-pb 0 --api $R/bs_api.so 2>&1 | tail -1)
(cd $W/new && $PY $R/bsd.py --seed 7305 --card 9 --out $W/new/ready --deepq 100000000 --select 12 --blocks 1 --threads 4 --shallow-threads 2 --pred-pb ${PB:-100000} --alpha ${ALPHA:-0.6} --pred-threads 4 --api $R/bs_api.so 2>&1 | tail -2)
cd $R && $PY - "$W" <<'PY'
import numpy as np, sys, math, json, argparse; sys.path.insert(0, "."); import scanhunt_v0 as sc, fastmake; W = sys.argv[1]
ns = argparse.Namespace(zd=1439, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=1000000, deep_q=100000000, deep_from_ring=1, rings="1568,4374,7244,10198,13500,17734,22818,31576", bits=2048, seed=7305, kblock=20000, select=12, fast=2)
cfg, P = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P); HI = 31576; E_TOT = 28.3; prs = np.ascontiguousarray(sv.prs, dtype=np.int64); PEm = np.ascontiguousarray(sv.PEm, dtype=np.int64)
def full_mean(ks):
    ks = np.ascontiguousarray(np.sort(np.asarray(ks, dtype=np.int64))); _, o, c, n = fastmake._raw(ks, prs, PEm, 0, HI, qd=None, PEd=None); return float(np.mean(c[:len(ks)]))
old = json.load(open(f"{W}/old/ready/sc_r01_0001.manifest.json"))["ks"]; new = json.load(open(f"{W}/new/ready/sc_r01_0001.manifest.json"))["ks"]
k0 = sc.kstart(cfg); pool = np.array([k for k in (k0 + 2*np.arange(240000, dtype=np.int64)).tolist() if math.gcd(k, 2310) == 1]); ctl = np.random.default_rng(7).choice(pool, len(new), replace=False)
mc, mo, mn = full_mean(ctl), full_mean(old), full_mean(new)
for name, m in (("control (random 1/12)", mc), ("rung-1 ranking", mo), ("prediction + rung-1", mn)): print(f"  {name:<24}: full-window survivors {m:.0f} ({(1-m/mc)*100:+.2f}%) -> crown-lambda x{math.exp(E_TOT*(1-m/mc)):.2f}")
print("G-PRED:", "PASS" if mn < mo - 8 else "FAIL", f"(new vs old: x{math.exp(E_TOT*(mo-mn)/mc):.2f})"); sys.exit(0 if mn < mo - 8 else 2)
PY
