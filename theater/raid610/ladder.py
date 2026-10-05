#!/usr/bin/env python3
"""ladder.py -- the ladder manager (2026-09-17). ONE process per card replaces that card's 175 shell loops.

Same files, same protocol, same outputs as raid_loop_v2.sh: per seed a work dir (/dev/shm/beacon/hunt_s<S>) with the
loop's fixed names (sc_r0R_<bid>.bin/.manifest.json/.v.bin, sc_carry_rRR.json, sc_state.json), requests into the card's
feeder queue (<Q>/req/<name>.json), verdict = the .v.bin appearing; fold / make / finish are scanhunt's own functions,
called in-process by a pool of forked workers (no interpreter starts, sieve object cached); fossils (manifests, rung >= 6)
copied to the overlay hunt dir; finish output appended to finish.log; per-seed hunt logs kept.
Differences from the shell loop, by design: no legacy direct-drive fallback (a failed/absent feeder abandons the ring and
logs it); verdicts polled once per tick for all windows instead of 700 shells polling.
"""
import os, sys, json, time, glob, shutil, random, argparse, contextlib, multiprocessing as mp, io
HOME = os.path.expanduser("~"); R610 = f"{HOME}/beacon/raid610"

def venue_args(seed, venue, a):
    import venue as _venue; _V = _venue.load()
    if venue == "crown" and _V["name"] == "crown": rings, merit = "1568,4374,7244,10198,13500,17734,22818,31576", 45.0
    elif venue == "raid": rings, merit = "1568,4374,7244,10198,13500,17734,26542", 37.8241
    else: rings, merit = _V["rings"], float(_V["merit"])
    def kn(n, d):
        try: return open(f"{R610}/{n}.txt").read().strip() or d
        except OSError: return d
    deepq = int(kn("DEEPQ", "0")); deepr = int(kn("DEEPR", "1")); select = int(kn("SELECT", "1"))
    return dict(zd=_V["zd"], swap=list(_V["swap"]), kdig=_V["kdig"], merit=merit, Q=100000, deep_q=deepq, deep_from_ring=1, deep_rings=deepr,
                select=select, rings=rings, bits=_V["bits"], seed=seed, kblock=20000, fast=2, max_prp=60000, bin=None, round=1)

# ---------------- workers: in-process scanhunt, cwd = the window's work dir ----------------
_S = {}
def _winit(kitdir):
    sys.path.insert(0, kitdir); import scanhunt_v0 as sc
    real = sc.ScanSieve; cache = {}
    def cached(cfg, P):                                                  # one sieve object per cfg per worker (the loop rebuilt it per call)
        key = json.dumps(cfg, sort_keys=True) + str(P)
        if key not in cache: cache[key] = real(cfg, P)
        return cache[key]
    sc.ScanSieve = cached; _S["sc"] = sc

def _rung(path, r):
    d, b = os.path.split(path); return os.path.join(d, b.replace("r01", f"r{r:02d}", 1))

def _run(task):
    """task = (kind, workdir, logpath, argsdict). Runs make/fold/finish in cwd=workdir; stdout -> logpath (append). Returns (ok, msg)."""
    kind, workdir, logpath, ad = task; sc = _S["sc"]; a = argparse.Namespace(**ad)
    os.chdir(workdir)
    try:
        with open(logpath, "a") as lg, contextlib.redirect_stdout(lg):
            if kind == "fold": sc.cmd_fold(a)
            elif kind == "make": sc.cmd_make(a)
            elif kind == "finish": sc.cmd_finish(a)
        return True, ""
    except SystemExit as e: return False, f"exit {e}"
    except Exception as e: return False, f"{type(e).__name__}: {e}"

# ---------------- the window state machine ----------------
class Window:
    def __init__(self, seed, card, a):
        self.S = seed; self.C = card; self.a = a; self.state = "IDLE"; self.R = 0; self.B = None; self.t0 = 0; self.req = None; self.out = None; self.fut = None
        self.home = f"{R610}/hunt_s{seed}"; self.work = f"{a.work_base}/hunt_s{seed}"; self.log = f"{R610}/hunt_s{seed}.log"
        os.makedirs(self.home, exist_ok=True); os.makedirs(self.work, exist_ok=True)
        for f in ("sc_state.json", "finish.log"):
            p = f"{self.work}/{f}"
            if not os.path.islink(p):
                try: os.remove(p)
                except OSError: pass
                os.symlink(f"{self.home}/{f}", p)
        p = f"{self.work}/.sc_cache"
        if not os.path.islink(p): os.symlink(f"{R610}/.sc_cache", p)
    def logline(self, s):
        with open(self.log, "a") as f: f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {s}\n")

