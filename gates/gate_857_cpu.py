#!/usr/bin/env python3
"""gate_857_cpu.py -- v8.57 gates (ring 2 deep-sieved on the GPU daemon). CPU part anywhere; --gpu adds the GPU part on a box.

  python3 gate_857_cpu.py --old V856KIT --new V857KIT --work DIR [--cache DIR] [--threads N] [--gpu --card C --old-gpu-so F --new-gpu-so F]

Every gbsd run uses a test seed (78xx), its own --state and --out under DIR; production is never touched. Referee = ref856.c.
  G0   --gpu-rings 1: v8.57 == v8.56, single-class (class 317, 99,732-row pools) and mixed (S=2), 2 blocks at 1e8: bin + manifest bytes
  G1   --gpu-rings 2 vs 1, single-class, 2 blocks at DEEP1: ring files byte-identical, manifests identical but for "r2"; every kept
       window's ring-2 survivors == referee (|j| in (1568, 4374], all primes <= DEEP1)
  G1b  --gpu-rings 2, class 1993 at 1e8: sampled kept windows' ring 2 == referee at 1e8
  G2   --gpu-rings 2, mixed classes (S=2) at DEEP1: ring file identical to --gpu-rings 1; sampled ring 2 == referee
  G3   ladder path: fold (synthetic verdicts) carries r2 for exactly the advancing windows; the rung-2 make packs them: == referee,
       a subset of the 1e5 make on the same carry for every window, and == the 1e5 make minus composites with factors in (1e5, DEEP1]
  G4   onstart knobs: absent -> unchanged; SIEVERINGS2=2 -> --gpu-rings 2 on the second daemon only
  G5   refusals: --gpu-rings 2 with a v8.56 bs_api.so stops; a wide window without gbs_set_format makes gbs_block fail
  --gpu: GB0 --gpu-rings 1 GPU rings v8.56 == v8.57 | GB1 --gpu-rings 2 GPU rings + manifests == CPU twin | GB2 GPU ring 2 == referee"""
import argparse, base64, ctypes as C, filecmp, glob, hashlib, json, os, shutil, subprocess, sys, time
import numpy as np

