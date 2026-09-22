#!/usr/bin/env python3
"""bsd.py -- bucket-sieve daemon: one progression per card, persistent sieve to Q_deep, emits SELECTED rung-1 rings.
usage: bsd.py --seed S --card C --out READYDIR [--deepq 1e10] [--select 12] [--kblock 20000] [--ahead 20] [--blocks N]
Ring naming/contents are exactly what `scanhunt make --round 1 --select N` produces (gated byte-identical)."""
import argparse, ctypes, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scanhunt_v0 as sc, fastmake

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True); ap.add_argument("--card", type=int, default=0); ap.add_argument("--out", required=True)
    ap.add_argument("--deepq", type=int, default=10_000_000_000); ap.add_argument("--select", type=int, default=12)
    ap.add_argument("--kblock", type=int, default=20000); ap.add_argument("--ahead", type=int, default=20); ap.add_argument("--blocks", type=int, default=0); ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--bid-start", type=int, default=1); ap.add_argument("--bid-step", type=int, default=1)
    ap.add_argument("--shallow-threads", type=int, default=2)   # js2 sub-blocks per block: per-prime setup is paid per sub-block, so keep this small
    ap.add_argument("--pred-pb", type=int, default=100000)      # predictor: residue tables for linear primes <= pred-pb (0 = off: rank by rung-1 count only)
    ap.add_argument("--alpha", type=float, default=0.6)         # rank score = z(predicted full-window kills) - alpha * z(rung-1 survivors)
    ap.add_argument("--pred-threads", type=int, default=4)   # N daemons per card: start d+1, step N -> unique integer bids
    ap.add_argument("--zd", type=int, default=1439); ap.add_argument("--bits", type=int, default=2048)
    ap.add_argument("--rings", default="1568,4374,7244,10198,13500,17734,22818,31576"); ap.add_argument("--api", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "bs_api.so"))
    a = ap.parse_args()
    ns = argparse.Namespace(zd=a.zd, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=1_000_000, deep_q=a.deepq, deep_from_ring=1,
                            rings=a.rings, bits=a.bits, seed=a.seed, kblock=a.kblock, select=a.select, fast=2)
    cfg, P_eff = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P_eff)
    edges = [int(x) for x in a.rings.split(",")]; hi = edges[0]; Sh = hi // 2; I = 2 * Sh + 1; BW = (I + 63) // 64
    T = a.kblock * a.select; k0 = sc.kstart(cfg); nb = a.bits // 8
    lib = ctypes.CDLL(a.api)
    lib.bs_create_mt.restype = ctypes.c_void_p; lib.bs_create_mt.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int]
    lib.bs_block_mt.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; lib.bs_set_tmap_mt.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.bs_smask_create.restype = ctypes.c_void_p; lib.bs_smask_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int64, ctypes.c_int64]
    lib.bs_smask_apply.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p]
    lib.bs_js2_bits.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    lib.bs_rows_init.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    lib.bs_bits_from_js.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p]
    lib.bs_js_from_bits.restype = ctypes.c_int64; lib.bs_js_from_bits.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
    qd = np.ascontiguousarray(sv.qd, dtype=np.int64); PEd = np.ascontiguousarray(sv.PEd64, dtype=np.int64)
    prs = np.ascontiguousarray(sv.prs, dtype=np.int64); PEm = np.ascontiguousarray(sv.PEm, dtype=np.int64); cut = int(np.searchsorted(prs, 251, side="right"))
    # ---- full-window sparsity predictor: shared residue tables on tmpfs (built once per venue by whoever comes first) ----
    PRED = None
    if a.pred_pb > 0:
        lib.bs_pred_create.restype = ctypes.c_void_p; lib.bs_pred_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p]
        lib.bs_pred_attach.restype = ctypes.c_void_p; lib.bs_pred_attach.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64]
        lib.bs_pred_export.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64]
        lib.bs_predict.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_int, ctypes.c_void_p]
        FULLHI = edges[-1]; base = f"/dev/shm/pred_{a.zd}_{FULLHI}_{a.pred_pb}"; lockd = base + ".lock"
        if not os.path.exists(base + ".tab.npy"):
            try:
                os.mkdir(lockd)                                                      # atomic: the builder
                wheel = np.ascontiguousarray(prs[(prs >= 13) & (prs <= a.zd)]); nl = np.zeros(1, dtype=np.int64); nw = np.zeros(1, dtype=np.int64); t0 = time.time()
                Mb = lib.bs_pred_create(prs.ctypes.data, PEm.ctypes.data, len(prs), wheel.ctypes.data, len(wheel), FULLHI, a.pred_pb, nl.ctypes.data, nw.ctypes.data)
                npr, nwd = int(nl[0]), int(nw[0]); pp = np.empty(npr, dtype=np.int64); pe_ = np.empty(npr, dtype=np.int64); of = np.empty(npr, dtype=np.int64); tb = np.empty(nwd, dtype=np.uint16)
                lib.bs_pred_export(Mb, pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, nwd)
                for nm, arr in (("p", pp), ("pe", pe_), ("off", of), ("tab", tb)): np.save(f"{base}.{nm}.part{os.getpid()}.npy", arr); os.replace(f"{base}.{nm}.part{os.getpid()}.npy", f"{base}.{nm}.npy")
                print(f"bsd: predictor tables built: {npr:,} primes <= {a.pred_pb:,}, {nwd*2/1e6:.0f} MB on tmpfs, {time.time()-t0:.1f}s", flush=True)
                os.rmdir(lockd)
            except FileExistsError:
                while not os.path.exists(base + ".tab.npy"): time.sleep(2)              # someone else is building
        pp = np.load(base + ".p.npy", mmap_mode="r"); pe_ = np.load(base + ".pe.npy", mmap_mode="r"); of = np.load(base + ".off.npy", mmap_mode="r"); tb = np.load(base + ".tab.npy", mmap_mode="r")
        PRED = lib.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), FULLHI); _keep = (pp, pe_, of, tb)
    sp = np.ascontiguousarray(prs[:cut]); se = np.ascontiguousarray(PEm[:cut]); hp = np.ascontiguousarray(prs[cut:]); he = np.ascontiguousarray(PEm[cut:])
    SM = lib.bs_smask_create(sp.ctypes.data, se.ctypes.data, cut, k0, hi)          # small-prime masks (p <= 251), wheel + linear
    t0 = time.time(); S = lib.bs_create_mt(qd.ctypes.data, PEd.ctypes.data, len(qd), k0, T, hi, a.threads)
    print(f"bsd: seed {a.seed} card {a.card} k0 {k0} T {T} I {I} deepq {a.deepq:,} primes {len(qd):,} threads {a.threads} init {time.time()-t0:.1f}s", flush=True)
    os.makedirs(a.out, exist_ok=True); bid = 0; blk = 0
    from concurrent.futures import ThreadPoolExecutor
    import queue as _q, threading
    def prep(blk):
        """shallow stage for block blk on a COMPACT bitmap (one row per coprime window): init -> masks (p<=251) -> js2_bits (p>251)"""
        ks_all = k0 + 2 * (blk * T + np.arange(T, dtype=np.int64))
        cop = np.array([math.gcd(int(k), 2310) == 1 for k in ks_all.tolist()]); rows_t = np.nonzero(cop)[0].astype(np.int32); ks = np.ascontiguousarray(ks_all[rows_t]); nk = len(ks)
        tmap = np.full(T, -1, dtype=np.int32); tmap[rows_t] = np.arange(nk, dtype=np.int32)
        bb = np.zeros((nk, BW), dtype=np.uint64); rows_c = np.arange(nk, dtype=np.int32)
        lib.bs_rows_init(rows_c.ctypes.data, nk, 0, hi, bb.ctypes.data)
        lib.bs_smask_apply(SM, blk * T, rows_t.ctypes.data, nk, bb.ctypes.data)     # NOTE: window t = blk*T + rows_t[k]; row = k (compact)
        nsub = max(1, a.shallow_threads); bounds = [(nk * i // nsub, nk * (i + 1) // nsub) for i in range(nsub)]
        def shallow(b):
            lo_, hi_ = b; sub_ks = np.ascontiguousarray(ks[lo_:hi_]); sub_rows = np.ascontiguousarray(np.arange(lo_, hi_, dtype=np.int32))
            Tsub = int((sub_ks[-1] - sub_ks[0]) // 2 + 1)
            lib.bs_js2_bits(sub_ks.ctypes.data, len(sub_ks), sub_rows.ctypes.data, hp.ctypes.data, he.ctypes.data, len(hp), 0, hi, Tsub, bb.ctypes.data)
        with ThreadPoolExecutor(nsub) as ex: list(ex.map(shallow, bounds))
        return blk, rows_c, ks, tmap, bb
    ready_q = _q.Queue(maxsize=2)
    def producer():
        b = 0
        while a.blocks == 0 or b < a.blocks: ready_q.put(prep(b)); b += 1
        ready_q.put(None)
    threading.Thread(target=producer, daemon=True).start()
    pack_q = _q.Queue(maxsize=2); state = {"bid": a.bid_start - a.bid_step}
    def packer():
        while True:
            it = pack_q.get()
            if it is None: return
            blk, ks_sel, js_sel, t_sieve, tb, zsel = it; t2 = time.time()
            pjs, psizes, packed = fastmake.pack_given(ks_sel, js_sel, int(P_eff), nb)
            state["bid"] += a.bid_step; bid_ = state["bid"]; name = f"sc_r01_{bid_:04d}"; tmp = os.path.join(a.out, f".{name}.tmp")
            with open(tmp + ".bin", "wb") as f: f.write(__import__("struct").pack("<IIQ", sc.MAGIC_C, cfg["bits"], sum(psizes))); f.write(packed)
            man = dict(cfg=cfg, round=1, bid=bid_, ks=ks_sel, js=[j.tolist() for j in pjs], sizes=list(psizes), origin=dict(bsd=1, seed=a.seed, card=a.card, block=blk, deepq=a.deepq, select=a.select, pred_pb=a.pred_pb, alpha=a.alpha, pred_z=round(zsel, 3)))
            json.dump(man, open(tmp + ".manifest.json", "w"))
            os.replace(tmp + ".bin", os.path.join(a.out, name + ".bin")); os.replace(tmp + ".manifest.json", os.path.join(a.out, name + ".manifest.json"))
            print(f"bsd: block {blk} -> {name}: {len(ks_sel)} ks, {sum(psizes):,} cands (mean {sum(psizes)/max(len(psizes),1):.1f}/k) | sieve {t_sieve:.2f}s pack {time.time()-t2:.2f}s ring-to-ring {time.time()-tb:.1f}s pred_z {zsel:+.2f}", flush=True)
    pt = threading.Thread(target=packer, daemon=True); pt.start()
    while True:
        item = ready_q.get()
        if item is None: break
        while len([f for f in os.listdir(a.out) if f.endswith(".manifest.json")]) >= a.ahead: time.sleep(2)   # backpressure
        blk, rows, ks, tmap, bits = item; tb = time.time()
        t1 = time.time(); lib.bs_set_tmap_mt(S, tmap.ctypes.data); lib.bs_block_mt(S, bits.ctypes.data); t2 = time.time()
        out = np.empty(len(rows) * (I // 4) + 16, dtype=np.int32); cnt2 = np.empty(len(rows), dtype=np.int32)
        tot = lib.bs_js_from_bits(bits.ctypes.data, BW, I, Sh, rows.ctypes.data, len(rows), out.ctypes.data, cnt2.ctypes.data, len(out)); assert tot >= 0
        offs = np.concatenate([[0], np.cumsum(cnt2)[:-1]]); nkeep = len(rows) // a.select if a.select > 1 else len(rows)
        if PRED is not None and a.select > 1:
            pr = np.zeros(T); lib.bs_predict(PRED, int(k0 + 2 * blk * T), T, a.pred_threads, pr.ctypes.data)
            prc = pr[np.nonzero(tmap >= 0)[0]]                                           # predicted kills for the coprime rows, in row order
            s1 = cnt2.astype(float); score = (prc - prc.mean()) / (prc.std() + 1e-9) - a.alpha * (s1 - s1.mean()) / (s1.std() + 1e-9)
            keep = np.sort(np.argsort(-score, kind="stable")[:nkeep]); zsel = float(((prc[keep] - prc.mean()) / (prc.std() + 1e-9)).mean())
        else:
            keep = np.sort(np.argsort(cnt2, kind="stable")[:nkeep]); zsel = 0.0
        ks_sel = ks[keep].tolist(); js_sel = [out[offs[i]:offs[i] + cnt2[i]].copy() for i in keep]
        pack_q.put((blk, ks_sel, js_sel, t2 - t1, tb, zsel))
    pack_q.put(None); pt.join()

if __name__ == "__main__": main()
