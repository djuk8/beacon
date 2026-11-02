#!/usr/bin/env python3
"""ab856.py -- the v8.56 in-box A/B: single-class rings (bids >= 1e9) vs the mixed-class daemon (bids < 1e9), same box, same hours.
  ab856.py mark                      write the A/B start mark (raid610/ab856_start.json): time + feeder-ledger offsets
  ab856.py read [--hours H]          per arm since the mark (or the last H hours): rings, windows, tests, ring-1 candidates/window,
                                     rung entries (r2..r8) per million windows, walked finds >= 30 / 32 / 36 per million windows,
                                     single/mixed ratios with 95% intervals vs the CLASS_RESULT_v0 predictions (x1.077 rung 6, x1.22 >= 30)
  ab856.py audit --manifest M [--deepq Q] [--n N] [--threads T]
                                     N windows of a live ring vs the referee (ref856.so) at the production depth (default BSDQ.txt)
Arms come from the feeder ledgers (queue/c*/ledger.jsonl: every round's record carries the ring's bid) and, for walked finds,
from k itself (single-class k >= 1e15). Cards steal rings from each other's queues, so arms are split by ring, never by card."""
import argparse, glob, json, math, os, sys, time
R = "/root/beacon/raid610"
PRED = {6: 1.077, "m30": 1.22}

def arm(bid):
    try: b = int(bid)
    except (TypeError, ValueError): return None
    return "single" if b >= 1_000_000_000 else "mixed"          # single-class daemons number rings from 1e9 / 2e9

def cmd_mark(a):
    offs = {p: os.path.getsize(p) for p in glob.glob(f"{R}/queue/c*/ledger.jsonl")}
    knobs = {n: open(f"{R}/{n}.txt").read().strip() for n in ("SIEVESEED", "SIEVESEED2", "SIEVESTEP", "SIEVESTEP2", "SIEVECLASS", "SIEVECLASS2") if os.path.exists(f"{R}/{n}.txt")}
    json.dump(dict(ts=time.time(), iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), offsets=offs, knobs=knobs), open(f"{R}/ab856_start.json", "w"), indent=1)
    print(f"A/B mark written: {R}/ab856_start.json ({len(offs)} ledgers, knobs {knobs})")

def ci(x, y, nx, ny):
    """ratio of rates (x/nx)/(y/ny) with a 95% interval (Poisson counts x, y; exposures nx, ny)"""
    if x == 0 or y == 0: return float("nan"), float("nan"), float("nan")
    r = (x / nx) / (y / ny); s = math.sqrt(1 / x + 1 / y); return r, r * math.exp(-1.96 * s), r * math.exp(1.96 * s)

def cmd_read(a):
    st = json.load(open(f"{R}/ab856_start.json")) if os.path.exists(f"{R}/ab856_start.json") else None
    t0 = time.time() - a.hours * 3600 if a.hours else (st["ts"] if st else time.time() - 24 * 3600)
    A = {k: dict(rings=0, win=0, tests=0, n1=0, rung={r: 0 for r in range(2, 9)}) for k in ("single", "mixed")}
    for p in glob.glob(f"{R}/queue/c*/ledger.jsonl"):
        with open(p, "rb") as f:
            off = (st or {}).get("offsets", {}).get(p, 0) if not a.hours else 0
            if not off:
                try: f.seek(-1_500_000_000, 2); f.readline()
                except OSError: f.seek(0)
            else: f.seek(off)
            for ln in f:
                try: d = json.loads(ln)
                except Exception: continue
                if d.get("ts", 0) < t0: continue
                g = arm(d.get("bid")); r = int(d.get("round", 0))
                if g is None or not r: continue
                x = A[g]; x["tests"] += int(d.get("tested", 0))
                if r == 1: x["rings"] += 1; x["win"] += int(d.get("ks", 0)); x["n1"] += int(d.get("n", 0))
                elif r in x["rung"]: x["rung"][r] += int(d.get("ks", 0))
    F = {k: {30: 0, 32: 0, 36: 0, 40: 0} for k in ("single", "mixed")}; t0iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)); best = {"single": None, "mixed": None}
    if os.path.exists(f"{R}/campaign_ledger.log"):
        for ln in open(f"{R}/campaign_ledger.log"):
            f_ = ln.split()
            if len(f_) < 6 or f_[5] < t0iso: continue
            try: gap, merit, k = int(f_[0]), float(f_[1]), int(f_[2])
            except ValueError: continue
            g = "single" if k >= 10 ** 15 else "mixed"
            for m in F[g]:
                if merit >= m: F[g][m] += 1
            if best[g] is None or merit > best[g][1]: best[g] = (gap, merit, k)
    hrs = (time.time() - t0) / 3600
    print(f"=== v8.56 A/B since {t0iso} ({hrs:.1f} h){'' if st else ' (no mark file: last 24 h)'} ===")
    print(f"{'arm':<8}{'rings':>8}{'windows':>14}{'tests':>16}{'cand/w r1':>11}" + "".join(f"{'r' + str(r) + '/Mw':>10}" for r in range(2, 9)) + f"{'>=30/Mw':>10}{'>=32/Mw':>10}")
    for g in ("single", "mixed"):
        x = A[g]; w = max(x["win"], 1)
        print(f"{g:<8}{x['rings']:>8,}{x['win']:>14,}{x['tests']:>16,}{x['n1'] / w:>11.1f}" + "".join(f"{x['rung'][r] / w * 1e6:>10.1f}" for r in range(2, 9))
              + f"{F[g][30] / w * 1e6:>10.2f}{F[g][32] / w * 1e6:>10.2f}")
    s, m = A["single"], A["mixed"]
    if s["win"] and m["win"]:
        for r in (2, 4, 6, 7):
            q, lo, hi = ci(s["rung"][r], m["rung"][r], s["win"], m["win"])
            print(f"  rung-{r} entries per window, single/mixed: x{q:.3f} [{lo:.3f}, {hi:.3f}]" + (f"   predicted x{PRED[6]:.3f}" if r == 6 else ""))
        q, lo, hi = ci(s["rung"][6], m["rung"][6], s["tests"], m["tests"]); print(f"  rung-6 entries per TEST,   single/mixed: x{q:.3f} [{lo:.3f}, {hi:.3f}]   (tests/window single {s['tests']/s['win']:.1f} mixed {m['tests']/m['win']:.1f})")
        for t in (30, 32):
            q, lo, hi = ci(F["single"][t], F["mixed"][t], s["win"], m["win"])
            print(f"  walked merit >= {t} per window, single/mixed: x{q:.3f} [{lo:.3f}, {hi:.3f}]  ({F['single'][t]} vs {F['mixed'][t]})" + (f"   predicted x{PRED['m30']:.2f}" if t == 30 else ""))
        print("  (finds lag the rings by the hourly walk; read >= 30 after 3-4 days for a usable interval)")
    for g in ("single", "mixed"):
        if best[g]: print(f"  best {g}: gap {best[g][0]} merit {best[g][1]:.4f} k={best[g][2]}")