CR = "1568,4374,7244,10198,13500,17734,22818,31576"; E1, E2 = 1568, 4374
FILES = ["gbsd.py", "bs_api.c", "bsieve.c", "fastmake.py", "fastmake_c.c", "fastmake_numpy.py", "scanhunt_v0.py", "deep_primes.py", "resonance_map.py", "gbs.cu", "gbs_cpu.c", "ref856.c"]
ap = argparse.ArgumentParser()
ap.add_argument("--old", required=True); ap.add_argument("--new", required=True); ap.add_argument("--work", required=True)
ap.add_argument("--cache", default=""); ap.add_argument("--threads", type=int, default=2); ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--deep1", type=int, default=10_000_000); ap.add_argument("--deep2", type=int, default=100_000_000); ap.add_argument("--sample", type=int, default=200)
ap.add_argument("--only", default=""); ap.add_argument("--gpu", action="store_true"); ap.add_argument("--card", type=int, default=7)
ap.add_argument("--old-gpu-so", default=""); ap.add_argument("--new-gpu-so", default=""); ap.add_argument("--ref-all", action="store_true")
a = ap.parse_args()
W = os.path.abspath(a.work); os.makedirs(W, exist_ok=True); PY = sys.executable; TH = a.threads
CACHE = os.path.abspath(a.cache) if a.cache else f"{W}/sc_cache"; os.makedirs(CACHE, exist_ok=True)
LOG = open(f"{W}/gate_857.log", "a"); RES = {}
def say(s): print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]
def sh(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f"build failed: {cmd}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
class Fail(Exception): pass
def need(c, m):
    if not c: raise Fail(m)
def build(src, dst):
    os.makedirs(dst, exist_ok=True)
    for f in FILES + (["deepsieve.py"] if os.path.exists(f"{src}/deepsieve.py") else []): shutil.copy2(f"{src}/{f}", f"{dst}/{f}")
    sh("gcc -O3 -march=native -shared -fPIC -o bs_api.so bs_api.c -lpthread", cwd=dst); sh("gcc -O3 -shared -fPIC -o fastmake_c.so fastmake_c.c", cwd=dst)
    sh("gcc -O3 -march=native -shared -fPIC -o gbs_cpu.so gbs_cpu.c", cwd=dst); sh("gcc -O3 -march=native -fopenmp -shared -fPIC -o ref856.so ref856.c", cwd=dst)
OLD, NEW = f"{W}/code_old", f"{W}/code_new"; build(os.path.abspath(a.old), OLD); build(os.path.abspath(a.new), NEW)
say(f"=== gate_857 {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | old {a.old} | new {a.new} | gbsd old {sha(OLD+'/gbsd.py')} new {sha(NEW+'/gbsd.py')} | scanhunt old {sha(OLD+'/scanhunt_v0.py')} new {sha(NEW+'/scanhunt_v0.py')}")
sys.path.insert(0, NEW); import scanhunt_v0 as sc

def venue(seed, dq, Q=1_000_000):
    ns = argparse.Namespace(zd=1439, swap=[2, 3, 5, 7, 11], kdig=13, merit=45.0, Q=Q, deep_q=dq, deep_from_ring=1, rings=CR, bits=2048, seed=seed, kblock=20000, select=12, fast=2)
    cfg, P = sc.cfg_of(ns); return cfg, P, sc.ScanSieve(cfg, P, cache=CACHE)
def run_gbsd(name, code, seed, args, gpu_so=None, card=9):
    rd = f"{W}/run/{name}"; shutil.rmtree(rd, ignore_errors=True); os.makedirs(rd); os.symlink(CACHE, f"{rd}/.sc_cache"); shutil.rmtree(f"/dev/shm/gbsd_{seed}", ignore_errors=True)
    cmd = [PY, f"{code}/gbsd.py", "--seed", str(seed), "--card", str(card), "--out", f"{rd}/ready", "--state", f"{rd}/state.json", "--api", f"{code}/bs_api.so",
           "--gpu-api", gpu_so or f"{code}/gbs_cpu.so", "--workers", str(a.workers), "--pred-threads", str(TH)] + args
    t = time.time(); r = subprocess.run(cmd, cwd=rd, capture_output=True, text=True); open(f"{rd}.log", "w").write(" ".join(cmd) + "\n" + r.stdout + r.stderr)
    return rd, time.time() - t, r
def ok_gbsd(name, code, seed, args, **kw):
    rd, t, r = run_gbsd(name, code, seed, args, **kw); need(r.returncode == 0, f"{name}: gbsd exit {r.returncode}: {(r.stdout + r.stderr)[-500:]}"); return rd, t
def rings(rd, ext=""): return sorted(os.path.basename(f) for f in glob.glob(f"{rd}/ready/sc_r01_*{ext}"))
def same_files(r1, r2, ext):
    n1, n2 = rings(r1, ext), rings(r2, ext); need(n1 == n2 and n1, f"file sets differ: {n1[:3]} vs {n2[:3]}")
    bad = [n for n in n1 if not filecmp.cmp(f"{r1}/ready/{n}", f"{r2}/ready/{n}", shallow=False)]; need(not bad, f"{len(bad)} files differ: {bad[:3]}"); return n1
def man(rd, bid): return json.load(open(f"{rd}/ready/sc_r01_{bid:04d}.manifest.json"))
def r2_lists(m):
    R = m["r2"]; allj = np.frombuffer(base64.b64decode(R["b64"]), dtype="<i2").astype(np.int64); off = np.concatenate([[0], np.cumsum(R["cnt"])]).astype(np.int64)
    need(off[-1] == len(allj) and len(R["cnt"]) == len(m["ks"]), "r2 payload inconsistent"); return [allj[off[i]:off[i + 1]] for i in range(len(m["ks"]))]

REF = C.CDLL(f"{NEW}/ref856.so")
REF.ref_bits.argtypes = [C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_int]
def i64(x): return np.ascontiguousarray(np.asarray(x, dtype=np.int64))
def ref_js(ks, sv, lo, hi, deep=True):
    ks = i64(ks); prs = i64(sv.prs); pem = i64(sv.PEm); use = deep and bool(sv.dq)
    qd = i64(sv.qd) if use else np.zeros(1, np.int64); pe = i64(sv.PEd64) if use else np.zeros(1, np.int64)
    sh_ = hi // 2; bw = (2 * sh_ + 1 + 63) // 64; out = np.zeros((len(ks), bw), dtype=np.uint64)
    REF.ref_bits(ks.ctypes.data, len(ks), prs.ctypes.data, pem.ctypes.data, len(prs), qd.ctypes.data, pe.ctypes.data, len(sv.qd) if use else 0, lo, hi, out.ctypes.data, TH)
    res = []
    for x in range(len(ks)):
        b = np.unpackbits(out[x].view(np.uint8), bitorder="little")[:2 * sh_ + 1]; res.append((2 * (np.nonzero(b)[0] - sh_)).astype(np.int64))
    return res
def check_r2(rd, bid, sv, sample=0, rng=None):
    m = man(rd, bid); L2 = r2_lists(m); idx = list(range(len(m["ks"]))) if not sample else sorted(rng.choice(len(m["ks"]), min(sample, len(m["ks"])), replace=False).tolist())
    ref = ref_js([m["ks"][i] for i in idx], sv, E1, E2); bad = sum(1 for x, i in enumerate(idx) if not np.array_equal(np.sort(L2[i]), ref[x]))
    need(m["r2"]["lo"] == E1 and m["r2"]["hi"] == E2, f"r2 bounds {m['r2']['lo']}..{m['r2']['hi']}")
    need(bad == 0, f"ring {bid}: {bad}/{len(idx)} windows' ring 2 differ from the referee"); return len(idx), sum(len(L2[i]) for i in idx)
def same_but_r2(ra, rb, bid):
    A, B = man(ra, bid), man(rb, bid); A.pop("r2", None); B.pop("r2", None); need(A == B, f"ring {bid}: manifests differ beyond r2")
    need(filecmp.cmp(f"{ra}/ready/sc_r01_{bid:04d}.bin", f"{rb}/ready/sc_r01_{bid:04d}.bin", shallow=False), f"ring {bid}: ring file differs with --gpu-rings 2")
def gate(name, fn):
    if a.only and name not in a.only.split(","): return
    t = time.time()
    try: msg = fn(); RES[name] = "PASS"; say(f"{name}: PASS  {msg}  [{time.time()-t:.0f}s]")
    except Fail as e: RES[name] = "FAIL"; say(f"{name}: FAIL  {e}  [{time.time()-t:.0f}s]")
SC = ["--step", "2310", "--kbase", str(10 ** 15)]; ST = {}

def g0():
    for tag, seed, args in (("single", 7811, SC + ["--kclass", "317"]), ("mixed", 7812, [])):
        args = args + ["--deepq", str(a.deep2), "--select", "12", "--blocks", "2"]
        ro, _ = ok_gbsd(f"g0_{tag}_old", OLD, seed, args); rn, _ = ok_gbsd(f"g0_{tag}_new", NEW, seed, args)
        for ext in (".bin", ".manifest.json"): same_files(ro, rn, ext)
    return "v8.57 --gpu-rings 1 == v8.56: single-class (class 317) and mixed, 2 rings each at 1e8 - bins and manifests byte-identical"
def g1():
    args = SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "12", "--blocks", "2"]
    r1, t1 = ok_gbsd("g1_r1", NEW, 7813, args); r2, t2 = ok_gbsd("g1_r2", NEW, 7813, args + ["--gpu-rings", "2"]); ST["g1"] = r2
    cfg, P, sv = venue(7813, a.deep1); n = c = 0
    for b in (1, 2): same_but_r2(r1, r2, b); x, y = check_r2(r2, b, sv); n += x; c += y
    st = [l for l in open(r2 + ".log").read().splitlines() if "GPU rings 1+2" in l]; need(st, "no v8.57 start line")
    return f"ring files identical to --gpu-rings 1; {n:,} kept windows' ring 2 == referee at {a.deep1:.0e} ({c/n:.1f} survivors/window) | gbsd {t1:.0f}s -> {t2:.0f}s"
