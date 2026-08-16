#!/usr/bin/env python3
"""P5 ZERO-TOLERANCE GATE: livefire_g driven by the CPU/mpz backend must
reproduce livefire_m1a trial outcomes EXACTLY, uninterrupted AND through a
SIGKILL mid-hunt + resume. Container scale: D=1000, z=1e7, seed 77, N=3."""
import csv, json, os, shutil, signal, subprocess, sys, time
WD = os.path.dirname(os.path.abspath(__file__)); os.chdir(WD)
ROOT = os.path.dirname(WD)
M1A = os.path.join(ROOT, "p2", "livefire_m1a.py")
BLD = os.path.join(ROOT, "p2", "build_residue_table.py")
DRV = os.path.join(ROOT, "p3", "g1_fermat_cpu")
LFG = os.path.join(WD, "livefire_g.py")
TAB = os.path.join(WD, "tab")
D, Z, SEED, N = 1000, 1e7, 77, 3
COLS = ["D","zdesign","z","k","gap","merit","jleft","jright","tests","survivors"]
FAILS = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok: FAILS.append(name)
def rows(p): return [tuple(r[c] for c in COLS) for r in csv.DictReader(open(p))]
def fresh(d):
    if os.path.isdir(d): shutil.rmtree(d)
    os.makedirs(d)
def run_in(d, cmd, timeout=1800):
    r = subprocess.run(cmd, shell=True, cwd=d, capture_output=True, text=True,
                       timeout=timeout)
    if r.returncode != 0:
        print(f"CMD FAIL in {d}: {cmd}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
        sys.exit(1)
    return r.stdout + r.stderr

t0 = time.time()
print("== table ==")
if not os.path.isdir("tab"):
    run_in(".", f"python3 {BLD} --digits {D} --z {Z:.0f} --out tab --procs 2")
print("== reference: livefire_m1a ==")
if not os.path.exists("A/livefire_log.csv"):
    fresh("A")
    run_in("A", f"python3 {M1A} --digits {D} --z {Z:.0f} "
                f"--trials {N} --seed {SEED}")
ra = rows("A/livefire_log.csv"); print(f"  {len(ra)} trials")

GCMD = (f"python3 {LFG} --digits {D} --z {Z:.0f} --trials {N} "
        f"--seed {SEED} --table {TAB} --driver {DRV} --round 16")
print("== G-1: livefire_g(cpu driver) uninterrupted ==")
fresh("B"); run_in("B", GCMD)
rb = rows("B/livefire_log.csv")
check("G-1 livefire_g == m1a exact", ra == rb, f"{len(rb)} rows x {len(COLS)} cols")

print("== G-2: SIGKILL mid-hunt + resume ==")
fresh("C")
proc = subprocess.Popen(GCMD, shell=True, cwd="C", stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, preexec_fn=os.setsid)
killed = False; deadline = time.time() + 900
while time.time() < deadline:
    try:
        ck = json.load(open("C/ckpt.json"))
        prog = sum(s["L"]["cur"] + s["R"]["cur"] for s in ck.get("active", []))
        if ck.get("active") and prog >= 30:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL); killed = True
            print(f"  SIGKILL: logged={ck['n_logged']} active={len(ck['active'])} "
                  f"frontier-progress={prog}")
            break
    except Exception: pass
    time.sleep(0.05)
proc.wait()
check("G-2 kill landed mid-hunt", killed)
out = run_in("C", GCMD)
res = next((l for l in out.splitlines() if l.startswith("resume:")), "")
print(f"  {res}")
check("G-2 resume banner", res.startswith("resume:"))
check("G-2 interrupted+resumed == uninterrupted", rb == rows("C/livefire_log.csv"))

print()
if FAILS:
    print(f"P5 GATE: {len(FAILS)} FAILURE(S): {FAILS}  [{time.time()-t0:.0f}s]")
    sys.exit(1)
print(f"P5 GATE: ALL CHECKS PASS (zero tolerance held)  [{time.time()-t0:.0f}s]")
