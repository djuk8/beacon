#!/usr/bin/env python3
"""gate_ab -- G-AB for the window-design kit. Changed code is ungated code.

Legs (toy config: D=600, zd-override 97, z=2e5, 6 trials, mock CPU driver
honoring the exact G1 blob contract from livefire_g):
  A  builder: meta consistency + residue spot-checks vs direct P mod p.
  B  class fence: at (D=9800, zd=349) the patched bits formula picks 32768
     while the original 10^7 formula picks 2048 (the silent-truncation bug
     the patch exists to prevent); patched expression present in source.
  C  row-for-row m1a equivalence: livefire_gw (batched, mock driver) vs a
     sequential m1a-walk reference sharing sieve + RNG -- gap/jl/jr/tests/
     survivors/token identical per trial.
  D  SIGKILL mid-run + resume -> final log identical to reference.
  E  reconstruction drill: token -> --reconstruct-k -> k -> p1, p2 both
     prime, jr - jl == gap, for 3 logged finds.
  F  determinism: twin run identical.
Prints: AB GATE: ALL CHECKS PASS -- <n> checks
"""
import csv, glob, json, math, os, random, shutil, signal, subprocess, sys, time
import numpy as np, gmpy2
try:
    sys.set_int_max_str_digits(2_000_000)
except AttributeError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
CFG = dict(D=600, zdo=97, z=2e5, trials=6, seed=77, rnd=32, infl=4)
CHECKS = 0


def ok(cond, msg):
    global CHECKS
    print(("  pass: " if cond else "  FAIL: ") + msg)
    if not cond: sys.exit(1)
    CHECKS += 1


MOCK = r'''import struct, sys, gmpy2
d = open(sys.argv[1], "rb").read()
m, b, c = struct.unpack("<IIQ", d[:16]); assert m == 0x31433247
nb = b // 8; off = 16; v = bytearray()
for _ in range(c):
    n = int.from_bytes(d[off:off + nb], "little"); off += nb
    v.append(1 if gmpy2.powmod(2, n - 1, n) == 1 else 0)
open(sys.argv[2], "wb").write(struct.pack("<IIQ", 0x31563247, b, c) + bytes(v))
'''