def g1b():
    rd, _ = ok_gbsd("g1b", NEW, 7814, SC + ["--kclass", "1993", "--deepq", str(a.deep2), "--select", "12", "--blocks", "1", "--gpu-rings", "2"])
    cfg, P, sv = venue(7814, a.deep2); n, c = check_r2(rd, 1, sv, sample=a.sample, rng=np.random.default_rng(57))
    return f"class 1993 at {a.deep2:.0e}: {n} sampled kept windows' ring 2 == referee ({c/n:.1f}/window)"
def g2():
    args = ["--deepq", str(a.deep1), "--select", "12", "--blocks", "1"]
    r1, _ = ok_gbsd("g2_r1", NEW, 7815, args); r2, _ = ok_gbsd("g2_r2", NEW, 7815, args + ["--gpu-rings", "2"])
    same_but_r2(r1, r2, 1); cfg, P, sv = venue(7815, a.deep1); n, c = check_r2(r2, 1, sv, sample=a.sample, rng=np.random.default_rng(58))
    return f"mixed classes: ring file identical; {n} sampled kept windows' ring 2 == referee at {a.deep1:.0e}"
def g3():
    src = ST.get("g1") or ok_gbsd("g3_src", NEW, 7816, SC + ["--kclass", "317", "--deepq", str(a.deep1), "--select", "12", "--blocks", "1", "--gpu-rings", "2"])[0]
    m = man(src, 1); L2 = r2_lists(m); nk = len(m["ks"]); rng = np.random.default_rng(3)
    adv = (rng.random(nk) < 0.22) | (np.asarray(m["sizes"]) == 0)                   # ~22% of windows pass ring 1 (no prime in ring 1); empty rows always pass
    v = bytearray(sum(m["sizes"])); pos = 0
    for i, sz in enumerate(m["sizes"]):
        if not adv[i] and sz: v[pos + int(rng.integers(sz))] = 1
        pos += sz
    hdr = open(f"{src}/ready/sc_r01_0001.bin", "rb").read(16); bits = int.from_bytes(hdr[4:8], "little")
    def ladder_dir(name, with_r2):
        d = f"{W}/run/{name}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); os.symlink(CACHE, f"{d}/.sc_cache")
        mm = dict(m) if with_r2 else {k: x for k, x in m.items() if k != "r2"}
        json.dump(mm, open(f"{d}/sc_r01_0001.manifest.json", "w")); shutil.copy2(f"{src}/ready/sc_r01_0001.bin", f"{d}/sc_r01_0001.bin")
        open(f"{d}/sc_r01_0001.v.bin", "wb").write(sc.struct.pack("<IIQ", sc.MAGIC_V, bits, len(v)) + bytes(v))
        code = ("import sys, argparse, time; sys.path.insert(0, %r); import scanhunt_v0 as sc; A = dict(zd=1439, swap=[2,3,5,7,11], kdig=13, merit=45.0, Q=100000, "
                "deep_q=%d, deep_from_ring=1, deep_rings=1, select=12, rings=%r, bits=2048, seed=101, kblock=20000, fast=2, max_prp=60000); "
                "sc.cmd_fold(argparse.Namespace(**A, bin='sc_r01_0001.bin', round=1)); t = time.time(); sc.cmd_make(argparse.Namespace(**A, bin=None, round=2)); "
                "print('MAKE2 %%.2f s' %% (time.time() - t))") % (NEW, a.deep1, CR)
        r = subprocess.run([PY, "-c", code], cwd=d, capture_output=True, text=True); open(f"{d}.log", "w").write(r.stdout + r.stderr)
        need(r.returncode == 0, f"{name}: fold/make failed: {r.stderr[-600:]}"); return d, float(r.stdout.split("MAKE2 ")[1].split()[0]), r.stdout
    dd, td, outd = ladder_dir("g3_deep", True); ds, ts, _ = ladder_dir("g3_shallow", False)
    carry = json.load(open(f"{dd}/sc_carry_r01.json")); want = [m["ks"][i] for i in range(nk) if adv[i]]
    need(carry["ks"] == want and "r2" in carry, "fold: carried ks / r2 wrong")
    cl = r2_lists(dict(ks=carry["ks"], r2=carry["r2"])); need(all(np.array_equal(cl[x], L2[i]) for x, i in enumerate(np.nonzero(adv)[0])), "fold: carried r2 != the manifest's")
    need("ring from the GPU daemon's sieve" in outd, "make r2 did not take the GPU path")
    D = json.load(open(f"{dd}/sc_r02_0001.manifest.json")); Sm = json.load(open(f"{ds}/sc_r02_0001.manifest.json"))
    need(D["ks"] == Sm["ks"] == want, "r2 manifests: ks differ"); cfg, P, sv = venue(7813, a.deep1)
    ref = ref_js(want, sv, E1, E2); bad_ref = sum(1 for i in range(len(want)) if sorted(D["js"][i]) != ref[i].tolist())
    bad_sub = sum(1 for i in range(len(want)) if not set(D["js"][i]) <= set(Sm["js"][i]))
    need(bad_ref == 0 and bad_sub == 0, f"rung-2 ring: {bad_ref} windows != referee, {bad_sub} not a subset of the 1e5 make")
    cut = sum(Sm["sizes"]) / max(sum(D["sizes"]), 1)
    return (f"fold carried {len(want):,} of {nk:,} windows with their ring 2; rung-2 make (GPU path) == referee, subset of the 1e5 make in every window; "
            f"candidates {sum(Sm['sizes']):,} -> {sum(D['sizes']):,} (x{1/cut:.3f}); make {ts:.2f}s -> {td:.2f}s")
