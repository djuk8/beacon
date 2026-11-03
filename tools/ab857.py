#!/usr/bin/env python3
"""ab857.py -- the v8.57 in-box A/B: daemon 2 with ring 2 deep-sieved on the GPU (--gpu-rings 2) vs daemon 1 as before.
  ab857.py mark                      A/B start mark (raid610/ab857_start.json): time + feeder-ledger offsets
  ab857.py read [--hours H]          per arm since the mark: windows, round-2 windows and their tests, ring-2 pass rate, tests per window,
                                     rung-6 entries per window, per-card tests/s (sieve cards vs the rest); expected: round-2 tests per
                                     entering window ~halved, ring-2 pass rate UNCHANGED (sieving removes only composites - the canary),
                                     rung-6 per window unchanged (both arms single-class, mirror classes 317 / 1993)
  ab857.py audit --manifest M [--n N] [--deepq Q]   ring 1 and ring 2 of N windows of a live ring vs the referee at production depth
Arms by ring id in the feeder ledgers: d1 = ids 1e9..2e9 (first sieve daemon), d2 = ids >= 2e9 (second), mixed = older rings."""
import argparse, base64, glob, json, math, os, sys, time
R = "/root/beacon/raid610"

def arm(bid):
    try: b = int(bid)
    except (TypeError, ValueError): return None
    return "d2" if b >= 2_000_000_000 else "d1" if b >= 1_000_000_000 else "mixed"

def cmd_mark(a):
    offs = {p: os.path.getsize(p) for p in glob.glob(f"{R}/queue/c*/ledger.jsonl")}
    knobs = {n: open(f"{R}/{n}.txt").read().strip() for n in ("SIEVESEED", "SIEVESEED2", "SIEVERINGS", "SIEVERINGS2") if os.path.exists(f"{R}/{n}.txt")}
    json.dump(dict(ts=time.time(), iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), offsets=offs, knobs=knobs), open(f"{R}/ab857_start.json", "w"), indent=1)
    print(f"A/B mark written: {R}/ab857_start.json ({len(offs)} ledgers, knobs {knobs})")

def ratio(x, y, nx, ny):
    if not (x and y and nx and ny): return float("nan"), float("nan"), float("nan")
    r = (x / nx) / (y / ny); s = math.sqrt(1 / x + 1 / y); return r, r * math.exp(-1.96 * s), r * math.exp(1.96 * s)

def cmd_read(a):
    st = json.load(open(f"{R}/ab857_start.json")) if os.path.exists(f"{R}/ab857_start.json") else None
    t0 = time.time() - a.hours * 3600 if a.hours else (st["ts"] if st else time.time() - 12 * 3600)
    A = {g: dict(rings=0, win=0, tests=0, t1=0, rk={r: 0 for r in range(2, 9)}, rt={r: 0 for r in range(2, 9)}) for g in ("d1", "d2", "mixed")}
    card = {}; tmin, tmax = 1e30, 0
    for p in glob.glob(f"{R}/queue/c*/ledger.jsonl"):
        with open(p, "rb") as f:
            off = (st or {}).get("offsets", {}).get(p, 0) if not a.hours else 0
            if off: f.seek(off)
            else:
                try: f.seek(-1_500_000_000, 2); f.readline()
                except OSError: f.seek(0)
            for ln in f:
                try: d = json.loads(ln)
                except Exception: continue
                ts = d.get("ts", 0)
                if ts < t0: continue
                g = arm(d.get("bid")); r = int(d.get("round", 0)); te = int(d.get("tested", 0))
                c = d.get("card"); card[c] = card.get(c, 0) + te; tmin, tmax = min(tmin, ts), max(tmax, ts)
                if g is None or not r: continue
                x = A[g]; x["tests"] += te
                if r == 1: x["rings"] += 1; x["win"] += int(d.get("ks", 0)); x["t1"] += te
                elif r in x["rk"]: x["rk"][r] += int(d.get("ks", 0)); x["rt"][r] += te
    hrs = (time.time() - t0) / 3600
    print(f"=== v8.57 A/B since {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0))} ({hrs:.1f} h) | d2 = ring 2 from the GPU daemon ===")
    print(f"{'arm':<6}{'rings':>9}{'windows':>15}{'tests/w':>9}{'r1 t/w':>8}{'r2 win':>13}{'r2 t/win':>9}{'r2 pass':>9}{'r6/Mw':>8}{'r7/Mw':>7}")
    for g in ("d1", "d2", "mixed"):
        x = A[g]
        if not x["win"]: continue
        w = x["win"]; r2 = x["rk"][2]
        print(f"{g:<6}{x['rings']:>9,}{w:>15,}{x['tests']/w:>9.2f}{x['t1']/w:>8.2f}{r2:>13,}{(x['rt'][2]/r2 if r2 else 0):>9.2f}{(x['rk'][3]/r2 if r2 else 0):>9.4f}"
              f"{x['rk'][6]/w*1e6:>8.1f}{x['rk'][7]/w*1e6:>7.2f}")
    d1, d2 = A["d1"], A["d2"]
    if d1["win"] and d2["win"] and d1["rk"][2] and d2["rk"][2]:
        p1, p2 = d1["rk"][3] / d1["rk"][2], d2["rk"][3] / d2["rk"][2]; se = math.sqrt(p1 * (1 - p1) / d1["rk"][2] + p2 * (1 - p2) / d2["rk"][2])
        print(f"  ring-2 pass rate d2 - d1: {p2 - p1:+.4f} +- {1.96 * se:.4f}  (must be ~0: a deeper sieve removes only composites)")
        print(f"  round-2 tests per entering window d2/d1: x{(d2['rt'][2]/d2['rk'][2]) / (d1['rt'][2]/d1['rk'][2]):.3f}   (expected ~x0.5)")
        print(f"  tests per window d2/d1: x{(d2['tests']/d2['win']) / (d1['tests']/d1['win']):.3f}   (expected ~x0.86)")
        q, lo, hi = ratio(d2["rk"][6], d1["rk"][6], d2["win"], d1["win"]); print(f"  rung-6 entries per window d2/d1: x{q:.3f} [{lo:.3f}, {hi:.3f}]   (expected ~x1.00: same class value)")
    if card and tmax > tmin:
        dt = tmax - tmin; print("  tests/s per card: " + "  ".join(f"c{c} {v/dt:,.0f}" for c, v in sorted(card.items(), key=lambda z: str(z[0]))))
    for lg, nm in (("gbsd_sieve.log", "d1"), ("gbsd_sieve2.log", "d2")):       # the daemons' own GPU sieve time per block (printed every 20 blocks)
        try: gs = [l.strip() for l in open(f"{R}/{lg}", errors="replace").readlines()[-400:] if "gpu stage" in l][-3:]
        except OSError: gs = []
        if gs: print(f"  {nm} ({lg}): " + " | ".join(x.replace("gbsd: ", "") for x in gs))

