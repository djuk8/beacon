#!/usr/bin/env python3
"""gbsd.py -- GPU-resident sieve daemon: one progression per daemon; the GPU does every block's sieving (masks, medium walks,
FK record stepping); the CPU does per-prime init ONCE (certified bsieve.c code), selection, extraction, packing.
usage: gbsd.py --seed S --card C --out READYDIR [--deepq 1e10] [--select 12] [--kblock 20000] [--ahead 24] [--blocks N]
Rings are exactly what `scanhunt make --round 1 --select N` / bsd.py produce (gate: byte-identical).
v8.56: --step 2310 --kclass C walks ONE residue class mod 2310 (k = k0 + 2310 t, k0 = first k >= --kbase in the class, default 1e15;
CLASS_RESULT_v0); every row is a valid window, kblock 8311 keeps 8,311 windows per ring. --step 2 (default) = v8.55 byte for byte.
v8.57: --gpu-rings 2 sieves rings 1+2 on the GPU at --deepq; the ring file and the selection are unchanged (ring-1 part of the
bitmap), the kept windows' ring-2 survivors ride in the manifest ("r2") to the ladder's rung-2 make. --gpu-rings 1 = v8.56."""
import argparse, base64, ctypes, json, math, os, struct, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scanhunt_v0 as sc, fastmake

import multiprocessing as _mproc, struct as _struct
_W = {}
def _worker_init(api, cfg, P_eff_str, k0, T, I, Sh, BW, nb, select, alpha, pred_pb, zd, fullhi, pred_threads, magic, outs, bid_step, seed_=0, step_=2, kclass_=-1, gr_=1, r1c_=(0, 0), dq_=0, r1hi_=0):
    import ctypes as _c, numpy as _np, os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import fastmake as _fm
    L = _c.CDLL(api)
    L.bs_row_counts.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p]
    L.bs_js_from_bits.restype = _c.c_int64; L.bs_js_from_bits.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p, _c.c_int64, _c.c_void_p, _c.c_void_p, _c.c_int64]
    if gr_ > 1: L.bs_row_counts_rng.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_void_p]   # v8.57
    PRED = None
    if pred_pb > 0 and select > 1:
        L.bs_pred_attach.restype = _c.c_void_p; L.bs_pred_attach.argtypes = [_c.c_void_p, _c.c_void_p, _c.c_void_p, _c.c_void_p, _c.c_int64, _c.c_int64]
        L.bs_predict.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int, _c.c_void_p]
        if step_ != 2: L.bs_predict_s.argtypes = [_c.c_void_p, _c.c_int64, _c.c_int64, _c.c_int64, _c.c_int, _c.c_void_p]   # v8.56
        base = f"/dev/shm/pred_{zd}_{fullhi}_{pred_pb}"
        pp = _np.load(base + ".p.npy", mmap_mode="r"); pe_ = _np.load(base + ".pe.npy", mmap_mode="r"); of = _np.load(base + ".off.npy", mmap_mode="r"); tb = _np.load(base + ".tab.npy", mmap_mode="r")
        PRED = L.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), fullhi); _W["keep"] = (pp, pe_, of, tb)
    _W.update(dict(L=L, fm=_fm, cfg=cfg, seed=seed_, S=step_, kclass=kclass_, GR=gr_, R1C=r1c_, DQ=dq_, R1HI=r1hi_, P=int(P_eff_str), k0=k0, T=T, I=I, Sh=Sh, BW=BW, nb=nb, select=select, alpha=alpha, PRED=PRED, pt=pred_threads, magic=magic, outs=outs, np=_np))