def g4():
    on = f"{a.new}/onstart_raid_v2.sh"; need(subprocess.run(["bash", "-n", on]).returncode == 0, "bash -n failed"); n = open(on).read().splitlines()
    knob = "\n".join(l for l in n if l.startswith("X1=") or l.startswith("X2=") or l.startswith('[ "$(kn SIEVERINGS'))
    td = f"{W}/run/g4"; shutil.rmtree(td, ignore_errors=True); os.makedirs(td)
    sim = 'R610=%s; kn() { cat $R610/$1.txt 2>/dev/null | tr -d \' \\n\' | grep -q . && cat $R610/$1.txt | tr -d \' \\n\' || echo "$2"; }\n%s\necho "X1=[$X1] X2=[$X2]"' % (td, knob)
    r0 = subprocess.run(["bash", "-c", sim], capture_output=True, text=True).stdout.strip(); need(r0 == "X1=[] X2=[]", f"absent -> {r0}")
    for f, v in (("SIEVESTEP2", "2310"), ("SIEVERINGS2", "2")): open(f"{td}/{f}.txt", "w").write(v + "\n")
    r1 = subprocess.run(["bash", "-c", sim], capture_output=True, text=True).stdout.strip()
    need(r1 == "X1=[] X2=[--step 2310 --kclass 1993 --kbase 1000000000000000 --bid-start 2000000001 --gpu-rings 2]", f"present -> {r1}")
    return "knobs absent -> unchanged; SIEVERINGS2=2 adds --gpu-rings 2 to the second daemon only"