def cmd_audit(a):
    import ctypes as C, numpy as np
    sys.path.insert(0, R); import scanhunt_v0 as sc
    m = json.load(open(a.manifest)); ks = m["ks"]; dq = a.deepq or int(open(f"{R}/BSDQ.txt").read().strip())
    ns = argparse.Namespace(zd=1439, swap=[2, 3, 5, 7, 11], kdig=13, merit=45.0, Q=1_000_000, deep_q=dq, deep_from_ring=1, rings=",".join(map(str, m["cfg"]["edges"])), bits=2048, seed=0, kblock=20000, select=12, fast=2)
    cfg, P = sc.cfg_of(ns); sv = sc.ScanSieve(cfg, P, cache=f"{R}/.sc_cache"); hi = m["cfg"]["edges"][0]; Sh = hi // 2; BW = (2 * Sh + 1 + 63) // 64
    L = C.CDLL(a.ref); L.ref_bits.argtypes = [C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_int]
    rng = np.random.default_rng(int(time.time())); idx = sorted(rng.choice(len(ks), min(a.n, len(ks)), replace=False).tolist())
    kk = np.ascontiguousarray(np.array([ks[i] for i in idx], dtype=np.int64)); prs = np.ascontiguousarray(sv.prs, dtype=np.int64); pem = np.ascontiguousarray(sv.PEm, dtype=np.int64)
    qd = np.ascontiguousarray(sv.qd, dtype=np.int64); pe = np.ascontiguousarray(sv.PEd64, dtype=np.int64); out = np.zeros((len(kk), BW), dtype=np.uint64); t = time.time()
    L.ref_bits(kk.ctypes.data, len(kk), prs.ctypes.data, pem.ctypes.data, len(prs), qd.ctypes.data, pe.ctypes.data, len(qd), 0, hi, out.ctypes.data, a.threads)
    bad = 0
    for x, i in enumerate(idx):
        b = np.unpackbits(out[x].view(np.uint8), bitorder="little")[:2 * Sh + 1]; js = (2 * (np.nonzero(b)[0] - Sh)).tolist()
        if sorted(m["js"][i]) != js: bad += 1
    cls = sorted({k % 2310 for k in ks}); ok = bad == 0
    print(f"AUDIT {'PASS' if ok else 'FAIL'}: {os.path.basename(a.manifest)} | {len(idx)} of {len(ks):,} windows vs referee at {dq:.0e} ({len(qd):,} deep primes) "
          f"-> {bad} differ | classes {cls[:4]} | k {ks[0]}..{ks[-1]} | origin {m.get('origin')} | {time.time() - t:.0f}s")
    sys.exit(0 if ok else 2)

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
sp.add_parser("mark"); r_ = sp.add_parser("read"); r_.add_argument("--hours", type=float, default=0)
au = sp.add_parser("audit"); au.add_argument("--manifest", required=True); au.add_argument("--deepq", type=int, default=0); au.add_argument("--n", type=int, default=32)
au.add_argument("--threads", type=int, default=32); au.add_argument("--ref", default=f"{R}/ref856.so")
a = ap.parse_args(); dict(mark=cmd_mark, read=cmd_read, audit=cmd_audit)[a.cmd](a)
