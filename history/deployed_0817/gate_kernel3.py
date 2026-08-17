#!/usr/bin/env python3
"""BEACON kernel-v3 ZERO-TOLERANCE GATE.

Demands, on identical anchors:
  G-A  scores: kernel3 == kernel2, bit-exact (memcmp) when weights are
       integer-valued (production shape: tw = 1.0); hit-set-exact plus
       <=1e-12 rel when weights are fractional (FP associativity: kernel2
       sums prime-major, kernel3 sums canonical position-order -- equal sets,
       equal sums up to rounding; bit-exact restored for integer weights).
  G-B  hit sets: per-anchor (side, position) sets from kernel3 --dump equal
       kernel2d dumps exactly. This is the bug-catcher (both prior kernel
       bugs were set-level).
  G-C  oracle: independent numpy recomputation from first principles agrees
       with both on small K.
  G-D  determinism: kernel3 output byte-identical across forced tile sizes
       (scheduling-independence of the canonical accumulator), including a
       config that forces bucket-ring wraparound.
Exit nonzero on ANY failure.
"""
import json, os, shutil, struct, subprocess, sys
import numpy as np

WD = os.path.dirname(os.path.abspath(__file__))
os.chdir(WD)

def sh(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("CMD FAIL:", cmd); print(r.stdout); print(r.stderr); sys.exit(1)
    return r.stderr

def build():
    sh("gcc -O2 -o screen_kernel2  screen_kernel2.c")
    sh("gcc -O2 -o screen_kernel2d screen_kernel2d.c")
    sh("gcc -O3 -o kernel3 screen_kernel3.c")

def read_b3(path):
    with open(path, "rb") as f:
        np_ = np.fromfile(f, np.int64, 1)[0]
        pd = np.fromfile(f, np.int64, np_); pm = np.fromfile(f, np.int64, np_)
        R0 = np.fromfile(f, np.int64, np_)
        W, ntgt = np.fromfile(f, np.int64, 2)
        tgt = np.fromfile(f, np.int64, ntgt); tw = np.fromfile(f, np.float64, ntgt)
    return pd, pm, R0, int(W), tgt, tw

def read_dump2(path, W):
    out = {}
    with open(path, "rb") as f:
        buf = f.read()
    o = 0
    while o < len(buf):
        t, nP = struct.unpack_from("<qq", buf, o); o += 16
        P = np.frombuffer(buf, np.int64, nP, o); o += 8 * nP
        (nM,) = struct.unpack_from("<q", buf, o); o += 8
        M = np.frombuffer(buf, np.int64, nM, o); o += 8 * nM
        out[t] = (set(P.tolist()), set(M.tolist()))
    return out

def read_dump3(path, tgt, ntgt):
    out = {}
    with open(path, "rb") as f:
        buf = f.read()
    o = 0
    while o < len(buf):
        t, nb = struct.unpack_from("<qq", buf, o); o += 16
        bits = np.frombuffer(buf, np.uint32, nb, o); o += 4 * nb
        plus  = set(int(tgt[b]) for b in bits if b < ntgt)
        minus = set(int(tgt[b - ntgt]) for b in bits if b >= ntgt)
        out[t] = (plus, minus)
    return out

def oracle(pd, pm, R0, W, tgt, tw, K):
    """Independent recomputation. plus-kill: h ≡ -r (mod p); minus: h ≡ r."""
    Hmod = tgt[None, :] % pd[:, None]                       # np x ntgt
    scores = np.zeros(K); sets = {}
    for t in range(K):
        r = (R0 + t * pm) % pd
        rp = (pd - r) % pd                                  # -r mod p
        mp = np.any(Hmod == rp[:, None], axis=0)
        mm = np.any(Hmod == r[:, None],  axis=0)
        scores[t] = tw[mp].sum() + tw[mm].sum()
        sets[t] = (set(tgt[mp].tolist()), set(tgt[mm].tolist()))
    return scores, sets

def k3_run(b3, K, outdir, extra=""):
    if os.path.isdir(outdir): shutil.rmtree(outdir)
    os.makedirs(outdir)
    err = sh(f"./kernel3 {b3} 0 {K} {outdir} {extra}")
    return np.load(f"{outdir}/scores_0_{K}.npy"), err

FAILS = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok: FAILS.append(name)

def k3_run_t0(b3, T0, K, outdir, extra=""):
    if os.path.isdir(outdir): shutil.rmtree(outdir)
    os.makedirs(outdir)
    sh(f"./kernel3 {b3} {T0} {K} {outdir} {extra}")
    return np.load(f"{outdir}/scores_{T0}_{K}.npy")

def oracle_t0(pd, pm, R0, W, tgt, tw, T0, K):
    Hmod = tgt[None, :] % pd[:, None]
    scores = np.zeros(K); sets = {}
    for t in range(K):
        r = (R0 + ((T0 + t) % pd) * pm) % pd
        rp = (pd - r) % pd
        mp = np.any(Hmod == rp[:, None], axis=0)
        mm = np.any(Hmod == r[:, None],  axis=0)
        scores[t] = tw[mp].sum() + tw[mm].sum()
        sets[t] = (set(tgt[mp].tolist()), set(tgt[mm].tolist()))
    return scores, sets

def gate_case(tag, gen_cmd, K, Kdump, Kor, int_weights, tiles=(6,)):
    print(f"== {tag} ==")
    sh(gen_cmd)
    pd, pm, R0, W, tgt, tw = read_b3(f"{tag}.b3")
    # scores: kernel2 vs kernel3
    sh(f"./screen_kernel2 {tag}.b2 {K} {tag}.k2.bin")
    s2 = np.fromfile(f"{tag}.k2.bin", np.float64)
    s3, err3 = k3_run(f"{tag}.b3", K, f"out_{tag}")
    if int_weights:
        check("G-A scores bit-exact", s2.tobytes() == s3.tobytes(),
              f"K={K} max|d|={np.abs(s2-s3).max():.3g}")
    else:
        ok = np.allclose(s2, s3, rtol=1e-12, atol=1e-9)
        check("G-A scores <=1e-12", ok, f"max rel {np.max(np.abs(s2-s3)/np.maximum(np.abs(s2),1e-30)):.2e}")
    # hit sets: kernel2d vs kernel3 --dump
    sh(f"./screen_kernel2d {tag}.b2 {Kdump} {tag}.k2d.bin {tag}.k2d.dump")
    s2d = np.fromfile(f"{tag}.k2d.bin", np.float64)
    check("G-B kernel2d==kernel2 scores", s2d.tobytes() == s2[:Kdump].tobytes())
    d2 = read_dump2(f"{tag}.k2d.dump", W)
    _, _ = k3_run(f"{tag}.b3", Kdump, f"outd_{tag}", extra=f"--dump {tag}.k3.dump")
    d3 = read_dump3(f"{tag}.k3.dump", tgt, len(tgt))
    ok = all(d2[t] == d3[t] for t in range(Kdump))
    if not ok:
        bad = next(t for t in range(Kdump) if d2[t] != d3[t])
        print(f"      first mismatch t={bad}: k2 P{sorted(d2[bad][0])[:6]}.. "
              f"k3 P{sorted(d3[bad][0])[:6]}..")
    check("G-B hit sets exact", ok, f"Kdump={Kdump}")
    # oracle
    so, seto = oracle(pd, pm, R0, W, tgt, tw, Kor)
    check("G-C oracle vs kernel3 scores", np.allclose(so, s3[:Kor], rtol=1e-12, atol=1e-9))
    check("G-C oracle vs kernel3 sets", all(seto[t] == d3[t] for t in range(min(Kor, Kdump))))
    # G-E block composition: concatenated blocks == monolithic prefix,
    # and a T0>0 slice agrees with the independent oracle
    B = max(K // 4, 1)
    parts = [k3_run_t0(f"{tag}.b3", T0, B, f"outb_{tag}_{T0}") for T0 in (0, B, 2 * B)]
    comp = np.concatenate(parts)
    check("G-E block composition", comp.tobytes() == s3[:3 * B].tobytes(),
          f"3x{B} vs monolithic")
    Ko = min(Kor, B)
    so2, _ = oracle_t0(pd, pm, R0, W, tgt, tw, 2 * B, Ko)
    check("G-E T0>0 vs oracle", np.allclose(so2, parts[2][:Ko], rtol=1e-12, atol=1e-9),
          f"T0={2*B}")
    # determinism across schedules (incl. ring wrap for small tiles)
    ref = s3.tobytes()
    for tl in tiles:
        sT, _ = k3_run(f"{tag}.b3", K, f"outt_{tag}_{tl}", extra=f"--tile {tl}")
        check(f"G-D determinism tile=2^{tl}", sT.tobytes() == ref)

if __name__ == "__main__":
    build()
    gate_case("real_ones",
              "python3 make_blob3.py --case real --out real_ones --weights ones --seed 17",
              K=8192, Kdump=256, Kor=40, int_weights=True, tiles=(6, 9))
    gate_case("real_rint",
              "python3 make_blob3.py --case real --out real_rint --weights randint --seed 23",
              K=4096, Kdump=192, Kor=32, int_weights=True, tiles=(7,))
    gate_case("real_frac",
              "python3 make_blob3.py --case real --out real_frac --weights frac --seed 29",
              K=4096, Kdump=192, Kor=32, int_weights=False, tiles=(8,))
    gate_case("adv_small",
              "python3 make_blob3.py --case adv_small --out adv_small --seed 5",
              K=64, Kdump=64, Kor=48, int_weights=True, tiles=(2, 3))   # forces ring wrap
    gate_case("adv_bigp",
              "python3 make_blob3.py --case adv_bigp --out adv_bigp --seed 7",
              K=100, Kdump=100, Kor=48, int_weights=True, tiles=(3,))
    gate_case("adv_edge",
              "python3 make_blob3.py --case adv_edge --out adv_edge --seed 11",
              K=512, Kdump=256, Kor=40, int_weights=False, tiles=(4,))
    print()
    if FAILS:
        print(f"GATE: {len(FAILS)} FAILURE(S): {FAILS}"); sys.exit(1)
    print("GATE: ALL CHECKS PASS (zero tolerance held)")
