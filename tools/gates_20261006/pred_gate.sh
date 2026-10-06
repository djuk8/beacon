#!/bin/bash
# pred_gate.sh -- build bs_api_v2.so (new predictor loop) next to the daemons' bs_api.so and prove it on the daemons' REAL shm tables:
# outputs must be identical, and both are timed. Changes nothing in production.
set -eu; R=/root/beacon/raid610; PY=/venv/main/bin/python3; cd $R
$PY ~/patch_pred_v2.py bs_api.c /tmp/bs_api_v2.c && gcc -O3 -march=native -shared -fPIC -I $R -o $R/bs_api_v2.so /tmp/bs_api_v2.c -lpthread && echo "built bs_api_v2.so"
$PY - <<'PYEOF'
import ctypes as C, numpy as np, glob, time
base = sorted(glob.glob("/dev/shm/pred_*.p.npy"))[0][:-len(".p.npy")]; print("tables:", base)
pp, pe, of, tb = (np.load(base + x, mmap_mode="r") for x in (".p.npy", ".pe.npy", ".off.npy", ".tab.npy"))
old = C.CDLL("/root/beacon/raid610/bs_api.so"); new = C.CDLL("/root/beacon/raid610/bs_api_v2.so")
old.bs_pred_attach.restype = C.c_void_p; old.bs_pred_attach.argtypes = [C.c_void_p]*4 + [C.c_int64]*2
for L in (old, new): L.bs_predict.argtypes = [C.c_void_p, C.c_int64, C.c_int64, C.c_int, C.c_void_p]
M = old.bs_pred_attach(pp.ctypes.data, pe.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), 31576); T = 240000
to_b = tn_b = 9e9; ok = True
for k0 in (29000000000001, 29123456789013, 31000000000003, 31077777777773):
    a = np.zeros(T); b = np.zeros(T)
    t = time.time(); old.bs_predict(M, k0, T, 1, a.ctypes.data); to = time.time() - t
    t = time.time(); new.bs_predict(M, k0, T, 1, b.ctypes.data); tn = time.time() - t
    same = np.array_equal(a, b); ok &= same; to_b, tn_b = min(to_b, to), min(tn_b, tn)
    print(f"  k0 {k0}: identical {same} | old {to:.2f}s new {tn:.2f}s (one core, hunt running)")
print(f"RESULT: identical on all pools: {ok} | old {to_b:.2f}s new {tn_b:.2f}s per pool -> x{to_b/tn_b:.1f}   (deploy if identical: bash pred_deploy.sh)")
PYEOF