def _worker_ring(args):
    """one block's CPU tail: read the bitmap from shm, rank, extract, pack, write the ring. returns a log line."""
    blk, shmpath, bid, target = args; W = _W; np = W["np"]; L = W["L"]; T, I, Sh, BW = W["T"], W["I"], W["Sh"], W["BW"]; t0 = time.time()
    bits = np.fromfile(shmpath, dtype=np.uint64).reshape(T, BW)
    cnt = np.empty(T, dtype=np.int32); L.bs_row_counts(bits.ctypes.data, T, BW, I, cnt.ctypes.data)
    if W["GR"] > 1: cnt_all = cnt; cnt = np.empty(T, dtype=np.int32); L.bs_row_counts_rng(bits.ctypes.data, T, BW, W["R1C"][0], W["R1C"][1], cnt.ctypes.data)   # v8.57: selection keeps reading ring 1 only
    ks_all = W["k0"] + W["S"] * (blk * T + np.arange(T, dtype=np.int64)); cop = np.nonzero(np.gcd(ks_all, 2310) == 1)[0]
    nkeep = len(cop) // W["select"] if W["select"] > 1 else len(cop); zsel = 0.0
    if W["PRED"] is not None:
        pr = np.zeros(T); (L.bs_predict(W["PRED"], int(W["k0"] + 2 * blk * T), T, W["pt"], pr.ctypes.data) if W["S"] == 2 else L.bs_predict_s(W["PRED"], int(W["k0"] + W["S"] * blk * T), T, W["S"], W["pt"], pr.ctypes.data)); prc = pr[cop]; s1 = cnt[cop].astype(float)
        score = (prc - prc.mean()) / (prc.std() + 1e-9) - W["alpha"] * (s1 - s1.mean()) / (s1.std() + 1e-9)
        order = np.argsort(-score, kind="stable"); kept = np.sort(cop[order[:nkeep]]).astype(np.int32); zsel = float(((prc[order[:nkeep]] - prc.mean()) / (prc.std() + 1e-9)).mean())
    else:
        order = np.argsort(cnt[cop], kind="stable"); kept = np.sort(cop[order[:nkeep]]).astype(np.int32)
    out = np.empty(int((cnt if W["GR"] == 1 else cnt_all)[kept].sum()) + 16, dtype=np.int32); cnt2 = np.empty(len(kept), dtype=np.int32)
    tot = L.bs_js_from_bits(bits.ctypes.data, BW, I, Sh, kept.ctypes.data, len(kept), out.ctypes.data, cnt2.ctypes.data, len(out)); assert tot >= 0
    offs = np.concatenate([[0], np.cumsum(cnt2)[:-1]]); ks_sel = ks_all[kept].tolist(); js_sel = [out[offs[i]:offs[i] + cnt2[i]] for i in range(len(kept))]
    if W["GR"] > 1: r1 = W["R1HI"]; js2_sel = [j[np.abs(j) > r1] for j in js_sel]; js_sel = [j[np.abs(j) <= r1] for j in js_sel]   # v8.57: ring 1 -> ring file, ring 2 -> manifest
    pjs, psizes, packed = W["fm"].pack_given(ks_sel, js_sel, W["P"], W["nb"])
    odir = W["outs"][target]; name = f"sc_r01_{bid:04d}"; tmp = os.path.join(odir, f".{name}.tmp")
    with open(tmp + ".bin", "wb") as f: f.write(_struct.pack("<IIQ", W["magic"], W["cfg"]["bits"], sum(psizes))); f.write(packed)
    man = dict(cfg=W["cfg"], round=1, bid=bid, ks=ks_sel, js=[j.tolist() for j in pjs], sizes=list(psizes), origin=dict(gbsd=1, seed=W["seed"], block=blk, select=W["select"], pred_z=round(zsel, 3), **({} if W["S"] == 2 else dict(step=W["S"], kclass=W["kclass"]))))
    if W["GR"] > 1: man["r2"] = dict(lo=r1, hi=W["cfg"]["edges"][1], q=W["DQ"], cnt=[int(len(j)) for j in js2_sel], b64=base64.b64encode((np.concatenate(js2_sel) if js2_sel else np.zeros(0)).astype("<i2").tobytes()).decode("ascii"))
    json.dump(man, open(tmp + ".manifest.json", "w"))
    os.replace(tmp + ".bin", os.path.join(odir, name + ".bin")); os.replace(tmp + ".manifest.json", os.path.join(odir, name + ".manifest.json"))
    try: os.unlink(shmpath)
    except OSError: pass
    return f"gbsd: block {blk} -> {name}: {len(ks_sel)} ks, {sum(psizes):,} cands (mean {sum(psizes)/max(len(psizes),1):.1f}/k) | tail {time.time()-t0:.2f}s pred_z {zsel:+.2f} -> {os.path.basename(odir)}" + ('' if W["GR"] == 1 else f" | r2 {sum(len(j) for j in js2_sel)/max(len(js2_sel),1):.1f}/k")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True); ap.add_argument("--card", type=int, default=0); ap.add_argument("--out", required=True)
    ap.add_argument("--deepq", type=int, default=10_000_000_000); ap.add_argument("--select", type=int, default=12)
    ap.add_argument("--kblock", type=int, default=0); ap.add_argument("--ahead", type=int, default=24); ap.add_argument("--blocks", type=int, default=0)
    ap.add_argument("--zd", type=int, default=1439); ap.add_argument("--bits", type=int, default=2048); ap.add_argument("--pmask", type=int, default=251)
    ap.add_argument("--rings", default="1568,4374,7244,10198,13500,17734,22818,31576")
    ap.add_argument("--api", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "bs_api.so")); ap.add_argument("--gpu-api", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "gbs.so"))
    ap.add_argument("--bid-start", type=int, default=1); ap.add_argument("--bid-step", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--state", default="")                   # progression state file (default /root/beacon/raid610/sieve_state_<seed>.json): resume after relaunch instead of re-hunting from block 0          # CPU workers for the per-block tail (predict/rank/extract/pack/write); the GPU stage stays serial
    ap.add_argument("--serve", default="")                   # sieve-card mode: comma list of cards whose ready queues receive rings round-robin (e.g. 0,1,2); --out is then the parent dir
    ap.add_argument("--gpu-rings", type=int, default=1)   # v8.57: 2 = the GPU sieves rings 1+2 (ring 2 rides to the ladder pre-sieved)
    ap.add_argument("--step", type=int, default=2); ap.add_argument("--kclass", type=int, default=-1); ap.add_argument("--kbase", type=int, default=0)   # v8.56: --step 2310 --kclass C [--kbase K]: one residue class mod 2310
    ap.add_argument("--pred-pb", type=int, default=100000); ap.add_argument("--alpha", type=float, default=0.6); ap.add_argument("--pred-threads", type=int, default=8)
    a = ap.parse_args()
    if a.gpu_rings not in (1, 2): sys.exit("gbsd: --gpu-rings 1 or 2")
    if not a.kblock: a.kblock = 20000 if a.step == 2 else 8311                     # v8.56: 8311 x 12 = 99,732 single-class rows -> 8,311 windows per ring, as at step 2
    if a.step != 2 and (a.step != 2310 or not 0 < a.kclass < 2310 or math.gcd(a.kclass, 2310) != 1):
        sys.exit("gbsd: --step 2310 needs --kclass C with 0 < C < 2310 and gcd(C, 2310) == 1 (best pair: 317 / 1993)")
    ns = argparse.Namespace(zd=a.zd, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=1_000_000, deep_q=a.deepq, deep_from_ring=1, rings=a.rings, bits=a.bits, seed=a.seed, kblock=a.kblock, select=a.select, fast=2)
    cfg, P_eff = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P_eff)
    edges = [int(x) for x in a.rings.split(",")]; hi = edges[a.gpu_rings - 1]; Sh = hi // 2; I = 2 * Sh + 1; BW = (I + 63) // 64   # v8.57: rings 1..gpu_rings
    r1c = (Sh - edges[0] // 2, Sh + edges[0] // 2)                    # bit columns of ring 1 inside the sieved window
    T = a.kblock * a.select; k0 = sc.kstart(cfg); nb = a.bits // 8
    if a.step != 2: kb = a.kbase or 10 ** 15; k0 = kb + (a.kclass - kb) % 2310      # v8.56: first k >= kbase in the class (single-class k-space starts at 1e15)
    L = ctypes.CDLL(a.api); G = ctypes.CDLL(a.gpu_api)
    if a.gpu_rings > 1:                                                   # v8.57: a v8.56 library cannot hold the wider window -> refuse
        miss = [f for f, lib in (("bs_records_flat_w", L), ("bs_row_counts_rng", L), ("gbs_set_format", G)) if not hasattr(lib, f)]
        if miss: sys.exit(f"gbsd: --gpu-rings {a.gpu_rings} needs the v8.57 libraries (missing {miss} in {a.api} / {a.gpu_api})")
        L.bs_records_flat_w.restype = ctypes.c_int64; L.bs_records_flat_w.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
        G.gbs_set_format.restype = ctypes.c_int; G.gbs_set_format.argtypes = [ctypes.c_void_p, ctypes.c_int]
    if a.step != 2:                                                                    # v8.56: a v8.55 library would sieve the wrong progression silently -> refuse
        miss = [f for f, lib in (("bs_js2_consts_s", L), ("bs_records_flat_s", L), ("bs_predict_s", L), ("gbs_set_step", G)) if not hasattr(lib, f)]
        if miss: sys.exit(f"gbsd: --step {a.step} needs the v8.56 libraries (missing {miss} in {a.api} / {a.gpu_api})")
        L.bs_js2_consts_s.restype = ctypes.c_int64; L.bs_js2_consts_s.argtypes = [ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]
        L.bs_records_flat_s.restype = ctypes.c_int64; L.bs_records_flat_s.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
        G.gbs_set_step.restype = ctypes.c_int; G.gbs_set_step.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    L.bs_records_flat.restype = ctypes.c_int64; L.bs_records_flat.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    L.bs_js2_consts.argtypes = [ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]
    L.bs_wheel.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    L.bs_smask_create.restype = ctypes.c_void_p; L.bs_smask_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int64, ctypes.c_int64]
    L.bs_smask_words.restype = ctypes.c_int64; L.bs_smask_words.argtypes = [ctypes.c_void_p]; L.bs_smask_export.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    L.bs_row_counts.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    L.bs_js_from_bits.restype = ctypes.c_int64; L.bs_js_from_bits.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
    G.gbs_create.restype = ctypes.c_void_p
    G.gbs_create.argtypes = [ctypes.c_int, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    G.gbs_block.restype = ctypes.c_int; G.gbs_block.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # ---- progression state (resume after relaunch) ----
    bid = a.bid_start - a.bid_step; blk = 0
    statef = a.state or f"/root/beacon/raid610/sieve_state_{a.seed}.json"
    try:
        stt = json.load(open(statef)); blk = int(stt["next_block"]); bid = int(stt["next_bid"]) - a.bid_step
        print(f"gbsd: resuming seed {a.seed} at block {blk} (bid {bid + a.bid_step}) from {statef}", flush=True)
    except Exception: print(f"gbsd: fresh progression for seed {a.seed} (state {statef})", flush=True)
    if blk and (stt.get("step", 2), stt.get("kclass", -1), stt.get("k0", k0)) != (a.step, a.kclass, k0):   # v8.56: never resume another progression's state
        sys.exit(f"gbsd: state {statef} is step {stt.get('step', 2)} class {stt.get('kclass', -1)} k0 {stt.get('k0', '?')} - not this daemon (step {a.step} class {a.kclass} k0 {k0})")
    def save_state(nb, nbid):
        try:
            with open(statef + ".part", "w") as f: json.dump(dict(seed=a.seed, next_block=nb, next_bid=nbid, ts=time.time(), **({} if a.step == 2 else dict(step=a.step, kclass=a.kclass, k0=k0))), f)
            os.replace(statef + ".part", statef)
        except OSError: pass
    k0_run = k0 + a.step * blk * T                                          # the SIEVE's origin is the resumed offset; rings keep absolute k0 + 2*blk*T arithmetic
    if blk: print(f"gbsd: sieve origin shifted to block {blk} (k0_run = k0 + {a.step*blk*T:,})", flush=True)
    # ---- per-prime init on the CPU (once) ----
    t0 = time.time()
    prs = np.ascontiguousarray(sv.prs, dtype=np.int64); PEm = np.ascontiguousarray(sv.PEm, dtype=np.int64)
    cut = int(np.searchsorted(prs, a.pmask, side="right")); sp = np.ascontiguousarray(prs[:cut]); se = np.ascontiguousarray(PEm[:cut])
    mp = np.ascontiguousarray(prs[cut:]); me = np.ascontiguousarray(PEm[cut:]); nmed = len(mp)
    SM = L.bs_smask_create(sp.ctypes.data, se.ctypes.data, cut, k0_run, hi); mw = L.bs_smask_words(SM)
    spc = np.empty(cut, dtype=np.int64); moff = np.empty(cut, dtype=np.int64); mtab = np.empty(mw, dtype=np.uint64); L.bs_smask_export(SM, spc.ctypes.data, moff.ctypes.data, mtab.ctypes.data)
    mtc = np.empty(nmed, dtype=np.int64); mstep = np.empty(nmed, dtype=np.int64)
    if a.step == 2: L.bs_js2_consts(k0_run, mp.ctypes.data, me.ctypes.data, nmed, hi, mtc.ctypes.data, mstep.ctypes.data)
    elif L.bs_js2_consts_s(k0_run, mp.ctypes.data, me.ctypes.data, nmed, hi, a.step, mtc.ctypes.data, mstep.ctypes.data) != 0: sys.exit("gbsd: a medium prime divides step/2 - raise --pmask")
    keep = mtc >= 0; mp2 = np.ascontiguousarray(mp[keep]); mtc2 = np.ascontiguousarray(mtc[keep]); mstep2 = np.ascontiguousarray(mstep[keep])   # drop wheel primes / p=2 from the walk list
    wheel = np.empty(BW, dtype=np.uint64); L.bs_wheel(mp.ctypes.data, me.ctypes.data, nmed, 0, hi, wheel.ctypes.data)                       # wheel primes 251<p<=1439 handled via template
    qd = np.ascontiguousarray(sv.qd, dtype=np.int64); PEd = np.ascontiguousarray(sv.PEd64, dtype=np.int64)
    rec = np.empty((len(qd), 3), dtype=np.uint64)
    if a.gpu_rings > 1: nrec = L.bs_records_flat_w(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)   # v8.57: wide layout
    else: nrec = L.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, rec.ctypes.data) if a.step == 2 else L.bs_records_flat_s(qd.ctypes.data, PEd.ctypes.data, len(qd), k0_run, T, hi, a.step, rec.ctypes.data)
    if nrec < 0: sys.exit("gbsd: a deep prime divides step/2 (impossible above 11) - stop")
    t1 = time.time()
    g = G.gbs_create(a.card, T, hi, k0_run, rec.ctypes.data, nrec, cut, sp.ctypes.data, se.ctypes.data, spc.ctypes.data, mtab.ctypes.data, moff.ctypes.data, mw, len(mp2), mp2.ctypes.data, mtc2.ctypes.data, mstep2.ctypes.data, wheel.ctypes.data)
    if not g: sys.exit("gbs_create failed (GPU memory? device?)")
    if a.step != 2 and G.gbs_set_step(g, a.step) != 0: sys.exit("gbsd: gbs_set_step failed")
    if a.gpu_rings > 1 and G.gbs_set_format(g, 1) != 0: sys.exit("gbsd: gbs_set_format failed")
    del rec
    PRED = None
    if a.pred_pb > 0 and a.select > 1:
        L.bs_pred_create.restype = ctypes.c_void_p; L.bs_pred_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]
        L.bs_pred_attach.restype = ctypes.c_void_p; L.bs_pred_attach.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
        L.bs_pred_export.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
        L.bs_predict.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int, ctypes.c_void_p]
        FULLHI = edges[-1]; base = f"/dev/shm/pred_{a.zd}_{FULLHI}_{a.pred_pb}"; lockd = base + ".lock"
        if not os.path.exists(base + ".tab.npy"):
            try:
                os.mkdir(lockd)
                wheel = np.ascontiguousarray(prs[(prs >= 13) & (prs <= a.zd)]); nl = np.zeros(1, dtype=np.int64); nw = np.zeros(1, dtype=np.int64); t0 = time.time()
                Mb = L.bs_pred_create(prs.ctypes.data, PEm.ctypes.data, len(prs), wheel.ctypes.data, len(wheel), FULLHI, a.pred_pb, nl.ctypes.data, nw.ctypes.data)
                npr, nwd = int(nl[0]), int(nw[0]); pp = np.empty(npr, dtype=np.int64); pe_ = np.empty(npr, dtype=np.int64); of = np.empty(npr, dtype=np.int64); tb = np.empty(nwd, dtype=np.uint16)
                L.bs_pred_export(Mb, pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, nwd)
                for nm, arr in (("p", pp), ("pe", pe_), ("off", of), ("tab", tb)): np.save(f"{base}.{nm}.part{os.getpid()}.npy", arr); os.replace(f"{base}.{nm}.part{os.getpid()}.npy", f"{base}.{nm}.npy")
                print(f"gbsd: predictor tables built: {npr:,} primes <= {a.pred_pb:,}, {nwd*2/1e6:.0f} MB, {time.time()-t0:.1f}s", flush=True); os.rmdir(lockd)
            except FileExistsError:
                while not os.path.exists(base + ".tab.npy"): time.sleep(2)
        pp = np.load(base + ".p.npy", mmap_mode="r"); pe_ = np.load(base + ".pe.npy", mmap_mode="r"); of = np.load(base + ".off.npy", mmap_mode="r"); tb = np.load(base + ".tab.npy", mmap_mode="r")
        PRED = L.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), FULLHI); _keep = (pp, pe_, of, tb)
    serve = [int(x) for x in a.serve.split(",")] if a.serve else []
    outs = [os.path.join(a.out, f"c{c}") for c in serve] if serve else [a.out]
    for o_ in outs: os.makedirs(o_, exist_ok=True)
    print(f"gbsd: seed {a.seed} card {a.card} k0 {k0} T {T} I {I} deepq {a.deepq:,} records {nrec:,} medium {len(mp2):,} masks {cut} | cpu init {t1-t0:.1f}s upload {time.time()-t1:.1f}s" + ('' if a.step == 2 else f" | v8.56 single-class: k = k0 + {a.step} t, class {a.kclass}") + ('' if a.gpu_rings == 1 else f" | v8.57 GPU rings 1+2 (|j| <= {hi})"), flush=True)
    bits = np.empty((T, BW), dtype=np.uint64); shmdir = f"/dev/shm/gbsd_{a.seed}"; os.makedirs(shmdir, exist_ok=True)
    pool = _mproc.get_context("fork").Pool(a.workers, initializer=_worker_init, initargs=(a.api, cfg, str(int(P_eff)), k0, T, I, Sh, BW, nb, a.select, a.alpha, a.pred_pb, a.zd, edges[-1], a.pred_threads, sc.MAGIC_C, outs, a.bid_step, a.seed, a.step, a.kclass, a.gpu_rings, r1c, a.deepq, edges[0]))
    pending = []
    while a.blocks == 0 or blk < a.blocks:
        def qlen(o_): return len([f for f in os.listdir(o_) if f.endswith(".manifest.json")])
        while min(qlen(o_) for o_ in outs) + len(pending) >= a.ahead: time.sleep(0.5)   # produce only while the emptiest queue has room
        if len(pending) >= a.workers * 2:                                   # bound the in-flight bitmaps
            pending[0].get(); pending.pop(0)
        tb = time.time()
        if G.gbs_block(g, bits.ctypes.data) != 0: sys.exit("gbs_block failed")
        while True:                                                                    # tmpfs guard: wait instead of dying (2026-09-18: a 700-ring claim burst filled /dev/shm)
            st = os.statvfs("/dev/shm")
            if st.f_bavail * st.f_frsize > 4 * 2**30: break
            print("gbsd: /dev/shm low -- waiting", flush=True); time.sleep(5)
        shmpath = f"{shmdir}/blk_{blk}.bits"; bits.tofile(shmpath)
        bid += a.bid_step
        target = min(range(len(outs)), key=lambda i: qlen(outs[i]))                          # the ring goes to the emptiest queue (bounded total = ahead x cards)
        res = pool.apply_async(_worker_ring, ((blk, shmpath, bid, target),), callback=lambda s: print(s, flush=True))
        pending.append(res); blk += 1; save_state(blk, bid + a.bid_step)
        if blk % 20 == 0: print(f"gbsd: gpu stage {time.time()-tb:.2f}s/block, in flight {len(pending)}", flush=True)
    for r in pending: r.get()
    pool.close(); pool.join()

if __name__ == "__main__": main()