class Ladder:
    def __init__(self, a):
        self.a = a; self.Q = f"{R610}/queue/c{a.card}"; os.makedirs(f"{self.Q}/req", exist_ok=True); os.makedirs(f"{self.Q}/cancelled", exist_ok=True)
        self.NR = len(venue_args(1, a.venue, a)["rings"].split(","))
        self.wins = [Window(s, a.card, a) for s in a.seeds]
        self.pool = mp.get_context("fork").Pool(a.workers, initializer=_winit, initargs=(a.kitdir,))
        self.ready_own = f"{R610}/ready/c{a.card}"; self.slots = 0; self.inflight_r1 = 0
    # ---- ring supply ----
    def claim(self, w):
        for rd in ([self.ready_own] + sorted(glob.glob(f"{R610}/ready/c*"))):
            fs = glob.glob(f"{rd}/sc_r01_*.manifest.json")
            if not fs: continue
            f = random.choice(fs); n = os.path.basename(f)[:-len(".manifest.json")]
            try: os.rename(f, f"{w.work}/{n}.manifest.json")
            except OSError: continue
            try: os.rename(f"{rd}/{n}.bin", f"{w.work}/{n}.bin")
            except OSError: os.remove(f"{w.work}/{n}.manifest.json"); w.logline(f"BSD: bin missing for {n}"); continue
            return n
        return None
    # ---- feeder protocol ----
    def submit(self, w, bb):
        out = bb[:-4] + ".v.bin"; name = f"s{w.S}_r{w.R}_{os.path.basename(bb)[:-4]}_{os.getpid()}"; req = f"{self.Q}/req/{name}.json"
        with open(req + ".part", "w") as f: f.write(json.dumps(dict(bin=bb, out=out, seed=w.S, round=w.R, bid=os.path.basename(bb)[:-4].split("_")[-1])) + "\n")
        os.replace(req + ".part", req); w.req = req; w.reqname = name; w.out = out; w.t0 = time.time(); w.state = "WAIT"
    def dispatch(self, w, kind, extra=None):
        ad = dict(venue_args(w.S, self.a.venue, self.a)); ad["round"] = w.R if kind != "make" else w.R + 1
        if extra: ad.update(extra)
        logp = f"{w.work}/finish.log" if kind == "finish" else w.log
        w.fut = self.pool.apply_async(_run, ((kind, w.work, logp, ad),)); w.state = kind.upper()
    # ---- one tick ----
    def tick(self):
        self.inflight_r1 = sum(1 for w in self.wins if w.state == "WAIT" and w.R == 1)
        for w in self.wins:
            try: self.step(w)
            except Exception as e: w.logline(f"LADDER ERROR {w.state} r{w.R}: {type(e).__name__}: {e}"); self.reset(w)
    def reset(self, w):
        for f in glob.glob(f"{w.work}/sc_r0*") + glob.glob(f"{w.work}/sc_carry_r*.json"):
            try: os.remove(f)
            except OSError: pass
        w.state = "IDLE"; w.R = 0; w.B = None; w.fut = None
    def step(self, w):
        a = self.a
        if w.state == "IDLE":
            for f in glob.glob(f"{w.work}/sc_r0*") + glob.glob(f"{w.work}/sc_carry_r*.json"): os.remove(f)
            if a.bsd:
                if self.inflight_r1 >= a.max_r1: return                                   # cap rung-1 rings in flight per card (tmpfs footprint, feeder queueing)
                st = os.statvfs("/dev/shm")
                if st.f_bavail * st.f_frsize < a.shm_min_gb * 2**30: return               # tmpfs watermark (the shell loop's shm_wait)
                n = self.claim(w)
                if not n: return                                            # wait for supply (boxes with daemons wait)
                w.B = f"{w.work}/{n}.bin"; w.R = 1; self.submit(w, w.B)
            else:                                                            # no daemon: make rung 1 in-process
                w.R = 1; self.dispatch(w, "make", dict(round=1)); w.state = "MAKE1"
        elif w.state == "MAKE1":
            if not w.fut.ready(): return
            ok, msg = w.fut.get(); w.fut = None
            if not ok: w.logline(f"MAKE r1 FAIL {msg}"); self.reset(w); return
            bins = sorted(glob.glob(f"{w.work}/sc_r01_*.bin"), key=os.path.getmtime)
            if not bins: self.reset(w); return
            w.B = bins[-1]; self.submit(w, w.B)
        elif w.state == "WAIT":
            bb = _rung(w.B, w.R)
            if os.path.exists(w.out) and os.path.getsize(w.out) > 0:
                if w.R >= 6:                                                                  # fossil (manifest only), UNIQUE name: rung_bid_firstk (bids collide across daemons)
                    src = bb[:-4] + ".manifest.json"
                    try: k0 = json.load(open(src))["ks"][0]
                    except Exception: k0 = int(time.time() * 1e6)
                    shutil.copy2(src, f"{w.home}/{os.path.basename(src)[:-len('.manifest.json')]}_{k0}.manifest.json")
                self.dispatch(w, "fold", dict(bin=bb)); return
            failed = os.path.exists(f"{self.Q}/failed/{w.reqname}.json"); age = time.time() - w.t0
            if failed or age > a.wait2:
                w.logline(f"FEEDER {'FAILED' if failed else 'STUCK'} {bb} after {age:.1f}s (wait2 {a.wait2}) -- abandoned")
                try: os.replace(w.req, f"{self.Q}/cancelled/{w.reqname}.json")
                except OSError: pass
                self.reset(w)
        elif w.state == "FOLD":
            if not w.fut.ready(): return
            ok, msg = w.fut.get(); w.fut = None; bb = _rung(w.B, w.R)
            if not ok: w.logline(f"FOLD FAIL {bb} -- block abandoned: {msg}"); self.reset(w); return
            for f in (bb, bb[:-4] + ".v.bin"): 
                try: os.remove(f)
                except OSError: pass
            if w.R <= 5:
                try: os.remove(bb[:-4] + ".manifest.json")
                except OSError: pass
            if w.R < self.NR: self.dispatch(w, "make")
            else: self.dispatch(w, "finish"); w.state = "FINISH"
        elif w.state == "MAKE":
            if not w.fut.ready(): return
            ok, msg = w.fut.get(); w.fut = None
            if not ok: w.logline(f"MAKE r{w.R+1} FAIL {msg}"); self.reset(w); return
            nb = _rung(w.B, w.R + 1)
            if os.path.exists(nb): w.R += 1; self.submit(w, nb)
            else: self.dispatch(w, "finish"); w.state = "FINISH"              # no survivors carried: the ladder ends here
        elif w.state == "FINISH":
            if not w.fut.ready(): return
            w.fut.get(); w.fut = None; self.reset(w)
    def run(self):
        last = 0
        while True:
            self.tick(); time.sleep(self.a.tick)
            if time.time() - last > 60:
                st = {}
                for w in self.wins: st[w.state] = st.get(w.state, 0) + 1
                print(f"ladder c{self.a.card}: {dict(sorted(st.items()))}", flush=True); last = time.time()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--card", type=int, required=True); ap.add_argument("--seeds", required=True, help="comma list or a-b range")
    ap.add_argument("--workers", type=int, default=12); ap.add_argument("--max-r1", type=int, default=100); ap.add_argument("--shm-min-gb", type=float, default=20.0); ap.add_argument("--tick", type=float, default=0.5); ap.add_argument("--wait2", type=float, default=1800)
    ap.add_argument("--venue", default=None); ap.add_argument("--kitdir", default=R610); ap.add_argument("--work-base", default="/dev/shm/beacon"); ap.add_argument("--bsd", type=int, default=None)
    a = ap.parse_args()
    if a.venue is None:
        try: a.venue = open(f"{R610}/VENUE.txt").read().strip()
        except OSError: a.venue = "raid610"
    if a.bsd is None:
        try: a.bsd = int(open(f"{R610}/BSD.txt").read().strip() or 0)
        except OSError: a.bsd = 0
    if a.bsd == 0: a.bsd = 0
    seeds = []
    for tok in a.seeds.split(","):
        if "-" in tok: lo, hi = tok.split("-"); seeds += list(range(int(lo), int(hi) + 1))
        elif tok: seeds.append(int(tok))
    a.seeds = seeds
    os.environ["OMP_NUM_THREADS"] = "1"; os.environ["OPENBLAS_NUM_THREADS"] = "1"
    print(f"ladder c{a.card}: {len(a.seeds)} windows, {a.workers} workers, venue {a.venue}, bsd {a.bsd}, kit {a.kitdir}", flush=True)
    Ladder(a).run()

if __name__ == "__main__": main()
