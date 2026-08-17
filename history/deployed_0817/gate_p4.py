#!/usr/bin/env python3
"""P4 gate. Doctrine: changed code is ungated code. Four legs:
  A  instrument identity: Engine.pattern/.posterior vs swapstack_v1 at the
     certified config (D=400, ZS=1e5, ZT=1e6, seed 23, S8) -- exact.
  B  mechanics: smoke run; budgets respected, guided path monotone on
     accepts, eval accounting closes, both arms paired, summary written.
  C  determinism: two identical-seed runs -> identical trajectory hashes.
     SIGKILL mid-run + resume -> unit-identical to uninterrupted reference.
  D  invariants: S subset EDGE, |S| <= smax, digit drift <= bound, P in [0,1].
Prints: P4 GATE: ALL CHECKS PASS -- <n> checks
"""
import glob, json, os, shutil, signal, subprocess, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CHECKS = 0


def ok(cond, msg):
    global CHECKS
    if not cond:
        print(f"GATE FAIL: {msg}"); sys.exit(1)
    CHECKS += 1
    print(f"  pass: {msg}")


def leg_A():
    print("[A] instrument identity vs swapstack_v1 (certified config)")
    import swapstack_v1 as sv
    from p4_exchange import Engine
    rng = np.random.default_rng(23)
    fam_v1 = sv.family(8, rng)
    eng = Engine(400, 1e5, 1e6)
    fam_p4 = eng.family_from_S(fam_v1["S"])
    ok(np.array_equal(fam_v1["offs"], fam_p4["offs"]), "A1 offs identical")
    ok(np.array_equal(fam_v1["scrp"], fam_p4["scrp"]), "A2 scrp identical")
    ok(np.array_equal(fam_v1["Pmod"], fam_p4["Pmod"]), "A3 Pmod identical")
    ok(int(fam_v1["P"]) == int(fam_p4["P"]), "A4 primorial P identical")
    ok(np.array_equal(fam_v1["design"], fam_p4["design"]), "A5 design identical")
    k0 = fam_v1["k0"]
    mx = 0.0
    for i in (0, 17, 401, 9973, 55555):
        k = k0 + i
        dl1, dr1 = sv.pattern(k, fam_v1)
        dl2, dr2 = eng.pattern(k, fam_p4)
        assert np.array_equal(dl1, dl2) and np.array_equal(dr1, dr2), f"pattern k0+{i}"
        P1, E1 = sv.posterior(k, fam_v1, dl1, dr1)
        P2, E2 = eng.posterior(k, fam_p4, dl2, dr2)
        mx = max(mx, abs(P1 - P2) / max(P1, 1e-300), abs(E1 - E2) / max(E1, 1e-9))
    ok(mx == 0.0 or mx < 1e-15, f"A6 pattern+posterior exact on 5 anchors (max rel {mx:.1e})")


def run(out, seed=41, extra=()):
    return subprocess.run([sys.executable, "p4_exchange.py", "--smoke",
                           "--out", out, "--seed", str(seed), *extra],
                          capture_output=True, text=True)


def hashes(out):
    h = {}
    for f in sorted(glob.glob(f"{out}/a*_*.json")):
        u = json.load(open(f)); h[os.path.basename(f)] = u["hash"]
    return h


def leg_B():
    print("[B] mechanics + accounting (smoke)")
    shutil.rmtree("gb", ignore_errors=True)
    r = run("gb")
    ok(r.returncode == 0, "B1 smoke run exits 0")
    units = sorted(glob.glob("gb/a*_*.json"))
    ok(len(units) == 8, f"B2 4 anchors x 2 arms = 8 units ({len(units)})")
    man = json.load(open("gb/manifest.json"))
    budget = man["config"]["budget"]
    for f in units:
        u = json.load(open(f))
        ok(u["evals"] <= budget, f"B3 {os.path.basename(f)} evals {u['evals']} <= {budget}")
        ok(1 + sum(u["sl_ledger"]) == u["evals"] and u["rows"][-1]["evals"] <= u["evals"],
           f"B4 {os.path.basename(f)} eval ledger closes (1+{sum(u['sl_ledger'])}=={u['evals']})")
        if u["arm"] == "guided":
            ok(sum(u["sl_ledger"]) > 0,
               f"B8 {os.path.basename(f)} search occurred ({sum(u['sl_ledger'])} cand evals)")
            lp = [r_["logP"] for r_ in u["rows"]]
            ok(all(b > a_ for a_, b in zip(lp, lp[1:])) if len(lp) > 1 else True,
               f"B5 {os.path.basename(f)} guided path monotone")
            ok(all(r_["dlogP"] > 0 for r_ in u["rows"][1:]),
               f"B6 {os.path.basename(f)} accepts strictly positive")
    ok(os.path.exists("gb/summary.json"), "B7 summary written")
    s = json.load(open("gb/summary.json"))
    print(f"    (info) smoke paired median {s['paired_med']:+.3f} log10, "
          f"guided {s['guided_med']:+.3f}, random {s['random_med']:+.3f}, n={s['n']}")


