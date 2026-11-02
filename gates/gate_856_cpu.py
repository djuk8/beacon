#!/usr/bin/env python3
"""gate_856_cpu.py -- v8.56 single-class gates. CPU part runs anywhere (sandbox, or a box beside production); --gpu adds the GPU part.

  python3 gate_856_cpu.py --old OLDKIT --new NEWKIT --work DIR [--cache DIR] [--threads N] [--gpu --card C [--old-gpu-so F --new-gpu-so F]]

OLDKIT = a v8.55 kit dir (o1_kit), NEWKIT = the v8.56 kit dir. Every gbsd run uses a test seed, its own --state and --out under DIR:
production state, queues and seeds are never touched. Referee = ref856.c (direct per-(k,p) residues; shares only the venue tables).
  G0a  S=2 constants: v8.55 bs_api == v8.56 bs_api (old names and the _s names at S=2): js2 consts, records, masks, wheel, predictor
  G0b  S=2 rings: v8.55 gbsd == v8.56 gbsd (CPU twin), 2 blocks at 1e8, select 12, predictor on: bin + manifest bytes
  G0c  twin fidelity: v8.56 gbsd + twin (S=2, ranking by ring-1 count) == certified CPU `scanhunt make --select 12` at 1e8
  G1   S=2310 all rows (select 1): every window of 2 blocks == referee at DEEP1; ks = the class progression from the first k >= 1e15
  G2   S=2310 production geometry (kblock 8311 x select 12, predictor on), 2 blocks at DEEP1: every kept window == referee; the
       pool bitmaps (tapped) == referee on sampled rows; the selection recomputed from referee predictor sums + pool counts == ring
  G2r  resume: block 2 after a stop/restart == block 2 of the continuous run (bin + manifest bytes); state tagged with the class
  G2b  class 1993 at 1e8, 1 block: sampled kept windows == referee at 1e8
  G3   predictor: bs_predict_s(S=2310) == direct sums over 99,732 rows (bitwise), 3 origins
  G4   ladder path: rung-2 make on a single-class carry (cmd_make in-process, Q=1e5) == referee, per-k kernel, timed; mixed sets
       unchanged (old == new fastmake); deepening a single-class set refuses loudly
  G5   onstart: bash -n; knobs absent -> launch lines unchanged; knobs present -> the v8.56 arguments
  --gpu: GB2 S=2 GPU rings v8.55 == v8.56 | GB3 S=2310 GPU rings == CPU twin | GB4 GPU kept windows == referee at 1e8"""
import argparse, ctypes as C, filecmp, glob, hashlib, json, math, os, shutil, subprocess, sys, time
import numpy as np