def cmd_audit(a):
    import ctypes as C, numpy as np
    sys.path.insert(0, R); import scanhunt_v0 as sc
    m = json.load(open(a.manifest)); ks = m["ks"]; dq = a.deepq or int(open(f"{R}/BSDQ.txt").read().strip()); e = m["cfg"]["edges"]
    ns = argparse.Namespace(zd=1439, swap=[2, 3, 5, 7, 11], kdig=13, merit=45.0, Q=1_000_000, deep_q=dq, deep_from_ring=1, rings=",".join(map(str, e)), bits=2048, seed=0, kblock=20000, select=12, fast=2)
    cfg, P = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P, cache=f"{R}/.sc_cache")
    L = C.CDLL(a.ref); L.ref_bits.argtypes = [C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_int]
    rng = np.random.default_rng(int(time.time())); idx = sorted(rng.choice(len(ks), min(a.n, len(ks)), replace=False).tolist())
    kk = np.ascontiguousarray(np.array([ks[i] for i in idx], dtype=np.int64)); prs = np.ascontiguousarray(sv.prs, dtype=np.int64); pem = np.ascontiguousarray(sv.PEm, dtype=np.int64)
    qd = np.ascontiguousarray(sv.qd, dtype=np.int64); pe = np.ascontiguousarray(sv.PEd64, dtype=np.int64)
    def ref(lo, hi):
        sh = hi // 2; bw = (2 * sh + 1 + 63) // 64; out = np.zeros((len(kk), bw), dtype=np.uint64)
        L.ref_bits(kk.ctypes.data, len(kk), prs.ctypes.data, pem.ctypes.data, len(prs), qd.ctypes.data, pe.ctypes.data, len(qd), lo, hi, out.ctypes.data, a.threads)
        return [(2 * (np.nonzero(np.unpackbits(out[x].view(np.uint8), bitorder="little")[:2 * sh + 1])[0] - sh)).tolist() for x in range(len(kk))]
    t = time.time(); r1 = ref(0, e[0]); bad1 = sum(1 for x, i in enumerate(idx) if sorted(m["js"][i]) != r1[x]); bad2 = None
    if "r2" in m:
        R2 = m["r2"]; allj = np.frombuffer(base64.b64decode(R2["b64"]), dtype="<i2").astype(np.int64); off = np.concatenate([[0], np.cumsum(R2["cnt"])]).astype(np.int64)
        r2 = ref(R2["lo"], R2["hi"]); bad2 = sum(1 for x, i in enumerate(idx) if sorted(allj[off[i]:off[i + 1]].tolist()) != r2[x])
    ok = bad1 == 0 and (bad2 in (None, 0)) and ("r2" in m or not a.need_r2)
    print(f"AUDIT {'PASS' if ok else 'FAIL'}: {os.path.basename(a.manifest)} | {len(idx)} of {len(ks):,} windows vs referee at {dq:.0e} -> ring 1 {bad1} differ"
          f" | ring 2 {'absent' if bad2 is None else f'{bad2} differ'} | origin {m.get('origin')} | {time.time() - t:.0f}s")
    sys.exit(0 if ok else 2)

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
sp.add_parser("mark"); r_ = sp.add_parser("read"); r_.add_argument("--hours", type=float, default=0)
au = sp.add_parser("audit"); au.add_argument("--manifest", required=True); au.add_argument("--deepq", type=int, default=0); au.add_argument("--n", type=int, default=32)
au.add_argument("--threads", type=int, default=32); au.add_argument("--ref", default=f"{R}/ref856.so"); au.add_argument("--need-r2", action="store_true")
a = ap.parse_args(); dict(mark=cmd_mark, read=cmd_read, audit=cmd_audit)[a.cmd](a)