def g5():
    rd, t, r = run_gbsd("g5_oldapi", NEW, 7817, SC + ["--kclass", "317", "--deepq", str(a.deep1), "--blocks", "1", "--gpu-rings", "2", "--api", f"{OLD}/bs_api.so"])
    need(r.returncode != 0 and "needs the v8.57 libraries" in (r.stdout + r.stderr), "a v8.56 bs_api.so was accepted with --gpu-rings 2")
    G = C.CDLL(f"{NEW}/gbs_cpu.so"); G.gbs_create.restype = C.c_void_p; G.gbs_block.argtypes = [C.c_void_p, C.c_void_p]; G.gbs_set_format.argtypes = [C.c_void_p, C.c_int]
    z = np.zeros(4, np.int64); w = np.zeros(70, np.uint64)
    G.gbs_create.argtypes = [C.c_int, C.c_int64, C.c_int64, C.c_int64, C.c_void_p, C.c_int64, C.c_int, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.c_int64, C.c_int64, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    g = G.gbs_create(0, 4, E2, 10 ** 15 + 1627, None, 0, 0, z.ctypes.data, z.ctypes.data, z.ctypes.data, w.ctypes.data, z.ctypes.data, 0, 0, z.ctypes.data, z.ctypes.data, z.ctypes.data, w.ctypes.data)
    hb = np.zeros(4 * 70, np.uint64); need(G.gbs_block(g, hb.ctypes.data) != 0, "twin ran a 4,375-column window in the v2 layout")
    g2 = G.gbs_create(0, 4, E2, 10 ** 15 + 1627, None, 0, 0, z.ctypes.data, z.ctypes.data, z.ctypes.data, w.ctypes.data, z.ctypes.data, 0, 0, z.ctypes.data, z.ctypes.data, z.ctypes.data, w.ctypes.data)
    need(G.gbs_set_format(g2, 1) == 0 and G.gbs_block(g2, hb.ctypes.data) == 0, "twin refused the wide layout")
    return "gbsd --gpu-rings 2 refuses a v8.56 bs_api.so; gbs_block refuses a 4,375-column window in the v2 record layout, runs it in the wide one"
def gb0():
    args = SC + ["--kclass", "1993", "--deepq", str(a.deep2), "--select", "12", "--blocks", "2"]
    ro, to = ok_gbsd("gb0_old", OLD, 7821, args, gpu_so=a.old_gpu_so, card=a.card); rn, tn = ok_gbsd("gb0_new", NEW, 7821, args, gpu_so=a.new_gpu_so, card=a.card)
    for ext in (".bin", ".manifest.json"): same_files(ro, rn, ext)
    return f"GPU --gpu-rings 1: v8.56 == v8.57 (2 rings, bins + manifests) | {to:.0f}s / {tn:.0f}s"
def gb1():
    args = SC + ["--kclass", "1993", "--deepq", str(a.deep2), "--select", "12", "--blocks", "2", "--gpu-rings", "2"]
    rg, tg = ok_gbsd("gb1_gpu", NEW, 7822, args, gpu_so=a.new_gpu_so, card=a.card); rc, tc = ok_gbsd("gb1_twin", NEW, 7822, args); ST["gb1"] = rg
    for ext in (".bin", ".manifest.json"): same_files(rg, rc, ext)
    return f"GPU --gpu-rings 2 == CPU twin (2 rings, bins + manifests with r2) | gpu {tg:.0f}s twin {tc:.0f}s"
def gb2():
    rd = ST.get("gb1"); need(rd, "run GB1 first"); cfg, P, sv = venue(7822, a.deep2); n = 0
    for b in (1, 2): x, _ = check_r2(rd, b, sv, sample=0 if a.ref_all else a.sample, rng=np.random.default_rng(b)); n += x
    return f"{n:,} GPU kept windows' ring 2 == referee at {a.deep2:.0e}"

for nm, fn in (("G0", g0), ("G1", g1), ("G1b", g1b), ("G2", g2), ("G3", g3), ("G4", g4), ("G5", g5)): gate(nm, fn)
if a.gpu:
    if not (a.old_gpu_so and a.new_gpu_so): say("GPU part needs --old-gpu-so and --new-gpu-so"); RES["GPU"] = "FAIL"
    else:
        for nm, fn in (("GB0", gb0), ("GB1", gb1), ("GB2", gb2)): gate(nm, fn)
ok = bool(RES) and all(v == "PASS" for v in RES.values())
hashes = {f: sha(f"{NEW}/{f}") for f in ("gbsd.py", "bs_api.c", "gbs.cu", "gbs_cpu.c", "scanhunt_v0.py", "fastmake.py")}
json.dump(dict(ts=time.time(), result="PASS" if ok else "FAIL", gates=RES, new=os.path.abspath(a.new), hashes=hashes), open(f"{W}/gate_857_receipt.json", "w"), indent=1)
say(f"GATE 857: {'PASS' if ok else 'FAIL'} ({sum(v == 'PASS' for v in RES.values())}/{len(RES)}) {RES} | receipt {W}/gate_857_receipt.json")
sys.exit(0 if ok else 2)