CR = "1568,4374,7244,10198,13500,17734,22818,31576"; HI = 1568; Sh = HI // 2; I = 2 * Sh + 1; BW = (I + 63) // 64
FILES = ["gbsd.py", "bs_api.c", "bsieve.c", "fastmake.py", "fastmake_c.c", "fastmake_numpy.py", "scanhunt_v0.py", "deep_primes.py", "resonance_map.py", "gbs.cu"]
ap = argparse.ArgumentParser()
ap.add_argument("--old", required=True); ap.add_argument("--new", required=True); ap.add_argument("--work", required=True)
ap.add_argument("--cache", default=""); ap.add_argument("--threads", type=int, default=2); ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--deep1", type=int, default=10_000_000); ap.add_argument("--deep2", type=int, default=100_000_000); ap.add_argument("--sample", type=int, default=200)
ap.add_argument("--only", default=""); ap.add_argument("--gpu", action="store_true"); ap.add_argument("--card", type=int, default=7)
ap.add_argument("--old-gpu-so", default=""); ap.add_argument("--new-gpu-so", default=""); ap.add_argument("--ref-all", action="store_true")
a = ap.parse_args()
W = os.path.abspath(a.work); os.makedirs(W, exist_ok=True); PY = sys.executable; TH = a.threads
CACHE = os.path.abspath(a.cache) if a.cache else f"{W}/sc_cache"; os.makedirs(CACHE, exist_ok=True)
LOG = open(f"{W}/gate_856.log", "a"); RES = {}
def say(s): print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
def sh(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"build failed: {cmd}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
class Fail(Exception): pass
def need(cond, msg):
    if not cond: raise Fail(msg)

# ---------------- build: two code dirs ----------------
def build(src, dst, new):
    os.makedirs(dst, exist_ok=True)
    for f in FILES + (["gbs_cpu.c", "ref856.c"] if new else []) + (["deepsieve.py"] if os.path.exists(f"{src}/deepsieve.py") else []):
        shutil.copy2(f"{src}/{f}", f"{dst}/{f}")
    sh("gcc -O3 -march=native -shared -fPIC -o bs_api.so bs_api.c -lpthread", cwd=dst)
    sh("gcc -O3 -shared -fPIC -o fastmake_c.so fastmake_c.c", cwd=dst)
    if new:
        sh("gcc -O3 -march=native -shared -fPIC -o gbs_cpu.so gbs_cpu.c", cwd=dst)
        sh("gcc -O3 -march=native -fopenmp -shared -fPIC -o ref856.so ref856.c", cwd=dst)
OLD, NEW = f"{W}/code_old", f"{W}/code_new"
build(os.path.abspath(a.old), OLD, False); build(os.path.abspath(a.new), NEW, True); shutil.copy2(f"{NEW}/gbs_cpu.so", f"{OLD}/gbs_cpu.so")   # the twin stands in for the GPU in both
say(f"=== gate_856 {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | old {a.old} | new {a.new} | bs_api old {sha(OLD + '/bs_api.c')} new {sha(NEW + '/bs_api.c')} | gbsd old {sha(OLD + '/gbsd.py')} new {sha(NEW + '/gbsd.py')}")
sys.path.insert(0, NEW); import scanhunt_v0 as sc
TAP = f"{W}/tap_gbsd.py"
open(TAP, "w").write('''import os, sys
code = sys.argv[1]; sys.path.insert(0, code); sys.argv = [os.path.join(code, "gbsd.py")] + sys.argv[2:]
_unlink = os.unlink
def _keep(p, *x, **y):                                  # gate tap: keep the pool bitmaps the workers would delete
    if "/gbsd_" in str(p) and str(p).endswith(".bits"): return None
    return _unlink(p, *x, **y)
os.unlink = _keep
import gbsd; gbsd.main()
''')

def venue(seed, dq):
    ns = argparse.Namespace(zd=1439, swap=[2, 3, 5, 7, 11], kdig=13, merit=45.0, Q=1_000_000, deep_q=dq, deep_from_ring=1, rings=CR, bits=2048, seed=seed, kblock=20000, select=12, fast=2)
    cfg, P = sc.cfg_of(ns); return cfg, P, sc.ScanSieve(cfg, P, cache=CACHE)
def run_gbsd(name, code, seed, args, tap=False, gpu_so=None, card=9):
    rd = f"{W}/run/{name}"; shutil.rmtree(rd, ignore_errors=True); os.makedirs(rd); os.symlink(CACHE, f"{rd}/.sc_cache")
    shutil.rmtree(f"/dev/shm/gbsd_{seed}", ignore_errors=True)
    cmd = ([PY, TAP, code] if tap else [PY, f"{code}/gbsd.py"]) + ["--seed", str(seed), "--card", str(card), "--out", f"{rd}/ready", "--state", f"{rd}/state.json",
          "--api", f"{code}/bs_api.so", "--gpu-api", gpu_so or f"{code}/gbs_cpu.so", "--workers", str(a.workers), "--pred-threads", str(TH)] + args
    t = time.time(); r = subprocess.run(cmd, cwd=rd, capture_output=True, text=True); open(f"{rd}.log", "w").write(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    need(r.returncode == 0, f"{name}: gbsd exit {r.returncode}: {(r.stdout + r.stderr)[-600:]}")
    return rd, time.time() - t
def rerun(rd, code, seed, args, gpu_so=None, card=9):                      # same dir/state: resume
    cmd = [PY, f"{code}/gbsd.py", "--seed", str(seed), "--card", str(card), "--out", f"{rd}/ready", "--state", f"{rd}/state.json", "--api", f"{code}/bs_api.so",
           "--gpu-api", gpu_so or f"{code}/gbs_cpu.so", "--workers", str(a.workers), "--pred-threads", str(TH)] + args
    r = subprocess.run(cmd, cwd=rd, capture_output=True, text=True); open(f"{rd}.resume.log", "w").write(r.stdout + r.stderr)
    need(r.returncode == 0, f"resume: gbsd exit {r.returncode}: {(r.stdout + r.stderr)[-600:]}"); return r.stdout
def rings(rd): return sorted(os.path.basename(f) for f in glob.glob(f"{rd}/ready/sc_r01_*"))
def same_rings(r1, r2, names=None):
    n1, n2 = rings(r1), rings(r2)
    if names: n1 = [n for n in n1 if any(n.startswith(x) for x in names)]; n2 = [n for n in n2 if any(n.startswith(x) for x in names)]
    need(n1 == n2 and n1, f"ring sets differ: {n1[:4]} vs {n2[:4]}")
    bad = [n for n in n1 if not filecmp.cmp(f"{r1}/ready/{n}", f"{r2}/ready/{n}", shallow=False)]
    need(not bad, f"{len(bad)} ring files differ: {bad[:3]}"); return n1
def man(rd, bid): return json.load(open(f"{rd}/ready/sc_r01_{bid:04d}.manifest.json"))

REF = C.CDLL(f"{NEW}/ref856.so")
REF.ref_bits.argtypes = [C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_int]
REF.ref_pred.argtypes = [C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_int64, C.c_void_p, C.c_int]
def i64(x): return np.ascontiguousarray(np.asarray(x, dtype=np.int64))
def ref_bits(ks, sv, lo=0, hi=HI, deep=True, prs=None, pem=None):
    ks = i64(ks); prs = i64(sv.prs if prs is None else prs); pem = i64(sv.PEm if pem is None else pem)
    qd = i64(sv.qd) if deep and sv.dq else np.zeros(1, np.int64); pe = i64(sv.PEd64) if deep and sv.dq else np.zeros(1, np.int64); nq = len(sv.qd) if deep and sv.dq else 0
    bw = ((2 * (hi // 2) + 1) + 63) // 64; out = np.zeros((len(ks), bw), dtype=np.uint64)
    REF.ref_bits(ks.ctypes.data, len(ks), prs.ctypes.data, pem.ctypes.data, len(prs), qd.ctypes.data, pe.ctypes.data, nq, lo, hi, out.ctypes.data, TH); return out
def bits_js(row, hi=HI):
    sh_ = hi // 2; b = np.unpackbits(row.view(np.uint8), bitorder="little")[:2 * sh_ + 1]; return (2 * (np.nonzero(b)[0] - sh_)).astype(np.int64)
def popc(bits): return np.unpackbits(bits.view(np.uint8), axis=1).sum(axis=1).astype(np.int64)
PRED = None
def pred_tables():
    global PRED
    if PRED is None:
        base = sorted(glob.glob("/dev/shm/pred_1439_31576_100000.p.npy"))
        need(base, "predictor tables /dev/shm/pred_1439_31576_100000.* missing (a gbsd run with --pred-pb 100000 builds them)")
        b = base[0][:-len(".p.npy")]; PRED = tuple(np.load(b + x, mmap_mode="r") for x in (".p.npy", ".pe.npy", ".off.npy", ".tab.npy"))
    return PRED
def ref_pred(ks):
    p, pe, of, tb = pred_tables(); ks = i64(ks); out = np.zeros(len(ks))
    REF.ref_pred(ks.ctypes.data, len(ks), p.ctypes.data, pe.ctypes.data, of.ctypes.data, tb.ctypes.data, len(p), out.ctypes.data, TH); return out
def check_ring_vs_ref(rd, bid, sv, sample=0, rng=None):
    m = man(rd, bid); ks = m["ks"]; idx = range(len(ks)) if not sample else sorted(rng.choice(len(ks), min(sample, len(ks)), replace=False).tolist())
    kk = [ks[i] for i in idx]; rb = ref_bits(kk, sv); bad = 0
    for x, i in enumerate(idx):
        if sorted(m["js"][i]) != bits_js(rb[x]).tolist() or m["sizes"][i] != len(m["js"][i]): bad += 1
    need(bad == 0, f"ring {bid}: {bad}/{len(kk)} windows differ from the referee"); return len(kk), sum(len(m["js"][i]) for i in idx)
def gate(name, fn):
    if a.only and name not in a.only.split(","): return
    t = time.time()
    try: msg = fn(); RES[name] = "PASS"; say(f"{name}: PASS  {msg}  [{time.time()-t:.0f}s]")
    except Fail as e: RES[name] = "FAIL"; say(f"{name}: FAIL  {e}  [{time.time()-t:.0f}s]")

K317 = 10 ** 15 + (317 - 10 ** 15) % 2310; K1993 = 10 ** 15 + (1993 - 10 ** 15) % 2310
SC = ["--step", "2310", "--kbase", str(10 ** 15)]

# ---------------- G0a: S=2 constants ----------------
def g0a():
    cfg, P, sv = venue(7302, a.deep2); Lo, Ln = C.CDLL(f"{OLD}/bs_api.so"), C.CDLL(f"{NEW}/bs_api.so")
    for L in (Lo, Ln):
        L.bs_js2_consts.argtypes = [C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_void_p, C.c_void_p]
        L.bs_records_flat.restype = C.c_int64; L.bs_records_flat.argtypes = [C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_int64, C.c_void_p]
        L.bs_wheel.argtypes = [C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p]
        L.bs_smask_create.restype = C.c_void_p; L.bs_smask_create.argtypes = [C.c_void_p, C.c_void_p, C.c_int, C.c_int64, C.c_int64]
        L.bs_smask_words.restype = C.c_int64; L.bs_smask_words.argtypes = [C.c_void_p]; L.bs_smask_export.argtypes = [C.c_void_p] * 4
        L.bs_predict.argtypes = [C.c_void_p, C.c_int64, C.c_int64, C.c_int, C.c_void_p]
        L.bs_pred_attach.restype = C.c_void_p; L.bs_pred_attach.argtypes = [C.c_void_p] * 4 + [C.c_int64] * 2
    Ln.bs_js2_consts_s.restype = C.c_int64; Ln.bs_js2_consts_s.argtypes = [C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_void_p]
    Ln.bs_records_flat_s.restype = C.c_int64; Ln.bs_records_flat_s.argtypes = [C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_int64, C.c_int64, C.c_void_p]
    Ln.bs_predict_s.argtypes = [C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_int, C.c_void_p]
    prs, PEm = i64(sv.prs), i64(sv.PEm); cut = int(np.searchsorted(prs, 251, side="right")); sp, se, mp, me = i64(prs[:cut]), i64(PEm[:cut]), i64(prs[cut:]), i64(PEm[cut:])
    qd, PEd = i64(sv.qd), i64(sv.PEd64); T = 240000; n = 0
    run_gbsd("g0a_tables", NEW, 7390, ["--deepq", str(a.deep1), "--select", "12", "--blocks", "1"]) if not glob.glob("/dev/shm/pred_1439_31576_100000.tab.npy") else None
    pp, pe_, of, tb = pred_tables(); Mo = Lo.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), 31576)
    Mn = Ln.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), 31576)
    for k0 in (sc.kstart(cfg), sc.kstart(cfg) + 2 * 240000 * 7, 441041839285477, 1000000000000317):
        tc = [np.empty(len(mp), np.int64) for _ in range(3)]; st = [np.empty(len(mp), np.int64) for _ in range(3)]
        Lo.bs_js2_consts(k0, mp.ctypes.data, me.ctypes.data, len(mp), HI, tc[0].ctypes.data, st[0].ctypes.data)
        Ln.bs_js2_consts(k0, mp.ctypes.data, me.ctypes.data, len(mp), HI, tc[1].ctypes.data, st[1].ctypes.data)
        nc = Ln.bs_js2_consts_s(k0, mp.ctypes.data, me.ctypes.data, len(mp), HI, 2, tc[2].ctypes.data, st[2].ctypes.data)
        need(nc == 0 and all(np.array_equal(tc[0], x) for x in tc[1:]) and all(np.array_equal(st[0], x) for x in st[1:]), f"js2 consts differ at k0 {k0}")
        rec = [np.empty((len(qd), 3), np.uint64) for _ in range(3)]
        nr = [Lo.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0, T, HI, rec[0].ctypes.data), Ln.bs_records_flat(qd.ctypes.data, PEd.ctypes.data, len(qd), k0, T, HI, rec[1].ctypes.data),
              Ln.bs_records_flat_s(qd.ctypes.data, PEd.ctypes.data, len(qd), k0, T, HI, 2, rec[2].ctypes.data)]
        need(nr[0] == nr[1] == nr[2] and all(np.array_equal(rec[0][:nr[0]], x[:nr[0]]) for x in rec[1:]), f"records differ at k0 {k0}")
        ex = []
        for L in (Lo, Ln):
            M = L.bs_smask_create(sp.ctypes.data, se.ctypes.data, cut, k0, HI); w = L.bs_smask_words(M); c_ = np.empty(cut, np.int64); o_ = np.empty(cut, np.int64); t_ = np.empty(w, np.uint64)
            L.bs_smask_export(M, c_.ctypes.data, o_.ctypes.data, t_.ctypes.data); wh = np.empty(BW, np.uint64); L.bs_wheel(mp.ctypes.data, me.ctypes.data, len(mp), 0, HI, wh.ctypes.data); ex.append((c_, o_, t_, wh))
        need(all(np.array_equal(x, y) for x, y in zip(*ex)), f"masks/wheel differ at k0 {k0}")
        pr = [np.zeros(T) for _ in range(3)]
        Lo.bs_predict(Mo, k0, T, TH, pr[0].ctypes.data); Ln.bs_predict(Mn, k0, T, TH, pr[1].ctypes.data); Ln.bs_predict_s(Mn, k0, T, 2, TH, pr[2].ctypes.data)
        need(all(np.array_equal(pr[0], x) for x in pr[1:]), f"predictor differs at k0 {k0}"); n += 1
    return f"{n} origins: js2 consts ({len(mp):,} medium), records ({nr[0]:,} at {a.deep2:.0e}), masks, wheel, predictor ({T:,} rows): v8.55 == v8.56 == _s(S=2)"

