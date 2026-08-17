#!/usr/bin/env python3
"""BEACON P2 ZERO-TOLERANCE GATE (container scale: D=1000, z=1e7, seed 77).

  G-1  m2 (shared table) reproduces livefire_m1a trial outcomes EXACTLY:
       columns (D, zdesign, z, k, gap, merit, jleft, jright, tests, survivors)
       equal row-for-row over N trials.
  G-2  kill -9 mid-trial (SIGKILL, no cleanup) + restart reproduces the
       uninterrupted m2 log EXACTLY, and the resume banner shows RNG-replay +
       survivor-count integrity asserts held.
  G-3  fallback path (no --table) reproduces m1a on a 1-trial run.
Exit nonzero on any failure.
"""
import csv, json, os, shutil, signal, subprocess, sys, time

WD = os.path.dirname(os.path.abspath(__file__))
os.chdir(WD)
D, Z, SEED, N = 1000, 1e7, 77, 3
COLS = ["D", "zdesign", "z", "k", "gap", "merit", "jleft", "jright",
        "tests", "survivors"]
FAILS = []

def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok: FAILS.append(name)

def rows(path):
    return [tuple(r[c] for c in COLS) for r in csv.DictReader(open(path))]

def fresh(d):
    if os.path.isdir(d): shutil.rmtree(d)
    os.makedirs(d)

def run_in(d, cmd, timeout=1200):
    r = subprocess.run(cmd, shell=True, cwd=d, capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"CMD FAIL in {d}: {cmd}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        sys.exit(1)
    return r.stdout + r.stderr

if __name__ == "__main__":
    t0 = time.time()
    print("== table build ==")
    if os.path.isdir("tab"): shutil.rmtree("tab")
    out = run_in(".", f"python3 build_residue_table.py --digits {D} "
                      f"--z {Z:.0f} --out tab --procs 2")
    print("  " + out.strip().splitlines()[-1])

    print("== reference: livefire_m1a ==")
    fresh("A")
    run_in("A", f"python3 ../livefire_m1a.py --digits {D} --z {Z:.0f} "
                f"--trials {N} --seed {SEED}")
    ra = rows("A/livefire_log.csv")
    print(f"  {len(ra)} trials logged")

    print("== G-1: m2 + shared table, uninterrupted ==")
    fresh("B")
    run_in("B", f"python3 ../livefire_m2.py --digits {D} --z {Z:.0f} "
                f"--trials {N} --seed {SEED} --table ../tab")
    rb = rows("B/livefire_log.csv")
    check("G-1 m2(table) == m1a exact", ra == rb,
          f"{len(rb)} rows x {len(COLS)} cols")

    print("== G-2: kill -9 mid-trial + resume ==")
    fresh("C")
    proc = subprocess.Popen(
        f"python3 ../livefire_m2.py --digits {D} --z {Z:.0f} "
        f"--trials {N} --seed {SEED} --table ../tab",
        shell=True, cwd="C", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, preexec_fn=os.setsid)
    killed = False
    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            ck = json.load(open("C/ckpt.json"))
            if ck.get("n_done", 0) >= 1 and "k" in ck and ck.get("tests", 0) >= 20:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                killed = True
                print(f"  SIGKILL at trial {ck['n_done']+1}, k={ck['k']}, "
                      f"pos={ck['pos']}, tests={ck['tests']}")
                break
        except Exception:
            pass
        time.sleep(0.03)
    proc.wait()
    check("G-2 kill landed mid-trial", killed)
    out = run_in("C", f"python3 ../livefire_m2.py --digits {D} --z {Z:.0f} "
                      f"--trials {N} --seed {SEED} --table ../tab")
    resumed = next((l for l in out.splitlines() if l.startswith("resume:")), "")
    print(f"  {resumed}")
    check("G-2 resume banner shows mid-trial state", "mid-trial" in resumed)
    rc = rows("C/livefire_log.csv")
    check("G-2 interrupted+resumed == uninterrupted", rb == rc,
          f"{len(rc)} rows")

    print("== G-3: fallback (no --table), 1 trial ==")
    fresh("Dd")
    run_in("Dd", f"python3 ../livefire_m2.py --digits {D} --z {Z:.0f} "
                 f"--trials 1 --seed {SEED}")
    check("G-3 fallback == m1a (trial 1)", rows("Dd/livefire_log.csv") == ra[:1])

    print()
    if FAILS:
        print(f"P2 GATE: {len(FAILS)} FAILURE(S): {FAILS}  "
              f"[{time.time()-t0:.0f}s]"); sys.exit(1)
    print(f"P2 GATE: ALL CHECKS PASS (zero tolerance held)  [{time.time()-t0:.0f}s]")