def run_gw(wdir, table, kill_after_rows=None):
    os.makedirs(wdir, exist_ok=True)
    cmd = [PY, os.path.join(HERE, "livefire_gw.py"),
           "--digits", str(CFG["D"]), "--z", str(CFG["z"]),
           "--trials", str(CFG["trials"]), "--seed", str(CFG["seed"]),
           "--zd-override", str(CFG["zdo"]), "--table", table,
           "--driver", f"{PY} {os.path.join(HERE, 'mockdrv.py')}",
           "--round", str(CFG["rnd"]), "--inflight", str(CFG["infl"])]
    p = subprocess.Popen(cmd, cwd=wdir, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    log = os.path.join(wdir, "livefire_log.csv")
    if kill_after_rows:
        while p.poll() is None:
            n = sum(1 for _ in open(log)) - 1 if os.path.exists(log) else 0
            if n >= kill_after_rows:
                os.kill(p.pid, signal.SIGKILL); p.wait()
                return None, n
            time.sleep(0.1)
        return None, sum(1 for _ in open(log)) - 1
    out, _ = p.communicate()
    return out, p.returncode


def read_rows(wdir):
    rows = list(csv.DictReader(open(os.path.join(wdir, "livefire_log.csv"))))
    return [dict(zd=int(r["zdesign"]), k=r["k"], gap=int(r["gap"]),
                 jl=int(r["jleft"]), jr=int(r["jright"]),
                 tests=int(r["tests"]), surv=int(r["survivors"]))
            for r in rows]


def reference_rows(table):
    import livefire_gw as gw
    D, zdo, z = CFG["D"], CFG["zdo"], int(CFG["z"])
    P, zd, design = gw.build_base(D, zdo)
    k0_lo = 10 ** (D - 1) // P + 1
    k0_hi = 10 ** D // P - 10 ** 7
    L = D * math.log(10); Wside = int(25 * L); W = 2 * Wside + 1
    tab_p, tab_r = gw.open_table(table, zd, z, D)
    n_med = int(np.searchsorted(
        np.asarray(tab_p[:min(len(tab_p), 10_000_000)]), W))
    small_p = np.asarray(tab_p[:n_med]).copy()
    small_r = np.asarray(tab_r[:n_med]).copy()
    random.seed(CFG["seed"])
    k0 = random.randrange(k0_lo, k0_hi)
    kb = gw.make_kbase(k0, small_p, small_r, tab_p, tab_r, n_med, 4_000_000)
    rows = []
    for t in range(CFG["trials"]):
        k = k0 + random.randrange(0, 10 ** 7)
        order = gw.sieve_trial(k, W, Wside, design, small_p, small_r,
                               tab_p, tab_r, n_med, 4_000_000, kb=kb)
        n0 = int(k) * P
        jl = jr = None; tests = 0
        for j in order:                       # verbatim m1a walk
            if j == 0 or (j < 0 and jl is not None) or (j > 0 and jr is not None):
                continue
            tests += 1
            cand = n0 + int(j)
            if gmpy2.powmod(2, cand - 1, cand) == 1 and gmpy2.is_prime(cand, 25):
                if j < 0: jl = int(j)
                else: jr = int(j)
                if jl is not None and jr is not None: break
        rows.append(dict(zd=zd, k=f"s{CFG['seed']}t{t}", gap=jr - jl, jl=jl,
                         jr=jr, tests=tests, surv=len(order)))
    return rows, P, zd


def main():
    t0 = time.time()
    open(os.path.join(HERE, "mockdrv.py"), "w").write(MOCK)
    for d in ("tabw", "r1", "r2", "rk"):
        shutil.rmtree(os.path.join(HERE, d), ignore_errors=True)
    table = os.path.join(HERE, "tabw")

    print("[A] builder with zd-override")
    r = subprocess.run([PY, os.path.join(HERE, "build_residue_table_ab.py"),
                        "--digits", str(CFG["D"]), "--z", str(CFG["z"]),
                        "--zd-override", str(CFG["zdo"]), "--out", table,
                        "--procs", "2"], capture_output=True, text=True)
    ok(r.returncode == 0, "A1 builder exits 0")
    import json
    meta = json.load(open(os.path.join(table, "meta.json")))
    ok(meta["zdesign"] == CFG["zdo"] and meta["zd_override"],
       f"A2 meta zdesign == {CFG['zdo']}, override flagged")
    import livefire_gw as gw
    P, zd, design = gw.build_base(CFG["D"], CFG["zdo"])
    dp = np.load(os.path.join(table, "primes.npy"))
    dr = np.load(os.path.join(table, "resid.npy"))
    idx = np.linspace(0, len(dp) - 1, 5).astype(int)
    ok(all(int(P % int(dp[i])) == int(dr[i]) for i in idx),
       "A3 residue spot-checks (5) == direct P mod p")

    print("[B] class fence at (D=9800, zd=349)")
    P9, _, _ = gw.build_base(9800, 349)
    khi9 = 10 ** 9800 // P9
    pick = lambda x: next(b for b in gw.CLASSES if b >= x.bit_length() + 1)
    ok(pick(khi9 * P9) == 32768 and pick(int(10 ** 7) * P9) == 2048,
       f"B1 patched formula -> 32768; original formula -> 2048 (the bug)")
    ok("(kmax * P)" in open(os.path.join(HERE, "livefire_gw.py")).read(),
       "B2 patched expression present in livefire_gw source")

    print("[C] row-for-row m1a equivalence (batched gw vs sequential walk)")
    out, rc = run_gw(os.path.join(HERE, "r1"), table)
    ok(rc == 0, "C0 gw run exits 0")
    ok("class 2048" in out, "C1 toy header class 2048 (10^600 fits)")
    got = read_rows(os.path.join(HERE, "r1"))
    ref, Pt, zdt = reference_rows(table)
    ok(len(got) == CFG["trials"], f"C2 {CFG['trials']} rows logged")
    for i, (g, rr) in enumerate(zip(got, ref)):
        ok(g == rr, f"C3 trial {i}: gap={g['gap']} jl={g['jl']} jr={g['jr']} "
                    f"tests={g['tests']} surv={g['surv']} token={g['k']} == ref")

    print("[D] SIGKILL mid-run + resume identity")
    _, pre = run_gw(os.path.join(HERE, "rk"), table, kill_after_rows=2)
    ok(pre is not None and pre < CFG["trials"],
       f"D1 kill landed mid-run ({pre}/{CFG['trials']} rows)")
    run_gw(os.path.join(HERE, "rk"), table)
    ok(read_rows(os.path.join(HERE, "rk")) == ref,
       "D2 resumed log identical to reference")

    print("[E] reconstruction drill (token -> k -> endpoints prime)")
    for i in (0, 2, 4):
        r = subprocess.run([PY, os.path.join(HERE, "livefire_gw.py"),
                            "--digits", str(CFG["D"]), "--z", str(CFG["z"]),
                            "--zd-override", str(CFG["zdo"]),
                            "--reconstruct-k", ref[i]["k"]],
                           capture_output=True, text=True)
        k = int(r.stdout.strip().splitlines()[-1])
        p1 = k * int(Pt) + ref[i]["jl"]; p2 = k * int(Pt) + ref[i]["jr"]
        ok(gmpy2.is_prime(p1, 25) and gmpy2.is_prime(p2, 25)
           and ref[i]["jr"] - ref[i]["jl"] == ref[i]["gap"],
           f"E1 trial {i}: p1, p2 prime; gap consistent (k {len(str(k))}d)")

    print("[G] >4300-digit fence (py>=3.11 int-str limit; on-box catch #2)")
    tab5 = os.path.join(HERE, "tab5")
    shutil.rmtree(tab5, ignore_errors=True)
    r = subprocess.run([PY, os.path.join(HERE, "build_residue_table_ab.py"),
                        "--digits", "5000", "--z", str(CFG["z"]),
                        "--zd-override", str(CFG["zdo"]), "--out", tab5,
                        "--procs", "2"], capture_output=True, text=True)
    ok(r.returncode == 0, "G0 D=5000 table builds")
    g5 = os.path.join(HERE, "r5")
    shutil.rmtree(g5, ignore_errors=True); os.makedirs(g5)
    cmd5 = [PY, os.path.join(HERE, "livefire_gw.py"), "--digits", "5000",
            "--z", str(CFG["z"]), "--trials", "1", "--seed", "91",
            "--zd-override", str(CFG["zdo"]), "--table", tab5,
            "--driver", f"{PY} {os.path.join(HERE, 'mockdrv.py')}",
            "--round", "32", "--inflight", "1"]
    lf = open(os.path.join(g5, "run.log"), "w")
    p5 = subprocess.Popen(cmd5, cwd=g5, stdout=lf, stderr=subprocess.STDOUT)
    ckp = os.path.join(g5, "ckpt.json")
    t0g = time.time()
    while p5.poll() is None and not os.path.exists(ckp):
        if time.time() - t0g > 180:
            os.kill(p5.pid, signal.SIGKILL); p5.wait()
            ok(False, "G1 timed out before first ckpt")
        time.sleep(0.2)
    if p5.poll() is None:
        os.kill(p5.pid, signal.SIGKILL); p5.wait()
    lf.close()
    runlog = open(os.path.join(g5, "run.log")).read()
    ok("kbase ready" in runlog and "Traceback" not in runlog,
       "G1 D=5000 run passes k0 print + kbase (no int-str crash)")
    ck = json.load(open(ckp))
    offs = [int(st["k"]) for st in ck.get("active", [])]
    ok(offs and all(0 <= o < 10 ** 7 for o in offs),
       f"G2 ckpt stores small t-offsets ({len(offs)} active, max {max(offs)})")
    r = subprocess.run([PY, os.path.join(HERE, "livefire_gw.py"),
                        "--digits", "5000", "--z", str(CFG["z"]),
                        "--zd-override", str(CFG["zdo"]),
                        "--reconstruct-k", "s91t0"],
                       capture_output=True, text=True)
    kk = int(r.stdout.strip().splitlines()[-1])
    ok(len(str(kk)) > 4300, f"G3 reconstruct prints {len(str(kk))}-digit k "
                            f"(crosses the 4300 limit)")

    print("[F] determinism (twin run)")
    run_gw(os.path.join(HERE, "r2"), table)
    ok(read_rows(os.path.join(HERE, "r2")) == ref, "F1 twin identical")

    print(f"\nAB GATE: ALL CHECKS PASS -- {CHECKS} checks [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