# ---------------- G0b / G0c: S=2 rings ----------------
def g0b():
    args = ["--deepq", str(a.deep2), "--select", "12", "--blocks", "2"]
    ro, to = run_gbsd("g0b_old", OLD, 7302, args); rn, tn = run_gbsd("g0b_new", NEW, 7302, args); names = same_rings(ro, rn)
    return f"{len(names)} files byte-identical (2 rings x bin+manifest, seed 7302, 1e8, select 12, predictor on) | wall old {to:.0f}s new {tn:.0f}s"
def g0c():
    rn, _ = run_gbsd("g0c_gbsd", NEW, 7302, ["--deepq", str(a.deep2), "--select", "12", "--pred-pb", "0", "--blocks", "1"])
    md = f"{W}/run/g0c_make"; shutil.rmtree(md, ignore_errors=True); os.makedirs(md); os.symlink(CACHE, f"{md}/.sc_cache")
    r = subprocess.run([PY, f"{NEW}/scanhunt_v0.py", "make", "--round", "1", "--zd", "1439", "--swap", "2", "3", "5", "7", "11", "--kdig", "13", "--merit", "45.0", "--Q", "1000000",
                        "--deep-q", str(a.deep2), "--deep-from-ring", "1", "--rings", CR, "--bits", "2048", "--seed", "7302", "--kblock", "20000", "--select", "12"], cwd=md, capture_output=True, text=True)
    open(f"{md}.log", "w").write(r.stdout + r.stderr); need(r.returncode == 0, f"make failed: {r.stderr[-400:]}")
    g, m = man(rn, 1), json.load(open(f"{md}/sc_r01_0001.manifest.json"))
    need(g["ks"] == m["ks"] and g["js"] == m["js"] and g["sizes"] == m["sizes"], "twin ring != certified make (ks/js/sizes)")
    need(filecmp.cmp(f"{rn}/ready/sc_r01_0001.bin", f"{md}/sc_r01_0001.bin", shallow=False), "twin ring bin != certified make bin")
    return f"twin (S=2, ring-1 ranking) == scanhunt make --select 12 at 1e8: {len(g['ks']):,} ks, {sum(g['sizes']):,} candidates, bin identical"