def leg_C():
    print("[C] determinism + SIGKILL-resume identity")
    shutil.rmtree("gc1", ignore_errors=True); shutil.rmtree("gc2", ignore_errors=True)
    ok(run("gc1").returncode == 0, "C1 reference run")
    ok(run("gc2").returncode == 0, "C2 second identical-seed run")
    h1, h2 = hashes("gc1"), hashes("gc2")
    ok(h1 == h2 and len(h1) == 8, "C3 trajectory hashes identical across runs")
    shutil.rmtree("gck", ignore_errors=True)
    p = subprocess.Popen([sys.executable, "p4_exchange.py", "--smoke",
                          "--out", "gck", "--seed", "41"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while len(glob.glob("gck/a*_*.json")) < 3 and p.poll() is None:
        time.sleep(0.2)
    os.kill(p.pid, signal.SIGKILL); p.wait()
    pre = len(glob.glob("gck/a*_*.json"))
    ok(run("gck").returncode == 0, f"C4 resume after SIGKILL ({pre}/8 units survived kill)")
    ok(hashes("gck") == h1, "C5 resumed run unit-identical to reference")
    ok(pre < 8, "C6 kill landed mid-run (drill meaningful)")


def leg_D():
    print("[D] invariants")
    from p4_exchange import Engine
    eng = Engine(400, 1e5, 1e6)
    edge = set(int(x) for x in eng.EDGE)
    man = json.load(open("gb/manifest.json"))
    smax, drift = man["config"]["smax"], man["config"]["drift"]
    S0 = np.array(man["S0"], np.int64); fam0 = eng.family_from_S(S0)
    for f in sorted(glob.glob("gb/a*_*.json")):
        u = json.load(open(f))
        S = [int(x) for x in u["final_S"]]
        ok(set(S) <= edge and len(S) <= smax, f"D1 {os.path.basename(f)} S legal")
        d0 = eng.digits(int(man["anchors"][u["anchor_idx"]]), fam0)
        fam = eng.family_from_S(np.array(S, np.int64))
        d = eng.digits(int(u["final_k"]), fam)
        ok(abs(d - d0) <= drift,
           f"D2 {os.path.basename(f)} drift-from-init {abs(d-d0):.2f} <= {drift}")
        ok(0.0 <= u["rows"][0]["P"] <= 1.0, f"D3 {os.path.basename(f)} P in [0,1]")


def leg_E():
    print("[E] walker legality across seeds and configs (catch-#5 fence)")
    from p4_exchange import Engine, run_arm, legal_moves, apply_move
    eng = Engine(400, 1e5, 1e6)
    S0 = eng.DESIGN[-8:]; fam0 = eng.family_from_S(S0)
    for seed in (23, 41, 7):
        rng = np.random.default_rng(seed)
        k0 = int(rng.integers(10 ** 6, 10 ** 7)) * fam0["R"]
        u = run_arm(eng, "guided", S0, k0, budget=24, C=6, patience=6,
                    smax=24, drift=2.0, seed=seed * 7 + 1)
        ok(u["evals"] > 1 and sum(u["sl_ledger"]) > 0,
           f"E1 D=400 seed {seed}: walker searches (evals {u['evals']})")
    eng2 = Engine(1000, 2e5, 3e6)
    S2 = eng2.DESIGN[-8:]; fam2 = eng2.family_from_S(S2)
    rng = np.random.default_rng(23)
    k2 = int(rng.integers(10 ** 6, 10 ** 7)) * fam2["R"]
    d0 = eng2.digits(k2, fam2)
    n_legal = sum(1 for mv in legal_moves(eng2, S2)[:24]
                  if apply_move(eng2, [int(x) for x in S2], k2, mv, 24, 2.0, d0)
                  is not None)
    ok(n_legal >= 1, f"E2 D=1000 seed 23: legal moves from init ({n_legal}/24)")


if __name__ == "__main__":
    t0 = time.time()
    leg_A(); leg_E(); leg_B(); leg_C(); leg_D()
    print(f"\nP4 GATE: ALL CHECKS PASS -- {CHECKS} checks [{time.time()-t0:.0f}s]")