# ---------------- G1: S=2310 all rows ----------------
def g1():
    kb = 4000; rd, t = run_gbsd("g1", NEW, 7311, SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "1", "--kblock", str(kb), "--blocks", "2", "--pred-pb", "0"])
    cfg, P, sv = venue(7311, a.deep1); tot = 0
    for b in (1, 2):
        m = man(rd, b); ks = m["ks"]; exp = [K317 + 2310 * ((b - 1) * kb + i) for i in range(kb)]
        need(ks == exp, f"block {b}: ks are not the class progression from {K317}"); need(m["origin"].get("step") == 2310 and m["origin"].get("kclass") == 317, "origin lacks step/kclass")
        n, c = check_ring_vs_ref(rd, b, sv); tot += n
    return f"{tot:,} windows (2 blocks x {kb}, every row) == referee at {a.deep1:.0e}; ks = {K317} + 2310 t exactly | gbsd {t:.0f}s"

# ---------------- G2 / G2r / G2b: production geometry ----------------
G2DIR = {}
def g2():
    seed = 7312; rd, t = run_gbsd("g2", NEW, seed, SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "12", "--blocks", "2"], tap=True); G2DIR["rd"] = rd
    cfg, P, sv = venue(seed, a.deep1); T = 8311 * 12; rng = np.random.default_rng(856); msgs = []
    st = json.load(open(f"{rd}/state.json")); need(st.get("step") == 2310 and st.get("kclass") == 317 and st.get("k0") == K317 and st["next_block"] == 2, f"state not tagged: {st}")
    for b in (1, 2):
        m = man(rd, b); blk = b - 1; ks_all = K317 + 2310 * (blk * T + np.arange(T, dtype=np.int64))
        need(len(m["ks"]) == T // 12, f"ring {b}: {len(m['ks'])} windows, want {T // 12}")
        n, c = check_ring_vs_ref(rd, b, sv)
        bits = np.fromfile(f"/dev/shm/gbsd_{seed}/blk_{blk}.bits", dtype=np.uint64).reshape(T, BW)
        rows = np.sort(rng.choice(T, a.sample, replace=False)); rb = ref_bits(ks_all[rows], sv)
        need(np.array_equal(bits[rows], rb), f"block {b}: pool bitmaps differ from the referee on sampled rows")
        cnt = popc(bits); cop = np.nonzero(np.gcd(ks_all, 2310) == 1)[0]; need(len(cop) == T, "single-class pool has non-coprime rows")
        pr = ref_pred(ks_all); prc = pr[cop]; s1 = cnt[cop].astype(float); nkeep = len(cop) // 12
        score = (prc - prc.mean()) / (prc.std() + 1e-9) - 0.6 * (s1 - s1.mean()) / (s1.std() + 1e-9)
        order = np.argsort(-score, kind="stable"); kept = np.sort(cop[order[:nkeep]]); zsel = float(((prc[order[:nkeep]] - prc.mean()) / (prc.std() + 1e-9)).mean())
        need(ks_all[kept].tolist() == m["ks"], f"block {b}: selection recomputed from referee sums != ring ks")
        need(round(zsel, 3) == m["origin"]["pred_z"], f"block {b}: pred_z {m['origin']['pred_z']} != recomputed {round(zsel, 3)}")
        msgs.append(f"ring {b}: {n:,} kept == referee, {a.sample} pool rows == referee, selection == recomputed (pred_z {zsel:+.3f})")
    shutil.rmtree(f"/dev/shm/gbsd_{seed}", ignore_errors=True)
    return " | ".join(msgs) + f" | gbsd {t:.0f}s"
def g2r():
    seed = 7313; args = SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "12"]
    rc, _ = run_gbsd("g2r_cont", NEW, seed, args + ["--blocks", "2"])
    rs, _ = run_gbsd("g2r_stop", NEW, seed, args + ["--blocks", "1"]); out = rerun(rs, NEW, seed, args + ["--blocks", "2"])
    need("resuming seed 7313 at block 1" in out, f"no resume line: {out[:300]}")
    same_rings(rc, rs, names=["sc_r01_0002"])
    bad = subprocess.run([PY, f"{NEW}/gbsd.py", "--seed", str(seed), "--card", "9", "--out", f"{rs}/ready", "--state", f"{rs}/state.json", "--api", f"{NEW}/bs_api.so",
                          "--gpu-api", f"{NEW}/gbs_cpu.so", "--deepq", str(a.deep1), "--blocks", "3"], cwd=rs, capture_output=True, text=True)   # an S=2 daemon must refuse this state
    need(bad.returncode != 0 and "not this daemon" in (bad.stdout + bad.stderr), "an S=2 daemon resumed a single-class state")
    return "block 2 after stop/restart == continuous run (bin + manifest bytes); an S=2 daemon refuses the single-class state"
def g2b():
    seed = 7314; rd, t = run_gbsd("g2b", NEW, seed, SC + ["--kclass", "1993", "--deepq", str(a.deep2), "--select", "12", "--blocks", "1"])
    cfg, P, sv = venue(seed, a.deep2); m = man(rd, 1)
    need(all(k % 2310 == 1993 and k >= 10 ** 15 for k in m["ks"]) and m["ks"][0] >= K1993, "class 1993 ks wrong")
    n, c = check_ring_vs_ref(rd, 1, sv, sample=a.sample, rng=np.random.default_rng(1993))
    return f"class 1993: {n} sampled kept windows ({c:,} survivors) == referee at {a.deep2:.0e} | gbsd {t:.0f}s"

# ---------------- G3: predictor ----------------
def g3():
    Ln = C.CDLL(f"{NEW}/bs_api.so"); Ln.bs_pred_attach.restype = C.c_void_p; Ln.bs_pred_attach.argtypes = [C.c_void_p] * 4 + [C.c_int64] * 2
    Ln.bs_predict_s.argtypes = [C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_int, C.c_void_p]
    pp, pe_, of, tb = pred_tables(); M = Ln.bs_pred_attach(pp.ctypes.data, pe_.ctypes.data, of.ctypes.data, tb.ctypes.data, len(pp), 31576); T = 99732
    for k0 in (K317, K1993 + 2310 * T * 37, 441041839285477 - (441041839285477 - 317) % 2310):
        a_ = np.zeros(T); Ln.bs_predict_s(M, k0, T, 2310, TH, a_.ctypes.data); b_ = ref_pred(k0 + 2310 * np.arange(T, dtype=np.int64))
        need(np.array_equal(a_, b_), f"bs_predict_s differs from direct sums at k0 {k0} ({int(np.sum(a_ != b_))} rows)")
    return f"bs_predict_s(S=2310) == direct per-k sums, {T:,} rows x 3 origins ({len(pp):,} primes)"

# ---------------- G4: ladder path ----------------
def g4():
    import importlib.util
    def load(name, path):
        sp_ = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(m); return m
    fo, fn = load("fm_old856", f"{OLD}/fastmake.py"), load("fm_new856", f"{NEW}/fastmake.py"); need(fo.IMPL == "c" and fn.IMPL == "c", "fastmake C kernel not loaded")
    ns = argparse.Namespace(zd=1439, swap=[2, 3, 5, 7, 11], kdig=13, merit=45.0, Q=100000, deep_q=a.deep1, deep_from_ring=1, rings=CR, bits=2048, seed=101, kblock=20000, select=12, fast=2)
    cfg, P = sc.cfg_of(ns); sv5 = sc.ScanSieve(cfg, P, cache=CACHE)
    rd = G2DIR.get("rd") or run_gbsd("g4_src", NEW, 7315, SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "12", "--blocks", "1"])[0]
    ks1 = man(rd, 1)["ks"]; carry = sorted(np.random.default_rng(4).choice(ks1, 4600, replace=False).tolist())
    md = f"{W}/run/g4_make"; shutil.rmtree(md, ignore_errors=True); os.makedirs(md); os.symlink(CACHE, f"{md}/.sc_cache")
    json.dump(dict(ks=carry, bid=2000000001, round=1), open(f"{md}/sc_carry_r01.json", "w"))
    code = ("import sys, argparse, time; sys.path.insert(0, %r); import scanhunt_v0 as sc; t = time.time(); "
            "sc.cmd_make(argparse.Namespace(zd=1439, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=100000, deep_q=%d, deep_from_ring=1, deep_rings=1, select=12, rings=%r, bits=2048, seed=101, kblock=20000, fast=2, max_prp=60000, bin=None, round=2)); "
            "print('MAKE2 %%.2f s' %% (time.time() - t))") % (NEW, a.deep1, CR)
    r = subprocess.run([PY, "-c", code], cwd=md, capture_output=True, text=True); open(f"{md}.log", "w").write(r.stdout + r.stderr)
    need(r.returncode == 0, f"rung-2 make failed: {r.stderr[-500:]}"); tm = float(r.stdout.split("MAKE2 ")[1].split()[0])
    m2 = json.load(open(f"{md}/sc_r02_2000000001.manifest.json")); need(m2["ks"] == carry, "rung-2 manifest ks != carry")
    rb = ref_bits(carry, sv5, lo=1568, hi=4374, deep=False); bad = sum(1 for i in range(len(carry)) if sorted(m2["js"][i]) != bits_js(rb[i], 4374).tolist())
    need(bad == 0, f"rung-2 make: {bad}/{len(carry)} windows differ from the referee"); need(tm < 30, f"rung-2 make took {tm:.1f}s (per-k path not taken?)")
    mixed = man(G0B["new"], 1)["ks"][:4600] if G0B.get("new") else None
    if mixed:
        jo = fo.block_js(np.array(mixed), sv5.prs, sv5.PEm, 1568, 4374); jn = fn.block_js(np.array(mixed), sv5.prs, sv5.PEm, 1568, 4374)
        need(len(jo) == len(jn) and all(np.array_equal(x, y) for x, y in zip(jo, jn)), "mixed set: v8.56 fastmake != v8.55")
    try: fn.block_js(np.array(carry), sv5.prs, sv5.PEm, 1568, 4374, qd=sv5.qd, PEd=sv5.PEd64); raised = False
    except RuntimeError as e: raised = "single-class" in str(e)
    need(raised, "deepening a single-class set did not refuse")
    return f"rung-2 make on a 4,600-window single-class carry == referee (Q 1e5), {tm:.1f}s; mixed set old == new{'' if mixed else ' (skipped: run G0b)'}; single-class deepen refuses"
G0B = {}
def g0b_wrap():
    msg = g0b(); G0B["new"] = f"{W}/run/g0b_new"; return msg

# ---------------- G5: onstart ----------------
def g5():
    on_o, on_n = f"{a.old}/onstart_raid_v2.sh", f"{a.new}/onstart_raid_v2.sh"
    need(subprocess.run(["bash", "-n", on_n]).returncode == 0, "bash -n failed")
    o, n = open(on_o).read().splitlines(), open(on_n).read().splitlines()
    import difflib; d = [l for l in difflib.unified_diff(o, n, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    need(len(d) == 6 and sum(1 for l in d if l.startswith("+")) == 4, f"unexpected onstart diff ({len(d)} lines)")   # +2 knob lines, 2 launch lines changed
    knob = "\n".join(l for l in n if l.startswith("X1=") or l.startswith("X2="))
    td = f"{W}/run/g5"; shutil.rmtree(td, ignore_errors=True); os.makedirs(td)
    sim = 'R610=%s; kn() { cat $R610/$1.txt 2>/dev/null | tr -d \' \\n\' | grep -q . && cat $R610/$1.txt | tr -d \' \\n\' || echo "$2"; }\n%s\necho "X1=[$X1] X2=[$X2]"' % (td, knob)
    r0 = subprocess.run(["bash", "-c", sim], capture_output=True, text=True).stdout.strip(); need(r0 == "X1=[] X2=[]", f"knobs absent -> {r0}")
    open(f"{td}/SIEVESTEP2.txt", "w").write("2310\n"); r1 = subprocess.run(["bash", "-c", sim], capture_output=True, text=True).stdout.strip()
    need(r1 == "X1=[] X2=[--step 2310 --kclass 1993 --kbase 1000000000000000 --bid-start 2000000001]", f"knobs present -> {r1}")
    for l in n:
        if "SIEVE CARD c$SIEVECARD seed" in l: need("gbs.so $X1 >>" in l, "daemon-1 launch line lacks $X1")
        if "SIEVE CARD c$SIEVECARD2 seed" in l: need("gbs.so $X2 >>" in l, "daemon-2 launch line lacks $X2")
    return "bash -n ok; diff = knob lines + $X1/$X2 + echo tags only; absent -> empty; SIEVESTEP2=2310 -> --step 2310 --kclass 1993 --kbase 1e15 --bid-start 2000000001"

# ---------------- GPU part ----------------
def gb2():
    args = ["--deepq", str(a.deep2), "--select", "12", "--blocks", "2"]
    ro, to = run_gbsd("gb2_old", OLD, 7322, args, gpu_so=a.old_gpu_so, card=a.card); rn, tn = run_gbsd("gb2_new", NEW, 7322, args, gpu_so=a.new_gpu_so, card=a.card)
    names = same_rings(ro, rn); return f"GPU v8.55 == GPU v8.56 at S=2: {len(names)} files | {to:.0f}s / {tn:.0f}s"
GB3 = {}
def gb3():
    args = SC + ["--kclass", "1993", "--deepq", str(a.deep2), "--select", "12", "--blocks", "2"]
    rg, tg = run_gbsd("gb3_gpu", NEW, 7323, args, gpu_so=a.new_gpu_so, card=a.card); rc, tc_ = run_gbsd("gb3_twin", NEW, 7323, args)
    names = same_rings(rg, rc); GB3["rd"] = rg; return f"S=2310 GPU rings == CPU twin: {len(names)} files | gpu {tg:.0f}s twin {tc_:.0f}s"
def gb4():
    rd = GB3.get("rd"); need(rd, "run GB3 first"); cfg, P, sv = venue(7323, a.deep2); tot = 0
    for b in (1, 2): n, c = check_ring_vs_ref(rd, b, sv, sample=0 if a.ref_all else a.sample, rng=np.random.default_rng(b)); tot += n
    return f"{tot:,} GPU kept windows == referee at {a.deep2:.0e}"

gate("G0a", g0a); gate("G0b", g0b_wrap); gate("G0c", g0c); gate("G1", g1); gate("G2", g2); gate("G2r", g2r); gate("G2b", g2b); gate("G3", g3); gate("G4", g4); gate("G5", g5)
if a.gpu:
    need_gpu = a.old_gpu_so and a.new_gpu_so
    if not need_gpu: say("GPU part needs --old-gpu-so and --new-gpu-so"); RES["GPU"] = "FAIL"
    else: gate("GB2", gb2); gate("GB3", gb3); gate("GB4", gb4)
ok = bool(RES) and all(v == "PASS" for v in RES.values())
hashes = {f: sha(f"{NEW}/{f}") for f in ("gbsd.py", "bs_api.c", "gbs.cu", "fastmake.py", "gbs_cpu.c", "ref856.c")}
json.dump(dict(ts=time.time(), result="PASS" if ok else "FAIL", gates=RES, new=os.path.abspath(a.new), hashes=hashes), open(f"{W}/gate_856_receipt.json", "w"), indent=1)
say(f"GATE 856: {'PASS' if ok else 'FAIL'} ({sum(v == 'PASS' for v in RES.values())}/{len(RES)}) {RES} | receipt {W}/gate_856_receipt.json")
sys.exit(0 if ok else 2)
